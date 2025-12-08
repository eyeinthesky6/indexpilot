"""Resilience and corruption prevention mechanisms"""

import logging
import threading
import time
from contextlib import contextmanager

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection, safe_get_row_value
from src.monitoring import get_monitoring
from src.rollback import is_system_enabled
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()

# Track active operations that could cause corruption
_active_operations: dict[str, JSONDict] = {}
_operations_lock = threading.Lock()


def _get_max_operation_duration() -> int:
    """Get maximum operation duration from config or default"""
    return _config_loader.get_int(
        "features.resilience.max_operation_duration_seconds", 600
    )  # 10 minutes default


@contextmanager
def safe_database_operation(operation_name: str, resource: str, rollback_on_failure: bool = True):
    """
    Context manager for safe database operations with automatic rollback.

    Ensures operations are:
    - Tracked for monitoring
    - Rolled back on failure
    - Checked against system enable status
    - Protected from concurrent execution

    Args:
        operation_name: Name of the operation (e.g., 'index_creation')
        resource: Resource being modified (e.g., table name)
        rollback_on_failure: If True, rollback transaction on failure

    Yields:
        Connection object
    """
    # Check if system is enabled
    if not is_system_enabled():
        raise RuntimeError(f"Operation {operation_name} blocked: system is disabled")

    operation_id = f"{operation_name}:{resource}:{time.time()}"
    start_time = time.time()

    # Track operation
    with _operations_lock:
        if resource in _active_operations:
            existing = _active_operations[resource]
            raise RuntimeError(
                f"Operation {operation_name} on {resource} blocked: "
                f"another operation ({existing['name']}) is in progress"
            )
        _active_operations[resource] = {
            "id": operation_id,
            "name": operation_name,
            "started_at": start_time,
        }

    conn = None
    try:
        with get_connection() as conn:
            # Set transaction isolation level for safety
            cursor = conn.cursor()
            try:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                cursor.close()
            except Exception as e:
                logger.warning(f"Failed to set transaction isolation: {e}")

            try:
                yield conn
                # Success - commit is handled by get_connection context manager
            except Exception as e:
                if rollback_on_failure:
                    try:
                        conn.rollback()
                        logger.info(f"Rolled back {operation_name} on {resource} due to error: {e}")
                    except Exception as rollback_error:
                        logger.error(
                            f"Failed to rollback {operation_name} on {resource}: {rollback_error}"
                        )
                        # This is critical - log to monitoring
                        monitoring = get_monitoring()
                        monitoring.alert(
                            "critical",
                            f"Failed to rollback {operation_name} on {resource}: {rollback_error}",
                        )
                raise
    finally:
        # Remove from active operations
        with _operations_lock:
            _active_operations.pop(resource, None)
        duration = time.time() - start_time
        if duration > _get_max_operation_duration():
            logger.warning(f"Operation {operation_name} on {resource} took {duration:.2f}s")


