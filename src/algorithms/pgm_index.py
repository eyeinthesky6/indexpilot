"""PGM-Index (Piecewise Geometric Model) Algorithm Implementation

Based on "The PGM-index: a fully-dynamic compressed learned index with provable worst-case bounds"
arXiv:1910.06169

This module implements PGM-Index analysis for determining when learned indexes would be beneficial.
Since PostgreSQL doesn't natively support learned indexes, this provides analysis and recommendations
for when PGM-Index concepts would be most effective.

Algorithm concepts are not copyrightable; attribution provided as good practice.
See THIRD_PARTY_ATTRIBUTIONS.md for complete attribution.
"""

import logging
from typing import Any

from psycopg2 import sql

from src.config_loader import ConfigLoader
from src.db import get_cursor
from src.stats import get_table_row_count, get_table_size_info

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def analyze_pgm_index_suitability(
    table_name: str,
    field_name: str,
    query_patterns: dict[str, Any],
    read_write_ratio: float | None = None,
) -> dict[str, Any]:
    """
    Analyze if PGM-Index would be suitable for a given table/field combination.

    Based on "The PGM-index: a fully-dynamic compressed learned index with provable worst-case bounds"
    arXiv:1910.06169

    PGM-Index is most beneficial for:
    - Read-heavy workloads (high read/write ratio)
    - Large tables with predictable access patterns
    - Space-constrained environments (2-10x space savings)
    - Sequential or range queries

    Args:
        table_name: Table name
        field_name: Field name
        query_patterns: Query pattern information (has_range, has_exact, has_like, etc.)
        read_write_ratio: Optional read/write ratio (reads / writes). Higher = more read-heavy.

    Returns:
        dict with analysis results:
        - is_suitable: bool - Whether PGM-Index would be suitable
        - confidence: float - Confidence in suitability (0.0 to 1.0)
        - reason: str - Reason for suitability assessment
        - estimated_space_savings: float - Estimated space savings vs B-tree (0.0 to 1.0)
        - suitability_score: float - Overall suitability score (0.0 to 1.0)
        - recommendations: list[str] - List of recommendations
    """
    try:
        from src.validation import validate_field_name, validate_table_name

        _ = validate_table_name(table_name)  # Validation only
        _ = validate_field_name(field_name, table_name)  # Validation only
    except Exception as e:
        logger.debug(f"Invalid table/field for PGM-Index analysis: {e}")
        return {
            "is_suitable": False,
            "confidence": 0.0,
            "reason": "validation_failed",
            "estimated_space_savings": 0.0,
            "suitability_score": 0.0,
            "recommendations": ["Validation failed"],
        }

    # Get table statistics
    try:
        table_size_info = get_table_size_info(table_name)
        row_count = table_size_info.get("row_count", 0)
    except Exception as e:
        logger.debug(f"Failed to get table size info for PGM-Index analysis: {e}")
        row_count = 0

    # Get field data distribution (for learned index suitability)
    try:
        distribution_info = _get_field_distribution(table_name, field_name)
    except Exception as e:
        logger.debug(f"Failed to get field distribution: {e}")
        distribution_info = {
            "distinct_count": 0,
            "null_count": 0,
            "is_ordered": False,
            "distribution_type": "unknown",
        }

    # Analyze query patterns
    has_range = query_patterns.get("has_range", False)
    has_exact = query_patterns.get("has_exact", False)
    has_like = query_patterns.get("has_like", False)
    is_read_heavy = read_write_ratio is None or read_write_ratio >= 10.0

    # PGM-Index suitability factors
    suitability_factors: dict[str, float] = {}

    # Factor 1: Table size (larger tables benefit more from space savings)
    min_rows_for_pgm = _config_loader.get_int("features.pgm_index.min_rows", 10000)
    if row_count >= min_rows_for_pgm:
        # Larger tables benefit more (up to 0.3 points)
        if row_count >= 1000000:
            suitability_factors["table_size"] = 0.3
        elif row_count >= 100000:
            suitability_factors["table_size"] = 0.25
        else:
            suitability_factors["table_size"] = 0.2
    else:
        suitability_factors["table_size"] = 0.0

    # Factor 2: Read-heavy workload (PGM-Index excels at reads)
    if is_read_heavy:
        suitability_factors["read_heavy"] = 0.3
    elif read_write_ratio and read_write_ratio >= 5.0:
        suitability_factors["read_heavy"] = 0.2
    else:
        suitability_factors["read_heavy"] = 0.0

    # Factor 3: Query patterns (range queries benefit more)
    if has_range:
        suitability_factors["query_pattern"] = 0.2
    elif has_exact and not has_like:
        suitability_factors["query_pattern"] = 0.15
    else:
        suitability_factors["query_pattern"] = 0.1

    # Factor 4: Data distribution (ordered/semi-ordered data works better)
    if distribution_info.get("is_ordered", False):
        suitability_factors["distribution"] = 0.2
    elif distribution_info.get("distribution_type") == "sequential":
        suitability_factors["distribution"] = 0.15
    else:
        suitability_factors["distribution"] = 0.05

    # Calculate overall suitability score
    suitability_score = sum(suitability_factors.values())
    suitability_score = min(1.0, suitability_score)  # Cap at 1.0

    # Determine if suitable (threshold: 0.5)
    min_suitability = _config_loader.get_float("features.pgm_index.min_suitability", 0.5)
    is_suitable = suitability_score >= min_suitability

    # Estimate space savings (PGM-Index typically saves 50-80% space)
    if is_suitable:
        # Higher savings for larger, read-heavy tables
        if row_count >= 1000000 and is_read_heavy:
            estimated_space_savings = 0.75  # 75% savings
        elif row_count >= 100000:
            estimated_space_savings = 0.65  # 65% savings
        else:
            estimated_space_savings = 0.50  # 50% savings
    else:
        estimated_space_savings = 0.0

    # Calculate confidence
    confidence = suitability_score  # Use suitability score as confidence

    # Generate recommendations
    recommendations: list[str] = []
    if not is_suitable:
        if row_count < min_rows_for_pgm:
            recommendations.append(f"Table too small (need {min_rows_for_pgm}+ rows)")
        if not is_read_heavy:
            recommendations.append(
                "PGM-Index best for read-heavy workloads (10:1 read/write ratio)"
            )
        if not has_range and not has_exact:
            recommendations.append("PGM-Index works best with range or exact match queries")
    else:
        recommendations.append("PGM-Index would provide significant space savings")
        if estimated_space_savings >= 0.7:
            recommendations.append("High space savings potential (70%+)")
        if is_read_heavy:
            recommendations.append("Excellent for read-heavy workload")

    # Determine reason
    if is_suitable:
        reason = "suitable_for_pgm"
    elif row_count < min_rows_for_pgm:
        reason = "table_too_small"
    elif not is_read_heavy:
        reason = "not_read_heavy"
    else:
        reason = "low_suitability_score"

    return {
        "is_suitable": is_suitable,
        "confidence": confidence,
        "reason": reason,
        "estimated_space_savings": estimated_space_savings,
        "suitability_score": suitability_score,
        "suitability_factors": suitability_factors,
        "recommendations": recommendations,
        "row_count": row_count,
        "read_write_ratio": read_write_ratio,
        "distribution_info": distribution_info,
    }


