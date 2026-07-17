import json
from contextlib import contextmanager

import pytest

import src.auto_indexer as auto_indexer
import src.workload_dna as workload_dna
from src.auto_indexer import review_planner_recommendations
from src.workload_dna import (
    analyze_index_sprawl_snapshot,
    analyze_proposed_index_snapshot,
    analyze_workload_snapshot,
    build_candidate_sql,
    build_index_review_report,
    build_migration_review_report,
    build_workload_readiness_report,
    compare_index_review_reports,
    derive_review_verdict,
    extract_query_pattern,
    render_review_markdown,
    render_review_sarif,
    sanitize_workload_snapshot,
    validate_report_with_hypopg,
    validate_sanitized_workload_snapshot,
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


def test_sanitized_snapshot_removes_raw_sql_and_database_identity():
    live_snapshot = _snapshot()
    live_snapshot["source"]["database_name"] = "private-production"

    sanitized = sanitize_workload_snapshot(live_snapshot)
    serialized = json.dumps(sanitized)

    assert sanitized["report_type"] == "indexpilot_sanitized_workload_snapshot"
    assert sanitized["snapshot_version"] == 1
    assert sanitized["sanitized"] is True
    assert "workload" not in sanitized
    assert "private-production" not in serialized
    assert POSTGREST_TICK_QUERY.strip() not in serialized
    assert sanitized["summary"]["workload_query_fingerprints"] == 1
    assert sanitized["workload_patterns"][0]["equality_columns"] == ["symbol"]


def test_offline_snapshot_reviews_exact_index_without_database_access(monkeypatch):
    sanitized = sanitize_workload_snapshot(_snapshot())

    def fail_if_connected(**kwargs):
        raise AssertionError(f"offline review attempted database access: {kwargs}")

    monkeypatch.setattr(workload_dna, "collect_workload_snapshot", fail_if_connected)
    report = build_index_review_report(
        "CREATE INDEX CONCURRENTLY idx_tick_symbol_time "
        "ON public.tick_data (symbol, timestamp)",
        snapshot=sanitized,
    )

    assert report["source_mode"] == "sanitized_offline_snapshot"
    assert report["summary"]["matching_workload_fingerprints"] == 1
    assert report["candidates"][0]["expression"]["calls"] == 4_960
    assert report["planner_validation"]["status"] == "not_requested"


def test_sanitized_snapshot_preserves_equality_only_evidence():
    live_snapshot = _snapshot()
    live_snapshot["workload"][0]["query"] = (
        "SELECT price FROM public.tick_data WHERE symbol = $1"
    )
    sanitized = sanitize_workload_snapshot(live_snapshot)

    report = build_index_review_report(
        "CREATE INDEX CONCURRENTLY idx_tick_symbol ON public.tick_data (symbol)",
        snapshot=sanitized,
    )

    assert sanitized["workload_patterns"][0]["equality_columns"] == ["symbol"]
    assert report["summary"]["matching_workload_fingerprints"] == 1


def test_sanitized_snapshot_reviews_migration_without_database_access(monkeypatch):
    sanitized = sanitize_workload_snapshot(_snapshot())

    def fail_if_connected(**kwargs):
        raise AssertionError(f"offline migration review attempted database access: {kwargs}")

    monkeypatch.setattr(workload_dna, "collect_workload_snapshot", fail_if_connected)
    report = build_migration_review_report(
        "CREATE INDEX CONCURRENTLY idx_tick_symbol_time "
        "ON public.tick_data (symbol, timestamp);",
        snapshot=sanitized,
    )

    assert report["source_mode"] == "sanitized_offline_snapshot"
    assert report["summary"]["reviewed_indexes"] == 1
    assert report["reviews"][0]["summary"]["matching_workload_fingerprints"] == 1


def test_offline_snapshot_rejects_raw_query_fields():
    sanitized = sanitize_workload_snapshot(_snapshot())
    sanitized["workload_patterns"][0]["query"] = "SELECT secret FROM private_table"

    with pytest.raises(ValueError, match="offline_snapshot_contains_private_source_fields"):
        validate_sanitized_workload_snapshot(sanitized)


def _two_fingerprint_snapshot():
    snapshot = _snapshot()
    query_1 = "SELECT price FROM public.tick_data WHERE symbol = $1 AND timestamp >= $2 ORDER BY timestamp"
    query_2 = "SELECT id FROM public.tick_data WHERE symbol = $1 AND timestamp >= $2 ORDER BY timestamp"

    snapshot["workload"] = [
        {
            "calls": 2_000,
            "total_exec_time_ms": 1000.0,
            "mean_exec_time_ms": 0.5,
            "rows": 2_000,
            "query": query_1,
        },
        {
            "calls": 3_000,
            "total_exec_time_ms": 2100.0,
            "mean_exec_time_ms": 0.7,
            "rows": 3_000,
            "query": query_2,
        },
    ]
    return snapshot

def test_multiple_fingerprints_characterize_workload_discovery():
    report = analyze_workload_snapshot(_two_fingerprint_snapshot())

    # One candidate is emitted
    assert report["summary"]["candidate_mutations"] == 1
    candidate = report["candidates"][0]

    # Candidate column support counts distinct supporting fingerprints
    expression = candidate["expression"]
    assert expression["calls"] == 5_000
    assert expression["total_exec_time_ms"] == 3100.0
    assert expression["max_mean_exec_time_ms"] == 0.7

    assert len(expression["query_fingerprints"]) == 2
    assert len(set(expression["query_fingerprints"])) == 2

    # Sanitize removes query text
    sanitized = sanitize_workload_snapshot(_two_fingerprint_snapshot())
    assert sanitized["summary"]["workload_query_fingerprints"] == 2

    serialized = json.dumps(sanitized)
    assert "SELECT price" not in serialized
    assert "SELECT id" not in serialized

def test_multiple_fingerprints_characterize_exact_review():
    snapshot = _two_fingerprint_snapshot()
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol", "timestamp", "price"],
    }

    report = analyze_proposed_index_snapshot(snapshot, proposal)

    assert report["summary"]["matching_workload_fingerprints"] == 2
    expression = report["candidates"][0]["expression"]

    # Candidate column support counts distinct supporting fingerprints
    assert expression["candidate_column_support"] == {
        "symbol": 2,
        "timestamp": 2,
        "price": 0,
    }
    assert expression["unused_trailing_columns"] == ["price"]


