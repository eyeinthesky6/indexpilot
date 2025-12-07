# mypy: ignore-errors
"""Before/after validation with EXPLAIN plan comparison"""

import logging
from typing import Any

from src.config_loader import ConfigLoader
from src.query_analyzer import analyze_query_plan, analyze_query_plan_fast
from src.type_definitions import JSONDict, QueryParams

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_before_after_validation_enabled() -> bool:
    """Check if before/after validation is enabled"""
    return _config_loader.get_bool("features.before_after_validation.enabled", True)


def compare_query_plans(
    query: str,
    params: QueryParams | None = None,
    before_plan: dict[str, Any] | None = None,
    after_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Compare query plans before and after index creation.

    Args:
        query: SQL query
        params: Query parameters
        before_plan: Query plan before index (if None, will analyze)
        after_plan: Query plan after index (if None, will analyze)

    Returns:
        dict with plan comparison results
    """
    if not is_before_after_validation_enabled():
        return {"skipped": True, "reason": "before_after_validation_disabled"}

    result: JSONDict = {
        "before_plan": {},
        "after_plan": {},
        "comparison": {},
        "improvement": {},
    }

    try:
        # Get before plan if not provided
        if before_plan is None:
            before_plan = analyze_query_plan_fast(query, params)
            if not before_plan:
                before_plan = analyze_query_plan(query, params)

        # Get after plan if not provided
        if after_plan is None:
            after_plan = analyze_query_plan_fast(query, params)
            if not after_plan:
                after_plan = analyze_query_plan(query, params)

        if not before_plan or not after_plan:
            return {"error": "Could not get query plans for comparison"}

        result["before_plan"] = {
            "total_cost": before_plan.get("total_cost", 0),
            "has_seq_scan": before_plan.get("has_seq_scan", False),
            "has_index_scan": before_plan.get("has_index_scan", False),
            "node_type": before_plan.get("node_type", "Unknown"),
            "actual_time_ms": before_plan.get("actual_time_ms", 0),
        }

        result["after_plan"] = {
            "total_cost": after_plan.get("total_cost", 0),
            "has_seq_scan": after_plan.get("has_seq_scan", False),
            "has_index_scan": after_plan.get("has_index_scan", False),
            "node_type": after_plan.get("node_type", "Unknown"),
            "actual_time_ms": after_plan.get("actual_time_ms", 0),
        }

        # Calculate improvements
        before_plan_val = result.get("before_plan", {})
        after_plan_val = result.get("after_plan", {})
        before_plan: dict[str, Any] | None = (
            before_plan_val if isinstance(before_plan_val, dict) else None
        )
        after_plan: dict[str, Any] | None = (
            after_plan_val if isinstance(after_plan_val, dict) else None
        )
        before_cost_val = (
            before_plan.get("total_cost", 0.0) if isinstance(before_plan, dict) else 0.0
        )
        after_cost_val = after_plan.get("total_cost", 0.0) if isinstance(after_plan, dict) else 0.0
        before_cost = float(before_cost_val) if isinstance(before_cost_val, (int, float)) else 0.0
        after_cost = float(after_cost_val) if isinstance(after_cost_val, (int, float)) else 0.0
        cost_improvement = (
            ((before_cost - after_cost) / before_cost * 100.0) if before_cost > 0 else 0.0
        )

        before_time_val = (
            before_plan.get("actual_time_ms", 0.0) if isinstance(before_plan, dict) else 0.0
        )
        after_time_val = (
            after_plan.get("actual_time_ms", 0.0) if isinstance(after_plan, dict) else 0.0
        )
        before_time = float(before_time_val) if isinstance(before_time_val, (int, float)) else 0.0
        after_time = float(after_time_val) if isinstance(after_time_val, (int, float)) else 0.0
        time_improvement = (
            ((before_time - after_time) / before_time * 100.0) if before_time > 0 else 0.0
        )

        # Check if sequential scan was eliminated
        seq_scan_eliminated = (
            result["before_plan"]["has_seq_scan"] and not result["after_plan"]["has_seq_scan"]
        )

        # Check if index scan was introduced
        index_scan_introduced = (
            not result["before_plan"]["has_index_scan"] and result["after_plan"]["has_index_scan"]
        )

        result["comparison"] = {
            "cost_reduction": before_cost - after_cost,
            "cost_improvement_pct": cost_improvement,
            "time_reduction_ms": before_time - after_time,
            "time_improvement_pct": time_improvement,
            "seq_scan_eliminated": seq_scan_eliminated,
            "index_scan_introduced": index_scan_introduced,
        }

        result["improvement"] = {
            "significant": cost_improvement > 20.0 or time_improvement > 20.0,
            "cost_improved": cost_improvement > 0,
            "time_improved": time_improvement > 0,
            "overall_improvement": cost_improvement > 0 or time_improvement > 0,
        }

        logger.info(
            f"Plan comparison: Cost improvement: {cost_improvement:.1f}%, "
            f"Time improvement: {time_improvement:.1f}%, "
            f"Seq scan eliminated: {seq_scan_eliminated}"
        )

    except Exception as e:
        logger.error(f"Failed to compare query plans: {e}")
        result["error"] = str(e)

    return result


def validate_index_improvement(
    query: str,
    params: QueryParams | None = None,
    before_plan: dict[str, Any] | None = None,
    after_plan: dict[str, Any] | None = None,
    min_improvement_pct: float = 20.0,
) -> dict[str, Any]:
    """
    Validate that index provides sufficient improvement.

    Args:
        query: SQL query
        params: Query parameters
        before_plan: Query plan before index
        after_plan: Query plan after index
        min_improvement_pct: Minimum improvement percentage required

    Returns:
        dict with validation results
    """
    comparison = compare_query_plans(query, params, before_plan, after_plan)

    if comparison.get("skipped") or comparison.get("error"):
        return {
            "valid": False,
            "reason": comparison.get("reason") or comparison.get("error", "unknown"),
            "comparison": comparison,
        }

    comparison_data = comparison.get("comparison", {})

    cost_improvement = comparison_data.get("cost_improvement_pct", 0.0)
    time_improvement = comparison_data.get("time_improvement_pct", 0.0)
    max_improvement = max(cost_improvement, time_improvement)

    valid = max_improvement >= min_improvement_pct

    return {
        "valid": valid,
        "improvement_pct": max_improvement,
        "cost_improvement_pct": cost_improvement,
        "time_improvement_pct": time_improvement,
        "min_required_pct": min_improvement_pct,
        "reason": f"Improvement {max_improvement:.1f}% {'meets' if valid else 'below'} threshold of {min_improvement_pct}%",
        "comparison": comparison,
        "should_rollback": not valid
        and max_improvement < 0,  # Negative improvement = should rollback
    }
