"""Cortex (Data Correlation Exploitation) Algorithm Implementation

Based on "Cortex: Leveraging Correlation for Efficient Data Analytics"
arXiv:2012.06683

This module implements Cortex concepts for multi-attribute correlation detection,
helping to identify composite index opportunities based on data correlations.

Enhanced with mutual information and chi-squared test for accurate correlation detection.
"""

import logging
from typing import Any

import numpy as np
from psycopg2.extras import RealDictCursor

try:
    from scipy.stats import chi2_contingency

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    chi2_contingency = None

try:
    from sklearn.feature_selection import mutual_info_regression
    from sklearn.preprocessing import LabelEncoder

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    mutual_info_regression = None
    LabelEncoder = None

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


def _calculate_mutual_information(col1_values: list[Any], col2_values: list[Any]) -> float:
    """
    Calculate mutual information between two columns.

    Mutual Information: I(X;Y) = H(X) + H(Y) - H(X,Y)
    Measures the amount of information obtained about one variable through the other.

    Args:
        col1_values: Values from first column
        col2_values: Values from second column

    Returns:
        Mutual information score (0.0 to 1.0, normalized)
    """
    if not SCIPY_AVAILABLE or not SKLEARN_AVAILABLE or len(col1_values) < 10:
        return 0.0

    try:
        # Convert to numeric arrays for mutual information calculation
        # For categorical data, we'll use label encoding
        if LabelEncoder is None:
            return 0.0

        le1 = LabelEncoder()
        le2 = LabelEncoder()

        # Handle mixed types - convert to string then encode
        col1_encoded = le1.fit_transform([str(v) for v in col1_values])
        col2_encoded = le2.fit_transform([str(v) for v in col2_values])

        # Reshape for sklearn
        col1_2d = col1_encoded.reshape(-1, 1)

        # Calculate mutual information
        mi_score = mutual_info_regression(col1_2d, col2_encoded, random_state=42)[0]

        # Normalize to 0-1 range (mutual information can be any positive value)
        # Use log2 of number of unique values as normalization factor
        max_mi = min(np.log2(len(set(col1_values)) + 1), np.log2(len(set(col2_values)) + 1))
        normalized_mi = min(1.0, mi_score / max_mi) if max_mi > 0 else 0.0

        return float(normalized_mi)
    except Exception as e:
        logger.debug(f"Mutual information calculation failed: {e}")
        return 0.0


def _calculate_chi_squared(col1_values: list[Any], col2_values: list[Any]) -> float:
    """
    Calculate chi-squared test statistic for independence.

    Chi-squared test: Tests if two categorical variables are independent.
    Higher chi-squared value = stronger association (correlation).

    Args:
        col1_values: Values from first column
        col2_values: Values from second column

    Returns:
        Normalized chi-squared score (0.0 to 1.0)
    """
    if not SCIPY_AVAILABLE or len(col1_values) < 10:
        return 0.0

    try:
        # Create contingency table
        from collections import Counter

        # Create pairs and count frequencies
        pairs = list(zip(col1_values, col2_values, strict=False))
        pair_counts = Counter(pairs)

        # Get unique values
        unique_col1 = sorted(set(col1_values))
        unique_col2 = sorted(set(col2_values))

        # Build contingency table
        contingency = np.zeros((len(unique_col1), len(unique_col2)))
        col1_map = {val: idx for idx, val in enumerate(unique_col1)}
        col2_map = {val: idx for idx, val in enumerate(unique_col2)}

        for (v1, v2), count in pair_counts.items():
            if v1 in col1_map and v2 in col2_map:
                contingency[col1_map[v1], col2_map[v2]] = count

        # Calculate chi-squared statistic
        chi2, p_value, dof, expected = chi2_contingency(contingency)

        # Normalize chi-squared value
        # Cramér's V: sqrt(chi2 / (n * min(r-1, c-1)))
        n = len(col1_values)
        min_dim = min(len(unique_col1), len(unique_col2))
        cramers_v = np.sqrt(chi2 / (n * (min_dim - 1))) if min_dim > 1 and n > 0 else 0.0

        # Cramér's V is already normalized to 0-1
        return float(min(1.0, max(0.0, cramers_v)))
    except Exception as e:
        logger.debug(f"Chi-squared calculation failed: {e}")
        return 0.0


def calculate_correlation(table_name: str, column1: str, column2: str) -> dict[str, Any] | None:
    """
    Calculate correlation between two columns using statistical methods.

    Cortex leverages data correlations to extend primary indexes.

    Enhanced with mutual information and chi-squared test for accurate correlation detection
    as per Cortex paper (arXiv:2012.06683).

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
        from psycopg2 import sql

        from src.validation import validate_field_name, validate_table_name

        validated_table = validate_table_name(table_name)
        validated_col1 = validate_field_name(column1, table_name)
        validated_col2 = validate_field_name(column2, table_name)
    except Exception as e:
        logger.debug(f"Validation failed for {table_name}.{column1}-{column2}: {e}")
        return None

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get sample data for correlation analysis
                # Use a sample to avoid full table scans on large tables
                sample_size = _config_loader.get_int("features.cortex.sample_size", 10000)

                # Get raw sample data for statistical analysis
                sample_query = sql.SQL(
                    """
                    SELECT {col1}, {col2}
                    FROM {table}
                    WHERE {col1} IS NOT NULL AND {col2} IS NOT NULL
                    LIMIT %s
                    """
                ).format(
                    col1=sql.Identifier(validated_col1),
                    col2=sql.Identifier(validated_col2),
                    table=sql.Identifier(validated_table),
                )

                cursor.execute(sample_query, (sample_size,))
                samples = cursor.fetchall()

                if len(samples) < 10:  # Need minimum samples
                    return None

                # Extract column values
                col1_values = [row[validated_col1] for row in samples]
                col2_values = [row[validated_col2] for row in samples]

                config = get_cortex_config()
                use_mutual_info = config.get("use_mutual_information", True)

                # Calculate correlation using appropriate statistical method
                if use_mutual_info and SKLEARN_AVAILABLE:
                    # Use mutual information (preferred for continuous/categorical mixed data)
                    correlation_score = _calculate_mutual_information(col1_values, col2_values)
                    method = "mutual_information"
                elif SCIPY_AVAILABLE:
                    # Use chi-squared test (good for categorical data)
                    correlation_score = _calculate_chi_squared(col1_values, col2_values)
                    method = "chi_squared"
                else:
                    # Fallback to simplified co-occurrence frequency
                    # Count unique pairs
                    unique_pairs = len(set(zip(col1_values, col2_values, strict=False)))
                    total_samples = len(samples)

                    # High correlation: few unique pairs relative to total samples
                    correlation_score = (
                        1.0 - (unique_pairs / total_samples) if total_samples > 0 else 0.0
                    )
                    correlation_score = max(0.0, min(1.0, correlation_score))
                    method = "co_occurrence"

                threshold = config.get("correlation_threshold", 0.7)

                return {
                    "column1": column1,
                    "column2": column2,
                    "correlation_score": correlation_score,
                    "is_correlated": correlation_score >= threshold,
                    "method": method,
                    "sample_size": len(samples),
                    "scipy_available": SCIPY_AVAILABLE,
                    "sklearn_available": SKLEARN_AVAILABLE,
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
