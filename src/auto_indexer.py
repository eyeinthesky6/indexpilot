"""Auto-indexer - automatic index creation based on query patterns"""

import logging
import threading
import time
from typing import Any

from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from src.algorithms.cert import validate_cardinality_with_cert
from src.config_loader import ConfigLoader
from src.db import get_connection
from src.error_handler import IndexCreationError, handle_errors
from src.lock_manager import create_index_with_lock_management
from src.maintenance_window import is_in_maintenance_window, should_wait_for_maintenance_window
from src.monitoring import get_monitoring
from src.pattern_detection import should_create_index_based_on_pattern
from src.query_analyzer import (
    analyze_query_plan,
    analyze_query_plan_fast,
    measure_query_performance,
)
from src.query_patterns import detect_query_patterns, get_null_ratio
from src.rate_limiter import check_index_creation_rate_limit
from src.rollback import require_enabled
from src.stats import (
    get_field_usage_stats,
    get_table_row_count,
    get_table_size_info,
)
from src.type_definitions import JSONDict, QueryParams
from src.write_performance import can_create_index_for_table, monitor_write_performance

logger = logging.getLogger(__name__)

# Load configuration with error handling
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    # Create a minimal config loader that will use defaults
    _config_loader = ConfigLoader()


# Cost tuning configuration constants
# Loaded from config file with defaults
def _get_cost_config() -> JSONDict:
    """Get cost configuration from config file with validation"""
    config = {
        "BUILD_COST_PER_1000_ROWS": _config_loader.get_float(
            "features.auto_indexer.build_cost_per_1000_rows", 1.0
        ),
        "QUERY_COST_PER_10000_ROWS": _config_loader.get_float(
            "features.auto_indexer.query_cost_per_10000_rows", 1.0
        ),
        "MIN_QUERY_COST": _config_loader.get_float("features.auto_indexer.min_query_cost", 0.1),
        "INDEX_TYPE_COSTS": {
            "partial": _config_loader.get_float(
                "features.auto_indexer.index_type_costs.partial", 0.5
            ),
            "expression": _config_loader.get_float(
                "features.auto_indexer.index_type_costs.expression", 0.7
            ),
            "standard": _config_loader.get_float(
                "features.auto_indexer.index_type_costs.standard", 1.0
            ),
            "multi_column": _config_loader.get_float(
                "features.auto_indexer.index_type_costs.multi_column", 1.2
            ),
        },
        "MIN_SELECTIVITY_FOR_INDEX": _config_loader.get_float(
            "features.auto_indexer.min_selectivity_for_index", 0.01
        ),
        "HIGH_SELECTIVITY_THRESHOLD": _config_loader.get_float(
            "features.auto_indexer.high_selectivity_threshold", 0.5
        ),
        "MIN_IMPROVEMENT_PCT": _config_loader.get_float(
            "features.auto_indexer.min_improvement_pct", 20.0
        ),
        "SAMPLE_QUERY_RUNS": _config_loader.get_int("features.auto_indexer.sample_query_runs", 5),
        "USE_REAL_QUERY_PLANS": _config_loader.get_bool(
            "features.auto_indexer.use_real_query_plans", True
        ),
        "MIN_PLAN_COST_FOR_INDEX": _config_loader.get_float(
            "features.auto_indexer.min_plan_cost_for_index", 100.0
        ),
        # Table size thresholds
        "SMALL_TABLE_ROW_COUNT": _config_loader.get_int(
            "features.auto_indexer.small_table_row_count", 1000
        ),
        "MEDIUM_TABLE_ROW_COUNT": _config_loader.get_int(
            "features.auto_indexer.medium_table_row_count", 10000
        ),
        "SMALL_TABLE_MIN_QUERIES_PER_HOUR": _config_loader.get_int(
            "features.auto_indexer.small_table_min_queries_per_hour", 1000
        ),
        "SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT": _config_loader.get_float(
            "features.auto_indexer.small_table_max_index_overhead_pct", 50.0
        ),
        "MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT": _config_loader.get_float(
            "features.auto_indexer.medium_table_max_index_overhead_pct", 60.0
        ),
        "LARGE_TABLE_COST_REDUCTION_FACTOR": _config_loader.get_float(
            "features.auto_indexer.large_table_cost_reduction_factor", 0.8
        ),
        "MAX_WAIT_FOR_MAINTENANCE_WINDOW": _config_loader.get_int(
            "features.auto_indexer.max_wait_for_maintenance_window", 3600
        ),
        # EXPLAIN integration settings
        "EXPLAIN_USAGE_TRACKING_ENABLED": _config_loader.get_bool(
            "features.auto_indexer.explain_usage_tracking_enabled", True
        ),
        "MIN_EXPLAIN_COVERAGE_PCT": _config_loader.get_float(
            "features.auto_indexer.min_explain_coverage_pct", 70.0
        ),
    }

    # Validate logical constraints
    small_count_val = config.get("SMALL_TABLE_ROW_COUNT", 1000)
    small_count: int = (
        int(small_count_val) if isinstance(small_count_val, (int, str, float)) else 1000
    )
    medium_count_val = config.get("MEDIUM_TABLE_ROW_COUNT", 10000)
    medium_count: int = (
        int(medium_count_val) if isinstance(medium_count_val, (int, str, float)) else 10000
    )
    if small_count >= medium_count:
        logger.warning(
            f"Invalid table size thresholds: small ({small_count}) >= medium "
            f"({medium_count}), adjusting"
        )
        config["SMALL_TABLE_ROW_COUNT"] = min(1000, medium_count - 1000)

    min_selectivity_val = config.get("MIN_SELECTIVITY_FOR_INDEX", 0.01)
    min_selectivity: float = (
        float(min_selectivity_val) if isinstance(min_selectivity_val, (int, str, float)) else 0.01
    )
    high_selectivity_val = config.get("HIGH_SELECTIVITY_THRESHOLD", 0.5)
    high_selectivity: float = (
        float(high_selectivity_val) if isinstance(high_selectivity_val, (int, str, float)) else 0.5
    )
    if min_selectivity >= high_selectivity:
        logger.warning(
            f"Invalid selectivity thresholds: min ({min_selectivity}) >= high "
            f"({high_selectivity}), adjusting"
        )
        config["MIN_SELECTIVITY_FOR_INDEX"] = min(0.01, high_selectivity - 0.1)

    # Validate cost factors are positive
    for key in ["BUILD_COST_PER_1000_ROWS", "QUERY_COST_PER_10000_ROWS", "MIN_QUERY_COST"]:
        cost_val = config.get(key, 1.0)
        cost_value: float = float(cost_val) if isinstance(cost_val, (int, str, float)) else 1.0
        if cost_value <= 0:
            logger.warning(f"Invalid {key}: {cost_value}, must be positive, using default")
            config[key] = {
                "BUILD_COST_PER_1000_ROWS": 1.0,
                "QUERY_COST_PER_10000_ROWS": 1.0,
                "MIN_QUERY_COST": 0.1,
            }[key]

    # Validate percentage values are in [0, 100]
    for key in [
        "SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT",
        "MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT",
        "MIN_IMPROVEMENT_PCT",
    ]:
        pct_val = config.get(key, 50.0)
        pct_value: float = float(pct_val) if isinstance(pct_val, (int, str, float)) else 50.0
        if not (0 <= pct_value <= 100):
            logger.warning(f"Invalid {key}: {pct_value}, must be in [0, 100], clamping")
            config[key] = max(0, min(100, pct_value))

    # Validate reduction factor is in [0, 1]
    reduction_val = config.get("LARGE_TABLE_COST_REDUCTION_FACTOR", 0.8)
    reduction_factor: float = (
        float(reduction_val) if isinstance(reduction_val, (int, str, float)) else 0.8
    )
    if not (0 < reduction_factor <= 1):
        logger.warning(
            f"Invalid LARGE_TABLE_COST_REDUCTION_FACTOR: {reduction_factor}, clamping to [0.1, 1.0]"
        )
        config["LARGE_TABLE_COST_REDUCTION_FACTOR"] = max(0.1, min(1.0, reduction_factor))

    return config  # type: ignore[return-value]


# Cache config to avoid repeated lookups
_COST_CONFIG = _get_cost_config()

# EXPLAIN usage tracking for coverage monitoring
_explain_usage_stats = {
    "total_decisions": 0,
    "explain_used": 0,
    "explain_successful": 0,
    "fallback_to_estimate": 0,
}


def get_explain_usage_stats() -> dict[str, float]:
    """
    Get EXPLAIN usage statistics for coverage monitoring.

    Returns:
        dict with usage statistics and coverage percentages
    """
    total = _explain_usage_stats["total_decisions"]
    if total == 0:
        return {
            "total_decisions": 0,
            "explain_used": 0,
            "explain_successful": 0,
            "fallback_to_estimate": 0,
            "explain_coverage_pct": 0.0,
            "explain_success_rate_pct": 0.0,
            "meets_minimum_coverage": False,
        }

    explain_used = _explain_usage_stats["explain_used"]
    explain_successful = _explain_usage_stats["explain_successful"]

    coverage_pct = (explain_used / total) * 100.0
    success_rate_pct = (explain_successful / explain_used * 100.0) if explain_used > 0 else 0.0
    min_coverage_val = _COST_CONFIG.get("MIN_EXPLAIN_COVERAGE_PCT", 70.0)
    min_coverage = float(min_coverage_val) if isinstance(min_coverage_val, (int, float)) else 70.0
    meets_minimum = coverage_pct >= min_coverage

    return {
        "total_decisions": total,
        "explain_used": explain_used,
        "explain_successful": explain_successful,
        "fallback_to_estimate": _explain_usage_stats["fallback_to_estimate"],
        "explain_coverage_pct": coverage_pct,
        "explain_success_rate_pct": success_rate_pct,
        "meets_minimum_coverage": meets_minimum,
        "minimum_required_pct": min_coverage,
    }


def reset_explain_usage_stats() -> None:
    """Reset EXPLAIN usage statistics (for testing/monitoring)"""
    global _explain_usage_stats
    _explain_usage_stats = {
        "total_decisions": 0,
        "explain_used": 0,
        "explain_successful": 0,
        "fallback_to_estimate": 0,
    }


def log_explain_coverage_warning() -> None:
    """Log warning if EXPLAIN coverage drops below minimum threshold"""
    if not _COST_CONFIG.get("EXPLAIN_USAGE_TRACKING_ENABLED", True):
        return

    stats = get_explain_usage_stats()
    if not stats["meets_minimum_coverage"] and stats["total_decisions"] > 10:
        # Only warn after we have enough data points
        logger.warning(
            f"EXPLAIN coverage below minimum threshold: {stats['explain_coverage_pct']:.1f}% "
            f"(required: {stats['minimum_required_pct']:.1f}%). "
            f"Consider improving EXPLAIN integration or reducing minimum threshold."
        )


