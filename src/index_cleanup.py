"""Automatic index cleanup for unused indexes"""

import logging
from datetime import datetime, timedelta

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.monitoring import get_monitoring
from src.resilience import safe_database_operation
from src.rollback import is_system_enabled

logger = logging.getLogger(__name__)


def find_unused_indexes(min_scans=10, days_unused=7, _min_size_mb=1.0):
    """
    Find indexes that are rarely or never used.

    Args:
        min_scans: Minimum number of scans to consider index as used
        days_unused: Number of days without scans to consider unused
        _min_size_mb: Minimum size threshold (reserved for future use)

    Returns:
        List of unused indexes
    """
    if not is_system_enabled():
        logger.info("Index cleanup skipped: system is disabled")
        return []

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get index usage statistics
            cursor.execute(
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched,
                    pg_size_bytes(pg_relation_size(indexname::regclass)) as index_size_bytes
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                  AND indexname LIKE 'idx_%'
                  AND idx_scan < %s
                ORDER BY idx_scan ASC, indexname
            """,
                (min_scans,),
            )

            indexes = cursor.fetchall()

            # Filter by age (check when index was created)
            unused = []
            cutoff_date = datetime.now() - timedelta(days=days_unused)

            for idx in indexes:
                # Check if index was created by our system
                cursor.execute(
                    """
                    SELECT created_at, details_json
                    FROM mutation_log
                    WHERE mutation_type = 'CREATE_INDEX'
                      AND details_json::text LIKE %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """,
                    (f"%{idx['indexname']}%",),
                )

                creation_record = cursor.fetchone()

                if creation_record:
                    # Use safe access to prevent tuple index errors
                    from src.db import safe_get_row_value
                    
                    created_at = safe_get_row_value(creation_record, "created_at", None)
                    if created_at and isinstance(created_at, datetime):
                        if created_at < cutoff_date and idx["index_scans"] < min_scans:
                            unused.append(
                                {
                                    "indexname": idx["indexname"],
                                    "tablename": idx["tablename"],
                                    "scans": idx["index_scans"],
                                    "size_bytes": idx["index_size_bytes"],
                                    "created_at": created_at.isoformat(),
                                    "days_unused": (datetime.now() - created_at).days,
                                }
                            )
                    elif idx["index_scans"] < min_scans:
                        # Creation record exists but created_at is missing/invalid
                        unused.append(
                            {
                                "indexname": idx["indexname"],
                                "tablename": idx["tablename"],
                                "scans": idx["index_scans"],
                                "size_bytes": idx["index_size_bytes"],
                                "created_at": None,
                                "days_unused": None,
                            }
                        )
                elif idx["index_scans"] < min_scans:
                    # Index with no creation record but low usage
                    unused.append(
                        {
                            "indexname": idx["indexname"],
                            "tablename": idx["tablename"],
                            "scans": idx["index_scans"],
                            "size_bytes": idx["index_size_bytes"],
                            "created_at": None,
                            "days_unused": None,
                        }
                    )

            return unused
        finally:
            cursor.close()


def cleanup_unused_indexes(min_scans=10, days_unused=7, _min_size_mb=1.0, dry_run=True):
    """
    Remove unused indexes.

    Args:
        min_scans: Minimum number of scans to consider index as used
        days_unused: Number of days without scans to consider unused
        _min_size_mb: Minimum size threshold (reserved for future use)
        dry_run: If True, only report what would be deleted

    Returns:
        List of indexes removed (or would be removed)
    """
    if not is_system_enabled():
        logger.info("Index cleanup skipped: system is disabled")
        return []

    unused = find_unused_indexes(min_scans, days_unused)

    if not unused:
        logger.info("No unused indexes found")
        return []

    removed = []
    monitoring = get_monitoring()

    for idx in unused:
        index_name = idx["indexname"]
        table_name = idx["tablename"]

        if dry_run:
            logger.info(
                f"[DRY RUN] Would remove unused index: {index_name} "
                f"(table: {table_name}, scans: {idx['scans']}, "
                f"size: {idx['size_bytes'] / 1024 / 1024:.2f}MB)"
            )
            removed.append(idx)
        else:
            try:
                # Use safe database operation for transaction safety
                with safe_database_operation(
                    "index_cleanup", table_name, rollback_on_failure=True
                ) as conn:
                    cursor = conn.cursor(cursor_factory=RealDictCursor)
                    try:
                        # Drop the index
                        logger.info(
                            f"Removing unused index: {index_name} "
                            f"(table: {table_name}, scans: {idx['scans']})"
                        )
                        cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')

                        # Log the removal to audit trail
                        from src.audit import log_audit_event

                        log_audit_event(
                            "DROP_INDEX",
                            table_name=table_name,
                            details={
                                "index_name": index_name,
                                "reason": "unused",
                                "scans": idx["scans"],
                                "size_bytes": idx["size_bytes"],
                                "days_unused": idx.get("days_unused"),
                            },
                            severity="info",
                        )

                        # Commit is handled by safe_database_operation
                        removed.append(idx)

                        monitoring.alert(
                            "info",
                            f"Removed unused index: {index_name} "
                            f"(scans: {idx['scans']}, "
                            f"size: {idx['size_bytes'] / 1024 / 1024:.2f}MB)",
                        )
                    except Exception as e:
                        # Rollback is handled by safe_database_operation
                        logger.error(f"Failed to remove index {index_name}: {e}")
                        monitoring.alert(
                            "warning", f"Failed to remove unused index {index_name}: {e}"
                        )
                        raise
                    finally:
                        cursor.close()
            except Exception as e:
                logger.error(f"Error removing index {index_name}: {e}")
                continue

    logger.info(f"{'Would remove' if dry_run else 'Removed'} {len(removed)} unused indexes")
    return removed


def get_index_statistics():
    """Get statistics on all indexes"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
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
                    pg_size_bytes(pg_relation_size(tablename::regclass)) as table_size_bytes
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                  AND indexname LIKE 'idx_%'
                ORDER BY idx_scan ASC
            """
            )
            return cursor.fetchall()
        finally:
            cursor.close()
