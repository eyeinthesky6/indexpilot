"""Academic algorithm implementations exposed through lazy imports.

The launch CLI only needs the lightweight planner admission path.  Importing
that path must not eagerly require optional scientific/ML dependencies.  The
public package-level exports remain available and load their implementation
only when a caller actually uses one.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "validate_cardinality_with_cert": ("src.algorithms.cert", "validate_cardinality_with_cert"),
    "enhance_plan_analysis": ("src.algorithms.qpg", "enhance_plan_analysis"),
    "identify_bottlenecks": ("src.algorithms.qpg", "identify_bottlenecks"),
    "analyze_plan_diversity": ("src.algorithms.qpg", "analyze_plan_diversity"),
    "enhance_composite_detection": ("src.algorithms.cortex", "enhance_composite_detection"),
    "find_correlated_columns": ("src.algorithms.cortex", "find_correlated_columns"),
    "predict_index_utility": ("src.algorithms.predictive_indexing", "predict_index_utility"),
    "refine_heuristic_decision": (
        "src.algorithms.predictive_indexing",
        "refine_heuristic_decision",
    ),
    "classify_pattern": ("src.algorithms.xgboost_classifier", "classify_pattern"),
    "score_recommendation": ("src.algorithms.xgboost_classifier", "score_recommendation"),
    "train_model": ("src.algorithms.xgboost_classifier", "train_model"),
    "get_model_status": ("src.algorithms.xgboost_classifier", "get_model_status"),
    "analyze_pgm_index_suitability": (
        "src.algorithms.pgm_index",
        "analyze_pgm_index_suitability",
    ),
    "get_alex_index_recommendation": (
        "src.algorithms.alex",
        "get_alex_index_recommendation",
    ),
    "should_use_alex_strategy": ("src.algorithms.alex", "should_use_alex_strategy"),
    "adapt_index_strategy_to_workload": (
        "src.algorithms.alex",
        "adapt_index_strategy_to_workload",
    ),
    "get_rss_index_recommendation": (
        "src.algorithms.radix_string_spline",
        "get_rss_index_recommendation",
    ),
    "get_fractal_tree_index_recommendation": (
        "src.algorithms.fractal_tree",
        "get_fractal_tree_index_recommendation",
    ),
    "analyze_idistance_suitability": (
        "src.algorithms.idistance",
        "analyze_idistance_suitability",
    ),
    "detect_multi_dimensional_pattern": (
        "src.algorithms.idistance",
        "detect_multi_dimensional_pattern",
    ),
    "get_idistance_index_recommendation": (
        "src.algorithms.idistance",
        "get_idistance_index_recommendation",
    ),
    "should_use_bx_tree_strategy": ("src.algorithms.bx_tree", "should_use_bx_tree_strategy"),
    "get_bx_tree_index_recommendation": (
        "src.algorithms.bx_tree",
        "get_bx_tree_index_recommendation",
    ),
    "optimize_index_with_constraints": (
        "src.algorithms.constraint_optimizer",
        "optimize_index_with_constraints",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load an optional algorithm only when its public export is requested."""
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
