"""Bx-tree (Moving Objects/Temporal Indexing) Algorithm Implementation

Bx-tree is an extension of B+ tree designed to efficiently index and query
moving objects in spatio-temporal databases. It integrates spatial and temporal
information into a single-dimensional index structure.

This module implements Bx-tree concepts for temporal query pattern detection,
helping to:
- Identify temporal query patterns that would benefit from Bx-tree-like behavior
- Recommend index strategies for temporal/moving object queries
- Provide temporal partitioning optimization recommendations

Bx-tree benefits:
- Temporal optimization: Extension of B+ tree for moving objects
- Time partitioning: Partitions by update time
- Space-filling curves: Uses space-filling curves for spatial mapping
- Dynamic datasets: Efficient for dynamic datasets with temporal queries

Note: PostgreSQL doesn't natively support Bx-tree indexes, but this module
provides analysis and recommendations for temporal query optimization strategies.

Algorithm concepts are not copyrightable; attribution provided as good practice.
"""

import logging

from src.config_loader import ConfigLoader
from src.stats import get_table_row_count
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def should_use_bx_tree_strategy(
    table_name: str,
    field_name: str,
    query_patterns: JSONDict,
) -> JSONDict:
    """
    Determine if Bx-tree strategy would be beneficial for temporal queries.

    Bx-tree indexes are beneficial for:
    - Temporal queries (time-based range queries)
    - Moving object queries (spatial-temporal queries)
    - Queries with time-based filters
    - Tables with temporal columns (timestamp, date)
    - Dynamic datasets with frequent temporal updates

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information

    Returns:
        dict with Bx-tree recommendation:
        - should_use_bx_tree: bool - Whether Bx-tree strategy is recommended
        - confidence: float - Confidence in recommendation (0.0 to 1.0)
        - reason: str - Reason for recommendation
        - temporal_characteristics: dict - Temporal analysis details
        - recommendation: str - Specific recommendation
    """
    try:
        # Check for temporal query patterns
        has_temporal = query_patterns.get("has_temporal", False)
        has_time_range = query_patterns.get("has_time_range", False)
        has_timestamp = query_patterns.get("has_timestamp", False)
        has_date_range = query_patterns.get("has_date_range", False)

        # Check field type for temporal types
        field_type = (
            query_patterns.get("field_type", "").lower() if query_patterns.get("field_type") else ""
        )
        is_temporal_type = any(
            temporal_type in field_type
            for temporal_type in ["timestamp", "date", "time", "interval"]
        )

        # Get table size
        table_row_count = get_table_row_count(table_name)

        # Bx-tree configuration thresholds
        min_table_size_for_bx_tree = _config_loader.get_int(
            "features.bx_tree.min_table_size", 10000
        )
        _ = _config_loader.get_int(
            "features.bx_tree.min_temporal_queries", 50
        )  # Reserved for future use

        # Check if we have temporal characteristics
        if not (
            has_temporal or has_time_range or has_timestamp or has_date_range or is_temporal_type
        ):
            return {
                "should_use_bx_tree": False,
                "confidence": 0.0,
                "reason": "no_temporal_patterns",
                "temporal_characteristics": {
                    "has_temporal": has_temporal,
                    "has_time_range": has_time_range,
                    "has_timestamp": has_timestamp,
                    "has_date_range": has_date_range,
                    "is_temporal_type": is_temporal_type,
                },
                "recommendation": "bx_tree_not_applicable",
                "recommendation_detail": "No temporal query patterns detected - Bx-tree not applicable",
            }

        # Check if table is large enough
        if table_row_count < min_table_size_for_bx_tree:
            return {
                "should_use_bx_tree": False,
                "confidence": 0.0,
                "reason": "table_too_small",
                "temporal_characteristics": {
                    "table_row_count": table_row_count,
                    "has_temporal": has_temporal,
                    "has_time_range": has_time_range,
                },
                "recommendation": "bx_tree_not_applicable",
                "recommendation_detail": (
                    f"Table too small ({table_row_count} rows) for Bx-tree consideration. "
                    f"Need at least {min_table_size_for_bx_tree} rows."
                ),
            }

        # Calculate Bx-tree suitability score
        # Bx-tree benefits from:
        # 1. Temporal query patterns (primary factor)
        # 2. Temporal field types
        # 3. Time range queries
        # 4. Large tables (more benefit from temporal partitioning)
        bx_tree_score = 0.0
        reasons = []

        # Factor 1: Temporal query patterns (most important)
        if has_temporal or has_time_range or has_timestamp or has_date_range:
            bx_tree_score += 0.4
            reasons.append("temporal_query_patterns")

        # Factor 2: Temporal field type
        if is_temporal_type:
            bx_tree_score += 0.3
            reasons.append(f"temporal_field_type ({field_type})")

        # Factor 3: Time range queries (Bx-tree strength)
        if has_time_range or has_date_range:
            bx_tree_score += 0.2
            reasons.append("time_range_queries")

        # Factor 4: Large table (more benefit from temporal partitioning)
        if table_row_count >= 100000:
            bx_tree_score += 0.1
            reasons.append(f"large_table ({table_row_count} rows)")

        # Check if Bx-tree strategy is recommended
        min_bx_tree_score = _config_loader.get_float("features.bx_tree.min_suitability_score", 0.5)
        should_use = bx_tree_score >= min_bx_tree_score
        confidence = min(bx_tree_score, 1.0)

        # Generate recommendation
        if should_use:
            recommendation = "bx_tree_strategy_recommended"
            recommendation_detail = (
                "Temporal query patterns detected - would benefit from "
                "Bx-tree-like temporal indexing strategy"
            )
        else:
            recommendation = "bx_tree_strategy_not_recommended"
            recommendation_detail = "Standard indexing strategy sufficient for this workload"

        return {
            "should_use_bx_tree": should_use,
            "confidence": confidence,
            "reason": "; ".join(reasons) if reasons else "standard_workload",
            "temporal_characteristics": {
                "has_temporal": has_temporal,
                "has_time_range": has_time_range,
                "has_timestamp": has_timestamp,
                "has_date_range": has_date_range,
                "is_temporal_type": is_temporal_type,
                "field_type": field_type,
                "table_row_count": table_row_count,
                "bx_tree_score": bx_tree_score,
            },
            "recommendation": recommendation,
            "recommendation_detail": recommendation_detail,
        }

    except Exception as e:
        logger.error(f"Error in should_use_bx_tree_strategy for {table_name}.{field_name}: {e}")
        return {
            "should_use_bx_tree": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "temporal_characteristics": {},
            "recommendation": "error",
        }


