"""Sustained pattern detection to avoid false optimizations"""

import logging

from src.config_loader import ConfigLoader
from src.monitoring import get_monitoring
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def _get_min_days_sustained() -> int:
    """Get minimum days of sustained pattern from config or default"""
    return _config_loader.get_int("features.pattern_detection.min_days_sustained", 3)


def _get_min_queries_per_day() -> int:
    """Get minimum queries per day from config or default"""
    return _config_loader.get_int("features.pattern_detection.min_queries_per_day", 50)


def _get_spike_detection_window() -> int:
    """Get spike detection window in days from config or default"""
    return _config_loader.get_int("features.pattern_detection.spike_detection_window", 7)


def _get_spike_threshold() -> float:
    """Get spike threshold multiplier from config or default"""
    return _config_loader.get_float("features.pattern_detection.spike_threshold", 3.0)


def detect_sustained_pattern(
    table_name: str, field_name: str, days: int = 7, time_window_hours: int | None = None
) -> dict[str, JSONValue]:
    """
    Detect if query pattern is sustained (not a one-time spike).

    Args:
        table_name: Table name
        field_name: Field name
        days: Number of days to analyze
        time_window_hours: If provided, use hourly analysis for short time windows (simulation mode)

    Returns:
        dict with pattern analysis
    """
    from src.db import get_cursor
    from src.validation import validate_field_name, validate_table_name

    table_name = validate_table_name(table_name)
    field_name = validate_field_name(field_name, table_name)

    with get_cursor() as cursor:
        # For short time windows (simulation mode), use hourly analysis instead of daily
        if time_window_hours and time_window_hours <= 24:
            # Use hourly grouping for simulations
            cursor.execute(
                """
                SELECT
                    DATE_TRUNC('hour', created_at) as query_period,
                    COUNT(*) as query_count
                FROM query_stats
                WHERE table_name = %s
                  AND field_name = %s
                  AND created_at >= NOW() - INTERVAL '1 hour' * %s
                GROUP BY DATE_TRUNC('hour', created_at)
                ORDER BY query_period DESC
            """,
                (table_name, field_name, time_window_hours),
            )

            period_counts = cursor.fetchall()

            # For simulations, require at least 2 hours of data and lower threshold
            min_periods_required = 2
            min_queries_per_period = 10  # Lower threshold for simulations

            if not period_counts or len(period_counts) < min_periods_required:
                return {
                    "is_sustained": False,
                    "reason": f"Insufficient data: {len(period_counts) if period_counts else 0} hours",
                    "days_analyzed": len(period_counts) if period_counts else 0,
                    "avg_queries_per_day": 0,
                    "min_queries_per_day": 0,
                    "max_queries_per_day": 0,
                }

            # Calculate statistics for hourly data
            # Use safe access to prevent tuple index errors
            from src.db import safe_get_row_value

            query_counts: list[int] = []
            for row in period_counts:
                count_val = safe_get_row_value(row, "query_count", 0) or safe_get_row_value(row, 1, 0)
                count = int(count_val) if isinstance(count_val, (int, float)) else 0
                query_counts.append(count)
            if not query_counts:
                return {
                    "is_sustained": False,
                    "reason": "no_data",
                    "days_analyzed": 0,
                    "days_above_threshold": 0,
                    "avg_queries_per_day": 0,
                    "min_queries_per_day": 0,
                    "max_queries_per_day": 0,
                    "is_spike": False,
                    "spike_ratio": 0,
                }
            avg_queries = sum(query_counts) / len(query_counts)
            min_queries = min(query_counts)
            max_queries = max(query_counts)

            # For simulations, be more lenient - just check if pattern exists
            periods_above_threshold = sum(
                1 for count in query_counts if count >= min_queries_per_period
            )
            is_sustained = (
                periods_above_threshold >= min_periods_required
                and avg_queries >= min_queries_per_period
            )

            # Check for spike (one period much higher than average)
            is_spike = (
                max_queries > avg_queries * _get_spike_threshold() if avg_queries > 0 else False
            )

            return {
                "is_sustained": is_sustained and not is_spike,
                "reason": "sustained_pattern"
                if (is_sustained and not is_spike)
                else (
                    "spike_detected"
                    if is_spike
                    else f"only_{periods_above_threshold}_periods_above_threshold"
                ),
                "days_analyzed": len(period_counts),
                "days_above_threshold": periods_above_threshold,
                "avg_queries_per_day": avg_queries,
                "min_queries_per_day": min_queries,
                "max_queries_per_day": max_queries,
                "is_spike": is_spike,
                "spike_ratio": max_queries / avg_queries if avg_queries > 0 else 0,
            }

        # Original daily analysis for production
        # Get daily query counts
        cursor.execute(
            """
            SELECT
                DATE(created_at) as query_date,
                COUNT(*) as query_count
            FROM query_stats
            WHERE table_name = %s
              AND field_name = %s
              AND created_at >= NOW() - INTERVAL '1 day' * %s
            GROUP BY DATE(created_at)
            ORDER BY query_date DESC
        """,
            (table_name, field_name, days),
        )

        daily_counts = cursor.fetchall()

        if not daily_counts or len(daily_counts) < _get_min_days_sustained():
            return {
                "is_sustained": False,
                "reason": f"Insufficient data: {len(daily_counts) if daily_counts else 0} days",
                "days_analyzed": len(daily_counts) if daily_counts else 0,
                "avg_queries_per_day": 0,
                "min_queries_per_day": 0,
                "max_queries_per_day": 0,
            }

        # Calculate statistics
        # Use safe access to prevent tuple index errors
        from src.db import safe_get_row_value

        query_counts: list[int] = []
        for row in daily_counts:
            count_val = safe_get_row_value(row, "query_count", 0) or safe_get_row_value(row, 1, 0)
            count = int(count_val) if isinstance(count_val, (int, float)) else 0
            query_counts.append(count)
        if not query_counts:
            return {
                "is_sustained": False,
                "reason": "no_data",
                "days_analyzed": 0,
                "days_above_threshold": 0,
                "avg_queries_per_day": 0,
                "min_queries_per_day": 0,
                "max_queries_per_day": 0,
                "is_spike": False,
                "spike_ratio": 0,
            }
        avg_queries = sum(query_counts) / len(query_counts)
        min_queries = min(query_counts)
        max_queries = max(query_counts)

        # Check for spike (one day much higher than average)
        is_spike = max_queries > avg_queries * _get_spike_threshold()

        # Check if pattern is sustained
        days_above_threshold = sum(
            1 for count in query_counts if count >= _get_min_queries_per_day()
        )
        is_sustained = (
            days_above_threshold >= _get_min_days_sustained()
            and not is_spike
            and avg_queries >= _get_min_queries_per_day()
        )

        return {
            "is_sustained": is_sustained,
            "reason": "sustained_pattern"
            if is_sustained
            else (
                "spike_detected"
                if is_spike
                else f"only_{days_above_threshold}_days_above_threshold"
            ),
            "days_analyzed": len(daily_counts),
            "days_above_threshold": days_above_threshold,
            "avg_queries_per_day": avg_queries,
            "min_queries_per_day": min_queries,
            "max_queries_per_day": max_queries,
            "is_spike": is_spike,
            "spike_ratio": max_queries / avg_queries if avg_queries > 0 else 0,
        }


