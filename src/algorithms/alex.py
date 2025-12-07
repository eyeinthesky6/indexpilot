"""ALEX (Adaptive Learned Index) Algorithm Implementation

Based on "ALEX: An Updatable Adaptive Learned Index"
arXiv:1905.08898
Authors: Jialin Ding, Umar Farooq Minhas, et al.

This module implements ALEX concepts for adaptive index recommendations, helping to:
- Identify dynamic workloads that would benefit from ALEX-like behavior
- Recommend index strategies for write-heavy and dynamic workloads
- Adapt index recommendations based on workload changes

ALEX is designed for dynamic workloads with frequent inserts, updates, and deletes.
It provides better write performance than B-trees while maintaining low memory footprint.

Algorithm concepts are not copyrightable; attribution provided as good practice.
See THIRD_PARTY_ATTRIBUTIONS.md for complete attribution.
"""

import logging
from typing import Any

from src.config_loader import ConfigLoader
from src.stats import get_field_usage_stats, get_table_row_count
from src.workload_analysis import analyze_workload

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def should_use_alex_strategy(
    table_name: str,
    field_name: str,
    time_window_hours: int = 24,
) -> dict[str, Any]:
    """
    Determine if ALEX strategy would be beneficial for this table/field.

    Based on "ALEX: An Updatable Adaptive Learned Index"
    arXiv:1905.08898

    ALEX is beneficial for:
    - Dynamic workloads (frequent inserts/updates/deletes)
    - Write-heavy workloads
    - Tables with changing data distributions
    - Workloads that need adaptive optimization

    Args:
        table_name: Table name
        field_name: Field name
        time_window_hours: Time window for workload analysis

    Returns:
        dict with ALEX recommendation:
        - should_use_alex: bool - Whether ALEX strategy is recommended
        - confidence: float - Confidence in recommendation (0.0 to 1.0)
        - reason: str - Reason for recommendation
        - workload_characteristics: dict - Workload analysis details
        - recommendation: str - Specific recommendation
    """
    try:
        # Analyze workload for this table
        workload_data = analyze_workload(table_name=table_name, time_window_hours=time_window_hours)

        if workload_data.get("skipped"):
            return {
                "should_use_alex": False,
                "confidence": 0.0,
                "reason": workload_data.get("reason", "insufficient_data"),
                "workload_characteristics": {},
                "recommendation": "insufficient_data",
            }

        # Find table in workload data
        table_info = None
        for table in workload_data.get("tables", []):
            if table["table_name"] == table_name:
                table_info = table
                break

        if not table_info:
            return {
                "should_use_alex": False,
                "confidence": 0.0,
                "reason": "no_workload_data",
                "workload_characteristics": {},
                "recommendation": "no_workload_data",
            }

        # Get workload characteristics
        read_ratio = table_info.get("read_ratio", 0.5)
        write_ratio = table_info.get("write_ratio", 0.5)
        workload_type = table_info.get("workload_type", "balanced")
        total_queries = table_info.get("total_queries", 0)
        read_queries = table_info.get("read_queries", 0)
        write_queries = table_info.get("write_queries", 0)

        # Get field-specific stats
        all_field_stats = get_field_usage_stats(time_window_hours=time_window_hours)
        # Filter for the specific table and field
        field_stats = [
            stat
            for stat in all_field_stats
            if stat.get("table_name") == table_name and stat.get("field_name") == field_name
        ]
        field_stats = field_stats[0] if field_stats else None

        # Get table size
        table_row_count = get_table_row_count(table_name)

        # ALEX configuration thresholds
        write_heavy_threshold = _config_loader.get_float("features.alex.write_heavy_threshold", 0.3)
        dynamic_workload_threshold = _config_loader.get_float(
            "features.alex.dynamic_workload_threshold", 0.4
        )
        min_queries_for_alex = _config_loader.get_int("features.alex.min_queries_for_alex", 100)
        min_table_size_for_alex = _config_loader.get_int(
            "features.alex.min_table_size_for_alex", 1000
        )

        # Calculate dynamic workload score
        # ALEX benefits from:
        # 1. Write-heavy workloads (better write performance)
        # 2. Frequent updates (adaptive behavior)
        # 3. Changing data distributions (adaptive learning)
        dynamic_score = 0.0
        reasons = []

        # Factor 1: Write-heavy workload
        if write_ratio >= write_heavy_threshold:
            dynamic_score += 0.4
            reasons.append(f"write_heavy_workload ({write_ratio:.1%} writes)")

        # Factor 2: High write query frequency
        if write_queries >= min_queries_for_alex:
            dynamic_score += 0.3
            reasons.append(f"high_write_frequency ({write_queries} write queries)")

        # Factor 3: Balanced or mixed workload (ALEX adapts well)
        if workload_type in ("balanced", "mixed"):
            dynamic_score += 0.2
            reasons.append("balanced_workload_adapts_well")

        # Factor 4: Table size (ALEX benefits larger tables)
        if table_row_count >= min_table_size_for_alex:
            dynamic_score += 0.1
            reasons.append(f"table_size_suitable ({table_row_count} rows)")

        # Check if ALEX strategy is recommended
        should_use = dynamic_score >= dynamic_workload_threshold
        confidence = min(dynamic_score, 1.0)

        # Generate recommendation
        if should_use:
            recommendation = "alex_strategy_recommended"
            if write_ratio >= write_heavy_threshold:
                recommendation_detail = (
                    f"Write-heavy workload ({write_ratio:.1%} writes) benefits from "
                    "ALEX-like adaptive indexing strategy"
                )
            else:
                recommendation_detail = (
                    "Dynamic workload with frequent changes benefits from "
                    "ALEX-like adaptive indexing strategy"
                )
        else:
            recommendation = "alex_strategy_not_recommended"
            if read_ratio > 0.7:
                recommendation_detail = (
                    "Read-heavy workload - consider PGM-Index or standard B-tree instead"
                )
            elif total_queries < min_queries_for_alex:
                recommendation_detail = (
                    f"Insufficient query volume ({total_queries} queries) - "
                    "standard indexing sufficient"
                )
            else:
                recommendation_detail = "Standard indexing strategy sufficient for this workload"

        return {
            "should_use_alex": should_use,
            "confidence": confidence,
            "reason": "; ".join(reasons) if reasons else "standard_workload",
            "workload_characteristics": {
                "read_ratio": read_ratio,
                "write_ratio": write_ratio,
                "workload_type": workload_type,
                "total_queries": total_queries,
                "read_queries": read_queries,
                "write_queries": write_queries,
                "table_row_count": table_row_count,
                "dynamic_score": dynamic_score,
            },
            "recommendation": recommendation,
            "recommendation_detail": recommendation_detail,
        }

    except Exception as e:
        logger.error(f"Error in should_use_alex_strategy for {table_name}.{field_name}: {e}")
        return {
            "should_use_alex": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "workload_characteristics": {},
            "recommendation": "error",
        }