def test_multiple_fingerprints_offline_sanitized_review():
    snapshot = _two_fingerprint_snapshot()
    sanitized = sanitize_workload_snapshot(snapshot)
    
    candidate_sql = "CREATE INDEX idx_tick_data ON public.tick_data (symbol, timestamp);"

    report = build_index_review_report(candidate_sql, snapshot=sanitized, validate_hypopg=False)

    assert report["summary"]["matching_workload_fingerprints"] == 2
    expression = report["candidates"][0]["expression"]
    assert expression["calls"] == 5_000
    assert expression["total_exec_time_ms"] == 3100.0

    serialized = json.dumps(report)
    assert "SELECT price" not in serialized
    assert "SELECT id" not in serialized
    assert "db_system" not in serialized
    assert "pg_stat_statements_total_exec_time_ms" not in serialized


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
        'CREATE INDEX CONCURRENTLY "idx_tick_data_symbol_timestamp_dna" '
        'ON "public"."tick_data" ("symbol", "timestamp");'
    )


def test_generated_candidate_name_is_disambiguated_instead_of_silently_skipped():
    sql = build_candidate_sql(
        "public",
        "tick_data",
        ["symbol", "timestamp"],
        existing_index_names={"idx_tick_data_symbol_timestamp_dna"},
    )

    assert '"idx_tick_data_symbol_timestamp_dna"' not in sql
    assert "IF NOT EXISTS" not in sql
    assert sql.startswith("CREATE INDEX CONCURRENTLY ")