def should_create_index_based_on_pattern(
    table_name: str, field_name: str, total_queries: int, time_window_hours: int | None = None
) -> tuple[bool, str]:
    """
    Determine if index should be created based on sustained pattern.

    Args:
        table_name: Table name
        field_name: Field name
        total_queries: Total queries in time window
        time_window_hours: Time window in hours (for simulation mode)

    Returns:
        (should_create, reason)
    """
    # Check for sustained pattern
    if time_window_hours and time_window_hours <= 24:
        # Simulation mode: use hourly analysis
        pattern = detect_sustained_pattern(
            table_name, field_name, days=1, time_window_hours=time_window_hours
        )
        # Lower threshold for simulations
        min_queries_for_simulation = 20
        if total_queries < min_queries_for_simulation:
            reason = f"Insufficient query volume: {total_queries} queries (simulation mode requires {min_queries_for_simulation})"
            return False, reason
    else:
        # Production mode: use daily analysis
        pattern = detect_sustained_pattern(
            table_name, field_name, days=_get_spike_detection_window()
        )
        # Pattern is sustained, check query volume
        if total_queries < _get_min_queries_per_day() * _get_min_days_sustained():
            reason = f"Insufficient query volume: {total_queries} queries"
            return False, reason

    if not pattern["is_sustained"]:
        reason = f"Pattern not sustained: {pattern['reason']}"
        logger.info(f"Skipping index for {table_name}.{field_name}: {reason}")

        # Alert if it's a spike
        if pattern.get("is_spike"):
            monitoring = get_monitoring()
            monitoring.alert(
                "info",
                f"Spike detected for {table_name}.{field_name} "
                f"(ratio: {pattern['spike_ratio']:.1f}x), skipping index",
            )

        return False, reason

    return True, "sustained_pattern_detected"


