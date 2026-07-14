"""Read-only workload DNA analysis for PostgreSQL.

This module turns PostgreSQL's aggregate workload statistics into explainable,
advisory-only composite-index candidates. It never executes DDL and it does not
store raw query text in its report.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.sql_parser import (
    PARSER_BACKEND,
    SQLPatternError,
    extract_postgres_query_pattern,
    parse_read_only_query,
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def extract_query_pattern(
    query: str,
    table_columns: dict[tuple[str, str], set[str]],
    default_schema: str = "public",
) -> dict[str, Any] | None:
    """Extract index-relevant columns through the PostgreSQL AST adapter."""
    return extract_postgres_query_pattern(query, table_columns, default_schema)


def _has_covering_prefix(existing_indexes: list[dict[str, Any]], columns: list[str]) -> bool:
    wanted = [column.lower() for column in columns]
    for index in existing_indexes:
        existing = [str(column).lower() for column in index.get("columns", []) if column]
        if existing[: len(wanted)] == wanted:
            return True
    return False


def _quote_identifier(identifier: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Unsupported PostgreSQL identifier: {identifier!r}")
    return f'"{identifier}"'


def build_candidate_sql(schema: str, table: str, columns: list[str]) -> str:
    """Build reviewable DDL text. This function does not execute it."""
    raw_name = "idx_" + "_".join([table, *columns, "dna"])
    if len(raw_name) > 63:
        digest = hashlib.sha256(raw_name.encode("utf-8")).hexdigest()[:8]
        raw_name = f"{raw_name[:54]}_{digest}"
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    return (
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        f"{_quote_identifier(raw_name)} ON {_quote_identifier(schema)}.{_quote_identifier(table)} "
        f"({quoted_columns});"
    )


def build_hypothetical_sql(schema: str, table: str, columns: list[str]) -> str:
    """Build the ordinary CREATE INDEX text expected by HypoPG."""
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    return (
        f"CREATE INDEX ON {_quote_identifier(schema)}.{_quote_identifier(table)} ({quoted_columns})"
    )


def _candidate_variants(candidate: dict[str, Any]) -> list[list[str]]:
    """Return small index alternatives for planner comparison.

    Equality-first composites are a useful heuristic, but LIMIT and ORDER BY can
    make a smaller ordering index cheaper. HypoPG should compare both shapes.
    """
    variants: list[list[str]] = []

    def add(columns: list[str]) -> None:
        if columns and columns not in variants:
            variants.append(columns)

    genome_columns = [str(column) for column in candidate["genome"]["columns"]]
    add(genome_columns)
    for length in range(1, len(genome_columns)):
        add(genome_columns[:length])

    expression = candidate.get("expression", {})
    tenant_key = candidate.get("tenant_evidence", {}).get("tenant_key")
    if tenant_key:
        for column in expression.get("range_columns", []) + expression.get("order_columns", []):
            add([str(tenant_key), str(column)])
    for column in expression.get("order_columns", []):
        add([str(column)])
    for column in expression.get("range_columns", []):
        add([str(column)])
    for column in expression.get("equality_columns", []):
        add([str(column)])
    return variants


def _safe_explain_query(query: str) -> str:
    """Accept one read-only workload statement for EXPLAIN without ANALYZE."""
    statement = query.strip()
    try:
        parse_read_only_query(statement)
    except SQLPatternError as exc:
        raise ValueError(str(exc)) from exc
    return statement


def _summarize_plan(raw_plan: Any) -> dict[str, Any]:
    """Keep planner evidence without retaining raw SQL or full plan text."""
    if isinstance(raw_plan, str):
        raw_plan = json.loads(raw_plan)
    if not isinstance(raw_plan, list) or not raw_plan:
        raise ValueError("unexpected_explain_shape")
    document = raw_plan[0]
    if not isinstance(document, dict) or not isinstance(document.get("Plan"), dict):
        raise ValueError("unexpected_explain_shape")
    plan = document["Plan"]

    node_types: list[str] = []
    index_names: list[str] = []

    def walk(node: dict[str, Any]) -> None:
        node_type = str(node.get("Node Type", "Unknown"))
        _append_unique(node_types, node_type)
        index_name = node.get("Index Name")
        if index_name:
            _append_unique(index_names, str(index_name))
        for child in node.get("Plans", []):
            if isinstance(child, dict):
                walk(child)

    walk(plan)
    plan_fingerprint = hashlib.sha256(
        json.dumps(plan, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return {
        "total_cost": round(float(plan.get("Total Cost", 0.0)), 3),
        "plan_rows": int(plan.get("Plan Rows", 0) or 0),
        "node_types": node_types,
        "index_names": index_names,
        "uses_hypothetical_index": any(name.startswith("<") for name in index_names),
        "plan_fingerprint": plan_fingerprint,
    }


def _explain_generic_plan(cursor: Any, query: str) -> dict[str, Any]:
    statement = _safe_explain_query(query)
    # PostgreSQL 16+ GENERIC_PLAN can explain pg_stat_statements queries that
    # retain $1-style placeholders. ANALYZE is deliberately never used.
    cursor.execute("EXPLAIN (FORMAT JSON, GENERIC_PLAN TRUE) " + statement)
    row = cursor.fetchone()
    if not row:
        raise ValueError("empty_explain_result")
    raw_plan = next(iter(row.values())) if isinstance(row, dict) else row[0]
    return _summarize_plan(raw_plan)


def _query_fingerprint_map(snapshot: dict[str, Any]) -> dict[str, str]:
    columns_by_table: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in snapshot.get("columns", []):
        key = (str(row["schema_name"]).lower(), str(row["table_name"]).lower())
        columns_by_table[key].add(str(row["column_name"]).lower())

    queries: dict[str, str] = {}
    for workload_row in snapshot.get("workload", []):
        query = str(workload_row.get("query", ""))
        pattern = extract_query_pattern(query, columns_by_table, snapshot.get("schema", "public"))
        if pattern:
            queries.setdefault(pattern["query_fingerprint"], query)
    return queries


def validate_report_with_hypopg(snapshot: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Attach optional, read-only HypoPG evidence to a workload DNA report.

    HypoPG indexes live only in the current backend. Each alternative is tested
    alone so a cheaper competing shape cannot be mistaken for the candidate.
    """
    validation = {
        "requested": True,
        "tool": "hypopg",
        "mode": "read_only_generic_explain",
        "available": False,
        "status": "unavailable",
        "reason": "extension_not_installed",
    }
    report["planner_validation"] = validation
    report["planner_recommendations"] = []
    report["summary"]["planner_validated_mutations"] = 0
    report["summary"]["planner_inconclusive_candidates"] = len(report["candidates"])

    query_map = _query_fingerprint_map(snapshot)
    recommendation_map: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}

    with get_connection() as conn:
        conn.rollback()
        cursor = conn.cursor()
        try:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'hypopg')")
            extension_row = cursor.fetchone()
            if not extension_row or not extension_row[0]:
                return report

            cursor.execute("SHOW server_version_num")
            version_row = cursor.fetchone()
            if not version_row or int(version_row[0]) < 160000:
                validation.update(
                    {
                        "available": True,
                        "status": "unsupported",
                        "reason": "postgresql_16_required_for_generic_plan",
                    }
                )
                return report

            validation.update(
                {
                    "available": True,
                    "status": "completed",
                    "reason": None,
                    "server_version_num": int(version_row[0]),
                }
            )
            cursor.execute("SET LOCAL statement_timeout = '5s'")

            for position, candidate in enumerate(report["candidates"]):
                candidate_validation: dict[str, Any] = {
                    "status": "inconclusive",
                    "reason": "representative_query_not_found",
                    "alternatives": [],
                }
                candidate["planner_validation"] = candidate_validation
                fingerprints = candidate["expression"].get("query_fingerprints", [])
                query = next((query_map[item] for item in fingerprints if item in query_map), None)
                if query is None:
                    continue

                savepoint = f"indexpilot_candidate_{position}"
                cursor.execute(f"SAVEPOINT {savepoint}")
                try:
                    baseline = _explain_generic_plan(cursor, query)
                    candidate_validation["baseline"] = baseline
                    candidate_validation["reason"] = "no_useful_hypothetical_index"

                    existing_indexes = candidate["evidence"].get("existing_indexes", [])
                    for columns in _candidate_variants(candidate):
                        if _has_covering_prefix(existing_indexes, columns):
                            continue
                        cursor.execute("SELECT hypopg_reset()")
                        ddl = build_hypothetical_sql(
                            candidate["genome"]["schema"],
                            candidate["genome"]["table"],
                            columns,
                        )
                        cursor.execute("SELECT * FROM hypopg_create_index(%s)", (ddl,))
                        cursor.fetchone()
                        plan = _explain_generic_plan(cursor, query)
                        baseline_cost = float(baseline["total_cost"])
                        alternative_cost = float(plan["total_cost"])
                        reduction = (
                            ((baseline_cost - alternative_cost) / baseline_cost) * 100.0
                            if baseline_cost > 0
                            else 0.0
                        )
                        candidate_validation["alternatives"].append(
                            {
                                "columns": columns,
                                "total_cost": alternative_cost,
                                "cost_reduction_pct": round(reduction, 2),
                                "uses_hypothetical_index": plan["uses_hypothetical_index"],
                                "node_types": plan["node_types"],
                                "plan_fingerprint": plan["plan_fingerprint"],
                            }
                        )
                    cursor.execute("SELECT hypopg_reset()")

                    useful = [
                        item
                        for item in candidate_validation["alternatives"]
                        if item["uses_hypothetical_index"]
                        and item["total_cost"] < baseline["total_cost"]
                    ]
                    if not useful:
                        continue
                    winner = min(useful, key=lambda item: item["total_cost"])
                    candidate_validation.update(
                        {
                            "status": "validated",
                            "reason": None,
                            "selected_columns": winner["columns"],
                            "selected_total_cost": winner["total_cost"],
                            "cost_reduction_pct": winner["cost_reduction_pct"],
                        }
                    )

                    schema = candidate["genome"]["schema"]
                    table = candidate["genome"]["table"]
                    columns = list(winner["columns"])
                    tenant_evidence = dict(candidate.get("tenant_evidence", {}))
                    tenant_key = tenant_evidence.get("tenant_key")
                    physical_scope = (
                        "shared_global_tenant_keyed"
                        if tenant_key and columns and columns[0] == tenant_key
                        else "shared_global"
                    )
                    key = (schema, table, tuple(columns))
                    recommendation = recommendation_map.setdefault(
                        key,
                        {
                            "schema": schema,
                            "table": table,
                            "columns": columns,
                            "status": "planner_validated",
                            "advisory_only": True,
                            "physical_scope": physical_scope,
                            "tenant_evidence": tenant_evidence,
                            "sql": build_candidate_sql(schema, table, columns),
                            "best_cost_reduction_pct": winner["cost_reduction_pct"],
                            "supporting_query_fingerprints": [],
                        },
                    )
                    recommendation["best_cost_reduction_pct"] = max(
                        recommendation["best_cost_reduction_pct"],
                        winner["cost_reduction_pct"],
                    )
                    for fingerprint in fingerprints:
                        _append_unique(recommendation["supporting_query_fingerprints"], fingerprint)
                except Exception:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    candidate_validation.update(
                        {"status": "inconclusive", "reason": "explain_failed"}
                    )
                finally:
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
        finally:
            cursor.close()
            conn.rollback()

    recommendations = sorted(
        recommendation_map.values(),
        key=lambda item: item["best_cost_reduction_pct"],
        reverse=True,
    )
    report["planner_recommendations"] = recommendations
    report["summary"]["planner_validated_mutations"] = len(recommendations)
    report["summary"]["planner_inconclusive_candidates"] = sum(
        candidate.get("planner_validation", {}).get("status") != "validated"
        for candidate in report["candidates"]
    )
    report["limits"].append(
        "HypoPG compares planner estimates only; benchmark selected indexes on a production copy."
    )
    return report