def _get_field_distribution(table_name: str, field_name: str) -> dict[str, Any]:
    """
    Get field data distribution information for learned index analysis.

    Args:
        table_name: Table name
        field_name: Field name

    Returns:
        dict with distribution information:
        - distinct_count: int - Number of distinct values
        - null_count: int - Number of NULL values
        - is_ordered: bool - Whether data appears ordered
        - distribution_type: str - Type of distribution (sequential, random, etc.)
    """
    try:
        from src.validation import validate_field_name, validate_table_name

        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)
    except Exception:
        return {
            "distinct_count": 0,
            "null_count": 0,
            "is_ordered": False,
            "distribution_type": "unknown",
        }

    with get_cursor() as cursor:
        try:
            # Get distinct count and null count
            distinct_query = sql.SQL(
                """
                SELECT
                    COUNT(DISTINCT {}) as distinct_count,
                    COUNT(*) FILTER (WHERE {} IS NULL) as null_count,
                    COUNT(*) as total_count
                FROM {}
            """
            ).format(
                sql.Identifier(validated_field),
                sql.Identifier(validated_field),
                sql.Identifier(validated_table),
            )
            cursor.execute(distinct_query)
            result = cursor.fetchone()

            if not result:
                return {
                    "distinct_count": 0,
                    "null_count": 0,
                    "is_ordered": False,
                    "distribution_type": "unknown",
                }

            distinct_count = result.get("distinct_count", 0) or 0
            null_count = result.get("null_count", 0) or 0
            total_count = result.get("total_count", 0) or 0

            # Check if data appears ordered (sample-based check)
            # For learned indexes, ordered/semi-ordered data works better
            is_ordered = False
            distribution_type = "random"

            if total_count > 100:
                # Sample first and last values to check ordering
                sample_query = sql.SQL(
                    """
                    SELECT
                        MIN({}) as min_val,
                        MAX({}) as max_val,
                        COUNT(*) as sample_count
                    FROM (
                        SELECT {}
                        FROM {}
                        WHERE {} IS NOT NULL
                        ORDER BY {}
                        LIMIT 1000
                    ) sample
                """
                ).format(
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_table),
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_field),
                )
                cursor.execute(sample_query)
                sample_result = cursor.fetchone()

                if sample_result and sample_result.get("sample_count", 0) > 10:
                    # If we have enough distinct values relative to total, might be sequential
                    distinct_ratio = (
                        float(distinct_count) / float(total_count) if total_count > 0 else 0.0
                    )
                    if distinct_ratio > 0.8:  # High distinct ratio suggests sequential/ordered
                        is_ordered = True
                        distribution_type = "sequential"
                    elif distinct_ratio > 0.5:
                        distribution_type = "semi_ordered"

            return {
                "distinct_count": distinct_count,
                "null_count": null_count,
                "is_ordered": is_ordered,
                "distribution_type": distribution_type,
            }
        except Exception as e:
            logger.debug(f"Error getting field distribution: {e}")
            return {
                "distinct_count": 0,
                "null_count": 0,
                "is_ordered": False,
                "distribution_type": "unknown",
            }
        finally:
            cursor.close()