def should_create_index(
    estimated_build_cost,
    queries_over_horizon,
    extra_cost_per_query_without_index,
    table_size_info=None,
    field_selectivity=None,
    table_name=None,
    field_name=None,
    workload_info=None,
):
    """
    Decide if an index should be created based on cost-benefit analysis with workload-aware thresholds.

    ✅ INTEGRATION COMPLETE: Predictive Indexing ML Enhancement (arXiv:1901.07064)
    - Heuristic cost-benefit analysis enhanced with ML-based utility prediction
    - Uses historical data and pattern-based prediction to refine decisions
    - Combines both approaches for improved accuracy

    ✅ INTEGRATION COMPLETE: Workload-Aware Indexing (pganalyze v3 feature)
    - Read-heavy workloads: More aggressive indexing (lower thresholds)
    - Write-heavy workloads: Conservative indexing (higher thresholds)
    - Balanced workloads: Standard thresholds

    Args:
        estimated_build_cost: Estimated cost to build the index (proportional to table size)
        queries_over_horizon: Number of queries expected over the time horizon
        extra_cost_per_query_without_index: Additional cost per query without index
        table_size_info: Optional dict with table size information (from get_table_size_info)
        field_selectivity: Optional field selectivity (0.0 to 1.0)
        table_name: Optional table name (for Predictive Indexing historical data lookup)
        field_name: Optional field name (for Predictive Indexing historical data lookup)
        workload_info: Optional dict with workload analysis (read_ratio, write_ratio, workload_type)

    Returns:
        Tuple of (should_create: bool, confidence: float, reason: str)
    """
    # Convert to float to avoid Decimal * float errors
    queries_over_horizon = float(queries_over_horizon) if queries_over_horizon else 0.0
    extra_cost_per_query_without_index = (
        float(extra_cost_per_query_without_index) if extra_cost_per_query_without_index else 0.0
    )
    estimated_build_cost = float(estimated_build_cost) if estimated_build_cost else 0.0

    if queries_over_horizon == 0:
        return False, 0.0, "no_queries"

    total_query_cost_without_index = queries_over_horizon * extra_cost_per_query_without_index

    # Base decision: cost of queries without index exceeds build cost
    cost_benefit_ratio = (
        total_query_cost_without_index / estimated_build_cost if estimated_build_cost > 0 else 0
    )
    base_decision = cost_benefit_ratio > 1.0

    # Apply workload-aware adjustments
    workload_type = "balanced"  # Default
    if workload_info and isinstance(workload_info, dict):
        workload_type = workload_info.get("workload_type", "balanced")

    # Adjust cost-benefit threshold based on workload
    adjusted_threshold = 1.0  # Default threshold
    if workload_type == "read_heavy":
        # Read-heavy: More aggressive indexing (lower threshold)
        adjusted_threshold = 0.8  # Require only 0.8x benefit instead of 1.0x
        reason_modifier = "read_heavy_workload_aggressive"
    elif workload_type == "write_heavy":
        # Write-heavy: Conservative indexing (higher threshold)
        adjusted_threshold = 1.5  # Require 1.5x benefit instead of 1.0x
        reason_modifier = "write_heavy_workload_conservative"
    else:
        # Balanced workload: Standard threshold
        adjusted_threshold = 1.0
        reason_modifier = "balanced_workload"

    # Apply workload-adjusted decision
    workload_adjusted_decision = cost_benefit_ratio > adjusted_threshold

    # Calculate confidence score (0.0 to 1.0) - adjusted for workload
    base_confidence = min(1.0, cost_benefit_ratio / 2.0)  # 2x benefit = full confidence

    # Boost confidence for read-heavy workloads, reduce for write-heavy
    if workload_type == "read_heavy":
        confidence = min(1.0, base_confidence * 1.2)  # 20% boost for read-heavy
    elif workload_type == "write_heavy":
        confidence = max(0.0, base_confidence * 0.8)  # 20% reduction for write-heavy
    else:
        confidence = base_confidence

    # Final decision combines base logic with workload adjustment
    final_decision = workload_adjusted_decision
    if workload_type == "read_heavy" and cost_benefit_ratio > 0.5:
        # For read-heavy, be more lenient even if below threshold
        final_decision = True
        reason = f"{reason_modifier}_lenient"
    elif workload_type == "write_heavy" and cost_benefit_ratio < 1.2:
        # For write-heavy, be more strict even if above threshold
        final_decision = False
        reason = f"{reason_modifier}_strict"
    else:
        reason = reason_modifier

    # Apply size-based adaptive thresholds
    if table_size_info:
        row_count = table_size_info.get("row_count", 0)
        index_overhead_percent = table_size_info.get("index_overhead_percent", 0.0)

        # Small tables: Require higher query volume threshold
        small_table_row_count_val = _COST_CONFIG.get("SMALL_TABLE_ROW_COUNT", 1000)
        small_table_row_count = (
            float(small_table_row_count_val)
            if isinstance(small_table_row_count_val, (int, float))
            else 1000.0
        )
        if row_count < small_table_row_count:
            # Require minimum queries/hour equivalent for small tables
            queries_per_hour_equivalent = queries_over_horizon / 24.0  # Assuming 24h horizon
            small_table_min_queries_val = _COST_CONFIG.get("SMALL_TABLE_MIN_QUERIES_PER_HOUR", 1000)
            small_table_min_queries = (
                float(small_table_min_queries_val)
                if isinstance(small_table_min_queries_val, (int, float))
                else 1000.0
            )
            if queries_per_hour_equivalent < small_table_min_queries:
                return False, 0.0, "small_table_low_query_volume"
            # Also check if index overhead would be too high
            if index_overhead_percent > _COST_CONFIG["SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT"]:
                return False, 0.0, "small_table_high_overhead"
            # Small tables need higher benefit ratio
            if cost_benefit_ratio < 2.0:
                return False, confidence, "small_table_insufficient_benefit"

        # Medium tables: Standard thresholds
        elif row_count < _COST_CONFIG["MEDIUM_TABLE_ROW_COUNT"]:
            # Standard thresholds apply, but check overhead
            if index_overhead_percent > _COST_CONFIG["MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT"]:
                return False, 0.0, "medium_table_high_overhead"
            # Require at least 1.5x benefit for medium tables
            if cost_benefit_ratio < 1.5:
                return False, confidence, "medium_table_insufficient_benefit"

        # Large tables: Lower thresholds, more aggressive indexing
        else:
            # For large tables, be more lenient - indexes are more beneficial
            # Apply cost reduction factor for large tables
            large_table_reduction_val = _COST_CONFIG.get("LARGE_TABLE_COST_REDUCTION_FACTOR", 0.8)
            large_table_reduction = (
                float(large_table_reduction_val)
                if isinstance(large_table_reduction_val, (int, float))
                else 0.8
            )
            adjusted_build_cost = estimated_build_cost * large_table_reduction
            adjusted_ratio = (
                total_query_cost_without_index / adjusted_build_cost
                if adjusted_build_cost > 0
                else 0
            )
            if adjusted_ratio > 1.0:
                confidence = min(1.0, adjusted_ratio / 1.5)  # Boost confidence for large tables
                return True, confidence, "large_table_benefit"

    # Check field selectivity
    if field_selectivity is not None:
        if field_selectivity < _COST_CONFIG["MIN_SELECTIVITY_FOR_INDEX"]:
            # Very low selectivity - probably not worth indexing
            return False, 0.0, f"low_selectivity_{field_selectivity:.3f}"
        elif field_selectivity > _COST_CONFIG["HIGH_SELECTIVITY_THRESHOLD"]:
            # High selectivity - boost confidence
            confidence = min(1.0, confidence * 1.2)
            reason = "high_selectivity_benefit"

    # ✅ INTEGRATION: Workload-Aware Indexing
    # Adjust thresholds based on workload type (read-heavy vs write-heavy)
    workload_adjustment = 1.0  # Default: no adjustment
    workload_reason = ""
    if table_name:
        try:
            from src.workload_analysis import analyze_workload, get_workload_config

            workload_config = get_workload_config()
            if workload_config.get("enabled", True):
                # Analyze workload for this table
                workload_result = analyze_workload(
                    table_name=table_name,
                    time_window_hours=workload_config.get("time_window_hours", 24),
                )

                if workload_result and not workload_result.get("skipped"):
                    # Get table-specific workload or overall
                    tables_data = workload_result.get("tables", [])
                    table_workload = None
                    if tables_data:
                        # Find workload for this specific table
                        table_workload = next(
                            (t for t in tables_data if t.get("table_name") == table_name), None
                        )

                    # Use table-specific or overall workload
                    workload_info = table_workload or workload_result.get("overall", {})
                    workload_type = workload_info.get("workload_type", "balanced")

                    if workload_type == "read_heavy":
                        # Read-heavy: More aggressive indexing (lower threshold)
                        workload_adjustment = 0.8  # 20% reduction in required benefit
                        workload_reason = "read_heavy_workload"
                        confidence = min(1.0, confidence * 1.15)  # Boost confidence
                    elif workload_type == "write_heavy":
                        # Write-heavy: Conservative indexing (higher threshold)
                        workload_adjustment = 1.3  # 30% increase in required benefit
                        workload_reason = "write_heavy_workload"
                        confidence = max(0.0, confidence * 0.9)  # Reduce confidence
                    # Balanced: No adjustment (workload_adjustment = 1.0)
        except Exception as e:
            logger.debug(f"Workload analysis failed: {e}")

    # Apply workload adjustment to cost-benefit ratio
    if workload_adjustment != 1.0:
        adjusted_cost_benefit_ratio = cost_benefit_ratio / workload_adjustment
        if workload_adjustment < 1.0:
            # Read-heavy: Lower threshold (more aggressive)
            if adjusted_cost_benefit_ratio > 1.0:
                base_decision = True
                reason = f"{workload_reason}_{reason}"
        else:
            # Write-heavy: Higher threshold (more conservative)
            if adjusted_cost_benefit_ratio < 1.0:
                base_decision = False
                reason = f"{workload_reason}_{reason}"

    # ✅ INTEGRATION: Predictive Indexing ML Enhancement (arXiv:1901.07064)
    # Refine heuristic decision using ML-based utility prediction
    try:
        from src.algorithms.predictive_indexing import (
            predict_index_utility,
            refine_heuristic_decision,
        )

        # Use table_name and field_name if available for better historical data lookup
        utility_prediction = predict_index_utility(
            table_name=table_name or "",
            field_name=field_name or "",
            estimated_build_cost=estimated_build_cost,
            queries_over_horizon=queries_over_horizon,
            extra_cost_per_query_without_index=extra_cost_per_query_without_index,
            table_size_info=table_size_info,
            field_selectivity=field_selectivity,
        )

        # Refine decision using ML prediction
        refined_decision, refined_confidence, refined_reason = refine_heuristic_decision(
            base_decision, confidence, utility_prediction
        )

        # ✅ INTEGRATION: Constraint Programming for Index Selection
        # Apply constraint programming to validate and refine decision
        try:
            from src.algorithms.constraint_optimizer import optimize_index_with_constraints

            # Get workload info for constraint optimization
            workload_info = None
            if table_name:
                try:
                    from src.workload_analysis import analyze_workload, get_workload_config

                    workload_config = get_workload_config()
                    if workload_config.get("enabled", True):
                        workload_result = analyze_workload(
                            table_name=table_name,
                            time_window_hours=workload_config.get("time_window_hours", 24),
                        )
                        if workload_result and not workload_result.get("skipped"):
                            tables_data = workload_result.get("tables", [])
                            table_workload = next(
                                (t for t in tables_data if t.get("table_name") == table_name), None
                            )
                            workload_info = table_workload or workload_result.get("overall", {})
                except Exception:
                    pass

            # Estimate index size (simplified - would use actual size estimation)
            estimated_index_size_mb = 0.0
            if table_size_info:
                row_count_val = table_size_info.get("row_count", 0)
                row_count = int(row_count_val) if row_count_val else 0
                # Rough estimate: 10% of table size for index
                table_size_mb_val = table_size_info.get("table_size_mb", 0.0)
                table_size_mb = float(table_size_mb_val) if table_size_mb_val else 0.0
                estimated_index_size_mb = table_size_mb * 0.1

            # Calculate improvement percentage
            improvement_pct = 0.0
            if cost_benefit_ratio > 1.0:
                improvement_pct = (cost_benefit_ratio - 1.0) * 100.0  # Convert to percentage

            # Get current index counts (simplified - would query actual counts)
            current_index_count = 0
            current_table_index_count = 0
            current_storage_usage_mb = 0.0

            # Apply constraint optimization
            constraint_decision, constraint_confidence, constraint_reason, _ = (
                optimize_index_with_constraints(
                    estimated_build_cost=estimated_build_cost,
                    queries_over_horizon=queries_over_horizon,
                    extra_cost_per_query_without_index=extra_cost_per_query_without_index,
                    estimated_index_size_mb=estimated_index_size_mb,
                    improvement_pct=improvement_pct,
                    table_name=table_name,
                    field_name=field_name,
                    tenant_id=None,  # Would get from context
                    table_size_info=table_size_info,
                    workload_info=workload_info,
                    current_index_count=current_index_count,
                    current_table_index_count=current_table_index_count,
                    current_storage_usage_mb=current_storage_usage_mb,
                )
            )

            # Constraint programming overrides heuristic/ML decision if constraints violated
            if not constraint_decision:
                # Constraints violated - reject index
                return (
                    False,
                    constraint_confidence,
                    constraint_reason,
                )

            # Combine constraint confidence with refined confidence
            constraint_weight = 0.3  # 30% weight for constraint optimization
            refined_confidence = (
                refined_confidence * (1.0 - constraint_weight)
                + constraint_confidence * constraint_weight
            )

        except Exception as e:
            logger.debug(f"Constraint optimization failed: {e}")

        # ✅ INTEGRATION: XGBoost Pattern Classification (arXiv:1603.02754)
        # Enhance decision with XGBoost recommendation score
        try:
            from src.query_pattern_learning import get_index_recommendation_score

            # Get query stats for XGBoost scoring
            if table_name and field_name:
                try:
                    from src.stats import get_field_usage_stats

                    all_usage_stats = get_field_usage_stats()
                    usage_stats_list = [
                        stat
                        for stat in all_usage_stats
                        if stat.get("table_name") == table_name
                        and stat.get("field_name") == field_name
                    ]
                    usage_stats: dict[str, Any] | None = (
                        usage_stats_list[0] if usage_stats_list else None
                    )
                    if usage_stats:
                        # Convert Decimal to float to avoid type errors
                        occurrence_count = usage_stats.get("total_queries", 0)
                        if occurrence_count:
                            occurrence_count = float(occurrence_count)
                        xgboost_score = get_index_recommendation_score(
                            table_name=table_name,
                            field_name=field_name,
                            query_type="SELECT",  # Default, could be enhanced
                            avg_duration_ms=usage_stats.get("avg_duration_ms"),
                            occurrence_count=occurrence_count,
                            row_count=table_size_info.get("row_count") if table_size_info else None,
                            selectivity=field_selectivity,
                        )

                        # Combine XGBoost score with refined confidence
                        # XGBoost score (0-1) influences confidence adjustment
                        xgboost_weight = 0.2  # 20% weight for XGBoost
                        refined_confidence = (
                            refined_confidence * (1.0 - xgboost_weight)
                            + xgboost_score * xgboost_weight
                        )

                        # Adjust decision if XGBoost strongly suggests opposite
                        if xgboost_score > 0.8 and not refined_decision:
                            # XGBoost strongly recommends, but heuristic says no
                            refined_decision = True
                            refined_reason = f"xgboost_override_{refined_reason}"
                        elif xgboost_score < 0.2 and refined_decision:
                            # XGBoost strongly discourages, but heuristic says yes
                            refined_decision = False
                            refined_reason = f"xgboost_override_{refined_reason}"
                except Exception as e:
                    logger.debug(f"XGBoost scoring failed: {e}")
        except Exception as e:
            logger.debug(f"XGBoost integration failed: {e}")

        return refined_decision, refined_confidence, refined_reason
    except Exception as e:
        # If Predictive Indexing fails, fall back to heuristic decision
        logger.debug(f"Predictive Indexing enhancement failed, using heuristic: {e}")
        return base_decision, confidence, reason


