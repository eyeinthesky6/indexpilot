"""Academic algorithm implementations for IndexPilot

This package contains implementations of academic algorithms for database optimization.
Each algorithm is in its own module for better organization and testability.

Phase 1: Quick Wins (✅ Complete)
- CERT: Cardinality Estimation Restriction Testing (arXiv:2306.00355) - ✅ Implemented
- QPG: Query Plan Guidance (arXiv:2312.17510) - ✅ Implemented
- Cortex: Data Correlation Exploitation (arXiv:2012.06683) - ✅ Implemented

Phase 2: ML Integration (Pending)
- Predictive Indexing (arXiv:1901.07064) - TODO
- XGBoost Pattern Classification (arXiv:1603.02754) - TODO

Phase 3: Advanced Index Types (Pending)
- PGM-Index, ALEX, RadixStringSpline, Fractal Tree, iDistance, Bx-tree - TODO
"""

from src.algorithms.cert import validate_cardinality_with_cert
from src.algorithms.cortex import enhance_composite_detection, find_correlated_columns
from src.algorithms.qpg import enhance_plan_analysis, identify_bottlenecks

__all__ = [
    "validate_cardinality_with_cert",
    "enhance_plan_analysis",
    "identify_bottlenecks",
    "enhance_composite_detection",
    "find_correlated_columns",
]
