"""Automatic statistics refresh using ANALYZE"""

import logging
from datetime import datetime
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()


def is_statistics_refresh_enabled() -> bool:
    """Check if statistics refresh is enabled"""
    return _config_loader.get_bool("features.statistics_refresh.enabled", True)


def get_statistics_refresh_config() -> dict[str, Any]:
    """Get statistics refresh configuration"""
    return {
        "enabled": is_statistics_refresh_enabled(),
        "interval_hours": _config_loader.get_int("features.statistics_refresh.interval_hours", 24),
        "stale_threshold_hours": _config_loader.get_int(
            "features.statistics_refresh.stale_threshold_hours", 24
        ),
        "min_table_size_mb": _config_loader.get_float(
            "features.statistics_refresh.min_table_size_mb", 1.0
        ),
        "auto_refresh_after_bulk_ops": _config_loader.get_bool(
            "features.statistics_refresh.auto_refresh_after_bulk_ops", True
        ),
    }


def detect_stale_statistics(
    stale_threshold_hours: int = 24, min_table_size_mb: float = 1.0
) -> list[dict[str, Any]]:
    """
    Detect tables with stale statistics.

    Args:
        stale_threshold_hours: Hours since last ANALYZE to consider stale
        min_table_size_mb: Minimum table size to check (skip small tables)

    Returns:
        List of tables with stale statistics
    """
    if not is_statistics_refresh_enabled():
        logger.debug("Statistics refresh is disabled")
        return []

    stale_tables = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get tables with stale statistics
                # last_analyze is NULL if never analyzed, or timestamp if analyzed
                query = """
                    SELECT
                        schemaname,
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size_pretty,
                        pg_total_relation_size(schemaname||'.'||tablename) / (1024.0 * 1024.0) as size_mb,
                        last_analyze,
                        last_autoanalyze,
                        CASE
                            WHEN last_analyze IS NULL AND last_autoanalyze IS NULL THEN 'never'
                            WHEN last_analyze IS NOT NULL AND last_autoanalyze IS NOT NULL THEN
                                GREATEST(last_analyze, last_autoanalyze)
                            WHEN last_analyze IS NOT NULL THEN last_analyze
                            ELSE last_autoanalyze
                        END as last_stats_update,
                        CASE
                            WHEN last_analyze IS NULL AND last_autoanalyze IS NULL THEN
                                EXTRACT(EPOCH FROM (NOW() - '1970-01-01'::timestamp)) / 3600
                            WHEN last_analyze IS NOT NULL AND last_autoanalyze IS NOT NULL THEN
                                EXTRACT(EPOCH FROM (NOW() - GREATEST(last_analyze, last_autoanalyze))) / 3600
                            WHEN last_analyze IS NOT NULL THEN
                                EXTRACT(EPOCH FROM (NOW() - last_analyze)) / 3600
                            ELSE
                                EXTRACT(EPOCH FROM (NOW() - last_autoanalyze)) / 3600
                        END as hours_since_update
                    FROM pg_stat_user_tables
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                      AND pg_total_relation_size(schemaname||'.'||tablename) / (1024.0 * 1024.0) >= %s
                      AND (
                          last_analyze IS NULL
                          OR last_autoanalyze IS NULL
                          OR EXTRACT(EPOCH FROM (NOW() - GREATEST(
                              COALESCE(last_analyze, '1970-01-01'::timestamp),
                              COALESCE(last_autoanalyze, '1970-01-01'::timestamp)
                          ))) / 3600 >= %s
                      )
                    ORDER BY hours_since_update DESC NULLS LAST, size_mb DESC
                """
                cursor.execute(query, (min_table_size_mb, stale_threshold_hours))
                results = cursor.fetchall()

                for row in results:
                    stale_tables.append(
                        {
                            "schema": row["schemaname"],
                            "table": row["tablename"],
                            "full_name": f"{row['schemaname']}.{row['tablename']}",
                            "size_mb": float(row["size_mb"]) if row["size_mb"] else 0.0,
                            "size_pretty": row["size_pretty"],
                            "last_analyze": row["last_analyze"].isoformat()
                            if row["last_analyze"]
                            else None,
                            "last_autoanalyze": row["last_autoanalyze"].isoformat()
                            if row["last_autoanalyze"]
                            else None,
                            "last_stats_update": row["last_stats_update"].isoformat()
                            if row["last_stats_update"]
                            and not isinstance(row["last_stats_update"], str)
                            else str(row["last_stats_update"]),
                            "hours_since_update": float(row["hours_since_update"])
                            if row["hours_since_update"]
                            else None,
                        }
                    )

                if stale_tables:
                    logger.info(
                        f"Found {len(stale_tables)} tables with stale statistics "
                        f"(threshold: {stale_threshold_hours}h, min size: {min_table_size_mb}MB)"
                    )

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to detect stale statistics: {e}")
        # Don't raise - return empty list on error

    return stale_tables