# CERT validation is now in src/algorithms/cert.py for better organization


def get_field_selectivity(table_name, field_name, validate_with_cert: bool = True) -> float:
    """
    Calculate field selectivity (distinct values / total rows).

    High selectivity (many distinct values) = better index candidate
    Low selectivity (few distinct values) = less beneficial index

    CERT (Cardinality Estimation Restriction Testing) Enhancement
    - Validates selectivity estimates using CERT approach (arXiv:2306.00355)
    - Compares estimated vs actual cardinality to detect stale statistics
    - Integration: CERT validation runs after selectivity calculation
    - See: docs/research/ALGORITHM_OVERLAP_ANALYSIS.md

    Args:
        table_name: Table name
        field_name: Field name
        validate_with_cert: Whether to validate with CERT (default: True)

    Returns:
        Selectivity ratio (0.0 to 1.0), or 0.0 if unable to calculate
    """
    try:
        from src.validation import validate_field_name, validate_table_name

        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get distinct count and total rows
                query = sql.SQL("""
                    SELECT
                        COUNT(DISTINCT {}) as distinct_count,
                        COUNT(*) as total_rows
                    FROM {}
                """).format(sql.Identifier(validated_field), sql.Identifier(validated_table))
                cursor.execute(query)
                result = cursor.fetchone()

                if result and result["total_rows"] and result["total_rows"] > 0:
                    distinct_count = result["distinct_count"] or 0
                    total_rows = result["total_rows"]
                    selectivity = distinct_count / total_rows
                    estimated_selectivity = float(selectivity)

                    # CERT validation: Validate the estimate if enabled
                    if validate_with_cert:
                        cert_result = validate_cardinality_with_cert(
                            table_name, field_name, estimated_selectivity
                        )

                        # If statistics are stale, log warning
                        if cert_result.get("statistics_stale", False):
                            logger.warning(
                                f"CERT: Stale statistics detected for {table_name}.{field_name} "
                                f"(error: {cert_result.get('error_pct', 0):.1f}%)"
                            )

                        # If validation shows high error, use actual selectivity from CERT
                        if not cert_result.get("is_valid", True) and cert_result.get(
                            "actual_selectivity"
                        ):
                            actual_selectivity = cert_result["actual_selectivity"]
                            logger.debug(
                                f"CERT: Using actual selectivity {actual_selectivity:.4f} "
                                f"instead of estimated {estimated_selectivity:.4f} "
                                f"for {table_name}.{field_name}"
                            )
                            return float(actual_selectivity)

                    return estimated_selectivity
                return 0.0
            finally:
                cursor.close()
    except Exception as e:
        # Handle all exceptions gracefully - return default selectivity
        # This includes ConnectionError, PoolError, and other database errors
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "pool", "closed", "shutdown"]):
            logger.debug(f"Database connection unavailable for selectivity calculation: {e}")
        else:
            logger.debug(f"Could not calculate selectivity for {table_name}.{field_name}: {e}")
        return 0.0


def get_sample_query_for_field(
    table_name, field_name, tenant_id=None
) -> tuple[str, QueryParams] | None:
    """
    Construct a sample query for a field to use with EXPLAIN.

    Gets actual sample values from the database to avoid NULL parameter issues.

    Returns:
        Tuple of (query_string, params) or None if unable to construct
    """
    try:
        from src.validation import validate_field_name, validate_table_name

        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)

        # Check if table has tenant_id field
        has_tenant = _has_tenant_field(table_name, use_cache=True)

        # Get actual sample values from the database to avoid NULL parameter issues
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get a sample value for the field (and tenant_id if needed)
                sample_value = None
                sample_tenant_id = tenant_id

                if has_tenant:
                    if tenant_id:
                        # Get sample value for this specific tenant
                        sample_query = sql.SQL(
                            "SELECT {} FROM {} WHERE tenant_id = %s AND {} IS NOT NULL LIMIT 1"
                        ).format(
                            sql.Identifier(validated_field),
                            sql.Identifier(validated_table),
                            sql.Identifier(validated_field),
                        )
                        cursor.execute(sample_query, [tenant_id])
                    else:
                        # Get sample tenant_id and field value
                        sample_query = sql.SQL(
                            "SELECT tenant_id, {} FROM {} WHERE {} IS NOT NULL LIMIT 1"
                        ).format(
                            sql.Identifier(validated_field),
                            sql.Identifier(validated_table),
                            sql.Identifier(validated_field),
                        )
                        cursor.execute(sample_query)

                    result = cursor.fetchone()
                    if result:
                        sample_value = result.get(validated_field)
                        if not sample_tenant_id:
                            sample_tenant_id = result.get("tenant_id")
                else:
                    # Single-tenant: get sample value
                    sample_query = sql.SQL("SELECT {} FROM {} WHERE {} IS NOT NULL LIMIT 1").format(
                        sql.Identifier(validated_field),
                        sql.Identifier(validated_table),
                        sql.Identifier(validated_field),
                    )
                    cursor.execute(sample_query)
                    result = cursor.fetchone()
                    if result:
                        sample_value = result.get(validated_field)

                # If we couldn't get a sample value, use IS NOT NULL instead of = %s
                if sample_value is None:
                    if has_tenant and sample_tenant_id:
                        query = sql.SQL(
                            "SELECT * FROM {} WHERE tenant_id = %s AND {} IS NOT NULL LIMIT 1"
                        ).format(sql.Identifier(validated_table), sql.Identifier(validated_field))
                        params = [sample_tenant_id]
                    elif has_tenant:
                        query = sql.SQL(
                            "SELECT * FROM {} WHERE tenant_id IS NOT NULL AND {} IS NOT NULL LIMIT 1"
                        ).format(sql.Identifier(validated_table), sql.Identifier(validated_field))
                        params = []
                    else:
                        query = sql.SQL("SELECT * FROM {} WHERE {} IS NOT NULL LIMIT 1").format(
                            sql.Identifier(validated_table), sql.Identifier(validated_field)
                        )
                        params = []
                else:
                    # Use actual sample value
                    if has_tenant and sample_tenant_id:
                        query = sql.SQL(
                            "SELECT * FROM {} WHERE tenant_id = %s AND {} = %s LIMIT 1"
                        ).format(sql.Identifier(validated_table), sql.Identifier(validated_field))
                        params = [sample_tenant_id, sample_value]
                    elif has_tenant:
                        query = sql.SQL(
                            "SELECT * FROM {} WHERE tenant_id = %s AND {} IS NOT NULL LIMIT 1"
                        ).format(sql.Identifier(validated_table), sql.Identifier(validated_field))
                        params = [sample_tenant_id]
                    else:
                        query = sql.SQL("SELECT * FROM {} WHERE {} = %s LIMIT 1").format(
                            sql.Identifier(validated_table), sql.Identifier(validated_field)
                        )
                        params = [sample_value]

                params_tuple: QueryParams = tuple(params) if params else ()
                query_str = query.as_string(conn)
                if isinstance(query_str, str):
                    return (query_str, params_tuple)
                return None  # type: ignore[unreachable]
            finally:
                cursor.close()
    except Exception as e:
        logger.debug(f"Could not construct sample query for {table_name}.{field_name}: {e}")
        return None