def get_pattern_summary(table_name: str, field_name: str) -> JSONDict:
    """Get summary of query pattern for a field"""
    pattern = detect_sustained_pattern(table_name, field_name)

    return {
        "table": table_name,
        "field": field_name,
        "pattern_analysis": pattern,
        "recommendation": "create_index" if pattern["is_sustained"] else "skip_index",
    }


def detect_multi_dimensional_pattern(
    table_name: str,
    field_names: list[str],
    query_patterns: JSONDict | None = None,
) -> JSONDict:
    """
    Detect multi-dimensional query patterns using iDistance analysis.

    Based on iDistance algorithm concepts for multi-dimensional indexing.
    Identifies queries involving multiple fields that would benefit from
    multi-dimensional indexing strategies.

    Args:
        table_name: Table name
        field_names: List of field names involved in query
        query_patterns: Optional query pattern information

    Returns:
        dict with multi-dimensional pattern analysis:
        - is_multi_dimensional: bool - Whether pattern involves multiple dimensions
        - dimensions: int - Number of dimensions
        - idistance_analysis: dict - iDistance suitability analysis
        - recommendation: str - Recommendation for index strategy
    """
    try:
        from src.algorithms.idistance import (
            analyze_idistance_suitability,
        )
        from src.algorithms.idistance import (
            detect_multi_dimensional_pattern as idistance_detect,
        )
        from src.config_loader import ConfigLoader

        config_loader = ConfigLoader()
        idistance_enabled = config_loader.get_bool("features.idistance.enabled", True)

        if not idistance_enabled:
            return {
                "is_multi_dimensional": False,
                "dimensions": 0,
                "idistance_analysis": {},
                "recommendation": "idistance_disabled",
            }

        # Use iDistance to detect multi-dimensional patterns
        if query_patterns is None:
            query_patterns = {}

        # Detect pattern using iDistance
        pattern_info = idistance_detect(table_name, field_names=field_names)

        # Analyze suitability
        idistance_analysis = analyze_idistance_suitability(
            table_name=table_name,
            field_names=field_names,
            query_patterns=query_patterns,
        )

        is_multi_dimensional = pattern_info.get("is_multi_dimensional", False)
        dimensions = pattern_info.get("dimensions", 0)

        # Determine recommendation
        if is_multi_dimensional and idistance_analysis.get("is_suitable", False):
            recommendation = "multi_dimensional_index_recommended"
        elif is_multi_dimensional:
            recommendation = "multi_dimensional_detected_but_not_optimal"
        else:
            recommendation = "single_dimensional_pattern"

        # Track algorithm usage for monitoring and analysis
        try:
            from src.algorithm_tracking import track_algorithm_usage

            track_algorithm_usage(
                table_name=table_name,
                field_name=None,  # Multi-dimensional involves multiple fields
                algorithm_name="idistance",
                recommendation={
                    "is_multi_dimensional": is_multi_dimensional,
                    "dimensions": dimensions,
                    "idistance_analysis": idistance_analysis,
                    "recommendation": recommendation,
                },
                used_in_decision=bool(
                    is_multi_dimensional and idistance_analysis.get("is_suitable", False)
                ),
            )
        except Exception as e:
            logger.warning(f"Could not track iDistance usage: {e}", exc_info=True)

        return {
            "is_multi_dimensional": is_multi_dimensional,
            "dimensions": dimensions,
            "idistance_analysis": idistance_analysis,
            "pattern_info": pattern_info,
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.debug(f"Multi-dimensional pattern detection failed: {e}")
        return {
            "is_multi_dimensional": False,
            "dimensions": 0,
            "idistance_analysis": {},
            "recommendation": "analysis_failed",
        }


def detect_temporal_pattern(
    table_name: str,
    field_name: str,
    query_patterns: JSONDict | None = None,
) -> JSONDict:
    """
    Detect temporal query patterns using Bx-tree analysis.

    Based on Bx-tree algorithm concepts for temporal/moving object indexing.
    Identifies queries with temporal characteristics that would benefit from
    Bx-tree-like temporal indexing strategies.

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Optional query pattern information

    Returns:
        dict with temporal pattern analysis:
        - is_temporal: bool - Whether pattern involves temporal queries
        - temporal_characteristics: dict - Temporal analysis details
        - bx_tree_analysis: dict - Bx-tree suitability analysis
        - recommendation: str - Recommendation for index strategy
    """
    try:
        from src.algorithms.bx_tree import (
            get_bx_tree_index_recommendation,
            should_use_bx_tree_strategy,
        )
        from src.config_loader import ConfigLoader

        config_loader = ConfigLoader()
        bx_tree_enabled = config_loader.get_bool("features.bx_tree.enabled", True)

        if not bx_tree_enabled:
            return {
                "is_temporal": False,
                "temporal_characteristics": {},
                "bx_tree_analysis": {},
                "recommendation": "bx_tree_disabled",
            }

        # Use Bx-tree to detect temporal patterns
        if query_patterns is None:
            query_patterns = {}

        # Analyze temporal suitability
        bx_tree_analysis = should_use_bx_tree_strategy(
            table_name=table_name,
            field_name=field_name,
            query_patterns=query_patterns,
        )

        # Get index recommendation
        bx_tree_recommendation = get_bx_tree_index_recommendation(
            table_name=table_name,
            field_name=field_name,
            query_patterns=query_patterns,
        )

        is_temporal = bx_tree_analysis.get("should_use_bx_tree", False)
        temporal_chars = bx_tree_analysis.get("temporal_characteristics", {})

        # Determine recommendation
        if is_temporal and bx_tree_recommendation.get("use_bx_tree_strategy", False):
            recommendation = "temporal_index_recommended"
        elif is_temporal:
            recommendation = "temporal_detected_but_not_optimal"
        else:
            recommendation = "non_temporal_pattern"

        # Track algorithm usage for monitoring and analysis
        try:
            from src.algorithm_tracking import track_algorithm_usage

            track_algorithm_usage(
                table_name=table_name,
                field_name=field_name,
                algorithm_name="bx_tree",
                recommendation={
                    "is_temporal": is_temporal,
                    "bx_tree_analysis": bx_tree_analysis,
                    "bx_tree_recommendation": bx_tree_recommendation,
                    "recommendation": recommendation,
                },
                used_in_decision=bool(
                    is_temporal and bx_tree_recommendation.get("use_bx_tree_strategy", False)
                ),
            )
        except Exception as e:
            logger.warning(f"Could not track Bx-tree usage: {e}", exc_info=True)

        return {
            "is_temporal": is_temporal,
            "temporal_characteristics": temporal_chars,
            "bx_tree_analysis": bx_tree_analysis,
            "bx_tree_recommendation": bx_tree_recommendation,
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.debug(f"Temporal pattern detection failed: {e}")
        return {
            "is_temporal": False,
            "temporal_characteristics": {},
            "bx_tree_analysis": {},
            "recommendation": "error",
        }
