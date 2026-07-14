"""Automatic index cleanup for unused indexes"""

import logging
import math
from contextlib import suppress
from datetime import datetime, timedelta

from src.db import get_cursor
from src.rollback import is_system_enabled

logger = logging.getLogger(__name__)


def find_unused_indexes(min_scans=10, days_unused=7, _min_size_mb=1.0):
    """
    Find indexes that are rarely or never used.

    Args:
        min_scans: Minimum number of scans to consider index as used
        days_unused: Number of days without scans to consider unused
        _min_size_mb: Minimum size threshold

    Returns:
        List of unused indexes
    """
    if not is_system_enabled():
        logger.info("Index cleanup skipped: system is disabled")
        return []
    if min_scans < 0 or days_unused < 0:
        raise ValueError("min_scans and days_unused must be non-negative")
    min_size_mb = float(_min_size_mb)
    if not math.isfinite(min_size_mb) or min_size_mb < 0:
        raise ValueError("min_size_mb must be a finite non-negative number")
    min_size_bytes = int(min_size_mb * 1024 * 1024)

    with get_cursor() as cursor:
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
                "  AND pg_relation_size(indexrelid) >= %s "
                "ORDER BY idx_scan ASC, indexrelname"
            )
            cursor.execute(query, ("public", "idx_%", min_scans, min_size_bytes))
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
        # Use safe access to prevent tuple index errors
        from src.db import safe_get_row_value

        for idx in indexes:
            indexname = safe_get_row_value(idx, "indexname", "")
            tablename = safe_get_row_value(idx, "tablename", "")
            if not indexname or not tablename:
                logger.warning(f"Could not extract index identity from result: {idx}")
                continue

            # Require a real apply receipt for this exact table and index. Advisory
            # CREATE_INDEX events are proposals, not proof that an index was created.
            cursor.execute(
                """
                SELECT created_at, details_json
                FROM mutation_log
                WHERE mutation_type = 'CREATE_INDEX'
                  AND table_name = %s
                  AND details_json->>'index_name' = %s
                  AND details_json->>'mode' = 'apply'
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (tablename, indexname),
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
                    with suppress(ValueError):
                        created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                index_scans_raw = safe_get_row_value(idx, "index_scans", 0)
                index_size_bytes_raw = safe_get_row_value(idx, "index_size_bytes", 0)

                # Type narrowing: index_scans and index_size_bytes should be int from database
                index_scans = index_scans_raw if isinstance(index_scans_raw, int) else 0
                index_size_bytes = (
                    index_size_bytes_raw if isinstance(index_size_bytes_raw, int) else 0
                )

                now = datetime.now(created_at.tzinfo) if created_at else None
                cutoff_date = now - timedelta(days=days_unused) if now else None
                if (
                    created_at
                    and cutoff_date
                    and created_at < cutoff_date
                    and index_scans < min_scans
                ):
                    unused.append(
                        {
                            "indexname": indexname,
                            "tablename": tablename,
                            "scans": index_scans,
                            "size_bytes": index_size_bytes,
                            "created_at": created_at.isoformat(),
                            "days_unused": (now - created_at).days if now else None,
                            "evidence_status": "low_cumulative_usage_over_known_age",
                            "safe_to_drop": False,
                        }
                    )
                # Missing or young creation evidence is intentionally not a cleanup candidate.
            # Indexes not recorded as created by IndexPilot remain outside this legacy detector.

        return unused


def cleanup_unused_indexes(min_scans=10, days_unused=7, _min_size_mb=1.0, dry_run=True):
    """
    Remove unused indexes.

    Args:
        min_scans: Minimum number of scans to consider index as used
        days_unused: Number of days without scans to consider unused
        _min_size_mb: Minimum size threshold
        dry_run: Must remain True; automatic deletion is disabled

    Returns:
        List of indexes removed (or would be removed)
    """
    if not is_system_enabled():
        logger.info("Index cleanup skipped: system is disabled")
        return []

    if not dry_run:
        raise RuntimeError(
            "automatic_index_drop_disabled: review evidence and perform any DROP INDEX "
            "through an explicit operator-controlled database migration"
        )

    unused = find_unused_indexes(min_scans, days_unused, _min_size_mb)

    if not unused:
        logger.info("No unused indexes found")
        return []

    removed = []
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
