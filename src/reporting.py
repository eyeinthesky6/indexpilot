"""Reporting module - compare baseline vs auto-index results

DEPRECATED: This module is kept for backward compatibility.
All functionality has been merged into src.scaled_reporting.

For new code, use:
    from src.scaled_reporting import (
        load_results,
        get_mutation_summary,
        generate_report,
        generate_scaled_report,
        get_index_analysis,
        compare_performance
    )
"""

# Re-export all functions from scaled_reporting for backward compatibility
from src.scaled_reporting import (
    compare_performance,
    generate_report,
    generate_scaled_report,
    get_index_analysis,
    get_mutation_summary,
    load_results,
)

__all__ = [
    'load_results',
    'get_mutation_summary',
    'generate_report',
    'generate_scaled_report',
    'get_index_analysis',
    'compare_performance'
]


if __name__ == '__main__':
    generate_report()

