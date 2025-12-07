"""Academic algorithm implementations for IndexPilot

This package contains implementations of academic algorithms for database optimization.
Each algorithm is in its own module for better organization and testability.

Phase 1: Quick Wins (✅ Complete)
- CERT: Cardinality Estimation Restriction Testing (arXiv:2306.00355) - ✅ Implemented
- QPG: Query Plan Guidance (arXiv:2312.17510) - ✅ Implemented
- Cortex: Data Correlation Exploitation (arXiv:2012.06683) - ✅ Implemented

Phase 2: ML Integration
- Predictive Indexing (arXiv:1901.07064) - ✅ Implemented
- XGBoost Pattern Classification (arXiv:1603.02754) - ✅ Implemented

Phase 3: Advanced Index Types (✅ Complete)
- PGM-Index (arXiv:1910.06169) - ✅ Implemented
- ALEX (arXiv:1905.08898) - ✅ Implemented
- RadixStringSpline (arXiv:2111.14905) - ✅ Implemented
- Fractal Tree - ✅ Implemented

Phase 4: Specialized Features
- iDistance (Multi-Dimensional) - ✅ Implemented
- Bx-tree (Temporal) - TODO
"""

from src.algorithms.alex import (
    adapt_index_strategy_to_workload,
    get_alex_index_recommendation,
    should_use_alex_strategy,
)
from src.algorithms.cert import validate_cardinality_with_cert
from src.algorithms.cortex import enhance_composite_detection, find_correlated_columns
from src.algorithms.fractal_tree import get_fractal_tree_index_recommendation
from src.algorithms.idistance import (
    analyze_idistance_suitability,
    detect_multi_dimensional_pattern,
    get_idistance_index_recommendation,
)
from src.algorithms.pgm_index import analyze_pgm_index_suitability
from src.algorithms.predictive_indexing import (
    predict_index_utility,
    refine_heuristic_decision,
)
from src.algorithms.qpg import enhance_plan_analysis, identify_bottlenecks
from src.algorithms.radix_string_spline import get_rss_index_recommendation
from src.algorithms.xgboost_classifier import (
    classify_pattern,
    get_model_status,
    score_recommendation,
    train_model,
)

__all__ = [
    "validate_cardinality_with_cert",
    "enhance_plan_analysis",
    "identify_bottlenecks",
    "enhance_composite_detection",
    "find_correlated_columns",
    "predict_index_utility",
    "refine_heuristic_decision",
    "classify_pattern",
    "score_recommendation",
    "train_model",
    "get_model_status",
    # Phase 3: Advanced Index Types
    "analyze_pgm_index_suitability",
    "get_alex_index_recommendation",
    "should_use_alex_strategy",
    "adapt_index_strategy_to_workload",
    "get_rss_index_recommendation",
    "get_fractal_tree_index_recommendation",
    # Phase 4: Specialized Features
    "analyze_idistance_suitability",
    "detect_multi_dimensional_pattern",
    "get_idistance_index_recommendation",
]
