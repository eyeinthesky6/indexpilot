"""Stable public package surface for IndexPilot."""

from src.workload_dna import (
    analyze_workload_snapshot,
    build_index_review_report,
    build_workload_dna_report,
    extract_query_pattern,
    render_review_markdown,
    validate_report_with_hypopg,
)

__version__ = "1.1.0a1"

__all__ = [
    "__version__",
    "analyze_workload_snapshot",
    "build_index_review_report",
    "build_workload_dna_report",
    "extract_query_pattern",
    "render_review_markdown",
    "validate_report_with_hypopg",
]
