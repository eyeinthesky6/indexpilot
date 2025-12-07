"""Cortex (Data Correlation Exploitation) Algorithm Implementation

Based on "Cortex: Leveraging Correlation for Efficient Data Analytics"
arXiv:2012.06683

This module implements Cortex concepts for multi-attribute correlation detection,
helping to identify composite index opportunities based on data correlations.
"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_cortex_enabled() -> bool:
    """Check if Cortex enhancement is enabled"""
    return _config_loader.get_bool("features.cortex.enabled", True)


def get_cortex_config() -> dict[str, Any]:
    """Get Cortex configuration"""
    return {
        "enabled": is_cortex_enabled(),
        "correlation_threshold": _config_loader.get_float(
            "features.cortex.correlation_threshold", 0.7
        ),
        "min_correlation_samples": _config_loader.get_int(
            "features.cortex.min_correlation_samples", 100
        ),
        "use_mutual_information": _config_loader.get_bool(
            "features.cortex.use_mutual_information", True
        ),
    }


def calculate_correlation(table_name: str, column1: str, column2: str) -> dict[str, Any] | None:
    """
    Calculate correlation between two columns using statistical methods.

    Cortex leverages data correlations to extend primary indexes.

    Args:
        table_name: Table name
        column1: First column
        column2: Second column

    Returns:
        dict with correlation information or None if calculation fails
    """
    if not is_cortex_enabled():
        return None

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get sample data for correlation analysis
                # Use a sample to avoid full table scans on large tables
                sample_size = _config_loader.get_int("features.cortex.sample_size", 10000)

                cursor.execute(
                    f"""
                    SELECT
                        {column1},
                        {column2},
                        COUNT(*) as frequency
                    FROM (
                        SELECT {column1}, {column2}
                        FROM {table_name}
                        WHERE {column1} IS NOT NULL AND {column2} IS NOT NULL
                        LIMIT %s
                    ) sample
                    GROUP BY {column1}, {column2}
                    ORDER BY frequency DESC
                    LIMIT 100
                    """,
                    (sample_size,),
                )

                samples = cursor.fetchall()
                if len(samples) < 10:  # Need minimum samples
                    return None

                # Calculate correlation metrics
                # For simplicity, we'll use co-occurrence frequency as a proxy for correlation
                # In a full implementation, we'd use mutual information or chi-squared test

                total_samples = sum(s["frequency"] for s in samples)
                unique_pairs = len(samples)

                # High correlation: few unique pairs relative to total samples
                # Low correlation: many unique pairs relative to total samples
                correlation_score = (
                    1.0 - (unique_pairs / total_samples) if total_samples > 0 else 0.0
                )

                # Normalize to 0-1 range
                correlation_score = max(0.0, min(1.0, correlation_score))

                config = get_cortex_config()
                threshold = config.get("correlation_threshold", 0.7)

                return {
                    "column1": column1,
                    "column2": column2,
                    "correlation_score": correlation_score,
                    "is_correlated": correlation_score >= threshold,
                    "unique_pairs": unique_pairs,
                    "total_samples": total_samples,
                    "sample_size": sample_size,
                }

            except Exception as e:
                logger.debug(
                    f"Correlation calculation failed for {table_name}.{column1}-{column2}: {e}"
                )
                return None
            finally:
                cursor.close()

    except Exception as e:
        logger.debug(f"Correlation calculation failed: {e}")
        return None


def find_correlated_columns(table_name: str, candidate_columns: list[str]) -> list[dict[str, Any]]:
    """
    Find correlated column pairs using Cortex principles.

    Args:
        table_name: Table name
        candidate_columns: List of candidate columns to analyze

    Returns:
        List of correlated column pairs
    """
    if not is_cortex_enabled():
        return []

    if len(candidate_columns) < 2:
        return []

    correlated_pairs: list[dict[str, Any]] = []

    # Analyze pairs of columns
    for i, col1 in enumerate(candidate_columns):
        for col2 in candidate_columns[i + 1 :]:
            correlation = calculate_correlation(table_name, col1, col2)
            if correlation and correlation.get("is_correlated", False):
                correlated_pairs.append(correlation)

    return correlated_pairs


def suggest_correlated_indexes(
    table_name: str, correlated_pairs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Suggest composite indexes based on correlated columns.

    Args:
        table_name: Table name
        correlated_pairs: List of correlated column pairs

    Returns:
        List of index suggestions
    """
    if not is_cortex_enabled():
        return []

    suggestions: list[dict[str, Any]] = []

    for pair in correlated_pairs:
        col1 = pair.get("column1")
        col2 = pair.get("column2")
        correlation_score = pair.get("correlation_score", 0.0)

        if col1 and col2:
            # Suggest composite index for correlated columns
            index_name = f"idx_{table_name}_{col1}_{col2}_cortex"
            suggestions.append(
                {
                    "table_name": table_name,
                    "columns": [col1, col2],
                    "index_name": index_name,
                    "index_sql": f"CREATE INDEX CONCURRENTLY {index_name} ON {table_name} ({col1}, {col2})",
                    "reason": f"Cortex: High correlation ({correlation_score:.2f}) between {col1} and {col2}",
                    "correlation_score": correlation_score,
                    "priority": "high" if correlation_score > 0.8 else "medium",
                }
            )

    return suggestions


def enhance_composite_detection(
    base_suggestions: list[dict[str, Any]], table_name: str, candidate_columns: list[str]
) -> list[dict[str, Any]]:
    """
    Enhance composite index detection with Cortex correlation analysis.

    Args:
        base_suggestions: Base composite index suggestions
        table_name: Table name
        candidate_columns: Candidate columns for analysis

    Returns:
        Enhanced suggestions with Cortex correlation insights
    """
    if not is_cortex_enabled():
        return base_suggestions

    # Find correlated columns
    correlated_pairs = find_correlated_columns(table_name, candidate_columns)

    if not correlated_pairs:
        return base_suggestions

    # Get Cortex-based suggestions
    cortex_suggestions = suggest_correlated_indexes(table_name, correlated_pairs)

    # Merge with base suggestions (avoid duplicates)
    enhanced = base_suggestions.copy()

    for cortex_suggestion in cortex_suggestions:
        cortex_cols = set(cortex_suggestion.get("columns", []))
        # Check if similar suggestion already exists
        is_duplicate = False
        for existing in enhanced:
            existing_cols = set(existing.get("columns", []))
            if cortex_cols == existing_cols:
                # Enhance existing suggestion with Cortex info
                existing["cortex_correlation"] = cortex_suggestion.get("correlation_score", 0.0)
                existing["reason"] = (
                    f"{existing.get('reason', '')} [Cortex: correlation {cortex_suggestion.get('correlation_score', 0.0):.2f}]"
                )
                is_duplicate = True
                break

        if not is_duplicate:
            enhanced.append(cortex_suggestion)

    return enhanced
