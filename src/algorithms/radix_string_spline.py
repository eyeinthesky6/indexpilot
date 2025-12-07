"""RadixStringSpline (RSS) Algorithm Implementation

Based on "Bounding the Last Mile: Efficient Learned String Indexing"
arXiv:2111.14905

This module implements RadixStringSpline concepts for efficient string indexing, helping to:
- Identify string fields that would benefit from RSS-like behavior
- Recommend index strategies for string queries (email, name searches, etc.)
- Provide memory-efficient indexing recommendations for string fields

RSS uses minimal string prefixes for efficient indexing, providing:
- Comparable performance with less memory (40-60% storage savings)
- Fast hash-table lookups
- Bounded-error searches
- Efficient for dynamic string workloads

Algorithm concepts are not copyrightable; attribution provided as good practice.
See THIRD_PARTY_ATTRIBUTIONS.md for complete attribution.
"""

import logging

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.stats import get_table_row_count
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def should_use_rss_strategy(
    table_name: str,
    field_name: str,
    field_type: str,
    query_patterns: JSONDict,
) -> JSONDict:
    """
    Determine if RadixStringSpline strategy would be beneficial for this string field.

    Based on "Bounding the Last Mile: Efficient Learned String Indexing"
    arXiv:2111.14905

    RSS is beneficial for:
    - String/text fields (varchar, text, char)
    - High cardinality string fields
    - Frequent string equality and prefix searches
    - Fields with long string values
    - Memory-constrained environments

    Args:
        table_name: Table name
        field_name: Field name
        field_type: PostgreSQL data type
        query_patterns: Query pattern information

    Returns:
        dict with RSS recommendation:
        - should_use_rss: bool - Whether RSS strategy is recommended
        - confidence: float - Confidence in recommendation (0.0 to 1.0)
        - reason: str - Reason for recommendation
        - field_characteristics: dict - Field analysis details
        - recommendation: str - Specific recommendation
    """
    try:
        # Check if field type is suitable for RSS (string types)
        field_type_lower = field_type.lower() if field_type else ""
        is_string_type = any(
            string_type in field_type_lower
            for string_type in ["text", "varchar", "char", "character"]
        )

        if not is_string_type:
            return {
                "should_use_rss": False,
                "confidence": 0.0,
                "reason": "not_string_type",
                "field_characteristics": {"field_type": field_type},
                "recommendation": "rss_not_applicable",
                "recommendation_detail": "RSS is only applicable to string/text fields",
            }

        # Get table size
        table_row_count = get_table_row_count(table_name)

        # Get field characteristics
        field_chars = _analyze_string_field_characteristics(table_name, field_name, field_type)

        # RSS configuration thresholds
        min_table_size_for_rss = _config_loader.get_int(
            "features.radix_string_spline.min_table_size", 1000
        )
        min_cardinality_for_rss = _config_loader.get_float(
            "features.radix_string_spline.min_cardinality_ratio", 0.1
        )
        min_avg_length_for_rss = _config_loader.get_int(
            "features.radix_string_spline.min_avg_string_length", 10
        )

        # Analyze query patterns
        has_exact_val = query_patterns.get("has_exact", False)
        has_exact = bool(has_exact_val) if isinstance(has_exact_val, (bool, int, float)) else False
        has_like_val = query_patterns.get("has_like", False)
        has_like = bool(has_like_val) if isinstance(has_like_val, (bool, int, float)) else False
        has_prefix_val = query_patterns.get("has_prefix", False)
        has_prefix_bool = bool(has_prefix_val) if isinstance(has_prefix_val, (bool, int, float)) else False
        has_like_prefix_val = query_patterns.get("has_like_prefix", False)
        has_like_prefix_bool = bool(has_like_prefix_val) if isinstance(has_like_prefix_val, (bool, int, float)) else False
        has_prefix = has_prefix_bool or has_like_prefix_bool

        # Calculate RSS suitability score
        # RSS benefits from:
        # 1. String field type (required)
        # 2. High cardinality (RSS uses minimal prefixes efficiently)
        # 3. Long string values (more memory savings)
        # 4. Equality and prefix searches (RSS strengths)
        # 5. Large tables (more benefit from memory savings)
        rss_score = 0.0
        reasons = []

        # Factor 1: String type (required, already checked)
        rss_score += 0.2
        reasons.append("string_field_type")

        # Factor 2: High cardinality (RSS handles high cardinality well)
        cardinality_ratio_val = field_chars.get("cardinality_ratio", 0.0)
        cardinality_ratio = float(cardinality_ratio_val) if isinstance(cardinality_ratio_val, (int, float)) else 0.0
        if cardinality_ratio >= min_cardinality_for_rss:
            rss_score += 0.3
            reasons.append(f"high_cardinality ({cardinality_ratio:.1%} distinct)")

        # Factor 3: Long string values (more memory savings)
        avg_length_val = field_chars.get("avg_length", 0)
        avg_length = int(avg_length_val) if isinstance(avg_length_val, (int, float)) else 0
        if avg_length >= min_avg_length_for_rss:
            rss_score += 0.2
            reasons.append(f"long_strings (avg {avg_length} chars)")

        # Factor 4: Suitable query patterns (equality, prefix searches)
        if has_exact or has_prefix:
            rss_score += 0.2
            reasons.append("equality_or_prefix_searches")

        # Factor 5: Large table (more benefit from memory savings)
        if table_row_count >= min_table_size_for_rss:
            rss_score += 0.1
            reasons.append(f"large_table ({table_row_count} rows)")

        # Check if RSS strategy is recommended
        min_rss_score = _config_loader.get_float(
            "features.radix_string_spline.min_suitability_score", 0.5
        )
        should_use = rss_score >= min_rss_score
        confidence = min(rss_score, 1.0)

        # Generate recommendation
        if should_use:
            recommendation = "rss_strategy_recommended"
            recommendation_detail = (
                f"String field with high cardinality ({cardinality_ratio:.1%} distinct) "
                f"and long values (avg {avg_length} chars) benefits from "
                "RSS-like memory-efficient indexing strategy"
            )
        else:
            recommendation = "rss_strategy_not_recommended"
            if cardinality_ratio < min_cardinality_for_rss:
                recommendation_detail = (
                    f"Low cardinality ({cardinality_ratio:.1%} distinct) - "
                    "standard B-tree indexing sufficient"
                )
            elif avg_length < min_avg_length_for_rss:
                recommendation_detail = (
                    f"Short string values (avg {avg_length} chars) - "
                    "RSS benefits minimal, standard indexing sufficient"
                )
            else:
                recommendation_detail = (
                    "Standard indexing strategy sufficient for this string field"
                )

        return {
            "should_use_rss": should_use,
            "confidence": confidence,
            "reason": "; ".join(reasons) if reasons else "standard_string_field",
            "field_characteristics": {
                "field_type": field_type,
                "cardinality_ratio": cardinality_ratio,
                "avg_length": avg_length,
                "table_row_count": table_row_count,
                "has_exact": has_exact,
                "has_like": has_like,
                "has_prefix": has_prefix,
                "rss_score": rss_score,
            },
            "recommendation": recommendation,
            "recommendation_detail": recommendation_detail,
        }

    except Exception as e:
        logger.error(f"Error in should_use_rss_strategy for {table_name}.{field_name}: {e}")
        return {
            "should_use_rss": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "field_characteristics": {},
            "recommendation": "error",
        }