def test_marks_empty_workload_as_missing_evidence():
    snapshot = _snapshot()
    snapshot["workload"] = []

    report = analyze_workload_snapshot(snapshot)

    assert report["summary"]["workload_stats_empty"] is True
    assert report["summary"]["candidate_mutations"] == 0
    assert any("window is empty" in item for item in report["limits"])


def test_discovery_skips_quoted_identifiers_instead_of_emitting_wrong_ddl():
    snapshot = _snapshot()
    snapshot["workload"][0]["query"] = (
        'SELECT * FROM public."TickData" WHERE "Symbol" = $1 AND "Timestamp" >= $2'
    )
    for row in snapshot["columns"]:
        row["table_name"] = "TickData"
        row["column_name"] = str(row["column_name"]).title()
    snapshot["table_stats"][0]["table_name"] = "TickData"

    report = analyze_workload_snapshot(snapshot)

    assert report["summary"]["candidate_mutations"] == 0
    assert report["summary"]["patterns_skipped_as_unsupported_identifiers"] == 1
    assert any("unsupported identifiers" in item for item in report["limits"])


def test_discovery_skips_partitioned_parent_instead_of_emitting_invalid_concurrent_ddl():
    snapshot = _snapshot()
    snapshot["table_stats"][0]["relation_kind"] = "p"

    report = analyze_workload_snapshot(snapshot)

    assert report["summary"]["candidate_mutations"] == 0
    assert report["summary"]["patterns_skipped_as_partitioned_parents"] == 1
    assert any("Partitioned parent" in item for item in report["limits"])


def test_exact_concurrent_proposal_on_partitioned_parent_has_a_deployment_blocker():
    snapshot = _snapshot()
    snapshot["table_stats"][0]["relation_kind"] = "p"
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol"],
        "concurrently": True,
        "normalized_sql": ("CREATE INDEX CONCURRENTLY idx_tick_symbol ON public.tick_data(symbol)"),
    }

    report = analyze_proposed_index_snapshot(snapshot, proposal)

    assert report["operational_notes"] == [
        {
            "code": "partitioned_parent_concurrent_build_unsupported",
            "level": "blocker",
            "message": (
                "PostgreSQL cannot use CREATE INDEX CONCURRENTLY on a partitioned parent; "
                "review leaf-partition deployment separately."
            ),
        }
    ]


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


def test_auto_indexer_uses_a_safe_threshold_and_unrounded_decision_value(monkeypatch):
    monkeypatch.setitem(auto_indexer._COST_CONFIG, "MIN_IMPROVEMENT_PCT", -5.0)
    report = {
        "planner_validation": {"status": "completed"},
        "planner_recommendations": [
            {
                "schema": "public",
                "table": "tick_data",
                "columns": ["symbol"],
                "status": "planner_validated",
                "best_cost_reduction_pct": 20.0,
                "decision_cost_reduction_pct": 19.996,
                "physical_scope": "shared_global",
                "tenant_evidence": {},
            }
        ],
    }

    review = review_planner_recommendations(report)

    assert review["minimum_improvement_pct"] == 20.0
    assert review["status"] == "no_candidates_admitted"
    assert review["skipped"][0]["reason"] == "below_auto_indexer_improvement_threshold"


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


def test_exact_review_exposes_trailing_key_support_without_overclaiming():
    snapshot = _snapshot()
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol", "timestamp", "price"],
    }

    report = analyze_proposed_index_snapshot(snapshot, proposal)
    expression = report["candidates"][0]["expression"]

    assert expression["candidate_column_support"] == {
        "symbol": 1,
        "timestamp": 1,
        "price": 0,
    }
    assert expression["unused_trailing_columns"] == ["price"]
    assert any(
        note["code"] == "unused_trailing_columns_not_observed"
        for note in report["operational_notes"]
    )


