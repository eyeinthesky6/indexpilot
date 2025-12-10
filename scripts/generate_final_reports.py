"""Generate final reports for large and small database performance tests"""

import json
import os

from src.db import get_cursor
from src.paths import get_report_path


def get_database_size_info():
    """Get comprehensive database size information"""
    with get_cursor() as cursor:
        # Database size
        cursor.execute(
            """
            SELECT
                pg_size_pretty(pg_database_size(current_database())) as db_size,
                pg_database_size(current_database()) as db_size_bytes
        """
        )
        db_info = cursor.fetchone()

        # Table sizes
        cursor.execute(
            """
            SELECT
                tablename,
                pg_size_pretty(pg_total_relation_size('public.'||tablename)) as size,
                pg_total_relation_size('public.'||tablename) as size_bytes,
                pg_size_pretty(pg_relation_size('public.'||tablename)) as table_size,
                pg_relation_size('public.'||tablename) as table_size_bytes
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size('public.'||tablename) DESC
        """
        )
        tables = cursor.fetchall()

        # Index sizes
        cursor.execute(
            """
            SELECT
                indexname,
                tablename,
                pg_size_pretty(pg_relation_size(indexname::regclass)) as size,
                pg_relation_size(indexname::regclass) as size_bytes
            FROM pg_indexes
            WHERE schemaname = 'public' AND indexname LIKE 'idx_%'
            ORDER BY pg_relation_size(indexname::regclass) DESC
        """
        )
        indexes = cursor.fetchall()

        # Row counts
        cursor.execute("SELECT COUNT(*) as count FROM contacts")
        contacts_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM organizations")
        orgs_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM interactions")
        interactions_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM query_stats")
        stats_count = cursor.fetchone()["count"]

        # Total index size
        total_index_bytes = sum(idx["size_bytes"] for idx in indexes)
        total_table_bytes = sum(t["table_size_bytes"] for t in tables)
        index_overhead_pct = (
            (total_index_bytes / total_table_bytes * 100) if total_table_bytes > 0 else 0
        )

        return {
            "database": {"size": db_info["db_size"], "size_bytes": db_info["db_size_bytes"]},
            "tables": [
                {
                    "name": t["tablename"],
                    "total_size": t["size"],
                    "total_size_bytes": t["size_bytes"],
                    "table_size": t["table_size"],
                    "table_size_bytes": t["table_size_bytes"],
                }
                for t in tables
            ],
            "indexes": [
                {
                    "name": idx["indexname"],
                    "table": idx["tablename"],
                    "size": idx["size"],
                    "size_bytes": idx["size_bytes"],
                }
                for idx in indexes
            ],
            "row_counts": {
                "contacts": contacts_count,
                "organizations": orgs_count,
                "interactions": interactions_count,
                "query_stats": stats_count,
            },
            "summary": {
                "total_index_size_bytes": total_index_bytes,
                "total_table_size_bytes": total_table_bytes,
                "index_overhead_percent": round(index_overhead_pct, 2),
                "total_indexes": len(indexes),
            },
        }


