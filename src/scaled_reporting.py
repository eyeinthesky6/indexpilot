"""Enhanced reporting for scaled simulations - compares baseline vs auto-index

This module provides comprehensive reporting functionality including:
- Basic reporting (generate_report)
- Scaled simulation reporting (generate_scaled_report)
- Performance comparisons
- Index analysis
- Mutation summaries
"""

import json
import logging
import os

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.paths import get_report_path
from src.type_definitions import DatabaseRow, JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load config for reporting toggle
try:
    from src.config_loader import ConfigLoader

    _config_loader: ConfigLoader | None = ConfigLoader()
except Exception:
    _config_loader = None


def is_reporting_enabled() -> bool:
    """Check if reporting is enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("operational.reporting.enabled", True)


def load_results(filename: str) -> JSONValue | None:
    """Load results from JSON file"""
    filepath = get_report_path(filename)
    if os.path.exists(filepath):
        with open(filepath, encoding="utf-8") as f:
            loaded_data: object = json.load(f)
            # json.load returns Any, but JSONValue covers all JSON-serializable types
            # This is safe because json.load only returns JSON-serializable values
            return loaded_data  # type: ignore[return-value]
    return None


def get_index_analysis():
    """Analyze created indexes and validate against query patterns"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get all created indexes
            cursor.execute(
                """
                SELECT
                    table_name,
                    field_name,
                    details_json,
                    created_at
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                ORDER BY created_at DESC
            """
            )
            indexes = cursor.fetchall()

            # Get query stats for these fields
            cursor.execute(
                """
                SELECT
                    table_name,
                    field_name,
                    COUNT(*) as total_queries,
                    AVG(duration_ms) as avg_duration_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_duration_ms
                FROM query_stats
                WHERE field_name IS NOT NULL
                GROUP BY table_name, field_name
                ORDER BY total_queries DESC
            """
            )
            query_stats = cursor.fetchall()

            # Build analysis
            index_map: dict[tuple[str, str], DatabaseRow] = {
                (str(idx.get("table_name", "")), str(idx.get("field_name", ""))): idx
                for idx in indexes
            }
            query_map: dict[tuple[str, str], DatabaseRow] = {
                (str(q.get("table_name", "")), str(q.get("field_name", ""))): q for q in query_stats
            }

            analysis: JSONDict = {
                "indexes_created": len(indexes),
                "index_details": [],
                "high_query_fields_without_index": [],
                "low_query_fields_with_index": [],
            }

            # Analyze each index
            for idx in indexes:
                table = idx["table_name"]
                field = idx["field_name"]
                key = (table, field)

                query_info = query_map.get(key, {})
                details = (
                    json.loads(idx["details_json"])
                    if isinstance(idx["details_json"], str)
                    else idx["details_json"]
                )

                index_detail = {
                    "table": table,
                    "field": field,
                    "queries_analyzed": details.get("queries_analyzed", 0),
                    "build_cost": details.get("build_cost_estimate", 0),
                    "current_queries": query_info.get("total_queries", 0),
                    "avg_duration_ms": query_info.get("avg_duration_ms", 0),
                    "p95_duration_ms": query_info.get("p95_duration_ms", 0),
                    "p99_duration_ms": query_info.get("p99_duration_ms", 0),
                }
                analysis["index_details"].append(index_detail)  # type: ignore[union-attr]

            # Find fields with high query volume but no index
            for q in query_stats:
                table_name = str(q.get("table_name", ""))
                field_name = str(q.get("field_name", ""))
                key = (table_name, field_name)
                total_queries_val = q.get("total_queries", 0)
                total_queries = (
                    total_queries_val if isinstance(total_queries_val, int | float) else 0
                )
                if key not in index_map and total_queries > 1000:
                    high_query_field: JSONDict = {
                        "table": table_name,
                        "field": field_name,
                        "queries": total_queries,
                        "avg_duration_ms": q.get("avg_duration_ms", 0)
                        if isinstance(q.get("avg_duration_ms"), int | float)
                        else 0,
                        "p95_duration_ms": q.get("p95_duration_ms", 0)
                        if isinstance(q.get("p95_duration_ms"), int | float)
                        else 0,
                    }
                    analysis["high_query_fields_without_index"].append(high_query_field)  # type: ignore[union-attr]

            # Find indexes on low-query fields (potential over-indexing)
            for idx in indexes:
                table_name = str(idx.get("table_name", ""))
                field_name = str(idx.get("field_name", ""))
                key = (table_name, field_name)
                query_info_raw = query_map.get(key, {})
                query_info_low: DatabaseRow = (
                    query_info_raw if isinstance(query_info_raw, dict) else {}
                )
                total_queries_val = query_info_low.get("total_queries", 0)
                total_queries = (
                    total_queries_val if isinstance(total_queries_val, int | float) else 0
                )
                if total_queries < 100:
                    details_json_val = idx.get("details_json")
                    if isinstance(details_json_val, str):
                        loaded_details: object = json.loads(details_json_val)
                        details_low = loaded_details if isinstance(loaded_details, dict) else {}
                    elif isinstance(details_json_val, dict):
                        details_low = details_json_val
                    else:
                        details_low = {}
                    details_low_typed: JSONDict = details_low
                    low_query_field: JSONDict = {
                        "table": table_name,
                        "field": field_name,
                        "queries": total_queries,
                        "queries_at_creation": details_low_typed.get("queries_analyzed", 0)
                        if isinstance(details_low_typed.get("queries_analyzed"), int | float)
                        else 0,
                    }
                    analysis["low_query_fields_with_index"].append(low_query_field)  # type: ignore[union-attr]

            return analysis
        finally:
            cursor.close()