def get_alex_index_recommendation(
    table_name: str,
    field_name: str,
    query_patterns: dict[str, Any],
    time_window_hours: int = 24,
) -> dict[str, Any]:
    """
    Get ALEX-based index type recommendation.

    Since PostgreSQL doesn't natively support learned indexes, this function:
    1. Identifies when ALEX strategy would be beneficial
    2. Recommends PostgreSQL index types that provide similar benefits
    3. Suggests index strategies that mimic ALEX advantages

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information
        time_window_hours: Time window for analysis

    Returns:
        dict with index recommendation:
        - index_type: str - Recommended index type (btree, hash, etc.)
        - use_alex_strategy: bool - Whether to use ALEX-like approach
        - confidence: float - Confidence in recommendation
        - reason: str - Reason for recommendation
        - alex_insights: dict - ALEX-specific insights
    """
    try:
        # Check if ALEX strategy is recommended
        alex_analysis = should_use_alex_strategy(
            table_name=table_name, field_name=field_name, time_window_hours=time_window_hours
        )

        if not alex_analysis.get("should_use_alex", False):
            # ALEX not recommended, return standard recommendation
            return {
                "index_type": "btree",
                "use_alex_strategy": False,
                "confidence": 1.0 - alex_analysis.get("confidence", 0.0),
                "reason": alex_analysis.get("recommendation_detail", "standard_indexing"),
                "alex_insights": alex_analysis,
            }

        # ALEX strategy is recommended
        workload_chars = alex_analysis.get("workload_characteristics", {})
        write_ratio = workload_chars.get("write_ratio", 0.5)

        # For write-heavy workloads, recommend strategies that minimize write overhead
        # ALEX benefits: better write performance, adaptive updates

        # Strategy 1: Use partial indexes for filtered queries (reduces write overhead)
        # Strategy 2: Use covering indexes to reduce index maintenance
        # Strategy 3: Consider hash indexes for equality-only queries (lower write overhead)
        # Strategy 4: Use B-tree with fillfactor tuning for better write performance

        has_exact = query_patterns.get("has_exact", False)
        has_range = query_patterns.get("has_range", False)
        has_like = query_patterns.get("has_like", False)

        # For write-heavy workloads with equality queries, hash can be beneficial
        # (though PostgreSQL discourages hash indexes, they have lower write overhead)
        if write_ratio >= 0.4 and has_exact and not has_range and not has_like:
            return {
                "index_type": "hash",
                "use_alex_strategy": True,
                "confidence": alex_analysis.get("confidence", 0.7),
                "reason": (
                    "ALEX strategy: Hash index recommended for write-heavy equality queries "
                    "(lower write overhead, similar to ALEX benefits)"
                ),
                "alex_insights": alex_analysis,
                "strategy_note": (
                    "Note: Hash indexes have limitations in PostgreSQL (no WAL-logging, "
                    "no replication). Consider B-tree with fillfactor tuning as alternative."
                ),
            }

        # Default: B-tree with ALEX-like considerations
        # ALEX provides adaptive behavior, which we can approximate with:
        # - Partial indexes for filtered workloads
        # - Expression indexes for specific patterns
        # - Careful index selection to minimize write overhead

        return {
            "index_type": "btree",
            "use_alex_strategy": True,
            "confidence": alex_analysis.get("confidence", 0.7),
            "reason": (
                "ALEX strategy: B-tree recommended with write-performance considerations "
                "(minimize index overhead, use partial/expression indexes where beneficial)"
            ),
            "alex_insights": alex_analysis,
            "strategy_recommendations": [
                "Consider partial indexes for filtered queries (reduces write overhead)",
                "Use expression indexes for specific patterns (reduces index size)",
                "Monitor write performance and adjust index count accordingly",
                "Consider covering indexes to reduce index maintenance overhead",
            ],
        }

    except Exception as e:
        logger.error(f"Error in get_alex_index_recommendation for {table_name}.{field_name}: {e}")
        return {
            "index_type": "btree",
            "use_alex_strategy": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "alex_insights": {},
        }