def estimate_build_cost(
    table_name, field_name, row_count=None, index_type="standard", use_real_plans=True
):
    """
    Estimate the cost of building an index.

    Uses real query plan costs when available, falls back to row-count-based estimation.

    Args:
        table_name: Table name
        field_name: Field name
        row_count: Optional row count (will fetch if not provided)
        index_type: Type of index ('standard', 'partial', 'expression', 'multi_column')
        use_real_plans: Whether to use real EXPLAIN plans (default: True)

    Returns:
        Estimated build cost
    """
    if row_count is None:
        row_count = get_table_row_count(table_name)

    # Base cost: proportional to table row count
    row_count_val = row_count if isinstance(row_count, (int, float)) else 0.0
    build_cost_val = _COST_CONFIG.get("BUILD_COST_PER_1000_ROWS", 1.0)
    build_cost = build_cost_val if isinstance(build_cost_val, (int, float)) else 1.0
    base_cost = row_count_val / (1000.0 / build_cost)

    # Apply index type multiplier
    index_type_costs_val = _COST_CONFIG.get("INDEX_TYPE_COSTS", {})
    type_multiplier = 1.0
    if isinstance(index_type_costs_val, dict):
        multiplier_val = index_type_costs_val.get(index_type, 1.0)
        type_multiplier = float(multiplier_val) if isinstance(multiplier_val, (int, float)) else 1.0
    estimated_cost = base_cost * type_multiplier

    # Try to get more accurate cost from actual index creation estimate
    # PostgreSQL can estimate index build cost using EXPLAIN
    explain_used = False
    explain_successful = False
    if use_real_plans and _COST_CONFIG["USE_REAL_QUERY_PLANS"]:
        try:
            # Get a sample query to estimate index benefit
            sample_query = get_sample_query_for_field(table_name, field_name)
            if sample_query:
                query_str, params = sample_query
                # Use fast EXPLAIN first (without ANALYZE) for speed
                # Fall back to ANALYZE if needed for more accuracy
                plan = analyze_query_plan_fast(query_str, params)
                if not plan or plan.get("total_cost", 0) == 0:
                    # Fall back to ANALYZE if fast EXPLAIN didn't provide useful info
                    plan = analyze_query_plan(query_str, params, max_retries=2)
                if plan and plan.get("total_cost", 0) > 0:
                    explain_used = True
                    explain_successful = True
                    # Use plan cost as a reference, but scale by row count
                    # Index build is typically O(n log n), so we use a scaling factor
                    plan_cost_val = plan.get("total_cost", 0)
                    plan_cost = float(plan_cost_val) if plan_cost_val else 0.0
                    type_multiplier_float = float(type_multiplier) if type_multiplier else 1.0
                    # Scale plan cost to build cost (build is typically 2-5x query cost)
                    build_cost_from_plan = plan_cost * 3.0 * type_multiplier_float
                    # Use weighted average: 70% from plan, 30% from row count
                    estimated_cost = (build_cost_from_plan * 0.7) + (estimated_cost * 0.3)
                    logger.info(
                        f"EXPLAIN used for build cost estimation: {table_name}.{field_name} "
                        f"(plan_cost={plan_cost:.2f}, final_cost={estimated_cost:.2f})"
                    )
                elif plan:
                    logger.debug(
                        f"EXPLAIN plan returned but cost is 0 for {table_name}.{field_name}, "
                        "using row-count estimate"
                    )
                else:
                    logger.debug(
                        f"EXPLAIN plan analysis returned None for {table_name}.{field_name}, "
                        "using row-count estimate"
                    )
            else:
                logger.debug(
                    f"Could not generate sample query for {table_name}.{field_name}, "
                    "skipping EXPLAIN analysis"
                )
        except Exception as e:
            logger.warning(
                f"EXPLAIN failed for build cost estimation ({table_name}.{field_name}): {e}, "
                "falling back to row-count estimate"
            )
            # Fall back to row-count-based estimate

    # Track EXPLAIN usage for coverage monitoring
    if _COST_CONFIG.get("EXPLAIN_USAGE_TRACKING_ENABLED", True):
        _explain_usage_stats["total_decisions"] += 1
        if explain_used:
            _explain_usage_stats["explain_used"] += 1
            if explain_successful:
                _explain_usage_stats["explain_successful"] += 1
        else:
            _explain_usage_stats["fallback_to_estimate"] += 1

    if not explain_used:
        logger.debug(
            f"Using row-count-based build cost estimate for {table_name}.{field_name} "
            f"(EXPLAIN not used or unavailable)"
        )

    # Ensure return value is float, not Decimal
    return float(estimated_cost) if estimated_cost else 0.0


def estimate_query_cost_without_index(table_name, field_name, row_count=None, use_real_plans=True):
    """
    Estimate the cost per query without an index.

    Uses real EXPLAIN plan costs when available, falls back to row-count-based estimation.

    Args:
        table_name: Table name
        field_name: Field name
        row_count: Optional row count (will fetch if not provided)
        use_real_plans: Whether to use real query plans (default: True)

    Returns:
        Estimated cost per query without index
    """
    if row_count is None:
        row_count = get_table_row_count(table_name)

    # Base cost: full table scan cost proportional to row count
    min_query_cost_val = _COST_CONFIG.get("MIN_QUERY_COST", 0.1)
    min_query_cost = min_query_cost_val if isinstance(min_query_cost_val, (int, float)) else 0.1
    query_cost_per_10k_val = _COST_CONFIG.get("QUERY_COST_PER_10000_ROWS", 1.0)
    query_cost_per_10k = (
        query_cost_per_10k_val if isinstance(query_cost_per_10k_val, (int, float)) else 1.0
    )
    divisor = 10000.0 / query_cost_per_10k if query_cost_per_10k > 0 else 10000.0
    base_cost = max(min_query_cost, float(row_count) / divisor)

    # Try to get real cost from EXPLAIN plan
    explain_used = False
    explain_successful = False
    if use_real_plans and _COST_CONFIG["USE_REAL_QUERY_PLANS"]:
        try:
            # Get sample queries from stats to analyze
            from src.stats import get_query_stats

            query_stats = get_query_stats(
                time_window_hours=24, table_name=table_name, field_name=field_name
            )

            if query_stats and len(query_stats) > 0 and isinstance(query_stats[0], dict):
                # Get a representative tenant_id for sample query
                tenant_id = query_stats[0].get("tenant_id")
                sample_query = get_sample_query_for_field(table_name, field_name, tenant_id)

                if sample_query:
                    query_str, params = sample_query
                    # Use fast EXPLAIN first, fall back to ANALYZE if needed
                    plan = analyze_query_plan_fast(query_str, params)
                    if not plan or plan.get("total_cost", 0) == 0:
                        # Fall back to ANALYZE for actual execution times
                        plan = analyze_query_plan(query_str, params, max_retries=2)

                    if plan:
                        plan_cost_val = plan.get("total_cost", 0)
                        plan_cost = float(plan_cost_val) if plan_cost_val else 0.0
                        has_seq_scan = plan.get("has_seq_scan", False)
                        actual_time_val = plan.get("actual_time_ms", 0)
                        actual_time = float(actual_time_val) if actual_time_val else 0.0

                        # If we have a sequential scan with high cost, use that
                        min_plan_cost_val = _COST_CONFIG.get("MIN_PLAN_COST_FOR_INDEX", 100.0)
                        min_plan_cost = (
                            float(min_plan_cost_val)
                            if isinstance(min_plan_cost_val, (int, float))
                            else 100.0
                        )
                        if has_seq_scan and plan_cost > min_plan_cost:
                            explain_used = True
                            explain_successful = True
                            # Use actual plan cost, but convert to our cost units
                            # Plan costs are in PostgreSQL cost units, we normalize them
                            # Typical seq scan cost: ~0.01 per row, so divide by 100
                            normalized_cost = plan_cost / 100.0
                            # Use weighted average: 80% from plan, 20% from row count
                            base_cost = (normalized_cost * 0.8) + (base_cost * 0.2)

                            # Also factor in actual execution time if available
                            if actual_time > 0:
                                # Convert ms to cost units (rough approximation)
                                time_based_cost = actual_time / 10.0  # 10ms = 1 cost unit
                                # Blend time and cost estimates
                                base_cost = (base_cost * 0.6) + (time_based_cost * 0.4)

                            logger.info(
                                f"EXPLAIN used for query cost estimation: {table_name}.{field_name} "
                                f"(plan_cost={plan_cost:.2f}, seq_scan={has_seq_scan}, "
                                f"actual_time={actual_time:.2f}ms, final_cost={base_cost:.2f})"
                            )
                        elif plan_cost > 0:
                            logger.debug(
                                f"EXPLAIN plan cost ({plan_cost:.2f}) below threshold "
                                f"({min_plan_cost:.2f}) or no seq scan for {table_name}.{field_name}"
                            )
                    elif plan is None:
                        logger.debug(
                            f"EXPLAIN plan analysis returned None for {table_name}.{field_name}"
                        )
                else:
                    logger.debug(
                        f"Could not generate sample query for {table_name}.{field_name} "
                        f"(tenant_id={tenant_id})"
                    )
            else:
                logger.debug(
                    f"No query stats available for EXPLAIN analysis: {table_name}.{field_name}"
                )
        except Exception as e:
            logger.warning(
                f"EXPLAIN failed for query cost estimation ({table_name}.{field_name}): {e}, "
                "falling back to row-count estimate"
            )
            # Fall back to row-count-based estimate

    # Track EXPLAIN usage for coverage monitoring
    if _COST_CONFIG.get("EXPLAIN_USAGE_TRACKING_ENABLED", True):
        _explain_usage_stats["total_decisions"] += 1
        if explain_used:
            _explain_usage_stats["explain_used"] += 1
            if explain_successful:
                _explain_usage_stats["explain_successful"] += 1
        else:
            _explain_usage_stats["fallback_to_estimate"] += 1

    if not explain_used:
        logger.debug(
            f"Using row-count-based query cost estimate for {table_name}.{field_name} "
            f"(EXPLAIN not used or unavailable)"
        )

    # Factor in field selectivity
    selectivity = get_field_selectivity(table_name, field_name)
    if selectivity > 0:
        # Low selectivity fields (e.g., boolean flags) have lower query cost
        # High selectivity fields have higher query cost (more rows to scan)
        # Adjust cost based on selectivity
        min_selectivity_val = _COST_CONFIG.get("MIN_SELECTIVITY_FOR_INDEX", 0.01)
        min_selectivity = (
            min_selectivity_val if isinstance(min_selectivity_val, (int, float)) else 0.01
        )
        if selectivity < min_selectivity:
            # Very low selectivity - queries are cheap (few distinct values)
            base_cost *= 0.5
        else:
            high_selectivity_threshold_val = _COST_CONFIG.get("HIGH_SELECTIVITY_THRESHOLD", 0.5)
            high_selectivity_threshold = (
                high_selectivity_threshold_val
                if isinstance(high_selectivity_threshold_val, (int, float))
                else 0.5
            )
            if selectivity > high_selectivity_threshold:
                # High selectivity - queries are expensive (many distinct values)
                base_cost *= 1.2

    # Ensure return value is float, not Decimal
    return float(base_cost) if base_cost else 0.0