def check_database_integrity() -> JSONDict:
    """
    Check database integrity and detect potential corruption.

    Returns:
        dict with integrity check results
    """
    results: JSONDict = {"status": "healthy", "checks": {}, "issues": []}
    # Type narrowing: ensure issues is a list for append operations
    issues_list: list[dict[str, JSONValue]] = []
    # Type narrowing: ensure checks is a dict for indexed assignment
    checks_dict: dict[str, JSONValue] = {}
    checks_val = results.get("checks")
    if isinstance(checks_val, dict):
        checks_dict = {str(k): v for k, v in checks_val.items()}
    results["checks"] = checks_dict

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Check for orphaned indexes (indexes without corresponding table)
            try:
                cursor.execute(
                    """
                    SELECT
                        i.indexname,
                        i.tablename
                    FROM pg_indexes i
                    LEFT JOIN pg_class t ON t.relname = i.tablename
                    WHERE i.schemaname = 'public'
                      AND i.indexname LIKE 'idx_%'
                      AND t.oid IS NULL
                """
                )
                orphaned = cursor.fetchall()
                if orphaned:
                    issues_list.append(
                        {
                            "type": "orphaned_indexes",
                            "count": len(orphaned),
                            "indexes": [idx["indexname"] for idx in orphaned],
                        }
                    )
                    results["status"] = "degraded"
                checks_dict["orphaned_indexes"] = len(orphaned)
            except Exception as e:
                logger.error(f"Failed to check orphaned indexes: {e}")
                checks_dict["orphaned_indexes"] = "error"

            # Check for invalid indexes
            try:
                cursor.execute(
                    """
                    SELECT
                        schemaname,
                        tablename,
                        indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND indexname LIKE 'idx_%'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM pg_index
                          WHERE indexrelid = (
                              SELECT oid FROM pg_class WHERE relname = indexname
                          )
                          AND indisvalid = TRUE
                      )
                """
                )
                invalid = cursor.fetchall()
                if invalid:
                    issues_list.append(
                        {
                            "type": "invalid_indexes",
                            "count": len(invalid),
                            "indexes": [
                                str(idx.get("indexname", ""))
                                for idx in invalid
                                if isinstance(idx, dict)
                            ],
                        }
                    )
                    results["status"] = "degraded"
                checks_dict["invalid_indexes"] = len(invalid)
            except Exception as e:
                logger.error(f"Failed to check invalid indexes: {e}")
                checks_dict["invalid_indexes"] = "error"

            # Check for stale advisory locks
            try:
                cursor.execute(
                    """
                    SELECT
                        locktype,
                        objid,
                        pid,
                        mode,
                        granted
                    FROM pg_locks
                    WHERE locktype = 'advisory'
                      AND granted = TRUE
                      AND pid NOT IN (SELECT pid FROM pg_stat_activity)
                """
                )
                stale_locks = cursor.fetchall()
                if stale_locks:
                    locks_list: list[JSONValue] = []
                    for lock in stale_locks:
                        if isinstance(lock, dict):
                            objid_val = lock.get("objid")
                            if objid_val is not None:
                                locks_list.append(objid_val)
                    issues_list.append(
                        {
                            "type": "stale_advisory_locks",
                            "count": len(stale_locks),
                            "locks": locks_list,
                        }
                    )
                    results["status"] = "degraded"
                checks_dict["stale_advisory_locks"] = len(stale_locks)
            except Exception as e:
                logger.error(f"Failed to check stale locks: {e}")
                checks_dict["stale_advisory_locks"] = "error"

            # Check for active operations that might be stale
            with _operations_lock:
                current_time = time.time()
                stale_operations: list[JSONDict] = []
                for resource, op_info in _active_operations.items():
                    started_at_val = op_info.get("started_at", 0)
                    started_at = started_at_val if isinstance(started_at_val, int | float) else 0.0
                    duration = current_time - float(started_at)
                    if duration > _get_max_operation_duration():
                        op_name_val = op_info.get("name", "unknown")
                        op_name = str(op_name_val) if op_name_val is not None else "unknown"
                        stale_operations.append(
                            {"resource": resource, "operation": op_name, "duration": duration}
                        )
                if stale_operations:
                    issues_list.append(
                        {
                            "type": "stale_operations",
                            "count": len(stale_operations),
                            "operations": stale_operations,  # type: ignore[dict-item]
                        }
                    )
                    results["status"] = "degraded"
                checks_dict["stale_operations"] = len(stale_operations)

            cursor.close()

    except Exception as e:
        logger.error(f"Database integrity check failed: {e}")
        results["status"] = "error"
        results["error"] = str(e)

    # Assign issues_list and checks_dict back to results
    # Both are JSONValue-compatible (list and dict are valid JSONValue types)
    results["issues"] = issues_list  # type: ignore[assignment]
    results["checks"] = checks_dict
    return results


def cleanup_orphaned_indexes() -> list[str]:
    """
    Clean up orphaned indexes (indexes without corresponding tables).

    Returns:
        List of cleaned up index names
    """
    cleaned = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Find orphaned indexes
            cursor.execute(
                """
                SELECT
                    i.indexname
                FROM pg_indexes i
                LEFT JOIN pg_class t ON t.relname = i.tablename
                WHERE i.schemaname = 'public'
                  AND i.indexname LIKE 'idx_%'
                  AND t.oid IS NULL
            """
            )
            orphaned = cursor.fetchall()

            for idx in orphaned:
                index_name = idx["indexname"]
                try:
                    logger.info(f"Cleaning up orphaned index: {index_name}")
                    cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')
                    conn.commit()
                    cleaned.append(index_name)
                except Exception as e:
                    logger.error(f"Failed to drop orphaned index {index_name}: {e}")
                    conn.rollback()

            cursor.close()

    except Exception as e:
        logger.error(f"Failed to cleanup orphaned indexes: {e}")

    return cleaned