def test_exact_review_does_not_claim_matching_evidence_when_none_exists():
    snapshot = _snapshot()
    snapshot["workload"][0]["query"] = "SELECT * FROM tick_data WHERE price = $1"

    report = analyze_proposed_index_snapshot(
        snapshot,
        {"schema": "public", "table": "tick_data", "columns": ["symbol"]},
    )

    reasons = report["candidates"][0]["reason"]
    assert report["summary"]["matching_workload_fingerprints"] == 0
    assert any("no matching workload" in reason for reason in reasons)
    assert not any("matching workload evidence was aggregated" in reason for reason in reasons)


def test_exact_review_blocks_existing_name_with_a_different_shape():
    snapshot = _snapshot(["price"])
    snapshot["indexes"][0]["index_name"] = "idx_tick_data_candidate"

    report = analyze_proposed_index_snapshot(
        snapshot,
        {
            "schema": "public",
            "table": "tick_data",
            "columns": ["symbol", "timestamp"],
            "index_name": "idx_tick_data_candidate",
            "if_not_exists": True,
        },
    )

    assert any(
        note["code"] == "index_name_already_exists_for_different_shape"
        and note["level"] == "blocker"
        for note in report["operational_notes"]
    )


def test_read_only_workload_filter_keeps_leading_comment_queries():
    rows = [
        {"query": "DELETE FROM tick_data"},
        {"query": "/* application=checkout */ SELECT * FROM tick_data"},
    ]

    selected = workload_dna._filter_read_only_workload_rows(rows, limit=10)

    assert [row["query"] for row in selected] == [rows[1]["query"]]


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


def test_migration_review_reuses_one_snapshot_and_reports_internal_overlap(monkeypatch):
    calls = []

    def fake_collect(**kwargs):
        calls.append(kwargs)
        return _snapshot()

    monkeypatch.setattr(workload_dna, "collect_workload_snapshot", fake_collect)
    report = build_migration_review_report(
        """
        ALTER TABLE tick_data ADD COLUMN source text;
        CREATE INDEX CONCURRENTLY idx_tick_symbol ON public.tick_data (symbol);
        CREATE INDEX CONCURRENTLY idx_tick_symbol_time
          ON public.tick_data (symbol, timestamp);
        """
    )

    assert len(calls) == 1
    assert report["report_type"] == "indexpilot_migration_review"
    assert report["migration"] == {
        "statement_count": 3,
        "ignored_non_index_statements": 1,
        "reviewed_index_statements": 2,
    }
    assert report["summary"]["reviewed_indexes"] == 2
    assert report["summary"]["migration_overlap_findings"] == 1
    assert report["migration_overlap_findings"][0]["type"] == "leading_prefix_overlap"
    assert report["migration_overlap_findings"][0]["safe_to_drop"] is False


def test_migration_review_detects_schema_wide_duplicate_index_names():
    findings = workload_dna._migration_overlap_findings(
        [
            {
                "schema": "public",
                "table": "orders",
                "index_name": "idx_status",
                "columns": ["status"],
                "statement_number": 1,
            },
            {
                "schema": "public",
                "table": "invoices",
                "index_name": "idx_status",
                "columns": ["status"],
                "statement_number": 2,
            },
        ]
    )

    assert findings == [
        {
            "type": "duplicate_index_name",
            "schema": "public",
            "index_name": "idx_status",
            "left_table": "orders",
            "right_table": "invoices",
            "left_statement": 1,
            "right_statement": 2,
            "action": "rename_index",
            "safe_to_drop": False,
        }
    ]


def test_negative_exact_review_markdown_does_not_print_actionable_ddl():
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol", "timestamp"],
    }
    report = analyze_proposed_index_snapshot(_snapshot(["symbol", "timestamp"]), proposal)
    report["verdict"] = derive_review_verdict(report)

    markdown = render_review_markdown(report)

    assert "no CREATE INDEX action is supported" in markdown
    assert "```sql" not in markdown


