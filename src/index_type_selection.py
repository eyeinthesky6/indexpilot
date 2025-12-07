"""EXPLAIN-based index type selection (B-tree vs Hash vs GIN)"""

# INTEGRATION NOTE: Learned Index Types Enhancement
# Current: B-tree, Hash, GIN index type selection
# Enhancement: Add learned index types:
#   - PGM-Index (arXiv:1910.06169) for read-heavy workloads
#   - ALEX (arXiv:1905.08898) for dynamic workloads
#   - RadixStringSpline (arXiv:2111.14905) for string fields
# Integration: Add learned index types as additional options in select_optimal_index_type()
# See: docs/research/ALGORITHM_OVERLAP_ANALYSIS.md

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.query_analyzer import analyze_query_plan_fast
from src.type_definitions import QueryParams
from src.validation import validate_field_name, validate_table_name

logger = logging.getLogger(__name__)


def select_optimal_index_type(
    table_name: str,
    field_name: str,
    query_patterns: dict[str, Any],
    sample_query: tuple[str, tuple[Any, ...]] | None = None,
) -> dict[str, Any]:
    """
    Select optimal index type using EXPLAIN analysis.

    Compares B-tree, Hash, GIN, and PGM-Index (if enabled) to find the best option.
    Note: PGM-Index is not natively supported in PostgreSQL, but suitability analysis
    is provided. When PGM-Index is recommended, a B-tree index is created with
    recommendations for learned index benefits.

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information
        sample_query: Optional sample query (query_str, params)

    Returns:
        dict with recommended index type and analysis
    """
    try:
        _ = validate_table_name(table_name)  # Validation only, result not used
        _ = validate_field_name(field_name, table_name)  # Validation only, result not used
    except Exception as e:
        logger.debug(f"Invalid table/field for index type selection: {e}")
        return {"index_type": "btree", "reason": "validation_failed", "confidence": 0.0}

    # Get field data type
    field_type = _get_field_type(table_name, field_name)
    if not field_type:
        return {"index_type": "btree", "reason": "unknown_field_type", "confidence": 0.0}

    # Analyze query patterns
    has_like = query_patterns.get("has_like", False)
    has_exact = query_patterns.get("has_exact", False)
    has_range = query_patterns.get("has_range", False)

    # Check ALEX strategy (if enabled)
    alex_recommendation = None
    try:
        from src.config_loader import ConfigLoader

        config_loader = ConfigLoader()
        alex_enabled = config_loader.get_bool("features.alex.enabled", True)

        if alex_enabled:
            from src.algorithms.alex import get_alex_index_recommendation

            alex_recommendation = get_alex_index_recommendation(
                table_name=table_name,
                field_name=field_name,
                query_patterns=query_patterns,
                time_window_hours=24,
            )

            # If ALEX strongly recommends a specific strategy, consider it
            if alex_recommendation and alex_recommendation.get("use_alex_strategy", False):
                alex_confidence = alex_recommendation.get("confidence", 0.0)
                if alex_confidence >= 0.7:
                    # ALEX has high confidence, use its recommendation
                    recommended_type = alex_recommendation.get("index_type", "btree")
                    return {
                        "index_type": recommended_type,
                        "reason": alex_recommendation.get("reason", "alex_strategy"),
                        "confidence": alex_confidence,
                        "alex_recommendation": alex_recommendation,
                        "method": "alex_analysis",
                    }
    except Exception as e:
        logger.debug(f"ALEX analysis failed (non-critical): {e}")
        # Continue with standard analysis if ALEX fails

    # Get sample query if not provided
    if not sample_query:
        from src.auto_indexer import get_sample_query_for_field

        sample_query = get_sample_query_for_field(table_name, field_name)
        if not sample_query:
            # Fall back to heuristics if no sample query
            result = _select_index_type_by_heuristics(field_type, has_like, has_exact, has_range)
            # Add ALEX insights if available
            if alex_recommendation:
                result["alex_insights"] = alex_recommendation.get("alex_insights", {})
            return result

    query_str, params = sample_query

    # Compare index types using EXPLAIN
    # Include PGM-Index if enabled (though PostgreSQL doesn't natively support it,
    # we analyze suitability and provide recommendations)
    index_types = ["btree", "hash", "gin"]

    # Check if PGM-Index analysis is enabled
    try:
        from src.config_loader import ConfigLoader

        config_loader = ConfigLoader()
        pgm_enabled = config_loader.get_bool("features.pgm_index.enabled", False)
        if pgm_enabled:
            index_types.append("pgm")
    except Exception:
        pgm_enabled = False

    comparisons = []

    for idx_type in index_types:
        # Special handling for PGM-Index (learned index analysis)
        if idx_type == "pgm":
            comparison = _compare_pgm_index_suitability(
                table_name, field_name, query_patterns, query_str, params
            )
            if comparison:
                comparisons.append(comparison)
            continue

        # Check if index type is suitable for this field type
        if not _is_index_type_suitable(idx_type, field_type):
            continue

        # Create hypothetical index and analyze
        comparison = _compare_index_type_with_explain(
            table_name, field_name, idx_type, query_str, params
        )
        if comparison:
            comparisons.append(comparison)

    if not comparisons:
        # Fall back to heuristics
        result = _select_index_type_by_heuristics(field_type, has_like, has_exact, has_range)
        # Add ALEX insights if available
        if alex_recommendation:
            result["alex_insights"] = alex_recommendation.get("alex_insights", {})
        return result

    # Select best index type based on EXPLAIN analysis
    best_comparison = min(comparisons, key=lambda x: x.get("estimated_cost", float("inf")))
    recommended_type = best_comparison["index_type"]

    return {
        "index_type": recommended_type,
        "reason": "explain_analysis",
        "confidence": best_comparison.get("confidence", 0.7),
        "comparisons": comparisons,
        "best_comparison": best_comparison,
    }


