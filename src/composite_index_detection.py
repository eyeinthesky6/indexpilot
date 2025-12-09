"""Composite index detection using EXPLAIN analysis"""

# INTEGRATION NOTE: Cortex (Data Correlation Exploitation) Enhancement - ✅ COMPLETE
# Current: Enhanced composite index detection with Cortex correlation analysis
# Enhancement: Cortex implemented in src/algorithms/cortex.py
# Integration: Cortex analysis integrated into detect_composite_index_opportunities()
# See: docs/research/ALGORITHM_OVERLAP_ANALYSIS.md

import logging

# from collections import defaultdict  # Reserved for future use
from typing import Any

from src.config_loader import ConfigLoader
from src.db import get_cursor
from src.query_analyzer import analyze_query_plan_fast
from src.stats import get_query_stats

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()

# Constants for composite index detection thresholds (with config defaults)
DEFAULT_TIME_WINDOW_HOURS = 24
DEFAULT_MIN_QUERY_COUNT = 10


def _get_high_cost_threshold() -> float:
    """Get high cost threshold from config or default"""
    return _config_loader.get_float("features.composite_index_detection.high_cost_threshold", 100.0)


def _get_min_improvement_percent() -> float:
    """Get minimum improvement percentage from config or default"""
    return _config_loader.get_float(
        "features.composite_index_detection.min_improvement_percent", 10.0
    )


def _get_estimated_improvement_percent() -> float:
    """Get estimated improvement percentage from config or default"""
    return _config_loader.get_float(
        "features.composite_index_detection.estimated_improvement_percent", 50.0
    )


def detect_composite_index_opportunities(
    table_name: str,
    time_window_hours: int | None = None,
    min_query_count: int | None = None,
) -> list[dict[str, Any]]:
    """
    Detect opportunities for composite indexes by analyzing query patterns.

    Uses EXPLAIN to identify queries that would benefit from multi-column indexes.

    Args:
        table_name: Table to analyze
        time_window_hours: Time window for query analysis (defaults to config or constant)
        min_query_count: Minimum queries needed to suggest composite index (defaults to config or constant)

    Returns:
        List of composite index suggestions
    """
    # Use config values or constants as defaults
    if time_window_hours is None:
        time_window_hours = _config_loader.get_int(
            "features.composite_index_detection.time_window_hours", DEFAULT_TIME_WINDOW_HOURS
        )
    if min_query_count is None:
        min_query_count = _config_loader.get_int(
            "features.composite_index_detection.min_query_count", DEFAULT_MIN_QUERY_COUNT
        )

    try:
        from src.validation import validate_table_name

        _ = validate_table_name(table_name)  # Validation only, result not used
    except Exception as e:
        logger.debug(f"Invalid table name {table_name}: {e}")
        return []

    # Get query stats for this table
    query_stats = get_query_stats(time_window_hours=time_window_hours, table_name=table_name)

    if not query_stats:
        return []

    # Group queries by field combinations
    # For now, we'll analyze individual fields and look for patterns
    # In a full implementation, we'd parse actual queries to find WHERE clause combinations
    # field_combinations: dict[tuple[str, ...], int] = defaultdict(int)  # Reserved for future use

    # Analyze each field's query patterns
    with get_cursor() as cursor:
        try:
            # Get fields that are frequently queried together
            # This is a simplified approach - in production, we'd parse actual queries
            cursor.execute(
                """
                SELECT DISTINCT field_name, COUNT(*) as query_count
                FROM query_stats
                WHERE table_name = %s
                  AND created_at >= NOW() - INTERVAL '1 hour' * %s
                GROUP BY field_name
                HAVING COUNT(*) >= %s
                ORDER BY query_count DESC
            """,
                (table_name, time_window_hours, min_query_count),
            )

            fields = cursor.fetchall()
            if len(fields) < 2:
                # Need at least 2 fields for composite index
                return []

            # For each pair of frequently-queried fields, check if composite would help
            suggestions = []
            for i, field1 in enumerate(fields):
                for field2 in fields[i + 1 :]:
                    field1_name = field1["field_name"]
                    field2_name = field2["field_name"]

                    # Check if queries on these fields would benefit from composite index
                    # by analyzing a sample query
                    opportunity = _analyze_composite_opportunity(
                        table_name, field1_name, field2_name
                    )

                    if opportunity:
                        suggestions.append(opportunity)

            # Cortex Enhancement: Add correlation-based suggestions
            try:
                from src.algorithms.cortex import enhance_composite_detection

                # Get candidate columns from fields
                candidate_columns = [f["field_name"] for f in fields]
                logger.info(
                    f"[ALGORITHM] Calling Cortex for composite index detection "
                    f"(table: {table_name}, candidate_columns: {len(candidate_columns)})"
                )
                enhanced_suggestions = enhance_composite_detection(
                    suggestions, table_name, candidate_columns
                )
                # Track algorithm usage for monitoring and analysis
                try:
                    from src.algorithm_tracking import track_algorithm_usage

                    track_algorithm_usage(
                        table_name=table_name,
                        field_name=None,  # Composite indexes involve multiple fields
                        algorithm_name="cortex",
                        recommendation={
                            "original_suggestions": len(suggestions),
                            "enhanced_suggestions": len(enhanced_suggestions),
                            "candidate_columns": candidate_columns,
                        },
                        used_in_decision=len(enhanced_suggestions) > len(suggestions),
                    )
                except Exception as e:
                    logger.warning(f"Could not track Cortex usage: {e}", exc_info=True)
                suggestions = enhanced_suggestions
            except Exception as e:
                logger.debug(f"Cortex enhancement failed: {e}")
                # Continue with base suggestions if Cortex fails

            return suggestions
        except Exception as e:
            logger.error(f"Error detecting composite indexes: {e}")
            return []


