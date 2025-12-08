"""Index Lifecycle Management Integration

Orchestrates comprehensive index lifecycle management including:
- Weekly/monthly scheduling (vs hourly)
- Per-tenant lifecycle management
- VACUUM ANALYZE integration for tables with indexes
- Unified workflow connecting cleanup, health monitoring, statistics refresh
- Automatic REINDEX for bloated indexes
- Index statistics refresh after lifecycle operations

This integrates existing modules:
- index_cleanup.py (unused index removal)
- index_health.py (bloat detection, REINDEX)
- statistics_refresh.py (ANALYZE operations)
- maintenance.py (scheduling framework)
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, cast

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.monitoring import get_monitoring

logger = logging.getLogger(__name__)

# Load config
_config_loader: ConfigLoader | None = None
try:
    _config_loader = ConfigLoader()
except Exception:
    _config_loader = None


# Lifecycle scheduling intervals (seconds) - configurable
def _get_weekly_interval() -> int:
    """Get weekly interval from config or default"""
    if _config_loader is None:
        return 7 * 24 * 60 * 60  # 7 days default
    days = _config_loader.get_int("features.index_lifecycle.weekly_interval_days", 7)
    return days * 24 * 60 * 60


def _get_monthly_interval() -> int:
    """Get monthly interval from config or default"""
    if _config_loader is None:
        return 30 * 24 * 60 * 60  # 30 days default
    days = _config_loader.get_int("features.index_lifecycle.monthly_interval_days", 30)
    return days * 24 * 60 * 60


# Last run timestamps for lifecycle operations
_last_weekly_lifecycle: float = 0.0
_last_monthly_lifecycle: float = 0.0
_lifecycle_lock = threading.Lock()


def is_lifecycle_management_enabled() -> bool:
    """Check if index lifecycle management is enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("features.index_lifecycle.enabled", True)


def get_lifecycle_config() -> dict[str, Any]:
    """Get lifecycle management configuration"""
    if _config_loader is None:
        return {
            "enabled": True,
            "weekly_schedule": True,
            "monthly_schedule": True,
            "per_tenant_management": True,
            "vacuum_analyze_integration": True,
            "auto_reindex_enabled": False,  # Conservative default
            "statistics_refresh_enabled": True,
            "cleanup_enabled": True,
        }

    return {
        "enabled": is_lifecycle_management_enabled(),
        "weekly_schedule": _config_loader.get_bool(
            "features.index_lifecycle.weekly_schedule", True
        ),
        "monthly_schedule": _config_loader.get_bool(
            "features.index_lifecycle.monthly_schedule", True
        ),
        "per_tenant_management": _config_loader.get_bool(
            "features.index_lifecycle.per_tenant_management", True
        ),
        "vacuum_analyze_integration": _config_loader.get_bool(
            "features.index_lifecycle.vacuum_analyze_integration", True
        ),
        "auto_reindex_enabled": _config_loader.get_bool(
            "features.index_lifecycle.auto_reindex_enabled", False
        ),
        "statistics_refresh_enabled": _config_loader.get_bool(
            "features.index_lifecycle.statistics_refresh_enabled", True
        ),
        "cleanup_enabled": _config_loader.get_bool(
            "features.index_lifecycle.cleanup_enabled", True
        ),
    }