def analyze_workload_snapshot(
    snapshot: dict[str, Any],
    *,
    min_table_rows: int = 10_000,
) -> dict[str, Any]:
    """Turn a collected PostgreSQL snapshot into an advisory DNA report."""
    columns_by_table: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in snapshot.get("columns", []):
        key = (str(row["schema_name"]).lower(), str(row["table_name"]).lower())
        columns_by_table[key].add(str(row["column_name"]).lower())

    table_stats = {
        (str(row["schema_name"]).lower(), str(row["table_name"]).lower()): row
        for row in snapshot.get("table_stats", [])
    }
    indexes_by_table: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in snapshot.get("indexes", []):
        key = (str(row["schema_name"]).lower(), str(row["table_name"]).lower())
        indexes_by_table[key].append(row)

    candidates: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    patterns_observed = 0
    covered_patterns = 0
    small_table_patterns = 0

    for workload_row in snapshot.get("workload", []):
        pattern = extract_query_pattern(
            str(workload_row.get("query", "")), columns_by_table, snapshot.get("schema", "public")
        )
        if pattern is None:
            continue
        patterns_observed += 1

        key = (pattern["schema"], pattern["table"])
        stats = table_stats.get(key)
        if not stats:
            continue
        estimated_rows = int(stats.get("estimated_rows", 0) or 0)
        if estimated_rows < min_table_rows:
            small_table_patterns += 1
            continue

        candidate_columns = list(pattern["candidate_columns"])
        existing_indexes = indexes_by_table.get(key, [])
        if _has_covering_prefix(existing_indexes, candidate_columns):
            covered_patterns += 1
            continue

        candidate_key = (pattern["schema"], pattern["table"], tuple(candidate_columns))
        calls = int(workload_row.get("calls", 0) or 0)
        total_ms = float(workload_row.get("total_exec_time_ms", 0.0) or 0.0)
        mean_ms = float(workload_row.get("mean_exec_time_ms", 0.0) or 0.0)

        if candidate_key not in candidates:
            candidates[candidate_key] = {
                "genome": {
                    "schema": pattern["schema"],
                    "table": pattern["table"],
                    "columns": candidate_columns,
                    "physical_scope": pattern["physical_scope"],
                },
                "expression": {
                    "calls": 0,
                    "total_exec_time_ms": 0.0,
                    "max_mean_exec_time_ms": 0.0,
                    "query_fingerprints": [],
                    "equality_columns": pattern["equality_columns"],
                    "range_columns": pattern["range_columns"],
                    "order_columns": pattern["order_columns"],
                },
                "evidence": {
                    "estimated_rows": estimated_rows,
                    "sequential_scans": int(stats.get("sequential_scans", 0) or 0),
                    "index_scans": int(stats.get("index_scans", 0) or 0),
                    "total_size_bytes": int(stats.get("total_size_bytes", 0) or 0),
                    "existing_indexes": [
                        {
                            "name": index.get("index_name"),
                            "columns": index.get("columns", []),
                        }
                        for index in existing_indexes
                    ],
                },
                "tenant_evidence": pattern["tenant_evidence"],
                "mutation": {
                    "type": "CREATE_INDEX",
                    "status": "candidate",
                    "advisory_only": True,
                    "sql": build_candidate_sql(
                        pattern["schema"], pattern["table"], candidate_columns
                    ),
                },
                "reason": [
                    "repeated equality plus range/order workload",
                    "table is large enough to review",
                    "no existing index has the same leading columns",
                ],
            }

        candidate = candidates[candidate_key]
        expression = candidate["expression"]
        expression["calls"] += calls
        expression["total_exec_time_ms"] += total_ms
        expression["max_mean_exec_time_ms"] = max(expression["max_mean_exec_time_ms"], mean_ms)
        fingerprint = pattern["query_fingerprint"]
        if fingerprint not in expression["query_fingerprints"]:
            expression["query_fingerprints"].append(fingerprint)

    ordered_candidates = sorted(
        candidates.values(),
        key=lambda item: (
            item["expression"]["total_exec_time_ms"],
            item["expression"]["calls"],
        ),
        reverse=True,
    )
    for candidate in ordered_candidates:
        expression = candidate["expression"]
        expression["total_exec_time_ms"] = round(expression["total_exec_time_ms"], 3)
        expression["max_mean_exec_time_ms"] = round(expression["max_mean_exec_time_ms"], 3)

    return {
        "report_type": "indexpilot_workload_dna",
        "report_version": 2,
        # timezone.utc keeps the documented Python 3.10 compatibility.
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "advisory_only": True,
        "parser": {"backend": PARSER_BACKEND, "regex_fallback": False},
        "source": snapshot.get("source", {}),
        "thresholds": {
            "minimum_calls": snapshot.get("minimum_calls"),
            "minimum_estimated_table_rows": min_table_rows,
        },
        "summary": {
            "workload_rows_read": len(snapshot.get("workload", [])),
            "workload_stats_empty": not snapshot.get("workload"),
            "indexable_patterns_observed": patterns_observed,
            "patterns_already_covered": covered_patterns,
            "patterns_skipped_as_small_tables": small_table_patterns,
            "candidate_mutations": len(ordered_candidates),
            "planner_validated_mutations": 0,
            "planner_inconclusive_candidates": len(ordered_candidates),
        },
        "candidates": ordered_candidates,
        "planner_validation": {
            "requested": False,
            "tool": "hypopg",
            "status": "not_requested",
        },
        "planner_recommendations": [],
        "limits": [
            "Candidates are parser and statistics evidence, not proof of faster execution.",
            "No index was created or dropped.",
            "Validate candidates with EXPLAIN and preferably HypoPG before applying them.",
            *(
                [
                    "The selected pg_stat_statements window is empty; collect representative "
                    "traffic before treating this report as evidence."
                ]
                if not snapshot.get("workload")
                else []
            ),
        ],
    }