def _analyze_string_field_characteristics(
    table_name: str, field_name: str, field_type: str
) -> JSONDict:
    """
    Analyze string field characteristics for RSS suitability.

    Args:
        table_name: Table name
        field_name: Field name
        field_type: PostgreSQL data type

    Returns:
        dict with field characteristics:
        - cardinality_ratio: float - Ratio of distinct values to total rows
        - avg_length: int - Average string length
        - max_length: int - Maximum string length
    """
    try:
        from src.validation import validate_field_name, validate_table_name

        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get total row count
                from psycopg2 import sql

                count_query = sql.SQL("SELECT COUNT(*) as total FROM {}").format(
                    sql.Identifier(validated_table)
                )
                cursor.execute(count_query)
                total_result = cursor.fetchone()
                total_rows_val = total_result.get("total", 0) if total_result else 0
                total_rows = int(total_rows_val) if isinstance(total_rows_val, (int, float)) else 0

                if total_rows == 0:
                    return {
                        "cardinality_ratio": 0.0,
                        "avg_length": 0,
                        "max_length": 0,
                    }

                # Get distinct count and string length statistics
                stats_query = sql.SQL(
                    """
                    SELECT
                        COUNT(DISTINCT {}) as distinct_count,
                        AVG(LENGTH({})) as avg_length,
                        MAX(LENGTH({})) as max_length
                    FROM {}
                """
                ).format(
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_table),
                )
                cursor.execute(stats_query)
                stats_result = cursor.fetchone()

                if stats_result:
                    distinct_count_val = stats_result.get("distinct_count", 0)
                    distinct_count = int(distinct_count_val) if isinstance(distinct_count_val, (int, float)) else 0
                    avg_length_val = stats_result.get("avg_length", 0)
                    avg_length = int(avg_length_val) if isinstance(avg_length_val, (int, float)) else 0
                    max_length_val = stats_result.get("max_length", 0)
                    max_length = int(max_length_val) if isinstance(max_length_val, (int, float)) else 0

                    cardinality_ratio = (
                        float(distinct_count) / float(total_rows) if total_rows > 0 else 0.0
                    )

                    return {
                        "cardinality_ratio": cardinality_ratio,
                        "avg_length": int(avg_length) if avg_length else 0,
                        "max_length": int(max_length) if max_length else 0,
                    }

                return {
                    "cardinality_ratio": 0.0,
                    "avg_length": 0,
                    "max_length": 0,
                }
            finally:
                cursor.close()
    except Exception as e:
        logger.debug(f"Error analyzing string field characteristics: {e}")
        return {
            "cardinality_ratio": 0.0,
            "avg_length": 0,
            "max_length": 0,
        }


