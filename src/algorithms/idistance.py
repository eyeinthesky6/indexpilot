"""iDistance Algorithm Implementation

Based on iDistance multi-dimensional indexing technique for efficient k-nearest neighbor (kNN) queries.

This module implements iDistance concepts for multi-dimensional query pattern detection and analysis,
helping to:
- Identify multi-dimensional query patterns that would benefit from iDistance-like behavior
- Analyze query characteristics (k-NN, range queries, high-dimensional data)
- Recommend PostgreSQL index strategies for multi-dimensional queries

iDistance benefits:
- Efficient k-NN queries in high-dimensional spaces
- Maps multi-dimensional data to one dimension using reference points
- Handles skewed data distributions effectively
- Uses B+-tree for indexing the mapped space

Note: PostgreSQL doesn't natively support iDistance indexes, but this module provides
analysis and recommendations for multi-dimensional query optimization strategies.

Algorithm concepts are not copyrightable; attribution provided as good practice.
See THIRD_PARTY_ATTRIBUTIONS.md for complete attribution.
"""

import logging
from typing import cast

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.stats import get_table_row_count
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def analyze_idistance_suitability(
    table_name: str,
    field_names: list[str],
    query_patterns: JSONDict,
) -> JSONDict:
    """
    Analyze if iDistance strategy would be beneficial for multi-dimensional queries.

    iDistance is beneficial for:
    - Multi-dimensional queries (queries involving multiple fields)
    - k-NN (k-nearest neighbor) queries
    - High-dimensional data spaces
    - Skewed data distributions
    - Range queries across multiple dimensions

    Args:
        table_name: Table name
        field_names: List of field names involved in multi-dimensional query
        query_patterns: Query pattern information (has_knn, has_range, dimensions, etc.)

    Returns:
        dict with iDistance analysis:
        - is_suitable: bool - Whether iDistance strategy is recommended
        - confidence: float - Confidence in recommendation (0.0 to 1.0)
        - reason: str - Reason for recommendation
        - dimensions: int - Number of dimensions detected
        - query_characteristics: dict - Query pattern analysis
        - recommendations: list[str] - List of recommendations
    """
    try:
        from src.validation import validate_table_name

        _ = validate_table_name(table_name)  # Validation only
    except Exception as e:
        logger.debug(f"Invalid table for iDistance analysis: {e}")
        return {
            "is_suitable": False,
            "confidence": 0.0,
            "reason": "validation_failed",
            "dimensions": 0,
            "query_characteristics": {},
            "recommendations": ["Validation failed"],
        }

    # Analyze query patterns
    has_knn_val = query_patterns.get("has_knn", False)
    has_range_val = query_patterns.get("has_range", False)
    has_multi_field_val = query_patterns.get("has_multi_field", False)
    dimensions_val = query_patterns.get("dimensions", len(field_names) if field_names else 0)
    has_knn = bool(has_knn_val) if isinstance(has_knn_val, bool) else False
    has_range = bool(has_range_val) if isinstance(has_range_val, bool) else False
    has_multi_field = bool(has_multi_field_val) if isinstance(has_multi_field_val, bool) else False
    dimensions = (
        int(dimensions_val)
        if isinstance(dimensions_val, (int, float))
        else (len(field_names) if field_names else 0)
    )

    # Get table statistics
    try:
        table_row_count = get_table_row_count(table_name)
    except Exception as e:
        logger.debug(f"Failed to get table row count: {e}")
        table_row_count = 0

    # iDistance suitability factors
    suitability_factors: dict[str, float] = {}

    # Factor 1: Multi-dimensional queries (iDistance is designed for this)
    if has_multi_field and dimensions >= 2:
        if dimensions >= 3:
            suitability_factors["multi_dimensional"] = 0.3  # High-dimensional
        else:
            suitability_factors["multi_dimensional"] = 0.2  # 2D
    else:
        suitability_factors["multi_dimensional"] = 0.0

    # Factor 2: k-NN queries (iDistance excels at this)
    if has_knn:
        suitability_factors["knn_queries"] = 0.3
    else:
        suitability_factors["knn_queries"] = 0.0

    # Factor 3: Range queries (iDistance supports this)
    if has_range:
        suitability_factors["range_queries"] = 0.2
    else:
        suitability_factors["range_queries"] = 0.1  # Still useful for range

    # Factor 4: Table size (larger tables benefit more)
    min_rows_for_idistance_val = _config_loader.get_int("features.idistance.min_table_rows", 1000)
    min_rows_for_idistance = (
        int(min_rows_for_idistance_val)
        if isinstance(min_rows_for_idistance_val, (int, float))
        else 1000
    )
    if table_row_count >= min_rows_for_idistance:
        if table_row_count >= 100000:
            suitability_factors["table_size"] = 0.2
        else:
            suitability_factors["table_size"] = 0.1
    else:
        suitability_factors["table_size"] = 0.0

    # Calculate overall suitability score
    suitability_score = sum(suitability_factors.values())
    suitability_score = min(1.0, suitability_score)  # Cap at 1.0

    # Determine if suitable (threshold: 0.5)
    min_suitability_val = _config_loader.get_float("features.idistance.min_suitability", 0.5)
    min_suitability = (
        float(min_suitability_val)
        if isinstance(min_suitability_val, (int, float))
        else 0.5
    )
    is_suitable = suitability_score >= min_suitability

    # Calculate confidence
    confidence = suitability_score

    # Generate recommendations
    recommendations: list[str] = []
    if not is_suitable:
        if not has_multi_field or dimensions < 2:
            recommendations.append("iDistance requires multi-dimensional queries (2+ fields)")
        if not has_knn and not has_range:
            recommendations.append("iDistance best for k-NN or range queries")
        if table_row_count < min_rows_for_idistance:
            recommendations.append(f"Table too small (need {min_rows_for_idistance}+ rows)")
    else:
        recommendations.append("iDistance strategy would benefit multi-dimensional queries")
        if has_knn:
            recommendations.append("Excellent for k-NN queries")
        if dimensions >= 3:
            recommendations.append("High-dimensional queries benefit significantly")

    # Determine reason
    if is_suitable:
        reason = "suitable_for_idistance"
    elif not has_multi_field or dimensions < 2:
        reason = "not_multi_dimensional"
    elif not has_knn and not has_range:
        reason = "unsuitable_query_pattern"
    else:
        reason = "low_suitability_score"

    # Convert suitability_factors to JSONDict (float values are JSONValue)
    suitability_factors_dict: JSONDict = {k: float(v) for k, v in suitability_factors.items()}
    
    # Convert recommendations to list[JSONValue] (str values are JSONValue)
    recommendations_list: list[JSONValue] = [str(r) for r in recommendations]
    
    return {
        "is_suitable": is_suitable,
        "confidence": confidence,
        "reason": reason,
        "dimensions": dimensions,
        "suitability_score": suitability_score,
        "suitability_factors": suitability_factors_dict,
        "query_characteristics": {
            "has_knn": has_knn,
            "has_range": has_range,
            "has_multi_field": has_multi_field,
            "field_count": len(field_names) if field_names else 0,
        },
        "recommendations": recommendations_list,
        "table_row_count": table_row_count,
    }


