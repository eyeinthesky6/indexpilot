"""Lock management to prevent long table locks"""

import logging
import threading
import time
from contextlib import contextmanager, suppress

from psycopg2.extras import RealDictCursor

from src.cpu_throttle import (
    monitor_cpu_during_operation,
    record_index_creation,
    should_throttle_index_creation,
    wait_for_cpu_cooldown,
)
from src.error_handler import IndexCreationError
from src.monitoring import get_monitoring
from src.resilience import safe_database_operation, verify_index_integrity

logger = logging.getLogger(__name__)

# Track active locks
_active_locks = {}
_lock_tracker_lock = threading.Lock()

# Maximum lock duration (seconds)
MAX_LOCK_DURATION = 300  # 5 minutes


def track_lock(lock_type, resource, timeout=None):
    """
    Track a lock acquisition.

    Args:
        lock_type: Type of lock (e.g., 'index_creation', 'table_alter')
        resource: Resource being locked (e.g., table name)
        timeout: Maximum duration for the lock
    """
    lock_id = f"{lock_type}:{resource}:{time.time()}"

    with _lock_tracker_lock:
        _active_locks[lock_id] = {
            "type": lock_type,
            "resource": resource,
            "started_at": time.time(),
            "timeout": timeout or MAX_LOCK_DURATION,
        }

    logger.debug(f"Lock acquired: {lock_id}")
    return lock_id


def release_lock(lock_id):
    """Release a tracked lock"""
    with _lock_tracker_lock:
        if lock_id in _active_locks:
            duration = time.time() - _active_locks[lock_id]["started_at"]
            lock_info = _active_locks.pop(lock_id)
            logger.debug(f"Lock released: {lock_id} (duration: {duration:.2f}s)")

            # Alert if lock was held too long
            if duration > lock_info["timeout"]:
                monitoring = get_monitoring()
                monitoring.alert(
                    "warning",
                    f"Lock {lock_info['type']} on {lock_info['resource']} "
                    f"held for {duration:.2f}s (exceeded {lock_info['timeout']}s)",
                )
            return duration
    return None


def check_stale_locks():
    """Check for stale locks that may have been abandoned"""
    current_time = time.time()
    stale_locks = []

    with _lock_tracker_lock:
        for lock_id, lock_info in list(_active_locks.items()):
            duration = current_time - lock_info["started_at"]
            if duration > lock_info["timeout"] * 2:  # 2x timeout = stale
                stale_locks.append(
                    {
                        "lock_id": lock_id,
                        "type": lock_info["type"],
                        "resource": lock_info["resource"],
                        "duration": duration,
                    }
                )
                # Remove stale lock
                _active_locks.pop(lock_id)

    if stale_locks:
        monitoring = get_monitoring()
        for stale in stale_locks:
            monitoring.alert(
                "warning",
                f"Stale lock detected: {stale['type']} on {stale['resource']} "
                f"(duration: {stale['duration']:.2f}s)",
            )

    return stale_locks


@contextmanager
def managed_lock(lock_type, resource, timeout=None):
    """
    Context manager for lock management.

    Args:
        lock_type: Type of lock
        resource: Resource being locked
        timeout: Maximum duration for the lock
    """
    lock_id = track_lock(lock_type, resource, timeout)

    try:
        yield lock_id
    finally:
        release_lock(lock_id)


