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
    ProposedIndexError,
    SQLPatternError,
    canonical_query_fingerprint,
    extract_postgres_query_pattern,
    extract_proposed_index_query_context,
    parse_migration_indexes,
    parse_proposed_index,
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


def _is_comparable_simple_btree(index: dict[str, Any]) -> bool:
    """Return whether an existing index is comparable to the preview shape."""
    if not bool(index.get("is_valid", True)) or not bool(index.get("is_ready", True)):
        return False
    if bool(index.get("is_partial", False)) or bool(index.get("is_expression", False)):
        return False
    if str(index.get("access_method", "btree")).lower() != "btree":
        return False
    if not bool(index.get("uses_default_opclasses", True)):
        return False
    if not bool(index.get("uses_default_collations", True)):
        return False
    return bool(index.get("uses_default_sort_order", True))


def _public_index_evidence(index: dict[str, Any]) -> dict[str, Any]:
    """Keep catalog evidence in one stable, JSON-safe public shape."""
    return {
        "name": index.get("index_name", index.get("name")),
        "columns": list(index.get("columns", [])),
        "include_columns": list(index.get("include_columns", [])),
        "is_valid": bool(index.get("is_valid", True)),
        "is_ready": bool(index.get("is_ready", True)),
        "is_partial": bool(index.get("is_partial", False)),
        "is_expression": bool(index.get("is_expression", False)),
        "is_unique": bool(index.get("is_unique", False)),
        "is_primary": bool(index.get("is_primary", False)),
        "is_exclusion": bool(index.get("is_exclusion", False)),
        "is_constraint_owned": bool(index.get("is_constraint_owned", False)),
        "access_method": str(index.get("access_method", "btree")),
        "uses_default_opclasses": bool(index.get("uses_default_opclasses", True)),
        "uses_default_collations": bool(index.get("uses_default_collations", True)),
        "uses_default_sort_order": bool(index.get("uses_default_sort_order", True)),
        "index_scans": int(index.get("index_scans", 0) or 0),
        "index_size_bytes": int(index.get("index_size_bytes", 0) or 0),
    }


def _has_covering_prefix(existing_indexes: list[dict[str, Any]], columns: list[str]) -> bool:
    wanted = [column.lower() for column in columns]
    for index in existing_indexes:
        # Only a usable, ordinary B-tree is comparable to the simple candidate
        # shape emitted by this module. Partial, expression, invalid, or still-
        # building indexes must not suppress a recommendation for all rows.
        if not _is_comparable_simple_btree(index):
            continue
        existing = [str(column).lower() for column in index.get("columns", []) if column]
        if existing[: len(wanted)] == wanted:
            return True
    return False


def _quote_identifier(identifier: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Unsupported PostgreSQL identifier: {identifier!r}")
    return f'"{identifier}"'


def _candidate_index_name(
    schema: str,
    table: str,
    columns: list[str],
    *,
    existing_index_names: set[str] | None = None,
) -> str:
    """Return a deterministic schema-unique name for generated advisory DDL."""
    raw_name = "idx_" + "_".join([table, *columns, "dna"])
    if len(raw_name) > 63:
        digest = hashlib.sha256(raw_name.encode("utf-8")).hexdigest()[:8]
        raw_name = f"{raw_name[:54]}_{digest}"

    occupied = {name.lower() for name in existing_index_names or set()}
    if raw_name.lower() not in occupied:
        return raw_name

    identity = f"{schema}.{table}({','.join(columns)})"
    for attempt in range(1, 1_001):
        digest = hashlib.sha256(f"{identity}:{attempt}".encode()).hexdigest()[:8]
        candidate = f"{raw_name[:54]}_{digest}"
        if candidate.lower() not in occupied:
            return candidate
    raise ValueError("could_not_generate_unique_index_name")


def build_candidate_sql(
    schema: str,
    table: str,
    columns: list[str],
    *,
    existing_index_names: set[str] | None = None,
) -> str:
    """Build reviewable DDL text. This function does not execute it."""
    index_name = _candidate_index_name(
        schema,
        table,
        columns,
        existing_index_names=existing_index_names,
    )
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    return (
        "CREATE INDEX CONCURRENTLY "
        f"{_quote_identifier(index_name)} ON {_quote_identifier(schema)}.{_quote_identifier(table)} "
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
    if candidate.get("validation_mode") == "exact_shape":
        return [genome_columns]
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


def _filter_read_only_workload_rows(
    rows: list[dict[str, Any]], *, limit: int
) -> list[dict[str, Any]]:
    """Keep real read-only queries after parsing, including leading comments."""
    selected: list[dict[str, Any]] = []
    for row in rows:
        try:
            parse_read_only_query(str(row.get("query", "")))
        except SQLPatternError:
            continue
        selected.append(dict(row))
        if len(selected) >= limit:
            break
    return selected


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
    queries: dict[str, str] = {}
    for workload_row in snapshot.get("workload", []):
        query = str(workload_row.get("query", ""))
        try:
            statement = parse_read_only_query(query)
        except SQLPatternError:
            continue
        queries.setdefault(canonical_query_fingerprint(statement), query)
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
        hypopg_available = False
        try:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'hypopg')")
            extension_row = cursor.fetchone()
            if not extension_row or not extension_row[0]:
                return report
            hypopg_available = True

            # Connections can come from a pool. Hypothetical indexes are
            # backend-local, so clear any state left by an earlier caller
            # before measuring a baseline.
            cursor.execute("SELECT hypopg_reset()")

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
                    cursor.execute("SELECT hypopg_reset()")
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
                                "decision_cost_reduction_pct": reduction,
                                "uses_hypothetical_index": plan["uses_hypothetical_index"],
                                "node_types": plan["node_types"],
                                "plan_fingerprint": plan["plan_fingerprint"],
                            }
                        )
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
                            "decision_cost_reduction_pct": winner["decision_cost_reduction_pct"],
                            "supporting_query_fingerprints": [],
                        },
                    )
                    if (
                        winner["decision_cost_reduction_pct"]
                        > recommendation["decision_cost_reduction_pct"]
                    ):
                        recommendation["best_cost_reduction_pct"] = winner["cost_reduction_pct"]
                        recommendation["decision_cost_reduction_pct"] = winner[
                            "decision_cost_reduction_pct"
                        ]
                    for fingerprint in fingerprints:
                        _append_unique(recommendation["supporting_query_fingerprints"], fingerprint)
                except Exception:
                    cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    candidate_validation.update(
                        {"status": "inconclusive", "reason": "explain_failed"}
                    )
                finally:
                    try:
                        cursor.execute("SELECT hypopg_reset()")
                    except Exception:
                        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
        finally:
            if hypopg_available:
                try:
                    cursor.execute("SELECT hypopg_reset()")
                except Exception:
                    conn.rollback()
            cursor.close()
            conn.rollback()

    recommendations = sorted(
        recommendation_map.values(),
        key=lambda item: item["decision_cost_reduction_pct"],
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
    unsupported_tables: set[tuple[str, str]] = set()
    unsupported_columns: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in snapshot.get("columns", []):
        raw_schema = str(row["schema_name"])
        raw_table = str(row["table_name"])
        raw_column = str(row["column_name"])
        key = (raw_schema.lower(), raw_table.lower())
        normalized_column = raw_column.lower()
        columns_by_table[key].add(normalized_column)
        if (
            raw_schema != raw_schema.lower()
            or raw_table != raw_table.lower()
            or not _IDENTIFIER_RE.fullmatch(raw_schema)
            or not _IDENTIFIER_RE.fullmatch(raw_table)
        ):
            unsupported_tables.add(key)
        if raw_column != normalized_column or not _IDENTIFIER_RE.fullmatch(raw_column):
            unsupported_columns[key].add(normalized_column)

    table_stats = {
        (str(row["schema_name"]).lower(), str(row["table_name"]).lower()): row
        for row in snapshot.get("table_stats", [])
    }
    indexes_by_table: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    index_names_by_schema: dict[str, set[str]] = defaultdict(set)
    for row in snapshot.get("indexes", []):
        schema_name = str(row["schema_name"]).lower()
        key = (schema_name, str(row["table_name"]).lower())
        indexes_by_table[key].append(row)
        index_name = str(row.get("index_name", "")).strip()
        if index_name:
            index_names_by_schema[schema_name].add(index_name)

    candidates: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    patterns_observed = 0
    covered_patterns = 0
    small_table_patterns = 0
    unsupported_identifier_patterns = 0
    partitioned_parent_patterns = 0

    for workload_row in snapshot.get("workload", []):
        pattern = extract_query_pattern(
            str(workload_row.get("query", "")), columns_by_table, snapshot.get("schema", "public")
        )
        if pattern is None:
            continue
        patterns_observed += 1

        key = (pattern["schema"], pattern["table"])
        candidate_columns = list(pattern["candidate_columns"])
        if key in unsupported_tables or any(
            column in unsupported_columns.get(key, set()) for column in candidate_columns
        ):
            unsupported_identifier_patterns += 1
            continue
        stats = table_stats.get(key)
        if not stats:
            continue
        estimated_rows = int(stats.get("estimated_rows", 0) or 0)
        if estimated_rows < min_table_rows:
            small_table_patterns += 1
            continue
        if str(stats.get("relation_kind", "")) == "p":
            partitioned_parent_patterns += 1
            continue

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
                    "relation_kind": stats.get("relation_kind"),
                    "table_activity": {
                        "inserts": int(stats.get("inserts", 0) or 0),
                        "updates": int(stats.get("updates", 0) or 0),
                        "deletes": int(stats.get("deletes", 0) or 0),
                        "hot_updates": int(stats.get("hot_updates", 0) or 0),
                    },
                    "existing_indexes": [
                        _public_index_evidence(index) for index in existing_indexes
                    ],
                },
                "tenant_evidence": pattern["tenant_evidence"],
                "mutation": {
                    "type": "CREATE_INDEX",
                    "status": "candidate",
                    "advisory_only": True,
                    "sql": build_candidate_sql(
                        pattern["schema"],
                        pattern["table"],
                        candidate_columns,
                        existing_index_names=index_names_by_schema.get(pattern["schema"], set()),
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
            "patterns_skipped_as_unsupported_identifiers": unsupported_identifier_patterns,
            "patterns_skipped_as_partitioned_parents": partitioned_parent_patterns,
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
            *(
                [
                    "Some workload patterns used quoted or otherwise unsupported identifiers; "
                    "they were skipped instead of emitting DDL for a different object."
                ]
                if unsupported_identifier_patterns
                else []
            ),
            *(
                [
                    "Partitioned parent tables were skipped because PostgreSQL cannot build "
                    "their indexes CONCURRENTLY; review leaf partitions and deployment separately."
                ]
                if partitioned_parent_patterns
                else []
            ),
        ],
    }