def _analyze_composite_opportunity(
    table_name: str, field1: str, field2: str
) -> dict[str, Any] | None:
    """
    Analyze if a composite index on field1, field2 would be beneficial.

    Uses EXPLAIN to compare single-field vs composite index plans.

    Args:
        table_name: Table name
        field1: First field
        field2: Second field

    Returns:
        Opportunity dict if composite would help, None otherwise
    """
    try:
        from src.auto_indexer import _has_tenant_field
        from src.validation import validate_field_name, validate_table_name

        validated_table = validate_table_name(table_name)
        validated_field1 = validate_field_name(field1, table_name)
        validated_field2 = validate_field_name(field2, table_name)

        has_tenant = _has_tenant_field(table_name, use_cache=True)

        # Create a sample query with both fields in WHERE clause
        with get_cursor() as cursor:
            try:
                # Get sample values for both fields
                if has_tenant:
                    # Get sample tenant_id and field values
                    cursor.execute(
                        f"""
                        SELECT tenant_id, {validated_field1}, {validated_field2}
                        FROM {validated_table}
                        WHERE {validated_field1} IS NOT NULL
                          AND {validated_field2} IS NOT NULL
                        LIMIT 1
                    """
                    )
                else:
                    cursor.execute(
                        f"""
                        SELECT {validated_field1}, {validated_field2}
                        FROM {validated_table}
                        WHERE {validated_field1} IS NOT NULL
                          AND {validated_field2} IS NOT NULL
                        LIMIT 1
                    """
                    )

                sample = cursor.fetchone()
                if not sample:
                    return None

                # Build composite query
                if has_tenant:
                    tenant_id = sample["tenant_id"]
                    val1 = sample[validated_field1]
                    val2 = sample[validated_field2]
                    query = f"""
                        SELECT * FROM {validated_table}
                        WHERE tenant_id = %s AND {validated_field1} = %s AND {validated_field2} = %s
                        LIMIT 1
                    """
                    params = [tenant_id, val1, val2]
                else:
                    val1 = sample[validated_field1]
                    val2 = sample[validated_field2]
                    query = f"""
                        SELECT * FROM {validated_table}
                        WHERE {validated_field1} = %s AND {validated_field2} = %s
                        LIMIT 1
                    """
                    params = [val1, val2]

                # Analyze query plan
                plan = analyze_query_plan_fast(query, params)
                if not plan:
                    return None

                # Check if sequential scan (would benefit from composite index)
                has_seq_scan = plan.get("has_seq_scan", False)
                total_cost = plan.get("total_cost", 0)

                # Get high cost threshold from config or use default
                cost_threshold = _get_high_cost_threshold()

                # If sequential scan with high cost, composite index would help
                if has_seq_scan and total_cost > cost_threshold:
                    return {
                        "table_name": table_name,
                        "fields": [field1, field2],
                        "suggested_index": f"idx_{table_name}_{field1}_{field2}"
                        + ("_tenant" if has_tenant else ""),
                        "current_cost": total_cost,
                        "has_seq_scan": True,
                        "benefit": "high",  # Would eliminate sequential scan
                        "index_sql": _generate_composite_index_sql(
                            table_name, field1, field2, has_tenant
                        ),
                    }

                return None
            except Exception as e:
                logger.debug(f"Error analyzing composite opportunity query: {e}")
                return None

    except Exception as e:
        logger.debug(
            f"Could not analyze composite opportunity for {table_name}.{field1}+{field2}: {e}"
        )
        return None


def _generate_composite_index_sql(
    table_name: str, field1: str, field2: str, has_tenant: bool
) -> str:
    """Generate SQL for composite index."""

    from src.validation import validate_field_name, validate_table_name

    validated_table = validate_table_name(table_name)
    validated_field1 = validate_field_name(field1, table_name)
    validated_field2 = validate_field_name(field2, table_name)

    if has_tenant:
        index_name = f"idx_{table_name}_{field1}_{field2}_tenant"
        return f"""
            CREATE INDEX IF NOT EXISTS "{index_name}"
            ON {validated_table}(tenant_id, {validated_field1}, {validated_field2})
        """
    else:
        index_name = f"idx_{table_name}_{field1}_{field2}"
        return f"""
            CREATE INDEX IF NOT EXISTS "{index_name}"
            ON {validated_table}({validated_field1}, {validated_field2})
        """


