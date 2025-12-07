"""Index health monitoring and maintenance"""

import logging
from datetime import datetime
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.monitoring import get_monitoring
from src.resilience import safe_database_operation
from src.rollback import is_system_enabled

logger = logging.getLogger(__name__)


def monitor_index_health(
    bloat_threshold_percent: float = 20.0,
    min_size_mb: float = 1.0,
) -> dict[str, Any]:
    """
    Monitor index health: bloat, usage statistics, and size growth.

    Args:
        bloat_threshold_percent: Threshold for index bloat (default: 20%)
        min_size_mb: Minimum index size to monitor (default: 1MB)

    Returns:
        dict with health metrics for all indexes
    """
    if not is_system_enabled():
        logger.info("Index health monitoring skipped: system is disabled")
        return {"status": "disabled", "indexes": []}

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get comprehensive index statistics
            cursor.execute(
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched,
                    pg_size_bytes(pg_relation_size(indexname::regclass)) as index_size_bytes,
                    pg_size_bytes(pg_relation_size(tablename::regclass)) as table_size_bytes,
                    -- Estimate bloat using pg_stat_user_indexes and pg_class
                    (pg_stat_user_indexes.idx_scan::float / NULLIF(
                        (SELECT reltuples FROM pg_class WHERE oid = pg_stat_user_indexes.indexrelid), 0
                    )) as scan_efficiency
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                  AND indexname LIKE 'idx_%'
                ORDER BY indexname
            """
            )

            indexes = cursor.fetchall()
            health_data: dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "total_indexes": len(indexes),
                "indexes": [],
                "summary": {
                    "bloated": 0,
                    "underutilized": 0,
                    "healthy": 0,
                    "total_size_mb": 0.0,
                },
            }

            monitoring = get_monitoring()

            for idx in indexes:
                index_name = idx["indexname"]
                table_name = idx["tablename"]
                index_size_bytes = idx.get("index_size_bytes", 0) or 0
                table_size_bytes = idx.get("table_size_bytes", 0) or 0
                index_scans = idx.get("index_scans", 0) or 0
                index_size_mb = index_size_bytes / (1024 * 1024)

                # Skip small indexes
                if index_size_mb < min_size_mb:
                    continue

                # Calculate bloat estimate (simplified - actual bloat requires pgstattuple extension)
                # For now, we use scan efficiency as a proxy
                scan_efficiency = idx.get("scan_efficiency", 0) or 0

                # Get index creation date for growth tracking
                cursor.execute(
                    """
                    SELECT created_at, details_json
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                      AND details_json::text LIKE %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """,
                    (f"%{index_name}%",),
                )
                creation_record = cursor.fetchone()
                created_at = creation_record["created_at"] if creation_record else None
                age_days = (datetime.now() - created_at).days if created_at else None

                # Determine health status
                is_bloated = False
                is_underutilized = False
                health_status = "healthy"

                # Check for bloat (low scan efficiency + high size)
                if scan_efficiency < 0.1 and index_size_mb > 10:
                    is_bloated = True
                    health_status = "bloated"
                    summary = health_data["summary"]
                    if isinstance(summary, dict):
                        summary["bloated"] = summary.get("bloated", 0) + 1

                # Check for underutilization (low scans relative to age)
                if age_days and age_days > 7:
                    scans_per_day = index_scans / age_days if age_days > 0 else 0
                    if scans_per_day < 1.0:  # Less than 1 scan per day
                        is_underutilized = True
                        if not is_bloated:
                            health_status = "underutilized"
                            summary = health_data["summary"]
                            if isinstance(summary, dict):
                                summary["underutilized"] = summary.get("underutilized", 0) + 1

                if health_status == "healthy":
                    summary = health_data["summary"]
                    if isinstance(summary, dict):
                        summary["healthy"] = summary.get("healthy", 0) + 1

                index_health = {
                    "indexname": index_name,
                    "tablename": table_name,
                    "size_mb": round(index_size_mb, 2),
                    "size_bytes": index_size_bytes,
                    "table_size_mb": round(table_size_bytes / (1024 * 1024), 2),
                    "index_scans": index_scans,
                    "tuples_read": idx.get("tuples_read", 0) or 0,
                    "tuples_fetched": idx.get("tuples_fetched", 0) or 0,
                    "scan_efficiency": round(scan_efficiency, 4) if scan_efficiency else 0,
                    "created_at": created_at.isoformat() if created_at else None,
                    "age_days": age_days,
                    "health_status": health_status,
                    "is_bloated": is_bloated,
                    "is_underutilized": is_underutilized,
                }

                indexes_list = health_data["indexes"]
                if isinstance(indexes_list, list):
                    indexes_list.append(index_health)
                summary = health_data["summary"]
                if isinstance(summary, dict):
                    summary["total_size_mb"] = summary.get("total_size_mb", 0.0) + index_size_mb

                # Alert on issues
                if is_bloated:
                    monitoring.alert(
                        "warning",
                        f"Index {index_name} on {table_name} appears bloated "
                        f"(size: {index_size_mb:.2f}MB, efficiency: {scan_efficiency:.4f})",
                    )
                elif is_underutilized:
                    monitoring.alert(
                        "info",
                        f"Index {index_name} on {table_name} is underutilized "
                        f"(scans: {index_scans}, age: {age_days} days)",
                    )

            summary = health_data["summary"]
            if isinstance(summary, dict):
                summary["total_size_mb"] = round(summary.get("total_size_mb", 0.0), 2)

            summary = health_data.get("summary", {})
            healthy = summary.get("healthy", 0) if isinstance(summary, dict) else 0
            bloated = summary.get("bloated", 0) if isinstance(summary, dict) else 0
            underutilized = summary.get("underutilized", 0) if isinstance(summary, dict) else 0
            logger.info(
                f"Index health check: {healthy} healthy, "
                f"{bloated} bloated, "
                f"{underutilized} underutilized"
            )

            return health_data

        finally:
            cursor.close()


def find_bloated_indexes(
    bloat_threshold_percent: float = 20.0,
    min_size_mb: float = 10.0,
) -> list[dict[str, Any]]:
    """
    Find indexes that need REINDEX due to bloat.

    Args:
        bloat_threshold_percent: Bloat threshold (default: 20%)
        min_size_mb: Minimum index size to consider (default: 10MB)

    Returns:
        List of bloated indexes
    """
    health_data = monitor_index_health(
        bloat_threshold_percent=bloat_threshold_percent, min_size_mb=min_size_mb
    )

    bloated = [idx for idx in health_data.get("indexes", []) if idx.get("is_bloated", False)]

    return bloated


def reindex_bloated_indexes(
    bloat_threshold_percent: float = 20.0,
    min_size_mb: float = 10.0,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """
    Automatically REINDEX bloated indexes.

    Args:
        bloat_threshold_percent: Bloat threshold (default: 20%)
        min_size_mb: Minimum index size to consider (default: 10MB)
        dry_run: If True, only report what would be reindexed

    Returns:
        List of indexes reindexed (or would be reindexed)
    """
    if not is_system_enabled():
        logger.info("Index reindexing skipped: system is disabled")
        return []

    bloated = find_bloated_indexes(
        bloat_threshold_percent=bloat_threshold_percent, min_size_mb=min_size_mb
    )

    if not bloated:
        logger.info("No bloated indexes found")
        return []

    reindexed = []
    monitoring = get_monitoring()

    for idx in bloated:
        index_name = idx["indexname"]
        table_name = idx["tablename"]

        if dry_run:
            logger.info(
                f"[DRY RUN] Would REINDEX: {index_name} "
                f"(table: {table_name}, size: {idx['size_mb']:.2f}MB, "
                f"efficiency: {idx.get('scan_efficiency', 0):.4f})"
            )
            reindexed.append(idx)
        else:
            try:
                with safe_database_operation(
                    "index_reindex", table_name, rollback_on_failure=True
                ) as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    try:
                        logger.info(
                            f"REINDEXing bloated index: {index_name} "
                            f"(table: {table_name}, size: {idx['size_mb']:.2f}MB)"
                        )
                        # Try REINDEX CONCURRENTLY first (PostgreSQL 12+)
                        # If it fails, fall back to regular REINDEX
                        try:
                            cursor.execute(f'REINDEX INDEX CONCURRENTLY "{index_name}"')
                        except Exception:
                            # REINDEX CONCURRENTLY not available, use regular REINDEX
                            logger.warning(
                                f"REINDEX CONCURRENTLY not available for {index_name}, "
                                "using regular REINDEX (may block writes)"
                            )
                            cursor.execute(f'REINDEX INDEX "{index_name}"')

                        # Log to audit trail
                        from src.audit import log_audit_event

                        log_audit_event(
                            "REINDEX_INDEX",
                            table_name=table_name,
                            details={
                                "index_name": index_name,
                                "reason": "bloat",
                                "size_mb": idx["size_mb"],
                                "scan_efficiency": idx.get("scan_efficiency", 0),
                            },
                            severity="info",
                        )

                        reindexed.append(idx)

                        monitoring.alert(
                            "info",
                            f"REINDEXed bloated index: {index_name} (size: {idx['size_mb']:.2f}MB)",
                        )
                    except Exception:
                        # REINDEX CONCURRENTLY may not be available in all PostgreSQL versions
                        # Fall back to regular REINDEX
                        try:
                            logger.warning(
                                f"REINDEX CONCURRENTLY failed for {index_name}, "
                                "trying regular REINDEX: {e}"
                            )
                            cursor.execute(f'REINDEX INDEX "{index_name}"')
                            reindexed.append(idx)
                        except Exception as e2:
                            logger.error(f"Failed to REINDEX {index_name}: {e2}")
                            monitoring.alert("error", f"Failed to REINDEX {index_name}: {e2}")
                            raise
                    finally:
                        cursor.close()
            except Exception as e:
                logger.error(f"Error REINDEXing {index_name}: {e}")
                continue

    logger.info(f"{'Would REINDEX' if dry_run else 'REINDEXed'} {len(reindexed)} bloated indexes")
    return reindexed