def get_bx_tree_index_recommendation(
    table_name: str,
    field_name: str,
    query_patterns: JSONDict,
) -> JSONDict:
    """
    Get Bx-tree-based index recommendation for temporal queries.

    Since PostgreSQL doesn't natively support Bx-tree indexes, this function:
    1. Identifies when Bx-tree strategy would be beneficial
    2. Recommends PostgreSQL index types that provide similar temporal benefits
    3. Suggests index strategies that optimize temporal queries

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information

    Returns:
        dict with index recommendation:
        - index_type: str - Recommended index type (btree, etc.)
        - use_bx_tree_strategy: bool - Whether to use Bx-tree-like approach
        - confidence: float - Confidence in recommendation
        - reason: str - Reason for recommendation
        - bx_tree_insights: dict - Bx-tree-specific insights
    """
    try:
        # Check if Bx-tree strategy is recommended
        bx_tree_analysis = should_use_bx_tree_strategy(
            table_name=table_name,
            field_name=field_name,
            query_patterns=query_patterns,
        )

        if not bx_tree_analysis.get("should_use_bx_tree", False):
            # Bx-tree not recommended, return standard recommendation
            return {
                "index_type": "btree",
                "use_bx_tree_strategy": False,
                "confidence": 1.0 - bx_tree_analysis.get("confidence", 0.0),
                "reason": bx_tree_analysis.get("recommendation_detail", "standard_indexing"),
                "bx_tree_insights": bx_tree_analysis,
            }

        # Bx-tree strategy is recommended
        temporal_chars = bx_tree_analysis.get("temporal_characteristics", {})
        has_time_range = temporal_chars.get("has_time_range", False)
        has_date_range = temporal_chars.get("has_date_range", False)

        # For temporal queries, Bx-tree benefits:
        # - Temporal partitioning (time-based organization)
        # - Efficient time range queries
        # - Space-filling curves for spatial-temporal queries

        # Strategy: B-tree with temporal optimization
        # Bx-tree uses temporal partitioning, which we can approximate with:
        # - B-tree indexes on temporal columns
        # - Partial indexes for time ranges
        # - Expression indexes for time-based functions

        if has_time_range or has_date_range:
            return {
                "index_type": "btree",
                "use_bx_tree_strategy": True,
                "confidence": bx_tree_analysis.get("confidence", 0.7),
                "reason": (
                    "Bx-tree strategy: B-tree with temporal partitioning recommended "
                    "for time range queries (similar to Bx-tree's time-based organization)"
                ),
                "bx_tree_insights": bx_tree_analysis,
                "strategy_recommendations": [
                    "Use B-tree index on temporal column for efficient time range queries",
                    "Consider partial indexes for specific time ranges (reduces index size)",
                    "Use expression indexes on date/time functions if needed",
                    "Consider partitioning table by time ranges for very large temporal datasets",
                ],
            }

        # Default: B-tree with temporal considerations
        return {
            "index_type": "btree",
            "use_bx_tree_strategy": True,
            "confidence": bx_tree_analysis.get("confidence", 0.7),
            "reason": (
                "Bx-tree strategy: B-tree recommended for temporal queries "
                "(use temporal partitioning strategies where beneficial)"
            ),
            "bx_tree_insights": bx_tree_analysis,
            "strategy_recommendations": [
                "Use B-tree index on temporal column",
                "Consider partial indexes for filtered time ranges",
                "Monitor query performance and adjust based on temporal patterns",
            ],
        }

    except Exception as e:
        logger.error(
            f"Error in get_bx_tree_index_recommendation for {table_name}.{field_name}: {e}"
        )
        return {
            "index_type": "btree",
            "use_bx_tree_strategy": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "bx_tree_insights": {},
        }