def collect_workload_snapshot(
    *, schema: str = "public", min_calls: int = 100, limit: int = 200
) -> dict[str, Any]:
    """Collect aggregate workload, table, column, and index metadata read-only."""
    if not _IDENTIFIER_RE.fullmatch(schema):
        raise ValueError(f"Unsupported PostgreSQL schema: {schema!r}")
    if min_calls < 1:
        raise ValueError("min_calls must be at least 1")
    if limit < 1 or limit > 10_000:
        raise ValueError("limit must be between 1 and 10000")

    with get_connection() as conn:
        # get_connection() performs a health SELECT. End that transaction before
        # starting the explicitly read-only collection transaction.
        conn.rollback()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements') "
                "AS available"
            )
            extension_row = cursor.fetchone()
            if not extension_row or not extension_row["available"]:
                raise RuntimeError(
                    "pg_stat_statements is not enabled; enable it or supply workload statistics "
                    "through IndexPilot's explicit query-stat integration"
                )

            cursor.execute(
                "SELECT current_database() AS database_name, "
                "current_setting('server_version') AS server_version, "
                "current_setting('transaction_read_only') AS transaction_read_only, "
                "(SELECT stats_reset::text FROM pg_stat_statements_info) "
                "AS pg_stat_statements_reset_at"
            )
            source_row = dict(cursor.fetchone() or {})

            cursor.execute(
                """
                SELECT calls,
                       total_exec_time AS total_exec_time_ms,
                       mean_exec_time AS mean_exec_time_ms,
                       rows,
                       query
                FROM pg_stat_statements
                WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                  AND calls >= %s
                  AND query ~* '^\\s*(SELECT|WITH)'
                ORDER BY total_exec_time DESC
                LIMIT %s
                """,
                (min_calls, limit),
            )
            workload = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT schemaname AS schema_name,
                       relname AS table_name,
                       n_live_tup AS estimated_rows,
                       seq_scan AS sequential_scans,
                       idx_scan AS index_scans,
                       pg_total_relation_size(relid) AS total_size_bytes
                FROM pg_stat_user_tables
                WHERE schemaname = %s
                """,
                (schema,),
            )
            table_stats = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT table_schema AS schema_name, table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                """,
                (schema,),
            )
            columns = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                SELECT namespace.nspname AS schema_name,
                       table_class.relname AS table_name,
                       index_class.relname AS index_name,
                       array_remove(
                           array_agg(attribute.attname ORDER BY key_column.ordinality),
                           NULL
                       ) AS columns
                FROM pg_index index_meta
                JOIN pg_class table_class ON table_class.oid = index_meta.indrelid
                JOIN pg_class index_class ON index_class.oid = index_meta.indexrelid
                JOIN pg_namespace namespace ON namespace.oid = table_class.relnamespace
                JOIN LATERAL unnest(index_meta.indkey) WITH ORDINALITY
                    AS key_column(attnum, ordinality)
                    ON key_column.ordinality <= index_meta.indnkeyatts
                LEFT JOIN pg_attribute attribute
                    ON attribute.attrelid = table_class.oid
                   AND attribute.attnum = key_column.attnum
                WHERE namespace.nspname = %s
                GROUP BY namespace.nspname, table_class.relname, index_class.relname
                """,
                (schema,),
            )
            indexes = [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.rollback()

    return {
        "schema": schema,
        "minimum_calls": min_calls,
        "source": source_row,
        "workload": workload,
        "table_stats": table_stats,
        "columns": columns,
        "indexes": indexes,
    }


def build_workload_dna_report(
    *,
    schema: str = "public",
    min_calls: int = 100,
    min_table_rows: int = 10_000,
    limit: int = 200,
    validate_hypopg: bool = False,
) -> dict[str, Any]:
    """Collect and analyze one PostgreSQL workload without changing the database."""
    snapshot = collect_workload_snapshot(schema=schema, min_calls=min_calls, limit=limit)
    report = analyze_workload_snapshot(snapshot, min_table_rows=min_table_rows)
    if validate_hypopg:
        report = validate_report_with_hypopg(snapshot, report)
    from src.auto_indexer import review_planner_recommendations

    report["auto_indexer_review"] = review_planner_recommendations(report)
    return report