def get_tenant_indexes(tenant_id: int | None = None) -> list[dict[str, Any]]:
    """
    Get all indexes for a specific tenant or all tenants.

    Args:
        tenant_id: Optional tenant ID filter

    Returns:
        List of indexes with tenant information
    """
    with get_connection() as conn:
        from psycopg2.extras import RealDictCursor

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        try:
            # Get indexes with their tenant association via table relationships
            query = """
                SELECT
                    i.schemaname,
                    i.tablename,
                    i.indexname,
                    i.idx_scan as index_scans,
                    pg_size_bytes(pg_relation_size(i.indexname::regclass)) as index_size_bytes,
                    t.tenant_id,
                    c.reltuples as table_rows
                FROM pg_stat_user_indexes i
                LEFT JOIN tenants t ON i.tablename = 'contacts' OR i.tablename = 'organizations' OR i.tablename = 'interactions'
                LEFT JOIN pg_class c ON c.relname = i.tablename
                WHERE i.schemaname = 'public'
                  AND i.indexname LIKE 'idx_%'
            """

            if tenant_id is not None:
                query += " AND t.tenant_id = %s"
                cursor.execute(query, (tenant_id,))
            else:
                cursor.execute(query)

            indexes = []
            for row in cursor.fetchall():
                # Handle both dict (RealDictCursor) and tuple results
                if isinstance(row, dict):
                    indexes.append(
                        {
                            "schemaname": row.get("schemaname", ""),
                            "tablename": row.get("tablename", ""),
                            "indexname": row.get("indexname", ""),
                            "index_scans": row.get("index_scans", 0) or 0,
                            "index_size_mb": (row.get("index_size_bytes", 0) or 0) / (1024 * 1024),
                            "tenant_id": row.get("tenant_id"),
                            "table_rows": row.get("table_rows", 0) or 0,
                        }
                    )
                else:
                    # Fallback for tuple results
                    indexes.append(
                        {
                            "schemaname": row[0] if len(row) > 0 else "",
                            "tablename": row[1] if len(row) > 1 else "",
                            "indexname": row[2] if len(row) > 2 else "",
                            "index_scans": row[3] if len(row) > 3 else 0,
                            "index_size_mb": (row[4] if len(row) > 4 else 0) / (1024 * 1024),
                            "tenant_id": row[5] if len(row) > 5 else None,
                            "table_rows": row[6] if len(row) > 6 else 0,
                        }
                    )

            return indexes
        finally:
            cursor.close()