def get_optimization_strategy(table_name, row_count, table_size_info=None):
    """
    Get optimization strategy based on table size with size-aware thresholds.

    Args:
        table_name: Name of the table
        row_count: Number of rows in the table
        table_size_info: Optional dict with table size information

    Returns:
        dict: Strategy with primary/secondary approaches and thresholds
    """
    # Get table size info if not provided
    if table_size_info is None:
        table_size_info = get_table_size_info(table_name)

    if row_count < _COST_CONFIG["SMALL_TABLE_ROW_COUNT"]:
        # Small tables: Very selective indexing
        return {
            "primary": "caching",
            "secondary": "micro_indexes",
            "skip_traditional_indexes": True,
            "min_query_threshold": _COST_CONFIG["SMALL_TABLE_MIN_QUERIES_PER_HOUR"],
            "max_index_overhead": _COST_CONFIG["SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT"],
            "size_category": "small",
        }
    elif row_count < _COST_CONFIG["MEDIUM_TABLE_ROW_COUNT"]:
        # Medium tables: Standard approach
        return {
            "primary": "micro_indexes",
            "secondary": "caching",
            "skip_traditional_indexes": False,
            "min_query_threshold": 100,  # Standard threshold
            "max_index_overhead": _COST_CONFIG["MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT"],
            "size_category": "medium",
        }
    else:
        # Large tables: More aggressive indexing
        return {
            "primary": "indexing",
            "secondary": "caching",
            "skip_traditional_indexes": False,
            "min_query_threshold": 50,  # Lower threshold for large tables
            "max_index_overhead": 80.0,  # Can tolerate higher overhead
            "size_category": "large",
        }


# Cache for tenant field detection (performance optimization)
_tenant_field_cache: dict[str, bool] = {}
_tenant_field_cache_lock = threading.Lock()