def compare_performance():
    """Compare baseline vs auto-index performance metrics"""
    baseline = load_results("results_baseline.json")
    autoindex = load_results("results_with_auto_index.json")

    if not baseline or not autoindex:
        return None

    # Type narrowing for JSONValue to JSONDict
    if not isinstance(baseline, dict) or not isinstance(autoindex, dict):
        return None

    baseline_dict: JSONDict = baseline
    autoindex_dict: JSONDict = autoindex

    comparison: JSONDict = {
        "baseline": {
            "avg_ms": baseline_dict.get("overall_avg_ms", 0)
            if isinstance(baseline_dict.get("overall_avg_ms"), int | float)
            else 0,
            "p95_ms": baseline_dict.get("overall_p95_ms", 0)
            if isinstance(baseline_dict.get("overall_p95_ms"), int | float)
            else 0,
            "p99_ms": baseline_dict.get("overall_p99_ms", 0)
            if isinstance(baseline_dict.get("overall_p99_ms"), int | float)
            else 0,
            "total_queries": baseline_dict.get("total_queries", 0)
            if isinstance(baseline_dict.get("total_queries"), int | float)
            else 0,
        },
        "autoindex": {
            "avg_ms": autoindex_dict.get("overall_avg_ms", 0)
            if isinstance(autoindex_dict.get("overall_avg_ms"), int | float)
            else 0,
            "p95_ms": autoindex_dict.get("overall_p95_ms", 0)
            if isinstance(autoindex_dict.get("overall_p95_ms"), int | float)
            else 0,
            "p99_ms": autoindex_dict.get("overall_p99_ms", 0)
            if isinstance(autoindex_dict.get("overall_p99_ms"), int | float)
            else 0,
            "total_queries": autoindex_dict.get("total_queries", 0)
            if isinstance(autoindex_dict.get("total_queries"), int | float)
            else 0,
        },
    }

    # Calculate improvements
    baseline_val = comparison.get("baseline", {})
    autoindex_val = comparison.get("autoindex", {})
    baseline_dict_inner: JSONDict = baseline_val if isinstance(baseline_val, dict) else {}
    autoindex_dict_inner: JSONDict = autoindex_val if isinstance(autoindex_val, dict) else {}

    baseline_avg_ms_val = baseline_dict_inner.get("avg_ms", 0)
    baseline_avg_ms = baseline_avg_ms_val if isinstance(baseline_avg_ms_val, int | float) else 0
    baseline_p95_ms_val = baseline_dict_inner.get("p95_ms", 0)
    baseline_p95_ms = baseline_p95_ms_val if isinstance(baseline_p95_ms_val, int | float) else 0
    baseline_p99_ms_val = baseline_dict_inner.get("p99_ms", 0)
    baseline_p99_ms = baseline_p99_ms_val if isinstance(baseline_p99_ms_val, int | float) else 0
    autoindex_avg_ms_val = autoindex_dict_inner.get("avg_ms", 0)
    autoindex_avg_ms = autoindex_avg_ms_val if isinstance(autoindex_avg_ms_val, int | float) else 0
    autoindex_p95_ms_val = autoindex_dict_inner.get("p95_ms", 0)
    autoindex_p95_ms = autoindex_p95_ms_val if isinstance(autoindex_p95_ms_val, int | float) else 0
    autoindex_p99_ms_val = autoindex_dict_inner.get("p99_ms", 0)
    autoindex_p99_ms = autoindex_p99_ms_val if isinstance(autoindex_p99_ms_val, int | float) else 0

    if isinstance(baseline_avg_ms, int | float) and baseline_avg_ms > 0:
        comparison["improvements"] = {
            "avg_improvement_pct": ((baseline_avg_ms - autoindex_avg_ms) / baseline_avg_ms) * 100,
            "p95_improvement_pct": ((baseline_p95_ms - autoindex_p95_ms) / baseline_p95_ms) * 100,
            "p99_improvement_pct": ((baseline_p99_ms - autoindex_p99_ms) / baseline_p99_ms) * 100,
            "avg_improvement_ms": baseline_avg_ms - autoindex_avg_ms,
            "p95_improvement_ms": baseline_p95_ms - autoindex_p95_ms,
            "p99_improvement_ms": baseline_p99_ms - autoindex_p99_ms,
        }

        # Detect regression
        improvements_val = comparison.get("improvements", {})
        if isinstance(improvements_val, dict):
            improvements: JSONDict = improvements_val
            avg_imp_pct_val = improvements.get("avg_improvement_pct", 0)
            avg_imp_pct = avg_imp_pct_val if isinstance(avg_imp_pct_val, int | float) else 0
            p95_imp_pct_val = improvements.get("p95_improvement_pct", 0)
            p95_imp_pct = p95_imp_pct_val if isinstance(p95_imp_pct_val, int | float) else 0
            p99_imp_pct_val = improvements.get("p99_improvement_pct", 0)
            p99_imp_pct = p99_imp_pct_val if isinstance(p99_imp_pct_val, int | float) else 0
            comparison["regression_detected"] = (
                (isinstance(avg_imp_pct, int | float) and avg_imp_pct < -5)
                or (isinstance(p95_imp_pct, int | float) and p95_imp_pct < -5)
                or (isinstance(p99_imp_pct, int | float) and p99_imp_pct < -5)
            )
        else:
            comparison["regression_detected"] = False
    else:
        comparison["improvements"] = None
        comparison["regression_detected"] = False

    return comparison


