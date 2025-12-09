"""Automatic index cleanup for unused indexes"""

import logging
from datetime import datetime, timedelta

from psycopg2.extras import RealDictCursor

from src.db import get_connection, get_cursor
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
            # Note: pg_stat_user_indexes uses relname (not tablename) and indexrelname (not indexname)
            # Use pg_relation_size directly (returns bytes), not pg_size_bytes
            # Wrap in try-except for graceful error handling
            try:
                # Use parameterized query to avoid potential issues with RealDictCursor
                query = (
                    "SELECT "
                    "schemaname, "
                    "relname as tablename, "
                    "indexrelname as indexname, "
                    "idx_scan as index_scans, "
                    "idx_tup_read as tuples_read, "
                    "idx_tup_fetch as tuples_fetched, "
                    "pg_relation_size(indexrelid) as index_size_bytes "
                    "FROM pg_stat_user_indexes "
                    "WHERE schemaname = %s "
                    "  AND indexrelname LIKE %s "
                    "  AND idx_scan < %s "
                    "ORDER BY idx_scan ASC, indexrelname"
                )
                cursor.execute(query, ("public", "idx_%", min_scans))
            except Exception as e:
                # Handle query errors gracefully
                import traceback

                error_type = type(e).__name__
                logger.warning(
                    f"Failed to query index statistics ({error_type}): {e}. "
                    f"This may indicate a database state issue or driver problem."
                )
                if isinstance(e, IndexError):
                    logger.debug(f"IndexError traceback: {traceback.format_exc()}")
                return []  # Return empty list instead of crashing

            indexes = cursor.fetchall()

            # Filter by age (check when index was created)
            unused = []
            cutoff_date = datetime.now() - timedelta(days=days_unused)

            # Use safe access to prevent tuple index errors
            from src.db import safe_get_row_value

            for idx in indexes:
                indexname = safe_get_row_value(idx, "indexname", "")
                if not indexname:
                    logger.warning(f"Could not extract indexname from result: {idx}")
                    continue

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
                    (f"%{indexname}%",),
                )

                creation_record = cursor.fetchone()

                if creation_record:
                    # Use safe access to prevent tuple index errors
                    from src.db import safe_get_row_value

                    created_at_raw = safe_get_row_value(creation_record, "created_at", None)
                    # Database rows can contain datetime objects even though JSONValue doesn't include it
                    # We need to check at runtime since the type system doesn't know about datetime in DB rows
                    created_at: datetime | None = None
                    # Type narrowing: database rows can contain datetime objects
                    # Use object type to allow runtime isinstance check
                    created_at_obj: object = created_at_raw
                    if isinstance(created_at_obj, datetime):
                        created_at = created_at_obj
                    elif isinstance(created_at_raw, str):
                        # Try parsing if it's a string representation
                        try:
                            from dateutil.parser import parse  # type: ignore[import-untyped]

                            created_at = parse(created_at_raw)
                        except Exception:
                            pass
                    index_scans_raw = safe_get_row_value(idx, "index_scans", 0)
                    tablename = safe_get_row_value(idx, "tablename", "")
                    index_size_bytes_raw = safe_get_row_value(idx, "index_size_bytes", 0)

                    # Type narrowing: index_scans and index_size_bytes should be int from database
                    index_scans = index_scans_raw if isinstance(index_scans_raw, int) else 0
                    index_size_bytes = (
                        index_size_bytes_raw if isinstance(index_size_bytes_raw, int) else 0
                    )

                    if created_at and created_at < cutoff_date and index_scans < min_scans:
                        unused.append(
                            {
                                "indexname": indexname,
                                "tablename": tablename,
                                "scans": index_scans,
                                "size_bytes": index_size_bytes,
                                "created_at": created_at.isoformat(),
                                "days_unused": (datetime.now() - created_at).days,
                            }
                        )
                    elif index_scans < min_scans:
                        # Creation record exists but created_at is missing/invalid
                        unused.append(
                            {
                                "indexname": indexname,
                                "tablename": tablename,
                                "scans": index_scans,
                                "size_bytes": index_size_bytes,
                                "created_at": None,
                                "days_unused": None,
                            }
                        )
                else:
                    index_scans_raw = safe_get_row_value(idx, "index_scans", 0)
                    tablename = safe_get_row_value(idx, "tablename", "")
                    index_size_bytes_raw = safe_get_row_value(idx, "index_size_bytes", 0)

                    # Type narrowing: index_scans and index_size_bytes should be int from database
                    index_scans = index_scans_raw if isinstance(index_scans_raw, int) else 0
                    index_size_bytes = (
                        index_size_bytes_raw if isinstance(index_size_bytes_raw, int) else 0
                    )

                    if index_scans < min_scans:
                        # Index with no creation record but low usage
                        unused.append(
                            {
                                "indexname": indexname,
                                "tablename": tablename,
                                "scans": index_scans,
                                "size_bytes": index_size_bytes,
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
    with get_cursor() as cursor:
        # Note: pg_stat_user_indexes uses relname (not tablename) and indexrelname (not indexname)
        cursor.execute(
            """
                SELECT
                    schemaname,
                    relname as tablename,
                    indexrelname as indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched,
                    pg_relation_size(indexrelid) as index_size_bytes,
                    pg_relation_size(relid) as table_size_bytes
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                  AND indexrelname LIKE 'idx_%'
                ORDER BY idx_scan ASC
            """
        )
        return cursor.fetchall()