def _get_field_type(table_name: str, field_name: str) -> str | None:
    """Get PostgreSQL data type for a field."""
    try:
        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)
    except Exception:
        return None

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                """
                SELECT data_type, udt_name
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            """,
                (validated_table, validated_field),
            )
            result = cursor.fetchone()
            if result:
                # Prefer udt_name (more specific) over data_type
                udt_name = result.get("udt_name")
                data_type = result.get("data_type")
                if udt_name is not None:
                    return str(udt_name)
                if data_type is not None:
                    return str(data_type)
            return None
        finally:
            cursor.close()


def _is_index_type_suitable(index_type: str, field_type: str) -> bool:
    """
    Check if index type is suitable for field type.

    Args:
        index_type: Index type (btree, hash, gin, pgm)
        field_type: PostgreSQL data type

    Returns:
        True if index type is suitable
    """
    field_type_lower = field_type.lower() if field_type else ""

    # PGM-Index: Works for most types (similar to B-tree), but best for ordered data
    if index_type == "pgm":
        # PGM-Index works for most types, but not ideal for arrays/JSON
        unsuitable_types = ["array", "json", "jsonb", "tsvector"]
        return not any(unsuitable in field_type_lower for unsuitable in unsuitable_types)

    # Hash indexes: Only for equality comparisons, not for text/array types
    if index_type == "hash":
        # Hash indexes work well for integer, numeric, text (but limited use cases)
        # Not suitable for arrays, JSON, or text with LIKE patterns
        unsuitable_types = ["array", "json", "jsonb", "tsvector"]
        return not any(unsuitable in field_type_lower for unsuitable in unsuitable_types)

    # GIN indexes: For arrays, JSONB, full-text search
    if index_type == "gin":
        suitable_types = ["array", "jsonb", "tsvector", "text"]
        return bool(any(suitable in field_type_lower for suitable in suitable_types))

    # B-tree: Default, works for most types
    return index_type == "btree"