def create_index_with_lock_management(
    table_name, field_name, index_sql, timeout=300, respect_cpu_throttle=True
):
    """
    Create an index with lock management, CPU throttling, and timeout.

    Args:
        table_name: Table name
        field_name: Field name
        index_sql: SQL for creating the index
        timeout: Maximum time to wait for lock (seconds)
        respect_cpu_throttle: If True, check CPU before creating index

    Returns:
        True if index was created successfully, False if throttled
    """
    index_name = f"idx_{table_name}_{field_name}_tenant"

    # Check CPU throttling
    if respect_cpu_throttle:
        should_throttle, reason, wait_seconds = should_throttle_index_creation()
        if should_throttle:
            logger.info(f"Index creation throttled: {reason}")

            # Try to wait for cooldown (but don't wait too long)
            if wait_seconds > 0 and wait_seconds < 300:
                logger.info(f"Waiting {wait_seconds:.1f}s for CPU cooldown...")
                if not wait_for_cpu_cooldown(max_wait_seconds=int(wait_seconds)):
                    logger.warning("CPU cooldown timeout, skipping index creation")
                    monitoring = get_monitoring()
                    monitoring.alert("warning", f"Index creation skipped due to high CPU: {reason}")
                    return False

    # Use safe database operation context manager for transaction safety
    with (
        managed_lock("index_creation", table_name, timeout=timeout),
        safe_database_operation("index_creation", table_name, rollback_on_failure=False) as conn,
    ):
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Try to get an advisory lock (non-blocking)
            cursor.execute("SELECT pg_try_advisory_lock(hashtext(%s)) as lock_acquired", (table_name,))
            result = cursor.fetchone()
            # RealDictCursor returns a dict, access by column name
            lock_acquired = result.get("lock_acquired", False) if result else False

            if not lock_acquired:
                raise IndexCreationError(
                    f"Could not acquire lock on table {table_name} - "
                    "another operation may be in progress"
                )

            # Use CONCURRENT index creation to minimize lock time
            # (PostgreSQL 9.2+)
            # Note: CONCURRENTLY cannot be used in a transaction
            # So we commit the lock, create index, then continue
            conn.commit()

            # Release advisory lock before creating index
            cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", (table_name,))
            conn.commit()
            cursor.close()  # Close cursor before creating index outside transaction

            # Create index CONCURRENTLY (outside transaction - needs new connection)
            concurrent_sql = index_sql.replace(
                "CREATE INDEX IF NOT EXISTS", "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
            )

            logger.info(
                f"Creating index {index_name} on {table_name}.{field_name} "
                f"(with CONCURRENTLY to minimize locks and CPU throttling)..."
            )

            # Track concurrent build
            try:
                from src.concurrent_index_monitoring import track_concurrent_build

                track_concurrent_build(index_name, table_name, started_at=time.time())
            except Exception as e:
                logger.debug(f"Could not track concurrent build: {e}")

            # Monitor CPU during index creation
            # Use a new connection for CONCURRENTLY (must be outside transaction)
            def execute_index_creation():
                from contextlib import suppress

                from src.db import get_connection_pool
                start_time = time.time()
                concurrent_conn = None
                pool = None
                try:
                    pool = get_connection_pool()
                    if pool is None:
                        raise IndexCreationError("Database connection pool not available")

                    # Get connection directly from pool for autocommit mode
                    concurrent_conn = pool.getconn()
                    if concurrent_conn is None:
                        raise IndexCreationError("Failed to get connection from pool")

                    # Set autocommit BEFORE any operations (CONCURRENTLY requires this)
                    concurrent_conn.autocommit = True
                    concurrent_cursor = concurrent_conn.cursor()
                    try:
                        concurrent_cursor.execute(concurrent_sql)
                    finally:
                        concurrent_cursor.close()
                except Exception as e:
                    # Re-raise with better error message
                    error_msg = str(e) if e else "Unknown error"
                    error_type = type(e).__name__
                    raise IndexCreationError(
                        f"Failed to create index CONCURRENTLY ({error_type}): {error_msg}"
                    ) from e
                finally:
                    # Return connection to pool
                    if concurrent_conn and pool:
                        with suppress(Exception):
                            pool.putconn(concurrent_conn)
                duration = time.time() - start_time
                return duration

            duration = monitor_cpu_during_operation(
                f"index_creation_{index_name}", execute_index_creation
            )

            # Mark build as complete
            try:
                from src.concurrent_index_monitoring import complete_concurrent_build

                complete_concurrent_build(index_name, success=True)
            except Exception:
                pass

            # Re-acquire cursor for verification and logging (cursor was closed earlier)
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            logger.info(f"Index {index_name} created in {duration:.2f}s")

            # Release advisory lock (using new cursor)
            cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", (table_name,))
            conn.commit()

            monitoring = get_monitoring()
            monitoring.record_metric("index_creation_duration", duration)

            if duration > timeout:
                monitoring.alert(
                    "warning", f"Index creation took {duration:.2f}s (exceeded {timeout}s timeout)"
                )

            # Record index creation for throttling
            record_index_creation()

            # Verify index integrity after creation
            if not verify_index_integrity(table_name, index_name):
                logger.warning(f"Index {index_name} created but integrity check failed")
                monitoring.alert(
                    "warning", f"Index {index_name} integrity check failed after creation"
                )
                # Try to drop invalid index
                try:
                    cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')
                    conn.commit()
                    raise IndexCreationError(
                        f"Index {index_name} created but failed integrity check, dropped"
                    )
                except Exception as drop_error:
                    logger.error(f"Failed to drop invalid index {index_name}: {drop_error}")
                    conn.rollback()

            return True
        except Exception:
            conn.rollback()
            # Release advisory lock on error
            with suppress(Exception):
                cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", (table_name,))
            raise
        finally:
            cursor.close()


def get_active_locks():
    """Get list of currently active locks"""
    with _lock_tracker_lock:
        return [
            {
                "lock_id": lock_id,
                "type": info["type"],
                "resource": info["resource"],
                "duration": time.time() - info["started_at"],
                "timeout": info["timeout"],
            }
            for lock_id, info in _active_locks.items()
        ]
