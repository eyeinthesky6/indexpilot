import json
from contextlib import contextmanager

import src.workload_dna as workload_dna
from src.auto_indexer import review_planner_recommendations
from src.workload_dna import (
    analyze_proposed_index_snapshot,
    analyze_workload_snapshot,
    build_candidate_sql,
    derive_review_verdict,
    extract_query_pattern,
    render_review_markdown,
    validate_report_with_hypopg,
)

POSTGREST_TICK_QUERY = """
WITH pgrst_source AS (
  SELECT "public"."tick_data"."timestamp", "public"."tick_data"."price"
  FROM "public"."tick_data"
  WHERE "public"."tick_data"."symbol" = $1
    AND "public"."tick_data"."timestamp" >= $2
  ORDER BY "public"."tick_data"."timestamp" ASC
  LIMIT $3 OFFSET $4
)
SELECT * FROM pgrst_source
"""


def _snapshot(existing_index_columns=None, estimated_rows=21_010, existing_index_overrides=None):
    indexes = []
    if existing_index_columns:
        index = {
            "schema_name": "public",
            "table_name": "tick_data",
            "index_name": "idx_tick_data_existing",
            "columns": existing_index_columns,
            "is_valid": True,
            "is_ready": True,
            "is_partial": False,
            "is_expression": False,
            "access_method": "btree",
            "uses_default_opclasses": True,
            "uses_default_collations": True,
            "uses_default_sort_order": True,
        }
        index.update(existing_index_overrides or {})
        indexes.append(index)
    return {
        "schema": "public",
        "minimum_calls": 100,
        "source": {"database_name": "test", "server_version": "17"},
        "workload": [
            {
                "calls": 4_960,
                "total_exec_time_ms": 3_850.1,
                "mean_exec_time_ms": 0.776,
                "rows": 4_960,
                "query": POSTGREST_TICK_QUERY,
            }
        ],
        "table_stats": [
            {
                "schema_name": "public",
                "table_name": "tick_data",
                "estimated_rows": estimated_rows,
                "sequential_scans": 5_639,
                "index_scans": 0,
                "total_size_bytes": 3_629_056,
            }
        ],
        "columns": [
            {"schema_name": "public", "table_name": "tick_data", "column_name": name}
            for name in ("id", "symbol", "price", "timestamp")
        ],
        "indexes": indexes,
    }


def test_extracts_equality_then_range_column_from_postgrest_query():
    pattern = extract_query_pattern(
        POSTGREST_TICK_QUERY,
        {("public", "tick_data"): {"id", "symbol", "price", "timestamp"}},
    )

    assert pattern is not None
    assert pattern["candidate_columns"] == ["symbol", "timestamp"]
    assert pattern["equality_columns"] == ["symbol"]
    assert pattern["range_columns"] == ["timestamp"]
    assert "timestamp" in pattern["order_columns"]
    assert pattern["parser_backend"] == "sqlglot_postgres_ast"


def test_tenant_key_is_used_only_when_the_query_proves_it():
    columns = {("public", "action_audit"): {"tenant_id", "action_type", "timestamp", "payload"}}
    tenant_filtered = extract_query_pattern(
        """
        SELECT * FROM public.action_audit
        WHERE action_type = $1 AND tenant_id = $2 AND timestamp >= $3
        ORDER BY timestamp DESC
        """,
        columns,
    )
    global_query = extract_query_pattern(
        """
        SELECT * FROM public.action_audit
        WHERE action_type = $1 AND timestamp >= $2
        ORDER BY timestamp DESC
        """,
        columns,
    )

    assert tenant_filtered is not None
    assert tenant_filtered["candidate_columns"] == ["tenant_id", "action_type", "timestamp"]
    assert tenant_filtered["physical_scope"] == "shared_global_tenant_keyed"
    assert tenant_filtered["tenant_evidence"]["source"] == "query_equality_predicate"
    assert global_query is not None
    assert global_query["candidate_columns"] == ["action_type", "timestamp"]
    assert global_query["physical_scope"] == "shared_global"


def test_ast_parser_handles_join_aliases_without_guessing_from_projection_columns():
    pattern = extract_query_pattern(
        """
        SELECT t.symbol, a.action_type
        FROM public.tick_data AS t
        JOIN public.action_audit AS a ON a.tenant_id = t.tenant_id
        WHERE t.tenant_id = $1 AND t.timestamp >= $2
        ORDER BY t.timestamp DESC
        """,
        {
            ("public", "tick_data"): {"tenant_id", "symbol", "timestamp"},
            ("public", "action_audit"): {"tenant_id", "action_type", "timestamp"},
        },
    )

    assert pattern is not None
    assert pattern["table"] == "tick_data"
    assert pattern["candidate_columns"] == ["tenant_id", "timestamp"]
    assert "symbol" not in pattern["candidate_columns"]


def test_ast_fingerprint_groups_queries_with_different_parameter_numbers():
    columns = {("public", "tick_data"): {"symbol", "timestamp"}}
    first = extract_query_pattern(
        "SELECT * FROM tick_data WHERE symbol = $1 AND timestamp >= $2", columns
    )
    second = extract_query_pattern(
        "SELECT * FROM tick_data WHERE symbol = $7 AND timestamp >= $9", columns
    )

    assert first is not None and second is not None
    assert first["query_fingerprint"] == second["query_fingerprint"]


