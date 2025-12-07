"""QPG (Query Plan Guidance) Algorithm Implementation

Based on "Query Plan Guidance: Using Query Plans to Guide Testing and Optimization"
arXiv:2312.17510

This module implements QPG concepts for diverse plan generation and bottleneck identification,
helping to improve query optimization robustness and reduce wrong index recommendations.
"""

import logging
from typing import Any

from src.config_loader import ConfigLoader
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_qpg_enabled() -> bool:
    """Check if QPG enhancement is enabled"""
    return _config_loader.get_bool("features.qpg.enabled", True)


def get_qpg_config() -> dict[str, Any]:
    """Get QPG configuration"""
    return {
        "enabled": is_qpg_enabled(),
        "diverse_plan_generation": _config_loader.get_bool(
            "features.qpg.diverse_plan_generation", True
        ),
        "bottleneck_analysis_depth": _config_loader.get_int(
            "features.qpg.bottleneck_analysis_depth", 3
        ),
        "identify_logic_bugs": _config_loader.get_bool("features.qpg.identify_logic_bugs", True),
    }


def identify_bottlenecks(
    plan_node: dict[str, Any], depth: int = 0, max_depth: int = 3
) -> list[dict[str, Any]]:
    """
    Identify bottlenecks in query plan using QPG principles.

    QPG focuses on identifying expensive nodes, join types, and potential logic bugs.

    Args:
        plan_node: Query plan node (from EXPLAIN JSON)
        depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
        List of bottleneck information
    """
    if not is_qpg_enabled():
        return []

    if depth > max_depth:
        return []

    bottlenecks: list[dict[str, Any]] = []

    node_type = plan_node.get("Node Type", "Unknown")
    total_cost = plan_node.get("Total Cost", 0)
    actual_time = plan_node.get("Actual Total Time", 0)
    rows = plan_node.get("Actual Rows", plan_node.get("Plan Rows", 0))

    # Identify expensive nodes (high cost relative to rows)
    if total_cost > 0 and rows > 0:
        cost_per_row = total_cost / rows if rows > 0 else 0
        if cost_per_row > 100:  # High cost per row threshold
            bottlenecks.append(
                {
                    "type": "expensive_node",
                    "node_type": node_type,
                    "cost": total_cost,
                    "rows": rows,
                    "cost_per_row": cost_per_row,
                    "severity": "high" if cost_per_row > 1000 else "medium",
                    "recommendation": f"Node '{node_type}' has high cost per row ({cost_per_row:.2f}). "
                    f"Consider optimizing this operation.",
                }
            )

    # Identify slow operations (high actual time)
    if actual_time > 100:  # 100ms threshold
        bottlenecks.append(
            {
                "type": "slow_operation",
                "node_type": node_type,
                "actual_time_ms": actual_time,
                "severity": "high" if actual_time > 1000 else "medium",
                "recommendation": f"Node '{node_type}' takes {actual_time:.2f}ms. "
                f"Consider adding indexes or optimizing query structure.",
            }
        )

    # Identify problematic join types
    if node_type in ["Nested Loop", "Hash Join", "Merge Join"]:
        join_condition = plan_node.get("Join Filter") or plan_node.get("Hash Cond")
        if join_condition and total_cost > 1000:
            bottlenecks.append(
                {
                    "type": "expensive_join",
                    "node_type": node_type,
                    "join_condition": join_condition,
                    "cost": total_cost,
                    "severity": "high" if total_cost > 10000 else "medium",
                    "recommendation": f"Expensive {node_type} detected (cost: {total_cost:.2f}). "
                    f"Consider indexes on join columns: {join_condition}",
                }
            )

    # Identify sequential scans (already detected, but add QPG context)
    if node_type == "Seq Scan":
        relation_name = plan_node.get("Relation Name", "unknown")
        filter_condition = plan_node.get("Filter")
        if filter_condition:
            bottlenecks.append(
                {
                    "type": "sequential_scan_with_filter",
                    "relation": relation_name,
                    "filter": filter_condition,
                    "cost": total_cost,
                    "rows": rows,
                    "severity": "high",
                    "recommendation": f"Sequential scan on '{relation_name}' with filter '{filter_condition}'. "
                    f"Consider creating an index on filtered columns.",
                }
            )

    # Recursively analyze child nodes
    if "Plans" in plan_node:
        for child_plan in plan_node["Plans"]:
            child_bottlenecks = identify_bottlenecks(
                child_plan, depth=depth + 1, max_depth=max_depth
            )
            bottlenecks.extend(child_bottlenecks)

    return bottlenecks