def _compare_index_type_with_explain(
    table_name: str,
    field_name: str,
    index_type: str,
    query_str: str,
    params: QueryParams,
) -> dict[str, Any] | None:
    """
    Compare index type using EXPLAIN (theoretical analysis).

    Note: We can't actually create the index to test, so we use heuristics
    combined with EXPLAIN analysis of the query without index.

    Args:
        table_name: Table name
        field_name: Field name
        index_type: Index type to compare
        query_str: Query string
        params: Query parameters

    Returns:
        Comparison dict with estimated cost and confidence
    """
    # Analyze current query plan (without index)
    plan = analyze_query_plan_fast(query_str, params)
    if not plan:
        return None

    current_cost = plan.get("total_cost", 0)
    has_seq_scan = plan.get("has_seq_scan", False)

    # Estimate improvement with different index types
    # These are heuristic estimates based on PostgreSQL index characteristics

    if index_type == "btree":
        # B-tree: Good for equality, range, sorting
        # Typical improvement: 10-100x for equality, 5-50x for range
        if has_seq_scan:
            estimated_cost = current_cost / 20.0  # Conservative estimate
            confidence = 0.8
        else:
            estimated_cost = current_cost
            confidence = 0.5

    elif index_type == "hash":
        # Hash: Excellent for equality (O(1) lookup), but no range/sort support
        # Typical improvement: 50-200x for equality-only queries
        if has_seq_scan:
            estimated_cost = current_cost / 50.0  # Better for equality
            confidence = 0.7  # Lower confidence (limited use cases)
        else:
            estimated_cost = current_cost
            confidence = 0.3

    elif index_type == "gin":
        # GIN: Excellent for arrays, JSONB, full-text search
        # Typical improvement: 10-1000x for array/JSON queries
        if has_seq_scan:
            estimated_cost = current_cost / 30.0  # Good for complex types
            confidence = 0.9  # High confidence for suitable types
        else:
            estimated_cost = current_cost
            confidence = 0.5

    else:
        return None

    return {
        "index_type": index_type,
        "current_cost": current_cost,
        "estimated_cost": estimated_cost,
        "estimated_improvement": ((current_cost - estimated_cost) / current_cost * 100)
        if current_cost > 0
        else 0,
        "confidence": confidence,
        "has_seq_scan": has_seq_scan,
    }


def _compare_pgm_index_suitability(
    table_name: str,
    field_name: str,
    query_patterns: dict[str, Any],
    query_str: str,
    params: QueryParams,
) -> dict[str, Any] | None:
    """
    Compare PGM-Index suitability using learned index analysis.

    Note: PostgreSQL doesn't natively support PGM-Index, but we analyze
    suitability and provide recommendations. When PGM-Index is recommended,
    we fall back to B-tree with a note about learned index benefits.

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information
        query_str: Query string
        params: Query parameters

    Returns:
        Comparison dict with PGM-Index analysis or None if not suitable
    """
    try:
        from src.algorithms.pgm_index import analyze_pgm_index_suitability

        # Analyze PGM-Index suitability
        pgm_analysis = analyze_pgm_index_suitability(
            table_name=table_name,
            field_name=field_name,
            query_patterns=query_patterns,
            read_write_ratio=None,  # Could be enhanced to calculate from query stats
        )

        if not pgm_analysis.get("is_suitable", False):
            return None

        # Get current query plan for comparison
        plan = analyze_query_plan_fast(query_str, params)
        if not plan:
            return None

        current_cost = plan.get("total_cost", 0)
        has_seq_scan = plan.get("has_seq_scan", False)

        # PGM-Index provides similar or better read performance than B-tree
        # with significant space savings
        if has_seq_scan:
            # PGM-Index would provide similar improvement to B-tree for reads
            estimated_cost = current_cost / 20.0  # Similar to B-tree estimate
            confidence = pgm_analysis.get("confidence", 0.7)
        else:
            estimated_cost = current_cost
            confidence = (
                pgm_analysis.get("confidence", 0.5) * 0.8
            )  # Lower confidence if no seq scan

        # Adjust confidence based on suitability score
        suitability_score = pgm_analysis.get("suitability_score", 0.0)
        confidence = min(confidence, suitability_score)

        space_savings = pgm_analysis.get("estimated_space_savings", 0.0)

        return {
            "index_type": "pgm",
            "current_cost": current_cost,
            "estimated_cost": estimated_cost,
            "estimated_improvement": ((current_cost - estimated_cost) / current_cost * 100)
            if current_cost > 0
            else 0,
            "confidence": confidence,
            "has_seq_scan": has_seq_scan,
            "space_savings": space_savings,
            "suitability_score": suitability_score,
            "recommendations": pgm_analysis.get("recommendations", []),
            "note": "PGM-Index not natively supported in PostgreSQL - recommendation for learned index benefits",
        }
    except Exception as e:
        logger.debug(f"PGM-Index analysis failed: {e}")
        return None