def test_ast_parser_rejects_mutation_and_multiple_statements():
    columns = {("public", "tick_data"): {"symbol", "timestamp"}}

    assert extract_query_pattern("DELETE FROM tick_data", columns) is None
    assert extract_query_pattern("SELECT 1; SELECT 2", columns) is None


def test_builds_advisory_candidate_for_uncovered_large_table():
    report = analyze_workload_snapshot(_snapshot())

    assert report["advisory_only"] is True
    assert report["summary"]["candidate_mutations"] == 1
    candidate = report["candidates"][0]
    assert candidate["genome"]["columns"] == ["symbol", "timestamp"]
    assert candidate["expression"]["calls"] == 4_960
    assert candidate["mutation"]["advisory_only"] is True
    assert '"symbol", "timestamp"' in candidate["mutation"]["sql"]
    assert "query" not in candidate["expression"]


def test_suppresses_candidate_when_existing_index_has_same_prefix():
    report = analyze_workload_snapshot(_snapshot(["symbol", "timestamp", "price"]))

    assert report["summary"]["candidate_mutations"] == 0
    assert report["summary"]["patterns_already_covered"] == 1


def test_does_not_treat_non_comparable_existing_indexes_as_coverage():
    non_comparable_shapes = [
        {"is_valid": False},
        {"is_ready": False},
        {"is_partial": True},
        {"is_expression": True},
        {"access_method": "gin"},
        {"uses_default_opclasses": False},
        {"uses_default_collations": False},
        {"uses_default_sort_order": False},
    ]

    for shape in non_comparable_shapes:
        report = analyze_workload_snapshot(
            _snapshot(["symbol", "timestamp"], existing_index_overrides=shape)
        )
        assert report["summary"]["candidate_mutations"] == 1
        assert report["summary"]["patterns_already_covered"] == 0


def test_skips_small_table_to_avoid_index_noise():
    report = analyze_workload_snapshot(_snapshot(estimated_rows=12))

    assert report["summary"]["candidate_mutations"] == 0
    assert report["summary"]["patterns_skipped_as_small_tables"] == 1


def test_candidate_sql_is_concurrent_and_review_only_text():
    sql = build_candidate_sql("public", "tick_data", ["symbol", "timestamp"])

    assert sql == (
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_tick_data_symbol_timestamp_dna" '
        'ON "public"."tick_data" ("symbol", "timestamp");'
    )


def test_marks_empty_workload_as_missing_evidence():
    snapshot = _snapshot()
    snapshot["workload"] = []

    report = analyze_workload_snapshot(snapshot)

    assert report["summary"]["workload_stats_empty"] is True
    assert report["summary"]["candidate_mutations"] == 0
    assert any("window is empty" in item for item in report["limits"])


class _FakeHypoPGCursor:
    def __init__(self, initial_columns=None):
        self._row = None
        self._columns = initial_columns

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT EXISTS"):
            self._row = (True,)
        elif statement == "SHOW server_version_num":
            self._row = (170000,)
        elif statement.startswith("SELECT * FROM hypopg_create_index"):
            ddl = parameters[0]
            if '("symbol", "timestamp")' in ddl:
                self._columns = ("symbol", "timestamp")
            elif '("timestamp")' in ddl:
                self._columns = ("timestamp",)
            elif '("symbol")' in ddl:
                self._columns = ("symbol",)
            self._row = (1, "<1>trial")
        elif statement.startswith("SELECT hypopg_reset"):
            self._columns = None
            self._row = (None,)
        elif statement.startswith("EXPLAIN"):
            costs = {
                None: 100.0,
                ("symbol", "timestamp"): 30.0,
                ("timestamp",): 10.0,
                ("symbol",): 70.0,
            }
            plan = {
                "Node Type": "Seq Scan" if self._columns is None else "Index Scan",
                "Total Cost": costs[self._columns],
                "Plan Rows": 100,
            }
            if self._columns is not None:
                plan["Index Name"] = "<1>trial"
            self._row = ([{"Plan": plan}],)
        else:
            self._row = None

    def fetchone(self):
        return self._row

    def close(self):
        return None


class _FakeHypoPGConnection:
    def __init__(self, initial_columns=None):
        self.cursor_instance = _FakeHypoPGCursor(initial_columns)

    def rollback(self):
        return None

    def cursor(self):
        return self.cursor_instance


def test_hypopg_selects_cheaper_single_column_alternative(monkeypatch):
    @contextmanager
    def fake_connection():
        yield _FakeHypoPGConnection()

    monkeypatch.setattr(workload_dna, "get_connection", fake_connection)
    snapshot = _snapshot()
    report = analyze_workload_snapshot(snapshot)

    validated = validate_report_with_hypopg(snapshot, report)

    assert validated["planner_validation"]["status"] == "completed"
    assert validated["summary"]["planner_validated_mutations"] == 1
    recommendation = validated["planner_recommendations"][0]
    assert recommendation["columns"] == ["timestamp"]
    assert recommendation["best_cost_reduction_pct"] == 90.0
    assert '"timestamp"' in recommendation["sql"]
    assert POSTGREST_TICK_QUERY.strip() not in json.dumps(validated)