def detect_multi_dimensional_pattern(
    table_name: str, query_text: str | None = None, field_names: list[str] | None = None
) -> JSONDict:
    """
    Detect multi-dimensional query patterns that would benefit from iDistance.

    Args:
        table_name: Table name
        query_text: Optional query text to analyze
        field_names: Optional list of field names to check

    Returns:
        dict with pattern detection results:
        - is_multi_dimensional: bool - Whether query involves multiple dimensions
        - dimensions: int - Number of dimensions detected
        - has_knn: bool - Whether query appears to be k-NN
        - has_range: bool - Whether query has range conditions
        - field_names: list[str] - Fields involved
    """
    try:
        from src.validation import validate_table_name

        validated_table = validate_table_name(table_name)
    except Exception as e:
        logger.debug(f"Invalid table for multi-dimensional pattern detection: {e}")
        return {
            "is_multi_dimensional": False,
            "dimensions": 0,
            "has_knn": False,
            "has_range": False,
            "field_names": [],
        }

    # If field names provided, analyze them
    if field_names and len(field_names) >= 2:
        # Check if fields exist and get their types
        dimensions = 0
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                for field_name in field_names:
                    try:
                        from src.validation import validate_field_name

                        validated_field = validate_field_name(field_name, table_name)
                        cursor.execute(
                            """
                            SELECT data_type
                            FROM information_schema.columns
                            WHERE table_name = %s AND column_name = %s
                        """,
                            (validated_table, validated_field),
                        )
                        result = cursor.fetchone()
                        if result and isinstance(result, dict):
                            dimensions += 1
                    except Exception:
                        continue
            finally:
                cursor.close()

        # Convert field_names to list[JSONValue] (str values are JSONValue)
        field_names_list: list[JSONValue] = [
            str(fn) for fn in (field_names[:dimensions] if field_names else [])
        ]
        return {
            "is_multi_dimensional": dimensions >= 2,
            "dimensions": dimensions,
            "has_knn": False,  # Would need query analysis to detect
            "has_range": False,  # Would need query analysis to detect
            "field_names": field_names_list,
        }

    # If query text provided, try to analyze it
    if query_text:
        # Simple pattern detection (could be enhanced)
        query_lower = query_text.lower()
        has_knn = any(
            keyword in query_lower
            for keyword in ["nearest", "knn", "k-nn", "distance", "similar", "closest"]
        )
        has_range = any(
            keyword in query_lower for keyword in ["between", ">=", "<=", ">", "<", "range"]
        )

        # Count field references (simple heuristic)
        # This is a basic implementation - could be enhanced with SQL parsing
        field_count = 0
        if field_names:
            field_count = sum(1 for field in field_names if field.lower() in query_lower)

        return {
            "is_multi_dimensional": field_count >= 2,
            "dimensions": field_count,
            "has_knn": has_knn,
            "has_range": has_range,
            "field_names": [str(fn) for fn in (field_names[:field_count] if field_names else [])],
        }

    # Default: not multi-dimensional
    return {
        "is_multi_dimensional": False,
        "dimensions": 0,
        "has_knn": False,
        "has_range": False,
        "field_names": [],
    }