def _select_index_type_by_heuristics(
    field_type: str, has_like: bool, has_exact: bool, has_range: bool
) -> dict[str, Any]:
    """
    Select index type using heuristics when EXPLAIN is not available.

    Args:
        field_type: PostgreSQL data type
        field_name: Field name
        has_like: Whether queries use LIKE patterns
        has_exact: Whether queries use exact matches
        has_range: Whether queries use range comparisons

    Returns:
        dict with recommended index type
    """
    field_type_lower = field_type.lower() if field_type else ""

    # GIN for arrays, JSONB, full-text
    if "array" in field_type_lower or "jsonb" in field_type_lower:
        return {
            "index_type": "gin",
            "reason": "field_type_heuristic",
            "confidence": 0.9,
        }

    # Hash for equality-only queries (limited use cases)
    if (
        has_exact
        and not has_like
        and not has_range
        and field_type_lower in ["integer", "bigint", "numeric", "text", "varchar"]
    ):
        return {
            "index_type": "hash",
            "reason": "equality_only_heuristic",
            "confidence": 0.6,  # Lower confidence - hash has limitations
        }

    # B-tree: Default choice (most versatile)
    return {
        "index_type": "btree",
        "reason": "default_heuristic",
        "confidence": 0.7,
    }


def generate_index_sql_with_type(
    table_name: str,
    field_name: str,
    index_type: str,
    has_tenant: bool = False,
) -> tuple[str, str]:
    """
    Generate CREATE INDEX SQL with specified index type.

    Args:
        table_name: Table name
        field_name: Field name
        index_type: Index type (btree, hash, gin, pgm)
        has_tenant: Whether table has tenant_id field

    Returns:
        Tuple of (index_sql, index_name)
    """
    from src.validation import validate_field_name, validate_table_name

    validated_table = validate_table_name(table_name)
    validated_field = validate_field_name(field_name, table_name)

    # Note: PGM-Index is not natively supported in PostgreSQL
    # When pgm is requested, we create a B-tree index with a note
    # In the future, this could be extended to use PostgreSQL extensions
    # or external learned index implementations
    actual_index_type = "btree" if index_type == "pgm" else index_type

    # Generate index name
    type_suffix = f"_{index_type}" if index_type != "btree" else ""
    tenant_suffix = "_tenant" if has_tenant else ""
    index_name = f"idx_{table_name}_{field_name}{type_suffix}{tenant_suffix}"

    # Build index SQL
    if has_tenant:
        if actual_index_type == "gin":
            # GIN indexes may need special handling for tenant_id
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON "{validated_table}" USING {actual_index_type} (tenant_id, "{validated_field}")
            """
        else:
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON "{validated_table}" USING {actual_index_type} (tenant_id, "{validated_field}")
            """
    else:
        index_sql = f"""
            CREATE INDEX IF NOT EXISTS "{index_name}"
            ON "{validated_table}" USING {actual_index_type} ("{validated_field}")
        """

    return index_sql, index_name