def refresh_table_statistics(
    table_name: str | None = None,
    schema_name: str = "public",
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Refresh statistics for a table using ANALYZE.

    Args:
        table_name: Table name (None = all tables)
        schema_name: Schema name (default: public)
        dry_run: If True, don't actually run ANALYZE

    Returns:
        dict with refresh results
    """
    if not is_statistics_refresh_enabled():
        return {"skipped": True, "reason": "statistics_refresh_disabled"}

    result: JSONDict = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "tables_analyzed": [],
        "success": True,
        "error": None,
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if table_name:
                # Analyze specific table
                full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name
                analyze_query = f"ANALYZE {full_table_name}"

                if dry_run:
                    logger.info(f"[DRY RUN] Would run: {analyze_query}")
                    result["tables_analyzed"].append(
                        {"table": full_table_name, "status": "would_analyze"}
                    )
                else:
                    try:
                        cursor.execute(analyze_query)
                        logger.info(f"Analyzed table: {full_table_name}")
                        result["tables_analyzed"].append(
                            {"table": full_table_name, "status": "analyzed"}
                        )
                    except Exception as e:
                        logger.error(f"Failed to analyze {full_table_name}: {e}")
                        result["tables_analyzed"].append(
                            {"table": full_table_name, "status": "error", "error": str(e)}
                        )
                        result["success"] = False
                        result["error"] = str(e)
            else:
                # Analyze all tables in schema
                if dry_run:
                    stale = detect_stale_statistics()
                    logger.info(f"[DRY RUN] Would analyze {len(stale)} stale tables")
                    for table in stale:
                        result["tables_analyzed"].append(
                            {"table": table["full_name"], "status": "would_analyze"}
                        )
                else:
                    # Get all tables in schema
                    cursor.execute(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = %s
                        ORDER BY tablename
                        """,
                        (schema_name,),
                    )
                    tables = cursor.fetchall()

                    for table_row in tables:
                        table = table_row[0]
                        full_table_name = f"{schema_name}.{table}"
                        analyze_query = f"ANALYZE {full_table_name}"

                        try:
                            cursor.execute(analyze_query)
                            logger.debug(f"Analyzed table: {full_table_name}")
                            result["tables_analyzed"].append(
                                {"table": full_table_name, "status": "analyzed"}
                            )
                        except Exception as e:
                            logger.warning(f"Failed to analyze {full_table_name}: {e}")
                            result["tables_analyzed"].append(
                                {"table": full_table_name, "status": "error", "error": str(e)}
                            )

            cursor.close()

    except Exception as e:
        logger.error(f"Failed to refresh statistics: {e}")
        result["success"] = False
        result["error"] = str(e)

    return result


def refresh_stale_statistics(
    stale_threshold_hours: int = 24,
    min_table_size_mb: float = 1.0,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Refresh statistics for tables with stale statistics.

    Args:
        stale_threshold_hours: Hours since last ANALYZE to consider stale
        min_table_size_mb: Minimum table size to check
        dry_run: If True, don't actually run ANALYZE
        limit: Maximum number of tables to analyze (None = all)

    Returns:
        dict with refresh results
    """
    if not is_statistics_refresh_enabled():
        return {"skipped": True, "reason": "statistics_refresh_disabled"}

    result: JSONDict = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "stale_tables_found": 0,
        "tables_analyzed": [],
        "success": True,
        "error": None,
    }

    try:
        stale_tables = detect_stale_statistics(
            stale_threshold_hours=stale_threshold_hours, min_table_size_mb=min_table_size_mb
        )
        result["stale_tables_found"] = len(stale_tables)

        if not stale_tables:
            logger.info("No stale statistics found")
            return result

        # Limit number of tables if specified
        if limit and len(stale_tables) > limit:
            stale_tables = stale_tables[:limit]
            logger.info(f"Limiting to {limit} tables (found {result['stale_tables_found']} total)")

        with get_connection() as conn:
            cursor = conn.cursor()

            for table_info in stale_tables:
                full_table_name = table_info["full_name"]
                analyze_query = f"ANALYZE {full_table_name}"

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Would analyze: {full_table_name} "
                        f"(last update: {table_info['hours_since_update']:.1f}h ago)"
                    )
                    result["tables_analyzed"].append(
                        {
                            "table": full_table_name,
                            "status": "would_analyze",
                            "hours_since_update": table_info["hours_since_update"],
                        }
                    )
                else:
                    try:
                        cursor.execute(analyze_query)
                        logger.info(
                            f"Analyzed: {full_table_name} "
                            f"(last update: {table_info['hours_since_update']:.1f}h ago)"
                        )
                        result["tables_analyzed"].append(
                            {
                                "table": full_table_name,
                                "status": "analyzed",
                                "hours_since_update": table_info["hours_since_update"],
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to analyze {full_table_name}: {e}")
                        result["tables_analyzed"].append(
                            {
                                "table": full_table_name,
                                "status": "error",
                                "error": str(e),
                                "hours_since_update": table_info["hours_since_update"],
                            }
                        )
                        result["success"] = False
                        if not result["error"]:
                            result["error"] = str(e)

            cursor.close()

        logger.info(
            f"{'Would analyze' if dry_run else 'Analyzed'} {len(result['tables_analyzed'])} "
            f"tables with stale statistics"
        )

    except Exception as e:
        logger.error(f"Failed to refresh stale statistics: {e}")
        result["success"] = False
        result["error"] = str(e)

    return result


def get_statistics_status() -> dict[str, JSONValue]:
    """
    Get status of table statistics.

    Returns:
        dict with statistics status
    """
    config = get_statistics_refresh_config()
    stale_tables = detect_stale_statistics(
        stale_threshold_hours=config["stale_threshold_hours"],
        min_table_size_mb=config["min_table_size_mb"],
    )

    return {
        "enabled": config["enabled"],
        "stale_threshold_hours": config["stale_threshold_hours"],
        "stale_tables_count": len(stale_tables),
        "stale_tables": stale_tables[:10],  # Limit to first 10 for status
        "last_check": datetime.now().isoformat(),
    }
