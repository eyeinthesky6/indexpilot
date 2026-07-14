"""Stable public package surface for IndexPilot."""

from src.workload_dna import (
    analyze_workload_snapshot,
    build_workload_dna_report,
    extract_query_pattern,
    validate_report_with_hypopg,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "analyze_workload_snapshot",
    "build_workload_dna_report",
    "extract_query_pattern",
    "validate_report_with_hypopg",
]