def test_hypopg_clears_pooled_session_state_before_baseline(monkeypatch):
    connection = _FakeHypoPGConnection(initial_columns=("timestamp",))

    @contextmanager
    def fake_connection():
        yield connection

    monkeypatch.setattr(workload_dna, "get_connection", fake_connection)
    snapshot = _snapshot()

    validated = validate_report_with_hypopg(snapshot, analyze_workload_snapshot(snapshot))

    baseline = validated["candidates"][0]["planner_validation"]["baseline"]
    assert baseline["total_cost"] == 100.0
    assert connection.cursor_instance._columns is None


def test_auto_indexer_admits_hypopg_evidence_but_does_not_apply_it(monkeypatch):
    @contextmanager
    def fake_connection():
        yield _FakeHypoPGConnection()

    monkeypatch.setattr(workload_dna, "get_connection", fake_connection)
    snapshot = _snapshot()
    validated = validate_report_with_hypopg(snapshot, analyze_workload_snapshot(snapshot))

    review = review_planner_recommendations(validated)

    assert review["status"] == "admitted"
    assert review["decision_owner"] == "src.auto_indexer"
    assert review["accepted"][0]["eligible_for_apply"] is False
    assert review["accepted"][0]["apply_blockers"] == [
        "production_copy_benchmark_required",
        "operator_approval_required",
    ]


def test_auto_indexer_rejects_unproven_tenant_physical_scope():
    report = {
        "planner_validation": {"status": "completed"},
        "planner_recommendations": [
            {
                "schema": "public",
                "table": "action_audit",
                "columns": ["tenant_id", "timestamp"],
                "status": "planner_validated",
                "best_cost_reduction_pct": 80.0,
                "physical_scope": "shared_global_tenant_keyed",
                "tenant_evidence": {"tenant_key": "tenant_id", "source": "table_metadata"},
            }
        ],
    }

    review = review_planner_recommendations(report)

    assert review["status"] == "no_candidates_admitted"
    assert review["skipped"][0]["reason"] == "tenant_key_not_proven_by_workload"


def test_proposed_index_review_supports_equality_only_workload_without_raw_sql():
    snapshot = _snapshot()
    snapshot["workload"][0]["query"] = "SELECT * FROM tick_data WHERE symbol = $1"
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol"],
    }

    report = analyze_proposed_index_snapshot(snapshot, proposal)

    assert report["summary"]["matching_workload_fingerprints"] == 1
    assert report["candidates"][0]["validation_mode"] == "exact_shape"
    assert report["candidates"][0]["expression"]["equality_columns"] == ["symbol"]
    assert snapshot["workload"][0]["query"] not in json.dumps(report)


def test_proposed_index_review_reports_only_comparable_existing_overlap():
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol", "timestamp"],
    }

    covered = analyze_proposed_index_snapshot(_snapshot(["symbol", "timestamp"]), proposal)
    partial = analyze_proposed_index_snapshot(
        _snapshot(
            ["symbol", "timestamp"],
            existing_index_overrides={"is_partial": True},
        ),
        proposal,
    )

    assert covered["existing_overlap"] is True
    assert derive_review_verdict(covered)["status"] == "existing_overlap"
    assert partial["existing_overlap"] is False


def test_exact_proposed_index_can_be_worth_benchmarking_after_hypopg_admission(monkeypatch):
    @contextmanager
    def fake_connection():
        yield _FakeHypoPGConnection()

    monkeypatch.setattr(workload_dna, "get_connection", fake_connection)
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol", "timestamp"],
    }
    report = analyze_proposed_index_snapshot(_snapshot(), proposal)

    validated = validate_report_with_hypopg(_snapshot(), report)
    validated["auto_indexer_review"] = review_planner_recommendations(validated)
    verdict = derive_review_verdict(validated)
    markdown = render_review_markdown({**validated, "verdict": verdict})

    alternatives = validated["candidates"][0]["planner_validation"]["alternatives"]
    assert [item["columns"] for item in alternatives] == [["symbol", "timestamp"]]
    assert verdict["status"] == "worth_benchmarking"
    assert "planner evidence only" in markdown
    assert POSTGREST_TICK_QUERY.strip() not in markdown


def test_completed_hypopg_run_stays_inconclusive_when_candidate_explain_failed():
    report = analyze_proposed_index_snapshot(
        _snapshot(),
        {
            "schema": "public",
            "table": "tick_data",
            "columns": ["symbol", "timestamp"],
        },
    )
    report["planner_validation"] = {"requested": True, "status": "completed"}
    report["candidates"][0]["planner_validation"] = {
        "status": "inconclusive",
        "reason": "explain_failed",
    }
    report["auto_indexer_review"] = {
        "status": "no_candidates_admitted",
        "accepted": [],
    }

    assert derive_review_verdict(report)["status"] == "inconclusive"