def _has_tenant_field(table_name: str, use_cache: bool = True) -> bool:
    """
    Check if table has a tenant_id field (or similar tenant field).

    Uses caching to avoid repeated database queries.

    Args:
        table_name: Table name to check
        use_cache: Whether to use cache (default: True)

    Returns:
        True if table has tenant field, False otherwise
    """
    # Check cache first
    if use_cache:
        with _tenant_field_cache_lock:
            if table_name in _tenant_field_cache:
                return _tenant_field_cache[table_name]

    result = False
    try:
        from src.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Check genome_catalog for tenant_id or similar fields
                cursor.execute(
                    """
                    SELECT field_name
                    FROM genome_catalog
                    WHERE table_name = %s
                      AND (field_name = 'tenant_id' OR field_name LIKE 'tenant_%')
                """,
                    (table_name,),
                )
                result = cursor.fetchone() is not None
            finally:
                cursor.close()
    except Exception:
        # If genome_catalog not available, try to check actual table
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = %s
                          AND (column_name = 'tenant_id' OR column_name LIKE 'tenant_%')
                    """,
                        (table_name,),
                    )
                    result = cursor.fetchone() is not None
                finally:
                    cursor.close()
        except Exception:
            # Default: assume no tenant field (single-tenant or non-multi-tenant)
            result = False

    # Cache result
    if use_cache:
        with _tenant_field_cache_lock:
            _tenant_field_cache[table_name] = result

    return result


def clear_tenant_field_cache():
    """Clear the tenant field cache (useful after schema changes)"""
    global _tenant_field_cache
    with _tenant_field_cache_lock:
        _tenant_field_cache.clear()


def create_smart_index(table_name, field_name, row_count, query_patterns, _strategy=None):
    """
    Create optimized index based on query patterns and table size.
    Returns SQL for creating the index and index type.

    Automatically detects if table has tenant_id field and creates appropriate index.

    Args:
        table_name: Table name
        field_name: Field name
        row_count: Number of rows in table
        query_patterns: Dict with query pattern information
        _strategy: Optimization strategy (reserved for future use)

    Returns:
        Tuple of (index_sql, index_name, index_type)
    """
    quoted_table = f'"{table_name}"'
    quoted_field = f'"{field_name}"'

    # Check if table has tenant field
    has_tenant = _has_tenant_field(table_name)

    # Check for LIKE queries (pattern matching)
    has_like = query_patterns.get("has_like", False)

    # Check NULL ratio
    null_ratio = get_null_ratio(table_name, field_name)

    # Try EXPLAIN-based index type selection first (if enabled)
    use_explain_selection = _COST_CONFIG.get("USE_EXPLAIN_FOR_INDEX_TYPE", False)
    selected_index_type_info = None

    if use_explain_selection:
        try:
            from src.index_type_selection import select_optimal_index_type

            # Get sample query for analysis
            sample_query = None
            try:
                from src.stats import get_query_stats

                query_stats = get_query_stats(
                    time_window_hours=24, table_name=table_name, field_name=field_name
                )
                if query_stats and len(query_stats) > 0 and isinstance(query_stats[0], dict):
                    tenant_id = query_stats[0].get("tenant_id")
                    sample_query = get_sample_query_for_field(table_name, field_name, tenant_id)
            except Exception:
                pass

            selected_index_type_info = select_optimal_index_type(
                table_name=table_name,
                field_name=field_name,
                query_patterns=query_patterns,
                sample_query=sample_query,
            )

            if selected_index_type_info and selected_index_type_info.get("confidence", 0) > 0.6:
                # Use EXPLAIN-selected index type
                optimal_type = selected_index_type_info.get("index_type", "btree")
                logger.info(
                    f"EXPLAIN selected {optimal_type} index type for {table_name}.{field_name} "
                    f"(confidence: {selected_index_type_info.get('confidence', 0):.2f})"
                )
        except Exception as e:
            logger.debug(f"EXPLAIN-based index type selection failed: {e}, using heuristics")

    # Determine index type based on patterns and EXPLAIN analysis
    if has_like and row_count < _COST_CONFIG["MEDIUM_TABLE_ROW_COUNT"]:
        # Expression index for text search on small-medium tables
        index_type = "expression"
        if has_tenant:
            index_name = f"idx_{table_name}_{field_name}_lower_tenant"
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}(tenant_id, LOWER({quoted_field}))
            """
        else:
            index_name = f"idx_{table_name}_{field_name}_lower"
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}(LOWER({quoted_field}))
            """
        return index_sql, index_name, index_type
    elif null_ratio > 0.5 and row_count < _COST_CONFIG["MEDIUM_TABLE_ROW_COUNT"]:
        # Partial index: only index non-null values
        index_type = "partial"
        if has_tenant:
            index_name = f"idx_{table_name}_{field_name}_partial_tenant"
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}(tenant_id, {quoted_field})
                WHERE {quoted_field} IS NOT NULL
            """
        else:
            index_name = f"idx_{table_name}_{field_name}_partial"
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}({quoted_field})
                WHERE {quoted_field} IS NOT NULL
            """
        return index_sql, index_name, index_type
    else:
        # Standard index - use EXPLAIN-selected type if available
        if selected_index_type_info and selected_index_type_info.get("confidence", 0) > 0.6:
            optimal_type = selected_index_type_info.get("index_type", "btree")
            from src.index_type_selection import generate_index_sql_with_type

            index_sql, index_name = generate_index_sql_with_type(
                table_name=table_name,
                field_name=field_name,
                index_type=optimal_type,
                has_tenant=has_tenant,
            )
            index_type = f"{optimal_type}_standard" if has_tenant else optimal_type
            return index_sql, index_name, index_type
        else:
            # Fall back to default B-tree
            index_type = "multi_column" if has_tenant else "standard"
            if has_tenant:
                index_name = f"idx_{table_name}_{field_name}_tenant"
                index_sql = f"""
                    CREATE INDEX IF NOT EXISTS "{index_name}"
                    ON {quoted_table}(tenant_id, {quoted_field})
                """
            else:
                index_name = f"idx_{table_name}_{field_name}"
                index_sql = f"""
                    CREATE INDEX IF NOT EXISTS "{index_name}"
                    ON {quoted_table}({quoted_field})
                """
            return index_sql, index_name, index_type


@require_enabled
@handle_errors("analyze_and_create_indexes", default_return={"created": [], "skipped": []})
def analyze_and_create_indexes(time_window_hours=24, min_query_threshold=100):
    """
    Analyze query stats and create indexes for fields that meet the threshold.

    Args:
        time_window_hours: Time window to analyze queries
        min_query_threshold: Minimum number of queries required to consider indexing
    """
    created_indexes = []
    skipped_indexes = []

    # Get field usage statistics
    print(f"  Analyzing query stats from last {time_window_hours} hours...")
    field_stats = get_field_usage_stats(time_window_hours)
    print(f"  Found {len(field_stats)} field patterns to analyze")

    # Also check for foreign keys without indexes (high priority)
    fk_suggestions = []
    try:
        from src.foreign_key_suggestions import suggest_foreign_key_indexes

        if _config_loader.get_bool("features.foreign_key_suggestions.enabled", True):
            fk_suggestions = suggest_foreign_key_indexes(schema_name="public")
            if fk_suggestions:
                print(f"  Found {len(fk_suggestions)} foreign keys without indexes (high priority)")
                # Add FK suggestions to field_stats for processing
                for fk_suggestion in fk_suggestions:
                    # Parse table name from "schema.table" format
                    table_full = fk_suggestion["table"]
                    if "." in table_full:
                        _, table = table_full.split(".", 1)
                    else:
                        table = table_full

                    # Get the FK column (first non-tenant column)
                    columns = fk_suggestion["columns"]
                    fk_column = columns[-1] if columns else None

                    if fk_column:
                        # Add as a high-priority stat entry
                        field_stats.append(
                            {
                                "table_name": table,
                                "field_name": fk_column,
                                "query_count": 1000,  # High priority - assume frequent JOINs
                                "avg_duration_ms": 50.0,  # Assume moderate query time
                                "is_foreign_key": True,
                                "fk_suggestion": fk_suggestion,
                            }
                        )
    except Exception as e:
        logger.debug(f"Could not get foreign key suggestions: {e}")

    if not field_stats:
        print("  No query statistics found. Skipping index creation.")
        return {"created": [], "skipped": []}

    # Validate all table/field names before processing
    from src.validation import validate_field_name, validate_table_name

    validated_stats = []
    for stat in field_stats:
        try:
            # Ensure stat is a dict (RealDictCursor row) and has required fields
            if not isinstance(stat, dict):
                logger.warning(f"Skipping invalid stat type: {type(stat)}")
                continue
            if "table_name" not in stat or "field_name" not in stat:
                logger.warning(f"Skipping stat missing required fields: {stat.keys()}")
                continue
            table_name = validate_table_name(stat["table_name"])
            field_name = validate_field_name(stat["field_name"], table_name)
            stat["table_name"] = table_name
            stat["field_name"] = field_name
            validated_stats.append(stat)
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Skipping invalid stat: {e}")
            continue

    if not validated_stats:
        print("  No valid query statistics found after validation.")
        return {"created": [], "skipped": []}

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            for stat in validated_stats:
                table_name = stat["table_name"]
                field_name = stat["field_name"]
                # Convert to float immediately to avoid Decimal * float errors
                total_queries = float(stat["total_queries"]) if stat.get("total_queries") else 0.0

                # Check if any index already exists for this field
                # (could be standard, partial, or expression index)
                # Check if table has tenant field to determine index name patterns
                has_tenant = _has_tenant_field(table_name)

                if has_tenant:
                    # Multi-tenant index patterns
                    standard_index = f"idx_{table_name}_{field_name}_tenant"
                    partial_index = f"idx_{table_name}_{field_name}_partial_tenant"
                    expr_index = f"idx_{table_name}_{field_name}_lower_tenant"
                else:
                    # Single-tenant index patterns
                    standard_index = f"idx_{table_name}_{field_name}"
                    partial_index = f"idx_{table_name}_{field_name}_partial"
                    expr_index = f"idx_{table_name}_{field_name}_lower"

                # Validate table name to prevent SQL injection
                from src.validation import validate_table_name

                validated_table_name = validate_table_name(table_name)

                # Use PostgreSQL-specific query (could be abstracted via adapter in future)
                cursor.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM pg_indexes
                    WHERE tablename = %s
                      AND (indexname = %s OR indexname = %s OR indexname = %s
                           OR indexdef LIKE %s)
                """,
                    (
                        validated_table_name,
                        standard_index,
                        partial_index,
                        expr_index,
                        f"%{field_name}%",
                    ),
                )
                result = cursor.fetchone()
                exists = (
                    result.get("count", 0) > 0 if result and isinstance(result, dict) else False
                )

                if exists:
                    skipped_indexes.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "queries": total_queries,
                            "reason": "already_exists",
                        }
                    )
                    continue

                # Check if we can create index (write performance limits)
                can_create, limit_reason = can_create_index_for_table(table_name)
                if not can_create:
                    skipped_indexes.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "queries": total_queries,
                            "reason": limit_reason,
                        }
                    )
                    continue

                # Check for sustained pattern (not a spike)
                pattern_ok, pattern_reason = should_create_index_based_on_pattern(
                    table_name, field_name, int(total_queries), time_window_hours=time_window_hours
                )
                if not pattern_ok:
                    skipped_indexes.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "queries": total_queries,
                            "reason": pattern_reason,
                        }
                    )
                    continue

                # Check rate limiting (security: prevent abuse)
                rate_allowed, retry_after = check_index_creation_rate_limit(table_name)
                if not rate_allowed:
                    skipped_indexes.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "queries": total_queries,
                            "reason": f"rate_limit_exceeded (retry after {retry_after:.1f}s)",
                        }
                    )
                    continue

                # Check maintenance window (unless urgent)
                if not is_in_maintenance_window():
                    should_wait, wait_seconds = should_wait_for_maintenance_window(
                        "index_creation", max_wait_hours=6.0
                    )
                    max_wait_val = _COST_CONFIG.get("MAX_WAIT_FOR_MAINTENANCE_WINDOW", 3600)
                    max_wait = max_wait_val if isinstance(max_wait_val, (int, float)) else 3600
                    if should_wait and wait_seconds > max_wait:
                        skipped_indexes.append(
                            {
                                "table": table_name,
                                "field": field_name,
                                "queries": total_queries,
                                "reason": f"outside_maintenance_window (wait {wait_seconds / 3600:.1f}h)",
                            }
                        )
                        continue

                # Get table size information and strategy
                row_count = get_table_row_count(table_name)
                table_size_info = get_table_size_info(table_name)
                # Ensure row_count is int for strategy
                row_count = int(row_count) if row_count else 0
                strategy = get_optimization_strategy(table_name, row_count, table_size_info)

                # Apply size-based query threshold
                min_query_threshold = strategy.get("min_query_threshold", min_query_threshold)
                if total_queries < min_query_threshold:
                    skipped_indexes.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "queries": total_queries,
                            "reason": f"below_size_based_threshold (required: {min_query_threshold}, size_category: {strategy.get('size_category', 'unknown')})",
                        }
                    )
                    continue

                # Check index overhead limit
                max_index_overhead = strategy.get("max_index_overhead", 100.0)
                current_overhead = table_size_info.get("index_overhead_percent", 0.0)
                if current_overhead >= max_index_overhead:
                    skipped_indexes.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "queries": total_queries,
                            "reason": f"index_overhead_limit_exceeded (current: {current_overhead:.1f}%, max: {max_index_overhead:.1f}%)",
                        }
                    )
                    continue

                # Detect query patterns
                query_patterns = detect_query_patterns(table_name, field_name, time_window_hours)

                # Get field selectivity for better cost estimation
                field_selectivity = get_field_selectivity(table_name, field_name)

                # Determine index type based on patterns (preview)
                strategy = get_optimization_strategy(table_name, row_count, table_size_info)
                _preview_index_sql, _preview_index_name, preview_index_type = create_smart_index(
                    table_name, field_name, row_count, query_patterns, strategy
                )

                # Estimate costs with index type consideration
                build_cost = estimate_build_cost(
                    table_name, field_name, row_count, preview_index_type
                )
                query_cost_without_index = estimate_query_cost_without_index(
                    table_name, field_name, row_count, use_real_plans=True
                )

                # Get tenant-specific config if available
                tenant_id = None
                if isinstance(stat, dict):
                    tenant_id = stat.get("tenant_id")

                tenant_config = None
                if tenant_id:
                    try:
                        from src.per_tenant_config import get_tenant_index_config

                        tenant_config = get_tenant_index_config(tenant_id)
                    except Exception as e:
                        logger.debug(f"Could not get tenant config: {e}")

                # Adjust thresholds based on tenant config (if needed in future)
                # min_query_threshold_adjusted = min_query_threshold
                # if tenant_config:
                #     min_query_threshold_adjusted = tenant_config.get(
                #         "min_query_threshold", min_query_threshold
                #     )

                # Check if tenant has reached max indexes per table
                if tenant_config:
                    max_indexes = tenant_config.get("max_indexes_per_table", 10)
                    try:
                        with get_connection() as conn:
                            cursor = conn.cursor(cursor_factory=RealDictCursor)
                            try:
                                cursor.execute(
                                    """
                                    SELECT COUNT(*) as index_count
                                    FROM pg_indexes
                                    WHERE schemaname = 'public'
                                      AND tablename = %s
                                    """,
                                    (table_name,),
                                )
                                result = cursor.fetchone()
                                current_index_count = result["index_count"] if result else 0

                                if current_index_count >= max_indexes:
                                    logger.info(
                                        f"Skipping index for {table_name}: "
                                        f"tenant {tenant_id} has reached max indexes ({current_index_count}/{max_indexes})"
                                    )
                                    skipped_indexes.append(
                                        {
                                            "table": table_name,
                                            "field": field_name,
                                            "reason": f"max_indexes_per_table_reached_{current_index_count}_{max_indexes}",
                                        }
                                    )
                                    continue
                            finally:
                                cursor.close()
                    except Exception as e:
                        logger.debug(f"Could not check tenant index count: {e}")

                # Decide if we should create the index (with size-aware analysis + Predictive Indexing)
                should_create, confidence, reason = should_create_index(
                    build_cost,
                    total_queries,
                    query_cost_without_index,
                    table_size_info,
                    field_selectivity,
                    table_name=table_name,
                    field_name=field_name,
                )

                # For small tables, prefer micro-indexes even if traditional index would be skipped
                if strategy["skip_traditional_indexes"] and should_create:
                    # Still create, but use micro-index
                    should_create = True

                if should_create:
                    # ✅ INTEGRATION: Foreign Key Suggestions
                    # Check if this field is a foreign key that needs an index
                    try:
                        from src.foreign_key_suggestions import (
                            find_foreign_keys_without_indexes,
                            is_foreign_key_suggestions_enabled,
                        )

                        if is_foreign_key_suggestions_enabled():
                            fk_without_indexes = find_foreign_keys_without_indexes()
                            is_fk = any(
                                fk.get("table") == table_name
                                and fk.get("column") == field_name
                                for fk in fk_without_indexes
                            )
                            if is_fk:
                                # Boost confidence for foreign key indexes
                                confidence = min(1.0, confidence * 1.2)
                                reason = f"foreign_key_index_{reason}"
                                logger.info(
                                    f"Field {table_name}.{field_name} is a foreign key - "
                                    f"boosting index recommendation confidence"
                                )
                    except Exception as e:
                        logger.debug(f"Foreign key suggestion check failed: {e}")

                    # Check if we're in advisory mode (advisory = log only, apply = create indexes)
                    mode = _config_loader.get("features.auto_indexer.mode", "apply")
                    mode = mode.lower() if isinstance(mode, str) else "apply"

                    is_advisory_mode = mode == "advisory"

                    # Monitor write performance before creating
                    write_stats = monitor_write_performance(table_name)

                    # Measure performance before index creation (if we have sample queries)
                    before_perf = None
                    sample_query = None
                    try:
                        from src.stats import get_query_stats

                        query_stats = get_query_stats(
                            time_window_hours=24, table_name=table_name, field_name=field_name
                        )
                        if (
                            query_stats
                            and len(query_stats) > 0
                            and isinstance(query_stats[0], dict)
                        ):
                            # Get a representative tenant_id
                            tenant_id = query_stats[0].get("tenant_id")
                            sample_query = get_sample_query_for_field(
                                table_name, field_name, tenant_id
                            )

                            if sample_query:
                                query_str, params = sample_query
                                sample_runs_val = _COST_CONFIG.get("SAMPLE_QUERY_RUNS", 5)
                                sample_runs = (
                                    int(sample_runs_val)
                                    if isinstance(sample_runs_val, (int, float))
                                    else 5
                                )
                                before_perf = measure_query_performance(
                                    query_str, params, num_runs=sample_runs
                                )
                                # Note: before_plan analysis removed as it was unused
                    except Exception as e:
                        logger.debug(f"Could not measure before performance: {e}")

                    # Create smart index based on patterns and size
                    index_sql, index_name, index_type = create_smart_index(
                        table_name, field_name, row_count, query_patterns, strategy
                    )

                    # Check approval workflow if enabled (after index name is generated)
                    approval_result = None
                    if not is_advisory_mode:
                        try:
                            from src.approval_workflow import create_approval_request

                            # Get tenant_id if available
                            tenant_id = None
                            if isinstance(stat, dict):
                                tenant_id = stat.get("tenant_id")

                            approval_result = create_approval_request(
                                index_name=index_name,
                                table_name=table_name,
                                field_name=field_name,
                                index_sql=index_sql,
                                reason=reason,
                                confidence=confidence,
                                tenant_id=tenant_id,
                            )

                            if not approval_result.get("approved", True):
                                # Approval required - skip creation
                                logger.info(
                                    f"Index {index_name} requires approval (request_id: {approval_result.get('request_id')})"
                                )
                                skipped_indexes.append(
                                    {
                                        "table": table_name,
                                        "field": field_name,
                                        "index_name": index_name,
                                        "reason": "awaiting_approval",
                                        "request_id": approval_result.get("request_id"),
                                    }
                                )
                                continue
                        except Exception as e:
                            logger.debug(f"Approval workflow check failed: {e}")
                            # Continue with creation if approval system fails

                    if is_advisory_mode:
                        # Advisory mode: log candidate index but don't create it
                        print(
                            f"  [ADVISORY] Candidate index {index_name} on {table_name}.{field_name} "
                            f"(type: {index_type}, confidence: {confidence:.2f})..."
                        )

                        # Log candidate index to mutation_log
                        from src.audit import log_audit_event

                        log_audit_event(
                            "CREATE_INDEX",
                            table_name=table_name,
                            field_name=field_name,
                            details={
                                "index_name": index_name,
                                "index_type": index_type,
                                "index_sql": index_sql,
                                "build_cost_estimate": build_cost,
                                "queries_analyzed": total_queries,
                                "query_cost_without_index": query_cost_without_index,
                                "row_count": row_count,
                                "field_selectivity": field_selectivity,
                                "confidence": confidence,
                                "reason": reason,
                                "strategy": strategy["primary"],
                                "before_perf_ms": before_perf["median_ms"] if before_perf else None,
                                "mode": "advisory",
                                "estimated_improvement": f"{confidence * 100:.1f}%",
                            },
                            severity="info",
                        )

                        # Add to created_indexes list (but mark as advisory)
                        created_indexes.append(
                            {
                                "table": table_name,
                                "field": field_name,
                                "index_name": index_name,
                                "index_type": index_type,
                                "queries": total_queries,
                                "build_cost": build_cost,
                                "confidence": confidence,
                                "field_selectivity": field_selectivity,
                                "mode": "advisory",
                                "write_overhead_estimate": write_stats.get(
                                    "estimated_write_overhead", 0
                                ),
                            }
                        )
                        write_overhead_val = write_stats.get("estimated_write_overhead", 0)
                        write_overhead = (
                            float(write_overhead_val)
                            if isinstance(write_overhead_val, (int, float))
                            else 0.0
                        )
                        print(
                            f"[ADVISORY] Candidate index {index_name} on {table_name}.{field_name} "
                            f"(type: {index_type}, queries: {total_queries}, "
                            f"build_cost: {build_cost:.2f}, confidence: {confidence:.2f}, "
                            f"write overhead: {write_overhead * 100:.1f}%) - "
                            f"Logged to mutation_log. Set mode='apply' to create indexes."
                        )
                        continue  # Skip actual index creation

                    # Apply mode: actually create the index
                    # Check storage budget before creating
                    try:
                        from src.storage_budget import check_storage_budget

                        # Estimate index size (rough: ~30% of table size for standard index)
                        # Ensure row_count is int/float for multiplication
                        row_count_val = int(row_count) if row_count else 0
                        estimated_index_size_mb = (row_count_val * 0.00003) if row_count_val else 1.0
                        budget_check = check_storage_budget(
                            tenant_id=None,  # Check total budget (can be enhanced for per-tenant)
                            estimated_index_size_mb=estimated_index_size_mb,
                        )

                        if not budget_check.get("allowed", True):
                            logger.warning(
                                f"Skipping index {index_name}: {budget_check.get('reason', 'storage budget exceeded')}"
                            )
                            skipped_indexes.append(
                                {
                                    "table": table_name,
                                    "field": field_name,
                                    "index_name": index_name,
                                    "reason": budget_check.get("reason", "storage_budget_exceeded"),
                                    "budget_check": budget_check,
                                }
                            )
                            continue
                        elif budget_check.get("warning", False):
                            logger.warning(
                                f"Storage budget warning for {index_name}: {budget_check.get('reason', 'approaching limit')}"
                            )
                    except Exception as e:
                        logger.debug(f"Could not check storage budget: {e}")
                        # Continue with index creation if budget check fails

                    try:
                        print(
                            f"  Creating index {index_name} on {table_name}.{field_name} "
                            f"(type: {index_type}, confidence: {confidence:.2f})..."
                        )

                        # Check circuit breaker (Phase 3)
                        try:
                            from src.adaptive_safeguards import (
                                check_circuit_breaker,
                                record_circuit_failure,
                                record_circuit_success,
                            )

                            circuit_breaker_name = f"index_creation_{table_name}"
                            if not check_circuit_breaker(circuit_breaker_name):
                                logger.warning(
                                    f"Circuit breaker open for {circuit_breaker_name}, skipping index creation"
                                )
                                skipped_indexes.append(
                                    {
                                        "table": table_name,
                                        "field": field_name,
                                        "queries": total_queries,
                                        "reason": "circuit_breaker_open",
                                    }
                                )
                                continue
                        except Exception as e:
                            logger.debug(f"Circuit breaker check failed: {e}")

                        # Check canary deployment (Phase 3)
                        try:
                            from src.adaptive_safeguards import create_canary_deployment

                            canary_enabled = (
                                _config_loader.get_bool("features.canary_deployment.enabled", False)
                                if _config_loader
                                else False
                            )
                            if canary_enabled:
                                deployment_id = f"{index_name}_{int(time.time())}"
                                _canary_deployment = create_canary_deployment(
                                    deployment_id=deployment_id,
                                    index_name=index_name,
                                    table_name=table_name,
                                    canary_percent=10.0,  # 10% traffic
                                )
                                # Canary deployment created but not yet used in index creation flow
                        except Exception as e:
                            logger.debug(f"Canary deployment check failed: {e}")

                        # Track index creation attempt
                        try:
                            from src.safeguard_monitoring import track_index_creation_attempt

                            track_index_creation_attempt(
                                success=False, throttled=False, blocked=False
                            )
                        except Exception:
                            pass

                        # Use lock management with CPU throttling for index creation
                        # Wrap with retry logic if enabled
                        try:
                            from src.index_retry import retry_index_creation

                            def create_index_func(
                                t_name=table_name, f_name=field_name, idx_sql=index_sql
                            ):
                                return create_index_with_lock_management(
                                    t_name,
                                    f_name,
                                    idx_sql,
                                    timeout=300,
                                    respect_cpu_throttle=True,
                                )

                            retry_result = retry_index_creation(
                                create_index_func, table_name, field_name
                            )
                            success = retry_result.get("success", False)

                            if retry_result.get("retries", 0) > 0:
                                logger.info(
                                    f"Index {index_name} created after {retry_result.get('retries', 0)} retries"
                                )
                        except ImportError:
                            # Retry module not available, use direct call
                            success = create_index_with_lock_management(
                                table_name,
                                field_name,
                                index_sql,
                                timeout=300,
                                respect_cpu_throttle=True,
                            )
                        except Exception as e:
                            logger.debug(f"Retry logic failed, using direct call: {e}")
                            success = create_index_with_lock_management(
                                table_name,
                                field_name,
                                index_sql,
                                timeout=300,
                                respect_cpu_throttle=True,
                            )

                        if not success:
                            # Index creation was throttled, skip this index
                            logger.warning(f"Index creation throttled for {index_name}")
                            try:
                                from src.safeguard_monitoring import track_index_creation_attempt

                                track_index_creation_attempt(
                                    success=False, throttled=True, blocked=False
                                )
                            except Exception:
                                pass

                            # Record circuit breaker failure
                            try:
                                from src.adaptive_safeguards import record_circuit_failure

                                circuit_breaker_name = f"index_creation_{table_name}"
                                record_circuit_failure(circuit_breaker_name)
                            except Exception:
                                pass

                            skipped_indexes.append(
                                {
                                    "table": table_name,
                                    "field": field_name,
                                    "queries": total_queries,
                                    "reason": "cpu_throttled",
                                }
                            )
                            continue

                        # Track successful creation
                        try:
                            from src.safeguard_monitoring import track_index_creation_attempt

                            track_index_creation_attempt(
                                success=True, throttled=False, blocked=False
                            )
                        except Exception:
                            pass

                        # Record circuit breaker success
                        try:
                            from src.adaptive_safeguards import record_circuit_success

                            circuit_breaker_name = f"index_creation_{table_name}"
                            record_circuit_success(circuit_breaker_name)
                        except Exception:
                            pass

                        # Track index version (Phase 3)
                        try:
                            from src.index_lifecycle_advanced import track_index_version

                            track_index_version(
                                index_name=index_name,
                                table_name=table_name,
                                index_definition=index_sql,
                                created_by="auto_indexer",
                                metadata={
                                    "index_type": index_type,
                                    "build_cost": build_cost,
                                    "confidence": confidence,
                                },
                            )
                        except Exception as e:
                            logger.debug(f"Could not track index version: {e}")

                        # Validate index effectiveness using EXPLAIN before/after
                        validation_result = None
                        try:
                            if sample_query:
                                from src.composite_index_detection import (
                                    validate_index_effectiveness,
                                )

                                query_str, params = sample_query
                                validation_result = validate_index_effectiveness(
                                    table_name=table_name,
                                    field_name=field_name,
                                    index_name=index_name,
                                    sample_query=(query_str, params),
                                )

                                if validation_result.get("status") == "success":
                                    improvement_pct = validation_result.get(
                                        "improvement_percent", 0.0
                                    )
                                    effective = validation_result.get("effective", False)

                                    # ✅ ENHANCEMENT: Use EXPLAIN-based comparison for rollback decision
                                    explain_comparison = None
                                    try:
                                        from src.query_analyzer import compare_explain_before_after

                                        # Get sample query for comparison
                                        sample_query = get_sample_query_for_field(
                                            table_name, field_name
                                        )
                                        if sample_query:
                                            query_str, query_params = sample_query
                                            explain_comparison = compare_explain_before_after(
                                                query=query_str,
                                                params=query_params,
                                                index_name=index_name,
                                            )

                                            # Use EXPLAIN comparison if available and reliable
                                            if explain_comparison.get("is_effective") is not None:
                                                is_effective_explain = explain_comparison.get(
                                                    "is_effective", False
                                                )
                                                improvement_pct_explain = explain_comparison.get(
                                                    "improvement_pct", 0.0
                                                )

                                                # Prefer EXPLAIN-based decision over simple validation
                                                # EXPLAIN provides more accurate cost-based analysis
                                                effective = is_effective_explain
                                                improvement_pct = improvement_pct_explain

                                                cost_reduction_val = explain_comparison.get('cost_reduction_pct', 0.0)
                                                cost_reduction = (
                                                    float(cost_reduction_val)
                                                    if isinstance(cost_reduction_val, (int, float))
                                                    else 0.0
                                                )

                                                logger.info(
                                                    f"EXPLAIN-based validation for {index_name}: "
                                                    f"improvement={improvement_pct_explain:.2f}%, "
                                                    f"effective={is_effective_explain}, "
                                                    f"cost_reduction={cost_reduction:.2f}%"
                                                )
                                            else:
                                                logger.debug(
                                                    f"EXPLAIN comparison returned inconclusive for {index_name}, "
                                                    "falling back to performance validation"
                                                )
                                    except Exception as e:
                                        logger.debug(f"EXPLAIN comparison failed: {e}")
                                        # Fall back to validation_result

                                    # Enhanced rollback decision based on EXPLAIN and validation results
                                    should_rollback = False
                                    rollback_reason = ""

                                    # Ensure improvement_pct is a float for comparisons
                                    improvement_pct_float = (
                                        float(improvement_pct)
                                        if isinstance(improvement_pct, (int, float))
                                        else 0.0
                                    )

                                    if not effective:
                                        if improvement_pct_float < -10.0:  # Significant degradation (>10% worse)
                                            should_rollback = True
                                            rollback_reason = f"significant performance degradation ({improvement_pct_float:.2f}%)"
                                        elif improvement_pct_float < 0 and explain_comparison:
                                            # EXPLAIN shows negative impact
                                            explain_cost_reduction_val = explain_comparison.get("cost_reduction_pct", 0.0)
                                            explain_cost_reduction = (
                                                float(explain_cost_reduction_val)
                                                if isinstance(explain_cost_reduction_val, (int, float))
                                                else 0.0
                                            )
                                            if explain_cost_reduction < -5.0:  # EXPLAIN shows >5% cost increase
                                                should_rollback = True
                                                rollback_reason = f"EXPLAIN shows cost increase ({explain_cost_reduction:.2f}%)"
                                        elif improvement_pct_float < 0:
                                            # Minor degradation but no improvement
                                            should_rollback = True
                                            rollback_reason = f"no performance improvement ({improvement_pct:.2f}%)"

                                    if should_rollback:
                                        logger.warning(
                                            f"Index {index_name} will be rolled back: {rollback_reason}"
                                        )

                                        # Auto-rollback if enabled
                                        auto_rollback_enabled = (
                                            _config_loader.get_bool(
                                                "features.auto_rollback.enabled", False
                                            )
                                            if _config_loader
                                            else False
                                        )

                                        if auto_rollback_enabled:
                                            try:
                                                logger.warning(
                                                    f"Auto-rolling back index {index_name} due to negative improvement"
                                                )
                                                with get_connection() as rollback_conn:
                                                    rollback_cursor = rollback_conn.cursor()
                                                    try:
                                                        rollback_cursor.execute(
                                                            f'DROP INDEX CONCURRENTLY IF EXISTS "{index_name}"'
                                                        )
                                                        rollback_conn.commit()
                                                        logger.info(
                                                            f"Successfully rolled back index {index_name}"
                                                        )

                                                        # Log rollback to audit
                                                        from src.audit import log_audit_event

                                                        log_audit_event(
                                                            "ROLLBACK_INDEX",
                                                            table_name=table_name,
                                                            field_name=field_name,
                                                            details={
                                                                "index_name": index_name,
                                                                "reason": "negative_improvement",
                                                                "improvement_pct": improvement_pct,
                                                            },
                                                            severity="warning",
                                                        )

                                                        # Skip adding to created_indexes
                                                        continue
                                                    except Exception as rollback_error:
                                                        logger.error(
                                                            f"Failed to rollback index {index_name}: {rollback_error}"
                                                        )
                                                        rollback_conn.rollback()
                                            except Exception as e:
                                                logger.error(
                                                    f"Auto-rollback failed for {index_name}: {e}"
                                                )
                                        # Note: If auto-rollback disabled, index is kept but warning is logged
                                elif validation_result.get("status") == "theoretical":
                                    # Index doesn't exist yet, theoretical analysis
                                    recommended = validation_result.get("recommended", False)
                                    if not recommended:
                                        logger.debug(
                                            f"Index {index_name} theoretical analysis suggests limited benefit"
                                        )
                        except Exception as e:
                            logger.debug(f"Could not validate index effectiveness: {e}")

                        # Measure performance after index creation
                        after_perf = None
                        improvement_pct = 0.0
                        try:
                            if sample_query and before_perf:
                                query_str, params = sample_query
                                # Wait a moment for index to be ready
                                time.sleep(0.5)

                                sample_runs_val = _COST_CONFIG.get("SAMPLE_QUERY_RUNS", 5)
                                sample_runs = (
                                    int(sample_runs_val)
                                    if isinstance(sample_runs_val, (int, float))
                                    else 5
                                )
                                after_perf = measure_query_performance(
                                    query_str, params, num_runs=sample_runs
                                )
                                # Note: after_plan analysis removed as it was unused

                                # Calculate improvement
                                if before_perf["median_ms"] > 0:
                                    improvement_pct = (
                                        (before_perf["median_ms"] - after_perf["median_ms"])
                                        / before_perf["median_ms"]
                                    ) * 100.0

                                # If improvement is below threshold, consider removing index
                                min_improvement_val = _COST_CONFIG.get("MIN_IMPROVEMENT_PCT", 20.0)
                                min_improvement = (
                                    min_improvement_val
                                    if isinstance(min_improvement_val, (int, float))
                                    else 20.0
                                )
                                if improvement_pct < min_improvement:
                                    logger.warning(
                                        f"Index {index_name} shows only {improvement_pct:.1f}% improvement "
                                        f"(below {min_improvement}% threshold)"
                                    )
                                    # Auto-rollback if improvement is negative and enabled
                                    auto_rollback_enabled = (
                                        _config_loader.get_bool(
                                            "features.auto_rollback.enabled", False
                                        )
                                        if _config_loader
                                        else False
                                    )

                                    if auto_rollback_enabled and improvement_pct < 0:
                                        # Only auto-rollback if improvement is negative (not just below threshold)
                                        try:
                                            logger.warning(
                                                f"Auto-rolling back index {index_name} due to negative improvement"
                                            )
                                            with get_connection() as rollback_conn:
                                                rollback_cursor = rollback_conn.cursor()
                                                try:
                                                    rollback_cursor.execute(
                                                        f'DROP INDEX CONCURRENTLY IF EXISTS "{index_name}"'
                                                    )
                                                    rollback_conn.commit()
                                                    logger.info(
                                                        f"Successfully rolled back index {index_name}"
                                                    )

                                                    # Log rollback to audit
                                                    from src.audit import log_audit_event

                                                    log_audit_event(
                                                        "ROLLBACK_INDEX",
                                                        table_name=table_name,
                                                        field_name=field_name,
                                                        details={
                                                            "index_name": index_name,
                                                            "reason": "below_threshold_negative",
                                                            "improvement_pct": improvement_pct,
                                                            "threshold": min_improvement,
                                                        },
                                                        severity="warning",
                                                    )

                                                    # Skip adding to created_indexes
                                                    continue
                                                except Exception as rollback_error:
                                                    logger.error(
                                                        f"Failed to rollback index {index_name}: {rollback_error}"
                                                    )
                                                    rollback_conn.rollback()
                                        except Exception as e:
                                            logger.error(
                                                f"Auto-rollback failed for {index_name}: {e}"
                                            )
                                    # Note: If auto-rollback disabled or improvement >= 0, index is kept but warning is logged
                        except Exception as e:
                            logger.debug(f"Could not measure after performance: {e}")

                        # Log the mutation to audit trail
                        from src.audit import log_audit_event

                        log_audit_event(
                            "CREATE_INDEX",
                            table_name=table_name,
                            field_name=field_name,
                            details={
                                "index_name": index_name,
                                "index_type": index_type,
                                "build_cost_estimate": build_cost,
                                "queries_analyzed": total_queries,
                                "query_cost_without_index": query_cost_without_index,
                                "row_count": row_count,
                                "field_selectivity": field_selectivity,
                                "confidence": confidence,
                                "reason": reason,
                                "strategy": strategy["primary"],
                                "before_perf_ms": before_perf["median_ms"] if before_perf else None,
                                "after_perf_ms": after_perf["median_ms"] if after_perf else None,
                                "improvement_pct": improvement_pct if after_perf else None,
                                "mode": "apply",  # Index was actually created
                            },
                            severity="info",
                        )

                        # Monitor write performance after creating
                        monitor_write_performance(table_name)

                        created_indexes.append(
                            {
                                "table": table_name,
                                "field": field_name,
                                "index_name": index_name,
                                "index_type": index_type,
                                "queries": total_queries,
                                "build_cost": build_cost,
                                "confidence": confidence,
                                "field_selectivity": field_selectivity,
                                "improvement_pct": improvement_pct if after_perf else None,
                                "write_overhead_estimate": write_stats.get(
                                    "estimated_write_overhead", 0
                                ),
                            }
                        )
                        write_overhead_val = write_stats.get("estimated_write_overhead", 0)
                        write_overhead = (
                            float(write_overhead_val)
                            if isinstance(write_overhead_val, (int, float))
                            else 0.0
                        )
                        improvement_str = (
                            f"improvement: {improvement_pct:.1f}%, " if after_perf else ""
                        )
                        print(
                            f"Created index {index_name} on {table_name}.{field_name} "
                            f"(type: {index_type}, queries: {total_queries}, "
                            f"build_cost: {build_cost:.2f}, confidence: {confidence:.2f}, "
                            f"{improvement_str}"
                            f"write overhead: {write_overhead * 100:.1f}%)"
                        )

                        # Register newly created index with lifecycle management
                        try:
                            from src.index_lifecycle_manager import is_lifecycle_management_enabled
                            if is_lifecycle_management_enabled():
                                logger.debug(f"Index {index_name} registered with lifecycle management")
                        except Exception as lifecycle_error:
                            logger.debug(f"Could not register index {index_name} with lifecycle: {lifecycle_error}")
                    except (IndexCreationError, Exception) as e:
                        logger.error(f"Failed to create index {index_name}: {e}")
                        monitoring = get_monitoring()
                        monitoring.alert("warning", f"Failed to create index {index_name}: {e}")
                        skipped_indexes.append(
                            {
                                "table": table_name,
                                "field": field_name,
                                "queries": total_queries,
                                "reason": f"creation_failed: {str(e)}",
                            }
                        )
                else:
                    skipped_indexes.append(
                        {
                            "table": table_name,
                            "field": field_name,
                            "queries": total_queries,
                            "reason": reason,
                            "build_cost": build_cost,
                            "query_cost": query_cost_without_index,
                            "confidence": confidence,
                            "field_selectivity": field_selectivity,
                        }
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    # Log EXPLAIN coverage statistics if tracking is enabled
    if _COST_CONFIG.get("EXPLAIN_USAGE_TRACKING_ENABLED", True):
        explain_stats = get_explain_usage_stats()
        if explain_stats["total_decisions"] > 0:
            logger.info(
                f"EXPLAIN usage summary: {explain_stats['explain_coverage_pct']:.1f}% coverage "
                f"({explain_stats['explain_used']}/{explain_stats['total_decisions']} decisions), "
                f"{explain_stats['explain_success_rate_pct']:.1f}% success rate"
            )

            # Log warning if coverage is below minimum threshold
            log_explain_coverage_warning()

    return {"created": created_indexes, "skipped": skipped_indexes}


if __name__ == "__main__":
    results = analyze_and_create_indexes()
    print("\nIndex creation summary:")
    print(f"  Created: {len(results['created'])}")
    print(f"  Skipped: {len(results['skipped'])}")
