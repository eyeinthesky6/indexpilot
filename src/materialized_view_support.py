"""Materialized view support for index suggestions"""

import logging
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_materialized_view_support_enabled() -> bool:
    """Check if materialized view support is enabled"""
    return _config_loader.get_bool("features.materialized_view_support.enabled", True)


def find_materialized_views(schema_name: str = "public") -> list[dict[str, Any]]:
    """
    Find all materialized views in the schema.

    Args:
        schema_name: Schema to check (default: public)

    Returns:
        List of materialized views
    """
    if not is_materialized_view_support_enabled():
        logger.debug("Materialized view support is disabled")
        return []

    materialized_views = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                query = """
                    SELECT
                        schemaname,
                        matviewname,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size_pretty,
                        pg_total_relation_size(schemaname||'.'||matviewname) / (1024.0 * 1024.0) as size_mb,
                        hasindexes
                    FROM pg_matviews
                    WHERE schemaname = %s
                    ORDER BY matviewname
                """
                cursor.execute(query, (schema_name,))
                results = cursor.fetchall()

                for row in results:
                    materialized_views.append(
                        {
                            "schema": row["schemaname"],
                            "name": row["matviewname"],
                            "full_name": f"{row['schemaname']}.{row['matviewname']}",
                            "size_mb": float(row["size_mb"]) if row["size_mb"] else 0.0,
                            "size_pretty": row["size_pretty"],
                            "has_indexes": row.get("hasindexes", False),
                        }
                    )

                if materialized_views:
                    logger.info(
                        f"Found {len(materialized_views)} materialized views in schema '{schema_name}'"
                    )

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to find materialized views: {e}")

    return materialized_views


def get_materialized_view_indexes(
    mv_name: str, schema_name: str = "public"
) -> list[dict[str, Any]]:
    """
    Get indexes on a materialized view.

    Args:
        mv_name: Materialized view name
        schema_name: Schema name (default: public)

    Returns:
        List of indexes on the materialized view
    """
    if not is_materialized_view_support_enabled():
        return []

    indexes = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                query = """
                    SELECT
                        i.schemaname,
                        i.tablename,
                        i.indexname,
                        i.indexdef,
                        pg_size_pretty(pg_relation_size(i.indexname::regclass)) as size_pretty,
                        pg_relation_size(i.indexname::regclass) / (1024.0 * 1024.0) as size_mb,
                        idx_scan as index_scans
                    FROM pg_indexes i
                    LEFT JOIN pg_stat_user_indexes stat ON stat.indexrelname = i.indexname
                        AND stat.schemaname = i.schemaname
                    WHERE i.schemaname = %s
                      AND i.tablename = %s
                    ORDER BY i.indexname
                """
                cursor.execute(query, (schema_name, mv_name))
                results = cursor.fetchall()

                for row in results:
                    indexes.append(
                        {
                            "schema": row["schemaname"],
                            "table": row["tablename"],
                            "index_name": row["indexname"],
                            "indexdef": row["indexdef"],
                            "size_mb": float(row["size_mb"]) if row["size_mb"] else 0.0,
                            "size_pretty": row["size_pretty"],
                            "scans": int(row["index_scans"]) if row["index_scans"] else 0,
                        }
                    )

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to get indexes for materialized view {mv_name}: {e}")

    return indexes


def suggest_materialized_view_indexes(
    mv_name: str | None = None, schema_name: str = "public"
) -> list[dict[str, Any]]:
    """
    Suggest indexes for materialized views based on refresh patterns and query stats.

    Args:
        mv_name: Materialized view name (None = all views)
        schema_name: Schema name (default: public)

    Returns:
        List of index suggestions for materialized views
    """
    if not is_materialized_view_support_enabled():
        return []

    suggestions = []

    try:
        # Get materialized views
        if mv_name:
            # Get specific view
            mvs = [mv for mv in find_materialized_views(schema_name) if mv["name"] == mv_name]
        else:
            mvs = find_materialized_views(schema_name)

        for mv in mvs:
            mv_full_name = mv["full_name"]
            existing_indexes = get_materialized_view_indexes(mv["name"], schema_name)

            # Check query stats for this materialized view
            try:
                from src.stats import get_query_stats

                query_stats = get_query_stats(time_window_hours=24, table_name=mv["name"])

                if query_stats:
                    # Analyze query patterns
                    field_usage: dict[str, int] = {}
                    for stat in query_stats:
                        if isinstance(stat, dict):
                            field = stat.get("field_name")
                            if field:
                                field_usage[field] = field_usage.get(field, 0) + 1

                    # Suggest indexes for frequently queried fields
                    for field, count in field_usage.items():
                        if count >= 10:  # Threshold for MV index suggestion
                            # Check if index already exists
                            has_index = any(
                                field in idx.get("indexdef", "").lower() for idx in existing_indexes
                            )

                            if not has_index:
                                index_name = f"idx_{mv['name']}_{field}"
                                suggestions.append(
                                    {
                                        "materialized_view": mv_full_name,
                                        "field": field,
                                        "index_name": index_name,
                                        "index_sql": f"""
                                            CREATE INDEX {index_name}
                                            ON {mv_full_name} ({field})
                                        """.strip(),
                                        "reason": f"Field '{field}' queried {count} times in last 24h",
                                        "query_count": count,
                                        "priority": "medium",
                                    }
                                )
            except Exception as e:
                logger.debug(f"Could not analyze query stats for {mv_full_name}: {e}")

            # If no indexes exist, suggest a primary key index if possible
            if not existing_indexes:
                suggestions.append(
                    {
                        "materialized_view": mv_full_name,
                        "field": "id",
                        "index_name": f"idx_{mv['name']}_id",
                        "index_sql": f"""
                            CREATE INDEX idx_{mv["name"]}_id
                            ON {mv_full_name} (id)
                        """.strip(),
                        "reason": "No indexes exist on materialized view - suggest primary key index",
                        "priority": "high",
                    }
                )

        if suggestions:
            logger.info(f"Generated {len(suggestions)} index suggestions for materialized views")

    except Exception as e:
        logger.error(f"Failed to suggest materialized view indexes: {e}")

    return suggestions


def analyze_materialized_view_refresh_patterns(
    mv_name: str, schema_name: str = "public"
) -> dict[str, Any]:
    """
    Analyze refresh patterns for a materialized view.

    Args:
        mv_name: Materialized view name
        schema_name: Schema name (default: public)

    Returns:
        dict with refresh pattern analysis
    """
    if not is_materialized_view_support_enabled():
        return {"skipped": True, "reason": "materialized_view_support_disabled"}

    result: JSONDict = {
        "materialized_view": f"{schema_name}.{mv_name}",
        "refresh_pattern": {},
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get refresh history from pg_stat_user_tables (if available)
                # Note: PostgreSQL doesn't track MV refresh history directly
                # This is a placeholder for future enhancement
                result["refresh_pattern"] = {
                    "note": "PostgreSQL doesn't track MV refresh history directly",
                    "suggestion": "Monitor REFRESH MATERIALIZED VIEW commands in query logs",
                }

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to analyze refresh patterns for {mv_name}: {e}")
        result["error"] = str(e)

    return result