def analyze_proposed_index_snapshot(
    snapshot: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    """Build an advisory report for one operator-proposed B-tree index."""
    schema = str(proposal["schema"])
    table = str(proposal["table"])
    columns = [str(column) for column in proposal["columns"]]
    table_key = (schema, table)

    columns_by_table: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in snapshot.get("columns", []):
        key = (str(row["schema_name"]).lower(), str(row["table_name"]).lower())
        columns_by_table[key].add(str(row["column_name"]).lower())
    if table_key not in columns_by_table:
        raise ProposedIndexError("candidate_table_not_found")
    if any(column not in columns_by_table[table_key] for column in columns):
        raise ProposedIndexError("candidate_column_not_found")

    table_stats = next(
        (
            row
            for row in snapshot.get("table_stats", [])
            if str(row["schema_name"]).lower() == schema and str(row["table_name"]).lower() == table
        ),
        {},
    )
    existing_indexes = [
        row
        for row in snapshot.get("indexes", [])
        if str(row["schema_name"]).lower() == schema and str(row["table_name"]).lower() == table
    ]
    existing_overlap = _has_covering_prefix(existing_indexes, columns)

    expression: dict[str, Any] = {
        "calls": 0,
        "total_exec_time_ms": 0.0,
        "max_mean_exec_time_ms": 0.0,
        "query_fingerprints": [],
        "equality_columns": [],
        "range_columns": [],
        "order_columns": [],
    }
    supporting_fingerprints_by_column: dict[str, set[str]] = {column: set() for column in columns}
    tenant_evidence: dict[str, Any] = {
        "tenant_filtered": False,
        "tenant_key": None,
        "source": None,
    }
    for workload_row in snapshot.get("workload", []):
        context = extract_proposed_index_query_context(
            str(workload_row.get("query", "")),
            columns_by_table,
            target_schema=schema,
            target_table=table,
            candidate_columns=columns,
            default_schema=str(snapshot.get("schema", "public")),
        )
        if context is None:
            continue
        expression["calls"] += int(workload_row.get("calls", 0) or 0)
        expression["total_exec_time_ms"] += float(
            workload_row.get("total_exec_time_ms", 0.0) or 0.0
        )
        expression["max_mean_exec_time_ms"] = max(
            expression["max_mean_exec_time_ms"],
            float(workload_row.get("mean_exec_time_ms", 0.0) or 0.0),
        )
        _append_unique(expression["query_fingerprints"], context["query_fingerprint"])
        for column in context["candidate_columns_used"]:
            supporting_fingerprints_by_column[column].add(context["query_fingerprint"])
        for key in ("equality_columns", "range_columns", "order_columns"):
            for column in context[key]:
                _append_unique(expression[key], column)
        if (
            columns[0] == "tenant_id"
            and context["tenant_evidence"].get("source") == "query_equality_predicate"
        ):
            tenant_evidence = dict(context["tenant_evidence"])

    expression["total_exec_time_ms"] = round(expression["total_exec_time_ms"], 3)
    expression["max_mean_exec_time_ms"] = round(expression["max_mean_exec_time_ms"], 3)
    expression["candidate_column_support"] = {
        column: len(supporting_fingerprints_by_column[column]) for column in columns
    }
    expression["unused_trailing_columns"] = [
        column for column in columns[1:] if not supporting_fingerprints_by_column[column]
    ]
    physical_scope = (
        "shared_global_tenant_keyed"
        if tenant_evidence.get("tenant_key") and columns[0] == tenant_evidence["tenant_key"]
        else "shared_global"
    )
    normalized_proposal_sql = str(proposal.get("normalized_sql", "")).strip()
    existing_names_in_schema = {
        str(index.get("index_name", ""))
        for index in snapshot.get("indexes", [])
        if str(index.get("schema_name", "")).lower() == schema and index.get("index_name")
    }
    candidate_sql = (
        normalized_proposal_sql.rstrip(";") + ";"
        if normalized_proposal_sql
        else build_candidate_sql(
            schema,
            table,
            columns,
            existing_index_names=existing_names_in_schema,
        )
    )
    operational_notes: list[dict[str, str]] = []
    proposal_index_name = str(proposal.get("index_name") or "")
    name_collisions = [
        index
        for index in snapshot.get("indexes", [])
        if proposal_index_name
        and str(index.get("schema_name", "")).lower() == schema
        and str(index.get("index_name", "")).lower() == proposal_index_name.lower()
        and [str(column).lower() for column in index.get("columns", [])] != columns
    ]
    if name_collisions:
        operational_notes.append(
            {
                "code": "index_name_already_exists_for_different_shape",
                "level": "blocker",
                "message": (
                    f"Index name {proposal_index_name!r} already belongs to a different shape "
                    "in this schema; PostgreSQL would fail or IF NOT EXISTS could silently skip it."
                ),
            }
        )
    if not proposal.get("concurrently", False):
        operational_notes.append(
            {
                "code": "standard_index_build_requested",
                "level": "warning",
                "message": (
                    "The proposal omits CONCURRENTLY; a standard PostgreSQL index build can "
                    "block writes while it runs. Validate deployment safety separately."
                ),
            }
        )
    if str(table_stats.get("relation_kind", "")) == "p" and proposal.get("concurrently", False):
        operational_notes.append(
            {
                "code": "partitioned_parent_concurrent_build_unsupported",
                "level": "blocker",
                "message": (
                    "PostgreSQL cannot use CREATE INDEX CONCURRENTLY on a partitioned parent; "
                    "review leaf-partition deployment separately."
                ),
            }
        )
    if expression["unused_trailing_columns"]:
        operational_notes.append(
            {
                "code": "unused_trailing_columns_not_observed",
                "level": "warning",
                "message": (
                    "No matching fingerprint used these trailing keys: "
                    + ", ".join(expression["unused_trailing_columns"])
                    + ". Benchmark the full proposed width instead of assuming every key adds value."
                ),
            }
        )
    candidate = {
        "origin": "user_provided",
        "validation_mode": "exact_shape",
        "genome": {
            "schema": schema,
            "table": table,
            "columns": columns,
            "physical_scope": physical_scope,
        },
        "expression": expression,
        "evidence": {
            "estimated_rows": int(table_stats.get("estimated_rows", 0) or 0),
            "sequential_scans": int(table_stats.get("sequential_scans", 0) or 0),
            "index_scans": int(table_stats.get("index_scans", 0) or 0),
            "total_size_bytes": int(table_stats.get("total_size_bytes", 0) or 0),
            "relation_kind": table_stats.get("relation_kind"),
            "table_activity": {
                "inserts": int(table_stats.get("inserts", 0) or 0),
                "updates": int(table_stats.get("updates", 0) or 0),
                "deletes": int(table_stats.get("deletes", 0) or 0),
                "hot_updates": int(table_stats.get("hot_updates", 0) or 0),
            },
            "existing_overlap": existing_overlap,
            "existing_indexes": [_public_index_evidence(index) for index in existing_indexes],
        },
        "tenant_evidence": tenant_evidence,
        "mutation": {
            "type": "CREATE_INDEX",
            "status": "existing_overlap" if existing_overlap else "candidate",
            "advisory_only": True,
            "sql": candidate_sql,
        },
        "reason": ["operator supplied this exact index shape for review"],
    }

    matching_queries = len(expression["query_fingerprints"])
    candidate["reason"].append(
        "matching workload evidence was aggregated without retaining raw SQL"
        if matching_queries
        else "no matching workload fingerprint was observed for the leading key"
    )
    report = {
        "report_type": "indexpilot_index_review",
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "advisory_only": True,
        "parser": {"backend": PARSER_BACKEND, "regex_fallback": False},
        "source": snapshot.get("source", {}),
        "proposal": {
            "schema": schema,
            "table": table,
            "columns": columns,
            "index_name": proposal.get("index_name"),
            "method": "btree",
            "concurrently": bool(proposal.get("concurrently", False)),
            "if_not_exists": bool(proposal.get("if_not_exists", False)),
            "statement_number": proposal.get("statement_number"),
        },
        "summary": {
            "workload_rows_read": len(snapshot.get("workload", [])),
            "workload_stats_empty": not snapshot.get("workload"),
            "matching_workload_fingerprints": matching_queries,
            "candidate_mutations": 0 if existing_overlap else 1,
            "planner_validated_mutations": 0,
            "planner_inconclusive_candidates": 0 if existing_overlap else 1,
        },
        "candidates": [candidate],
        "planner_validation": {
            "requested": False,
            "tool": "hypopg",
            "status": "not_requested",
        },
        "planner_recommendations": [],
        "evidence_scope": {
            "matching_workload_fingerprints": matching_queries,
            "representative_queries_planned": 0,
            "full_workload_regression_tested": False,
        },
        "existing_overlap": existing_overlap,
        "operational_notes": operational_notes,
        "limits": [
            "No index was created or dropped.",
            "A positive verdict is planner evidence only, not measured latency.",
            "Only one representative query is planned in this preview.",
            "Benchmark on a production copy before applying any index.",
        ],
    }
    return report


def derive_review_verdict(report: dict[str, Any]) -> dict[str, str]:
    """Translate report evidence into a cautious, stable public verdict."""
    is_proposed_index = report.get("report_type") == "indexpilot_index_review"
    if report.get("existing_overlap"):
        return {
            "status": "existing_overlap",
            "reason": "a comparable valid B-tree already has this leading-column prefix",
        }

    review = report.get("auto_indexer_review", {})
    if review.get("status") == "admitted" and review.get("accepted"):
        return {
            "status": "worth_benchmarking",
            "reason": "HypoPG lowered planner cost enough to pass the existing advisory threshold",
        }

    planner_status = report.get("planner_validation", {}).get("status")
    candidate_validations = [
        candidate.get("planner_validation", {}) for candidate in report.get("candidates", [])
    ]
    planner_evaluated = any(validation.get("baseline") for validation in candidate_validations)
    planner_failed = any(
        validation.get("reason")
        in {"representative_query_not_found", "explain_failed", "empty_explain_result"}
        for validation in candidate_validations
    )
    if planner_status == "completed" and planner_evaluated and not planner_failed:
        return {
            "status": "not_supported_by_current_planner_evidence",
            "reason": (
                "the exact index was unused or did not pass the advisory improvement threshold"
                if is_proposed_index
                else "the discovered indexes were unused or did not pass the advisory improvement threshold"
            ),
        }
    summary = report.get("summary", {})
    if (
        not is_proposed_index
        and summary.get("patterns_already_covered", 0) > 0
        and not report.get("candidates")
    ):
        return {
            "status": "existing_overlap",
            "reason": "observed workload patterns already have comparable index prefixes",
        }
    if summary.get("workload_stats_empty"):
        reason = "the selected pg_stat_statements window is empty"
    elif is_proposed_index and not summary.get("matching_workload_fingerprints", 0):
        reason = "no observed query used the proposed index's leading column"
    elif not is_proposed_index and report.get("candidates"):
        reason = "candidate shapes need optional HypoPG planner validation"
    elif not is_proposed_index:
        reason = "no uncovered index pattern met the current workload thresholds"
    elif planner_status == "unavailable":
        reason = "HypoPG is not installed in the inspected database"
    elif planner_status == "unsupported":
        reason = "PostgreSQL 16 or newer is required for placeholder-safe planner review"
    elif planner_status == "completed":
        reason = "the candidate could not be evaluated conclusively by EXPLAIN"
    else:
        reason = "HypoPG planner review was not completed"
    return {"status": "inconclusive", "reason": reason}


def render_review_markdown(report: dict[str, Any]) -> str:
    """Render a report without exposing the raw workload queries."""
    if report.get("report_type") == "indexpilot_migration_review":
        return render_migration_review_markdown(report)

    verdict = report.get("verdict") or derive_review_verdict(report)
    summary = report.get("summary", {})
    lines = [
        "# IndexPilot index review",
        "",
        "> Advisory only. IndexPilot did not create, drop, or execute an index.",
        "",
        f"**Verdict:** `{verdict['status']}`",
        "",
        f"**Why:** {verdict['reason']}",
        "",
        "## Evidence",
        "",
        f"- Workload rows read: {summary.get('workload_rows_read', 0)}",
        "- Matching query fingerprints: "
        f"{summary.get('matching_workload_fingerprints', summary.get('indexable_patterns_observed', 0))}",
        f"- Planner validation: `{report.get('planner_validation', {}).get('status', 'unknown')}`",
        f"- Parser: `{report.get('parser', {}).get('backend', 'unknown')}`",
        "",
        "## Candidates",
        "",
    ]

    candidates = report.get("candidates", [])
    if not candidates:
        lines.append("No candidate index was identified in this workload window.")
    for position, candidate in enumerate(candidates, start=1):
        genome = candidate.get("genome", {})
        expression = candidate.get("expression", {})
        planner = candidate.get("planner_validation", {})
        column_text = ", ".join(f"`{column}`" for column in genome.get("columns", []))
        lines.extend(
            [
                f"### {position}. `{genome.get('schema')}.{genome.get('table')}`",
                "",
                f"- Columns: {column_text}",
                f"- Observed calls: {expression.get('calls', 0)}",
                f"- Total observed execution time: {expression.get('total_exec_time_ms', 0)} ms",
                f"- Candidate planner status: `{planner.get('status', 'not_validated')}`",
            ]
        )
        if planner.get("cost_reduction_pct") is not None:
            lines.append(f"- Best planner cost reduction: {planner['cost_reduction_pct']}%")
        exact_review = report.get("report_type") == "indexpilot_index_review"
        deployment_blocked = any(
            note.get("level") == "blocker" for note in report.get("operational_notes", [])
        )
        if not exact_review or (
            verdict.get("status") == "worth_benchmarking" and not deployment_blocked
        ):
            lines.extend(
                [
                    "",
                    "```sql",
                    str(candidate.get("mutation", {}).get("sql", "-- no SQL candidate")),
                    "```",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "- Action: no CREATE INDEX action is supported by the current evidence.",
                    "",
                ]
            )

    operational_notes = report.get("operational_notes", [])
    if operational_notes:
        lines.extend(["## Operational notes", ""])
        for note in operational_notes:
            lines.append(f"- `{note.get('code', 'note')}`: {note.get('message', '')}")
        lines.append("")

    lines.extend(["## Limits", ""])
    for limit in report.get("limits", []):
        lines.append(f"- {limit}")
    lines.extend(
        [
            "",
            "## Next step",
            "",
            "Benchmark any `worth_benchmarking` index on a production copy, including write overhead, "
            "index size, latency distribution, and rollback.",
            "",
        ]
    )
    return "\n".join(lines)


def render_migration_review_markdown(report: dict[str, Any]) -> str:
    """Render a combined, pull-request-friendly migration review."""
    migration = report.get("migration", {})
    summary = report.get("summary", {})
    lines = [
        "# IndexPilot migration index review",
        "",
        "> Advisory only. Non-index statements were not reviewed or executed.",
        "",
        "## Summary",
        "",
        f"- Migration statements parsed: {migration.get('statement_count', 0)}",
        f"- Index statements reviewed: {summary.get('reviewed_indexes', 0)}",
        f"- Non-index statements ignored: {migration.get('ignored_non_index_statements', 0)}",
        f"- Catalog/workload snapshots: {summary.get('snapshot_count', 0)}",
        f"- In-migration overlap findings: {summary.get('migration_overlap_findings', 0)}",
        "",
        "## Index reviews",
        "",
    ]
    for position, review in enumerate(report.get("reviews", []), start=1):
        proposal = review.get("proposal", {})
        verdict = review.get("verdict", {})
        candidate = (review.get("candidates") or [{}])[0]
        expression = candidate.get("expression", {})
        columns = ", ".join(f"`{column}`" for column in proposal.get("columns", []))
        statement_number = proposal.get("statement_number")
        statement_label = (
            f"statement {statement_number}" if statement_number is not None else f"index {position}"
        )
        lines.extend(
            [
                f"### {position}. `{proposal.get('schema')}.{proposal.get('table')}` ({statement_label})",
                "",
                f"- Columns: {columns}",
                f"- Verdict: `{verdict.get('status', 'inconclusive')}`",
                f"- Why: {verdict.get('reason', 'No reason recorded.')}",
                f"- Matching query fingerprints: {review.get('summary', {}).get('matching_workload_fingerprints', 0)}",
                f"- Observed calls: {expression.get('calls', 0)}",
                f"- Build mode requested: `{'concurrent' if proposal.get('concurrently') else 'standard'}`",
            ]
        )
        deployment_blocked = any(
            note.get("level") == "blocker" for note in review.get("operational_notes", [])
        )
        if verdict.get("status") == "worth_benchmarking" and not deployment_blocked:
            lines.extend(
                [
                    "",
                    "```sql",
                    str(candidate.get("mutation", {}).get("sql", "-- no SQL candidate")),
                    "```",
                ]
            )
        for note in review.get("operational_notes", []):
            lines.append(f"- `{note.get('code', 'note')}`: {note.get('message', '')}")
        lines.append("")

    findings = report.get("migration_overlap_findings", [])
    if findings:
        lines.extend(["## In-migration overlap", ""])
        for finding in findings:
            if finding.get("type") == "duplicate_index_name":
                lines.append(
                    "- Index name `{}.{}` is repeated in statements {} and {} for tables `{}` and "
                    "`{}`; rename one before deployment.".format(
                        finding.get("schema"),
                        finding.get("index_name"),
                        finding.get("left_statement"),
                        finding.get("right_statement"),
                        finding.get("left_table"),
                        finding.get("right_table"),
                    )
                )
            else:
                lines.append(
                    "- `{}.{}` statements {} and {}: `{}`; manual review only, not safe-to-drop proof.".format(
                        finding.get("schema"),
                        finding.get("table"),
                        finding.get("left_statement"),
                        finding.get("right_statement"),
                        finding.get("type"),
                    )
                )
        lines.append("")

    lines.extend(["## Limits", ""])
    for limit in report.get("limits", []):
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


def render_review_sarif(
    report: dict[str, Any], *, artifact_uri: str | None = None
) -> dict[str, Any]:
    """Render exact or migration verdicts as a portable SARIF 2.1.0 log."""
    reviews = (
        list(report.get("reviews", []))
        if report.get("report_type") == "indexpilot_migration_review"
        else [report]
    )
    level_by_status = {
        "worth_benchmarking": "note",
        "existing_overlap": "warning",
        "not_supported_by_current_planner_evidence": "note",
        "inconclusive": "warning",
    }
    results = []
    rules: dict[str, dict[str, Any]] = {}
    for review in reviews:
        verdict = review.get("verdict") or derive_review_verdict(review)
        status = str(verdict.get("status", "inconclusive"))
        rule_id = f"indexpilot.{status}"
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "shortDescription": {"text": status.replace("_", " ")},
                "helpUri": "https://github.com/eyeinthesky6/indexpilot#how-to-read-a-verdict",
            },
        )
        proposal = review.get("proposal", {})
        target = f"{proposal.get('schema', 'unknown')}.{proposal.get('table', 'unknown')}"
        columns = ", ".join(str(column) for column in proposal.get("columns", []))
        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": level_by_status.get(status, "warning"),
            "message": {"text": f"{target} ({columns}): {status} - {verdict.get('reason', '')}"},
            "properties": {
                "advisoryOnly": True,
                "statementNumber": proposal.get("statement_number"),
            },
        }
        if artifact_uri:
            result["locations"] = [
                {"physicalLocation": {"artifactLocation": {"uri": artifact_uri}}}
            ]
        results.append(result)

    if report.get("report_type") == "indexpilot_migration_review":
        overlap_rule_id = "indexpilot.existing_overlap"
        for finding in report.get("migration_overlap_findings", []):
            rules.setdefault(
                overlap_rule_id,
                {
                    "id": overlap_rule_id,
                    "shortDescription": {"text": "existing overlap"},
                    "helpUri": "https://github.com/eyeinthesky6/indexpilot#how-to-read-a-verdict",
                },
            )
            finding_type = str(finding.get("type", "migration_overlap"))
            left_table = str(finding.get("left_table") or finding.get("table") or "unknown")
            right_table = str(finding.get("right_table") or finding.get("table") or "unknown")
            message = (
                f"Migration statements {finding.get('left_statement')} and "
                f"{finding.get('right_statement')} have {finding_type}: "
                f"{finding.get('schema', 'unknown')}.{left_table} and {right_table}; "
                "manual review required."
            )
            overlap_result: dict[str, Any] = {
                "ruleId": overlap_rule_id,
                "level": "warning",
                "message": {"text": message},
                "properties": {
                    "advisoryOnly": True,
                    "findingType": finding_type,
                    "statementNumber": finding.get("left_statement"),
                    "relatedStatementNumber": finding.get("right_statement"),
                },
            }
            if artifact_uri:
                overlap_result["locations"] = [
                    {"physicalLocation": {"artifactLocation": {"uri": artifact_uri}}}
                ]
            results.append(overlap_result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "IndexPilot",
                        "informationUri": "https://github.com/eyeinthesky6/indexpilot",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def collect_workload_snapshot(
    *,
    schema: str = "public",
    min_calls: int = 100,
    limit: int = 200,
    require_pg_stat_statements: bool = True,
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
                "AS available, "
                "EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'hypopg') "
                "AS hypopg_available"
            )
            extension_row = cursor.fetchone()
            pg_stat_statements_available = bool(extension_row and extension_row["available"])
            if require_pg_stat_statements and not pg_stat_statements_available:
                raise RuntimeError(
                    "pg_stat_statements is not enabled; enable it or supply workload statistics "
                    "through IndexPilot's explicit query-stat integration"
                )

            cursor.execute(
                "SELECT current_database() AS database_name, "
                "current_setting('server_version') AS server_version, "
                "current_setting('server_version_num')::integer AS server_version_num, "
                "current_setting('transaction_read_only') AS transaction_read_only, "
                "(SELECT stats_reset::text FROM pg_stat_database "
                " WHERE datname = current_database()) AS database_stats_reset_at"
            )
            source_row = dict(cursor.fetchone() or {})
            source_row["pg_stat_statements_available"] = pg_stat_statements_available
            source_row["hypopg_available"] = bool(
                extension_row and extension_row.get("hypopg_available")
            )
            if pg_stat_statements_available:
                collection_limit = min(max(limit * 5, limit), 10_000)
                cursor.execute(
                    "SELECT stats_reset::text AS pg_stat_statements_reset_at "
                    "FROM pg_stat_statements_info"
                )
                reset_row = dict(cursor.fetchone() or {})
                source_row.update(reset_row)
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
                    ORDER BY total_exec_time DESC
                    LIMIT %s
                    """,
                    (min_calls, collection_limit),
                )
                workload = _filter_read_only_workload_rows(
                    [dict(row) for row in cursor.fetchall()], limit=limit
                )
            else:
                source_row["pg_stat_statements_reset_at"] = None
                workload = []

            cursor.execute(
                """
                SELECT schemaname AS schema_name,
                       relname AS table_name,
                       n_live_tup AS estimated_rows,
                       seq_scan AS sequential_scans,
                       idx_scan AS index_scans,
                       n_tup_ins AS inserts,
                       n_tup_upd AS updates,
                       n_tup_del AS deletes,
                       n_tup_hot_upd AS hot_updates,
                       last_analyze::text AS last_analyze_at,
                       last_autoanalyze::text AS last_autoanalyze_at,
                       (
                           SELECT relation_kind_class.relkind::text
                           FROM pg_class relation_kind_class
                           WHERE relation_kind_class.oid = pg_stat_user_tables.relid
                       ) AS relation_kind,
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
                       index_meta.indisvalid AS is_valid,
                       index_meta.indisready AS is_ready,
                       index_meta.indisunique AS is_unique,
                       index_meta.indisprimary AS is_primary,
                       index_meta.indisexclusion AS is_exclusion,
                       (index_meta.indpred IS NOT NULL) AS is_partial,
                       (index_meta.indexprs IS NOT NULL) AS is_expression,
                       access_method.amname AS access_method,
                       bool_or(constraint_meta.oid IS NOT NULL) AS is_constraint_owned,
                       COALESCE(index_stats.idx_scan, 0) AS index_scans,
                       pg_relation_size(index_class.oid) AS index_size_bytes,
                       bool_and(operator_class.opcdefault) AS uses_default_opclasses,
                       bool_and(key_column.collation_oid = attribute.attcollation)
                           AS uses_default_collations,
                       bool_and(key_column.option_bits = 0) AS uses_default_sort_order,
                        array_remove(
                            array_agg(attribute.attname ORDER BY key_column.ordinality),
                            NULL
                       ) AS columns,
                       COALESCE(
                           ARRAY(
                               SELECT include_attribute.attname
                               FROM unnest(index_meta.indkey::smallint[])
                                   WITH ORDINALITY AS include_key(attnum, ordinality)
                               JOIN pg_attribute include_attribute
                                 ON include_attribute.attrelid = index_meta.indrelid
                                AND include_attribute.attnum = include_key.attnum
                               WHERE include_key.ordinality > index_meta.indnkeyatts
                               ORDER BY include_key.ordinality
                           ),
                           ARRAY[]::name[]
                       ) AS include_columns
                FROM pg_index index_meta
                JOIN pg_class table_class ON table_class.oid = index_meta.indrelid
                JOIN pg_class index_class ON index_class.oid = index_meta.indexrelid
                JOIN pg_am access_method ON access_method.oid = index_class.relam
                JOIN pg_namespace namespace ON namespace.oid = table_class.relnamespace
                LEFT JOIN pg_constraint constraint_meta
                  ON constraint_meta.conindid = index_meta.indexrelid
                LEFT JOIN pg_stat_user_indexes index_stats
                  ON index_stats.indexrelid = index_meta.indexrelid
                JOIN LATERAL unnest(
                    index_meta.indkey::smallint[],
                    index_meta.indclass::oid[],
                    index_meta.indcollation::oid[],
                    index_meta.indoption::smallint[]
                ) WITH ORDINALITY
                    AS key_column(attnum, opclass_oid, collation_oid, option_bits, ordinality)
                    ON key_column.ordinality <= index_meta.indnkeyatts
                JOIN pg_opclass operator_class ON operator_class.oid = key_column.opclass_oid
                LEFT JOIN pg_attribute attribute
                    ON attribute.attrelid = table_class.oid
                   AND attribute.attnum = key_column.attnum
                WHERE namespace.nspname = %s
                GROUP BY namespace.nspname,
                         table_class.relname,
                         index_class.relname,
                         index_meta.indisvalid,
                         index_meta.indisready,
                         index_meta.indisunique,
                         index_meta.indisprimary,
                         index_meta.indisexclusion,
                         (index_meta.indpred IS NOT NULL),
                         (index_meta.indexprs IS NOT NULL),
                         access_method.amname,
                         index_stats.idx_scan,
                         index_meta.indkey,
                         index_meta.indnkeyatts,
                         index_meta.indrelid,
                         pg_relation_size(index_class.oid)
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


def build_workload_readiness_report(
    *, schema: str = "public", min_calls: int = 100, limit: int = 20
) -> dict[str, Any]:
    """Explain whether the database can provide useful review evidence."""
    snapshot = collect_workload_snapshot(
        schema=schema,
        min_calls=min_calls,
        limit=limit,
        require_pg_stat_statements=False,
    )
    source = snapshot.get("source", {})
    server_version_num = int(source.get("server_version_num", 0) or 0)
    pgss_available = bool(source.get("pg_stat_statements_available"))
    hypopg_available = bool(source.get("hypopg_available"))
    workload_rows = len(snapshot.get("workload", []))
    read_only = str(source.get("transaction_read_only", "")).lower() in {
        "on",
        "true",
        "1",
    }
    checks = [
        {
            "code": "read_only_transaction",
            "status": "pass" if read_only else "fail",
            "detail": "Catalog collection ran in a read-only transaction.",
        },
        {
            "code": "pg_stat_statements",
            "status": "pass" if pgss_available else "fail",
            "detail": (
                "Workload statistics extension is available."
                if pgss_available
                else "pg_stat_statements is not installed in this database."
            ),
        },
        {
            "code": "representative_workload",
            "status": "pass" if workload_rows else "warn",
            "detail": (
                f"{workload_rows} qualifying workload rows met min_calls={min_calls}."
                if workload_rows
                else f"No qualifying workload rows met min_calls={min_calls}."
            ),
        },
        {
            "code": "catalog_visibility",
            "status": "pass" if snapshot.get("table_stats") else "warn",
            "detail": f"{len(snapshot.get('table_stats', []))} user tables are visible in schema {schema}.",
        },
        {
            "code": "hypopg",
            "status": "pass" if hypopg_available else "optional",
            "detail": (
                "HypoPG is available."
                if hypopg_available
                else "HypoPG is not installed; catalog-only reviews still work."
            ),
        },
        {
            "code": "generic_plan_support",
            "status": "pass" if server_version_num >= 160000 else "warn",
            "detail": (
                "PostgreSQL supports placeholder-safe GENERIC_PLAN review."
                if server_version_num >= 160000
                else "PostgreSQL 16+ is required for placeholder-safe HypoPG review."
            ),
        },
    ]
    if not read_only or not pgss_available:
        status = "not_ready"
        reason = "a required read-only workload evidence check failed"
    elif not workload_rows:
        status = "needs_workload"
        reason = "the connection works, but the selected workload window is empty"
    elif not hypopg_available or server_version_num < 160000:
        status = "ready_without_planner_validation"
        reason = "catalog and workload review are ready; optional planner validation is unavailable"
    else:
        status = "ready"
        reason = "catalog, workload, and optional planner evidence are available"
    return {
        "report_type": "indexpilot_readiness",
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "advisory_only": True,
        "schema": schema,
        "source": source,
        "summary": {
            "status": status,
            "reason": reason,
            "workload_rows": workload_rows,
            "visible_tables": len(snapshot.get("table_stats", [])),
            "visible_indexes": len(snapshot.get("indexes", [])),
        },
        "checks": checks,
        "next_command": (
            f"indexpilot review --schema {schema} --min-calls {min_calls}"
            + (" --hypopg" if hypopg_available and server_version_num >= 160000 else "")
        ),
    }


def render_readiness_markdown(report: dict[str, Any]) -> str:
    """Render the workload readiness report for setup and CI logs."""
    summary = report.get("summary", {})
    source = report.get("source", {})
    lines = [
        "# IndexPilot workload readiness",
        "",
        f"**Status:** `{summary.get('status', 'not_ready')}`",
        "",
        f"**Why:** {summary.get('reason', '')}",
        "",
        "## Source",
        "",
        f"- Database: `{source.get('database_name', 'unknown')}`",
        f"- PostgreSQL: `{source.get('server_version', 'unknown')}`",
        f"- pg_stat_statements reset: `{source.get('pg_stat_statements_reset_at')}`",
        f"- Database statistics reset: `{source.get('database_stats_reset_at')}`",
        "",
        "## Checks",
        "",
    ]
    for check in report.get("checks", []):
        lines.append(
            f"- `{check.get('status', 'unknown')}` `{check.get('code', 'check')}`: "
            f"{check.get('detail', '')}"
        )
    lines.extend(
        [
            "",
            "## Next command",
            "",
            "```bash",
            str(report.get("next_command", "indexpilot review")),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def analyze_index_sprawl_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Report conservative index-shape overlap without claiming safe deletion."""
    indexes_by_table: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    skipped_non_comparable = 0
    for raw_index in snapshot.get("indexes", []):
        if not _is_comparable_simple_btree(raw_index):
            skipped_non_comparable += 1
            continue
        key = (
            str(raw_index.get("schema_name", "")).lower(),
            str(raw_index.get("table_name", "")).lower(),
        )
        indexes_by_table[key].append(_public_index_evidence(raw_index))

    findings: list[dict[str, Any]] = []
    for (schema, table), indexes in sorted(indexes_by_table.items()):
        for left_position, left in enumerate(indexes):
            for right in indexes[left_position + 1 :]:
                left_columns = [str(column).lower() for column in left["columns"]]
                right_columns = [str(column).lower() for column in right["columns"]]
                if not left_columns or not right_columns:
                    continue
                same_keys = left_columns == right_columns
                same_includes = sorted(left["include_columns"]) == sorted(right["include_columns"])
                same_uniqueness = left["is_unique"] == right["is_unique"]
                if same_keys and same_includes and same_uniqueness:
                    finding_type = "exact_duplicate_shape"
                elif (
                    left_columns == right_columns[: len(left_columns)]
                    or right_columns == left_columns[: len(right_columns)]
                ):
                    finding_type = "leading_prefix_overlap"
                else:
                    continue
                protected = any(
                    bool(index[field])
                    for index in (left, right)
                    for field in (
                        "is_primary",
                        "is_exclusion",
                        "is_constraint_owned",
                    )
                )
                findings.append(
                    {
                        "type": finding_type,
                        "schema": schema,
                        "table": table,
                        "left": left,
                        "right": right,
                        "constraint_protected": protected,
                        "action": "manual_review",
                        "safe_to_drop": False,
                        "evidence_scope": "catalog_shape_and_cumulative_usage_counters",
                    }
                )

    status = "review_candidates_found" if findings else "no_comparable_overlap_found"
    return {
        "report_type": "indexpilot_index_sprawl",
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "advisory_only": True,
        "source": snapshot.get("source", {}),
        "schema": snapshot.get("schema"),
        "summary": {
            "status": status,
            "indexes_inspected": len(snapshot.get("indexes", [])),
            "comparable_indexes": sum(len(items) for items in indexes_by_table.values()),
            "skipped_non_comparable_indexes": skipped_non_comparable,
            "overlap_findings": len(findings),
        },
        "findings": findings,
        "limits": [
            "Overlap is not proof that an index is redundant or safe to drop.",
            "Usage counters are cumulative and can be reset; rare or seasonal queries may be absent.",
            "Partial, expression, invalid, not-ready, non-B-tree, and non-default physical shapes were not compared.",
            "No DROP INDEX statement is generated or executed.",
        ],
    }


def build_index_sprawl_report(*, schema: str = "public") -> dict[str, Any]:
    """Collect a read-only catalog snapshot and report possible index overlap."""
    snapshot = collect_workload_snapshot(
        schema=schema,
        min_calls=1,
        limit=1,
        require_pg_stat_statements=False,
    )
    return analyze_index_sprawl_snapshot(snapshot)


def render_index_sprawl_markdown(report: dict[str, Any]) -> str:
    """Render factual index overlap findings without drop instructions."""
    summary = report.get("summary", {})
    source = report.get("source", {})
    lines = [
        "# IndexPilot existing-index overlap review",
        "",
        "> Advisory only. This report never declares an index safe to drop.",
        "",
        f"**Status:** `{summary.get('status', 'unknown')}`",
        "",
        f"- Indexes inspected: {summary.get('indexes_inspected', 0)}",
        f"- Comparable ordinary B-trees: {summary.get('comparable_indexes', 0)}",
        f"- Possible overlap findings: {summary.get('overlap_findings', 0)}",
        f"- Database statistics reset: `{source.get('database_stats_reset_at')}`",
        "",
        "## Findings",
        "",
    ]
    findings = report.get("findings", [])
    if not findings:
        lines.append("No comparable ordinary B-tree overlap was found.")
    for position, finding in enumerate(findings, start=1):
        left = finding.get("left", {})
        right = finding.get("right", {})
        lines.extend(
            [
                f"### {position}. `{finding.get('schema')}.{finding.get('table')}`",
                "",
                f"- Finding: `{finding.get('type')}`",
                f"- Left: `{left.get('name')}` on `{left.get('columns')}`; "
                f"{left.get('index_scans', 0)} scans; {left.get('index_size_bytes', 0)} bytes",
                f"- Right: `{right.get('name')}` on `{right.get('columns')}`; "
                f"{right.get('index_scans', 0)} scans; {right.get('index_size_bytes', 0)} bytes",
                f"- Constraint-protected pair: `{finding.get('constraint_protected', False)}`",
                "- Action: manual review only; this is not safe-to-drop proof.",
                "",
            ]
        )
    lines.extend(["## Limits", ""])
    for limit in report.get("limits", []):
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


def _parse_report_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _exact_existing_indexes(report: dict[str, Any]) -> list[dict[str, Any]]:
    proposal = report.get("proposal", {})
    wanted_columns = [str(column).lower() for column in proposal.get("columns", [])]
    candidates = report.get("candidates") or []
    evidence = candidates[0].get("evidence", {}) if candidates else {}
    matches = []
    for index in evidence.get("existing_indexes", []):
        columns = [str(column).lower() for column in index.get("columns", [])]
        if columns == wanted_columns and _is_comparable_simple_btree(index):
            matches.append(index)
    return matches


def compare_index_review_reports(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compare two exact-index reports without claiming causal performance gains."""
    for label, report in (("before", before), ("after", after)):
        if report.get("report_type") != "indexpilot_index_review":
            raise ValueError(f"{label}_report_must_be_indexpilot_index_review")
        if int(report.get("report_version", 0) or 0) < 1:
            raise ValueError(f"{label}_report_version_unsupported")

    before_proposal = before.get("proposal", {})
    after_proposal = after.get("proposal", {})
    identity_fields = ("schema", "table", "columns")
    if any(before_proposal.get(field) != after_proposal.get(field) for field in identity_fields):
        raise ValueError("proposal_identity_mismatch")

    before_source = before.get("source", {})
    after_source = after.get("source", {})
    before_database = before_source.get("database_name")
    after_database = after_source.get("database_name")
    if not before_database or not after_database:
        raise ValueError("source_database_missing")
    if before_database != after_database:
        raise ValueError("source_database_mismatch")
    before_time = _parse_report_time(before.get("generated_at"))
    after_time = _parse_report_time(after.get("generated_at"))
    if not before_time or not after_time or after_time <= before_time:
        raise ValueError("report_time_order_invalid")

    before_matches = _exact_existing_indexes(before)
    after_matches = _exact_existing_indexes(after)
    pgss_epoch_matches = bool(
        before_source.get("pg_stat_statements_reset_at")
        and before_source.get("pg_stat_statements_reset_at")
        == after_source.get("pg_stat_statements_reset_at")
    )
    database_epoch_matches = bool(
        before_source.get("database_stats_reset_at")
        and before_source.get("database_stats_reset_at")
        == after_source.get("database_stats_reset_at")
    )

    if before_matches:
        status = "inconclusive"
        reason = "the baseline already contained an exact comparable index shape"
        observed_index = None
    elif not after_matches:
        status = "inconclusive"
        reason = "the later report does not contain the exact comparable index shape"
        observed_index = None
    else:
        proposal_name = after_proposal.get("index_name")
        named_matches = [
            index for index in after_matches if proposal_name and index.get("name") == proposal_name
        ]
        observed_index = (named_matches or after_matches)[0]
        if int(observed_index.get("index_scans", 0) or 0) > 0:
            status = "usage_observed"
            reason = "PostgreSQL recorded scans on the exact index shape in the later snapshot"
        else:
            status = "no_usage_observed"
            reason = "the later snapshot recorded no scans on the exact index shape"

    before_candidate = (before.get("candidates") or [{}])[0]
    after_candidate = (after.get("candidates") or [{}])[0]
    before_expression = before_candidate.get("expression", {})
    after_expression = after_candidate.get("expression", {})
    workload_delta = None
    if pgss_epoch_matches:
        before_calls = int(before_expression.get("calls", 0) or 0)
        after_calls = int(after_expression.get("calls", 0) or 0)
        before_total_ms = float(before_expression.get("total_exec_time_ms", 0.0) or 0.0)
        after_total_ms = float(after_expression.get("total_exec_time_ms", 0.0) or 0.0)
        if after_calls >= before_calls and after_total_ms >= before_total_ms:
            workload_delta = {
                "matching_calls": after_calls - before_calls,
                "matching_total_exec_time_ms": round(
                    after_total_ms - before_total_ms,
                    3,
                ),
            }

    before_activity = before_candidate.get("evidence", {}).get("table_activity", {})
    after_activity = after_candidate.get("evidence", {}).get("table_activity", {})
    table_activity_delta = None
    if database_epoch_matches:
        fields = ("inserts", "updates", "deletes", "hot_updates")
        deltas = {
            field: int(after_activity.get(field, 0) or 0) - int(before_activity.get(field, 0) or 0)
            for field in fields
        }
        if all(value >= 0 for value in deltas.values()):
            table_activity_delta = deltas

    return {
        "report_type": "indexpilot_index_observation",
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "advisory_only": True,
        "proposal": {
            field: before_proposal.get(field)
            for field in ("schema", "table", "columns", "index_name")
        },
        "source": {
            "database_name": before_source.get("database_name"),
            "pg_stat_statements_epoch_matches": pgss_epoch_matches,
            "database_stats_epoch_matches": database_epoch_matches,
            "before_generated_at": before.get("generated_at"),
            "after_generated_at": after.get("generated_at"),
        },
        "verdict": {"status": status, "reason": reason},
        "observed_index": observed_index,
        "workload_delta": workload_delta,
        "table_activity_delta": table_activity_delta,
        "limits": [
            "Recorded scans show use, not that the index improved latency or earned its write cost.",
            "Zero recorded scans are not proof that an index is safe to drop; rare and seasonal queries may be absent.",
            "Workload and table-activity deltas are omitted when their reset epochs differ or counters regress.",
            "No index was created, dropped, or changed by this comparison.",
        ],
    }


def render_index_observation_markdown(report: dict[str, Any]) -> str:
    """Render the cautious post-deployment index observation."""
    proposal = report.get("proposal", {})
    verdict = report.get("verdict", {})
    observed = report.get("observed_index") or {}
    lines = [
        "# IndexPilot post-deployment index observation",
        "",
        "> Advisory only. This is usage evidence, not causal performance proof.",
        "",
        f"**Verdict:** `{verdict.get('status', 'inconclusive')}`",
        "",
        f"**Why:** {verdict.get('reason', '')}",
        "",
        "## Index",
        "",
        f"- Target: `{proposal.get('schema')}.{proposal.get('table')}`",
        f"- Columns: `{proposal.get('columns', [])}`",
        f"- Observed index: `{observed.get('name')}`",
        f"- Recorded scans: {observed.get('index_scans', 0)}",
        f"- Size: {observed.get('index_size_bytes', 0)} bytes",
        "",
        "## Comparable windows",
        "",
        f"- Workload statistics epoch matches: `{report.get('source', {}).get('pg_stat_statements_epoch_matches', False)}`",
        f"- Database statistics epoch matches: `{report.get('source', {}).get('database_stats_epoch_matches', False)}`",
        f"- Workload delta: `{report.get('workload_delta')}`",
        f"- Table activity delta: `{report.get('table_activity_delta')}`",
        "",
        "## Limits",
        "",
    ]
    for limit in report.get("limits", []):
        lines.append(f"- {limit}")
    lines.append("")
    return "\n".join(lines)


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
    report["verdict"] = derive_review_verdict(report)
    return report


def _finalize_index_review(
    snapshot: dict[str, Any],
    report: dict[str, Any],
    *,
    validate_hypopg: bool,
) -> dict[str, Any]:
    """Attach optional planner evidence and the stable verdict to one review."""
    matching_queries = report["summary"]["matching_workload_fingerprints"]
    if validate_hypopg and not report["existing_overlap"] and matching_queries:
        report = validate_report_with_hypopg(snapshot, report)
    elif validate_hypopg:
        reason = "existing_overlap" if report["existing_overlap"] else "no_matching_workload"
        report["planner_validation"] = {
            "requested": True,
            "tool": "hypopg",
            "status": "not_run",
            "reason": reason,
        }

    from src.auto_indexer import review_planner_recommendations

    report["auto_indexer_review"] = review_planner_recommendations(report)
    candidate_validation = report["candidates"][0].get("planner_validation", {})
    report["evidence_scope"]["representative_queries_planned"] = (
        1 if candidate_validation.get("baseline") else 0
    )
    report["verdict"] = derive_review_verdict(report)
    deployment_blockers = [
        note.get("code")
        for note in report.get("operational_notes", [])
        if note.get("level") == "blocker"
    ]
    if deployment_blockers and report["verdict"]["status"] == "worth_benchmarking":
        report["verdict"] = {
            "status": "inconclusive",
            "reason": (
                "planner evidence passed, but the proposed deployment form is unsupported: "
                + ", ".join(str(code) for code in deployment_blockers)
            ),
        }
    return report


def build_index_review_report(
    candidate_sql: str,
    *,
    default_schema: str = "public",
    min_calls: int = 100,
    limit: int = 200,
    validate_hypopg: bool = False,
) -> dict[str, Any]:
    """Review one simple proposed index without executing the supplied SQL."""
    proposal = parse_proposed_index(candidate_sql, default_schema=default_schema)
    snapshot = collect_workload_snapshot(
        schema=proposal["schema"], min_calls=min_calls, limit=limit
    )
    report = analyze_proposed_index_snapshot(snapshot, proposal)
    return _finalize_index_review(snapshot, report, validate_hypopg=validate_hypopg)


def _migration_overlap_findings(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find exact and leading-prefix overlap inside one migration."""
    findings: list[dict[str, Any]] = []
    for left_position, left in enumerate(proposals):
        for right in proposals[left_position + 1 :]:
            left_index_name = left.get("index_name")
            right_index_name = right.get("index_name")
            if (
                left["schema"] == right["schema"]
                and left_index_name
                and left_index_name == right_index_name
            ):
                findings.append(
                    {
                        "type": "duplicate_index_name",
                        "schema": left["schema"],
                        "index_name": left_index_name,
                        "left_table": left["table"],
                        "right_table": right["table"],
                        "left_statement": left.get("statement_number"),
                        "right_statement": right.get("statement_number"),
                        "action": "rename_index",
                        "safe_to_drop": False,
                    }
                )
                continue
            if (left["schema"], left["table"]) != (right["schema"], right["table"]):
                continue
            left_columns = [str(column) for column in left["columns"]]
            right_columns = [str(column) for column in right["columns"]]
            if left_columns == right_columns:
                finding_type = "exact_duplicate_shape"
            elif (
                left_columns == right_columns[: len(left_columns)]
                or right_columns == left_columns[: len(right_columns)]
            ):
                finding_type = "leading_prefix_overlap"
            else:
                continue
            findings.append(
                {
                    "type": finding_type,
                    "schema": left["schema"],
                    "table": left["table"],
                    "left_table": left["table"],
                    "right_table": right["table"],
                    "left_statement": left.get("statement_number"),
                    "left_columns": left_columns,
                    "right_statement": right.get("statement_number"),
                    "right_columns": right_columns,
                    "action": "manual_review",
                    "safe_to_drop": False,
                }
            )
    return findings


def build_migration_review_report(
    migration_sql: str,
    *,
    default_schema: str = "public",
    min_calls: int = 100,
    limit: int = 200,
    validate_hypopg: bool = False,
) -> dict[str, Any]:
    """Review every supported ``CREATE INDEX`` in one migration read-only."""
    parsed = parse_migration_indexes(migration_sql, default_schema=default_schema)
    proposals = list(parsed["proposals"])
    snapshots: dict[str, dict[str, Any]] = {}
    for schema in dict.fromkeys(str(proposal["schema"]) for proposal in proposals):
        snapshots[schema] = collect_workload_snapshot(
            schema=schema, min_calls=min_calls, limit=limit
        )

    reviews: list[dict[str, Any]] = []
    for proposal in proposals:
        snapshot = snapshots[str(proposal["schema"])]
        review = analyze_proposed_index_snapshot(snapshot, proposal)
        reviews.append(_finalize_index_review(snapshot, review, validate_hypopg=validate_hypopg))

    verdict_counts: dict[str, int] = defaultdict(int)
    for review in reviews:
        verdict_counts[str(review["verdict"]["status"])] += 1
    overlap_findings = _migration_overlap_findings(proposals)
    return {
        "report_type": "indexpilot_migration_review",
        "report_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "advisory_only": True,
        "parser": {"backend": PARSER_BACKEND, "regex_fallback": False},
        "migration": {
            "statement_count": parsed["statement_count"],
            "ignored_non_index_statements": parsed["ignored_statement_count"],
            "reviewed_index_statements": len(reviews),
        },
        "sources": {schema: snapshot.get("source", {}) for schema, snapshot in snapshots.items()},
        "summary": {
            "reviewed_indexes": len(reviews),
            "snapshot_count": len(snapshots),
            "verdict_counts": dict(sorted(verdict_counts.items())),
            "migration_overlap_findings": len(overlap_findings),
        },
        "reviews": reviews,
        "migration_overlap_findings": overlap_findings,
        "limits": [
            "Only supported CREATE INDEX statements were reviewed; other migration statements were ignored.",
            "Each candidate was tested independently; interactions between proposed indexes were not planned together.",
            "No index or migration statement was executed.",
            "Planner evidence is not measured latency or deployment-safety proof.",
        ],
    }
