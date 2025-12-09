"""Track algorithm usage for index decisions"""

import json
import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection

logger = logging.getLogger(__name__)


def track_algorithm_usage(
    table_name: str,
    field_name: str | None,
    algorithm_name: str,
    recommendation: dict[str, Any],
    used_in_decision: bool = False,
) -> None:
    """
    Track which algorithm was used for an index decision.

    Args:
        table_name: Table name
        field_name: Field name (optional)
        algorithm_name: Name of the algorithm (e.g., "predictive_indexing", "cert", "qpg")
        recommendation: Algorithm recommendation dict
        used_in_decision: Whether this algorithm's recommendation was used in the final decision
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    INSERT INTO algorithm_usage
                    (table_name, field_name, algorithm_name, recommendation_json, used_in_decision)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (
                        table_name,
                        field_name,
                        algorithm_name,
                        json.dumps(recommendation),
                        used_in_decision,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()
    except Exception as e:
        logger.warning(f"Could not track algorithm usage: {e}", exc_info=True)


def get_algorithm_usage_stats(
    table_name: str | None = None,
    algorithm_name: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Get algorithm usage statistics.

    Args:
        table_name: Optional table name filter
        algorithm_name: Optional algorithm name filter
        limit: Maximum number of records to return

    Returns:
        List of algorithm usage records
    """
    try:
        with get_cursor() as cursor:
            try:
                query = """
                    SELECT table_name, field_name, algorithm_name, recommendation_json,
                           used_in_decision, created_at
                    FROM algorithm_usage
                    WHERE 1=1
                """
                params = []

                if table_name:
                    query += " AND table_name = %s"
                    params.append(table_name)

                if algorithm_name:
                    query += " AND algorithm_name = %s"
                    params.append(algorithm_name)

                query += " ORDER BY created_at DESC LIMIT %s"
                params.append(str(limit))

                cursor.execute(query, params)
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    # Handle recommendation_json - may already be a dict or a JSON string
                    recommendation_value = row.get("recommendation_json")
                    if recommendation_value:
                        if isinstance(recommendation_value, dict):
                            recommendation = recommendation_value
                        elif isinstance(recommendation_value, str):
                            try:
                                recommendation = json.loads(recommendation_value)
                            except (json.JSONDecodeError, TypeError):
                                recommendation = {}
                        else:
                            recommendation = {}
                    else:
                        recommendation = {}

                    results.append(
                        {
                            "table_name": row["table_name"],
                            "field_name": row["field_name"],
                            "algorithm_name": row["algorithm_name"],
                            "recommendation": recommendation,
                            "used_in_decision": row["used_in_decision"],
                            "created_at": row["created_at"].isoformat()
                            if hasattr(row["created_at"], "isoformat")
                            else str(row["created_at"]),
                        }
                    )
                return results
            finally:
                cursor.close()
    except Exception as e:
        logger.debug(f"Could not get algorithm usage stats: {e}")
        return []