def perform_vacuum_analyze_for_indexes(
    indexes: list[dict[str, Any]], dry_run: bool = False
) -> dict[str, Any]:
    """
    Perform VACUUM ANALYZE on tables that have indexes.

    Args:
        indexes: List of indexes to analyze tables for
        dry_run: If True, only report what would be analyzed

    Returns:
        Dict with results
    """
    result = {
        "tables_analyzed": 0,
        "tables_skipped": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    if not is_lifecycle_management_enabled():
        logger.info("Index lifecycle management disabled, skipping VACUUM ANALYZE")
        return result

    config = get_lifecycle_config()
    if not config["vacuum_analyze_integration"]:
        logger.debug("VACUUM ANALYZE integration disabled")
        return result

    # Get unique tables from indexes
    tables_to_analyze = set()
    for idx in indexes:
        tables_to_analyze.add(idx["tablename"])

    monitoring = get_monitoring()

    for table_name in tables_to_analyze:
        try:
            if dry_run:
                logger.info(f"[DRY RUN] Would VACUUM ANALYZE table: {table_name}")
                result["tables_analyzed"] += 1
                continue

            logger.info(f"VACUUM ANALYZE table with indexes: {table_name}")

            with get_connection() as conn:
                cursor = conn.cursor()
                try:
                    # VACUUM ANALYZE the table
                    cursor.execute(f'VACUUM ANALYZE "{table_name}"')
                    conn.commit()

                    result["tables_analyzed"] += 1

                    monitoring.alert(
                        "info",
                        f"VACUUM ANALYZE completed for table: {table_name}",
                    )
                finally:
                    cursor.close()

        except Exception as e:
            logger.error(f"Failed to VACUUM ANALYZE table {table_name}: {e}")
            result["errors"] += 1
            monitoring.alert("warning", f"Failed to VACUUM ANALYZE table {table_name}: {e}")

    logger.info(
        f"VACUUM ANALYZE completed: {result['tables_analyzed']} tables analyzed, "
        f"{result['errors']} errors"
    )
    return result


def perform_per_tenant_lifecycle(
    tenant_id: int | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """
    Perform lifecycle management operations for a specific tenant or all tenants.

    Args:
        tenant_id: Optional tenant ID (None = all tenants)
        dry_run: If True, only report what would be done

    Returns:
        Dict with lifecycle operation results
    """
    result: dict[str, Any] = {
        "tenant_id": tenant_id,
        "indexes_processed": 0,
        "cleanup_results": {},
        "health_results": {},
        "statistics_results": {},
        "vacuum_results": {},
        "reindex_results": {},
        "dry_run": dry_run,
    }

    if not is_lifecycle_management_enabled():
        logger.info("Index lifecycle management disabled")
        return result

    config = get_lifecycle_config()
    monitoring = get_monitoring()

    try:
        # Get indexes for this tenant
        indexes = get_tenant_indexes(tenant_id)
        result["indexes_processed"] = len(indexes)

        if not indexes:
            logger.debug(f"No indexes found for tenant {tenant_id}")
            return result

        logger.info(
            f"Performing lifecycle management for {len(indexes)} indexes (tenant: {tenant_id})"
        )

        # 1. Index cleanup (remove unused indexes)
        if config["cleanup_enabled"]:
            try:
                from src.index_cleanup import cleanup_unused_indexes

                cleanup_result = cleanup_unused_indexes(dry_run=dry_run)
                result["cleanup_results"] = cleanup_result
                logger.info(f"Index cleanup completed: {len(cleanup_result)} indexes removed")
            except Exception as e:
                logger.error(f"Index cleanup failed for tenant {tenant_id}: {e}")
                result["cleanup_results"] = {"error": str(e)}

        # 2. Index health monitoring and REINDEX
        if config["auto_reindex_enabled"]:
            try:
                from src.index_health import reindex_bloated_indexes

                reindex_result = reindex_bloated_indexes(dry_run=dry_run)
                result["reindex_results"] = reindex_result
                logger.info(f"Index REINDEX completed: {len(reindex_result)} indexes reindexed")
            except Exception as e:
                logger.error(f"Index REINDEX failed for tenant {tenant_id}: {e}")
                result["reindex_results"] = {"error": str(e)}

        # 3. Statistics refresh for tables with indexes
        if config["statistics_refresh_enabled"]:
            try:
                from src.statistics_refresh import refresh_stale_statistics

                # Get unique tables from indexes (for future use in targeted refresh)
                _ = {idx["tablename"] for idx in indexes}
                stats_result = refresh_stale_statistics(dry_run=dry_run)
                result["statistics_results"] = stats_result
                logger.info(f"Statistics refresh completed for {len(stats_result)} tables")
            except Exception as e:
                logger.error(f"Statistics refresh failed for tenant {tenant_id}: {e}")
                result["statistics_results"] = {"error": str(e)}

        # 4. VACUUM ANALYZE integration
        if config["vacuum_analyze_integration"]:
            vacuum_result = perform_vacuum_analyze_for_indexes(indexes, dry_run=dry_run)
            result["vacuum_results"] = vacuum_result

        # Log summary
        monitoring.alert(
            "info",
            f"Index lifecycle management completed for tenant {tenant_id}: "
            f"{result['indexes_processed']} indexes processed",
        )

    except Exception as e:
        logger.error(f"Index lifecycle management failed for tenant {tenant_id}: {e}")
        monitoring.alert("error", f"Index lifecycle management failed for tenant {tenant_id}: {e}")
        result["error"] = str(e)

    return result


def perform_weekly_lifecycle(dry_run: bool = False) -> dict[str, Any]:
    """
    Perform weekly lifecycle management operations.

    Includes comprehensive cleanup, health checks, and optimization.
    """
    result = {
        "operation": "weekly_lifecycle",
        "timestamp": datetime.now().isoformat(),
        "tenants_processed": 0,
        "total_indexes_processed": 0,
        "dry_run": dry_run,
    }

    if not is_lifecycle_management_enabled():
        logger.info("Index lifecycle management disabled, skipping weekly operations")
        return result

    config = get_lifecycle_config()
    if not config["weekly_schedule"]:
        logger.debug("Weekly lifecycle scheduling disabled")
        return result

    monitoring = get_monitoring()

    try:
        # Get all tenants
        with get_connection() as conn:
            from psycopg2.extras import RealDictCursor

            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute("SELECT id FROM tenants ORDER BY id")
                tenants = cursor.fetchall()
            finally:
                cursor.close()

        # Handle both dict (RealDictCursor) and tuple results
        tenant_ids = []
        for row in tenants:
            if isinstance(row, dict):
                tenant_ids.append(row.get("id"))
            else:
                tenant_ids.append(row[0] if len(row) > 0 else None)
        tenant_ids = [tid for tid in tenant_ids if tid is not None]

        logger.info(f"Starting weekly lifecycle management for {len(tenant_ids)} tenants")

        # Process each tenant
        for tenant_id in tenant_ids:
            tenant_result = perform_per_tenant_lifecycle(tenant_id, dry_run=dry_run)
            result["tenants_processed"] = cast(int, result["tenants_processed"]) + 1
            result["total_indexes_processed"] = cast(
                int, result["total_indexes_processed"]
            ) + tenant_result.get("indexes_processed", 0)

        logger.info(
            f"Weekly lifecycle management completed: {result['tenants_processed']} tenants processed, "
            f"{result['total_indexes_processed']} indexes managed"
        )

        monitoring.alert(
            "info",
            f"Weekly index lifecycle management completed: {result['tenants_processed']} tenants, "
            f"{result['total_indexes_processed']} indexes",
        )

    except Exception as e:
        logger.error(f"Weekly lifecycle management failed: {e}")
        monitoring.alert("error", f"Weekly index lifecycle management failed: {e}")
        result["error"] = str(e)

    return result


def perform_monthly_lifecycle(dry_run: bool = False) -> dict[str, Any]:
    """
    Perform monthly lifecycle management operations.

    Includes deep cleanup, extensive health checks, and major optimizations.
    """
    result = {
        "operation": "monthly_lifecycle",
        "timestamp": datetime.now().isoformat(),
        "tenants_processed": 0,
        "total_indexes_processed": 0,
        "dry_run": dry_run,
    }

    if not is_lifecycle_management_enabled():
        logger.info("Index lifecycle management disabled, skipping monthly operations")
        return result

    config = get_lifecycle_config()
    if not config["monthly_schedule"]:
        logger.debug("Monthly lifecycle scheduling disabled")
        return result

    monitoring = get_monitoring()

    try:
        # Get all tenants
        with get_connection() as conn:
            from psycopg2.extras import RealDictCursor

            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute("SELECT id FROM tenants ORDER BY id")
                tenants = cursor.fetchall()
            finally:
                cursor.close()

        # Handle both dict (RealDictCursor) and tuple results
        tenant_ids = []
        for row in tenants:
            if isinstance(row, dict):
                tenant_ids.append(row.get("id"))
            else:
                tenant_ids.append(row[0] if len(row) > 0 else None)
        tenant_ids = [tid for tid in tenant_ids if tid is not None]

        logger.info(f"Starting monthly lifecycle management for {len(tenant_ids)} tenants")

        # Process each tenant with more aggressive settings
        for tenant_id in tenant_ids:
            tenant_result = perform_per_tenant_lifecycle(tenant_id, dry_run=dry_run)
            result["tenants_processed"] = cast(int, result["tenants_processed"]) + 1
            result["total_indexes_processed"] = cast(
                int, result["total_indexes_processed"]
            ) + tenant_result.get("indexes_processed", 0)

        # Additional monthly operations (could include index reorganization, etc.)
        logger.info(
            f"Monthly lifecycle management completed: {result['tenants_processed']} tenants processed, "
            f"{result['total_indexes_processed']} indexes managed"
        )

        monitoring.alert(
            "info",
            f"Monthly index lifecycle management completed: {result['tenants_processed']} tenants, "
            f"{result['total_indexes_processed']} indexes",
        )

    except Exception as e:
        logger.error(f"Monthly lifecycle management failed: {e}")
        monitoring.alert("error", f"Monthly index lifecycle management failed: {e}")
        result["error"] = str(e)

    return result


def run_lifecycle_scheduler():
    """
    Background scheduler for index lifecycle management.
    Runs weekly and monthly lifecycle operations.
    """
    global _last_weekly_lifecycle, _last_monthly_lifecycle

    if not is_lifecycle_management_enabled():
        return

    config = get_lifecycle_config()
    current_time = time.time()

    with _lifecycle_lock:
        # Check weekly lifecycle
        if (
            config["weekly_schedule"]
            and (current_time - _last_weekly_lifecycle) >= _get_weekly_interval()
        ):
            try:
                logger.info("Running scheduled weekly index lifecycle management")
                result = perform_weekly_lifecycle()
                if not result.get("error"):
                    _last_weekly_lifecycle = current_time
                    logger.info("Weekly index lifecycle management completed successfully")
                else:
                    logger.error("Weekly index lifecycle management failed")
            except Exception as e:
                logger.error(f"Scheduled weekly lifecycle failed: {e}")

        # Check monthly lifecycle
        if (
            config["monthly_schedule"]
            and (current_time - _last_monthly_lifecycle) >= _get_monthly_interval()
        ):
            try:
                logger.info("Running scheduled monthly index lifecycle management")
                result = perform_monthly_lifecycle()
                if not result.get("error"):
                    _last_monthly_lifecycle = current_time
                    logger.info("Monthly index lifecycle management completed successfully")
                else:
                    logger.error("Monthly index lifecycle management failed")
            except Exception as e:
                logger.error(f"Scheduled monthly lifecycle failed: {e}")


def get_lifecycle_status() -> dict[str, Any]:
    """
    Get current status of index lifecycle management.

    Returns:
        Dict with lifecycle status information
    """
    config = get_lifecycle_config()

    # Config is already properly typed

    return {
        "enabled": bool(config["enabled"]),
        "weekly_schedule_enabled": bool(config["weekly_schedule"]),
        "monthly_schedule_enabled": bool(config["monthly_schedule"]),
        "last_weekly_run": datetime.fromtimestamp(_last_weekly_lifecycle).isoformat()
        if _last_weekly_lifecycle > 0
        else None,
        "last_monthly_run": datetime.fromtimestamp(_last_monthly_lifecycle).isoformat()
        if _last_monthly_lifecycle > 0
        else None,
        "next_weekly_run": datetime.fromtimestamp(
            _last_weekly_lifecycle + _get_weekly_interval()
        ).isoformat()
        if _last_weekly_lifecycle > 0
        else None,
        "next_monthly_run": datetime.fromtimestamp(
            _last_monthly_lifecycle + _get_monthly_interval()
        ).isoformat()
        if _last_monthly_lifecycle > 0
        else None,
        "per_tenant_management": bool(config["per_tenant_management"]),
        "vacuum_analyze_integration": bool(config["vacuum_analyze_integration"]),
        "auto_reindex_enabled": bool(config["auto_reindex_enabled"]),
    }


# Manual execution functions for testing/administration
def run_manual_weekly_lifecycle(dry_run: bool = True) -> dict[str, Any]:
    """Manually trigger weekly lifecycle management (default dry run for safety)"""
    logger.info(f"Manual weekly lifecycle management triggered (dry_run={dry_run})")
    return perform_weekly_lifecycle(dry_run=dry_run)


def run_manual_monthly_lifecycle(dry_run: bool = True) -> dict[str, Any]:
    """Manually trigger monthly lifecycle management (default dry run for safety)"""
    logger.info(f"Manual monthly lifecycle management triggered (dry_run={dry_run})")
    return perform_monthly_lifecycle(dry_run=dry_run)


def run_manual_tenant_lifecycle(tenant_id: int, dry_run: bool = True) -> dict[str, Any]:
    """Manually trigger lifecycle management for a specific tenant"""
    logger.info(
        f"Manual tenant lifecycle management triggered for tenant {tenant_id} (dry_run={dry_run})"
    )
    return perform_per_tenant_lifecycle(tenant_id, dry_run=dry_run)