def get_mutation_summary() -> JSONDict:
    """Get summary of mutations (index creations)"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Count mutations by type
            cursor.execute(
                """
                SELECT
                    mutation_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT table_name) as tables_affected,
                    COUNT(DISTINCT field_name) as fields_affected
                FROM mutation_log
                GROUP BY mutation_type
                ORDER BY count DESC
            """
            )
            mutation_summary: list[DatabaseRow] = cursor.fetchall()

            # Get index creation details
            cursor.execute(
                """
                SELECT
                    table_name,
                    field_name,
                    details_json,
                    created_at
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                ORDER BY created_at DESC
            """
            )
            index_creations: list[DatabaseRow] = cursor.fetchall()

            return {
                "summary": mutation_summary,  # type: ignore[dict-item]
                "indexes": index_creations,  # type: ignore[dict-item]
            }
        finally:
            cursor.close()


def generate_report():
    """Generate comprehensive report (basic version)"""
    if not is_reporting_enabled():
        print("Reporting is disabled via operational.reporting.enabled in config.")
        return

    print("=" * 80)
    print("INDEXPILOT - PERFORMANCE REPORT")
    print("=" * 80)

    # Load results
    baseline_results = load_results("results_baseline.json")
    autoindex_results = load_results("results_with_auto_index.json")

    if baseline_results and isinstance(baseline_results, dict):
        baseline_dict_print: JSONDict = baseline_results
        print("\nBaseline Simulation:")
        print(f"  Tenants: {baseline_dict_print.get('num_tenants', 'N/A')}")
        print(f"  Queries per tenant: {baseline_dict_print.get('queries_per_tenant', 'N/A')}")
        print(f"  Timestamp: {baseline_dict_print.get('timestamp', 'N/A')}")

    if autoindex_results and isinstance(autoindex_results, dict):
        autoindex_dict_print: JSONDict = autoindex_results
        print("\nAuto-Index Simulation:")
        print(f"  Tenants: {autoindex_dict_print.get('num_tenants', 'N/A')}")
        print(f"  Queries per tenant: {autoindex_dict_print.get('queries_per_tenant', 'N/A')}")
        print(f"  Indexes created: {autoindex_dict_print.get('indexes_created', 'N/A')}")
        print(f"  Timestamp: {autoindex_dict_print.get('timestamp', 'N/A')}")

    # Mutation summary
    print("\n" + "=" * 80)
    print("MUTATION SUMMARY")
    print("=" * 80)
    mutation_data = get_mutation_summary()

    summary_val = mutation_data.get("summary", [])
    if summary_val and isinstance(summary_val, list):
        print("\nMutations by type:")
        for mut_raw in summary_val:
            mut: DatabaseRow = mut_raw if isinstance(mut_raw, dict) else {}  # type: ignore[assignment]
            mutation_type = str(mut.get("mutation_type", "unknown"))
            count = mut.get("count", 0) if isinstance(mut.get("count"), int | float) else 0
            tables_affected = (
                mut.get("tables_affected", 0)
                if isinstance(mut.get("tables_affected"), int | float)
                else 0
            )
            fields_affected = (
                mut.get("fields_affected", 0)
                if isinstance(mut.get("fields_affected"), int | float)
                else 0
            )
            print(
                f"  {mutation_type}: {count} mutations "
                f"({tables_affected} tables, {fields_affected} fields)"
            )

    indexes_val = mutation_data.get("indexes", [])
    if indexes_val and isinstance(indexes_val, list):
        print(f"\nIndexes Created ({len(indexes_val)}):")
        for idx_raw in indexes_val:
            idx: dict[str, JSONValue] = idx_raw if isinstance(idx_raw, dict) else {}
            details_json_val = idx.get("details_json")
            details: JSONDict = {}
            if details_json_val:
                if isinstance(details_json_val, str):
                    try:
                        details_raw = json.loads(details_json_val)
                        if isinstance(details_raw, dict):
                            details = details_raw
                    except (json.JSONDecodeError, TypeError):
                        details = {}
                elif isinstance(details_json_val, dict):
                    details = details_json_val
            table_name_print = str(idx.get("table_name", ""))
            field_name_print = str(idx.get("field_name", ""))
            print(f"  - {table_name_print}.{field_name_print}")
            if details:
                queries_analyzed = details.get("queries_analyzed", "N/A")
                build_cost = details.get("build_cost_estimate", "N/A")
                build_cost_float = build_cost if isinstance(build_cost, int | float) else 0
                print(f"    Queries analyzed: {queries_analyzed}")
                print(f"    Build cost estimate: {build_cost_float:.2f}")

    # Query performance stats
    print("\n" + "=" * 80)
    print("QUERY PERFORMANCE STATISTICS")
    print("=" * 80)

    # Get field usage stats
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                """
                SELECT
                    table_name,
                    field_name,
                    COUNT(*) as total_queries,
                    AVG(duration_ms) as avg_duration_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_duration_ms
                FROM query_stats
                WHERE field_name IS NOT NULL
                GROUP BY table_name, field_name
                ORDER BY total_queries DESC
                LIMIT 20
            """
            )
            top_queries = cursor.fetchall()

            if top_queries:
                print("\nTop 20 Query Patterns (by volume):")
                print(
                    f"{'Table':<20} {'Field':<20} {'Queries':<10} {'Avg (ms)':<12} {'P95 (ms)':<12} {'P99 (ms)':<12}"
                )
                print("-" * 80)
                for q in top_queries:
                    print(
                        f"{q['table_name']:<20} {q['field_name']:<20} {q['total_queries']:<10} "
                        f"{q['avg_duration_ms']:<12.2f} {q['p95_duration_ms']:<12.2f} {q['p99_duration_ms']:<12.2f}"
                    )
        finally:
            cursor.close()

    # Evaluation
    print("\n" + "=" * 80)
    print("EVALUATION")
    print("=" * 80)

    if autoindex_results and isinstance(autoindex_results, dict):
        indexes_created = autoindex_results.get("indexes_created", 0)
        if isinstance(indexes_created, int | float) and indexes_created > 0:
            print("\n[OK] Auto-indexing successfully created indexes based on query patterns")
            print("[OK] Mutation log provides lineage of all schema changes")
            print("\nNote: For a complete performance comparison, you would need to:")
            print("  1. Run baseline and auto-index simulations separately")
            print("  2. Compare query latencies before and after index creation")
            print("  3. Measure the impact on specific query patterns")
        else:
            print("\nWARNING: No indexes were created. This could indicate:")
            print("  - Query volume was below threshold")
            print("  - Cost-benefit analysis did not favor index creation")
            print("  - Indexes already exist for heavily-used fields")
    else:
        print("\nWARNING: No indexes were created. This could indicate:")
        print("  - Query volume was below threshold")
        print("  - Cost-benefit analysis did not favor index creation")
        print("  - Indexes already exist for heavily-used fields")

    print("\n" + "=" * 80)


def generate_scaled_report():
    """Generate comprehensive report for scaled simulation"""
    if not is_reporting_enabled():
        print("Reporting is disabled via operational.reporting.enabled in config.")
        return

    print("=" * 80)
    print("SCALED SIMULATION ANALYSIS REPORT")
    print("=" * 80)

    # Load results
    baseline = load_results("results_baseline.json")
    autoindex = load_results("results_with_auto_index.json")

    if baseline and isinstance(baseline, dict):
        baseline_dict: JSONDict = baseline
        num_tenants = baseline_dict.get("num_tenants", "N/A")
        queries_per_tenant = baseline_dict.get("queries_per_tenant", "N/A")
        total_queries = baseline_dict.get("total_queries", "N/A")
        contacts_per_tenant = baseline_dict.get("contacts_per_tenant", "N/A")
        overall_avg_ms = baseline_dict.get("overall_avg_ms", "N/A")
        overall_p95_ms = baseline_dict.get("overall_p95_ms", "N/A")
        overall_p99_ms = baseline_dict.get("overall_p99_ms", "N/A")

        print("\nBASELINE SIMULATION:")
        print(f"  Tenants: {num_tenants}")
        if isinstance(queries_per_tenant, int | float):
            print(f"  Queries per tenant: {queries_per_tenant:,}")
        else:
            print(f"  Queries per tenant: {queries_per_tenant}")
        if isinstance(total_queries, int | float):
            print(f"  Total queries: {total_queries:,}")
        else:
            print(f"  Total queries: {total_queries}")
        if isinstance(contacts_per_tenant, int | float):
            print(f"  Contacts per tenant: {contacts_per_tenant:,}")
        else:
            print(f"  Contacts per tenant: {contacts_per_tenant}")
        if isinstance(overall_avg_ms, int | float):
            print(f"  Average latency: {overall_avg_ms:.2f}ms")
        else:
            print(f"  Average latency: {overall_avg_ms}")
        if isinstance(overall_p95_ms, int | float):
            print(f"  P95 latency: {overall_p95_ms:.2f}ms")
        else:
            print(f"  P95 latency: {overall_p95_ms}")
        if isinstance(overall_p99_ms, int | float):
            print(f"  P99 latency: {overall_p99_ms:.2f}ms")
        else:
            print(f"  P99 latency: {overall_p99_ms}")

    if autoindex and isinstance(autoindex, dict):
        autoindex_dict: JSONDict = autoindex
        num_tenants = autoindex_dict.get("num_tenants", "N/A")
        queries_per_tenant = autoindex_dict.get("queries_per_tenant", "N/A")
        total_queries = autoindex_dict.get("total_queries", "N/A")
        contacts_per_tenant = autoindex_dict.get("contacts_per_tenant", "N/A")
        indexes_created = autoindex_dict.get("indexes_created", "N/A")
        overall_avg_ms = autoindex_dict.get("overall_avg_ms", "N/A")
        overall_p95_ms = autoindex_dict.get("overall_p95_ms", "N/A")
        overall_p99_ms = autoindex_dict.get("overall_p99_ms", "N/A")

        print("\nAUTO-INDEX SIMULATION:")
        print(f"  Tenants: {num_tenants}")
        if isinstance(queries_per_tenant, int | float):
            print(f"  Queries per tenant: {queries_per_tenant:,}")
        else:
            print(f"  Queries per tenant: {queries_per_tenant}")
        if isinstance(total_queries, int | float):
            print(f"  Total queries: {total_queries:,}")
        else:
            print(f"  Total queries: {total_queries}")
        if isinstance(contacts_per_tenant, int | float):
            print(f"  Contacts per tenant: {contacts_per_tenant:,}")
        else:
            print(f"  Contacts per tenant: {contacts_per_tenant}")
        print(f"  Indexes created: {indexes_created}")
        if isinstance(overall_avg_ms, int | float):
            print(f"  Average latency: {overall_avg_ms:.2f}ms")
        else:
            print(f"  Average latency: {overall_avg_ms}")
        if isinstance(overall_p95_ms, int | float):
            print(f"  P95 latency: {overall_p95_ms:.2f}ms")
        else:
            print(f"  P95 latency: {overall_p95_ms}")
        if isinstance(overall_p99_ms, int | float):
            print(f"  P99 latency: {overall_p99_ms:.2f}ms")
        else:
            print(f"  P99 latency: {overall_p99_ms}")

    # Performance comparison
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)

    comparison = compare_performance()
    if comparison and isinstance(comparison, dict):
        improvements_val = comparison.get("improvements")
        if improvements_val and isinstance(improvements_val, dict):
            imp: dict[str, JSONValue] = improvements_val
            baseline_val = comparison.get("baseline")
            autoindex_val = comparison.get("autoindex")

            if isinstance(baseline_val, dict) and isinstance(autoindex_val, dict):
                baseline_avg = baseline_val.get("avg_ms", 0)
                baseline_avg_float = (
                    float(baseline_avg) if isinstance(baseline_avg, int | float) else 0.0
                )
                autoindex_avg = autoindex_val.get("avg_ms", 0)
                autoindex_avg_float = (
                    float(autoindex_avg) if isinstance(autoindex_avg, int | float) else 0.0
                )
                imp_avg_ms = imp.get("avg_improvement_ms", 0)
                imp_avg_ms_float = float(imp_avg_ms) if isinstance(imp_avg_ms, int | float) else 0.0
                imp_avg_pct = imp.get("avg_improvement_pct", 0)
                imp_avg_pct_float = (
                    float(imp_avg_pct) if isinstance(imp_avg_pct, int | float) else 0.0
                )

                print("\nAverage Latency:")
                print(f"  Baseline: {baseline_avg_float:.2f}ms")
                print(f"  Auto-Index: {autoindex_avg_float:.2f}ms")
                print(f"  Improvement: {imp_avg_ms_float:.2f}ms ({imp_avg_pct_float:+.2f}%)")

                baseline_p95 = baseline_val.get("p95_ms", 0)
                baseline_p95_float = (
                    float(baseline_p95) if isinstance(baseline_p95, int | float) else 0.0
                )
                autoindex_p95 = autoindex_val.get("p95_ms", 0)
                autoindex_p95_float = (
                    float(autoindex_p95) if isinstance(autoindex_p95, int | float) else 0.0
                )
                imp_p95_ms = imp.get("p95_improvement_ms", 0)
                imp_p95_ms_float = float(imp_p95_ms) if isinstance(imp_p95_ms, int | float) else 0.0
                imp_p95_pct = imp.get("p95_improvement_pct", 0)
                imp_p95_pct_float = (
                    float(imp_p95_pct) if isinstance(imp_p95_pct, int | float) else 0.0
                )

                print("\nP95 Latency:")
                print(f"  Baseline: {baseline_p95_float:.2f}ms")
                print(f"  Auto-Index: {autoindex_p95_float:.2f}ms")
                print(f"  Improvement: {imp_p95_ms_float:.2f}ms ({imp_p95_pct_float:+.2f}%)")

                baseline_p99 = baseline_val.get("p99_ms", 0)
                baseline_p99_float = (
                    float(baseline_p99) if isinstance(baseline_p99, int | float) else 0.0
                )
                autoindex_p99 = autoindex_val.get("p99_ms", 0)
                autoindex_p99_float = (
                    float(autoindex_p99) if isinstance(autoindex_p99, int | float) else 0.0
                )
                imp_p99_ms = imp.get("p99_improvement_ms", 0)
                imp_p99_ms_float = float(imp_p99_ms) if isinstance(imp_p99_ms, int | float) else 0.0
                imp_p99_pct = imp.get("p99_improvement_pct", 0)
                imp_p99_pct_float = (
                    float(imp_p99_pct) if isinstance(imp_p99_pct, int | float) else 0.0
                )

                print("\nP99 Latency:")
                print(f"  Baseline: {baseline_p99_float:.2f}ms")
                print(f"  Auto-Index: {autoindex_p99_float:.2f}ms")
                print(f"  Improvement: {imp_p99_ms_float:.2f}ms ({imp_p99_pct_float:+.2f}%)")

                # Highlight if improvements are significant
                if imp_p95_pct_float > 10 or imp_p99_pct_float > 10:
                    print("\n[OK] SIGNIFICANT IMPROVEMENTS detected in P95/P99 percentiles!")
                elif imp_p95_pct_float > 0 or imp_p99_pct_float > 0:
                    print("\n[OK] Modest improvements detected in P95/P99 percentiles")
                else:
                    print("\n[WARN] No significant improvements in P95/P99 percentiles")

                # Check for regression
                regression_val = comparison.get("regression_detected", False)
                regression_detected = (
                    bool(regression_val) if isinstance(regression_val, bool) else False
                )
                if regression_detected:
                    print("\n[WARN] REGRESSION DETECTED: Performance degraded after indexing!")
                else:
                    print("\n[OK] No regression detected")
    else:
        print("\n[WARN] Cannot compare - missing baseline or auto-index results")

    # Index analysis
    print("\n" + "=" * 80)
    print("INDEX ANALYSIS")
    print("=" * 80)

    index_analysis = get_index_analysis()
    if index_analysis and isinstance(index_analysis, dict):
        indexes_created_val = index_analysis.get("indexes_created", 0)
        indexes_created = (
            int(indexes_created_val) if isinstance(indexes_created_val, int | float) else 0
        )
        print(f"\nTotal indexes created: {indexes_created}")

        # Expected indexes (based on query patterns)
        expected_indexes = [
            "contacts.email",
            "contacts.phone",
            "organizations.industry",
            "interactions.type",
            "contacts.custom_text_1",
        ]
        index_details_val = index_analysis.get("index_details", [])
        if isinstance(index_details_val, list):
            created_index_keys = [
                (str(idx.get("table", "")), str(idx.get("field", "")))
                for idx in index_details_val
                if isinstance(idx, dict)
            ]
        else:
            created_index_keys = []
        # Ensure each expected index has table.field format (2 elements after split)
        expected_keys = []
        for k in expected_indexes:
            parts = k.split(".")
            if len(parts) >= 2:
                expected_keys.append((parts[0], parts[1]))
            else:
                # Skip malformed entries (shouldn't happen, but handle gracefully)
                logger.warning(
                    f"Skipping malformed expected_index entry: {k} (expected 'table.field' format)"
                )

        print("\nIndex Selection Validation:")
        matches = [k for k in expected_keys if k in created_index_keys]
        print(f"  Expected indexes found: {len(matches)}/{len(expected_keys)}")

        if len(matches) == len(expected_keys):
            print("  [OK] All expected indexes were created")
        elif len(matches) >= len(expected_keys) * 0.8:
            print("  [OK] Most expected indexes were created")
        else:
            print("  [WARN] Some expected indexes were not created")

        print("\nCreated Indexes:")
        if isinstance(index_details_val, list):
            for idx in index_details_val:
                if isinstance(idx, dict):
                    table = str(idx.get("table", ""))
                    field = str(idx.get("field", ""))
                    queries_analyzed = idx.get("queries_analyzed", 0)
                    queries_analyzed_int = (
                        int(queries_analyzed) if isinstance(queries_analyzed, int | float) else 0
                    )
                    current_queries = idx.get("current_queries", 0)
                    current_queries_int = (
                        int(current_queries) if isinstance(current_queries, int | float) else 0
                    )
                    avg_duration = idx.get("avg_duration_ms", 0)
                    avg_duration_float = (
                        float(avg_duration) if isinstance(avg_duration, int | float) else 0.0
                    )
                    p95_duration = idx.get("p95_duration_ms", 0)
                    p95_duration_float = (
                        float(p95_duration) if isinstance(p95_duration, int | float) else 0.0
                    )
                    p99_duration = idx.get("p99_duration_ms", 0)
                    p99_duration_float = (
                        float(p99_duration) if isinstance(p99_duration, int | float) else 0.0
                    )
                    print(f"  - {table}.{field}")
                    print(f"    Queries at creation: {queries_analyzed_int:,}")
                    print(f"    Current queries: {current_queries_int:,}")
                    print(f"    Avg duration: {avg_duration_float:.2f}ms")
                    print(f"    P95 duration: {p95_duration_float:.2f}ms")
                    print(f"    P99 duration: {p99_duration_float:.2f}ms")

        # Over-indexing detection
        low_query_fields_val = index_analysis.get("low_query_fields_with_index", [])
        if low_query_fields_val and isinstance(low_query_fields_val, list):
            print("\n[WARN] OVER-INDEXING DETECTED:")
            print(f"  Found {len(low_query_fields_val)} indexes on low-query fields:")
            for idx in low_query_fields_val:
                if isinstance(idx, dict):
                    table = str(idx.get("table", ""))
                    field = str(idx.get("field", ""))
                    queries = idx.get("queries", 0)
                    queries_int = int(queries) if isinstance(queries, int | float) else 0
                    queries_at_creation = idx.get("queries_at_creation", 0)
                    queries_at_creation_int = (
                        int(queries_at_creation)
                        if isinstance(queries_at_creation, int | float)
                        else 0
                    )
                    print(
                        f"    - {table}.{field} ({queries_int} queries, created at {queries_at_creation_int} queries)"
                    )
        else:
            print("\n[OK] No over-indexing detected - all indexes are on high-query fields")

        # High-query fields without indexes
        high_query_fields_val = index_analysis.get("high_query_fields_without_index", [])
        if high_query_fields_val and isinstance(high_query_fields_val, list):
            print("\n[WARN] HIGH-QUERY FIELDS WITHOUT INDEXES:")
            print(f"  Found {len(high_query_fields_val)} high-query fields without indexes:")
            for field_item in high_query_fields_val[:10]:  # Top 10
                if not isinstance(field_item, dict):
                    continue
                field_dict = field_item
                table_val = field_dict.get("table", "")
                table = str(table_val) if table_val is not None else ""
                field_val = field_dict.get("field", "")
                field_name = str(field_val) if field_val is not None else ""
                queries = field_dict.get("queries", 0)
                queries_int = int(queries) if isinstance(queries, int | float) else 0
                avg_duration = field_dict.get("avg_duration_ms", 0)
                avg_duration_float = (
                    float(avg_duration) if isinstance(avg_duration, int | float) else 0.0
                )
                p95_duration = field_dict.get("p95_duration_ms", 0)
                p95_duration_float = (
                    float(p95_duration) if isinstance(p95_duration, int | float) else 0.0
                )
                print(
                    f"    - {table}.{field_name} ({queries_int:,} queries, avg: {avg_duration_float:.2f}ms, P95: {p95_duration_float:.2f}ms)"
                )
        else:
            print("\n[OK] All high-query fields have indexes")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if comparison and isinstance(comparison, dict):
        improvements_val = comparison.get("improvements")
        if improvements_val and isinstance(improvements_val, dict):
            imp_summary: dict[str, JSONValue] = improvements_val
            imp_p95_pct = imp_summary.get("p95_improvement_pct", 0)
            imp_p95_pct_float = float(imp_p95_pct) if isinstance(imp_p95_pct, int | float) else 0.0
            imp_p99_pct = imp_summary.get("p99_improvement_pct", 0)
            imp_p99_pct_float = float(imp_p99_pct) if isinstance(imp_p99_pct, int | float) else 0.0
            if imp_p95_pct_float > 10 or imp_p99_pct_float > 10:
                print("[OK] P95/P99 improvements are OBVIOUS and significant")
            elif imp_p95_pct_float > 0 or imp_p99_pct_float > 0:
                print("[OK] P95/P99 improvements are visible but modest")
            else:
                print("[WARN] P95/P99 improvements are not obvious at this scale")

    if index_analysis and isinstance(index_analysis, dict):
        index_details_val = index_analysis.get("index_details", [])
        if isinstance(index_details_val, list):
            created_index_keys = [
                (str(idx.get("table", "")), str(idx.get("field", "")))
                for idx in index_details_val
                if isinstance(idx, dict)
            ]
        else:
            created_index_keys = []
        expected_indexes = [
            "contacts.email",
            "contacts.phone",
            "organizations.industry",
            "interactions.type",
            "contacts.custom_text_1",
        ]
        # Ensure each expected index has table.field format (2 elements after split)
        expected_keys = []
        for k in expected_indexes:
            parts = k.split(".")
            if len(parts) >= 2:
                expected_keys.append((parts[0], parts[1]))
            else:
                # Skip malformed entries (shouldn't happen, but handle gracefully)
                logger.warning(
                    f"Skipping malformed expected_index entry: {k} (expected 'table.field' format)"
                )
        matches = [k for k in expected_keys if k in created_index_keys]
        if len(matches) >= len(expected_keys) * 0.8:
            print("[OK] Indexes created match intuition (expected fields indexed)")
        else:
            print("[WARN] Some expected indexes were not created")

        if index_analysis["low_query_fields_with_index"]:
            print("[WARN] Over-indexing detected - some indexes may be unnecessary")
        else:
            print("[OK] No over-indexing - index selection is appropriate")

    if comparison and comparison["regression_detected"]:
        print("[WARN] REGRESSION detected - performance degraded after indexing")
    elif comparison:
        print("[OK] No regression detected")

    print("\n" + "=" * 80)

    # Save detailed report
    from datetime import datetime

    report_data = {
        "comparison": comparison,
        "index_analysis": index_analysis,
        "timestamp": datetime.now().isoformat(),
    }

    report_path = get_report_path("scaled_analysis_report.json")
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2, default=str)

    print(f"\nDetailed analysis saved to {report_path}")


if __name__ == "__main__":
    generate_scaled_report()