def cleanup_invalid_indexes() -> list[str]:
    """
    Clean up invalid indexes (indexes marked as invalid).

    Returns:
        List of cleaned up index names
    """
    cleaned = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Find invalid indexes
            cursor.execute(
                """
                SELECT
                    i.indexname,
                    i.tablename
                FROM pg_indexes i
                JOIN pg_class ic ON ic.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = ic.oid
                WHERE i.schemaname = 'public'
                  AND i.indexname LIKE 'idx_%'
                  AND idx.indisvalid = FALSE
            """
            )
            invalid = cursor.fetchall()

            for idx in invalid:
                index_name = idx["indexname"]
                table_name = idx["tablename"]
                try:
                    logger.info(f"Cleaning up invalid index: {index_name} on {table_name}")
                    cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')
                    conn.commit()
                    cleaned.append(index_name)

                    # Log to audit trail
                    from src.audit import log_audit_event

                    log_audit_event(
                        "DROP_INDEX",
                        table_name=table_name,
                        details={
                            "index_name": index_name,
                            "reason": "invalid_index",
                            "action": "cleanup",
                        },
                        severity="warning",
                    )
                except Exception as e:
                    logger.error(f"Failed to drop invalid index {index_name}: {e}")
                    conn.rollback()

            cursor.close()

    except Exception as e:
        logger.error(f"Failed to cleanup invalid indexes: {e}")

    return cleaned


def cleanup_stale_advisory_locks() -> int:
    """
    Clean up stale advisory locks (locks from dead processes).

    Returns:
        Number of locks cleaned up
    """
    cleaned = 0

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Find stale advisory locks
            cursor.execute(
                """
                SELECT
                    objid
                FROM pg_locks
                WHERE locktype = 'advisory'
                  AND granted = TRUE
                  AND pid NOT IN (SELECT pid FROM pg_stat_activity)
            """
            )
            stale_locks = cursor.fetchall()

            for lock in stale_locks:
                objid = safe_get_row_value(lock, 0, None) or safe_get_row_value(lock, "objid", None)
                if objid is None:
                    continue
                try:
                    # Try to release the lock
                    cursor.execute("SELECT pg_advisory_unlock(%s)", (objid,))
                    result = cursor.fetchone()
                    unlock_result = safe_get_row_value(result, 0, False) or safe_get_row_value(result, "pg_advisory_unlock", False)
                    if unlock_result:
                        cleaned += 1
                        logger.info(f"Released stale advisory lock: {objid}")
                except Exception as e:
                    logger.warning(f"Failed to release stale lock {objid}: {e}")

            conn.commit()
            cursor.close()

    except Exception as e:
        logger.error(f"Failed to cleanup stale advisory locks: {e}")

    return cleaned


def verify_index_integrity(table_name: str, index_name: str) -> bool:
    """
    Verify that an index is valid and not corrupted.

    Args:
        table_name: Table name
        index_name: Index name

    Returns:
        True if index is valid, False otherwise
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            cursor.execute(
                """
                SELECT
                    idx.indisvalid,
                    idx.indisready,
                    idx.indislive
                FROM pg_index idx
                JOIN pg_class ic ON ic.oid = idx.indexrelid
                JOIN pg_class tc ON tc.oid = idx.indrelid
                WHERE ic.relname = %s
                  AND tc.relname = %s
            """,
                (index_name, table_name),
            )

            result = cursor.fetchone()
            cursor.close()

            if not result:
                return False

            # Index is valid if all flags are true
            is_valid = bool(result["indisvalid"] and result["indisready"] and result["indislive"])
            return is_valid

    except Exception as e:
        logger.error(f"Failed to verify index integrity for {index_name}: {e}")
        return False


def get_active_operations() -> list[JSONDict]:
    """
    Get list of currently active operations.

    Returns:
        List of active operation info
    """
    with _operations_lock:
        current_time = time.time()
        return [
            {
                "resource": resource,
                "operation": info["name"],
                "id": info["id"],
                "duration": current_time
                - (
                    float(started_at_val)
                    if isinstance((started_at_val := info.get("started_at")), int | float)
                    else 0.0
                ),
            }
            for resource, info in _active_operations.items()
        ]