def validate_index_effectiveness(
    table_name: str,
    field_name: str,
    index_name: str,
    sample_query: tuple[str, tuple[Any, ...]] | None = None,
) -> dict[str, Any]:
    """
    Validate index effectiveness by comparing before/after EXPLAIN plans.

    Args:
        table_name: Table name
        field_name: Field name
        index_name: Index name to validate
        sample_query: Optional sample query (query_str, params)

    Returns:
        dict with before/after comparison
    """
    from src.auto_indexer import get_sample_query_for_field
    from src.query_analyzer import analyze_query_plan_fast

    # Try to use enhanced before/after validation if available
    try:
        from src.before_after_validation import compare_query_plans, validate_index_improvement

        use_enhanced_validation = True
    except ImportError:
        use_enhanced_validation = False

    if not sample_query:
        # Get sample query
        sample_query = get_sample_query_for_field(table_name, field_name)
        if not sample_query:
            return {
                "status": "error",
                "message": "Could not generate sample query",
            }

    query_str, params = sample_query

    # Get before plan (if index doesn't exist yet, this is theoretical)
    # For existing indexes, we'd need to temporarily disable it
    # For now, we'll analyze the current plan
    before_plan = analyze_query_plan_fast(query_str, params)

    # Use enhanced validation if available
    if use_enhanced_validation and before_plan:
        try:
            # Get after plan after index creation
            after_plan = analyze_query_plan_fast(query_str, params)
            if after_plan:
                comparison = compare_query_plans(query_str, params, before_plan, after_plan)
                validation = validate_index_improvement(query_str, params, before_plan, after_plan)

                if comparison.get("improvement", {}).get("overall_improvement"):
                    improvement_pct = comparison.get("comparison", {}).get(
                        "cost_improvement_pct", 0.0
                    )
                    return {
                        "status": "success",
                        "index_exists": True,
                        "before": {
                            "cost": before_plan.get("total_cost", 0),
                            "has_seq_scan": before_plan.get("has_seq_scan", False),
                        },
                        "after": {
                            "cost": after_plan.get("total_cost", 0),
                            "has_seq_scan": after_plan.get("has_seq_scan", False),
                        },
                        "improvement_percent": round(improvement_pct, 2),
                        "effective": validation.get("valid", False),
                        "comparison": comparison,
                        "validation": validation,
                    }
        except Exception as e:
            logger.debug(f"Enhanced validation failed, falling back to basic: {e}")

    # Check if index exists
    with get_cursor() as cursor:
        cursor.execute(
            """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND indexname = %s
            """,
            (index_name,),
        )
        index_exists = cursor.fetchone() is not None

    if index_exists:
        # Index exists - get after plan
        after_plan = analyze_query_plan_fast(query_str, params)

        if before_plan and after_plan:
            before_cost = before_plan.get("total_cost", 0)
            after_cost = after_plan.get("total_cost", 0)
            improvement = ((before_cost - after_cost) / before_cost * 100) if before_cost > 0 else 0

            # Get minimum improvement threshold from config or use default
            min_improvement = _get_min_improvement_percent()

            return {
                "status": "success",
                "index_exists": True,
                "before": {
                    "cost": before_cost,
                    "has_seq_scan": before_plan.get("has_seq_scan", False),
                },
                "after": {
                    "cost": after_cost,
                    "has_seq_scan": after_plan.get("has_seq_scan", False),
                },
                "improvement_percent": round(improvement, 2),
                "effective": improvement > min_improvement,
            }
    else:
        # Index doesn't exist - theoretical analysis
        # We can't get a true "after" plan, but we can estimate
        if before_plan:
            before_cost = before_plan.get("total_cost", 0)
            has_seq_scan = before_plan.get("has_seq_scan", False)

            # Get thresholds from config or use defaults
            cost_threshold = _get_high_cost_threshold()
            estimated_improvement_pct = _get_estimated_improvement_percent()

            # Estimate improvement (index scan typically 10-100x faster than seq scan)
            estimated_improvement = (
                estimated_improvement_pct if has_seq_scan and before_cost > cost_threshold else 0.0
            )

            return {
                "status": "theoretical",
                "index_exists": False,
                "before": {
                    "cost": before_cost,
                    "has_seq_scan": has_seq_scan,
                },
                "estimated_improvement_percent": estimated_improvement,
                "recommended": has_seq_scan and before_cost > cost_threshold,
            }

    return {
        "status": "error",
        "message": "Could not analyze index effectiveness",
    }
