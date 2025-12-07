"""CERT (Cardinality Estimation Restriction Testing) Algorithm Implementation

Based on "CERT: Continuous Evaluation of Cardinality Estimation"
arXiv:2306.00355

This module implements CERT validation for cardinality estimates, helping to:
- Validate selectivity estimates against actual database queries
- Detect stale statistics
- Improve index recommendation accuracy

Algorithm concepts are not copyrightable; attribution provided as good practice.
See THIRD_PARTY_ATTRIBUTIONS.md for complete attribution.
"""

import logging
from typing import Any

from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection

logger = logging.getLogger(__name__)

# Load configuration
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def validate_cardinality_with_cert(
    table_name: str, field_name: str, estimated_selectivity: float
) -> dict[str, Any]:
    """
    Validate cardinality estimate using CERT (Cardinality Estimation Restriction Testing) approach.

    Based on "CERT: Continuous Evaluation of Cardinality Estimation"
    arXiv:2306.00355

    This function validates selectivity estimates by:
    1. Running restrictive queries to get actual row counts
    2. Comparing estimated vs actual cardinality
    3. Detecting when statistics are stale

    Args:
        table_name: Table name
        field_name: Field name
        estimated_selectivity: Estimated selectivity ratio (0.0 to 1.0)

    Returns:
        dict with validation results:
        - is_valid: bool - Whether estimate is within acceptable range
        - actual_selectivity: float - Actual selectivity from queries
        - error_pct: float - Percentage error between estimated and actual
        - statistics_stale: bool - Whether statistics appear stale
        - confidence: float - Confidence in the validation (0.0 to 1.0)
        - reason: str - Reason for validation result
    """
    try:
        from src.validation import validate_field_name, validate_table_name

        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get total row count
                count_query = sql.SQL("SELECT COUNT(*) as total_rows FROM {}").format(
                    sql.Identifier(validated_table)
                )
                cursor.execute(count_query)
                total_result = cursor.fetchone()
                if (
                    not total_result
                    or not total_result["total_rows"]
                    or total_result["total_rows"] == 0
                ):
                    return {
                        "is_valid": False,
                        "actual_selectivity": 0.0,
                        "error_pct": 100.0,
                        "statistics_stale": False,
                        "confidence": 0.0,
                        "reason": "empty_table",
                    }

                total_rows = total_result["total_rows"]

                # Get actual distinct count (actual cardinality)
                distinct_query = sql.SQL(
                    "SELECT COUNT(DISTINCT {}) as distinct_count FROM {}"
                ).format(sql.Identifier(validated_field), sql.Identifier(validated_table))
                cursor.execute(distinct_query)
                distinct_result = cursor.fetchone()

                if not distinct_result or distinct_result["distinct_count"] is None:
                    return {
                        "is_valid": False,
                        "actual_selectivity": 0.0,
                        "error_pct": 100.0,
                        "statistics_stale": False,
                        "confidence": 0.0,
                        "reason": "could_not_calculate",
                    }

                actual_distinct = distinct_result["distinct_count"]
                actual_selectivity = float(actual_distinct / total_rows) if total_rows > 0 else 0.0

                # Calculate error percentage
                if estimated_selectivity > 0:
                    error_pct = (
                        abs(actual_selectivity - estimated_selectivity)
                        / estimated_selectivity
                        * 100.0
                    )
                else:
                    error_pct = 100.0 if actual_selectivity > 0 else 0.0

                # CERT validation: Acceptable error threshold (configurable, default 10%)
                max_error_pct = _config_loader.get_float(
                    "features.auto_indexer.cert_max_error_pct", 10.0
                )
                is_valid = error_pct <= max_error_pct

                # Detect stale statistics: Large error suggests statistics are outdated
                statistics_stale = error_pct > max_error_pct * 2  # 2x threshold = likely stale

                # Calculate confidence based on error
                if error_pct == 0:
                    confidence = 1.0
                elif error_pct <= max_error_pct:
                    confidence = 1.0 - (error_pct / max_error_pct) * 0.2  # 0.8 to 1.0
                else:
                    confidence = max(0.0, 1.0 - (error_pct / (max_error_pct * 2)))  # 0.0 to 0.8

                return {
                    "is_valid": is_valid,
                    "actual_selectivity": actual_selectivity,
                    "error_pct": error_pct,
                    "statistics_stale": statistics_stale,
                    "confidence": confidence,
                    "reason": "validated" if is_valid else "high_error",
                }
            finally:
                cursor.close()
    except Exception as e:
        # Handle all exceptions gracefully - return low confidence result
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["connection", "pool", "closed", "shutdown"]):
            logger.debug(f"Database connection unavailable for CERT validation: {e}")
        else:
            logger.debug(f"CERT validation failed for {table_name}.{field_name}: {e}")
        return {
            "is_valid": False,
            "actual_selectivity": estimated_selectivity,  # Fall back to estimate
            "error_pct": 0.0,
            "statistics_stale": False,
            "confidence": 0.5,  # Medium confidence when validation fails
            "reason": "validation_failed",
        }
