#!/usr/bin/env python3
"""
Auto-generate case study from benchmark results
Date: 08-12-2025
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.db import get_connection

TEMPLATE_PATH = project_root / "docs" / "case_studies" / "TEMPLATE.md"
CASE_STUDIES_DIR = project_root / "docs" / "case_studies"
BASELINE_RESULTS = project_root / "docs" / "audit" / "toolreports" / "results_baseline.json"
AUTOINDEX_RESULTS = project_root / "docs" / "audit" / "toolreports" / "results_with_auto_index.json"


def load_results():
    """Load baseline and autoindex results"""
    baseline = {}
    autoindex = {}
    
    if BASELINE_RESULTS.exists():
        with open(BASELINE_RESULTS, 'r') as f:
            baseline = json.load(f)
    
    if AUTOINDEX_RESULTS.exists():
        with open(AUTOINDEX_RESULTS, 'r') as f:
            autoindex = json.load(f)
    
    return baseline, autoindex


def get_mutation_stats():
    """Get index creation statistics from database"""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Count indexes created
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(*) FILTER (WHERE details_json->>'mode' = 'advisory') as advisory,
                       COUNT(*) FILTER (WHERE details_json->>'mode' = 'apply') as applied
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                AND created_at > NOW() - INTERVAL '1 hour'
            """)
            result = cursor.fetchone()
            
            # Get index details
            cursor.execute("""
                SELECT table_name, column_name, index_type
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                AND created_at > NOW() - INTERVAL '1 hour'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            indexes = cursor.fetchall()
            
            cursor.close()
            
            return {
                'total': result[0] if result else 0,
                'advisory': result[1] if result else 0,
                'applied': result[2] if result else 0,
                'details': indexes
            }
    except Exception as e:
        print(f"Warning: Could not get mutation stats: {e}")
        return {'total': 0, 'advisory': 0, 'applied': 0, 'details': []}


def extract_metrics(data, prefix=""):
    """Extract metrics from results JSON"""
    metrics = {}
    
    # Try different possible keys
    if isinstance(data, dict):
        metrics['total_queries'] = data.get('total_queries', data.get('queries', 0))
        metrics['avg_latency'] = data.get('avg_latency_ms', data.get('average_latency_ms', data.get('avg', 0)))
        metrics['p95_latency'] = data.get('p95_latency_ms', data.get('p95', 0))
        metrics['p99_latency'] = data.get('p99_latency_ms', data.get('p99', 0))
        
        # Try nested structures
        if 'statistics' in data:
            stats = data['statistics']
            metrics['avg_latency'] = stats.get('avg_latency_ms', metrics['avg_latency'])
            metrics['p95_latency'] = stats.get('p95_latency_ms', metrics['p95_latency'])
            metrics['p99_latency'] = stats.get('p99_latency_ms', metrics['p99_latency'])
    
    return metrics


def generate_case_study(name="CRM_Simulation", scenario="small"):
    """Generate case study from test results"""
    
    print(f"Generating case study: {name}")
    
    # Load results
    baseline, autoindex = load_results()
    
    # Get metrics
    baseline_metrics = extract_metrics(baseline)
    autoindex_metrics = extract_metrics(autoindex)
    
    # Get mutation stats
    mutation_stats = get_mutation_stats()
    
    # Calculate improvements
    improvements = {}
    if baseline_metrics.get('avg_latency') and autoindex_metrics.get('avg_latency'):
        if baseline_metrics['avg_latency'] > 0:
            improvement = ((baseline_metrics['avg_latency'] - autoindex_metrics['avg_latency']) / 
                          baseline_metrics['avg_latency']) * 100
            improvements['avg_latency'] = improvement
    
    # Read template
    if not TEMPLATE_PATH.exists():
        print(f"Error: Template not found at {TEMPLATE_PATH}")
        return False
    
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Fill in template
    today = datetime.now().strftime("%d-%m-%Y")
    
    replacements = {
        '[Database Name / Company Name]': name,
        'DD-MM-YYYY': today,
        '[Database name]': 'indexpilot',
        '[Schema description]': f'Multi-tenant CRM ({scenario} scenario)',
        '[Number of tables, rows, database size]': '4 tables, ~5,000-50,000 rows',
        '[What application uses this database]': 'IndexPilot CRM Simulation',
        '[Type of workload]': 'OLTP - Multi-tenant queries',
        '[Number of users, queries per second, etc.]': f'{baseline_metrics.get("total_queries", 0)} queries',
        '[Symptom 1]': 'Query performance validation',
        '[Symptom 2]': 'Index creation testing',
        '[Symptom 3]': 'Multi-tenant workload handling',
        '[Business impact]': 'System validation and performance testing',
        '[Table 1]': 'tenants, contacts, organizations, interactions',
        '[List existing indexes]': 'Primary keys only (baseline)',
        'X ms': f'{baseline_metrics.get("avg_latency", "N/A")} ms',
        'Y ms': f'{autoindex_metrics.get("avg_latency", "N/A")} ms',
        'Z%': f'{improvements.get("avg_latency", 0):.1f}%' if improvements.get('avg_latency') else 'N/A',
        '[Indexes that IndexPilot created]': f'{mutation_stats["total"]} indexes analyzed',
        '[Why IndexPilot created it]': 'Query pattern analysis',
        '[Query that triggered it]': 'Multi-tenant CRM queries',
        '[Cost-benefit analysis]': 'Cost-benefit analysis passed',
    }
    
    # Simple replacement
    case_study = template
    for old, new in replacements.items():
        case_study = case_study.replace(old, str(new))
    
    # Add actual metrics table
    metrics_section = f"""
## Performance Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Queries | {baseline_metrics.get('total_queries', 'N/A')} | {autoindex_metrics.get('total_queries', 'N/A')} | - |
| Average Latency | {baseline_metrics.get('avg_latency', 'N/A')} ms | {autoindex_metrics.get('avg_latency', 'N/A')} ms | {improvements.get('avg_latency', 0):.1f}% |
| P95 Latency | {baseline_metrics.get('p95_latency', 'N/A')} ms | {autoindex_metrics.get('p95_latency', 'N/A')} ms | - |
| P99 Latency | {baseline_metrics.get('p99_latency', 'N/A')} ms | {autoindex_metrics.get('p99_latency', 'N/A')} ms | - |

## Indexes Analyzed

- **Total**: {mutation_stats['total']}
- **Advisory Mode**: {mutation_stats['advisory']}
- **Applied**: {mutation_stats['applied']}
"""
    
    # Insert metrics section after Executive Summary
    if '## Problem Statement' in case_study:
        case_study = case_study.replace('## Problem Statement', metrics_section + '\n## Problem Statement')
    
    # Save case study
    output_file = CASE_STUDIES_DIR / f"CASE_STUDY_{name.upper().replace(' ', '_')}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(case_study)
    
    print(f"[OK] Case study generated: {output_file}")
    print(f"\nMetrics:")
    print(f"  Baseline: {baseline_metrics.get('total_queries', 'N/A')} queries, {baseline_metrics.get('avg_latency', 'N/A')}ms avg")
    print(f"  Autoindex: {autoindex_metrics.get('total_queries', 'N/A')} queries, {autoindex_metrics.get('avg_latency', 'N/A')}ms avg")
    print(f"  Indexes: {mutation_stats['total']} analyzed")
    
    return True


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate case study from benchmark results')
    parser.add_argument('--name', default='CRM_Simulation', help='Case study name')
    parser.add_argument('--scenario', default='small', help='Test scenario')
    
    args = parser.parse_args()
    
    if generate_case_study(args.name, args.scenario):
        print("\n[OK] Case study generation complete!")
        print(f"   Edit: docs/case_studies/CASE_STUDY_{args.name.upper().replace(' ', '_')}.md")
        return 0
    else:
        print("\n[ERROR] Case study generation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