def get_idistance_index_recommendation(
    table_name: str,
    field_names: list[str],
    query_patterns: JSONDict,
) -> JSONDict:
    """
    Get iDistance-based index recommendation for multi-dimensional queries.

    Since PostgreSQL doesn't natively support iDistance indexes, this function:
    1. Identifies when iDistance strategy would be beneficial
    2. Analyzes multi-dimensional query patterns
    3. Suggests PostgreSQL index strategies that approximate iDistance benefits

    Args:
        table_name: Table name
        field_names: List of field names involved in query
        query_patterns: Query pattern information

    Returns:
        dict with recommendation:
        - use_idistance_strategy: bool - Whether to use iDistance-like approach
        - index_type: str - Recommended index type
        - confidence: float - Confidence in recommendation
        - reason: str - Reason for recommendation
        - idistance_insights: dict - iDistance-specific insights
    """
    try:
        # Analyze iDistance suitability
        idistance_analysis = analyze_idistance_suitability(
            table_name=table_name,
            field_names=field_names,
            query_patterns=query_patterns,
        )

        is_suitable = idistance_analysis.get("is_suitable", False)
        if not is_suitable:
            # iDistance not recommended, return standard recommendation
            confidence_val = idistance_analysis.get("confidence", 0.0)
            reason_val = idistance_analysis.get("reason", "standard_indexing")
            confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.0
            reason = str(reason_val) if isinstance(reason_val, str) else "standard_indexing"
            return {
                "use_idistance_strategy": False,
                "index_type": "btree",
                "confidence": confidence,
                "reason": reason,
                "idistance_insights": idistance_analysis,
            }

        # iDistance strategy is recommended
        dimensions_val = idistance_analysis.get(
            "dimensions", len(field_names) if field_names else 0
        )
        dimensions = (
            int(dimensions_val)
            if isinstance(dimensions_val, (int, float))
            else (len(field_names) if field_names else 0)
        )

        # For multi-dimensional queries, PostgreSQL options:
        # 1. Composite B-tree index (for equality and range)
        # 2. GIN index (for array/JSONB multi-dimensional data)
        # 3. GiST index (for geometric/spatial data)

        # Check field types to determine best strategy
        field_types = _get_field_types(table_name, field_names)
        has_geometric = any(
            "point" in str(ft).lower() or "geometry" in str(ft).lower() for ft in field_types
        )
        has_array = any("array" in str(ft).lower() for ft in field_types)

        if has_geometric and dimensions >= 2:
            # GiST index for spatial/geometric multi-dimensional queries
            confidence_val = idistance_analysis.get("confidence", 0.7)
            confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.7
            return {
                "use_idistance_strategy": True,
                "index_type": "gist",
                "confidence": confidence,
                "reason": "idistance_strategy_geometric",
                "recommendation_detail": (
                    "iDistance strategy: GiST index recommended for geometric multi-dimensional queries "
                    "(efficient for spatial k-NN and range queries, similar to iDistance benefits)"
                ),
                "idistance_insights": idistance_analysis,
            }

        if has_array and dimensions >= 2:
            # GIN index for array-based multi-dimensional data
            confidence_val = idistance_analysis.get("confidence", 0.7)
            confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.7
            return {
                "use_idistance_strategy": True,
                "index_type": "gin",
                "confidence": confidence,
                "reason": "idistance_strategy_array",
                "recommendation_detail": (
                    "iDistance strategy: GIN index recommended for array-based multi-dimensional queries "
                    "(efficient for array containment and overlap, similar to iDistance mapping benefits)"
                ),
                "idistance_insights": idistance_analysis,
            }

        # Default: Composite B-tree index for multi-dimensional queries
        # This approximates iDistance's one-dimensional mapping with B+-tree
        confidence_val = idistance_analysis.get("confidence", 0.7)
        confidence = float(confidence_val) if isinstance(confidence_val, (int, float)) else 0.7
        return {
            "use_idistance_strategy": True,
            "index_type": "btree",
            "confidence": confidence,
            "reason": "idistance_strategy_composite",
            "recommendation_detail": (
                "iDistance strategy: Composite B-tree index recommended for multi-dimensional queries "
                "(maps multiple dimensions to index key, similar to iDistance's one-dimensional mapping)"
            ),
            "idistance_insights": idistance_analysis,
        }

    except Exception as e:
        logger.error(f"Error in get_idistance_index_recommendation for {table_name}: {e}")
        return {
            "use_idistance_strategy": False,
            "index_type": "btree",
            "confidence": 0.0,
            "reason": "analysis_failed",
            "idistance_insights": {},
        }


def _get_field_types(table_name: str, field_names: list[str]) -> list[str]:
    """Get PostgreSQL data types for a list of fields."""
    field_types: list[str] = []
    try:
        from src.validation import validate_table_name

        validated_table = validate_table_name(table_name)
    except Exception:
        return []

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            for field_name in field_names:
                try:
                    from src.validation import validate_field_name

                    validated_field = validate_field_name(field_name, table_name)
                    cursor.execute(
                        """
                        SELECT data_type, udt_name
                        FROM information_schema.columns
                        WHERE table_name = %s AND column_name = %s
                    """,
                        (validated_table, validated_field),
                    )
                    result = cursor.fetchone()
                    if result and isinstance(result, dict):
                        udt_name_val = result.get("udt_name")
                        data_type_val = result.get("data_type")
                        udt_name = str(udt_name_val) if udt_name_val else None
                        data_type = str(data_type_val) if data_type_val else None
                        field_type = udt_name if udt_name else data_type if data_type else "unknown"
                        field_types.append(field_type)
                except Exception:
                    continue
        finally:
            cursor.close()

    return field_types
