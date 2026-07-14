#!/usr/bin/env python3
"""Benchmark candidate indexes on an isolated, read-only-derived workload copy.

This case runner intentionally copies only non-sensitive filter/order columns
from ProfitPilot.  The source connection is forced read-only, while all DDL and
insert measurements run in a database whose name starts with
``indexpilot_benchmark_``.
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2 import sql

SCHEMA = "indexpilot_benchmark"
CASES = (
    {
        "source_table": "action_audit",
        "target_table": "action_audit",
        "key_column": "action_type",
        "timestamp_column": "timestamp",
        "padding_bytes": 580,
        "variants": (("timestamp",), ("action_type", "timestamp")),
    },
    {
        "source_table": "tick_data",
        "target_table": "tick_data",
        "key_column": "symbol",
        "timestamp_column": "timestamp",
        "padding_bytes": 70,
        "variants": (("timestamp",), ("symbol", "timestamp")),
    },
)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * fraction))))
    return ordered[position]


def _source_proof(cursor: Any) -> dict[str, Any]:
    cursor.execute("SELECT count(*) FROM public.action_audit")
    action_rows = int(cursor.fetchone()[0])
    cursor.execute("SELECT count(*) FROM public.tick_data")
    tick_rows = int(cursor.fetchone()[0])
    cursor.execute("SELECT count(*) FROM pg_extension WHERE extname = 'hypopg'")
    hypopg_count = int(cursor.fetchone()[0])
    cursor.execute("SELECT count(*) FROM pg_indexes WHERE indexname LIKE '%_dna'")
    dna_indexes = int(cursor.fetchone()[0])
    return {
        "action_audit_rows": action_rows,
        "tick_data_rows": tick_rows,
        "hypopg_extensions": hypopg_count,
        "dna_indexes": dna_indexes,
    }


def _database_identity(connection: Any) -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_database(), COALESCE(inet_server_addr()::text, 'local'), "
            "pg_postmaster_start_time()::text"
        )
        database, address, started_at = cursor.fetchone()
    return {"database": database, "server_address": address, "server_started_at": started_at}


def _prepare_target(target: Any) -> None:
    target.autocommit = True
    identity = _database_identity(target)
    if not identity["database"].startswith("indexpilot_benchmark_"):
        raise RuntimeError("target_database_name_must_start_with_indexpilot_benchmark_")

    with target.cursor() as cursor:
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(SCHEMA)))
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(SCHEMA)))
        cursor.execute(
            sql.SQL("CREATE TABLE {}.benchmark_marker (created_at timestamptz NOT NULL)").format(
                sql.Identifier(SCHEMA)
            )
        )
        cursor.execute(
            sql.SQL("INSERT INTO {}.benchmark_marker VALUES (clock_timestamp())").format(
                sql.Identifier(SCHEMA)
            )
        )

        for case in CASES:
            cursor.execute(
                sql.SQL(
                    "CREATE TABLE {}.{} ({} text NOT NULL, {} timestamptz NOT NULL, "
                    "payload_padding text NOT NULL DEFAULT repeat('x', {}))"
                ).format(
                    sql.Identifier(SCHEMA),
                    sql.Identifier(case["target_table"]),
                    sql.Identifier(case["key_column"]),
                    sql.Identifier(case["timestamp_column"]),
                    sql.Literal(case["padding_bytes"]),
                )
            )


def _copy_case(source: Any, target: Any, case: dict[str, Any]) -> int:
    buffer = io.StringIO()
    with source.cursor() as source_cursor:
        copy_out = sql.SQL(
            "COPY (SELECT {}, {} FROM public.{} WHERE {} IS NOT NULL AND {} IS NOT NULL) "
            "TO STDOUT WITH (FORMAT CSV)"
        ).format(
            sql.Identifier(case["key_column"]),
            sql.Identifier(case["timestamp_column"]),
            sql.Identifier(case["source_table"]),
            sql.Identifier(case["key_column"]),
            sql.Identifier(case["timestamp_column"]),
        )
        source_cursor.copy_expert(copy_out.as_string(source), buffer)

    buffer.seek(0)
    with target.cursor() as target_cursor:
        copy_in = sql.SQL("COPY {}.{} ({}, {}) FROM STDIN WITH (FORMAT CSV)").format(
            sql.Identifier(SCHEMA),
            sql.Identifier(case["target_table"]),
            sql.Identifier(case["key_column"]),
            sql.Identifier(case["timestamp_column"]),
        )
        target_cursor.copy_expert(copy_in.as_string(target), buffer)
        target_cursor.execute(
            sql.SQL("ANALYZE {}.{}").format(
                sql.Identifier(SCHEMA), sql.Identifier(case["target_table"])
            )
        )
        target_cursor.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(SCHEMA), sql.Identifier(case["target_table"])
            )
        )
        return int(target_cursor.fetchone()[0])


def _representative_parameters(target: Any, case: dict[str, Any]) -> tuple[Any, Any, int]:
    with target.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                "SELECT {}, percentile_disc(0.90) WITHIN GROUP (ORDER BY {}) "
                "FROM {}.{} GROUP BY {} ORDER BY count(*) DESC LIMIT 1"
            ).format(
                sql.Identifier(case["key_column"]),
                sql.Identifier(case["timestamp_column"]),
                sql.Identifier(SCHEMA),
                sql.Identifier(case["target_table"]),
                sql.Identifier(case["key_column"]),
            )
        )
        key_value, cutoff = cursor.fetchone()
        cursor.execute(
            sql.SQL("SELECT count(*) FROM {}.{} WHERE {} = %s AND {} >= %s").format(
                sql.Identifier(SCHEMA),
                sql.Identifier(case["target_table"]),
                sql.Identifier(case["key_column"]),
                sql.Identifier(case["timestamp_column"]),
            ),
            (key_value, cutoff),
        )
        matching_rows = int(cursor.fetchone()[0])
    return key_value, cutoff, matching_rows


def _query_sql(case: dict[str, Any]) -> sql.Composed:
    return sql.SQL(
        "SELECT {}, {}, payload_padding FROM {}.{} "
        "WHERE {} = %s AND {} >= %s ORDER BY {} DESC LIMIT 100"
    ).format(
        sql.Identifier(case["key_column"]),
        sql.Identifier(case["timestamp_column"]),
        sql.Identifier(SCHEMA),
        sql.Identifier(case["target_table"]),
        sql.Identifier(case["key_column"]),
        sql.Identifier(case["timestamp_column"]),
        sql.Identifier(case["timestamp_column"]),
    )


def _plan_summary(cursor: Any, query: sql.Composed, parameters: tuple[Any, Any]) -> dict[str, Any]:
    cursor.execute(sql.SQL("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ") + query, parameters)
    document = cursor.fetchone()[0][0]
    node_types: list[str] = []
    index_names: list[str] = []

    def walk(node: dict[str, Any]) -> None:
        node_type = str(node.get("Node Type", "Unknown"))
        if node_type not in node_types:
            node_types.append(node_type)
        if node.get("Index Name") and node["Index Name"] not in index_names:
            index_names.append(node["Index Name"])
        for child in node.get("Plans", []):
            walk(child)

    walk(document["Plan"])
    return {
        "planning_ms": round(float(document.get("Planning Time", 0.0)), 3),
        "execution_ms": round(float(document.get("Execution Time", 0.0)), 3),
        "node_types": node_types,
        "index_names": index_names,
        "shared_hit_blocks": int(document["Plan"].get("Shared Hit Blocks", 0) or 0),
        "shared_read_blocks": int(document["Plan"].get("Shared Read Blocks", 0) or 0),
    }


def _measure_query(
    target: Any,
    case: dict[str, Any],
    parameters: tuple[Any, Any],
    runs: int,
) -> dict[str, Any]:
    query = _query_sql(case)
    durations: list[float] = []
    with target.cursor() as cursor:
        for _ in range(5):
            cursor.execute(query, parameters)
            cursor.fetchall()
        for _ in range(runs):
            started = time.perf_counter()
            cursor.execute(query, parameters)
            cursor.fetchall()
            durations.append((time.perf_counter() - started) * 1000.0)
        plan = _plan_summary(cursor, query, parameters)
    return {
        "runs": runs,
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(_percentile(durations, 0.95), 3),
        "plan": plan,
    }


def _measure_write(target: Any, case: dict[str, Any], batch_size: int) -> dict[str, Any]:
    insert_statement = sql.SQL(
        "INSERT INTO {}.{} ({}, {}) "
        "SELECT %s, clock_timestamp() + (item * interval '1 microsecond') "
        "FROM generate_series(1, %s) AS item"
    ).format(
        sql.Identifier(SCHEMA),
        sql.Identifier(case["target_table"]),
        sql.Identifier(case["key_column"]),
        sql.Identifier(case["timestamp_column"]),
    )
    durations: list[float] = []
    target.autocommit = False
    try:
        with target.cursor() as cursor:
            for _ in range(7):
                started = time.perf_counter()
                cursor.execute(insert_statement, ("__indexpilot_benchmark__", batch_size))
                durations.append((time.perf_counter() - started) * 1000.0)
                target.rollback()
    finally:
        target.rollback()
        target.autocommit = True
    return {
        "batch_rows": batch_size,
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(_percentile(durations, 0.95), 3),
        "transaction_rolled_back": True,
    }


def _benchmark_case(
    target: Any, case: dict[str, Any], runs: int, batch_size: int
) -> dict[str, Any]:
    key_value, cutoff, matching_rows = _representative_parameters(target, case)
    parameters = (key_value, cutoff)
    baseline_query = _measure_query(target, case, parameters, runs)
    baseline_write = _measure_write(target, case, batch_size)
    variants: list[dict[str, Any]] = []

    for position, columns in enumerate(case["variants"]):
        index_name = f"idx_benchmark_{case['target_table']}_{position}"
        create_statement = sql.SQL("CREATE INDEX {} ON {}.{} ({})").format(
            sql.Identifier(index_name),
            sql.Identifier(SCHEMA),
            sql.Identifier(case["target_table"]),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        )
        with target.cursor() as cursor:
            started = time.perf_counter()
            cursor.execute(create_statement)
            build_ms = (time.perf_counter() - started) * 1000.0
            cursor.execute(
                sql.SQL("ANALYZE {}.{}").format(
                    sql.Identifier(SCHEMA), sql.Identifier(case["target_table"])
                )
            )
            cursor.execute("SELECT pg_relation_size(%s::regclass)", (f"{SCHEMA}.{index_name}",))
            index_size_bytes = int(cursor.fetchone()[0])

        query_result = _measure_query(target, case, parameters, runs)
        write_result = _measure_write(target, case, batch_size)
        with target.cursor() as cursor:
            started = time.perf_counter()
            cursor.execute(
                sql.SQL("DROP INDEX {}.{}").format(
                    sql.Identifier(SCHEMA), sql.Identifier(index_name)
                )
            )
            rollback_ms = (time.perf_counter() - started) * 1000.0
            cursor.execute(
                "SELECT count(*) FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
                (SCHEMA, index_name),
            )
            index_absent = int(cursor.fetchone()[0]) == 0
        rollback_query = _measure_query(target, case, parameters, runs)

        baseline_median = baseline_query["median_ms"]
        baseline_write_median = baseline_write["median_ms"]
        variants.append(
            {
                "columns": list(columns),
                "build_ms": round(build_ms, 3),
                "index_size_bytes": index_size_bytes,
                "query": query_result,
                "latency_change_pct": round(
                    ((query_result["median_ms"] - baseline_median) / baseline_median) * 100.0,
                    2,
                )
                if baseline_median
                else None,
                "write": write_result,
                "write_overhead_pct": round(
                    ((write_result["median_ms"] - baseline_write_median) / baseline_write_median)
                    * 100.0,
                    2,
                )
                if baseline_write_median
                else None,
                "rollback": {
                    "drop_ms": round(rollback_ms, 3),
                    "index_absent": index_absent,
                    "query": rollback_query,
                },
            }
        )

    return {
        "source_table": case["source_table"],
        "copied_rows": int(
            next(
                item["copied_rows"]
                for item in _COPIED_CASES
                if item["source_table"] == case["source_table"]
            )
        ),
        "representative_matching_rows": matching_rows,
        "representative_values_redacted": True,
        "baseline": {"query": baseline_query, "write": baseline_write},
        "variants": variants,
    }


_COPIED_CASES: list[dict[str, Any]] = []


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dsn", required=True)
    parser.add_argument("--target-dsn", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--write-batch", type=int, default=1000)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.runs < 5 or args.write_batch < 1:
        raise SystemExit("runs must be >= 5 and write-batch must be >= 1")

    source = psycopg2.connect(args.source_dsn)
    target = psycopg2.connect(args.target_dsn)
    try:
        source_identity = _database_identity(source)
        target_identity = _database_identity(target)
        if source_identity == target_identity:
            raise RuntimeError("source_and_target_must_be_different_databases")

        source.rollback()
        target.rollback()
        with source.cursor() as source_cursor:
            source_cursor.execute("SET TRANSACTION READ ONLY")
            source_cursor.execute("SHOW transaction_read_only")
            if source_cursor.fetchone()[0] != "on":
                raise RuntimeError("source_transaction_is_not_read_only")
            proof_before = _source_proof(source_cursor)

        _prepare_target(target)
        for case in CASES:
            copied_rows = _copy_case(source, target, case)
            _COPIED_CASES.append({"source_table": case["source_table"], "copied_rows": copied_rows})

        results = [_benchmark_case(target, case, args.runs, args.write_batch) for case in CASES]
        with source.cursor() as source_cursor:
            proof_after = _source_proof(source_cursor)

        report = {
            "report_type": "indexpilot_production_copy_benchmark",
            # timezone.utc preserves the documented Python 3.10 compatibility.
            "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
            "source": {
                "database": source_identity["database"],
                "transaction_read_only": True,
                "copied_columns": {
                    "action_audit": ["action_type", "timestamp"],
                    "tick_data": ["symbol", "timestamp"],
                },
                "raw_values_in_report": False,
                "proof_before": proof_before,
                "proof_after": proof_after,
                "unchanged_during_benchmark": proof_before == proof_after,
            },
            "target": {
                "database": target_identity["database"],
                "guard_prefix_verified": True,
                "synthetic_padding_used": True,
            },
            "method": {
                "query_runs": args.runs,
                "warmup_runs": 5,
                "write_batch_rows": args.write_batch,
                "write_transactions_rolled_back": True,
                "real_indexes_created_only_on_target": True,
            },
            "cases": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"Benchmark complete: {args.output.resolve()}")
        print(f"ProfitPilot source unchanged: {proof_before == proof_after}")
        return 0
    finally:
        source.rollback()
        source.close()
        target.close()


if __name__ == "__main__":
    raise SystemExit(main())