def get_rss_index_recommendation(
    table_name: str,
    field_name: str,
    field_type: str,
    query_patterns: JSONDict,
) -> JSONDict:
    """
    Get RadixStringSpline-based index type recommendation for string fields.

    Since PostgreSQL doesn't natively support learned indexes, this function:
    1. Identifies when RSS strategy would be beneficial
    2. Recommends PostgreSQL index types that provide similar benefits
    3. Suggests index strategies that mimic RSS advantages

    Args:
        table_name: Table name
        field_name: Field name
        field_type: PostgreSQL data type
        query_patterns: Query pattern information

    Returns:
        dict with index recommendation:
        - index_type: str - Recommended index type (btree, hash, etc.)
        - use_rss_strategy: bool - Whether to use RSS-like approach
        - confidence: float - Confidence in recommendation
        - reason: str - Reason for recommendation
        - rss_insights: dict - RSS-specific insights
    """
    try:
        # Check if RSS strategy is recommended
        rss_analysis = should_use_rss_strategy(
            table_name=table_name,
            field_name=field_name,
            field_type=field_type,
            query_patterns=query_patterns,
        )

        should_use_rss_val = rss_analysis.get("should_use_rss", False)
        should_use_rss = bool(should_use_rss_val) if isinstance(should_use_rss_val, (bool, int, float)) else False
        if not should_use_rss:
            # RSS not recommended, return standard recommendation
            confidence_val = rss_analysis.get("confidence", 0.0)
            confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.0
            reason_val = rss_analysis.get("recommendation_detail", "standard_indexing")
            reason = str(reason_val) if isinstance(reason_val, str) else "standard_indexing"
            return {
                "index_type": "btree",
                "use_rss_strategy": False,
                "confidence": 1.0 - confidence,
                "reason": reason,
                "rss_insights": rss_analysis,
            }

        # RSS strategy is recommended
        has_exact_val = query_patterns.get("has_exact", False)
        has_exact = bool(has_exact_val) if isinstance(has_exact_val, (bool, int, float)) else False
        has_like_val = query_patterns.get("has_like", False)
        has_like = bool(has_like_val) if isinstance(has_like_val, (bool, int, float)) else False
        has_prefix_val = query_patterns.get("has_prefix", False)
        has_prefix_bool = bool(has_prefix_val) if isinstance(has_prefix_val, (bool, int, float)) else False
        has_like_prefix_val = query_patterns.get("has_like_prefix", False)
        has_like_prefix_bool = bool(has_like_prefix_val) if isinstance(has_like_prefix_val, (bool, int, float)) else False
        has_prefix = has_prefix_bool or has_like_prefix_bool

        # For string fields, RSS benefits:
        # - Memory-efficient indexing (minimal prefixes)
        # - Fast equality lookups
        # - Efficient prefix searches

        # Strategy 1: For equality-only queries, hash can be beneficial
        # (though PostgreSQL discourages hash indexes)
        if has_exact and not has_like and not has_prefix:
            confidence_val = rss_analysis.get("confidence", 0.7)
            confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.7
            return {
                "index_type": "hash",
                "use_rss_strategy": True,
                "confidence": confidence,
                "reason": (
                    "RSS strategy: Hash index recommended for string equality queries "
                    "(fast lookups, similar to RSS hash-table benefits)"
                ),
                "rss_insights": rss_analysis,
                "strategy_note": (
                    "Note: Hash indexes have limitations in PostgreSQL (no WAL-logging, "
                    "no replication). Consider B-tree with expression index as alternative."
                ),
            }

        # Strategy 2: For prefix searches, expression index on substring
        if has_prefix or has_like:
            confidence_val = rss_analysis.get("confidence", 0.7)
            confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.7
            return {
                "index_type": "btree",
                "use_rss_strategy": True,
                "confidence": confidence,
                "reason": (
                    "RSS strategy: B-tree with expression index recommended for string prefix searches "
                    "(efficient prefix matching, similar to RSS minimal prefix approach)"
                ),
                "rss_insights": rss_analysis,
                "strategy_recommendations": [
                    "Consider expression index on LEFT(field, N) for prefix searches",
                    "Use LOWER(field) expression index for case-insensitive searches",
                    "Monitor index size and consider partial indexes for filtered queries",
                    "Consider covering indexes to reduce index maintenance overhead",
                ],
            }

        # Default: B-tree with RSS-like considerations
        # RSS provides memory-efficient indexing, which we can approximate with:
        # - Expression indexes for specific patterns
        # - Partial indexes to reduce index size
        # - Careful index selection to minimize memory usage

        confidence_val = rss_analysis.get("confidence", 0.7)
        confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.7
        return {
            "index_type": "btree",
            "use_rss_strategy": True,
            "confidence": confidence,
            "reason": (
                "RSS strategy: B-tree recommended with memory-efficiency considerations "
                "(use expression/partial indexes where beneficial to reduce storage)"
            ),
            "rss_insights": rss_analysis,
            "strategy_recommendations": [
                "Consider expression indexes for specific string patterns (reduces index size)",
                "Use partial indexes for filtered queries (reduces memory usage)",
                "Monitor index size and adjust based on memory constraints",
                "Consider covering indexes to reduce index maintenance overhead",
            ],
        }

    except Exception as e:
        logger.error(f"Error in get_rss_index_recommendation for {table_name}.{field_name}: {e}")
        return {
            "index_type": "btree",
            "use_rss_strategy": False,
            "confidence": 0.0,
            "reason": f"error: {str(e)}",
            "rss_insights": {},
        }
