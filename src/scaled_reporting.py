"""Enhanced reporting for scaled simulations - compares baseline vs auto-index

This module provides comprehensive reporting functionality including:
- Basic reporting (generate_report)
- Scaled simulation reporting (generate_scaled_report)
- Performance comparisons
- Index analysis
- Mutation summaries
"""

import json
import os
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.paths import get_report_path

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
    return _config_loader.get_bool('operational.reporting.enabled', True)


def load_results(filename):
    """Load results from JSON file"""
    filepath = get_report_path(filename)
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return None


def get_index_analysis():
    """Analyze created indexes and validate against query patterns"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get all created indexes
            cursor.execute("""
                SELECT
                    table_name,
                    field_name,
                    details_json,
                    created_at
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                ORDER BY created_at DESC
            """)
            indexes = cursor.fetchall()

            # Get query stats for these fields
            cursor.execute("""
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
            """)
            query_stats = cursor.fetchall()

            # Build analysis
            index_map = {(idx['table_name'], idx['field_name']): idx for idx in indexes}
            query_map = {(q['table_name'], q['field_name']): q for q in query_stats}

            analysis: dict[str, Any] = {
                'indexes_created': len(indexes),
                'index_details': [],
                'high_query_fields_without_index': [],
                'low_query_fields_with_index': []
            }

            # Analyze each index
            for idx in indexes:
                table = idx['table_name']
                field = idx['field_name']
                key = (table, field)

                query_info = query_map.get(key, {})
                details = json.loads(idx['details_json']) if isinstance(idx['details_json'], str) else idx['details_json']

                analysis['index_details'].append({
                    'table': table,
                    'field': field,
                    'queries_analyzed': details.get('queries_analyzed', 0),
                    'build_cost': details.get('build_cost_estimate', 0),
                    'current_queries': query_info.get('total_queries', 0),
                    'avg_duration_ms': query_info.get('avg_duration_ms', 0),
                    'p95_duration_ms': query_info.get('p95_duration_ms', 0),
                    'p99_duration_ms': query_info.get('p99_duration_ms', 0)
                })

            # Find fields with high query volume but no index
            for q in query_stats:
                key = (q['table_name'], q['field_name'])
                if key not in index_map and q['total_queries'] > 1000:
                    analysis['high_query_fields_without_index'].append({
                        'table': q['table_name'],
                        'field': q['field_name'],
                        'queries': q['total_queries'],
                        'avg_duration_ms': q['avg_duration_ms'],
                        'p95_duration_ms': q['p95_duration_ms']
                    })

            # Find indexes on low-query fields (potential over-indexing)
            for idx in indexes:
                key = (idx['table_name'], idx['field_name'])
                query_info = query_map.get(key, {})
                if query_info.get('total_queries', 0) < 100:
                    details = json.loads(idx['details_json']) if isinstance(idx['details_json'], str) else idx['details_json']
                    analysis['low_query_fields_with_index'].append({
                        'table': idx['table_name'],
                        'field': idx['field_name'],
                        'queries': query_info.get('total_queries', 0),
                        'queries_at_creation': details.get('queries_analyzed', 0)
                    })

            return analysis
        finally:
            cursor.close()


def compare_performance():
    """Compare baseline vs auto-index performance metrics"""
    baseline = load_results('results_baseline.json')
    autoindex = load_results('results_with_auto_index.json')

    if not baseline or not autoindex:
        return None

    comparison: dict[str, Any] = {
        'baseline': {
            'avg_ms': baseline.get('overall_avg_ms', 0),
            'p95_ms': baseline.get('overall_p95_ms', 0),
            'p99_ms': baseline.get('overall_p99_ms', 0),
            'total_queries': baseline.get('total_queries', 0)
        },
        'autoindex': {
            'avg_ms': autoindex.get('overall_avg_ms', 0),
            'p95_ms': autoindex.get('overall_p95_ms', 0),
            'p99_ms': autoindex.get('overall_p99_ms', 0),
            'total_queries': autoindex.get('total_queries', 0)
        }
    }

    # Calculate improvements
    if comparison['baseline']['avg_ms'] > 0:
        comparison['improvements'] = {
            'avg_improvement_pct': ((comparison['baseline']['avg_ms'] - comparison['autoindex']['avg_ms']) /
                                   comparison['baseline']['avg_ms']) * 100,
            'p95_improvement_pct': ((comparison['baseline']['p95_ms'] - comparison['autoindex']['p95_ms']) /
                                   comparison['baseline']['p95_ms']) * 100,
            'p99_improvement_pct': ((comparison['baseline']['p99_ms'] - comparison['autoindex']['p99_ms']) /
                                   comparison['baseline']['p99_ms']) * 100,
            'avg_improvement_ms': comparison['baseline']['avg_ms'] - comparison['autoindex']['avg_ms'],
            'p95_improvement_ms': comparison['baseline']['p95_ms'] - comparison['autoindex']['p95_ms'],
            'p99_improvement_ms': comparison['baseline']['p99_ms'] - comparison['autoindex']['p99_ms']
        }

        # Detect regression
        comparison['regression_detected'] = (
            comparison['improvements']['avg_improvement_pct'] < -5 or
            comparison['improvements']['p95_improvement_pct'] < -5 or
            comparison['improvements']['p99_improvement_pct'] < -5
        )
    else:
        comparison['improvements'] = None
        comparison['regression_detected'] = False

    return comparison


def get_mutation_summary():
    """Get summary of mutations (index creations)"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Count mutations by type
            cursor.execute("""
                SELECT
                    mutation_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT table_name) as tables_affected,
                    COUNT(DISTINCT field_name) as fields_affected
                FROM mutation_log
                GROUP BY mutation_type
                ORDER BY count DESC
            """)
            mutation_summary = cursor.fetchall()

            # Get index creation details
            cursor.execute("""
                SELECT
                    table_name,
                    field_name,
                    details_json,
                    created_at
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                ORDER BY created_at DESC
            """)
            index_creations = cursor.fetchall()

            return {
                'summary': mutation_summary,
                'indexes': index_creations
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
    baseline_results = load_results('results_baseline.json')
    autoindex_results = load_results('results_with_auto_index.json')

    if baseline_results:
        print("\nBaseline Simulation:")
        print(f"  Tenants: {baseline_results.get('num_tenants', 'N/A')}")
        print(f"  Queries per tenant: {baseline_results.get('queries_per_tenant', 'N/A')}")
        print(f"  Timestamp: {baseline_results.get('timestamp', 'N/A')}")

    if autoindex_results:
        print("\nAuto-Index Simulation:")
        print(f"  Tenants: {autoindex_results.get('num_tenants', 'N/A')}")
        print(f"  Queries per tenant: {autoindex_results.get('queries_per_tenant', 'N/A')}")
        print(f"  Indexes created: {autoindex_results.get('indexes_created', 'N/A')}")
        print(f"  Timestamp: {autoindex_results.get('timestamp', 'N/A')}")

    # Mutation summary
    print("\n" + "=" * 80)
    print("MUTATION SUMMARY")
    print("=" * 80)
    mutation_data = get_mutation_summary()

    if mutation_data['summary']:
        print("\nMutations by type:")
        for mut in mutation_data['summary']:
            print(f"  {mut['mutation_type']}: {mut['count']} mutations "
                  f"({mut['tables_affected']} tables, {mut['fields_affected']} fields)")

    if mutation_data['indexes']:
        print(f"\nIndexes Created ({len(mutation_data['indexes'])}):")
        for idx in mutation_data['indexes']:
            if idx['details_json']:
                if isinstance(idx['details_json'], str):
                    details = json.loads(idx['details_json'])
                else:
                    details = idx['details_json']
            else:
                details = {}
            print(f"  - {idx['table_name']}.{idx['field_name']}")
            if details:
                print(f"    Queries analyzed: {details.get('queries_analyzed', 'N/A')}")
                print(f"    Build cost estimate: {details.get('build_cost_estimate', 'N/A'):.2f}")

    # Query performance stats
    print("\n" + "=" * 80)
    print("QUERY PERFORMANCE STATISTICS")
    print("=" * 80)

    # Get field usage stats
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
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
            """)
            top_queries = cursor.fetchall()

            if top_queries:
                print("\nTop 20 Query Patterns (by volume):")
                print(f"{'Table':<20} {'Field':<20} {'Queries':<10} {'Avg (ms)':<12} {'P95 (ms)':<12} {'P99 (ms)':<12}")
                print("-" * 80)
                for q in top_queries:
                    print(f"{q['table_name']:<20} {q['field_name']:<20} {q['total_queries']:<10} "
                          f"{q['avg_duration_ms']:<12.2f} {q['p95_duration_ms']:<12.2f} {q['p99_duration_ms']:<12.2f}")
        finally:
            cursor.close()

    # Evaluation
    print("\n" + "=" * 80)
    print("EVALUATION")
    print("=" * 80)

    if autoindex_results and autoindex_results.get('indexes_created', 0) > 0:
        print("\n✓ Auto-indexing successfully created indexes based on query patterns")
        print("✓ Mutation log provides lineage of all schema changes")
        print("\nNote: For a complete performance comparison, you would need to:")
        print("  1. Run baseline and auto-index simulations separately")
        print("  2. Compare query latencies before and after index creation")
        print("  3. Measure the impact on specific query patterns")
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
    baseline = load_results('results_baseline.json')
    autoindex = load_results('results_with_auto_index.json')

    if baseline:
        print("\nBASELINE SIMULATION:")
        print(f"  Tenants: {baseline.get('num_tenants', 'N/A')}")
        print(f"  Queries per tenant: {baseline.get('queries_per_tenant', 'N/A'):,}")
        print(f"  Total queries: {baseline.get('total_queries', 'N/A'):,}")
        print(f"  Contacts per tenant: {baseline.get('contacts_per_tenant', 'N/A'):,}")
        print(f"  Average latency: {baseline.get('overall_avg_ms', 'N/A'):.2f}ms")
        print(f"  P95 latency: {baseline.get('overall_p95_ms', 'N/A'):.2f}ms")
        print(f"  P99 latency: {baseline.get('overall_p99_ms', 'N/A'):.2f}ms")

    if autoindex:
        print("\nAUTO-INDEX SIMULATION:")
        print(f"  Tenants: {autoindex.get('num_tenants', 'N/A')}")
        print(f"  Queries per tenant: {autoindex.get('queries_per_tenant', 'N/A'):,}")
        print(f"  Total queries: {autoindex.get('total_queries', 'N/A'):,}")
        print(f"  Contacts per tenant: {autoindex.get('contacts_per_tenant', 'N/A'):,}")
        print(f"  Indexes created: {autoindex.get('indexes_created', 'N/A')}")
        print(f"  Average latency: {autoindex.get('overall_avg_ms', 'N/A'):.2f}ms")
        print(f"  P95 latency: {autoindex.get('overall_p95_ms', 'N/A'):.2f}ms")
        print(f"  P99 latency: {autoindex.get('overall_p99_ms', 'N/A'):.2f}ms")

    # Performance comparison
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)

    comparison = compare_performance()
    if comparison and comparison['improvements']:
        imp = comparison['improvements']
        print("\nAverage Latency:")
        print(f"  Baseline: {comparison['baseline']['avg_ms']:.2f}ms")
        print(f"  Auto-Index: {comparison['autoindex']['avg_ms']:.2f}ms")
        print(f"  Improvement: {imp['avg_improvement_ms']:.2f}ms ({imp['avg_improvement_pct']:+.2f}%)")

        print("\nP95 Latency:")
        print(f"  Baseline: {comparison['baseline']['p95_ms']:.2f}ms")
        print(f"  Auto-Index: {comparison['autoindex']['p95_ms']:.2f}ms")
        print(f"  Improvement: {imp['p95_improvement_ms']:.2f}ms ({imp['p95_improvement_pct']:+.2f}%)")

        print("\nP99 Latency:")
        print(f"  Baseline: {comparison['baseline']['p99_ms']:.2f}ms")
        print(f"  Auto-Index: {comparison['autoindex']['p99_ms']:.2f}ms")
        print(f"  Improvement: {imp['p99_improvement_ms']:.2f}ms ({imp['p99_improvement_pct']:+.2f}%)")

        # Highlight if improvements are significant
        if imp['p95_improvement_pct'] > 10 or imp['p99_improvement_pct'] > 10:
            print("\n✓ SIGNIFICANT IMPROVEMENTS detected in P95/P99 percentiles!")
        elif imp['p95_improvement_pct'] > 0 or imp['p99_improvement_pct'] > 0:
            print("\n✓ Modest improvements detected in P95/P99 percentiles")
        else:
            print("\n⚠ No significant improvements in P95/P99 percentiles")

        # Check for regression
        if comparison['regression_detected']:
            print("\n⚠ REGRESSION DETECTED: Performance degraded after indexing!")
        else:
            print("\n✓ No regression detected")
    else:
        print("\n⚠ Cannot compare - missing baseline or auto-index results")

    # Index analysis
    print("\n" + "=" * 80)
    print("INDEX ANALYSIS")
    print("=" * 80)

    index_analysis = get_index_analysis()
    if index_analysis:
        print(f"\nTotal indexes created: {index_analysis['indexes_created']}")

        # Expected indexes (based on query patterns)
        expected_indexes = ['contacts.email', 'contacts.phone', 'organizations.industry',
                          'interactions.type', 'contacts.custom_text_1']
        created_index_keys = [(idx['table'], idx['field']) for idx in index_analysis['index_details']]
        expected_keys = [tuple(k.split('.')) for k in expected_indexes]

        print("\nIndex Selection Validation:")
        matches = [k for k in expected_keys if k in created_index_keys]
        print(f"  Expected indexes found: {len(matches)}/{len(expected_keys)}")

        if len(matches) == len(expected_keys):
            print("  ✓ All expected indexes were created")
        elif len(matches) >= len(expected_keys) * 0.8:
            print("  ✓ Most expected indexes were created")
        else:
            print("  ⚠ Some expected indexes were not created")

        print("\nCreated Indexes:")
        for idx in index_analysis['index_details']:
            print(f"  - {idx['table']}.{idx['field']}")
            print(f"    Queries at creation: {idx['queries_analyzed']:,}")
            print(f"    Current queries: {idx['current_queries']:,}")
            print(f"    Avg duration: {idx['avg_duration_ms']:.2f}ms")
            print(f"    P95 duration: {idx['p95_duration_ms']:.2f}ms")
            print(f"    P99 duration: {idx['p99_duration_ms']:.2f}ms")

        # Over-indexing detection
        if index_analysis['low_query_fields_with_index']:
            print("\n⚠ OVER-INDEXING DETECTED:")
            print(f"  Found {len(index_analysis['low_query_fields_with_index'])} indexes on low-query fields:")
            for idx in index_analysis['low_query_fields_with_index']:
                print(f"    - {idx['table']}.{idx['field']} ({idx['queries']} queries, created at {idx['queries_at_creation']} queries)")
        else:
            print("\n✓ No over-indexing detected - all indexes are on high-query fields")

        # High-query fields without indexes
        if index_analysis['high_query_fields_without_index']:
            print("\n⚠ HIGH-QUERY FIELDS WITHOUT INDEXES:")
            print(f"  Found {len(index_analysis['high_query_fields_without_index'])} high-query fields without indexes:")
            for field in index_analysis['high_query_fields_without_index'][:10]:  # Top 10
                print(f"    - {field['table']}.{field['field']} ({field['queries']:,} queries, avg: {field['avg_duration_ms']:.2f}ms, P95: {field['p95_duration_ms']:.2f}ms)")
        else:
            print("\n✓ All high-query fields have indexes")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if comparison and comparison['improvements']:
        imp = comparison['improvements']
        if imp['p95_improvement_pct'] > 10 or imp['p99_improvement_pct'] > 10:
            print("✓ P95/P99 improvements are OBVIOUS and significant")
        elif imp['p95_improvement_pct'] > 0 or imp['p99_improvement_pct'] > 0:
            print("✓ P95/P99 improvements are visible but modest")
        else:
            print("⚠ P95/P99 improvements are not obvious at this scale")

    if index_analysis:
        matches = [k for k in expected_keys if k in created_index_keys]
        if len(matches) >= len(expected_keys) * 0.8:
            print("✓ Indexes created match intuition (expected fields indexed)")
        else:
            print("⚠ Some expected indexes were not created")

        if index_analysis['low_query_fields_with_index']:
            print("⚠ Over-indexing detected - some indexes may be unnecessary")
        else:
            print("✓ No over-indexing - index selection is appropriate")

    if comparison and comparison['regression_detected']:
        print("⚠ REGRESSION detected - performance degraded after indexing")
    elif comparison:
        print("✓ No regression detected")

    print("\n" + "=" * 80)

    # Save detailed report
    from datetime import datetime
    report_data = {
        'comparison': comparison,
        'index_analysis': index_analysis,
        'timestamp': datetime.now().isoformat()
    }

    report_path = get_report_path('scaled_analysis_report.json')
    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2, default=str)

    print(f"\nDetailed analysis saved to {report_path}")


if __name__ == '__main__':
    generate_scaled_report()

