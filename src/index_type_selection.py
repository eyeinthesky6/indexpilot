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
from src.validation import validate_field_name, validate_table_name

logger = logging.getLogger(__name__)


def select_optimal_index_type(
    table_name: str,
    field_name: str,
    query_patterns: dict[str, Any],
    sample_query: tuple[str, tuple] | None = None,
) -> dict[str, Any]:
    """
    Select optimal index type using EXPLAIN analysis.

    Compares B-tree, Hash, and GIN indexes to find the best option.

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information
        sample_query: Optional sample query (query_str, params)

    Returns:
        dict with recommended index type and analysis
    """
    try:
        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)
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

    # Get sample query if not provided
    if not sample_query:
        from src.auto_indexer import get_sample_query_for_field

        sample_query = get_sample_query_for_field(table_name, field_name)
        if not sample_query:
            # Fall back to heuristics if no sample query
            return _select_index_type_by_heuristics(field_type, has_like, has_exact, has_range)

    query_str, params = sample_query

    # Compare index types using EXPLAIN
    index_types = ["btree", "hash", "gin"]
    comparisons = []

    for idx_type in index_types:
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
        return _select_index_type_by_heuristics(field_type, has_like, has_exact, has_range)

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
                return result.get("udt_name") or result.get("data_type")
            return None
        finally:
            cursor.close()


def _is_index_type_suitable(index_type: str, field_type: str) -> bool:
    """
    Check if index type is suitable for field type.

    Args:
        index_type: Index type (btree, hash, gin)
        field_type: PostgreSQL data type

    Returns:
        True if index type is suitable
    """
    field_type_lower = field_type.lower() if field_type else ""

    # Hash indexes: Only for equality comparisons, not for text/array types
    if index_type == "hash":
        # Hash indexes work well for integer, numeric, text (but limited use cases)
        # Not suitable for arrays, JSON, or text with LIKE patterns
        unsuitable_types = ["array", "json", "jsonb", "tsvector"]
        if any(unsuitable in field_type_lower for unsuitable in unsuitable_types):
            return False
        return True

    # GIN indexes: For arrays, JSONB, full-text search
    if index_type == "gin":
        suitable_types = ["array", "jsonb", "tsvector", "text"]
        if any(suitable in field_type_lower for suitable in suitable_types):
            return True
        return False

    # B-tree: Default, works for most types
    if index_type == "btree":
        return True

    return False


def _compare_index_type_with_explain(
    table_name: str,
    field_name: str,
    index_type: str,
    query_str: str,
    params: tuple,
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
    if has_exact and not has_like and not has_range:
        # Only for simple types
        if field_type_lower in ["integer", "bigint", "numeric", "text", "varchar"]:
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
        index_type: Index type (btree, hash, gin)
        has_tenant: Whether table has tenant_id field

    Returns:
        Tuple of (index_sql, index_name)
    """
    from src.validation import validate_field_name, validate_table_name

    validated_table = validate_table_name(table_name)
    validated_field = validate_field_name(field_name, table_name)

    # Generate index name
    type_suffix = f"_{index_type}" if index_type != "btree" else ""
    tenant_suffix = "_tenant" if has_tenant else ""
    index_name = f"idx_{table_name}_{field_name}{type_suffix}{tenant_suffix}"

    # Build index SQL
    if has_tenant:
        if index_type == "gin":
            # GIN indexes may need special handling for tenant_id
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON "{validated_table}" USING {index_type} (tenant_id, "{validated_field}")
            """
        else:
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON "{validated_table}" USING {index_type} (tenant_id, "{validated_field}")
            """
    else:
        index_sql = f"""
            CREATE INDEX IF NOT EXISTS "{index_name}"
            ON "{validated_table}" USING {index_type} ("{validated_field}")
        """

    return index_sql, index_name
