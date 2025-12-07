"""Monitor CREATE INDEX CONCURRENTLY progress"""

import logging
import time
from typing import Any

from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection

logger = logging.getLogger(__name__)

# Load config
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()

# Track active concurrent index builds
_active_builds: dict[str, dict[str, Any]] = {}


def is_concurrent_monitoring_enabled() -> bool:
    """Check if concurrent index monitoring is enabled"""
    return _config_loader.get_bool("features.concurrent_index_monitoring.enabled", True)


def get_concurrent_monitoring_config() -> dict[str, Any]:
    """Get concurrent monitoring configuration"""
    return {
        "enabled": is_concurrent_monitoring_enabled(),
        "check_interval_seconds": _config_loader.get_int(
            "features.concurrent_index_monitoring.check_interval_seconds", 30
        ),
        "alert_on_hanging_seconds": _config_loader.get_int(
            "features.concurrent_index_monitoring.alert_on_hanging_seconds", 3600
        ),
    }


def track_concurrent_build(index_name: str, table_name: str, started_at: float | None = None):
    """
    Track a concurrent index build.

    Args:
        index_name: Name of the index being built
        table_name: Table name
        started_at: Start time (default: current time)
    """
    if not is_concurrent_monitoring_enabled():
        return

    if started_at is None:
        started_at = time.time()

    _active_builds[index_name] = {
        "index_name": index_name,
        "table_name": table_name,
        "started_at": started_at,
        "last_check": started_at,
        "status": "building",
    }

    logger.info(f"Tracking concurrent index build: {index_name} on {table_name}")


def get_index_build_progress(index_name: str) -> dict[str, Any] | None:
    """
    Get progress of a concurrent index build.

    Args:
        index_name: Name of the index

    Returns:
        dict with build progress or None if not found
    """
    if not is_concurrent_monitoring_enabled():
        return None

    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Check if index exists (build complete)
                cursor.execute(
                    """
                    SELECT
                        indexname,
                        schemaname,
                        tablename,
                        indexdef
                    FROM pg_indexes
                    WHERE indexname = %s
                    """,
                    (index_name,),
                )
                index_exists = cursor.fetchone()

                if index_exists:
                    # Index exists - build is complete
                    return {
                        "index_name": index_name,
                        "status": "complete",
                        "exists": True,
                    }

                # Check if index is being built (PostgreSQL 12+)
                # Query pg_stat_progress_create_index
                try:
                    cursor.execute(
                        """
                        SELECT
                            pid,
                            datname,
                            relid::regclass as table_name,
                            index_relid::regclass as index_name,
                            command,
                            phase,
                            tuples_total,
                            tuples_done,
                            partitions_total,
                            partitions_done
                        FROM pg_stat_progress_create_index
                        WHERE index_relid::regclass::text = %s
                        """,
                        (index_name,),
                    )
                    progress = cursor.fetchone()

                    if progress:
                        tuples_total = progress.get("tuples_total", 0) or 0
                        tuples_done = progress.get("tuples_done", 0) or 0
                        progress_pct = (
                            (tuples_done / tuples_total * 100.0) if tuples_total > 0 else 0.0
                        )

                        return {
                            "index_name": index_name,
                            "status": "building",
                            "phase": progress.get("phase", "unknown"),
                            "tuples_total": tuples_total,
                            "tuples_done": tuples_done,
                            "progress_percent": round(progress_pct, 2),
                            "command": progress.get("command", "unknown"),
                        }
                except Exception:
                    # pg_stat_progress_create_index not available (PostgreSQL < 12)
                    pass

                # Fallback: Check if process is running
                # Look for CREATE INDEX CONCURRENTLY in pg_stat_activity
                cursor.execute(
                    """
                    SELECT
                        pid,
                        state,
                        query,
                        query_start,
                        state_change
                    FROM pg_stat_activity
                    WHERE query LIKE %s
                      AND state != 'idle'
                    ORDER BY query_start DESC
                    LIMIT 1
                    """,
                    (f"%CREATE INDEX CONCURRENTLY%{index_name}%",),
                )
                activity = cursor.fetchone()

                if activity:
                    return {
                        "index_name": index_name,
                        "status": "building",
                        "phase": "unknown",
                        "progress_percent": None,  # Can't determine without pg_stat_progress_create_index
                        "pid": activity.get("pid"),
                        "state": activity.get("state"),
                        "query_start": activity.get("query_start").isoformat()
                        if activity.get("query_start")
                        else None,
                    }

                # Index not found and no active query - might have failed
                return {
                    "index_name": index_name,
                    "status": "unknown",
                    "exists": False,
                }

            finally:
                cursor.close()

    except Exception as e:
        logger.error(f"Failed to get index build progress for {index_name}: {e}")
        return None


def check_hanging_builds() -> list[dict[str, Any]]:
    """
    Check for hanging concurrent index builds.

    Returns:
        List of hanging builds
    """
    if not is_concurrent_monitoring_enabled():
        return []

    config = get_concurrent_monitoring_config()
    alert_threshold = config.get("alert_on_hanging_seconds", 3600)
    hanging_builds = []

    current_time = time.time()

    for index_name, build_info in list(_active_builds.items()):
        duration = current_time - build_info["started_at"]

        if duration > alert_threshold:
            # Check current status
            progress = get_index_build_progress(index_name)

            if progress and progress.get("status") == "building":
                hanging_builds.append(
                    {
                        "index_name": index_name,
                        "table_name": build_info["table_name"],
                        "duration_seconds": duration,
                        "duration_hours": round(duration / 3600, 2),
                        "started_at": build_info["started_at"],
                        "progress": progress,
                    }
                )

    return hanging_builds


def complete_concurrent_build(index_name: str, success: bool = True):
    """
    Mark a concurrent index build as complete.

    Args:
        index_name: Name of the index
        success: Whether build was successful
    """
    if index_name in _active_builds:
        build_info = _active_builds.pop(index_name)
        duration = time.time() - build_info["started_at"]

        if success:
            logger.info(f"Concurrent index build completed: {index_name} in {duration:.2f}s")
        else:
            logger.warning(f"Concurrent index build failed: {index_name} after {duration:.2f}s")


def get_active_builds() -> list[dict[str, Any]]:
    """
    Get list of all active concurrent index builds.

    Returns:
        List of active builds with progress
    """
    if not is_concurrent_monitoring_enabled():
        return []

    active_builds = []

    for index_name, build_info in _active_builds.items():
        progress = get_index_build_progress(index_name)

        if progress and progress.get("status") == "building":
            duration = time.time() - build_info["started_at"]
            active_builds.append(
                {
                    "index_name": index_name,
                    "table_name": build_info["table_name"],
                    "duration_seconds": duration,
                    "started_at": build_info["started_at"],
                    "progress": progress,
                }
            )
        elif progress and progress.get("status") == "complete":
            # Build completed, remove from tracking
            complete_concurrent_build(index_name, success=True)

    return active_builds


def get_concurrent_monitoring_status() -> dict[str, Any]:
    """
    Get status of concurrent index monitoring.

    Returns:
        dict with monitoring status
    """
    config = get_concurrent_monitoring_config()
    active_builds = get_active_builds()
    hanging_builds = check_hanging_builds()

    return {
        "enabled": config["enabled"],
        "active_builds_count": len(active_builds),
        "hanging_builds_count": len(hanging_builds),
        "active_builds": active_builds,
        "hanging_builds": hanging_builds,
        "check_interval_seconds": config["check_interval_seconds"],
        "alert_threshold_seconds": config["alert_on_hanging_seconds"],
    }