def test_readiness_distinguishes_required_and_optional_evidence(monkeypatch):
    snapshot = _snapshot()
    snapshot["source"].update(
        {
            "server_version_num": 170000,
            "transaction_read_only": "on",
            "pg_stat_statements_available": True,
            "hypopg_available": False,
            "pg_stat_statements_reset_at": "2026-07-01T00:00:00Z",
            "database_stats_reset_at": "2026-07-01T00:00:00Z",
        }
    )
    monkeypatch.setattr(workload_dna, "collect_workload_snapshot", lambda **kwargs: snapshot)

    report = build_workload_readiness_report(min_calls=100)

    assert report["summary"]["status"] == "ready_without_planner_validation"
    assert (
        next(check for check in report["checks"] if check["code"] == "hypopg")["status"]
        == "optional"
    )
    assert "--hypopg" not in report["next_command"]


def test_readiness_reports_missing_pg_stat_statements_as_not_ready(monkeypatch):
    snapshot = _snapshot()
    snapshot["workload"] = []
    snapshot["source"].update(
        {
            "server_version_num": 170000,
            "transaction_read_only": "on",
            "pg_stat_statements_available": False,
            "hypopg_available": False,
        }
    )
    monkeypatch.setattr(workload_dna, "collect_workload_snapshot", lambda **kwargs: snapshot)

    report = build_workload_readiness_report()

    assert report["summary"]["status"] == "not_ready"


def test_sprawl_review_is_conservative_and_never_emits_drop_sql():
    snapshot = _snapshot()
    common = {
        "schema_name": "public",
        "table_name": "tick_data",
        "is_valid": True,
        "is_ready": True,
        "is_partial": False,
        "is_expression": False,
        "access_method": "btree",
        "uses_default_opclasses": True,
        "uses_default_collations": True,
        "uses_default_sort_order": True,
        "include_columns": [],
        "is_unique": False,
        "is_primary": False,
        "is_exclusion": False,
        "is_constraint_owned": False,
    }
    snapshot["indexes"] = [
        {
            **common,
            "index_name": "idx_tick_symbol",
            "columns": ["symbol"],
            "index_scans": 0,
            "index_size_bytes": 1024,
        },
        {
            **common,
            "index_name": "idx_tick_symbol_time",
            "columns": ["symbol", "timestamp"],
            "index_scans": 50,
            "index_size_bytes": 4096,
        },
        {
            **common,
            "index_name": "idx_tick_partial",
            "columns": ["symbol"],
            "is_partial": True,
        },
    ]

    report = analyze_index_sprawl_snapshot(snapshot)

    assert report["summary"]["overlap_findings"] == 1
    assert report["summary"]["skipped_non_comparable_indexes"] == 1
    finding = report["findings"][0]
    assert finding["type"] == "leading_prefix_overlap"
    assert finding["safe_to_drop"] is False
    assert all("drop_sql" not in item for item in report["findings"])


def test_sprawl_preserves_constraint_protection_and_unique_semantics():
    snapshot = _snapshot()
    base = {
        "schema_name": "public",
        "table_name": "tick_data",
        "columns": ["symbol"],
        "include_columns": [],
        "is_valid": True,
        "is_ready": True,
        "is_partial": False,
        "is_expression": False,
        "access_method": "btree",
        "uses_default_opclasses": True,
        "uses_default_collations": True,
        "uses_default_sort_order": True,
        "is_primary": False,
        "is_exclusion": False,
    }
    snapshot["indexes"] = [
        {
            **base,
            "index_name": "tick_symbol_key",
            "is_unique": True,
            "is_constraint_owned": True,
        },
        {
            **base,
            "index_name": "idx_tick_symbol",
            "is_unique": False,
            "is_constraint_owned": False,
        },
    ]

    finding = analyze_index_sprawl_snapshot(snapshot)["findings"][0]

    assert finding["type"] == "leading_prefix_overlap"
    assert finding["constraint_protected"] is True