def adapt_index_strategy_to_workload(
    table_name: str,
    field_name: str,
    current_index_type: str,
    time_window_hours: int = 24,
) -> dict[str, Any]:
    """
    Adapt index strategy based on workload changes (ALEX adaptive behavior).

    ALEX adapts to workload changes over time. This function:
    1. Monitors workload changes
    2. Recommends strategy adjustments
    3. Identifies when index type should change

    Args:
        table_name: Table name
        field_name: Field name
        current_index_type: Current index type
        time_window_hours: Time window for analysis

    Returns:
        dict with adaptation recommendation:
        - should_adapt: bool - Whether to adapt strategy
        - recommended_index_type: str - Recommended index type
        - confidence: float - Confidence in recommendation
        - reason: str - Reason for adaptation
        - workload_changes: dict - Detected workload changes
    """
    try:
        # Analyze current workload
        alex_analysis = should_use_alex_strategy(
            table_name=table_name, field_name=field_name, time_window_hours=time_window_hours
        )

        workload_chars = alex_analysis.get("workload_characteristics", {})
        should_use_alex = alex_analysis.get("should_use_alex", False)

        # Check if current index type matches workload needs
        if should_use_alex and current_index_type == "btree":
            # ALEX strategy recommended but using standard B-tree
            # This is acceptable (B-tree is versatile)
            return {
                "should_adapt": False,
                "recommended_index_type": "btree",
                "confidence": 0.5,
                "reason": "Current B-tree index is acceptable for ALEX-like workload",
                "workload_changes": workload_chars,
            }

        if not should_use_alex and current_index_type in ("hash", "gin"):
            # ALEX not recommended but using specialized index
            # May want to switch to B-tree for versatility
            return {
                "should_adapt": True,
                "recommended_index_type": "btree",
                "confidence": 0.6,
                "reason": (
                    "Workload doesn't benefit from specialized index, "
                    "consider switching to B-tree for versatility"
                ),
                "workload_changes": workload_chars,
            }

        # No adaptation needed
        return {
            "should_adapt": False,
            "recommended_index_type": current_index_type,
            "confidence": 0.8,
            "reason": "Current index type matches workload characteristics",
            "workload_changes": workload_chars,
        }

    except Exception as e:
        logger.error(
            f"Error in adapt_index_strategy_to_workload for {table_name}.{field_name}: {e}"
        )
        return {
            "should_adapt": False,
            "recommended_index_type": current_index_type,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "workload_changes": {},
        }