def analyze_plan_diversity(
    base_plan: dict[str, Any], alternative_plans: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    Analyze plan diversity using QPG principles.

    QPG generates diverse query plans to identify bottlenecks and logic bugs.

    Args:
        base_plan: Base query plan
        alternative_plans: Alternative plans (if available)

    Returns:
        dict with diversity analysis
    """
    if not is_qpg_enabled():
        return {"diversity_score": 0.0, "note": "QPG disabled"}

    config = get_qpg_config()
    if not config.get("diverse_plan_generation", True):
        return {"diversity_score": 0.0, "note": "diverse_plan_generation disabled"}

    # For now, analyze the base plan
    # In a full implementation, we would generate alternative plans by:
    # - Trying different join orders
    # - Trying different index hints
    # - Trying different query structures

    base_cost = base_plan.get("Total Cost", 0)
    base_node_type = base_plan.get("Node Type", "Unknown")

    diversity_info: JSONDict = {
        "diversity_score": 0.0,
        "base_plan_cost": base_cost,
        "base_node_type": base_node_type,
        "alternative_plans_count": len(alternative_plans) if alternative_plans else 0,
    }

    if alternative_plans:
        # Compare costs across plans
        costs = [base_cost] + [p.get("Total Cost", 0) for p in alternative_plans]
        min_cost = min(costs)
        max_cost = max(costs)

        if max_cost > 0:
            # Diversity score: how much variation in costs
            diversity_info["diversity_score"] = (max_cost - min_cost) / max_cost
            diversity_info["cost_variance"] = max_cost - min_cost
            diversity_info["best_plan_cost"] = min_cost
            diversity_info["worst_plan_cost"] = max_cost

    return diversity_info


def identify_logic_bugs(plan_node: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Identify potential logic bugs using QPG principles.

    QPG identifies logic bugs by analyzing query plans for anomalies.

    Args:
        plan_node: Query plan node

    Returns:
        List of potential logic bugs
    """
    if not is_qpg_enabled():
        return []

    config = get_qpg_config()
    if not config.get("identify_logic_bugs", True):
        return []

    logic_bugs: list[dict[str, Any]] = []

    # Check for suspicious patterns
    node_type = plan_node.get("Node Type", "Unknown")
    plan_rows = plan_node.get("Plan Rows", 0)
    actual_rows = plan_node.get("Actual Rows", 0)

    # Large discrepancy between planned and actual rows suggests statistics issues
    if plan_rows > 0 and actual_rows > 0:
        discrepancy_ratio = abs(plan_rows - actual_rows) / max(plan_rows, actual_rows)
        if discrepancy_ratio > 0.5:  # 50% discrepancy threshold
            logic_bugs.append(
                {
                    "type": "statistics_mismatch",
                    "node_type": node_type,
                    "planned_rows": plan_rows,
                    "actual_rows": actual_rows,
                    "discrepancy_ratio": discrepancy_ratio,
                    "severity": "high" if discrepancy_ratio > 2.0 else "medium",
                    "recommendation": f"Large discrepancy between planned ({plan_rows}) and actual ({actual_rows}) rows. "
                    f"Statistics may be stale. Consider running ANALYZE.",
                }
            )

    # Check for cartesian products (very expensive)
    if (
        node_type == "Nested Loop" and plan_node.get("Join Filter") is None and plan_rows > 10000
    ):  # Large cartesian product
        logic_bugs.append(
            {
                "type": "potential_cartesian_product",
                "node_type": node_type,
                "rows": plan_rows,
                "severity": "high",
                "recommendation": "Potential cartesian product detected. "
                "Check if join condition is missing.",
            }
        )

    # Recursively check child nodes
    if "Plans" in plan_node:
        for child_plan in plan_node["Plans"]:
            child_bugs = identify_logic_bugs(child_plan)
            logic_bugs.extend(child_bugs)

    return logic_bugs


def enhance_plan_analysis(
    base_analysis: dict[str, Any], plan_node: dict[str, Any]
) -> dict[str, Any]:
    """
    Enhance query plan analysis with QPG insights.

    Args:
        base_analysis: Base plan analysis from analyze_query_plan
        plan_node: Query plan node

    Returns:
        Enhanced analysis with QPG insights
    """
    if not is_qpg_enabled():
        return base_analysis

    enhanced = base_analysis.copy()

    # Add QPG bottleneck identification
    bottlenecks = identify_bottlenecks(plan_node)
    if bottlenecks:
        enhanced["qpg_bottlenecks"] = bottlenecks
        enhanced["bottleneck_count"] = len(bottlenecks)

        # Add high-severity bottlenecks to recommendations
        high_severity = [b for b in bottlenecks if b.get("severity") == "high"]
        for bottleneck in high_severity:
            if "recommendation" in bottleneck:
                enhanced["recommendations"].append(f"[QPG] {bottleneck['recommendation']}")

    # Add QPG logic bug identification
    logic_bugs = identify_logic_bugs(plan_node)
    if logic_bugs:
        enhanced["qpg_logic_bugs"] = logic_bugs
        enhanced["logic_bug_count"] = len(logic_bugs)

        # Add logic bugs to recommendations
        for bug in logic_bugs:
            if "recommendation" in bug:
                enhanced["recommendations"].append(f"[QPG Logic Bug] {bug['recommendation']}")

    # Add diversity analysis (if alternative plans available)
    # For now, just mark that QPG analysis was performed
    enhanced["qpg_analysis_performed"] = True

    return enhanced