def generate_report(experiment_name, baseline_file, autoindex_file, output_file):
    """Generate a final report"""

    # Load results
    baseline = {}
    autoindex = {}

    baseline_path = get_report_path(baseline_file)
    autoindex_path = get_report_path(autoindex_file)

    if os.path.exists(baseline_path):
        with open(baseline_path) as f:
            baseline = json.load(f)

    if os.path.exists(autoindex_path):
        with open(autoindex_path) as f:
            autoindex = json.load(f)

    # Get database size info
    size_info = get_database_size_info()

    # Calculate improvements - handle both 'overall_stats' and direct keys
    baseline_avg = (
        baseline.get("overall_stats", {}).get("avg_ms", 0) or baseline.get("overall_avg_ms", 0) or 0
    )
    baseline_p95 = (
        baseline.get("overall_stats", {}).get("p95_ms", 0) or baseline.get("overall_p95_ms", 0) or 0
    )
    baseline_p99 = (
        baseline.get("overall_stats", {}).get("p99_ms", 0) or baseline.get("overall_p99_ms", 0) or 0
    )

    autoindex_avg = (
        autoindex.get("overall_stats", {}).get("avg_ms", 0)
        or autoindex.get("overall_avg_ms", 0)
        or 0
    )
    autoindex_p95 = (
        autoindex.get("overall_stats", {}).get("p95_ms", 0)
        or autoindex.get("overall_p95_ms", 0)
        or 0
    )
    autoindex_p99 = (
        autoindex.get("overall_stats", {}).get("p99_ms", 0)
        or autoindex.get("overall_p99_ms", 0)
        or 0
    )

    improvement_pct = (
        ((baseline_avg - autoindex_avg) / baseline_avg * 100) if baseline_avg > 0 else 0
    )
    improvement_p95 = (
        ((baseline_p95 - autoindex_p95) / baseline_p95 * 100) if baseline_p95 > 0 else 0
    )
    improvement_p99 = (
        ((baseline_p99 - autoindex_p99) / baseline_p99 * 100) if baseline_p99 > 0 else 0
    )

    # Helper to format numbers safely
    def fmt_num(value, default="N/A", decimals=2):
        if value == "N/A" or value is None:
            return default
        try:
            return f"{float(value):.{decimals}f}"
        except (ValueError, TypeError):
            return default

    # Generate report
    report = f"""# IndexPilot - Final Report ({experiment_name})

## Test Configuration

- **Database Size**: {experiment_name}
- **Tenants**: {baseline.get("num_tenants", "N/A")}
- **Queries per tenant**: {baseline.get("queries_per_tenant", "N/A")}
- **Data Scale**:
  - {baseline.get("contacts_per_tenant", "N/A")} contacts per tenant
  - {baseline.get("orgs_per_tenant", "N/A")} organizations per tenant
  - {baseline.get("interactions_per_tenant", "N/A")} interactions per tenant
- **Total Data**:
  - {size_info["row_counts"]["contacts"]:,} contacts
  - {size_info["row_counts"]["organizations"]:,} organizations
  - {size_info["row_counts"]["interactions"]:,} interactions
  - {size_info["row_counts"]["query_stats"]:,} query stats records

## Performance Results

### Baseline Performance
- **Total queries**: {baseline.get("total_queries", "N/A")}
- **Average latency**: {fmt_num(baseline_avg, "N/A")}ms
- **P95 latency**: {fmt_num(baseline_p95, "N/A")}ms
- **P99 latency**: {fmt_num(baseline_p99, "N/A")}ms

### Auto-Index Performance
- **Total queries**: {autoindex.get("total_queries", "N/A")}
- **Indexes created**: {autoindex.get("indexes_created", 0)}
- **Average latency**: {fmt_num(autoindex_avg, "N/A")}ms
- **P95 latency**: {fmt_num(autoindex_p95, "N/A")}ms
- **P99 latency**: {fmt_num(autoindex_p99, "N/A")}ms
- **Performance improvement**: {improvement_pct:.1f}% (avg), {improvement_p95:.1f}% (P95), {improvement_p99:.1f}% (P99)

## Database Size Analysis

### Table Sizes
"""

    for table in size_info["tables"]:
        report += f"- **{table['name']}**: {table['total_size']} (table: {table['table_size']})\n"

    report += f"""
### Index Sizes
- **Total indexes**: {size_info["summary"]["total_indexes"]}
- **Total index size**: {size_info["summary"]["total_index_size_bytes"] / 1024 / 1024:.2f} MB
- **Index overhead**: {size_info["summary"]["index_overhead_percent"]:.1f}% of table size

**Indexes Created:**
"""

    for idx in size_info["indexes"][:10]:
        report += f"- **{idx['name']}** ({idx['table']}): {idx['size']}\n"

    report += f"""
### Total Database Size
- **Database size**: {size_info["database"]["size"]} ({size_info["database"]["size_bytes"] / 1024 / 1024:.2f} MB)
- **Tables size**: {size_info["summary"]["total_table_size_bytes"] / 1024 / 1024:.2f} MB
- **Indexes size**: {size_info["summary"]["total_index_size_bytes"] / 1024 / 1024:.2f} MB
- **Index overhead ratio**: {size_info["summary"]["index_overhead_percent"]:.1f}%

## Performance Impact

### Query Performance
- **Average improvement**: {improvement_pct:.1f}%
- **P95 improvement**: {improvement_p95:.1f}%
- **P99 improvement**: {improvement_p99:.1f}%

### Storage Impact
- **Storage increase**: {size_info["summary"]["total_index_size_bytes"] / 1024 / 1024:.2f} MB
- **Index overhead**: {size_info["summary"]["index_overhead_percent"]:.1f}% of table size
- **Storage efficiency**: {"Good" if size_info["summary"]["index_overhead_percent"] < 50 else "High"} ({size_info["summary"]["index_overhead_percent"]:.1f}%)

## Observations

### {experiment_name} Database Characteristics
- **Total rows**: {sum(size_info["row_counts"].values()):,}
- **Index creation**: {autoindex.get("indexes_created", 0)} indexes created
- **Index overhead**: {size_info["summary"]["index_overhead_percent"]:.1f}% of table size
- **Performance gain**: {improvement_pct:.1f}% average improvement

### Key Findings
1. Indexes provide {"significant" if improvement_pct > 10 else "moderate" if improvement_pct > 5 else "minimal"} performance improvement
2. Index overhead is {"acceptable" if size_info["summary"]["index_overhead_percent"] < 50 else "high"} at {size_info["summary"]["index_overhead_percent"]:.1f}%
3. {"Indexes are cost-effective" if improvement_pct > size_info["summary"]["index_overhead_percent"] / 10 else "Index overhead may outweigh benefits"} for this database size
"""

    output_path = get_report_path(output_file)
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Generated report: {output_path}")


if __name__ == "__main__":
    # Generate reports
    generate_report(
        "Large Database",
        "results_baseline.json",
        "results_with_auto_index.json",
        "FINAL_REPORT_LARGE_DB.md",
    )
    print("Large DB report generated")

    # Note: Small DB report would need separate run with different data
    print("Note: Run small DB test separately to generate small DB report")