def test_post_deploy_comparison_reports_usage_without_claiming_performance():
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol", "timestamp"],
        "index_name": "idx_tick_data_symbol_timestamp",
    }
    before_snapshot = _snapshot()
    after_snapshot = _snapshot(
        ["symbol", "timestamp"],
        existing_index_overrides={
            "index_name": "idx_tick_data_symbol_timestamp",
            "index_scans": 12,
            "index_size_bytes": 8192,
        },
    )
    after_snapshot["workload"][0]["calls"] = 5_100
    for snapshot in (before_snapshot, after_snapshot):
        snapshot["source"].update(
            {
                "pg_stat_statements_reset_at": "2026-07-01T00:00:00Z",
                "database_stats_reset_at": "2026-07-01T00:00:00Z",
            }
        )
    before = analyze_proposed_index_snapshot(before_snapshot, proposal)
    after = analyze_proposed_index_snapshot(after_snapshot, proposal)
    before["generated_at"] = "2026-07-10T00:00:00+00:00"
    after["generated_at"] = "2026-07-14T00:00:00+00:00"

    observation = compare_index_review_reports(before, after)

    assert observation["verdict"]["status"] == "usage_observed"
    assert observation["observed_index"]["index_scans"] == 12
    assert observation["workload_delta"]["matching_calls"] == 140
    assert "improved latency" not in observation["verdict"]["reason"]
    assert any("not that the index improved latency" in item for item in observation["limits"])


def test_post_deploy_comparison_rejects_different_sources():
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol"],
    }
    before = analyze_proposed_index_snapshot(_snapshot(), proposal)
    after = analyze_proposed_index_snapshot(_snapshot(), proposal)
    before["generated_at"] = "2026-07-10T00:00:00+00:00"
    after["generated_at"] = "2026-07-14T00:00:00+00:00"
    after["source"]["database_name"] = "other"

    with pytest.raises(ValueError, match="^source_database_mismatch$"):
        compare_index_review_reports(before, after)


def test_post_deploy_comparison_requires_source_identity_and_monotonic_counters():
    proposal = {"schema": "public", "table": "tick_data", "columns": ["symbol"]}
    before = analyze_proposed_index_snapshot(_snapshot(), proposal)
    after = analyze_proposed_index_snapshot(_snapshot(), proposal)
    before["generated_at"] = "2026-07-10T00:00:00+00:00"
    after["generated_at"] = "2026-07-14T00:00:00+00:00"
    for report in (before, after):
        report["source"]["pg_stat_statements_reset_at"] = "2026-07-01T00:00:00Z"
    after["candidates"][0]["expression"]["total_exec_time_ms"] = 1.0

    observation = compare_index_review_reports(before, after)

    assert observation["workload_delta"] is None
    del before["source"]["database_name"]
    with pytest.raises(ValueError, match="^source_database_missing$"):
        compare_index_review_reports(before, after)


def test_sarif_contains_verdicts_without_raw_workload_sql():
    proposal = {
        "schema": "public",
        "table": "tick_data",
        "columns": ["symbol"],
        "statement_number": 4,
    }
    review = analyze_proposed_index_snapshot(_snapshot(), proposal)
    review["verdict"] = derive_review_verdict(review)

    sarif = render_review_sarif(review, artifact_uri="migrations/004.sql")
    serialized = json.dumps(sarif)

    assert sarif["version"] == "2.1.0"
    result = sarif["runs"][0]["results"][0]
    assert result["ruleId"].startswith("indexpilot.")
    assert result["properties"]["statementNumber"] == 4
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == (
        "migrations/004.sql"
    )
    assert POSTGREST_TICK_QUERY.strip() not in serialized


def test_migration_overlap_is_a_sarif_result_and_gate_status():
    report = {
        "report_type": "indexpilot_migration_review",
        "reviews": [],
        "migration_overlap_findings": [
            {
                "type": "duplicate_index_name",
                "schema": "public",
                "index_name": "idx_status",
                "left_table": "orders",
                "right_table": "invoices",
                "left_statement": 1,
                "right_statement": 2,
            }
        ],
    }

    sarif = render_review_sarif(report, artifact_uri="migration.sql")
    result = sarif["runs"][0]["results"][0]

    assert result["ruleId"] == "indexpilot.existing_overlap"
    assert result["properties"]["findingType"] == "duplicate_index_name"
    assert result["properties"]["relatedStatementNumber"] == 2