def estimate_pgm_index_cost(
    table_name: str, field_name: str, row_count: int | None = None
) -> dict[str, Any]:
    """
    Estimate the cost and benefits of creating a PGM-Index.

    Args:
        table_name: Table name
        field_name: Field name
        row_count: Optional row count (will be fetched if not provided)

    Returns:
        dict with cost estimates:
        - build_cost: float - Estimated build cost
        - estimated_size_bytes: float - Estimated index size in bytes
        - space_savings_vs_btree: float - Space savings vs B-tree (0.0 to 1.0)
        - maintenance_cost: float - Estimated maintenance cost
    """
    if row_count is None:
        row_count = get_table_row_count(table_name)

    # PGM-Index build cost is similar to B-tree but with better compression
    # Build cost scales with row count
    build_cost_per_1000 = _config_loader.get_float(
        "features.pgm_index.build_cost_per_1000_rows", 0.8
    )
    build_cost = (row_count / 1000.0) * build_cost_per_1000

    # Estimate index size (PGM-Index is 2-10x smaller than B-tree)
    # Assume average 8 bytes per row for B-tree, then apply PGM compression
    estimated_btree_size = row_count * 8  # Rough estimate
    pgm_compression_ratio = _config_loader.get_float("features.pgm_index.compression_ratio", 0.3)
    estimated_size_bytes = estimated_btree_size * pgm_compression_ratio

    # Space savings vs B-tree
    space_savings_vs_btree = 1.0 - pgm_compression_ratio

    # Maintenance cost (PGM-Index has lower maintenance for read-heavy workloads)
    maintenance_cost = build_cost * 0.1  # Lower maintenance overhead

    return {
        "build_cost": build_cost,
        "estimated_size_bytes": estimated_size_bytes,
        "space_savings_vs_btree": space_savings_vs_btree,
        "maintenance_cost": maintenance_cost,
    }
