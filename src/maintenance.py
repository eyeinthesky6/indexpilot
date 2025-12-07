"""Periodic maintenance tasks for database integrity"""

import logging
import time
from datetime import datetime

from src.monitoring import get_monitoring
from src.resilience import (
    check_database_integrity,
    cleanup_invalid_indexes,
    cleanup_orphaned_indexes,
    cleanup_stale_advisory_locks,
    get_active_operations,
)
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)

# Load config for maintenance tasks toggle
try:
    from src.config_loader import ConfigLoader

    _config_loader: ConfigLoader | None = ConfigLoader()
except Exception:
    _config_loader = None


def is_maintenance_tasks_enabled() -> bool:
    """Check if maintenance tasks are enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("operational.maintenance_tasks.enabled", True)


# Last maintenance run time
_last_maintenance_run: float = 0.0
_maintenance_interval = 3600  # 1 hour

# Get maintenance interval from config if available
try:
    from src.production_config import get_config

    _prod_config = get_config()
    _maintenance_interval = _prod_config.get_int("MAINTENANCE_INTERVAL", 3600)
except (ImportError, ValueError):
    pass  # Use default if config not available


def run_maintenance_tasks(force: bool = False) -> JSONDict:
    """
    Run periodic maintenance tasks to ensure database integrity.

    Tasks:
    - Check database integrity
    - Clean up orphaned indexes
    - Clean up invalid indexes
    - Clean up stale advisory locks
    - Check for stale operations
    - Log bypass status (for user visibility)

    Args:
        force: If True, run even if interval hasn't passed

    Returns:
        dict with maintenance results
    """
    if not is_maintenance_tasks_enabled():
        return {"skipped": True, "reason": "maintenance_tasks_disabled"}

    global _last_maintenance_run

    # Log bypass status periodically for user visibility
    try:
        from src.bypass_status import log_bypass_status

        log_bypass_status(include_details=False)  # Less verbose for periodic logs
    except Exception as e:
        logger.debug(f"Could not log bypass status: {e}")

    current_time = time.time()
    time_since_last = current_time - _last_maintenance_run

    if not force and time_since_last < _maintenance_interval:
        logger.debug(f"Skipping maintenance (last run {time_since_last:.0f}s ago)")
        return {"skipped": True, "reason": "interval_not_passed"}

    logger.info("Running maintenance tasks...")
    _last_maintenance_run = current_time

    cleanup_dict: JSONDict = {}
    results: JSONDict = {
        "timestamp": datetime.now().isoformat(),
        "integrity_check": {},
        "cleanup": cleanup_dict,
        "status": "success",
    }

    monitoring = get_monitoring()

    try:
        # 1. Check database integrity
        integrity_results = check_database_integrity()
        results["integrity_check"] = integrity_results

        if integrity_results.get("status") != "healthy":
            issues_val = integrity_results.get("issues", [])
            issues_list = issues_val if isinstance(issues_val, list) else []
            logger.warning(f"Database integrity check found issues: {issues_list}")
            monitoring.alert(
                "warning", f"Database integrity issues detected: {len(issues_list)} issues"
            )

        # 2. Clean up orphaned indexes
        orphaned = cleanup_orphaned_indexes()
        if orphaned:
            logger.info(f"Cleaned up {len(orphaned)} orphaned indexes")
            monitoring.alert("info", f"Cleaned up {len(orphaned)} orphaned indexes")
        cleanup_dict["orphaned_indexes"] = len(orphaned)

        # 3. Clean up invalid indexes
        invalid = cleanup_invalid_indexes()
        if invalid:
            logger.info(f"Cleaned up {len(invalid)} invalid indexes")
            monitoring.alert("warning", f"Cleaned up {len(invalid)} invalid indexes")
        cleanup_dict["invalid_indexes"] = len(invalid)

        # 4. Clean up stale advisory locks
        stale_locks = cleanup_stale_advisory_locks()
        if stale_locks > 0:
            logger.info(f"Cleaned up {stale_locks} stale advisory locks")
            monitoring.alert("info", f"Cleaned up {stale_locks} stale advisory locks")
        cleanup_dict["stale_advisory_locks"] = stale_locks

        # 5. Check for stale operations
        active_ops = get_active_operations()
        stale_ops = []
        for op in active_ops:
            if isinstance(op, dict):
                duration_val = op.get("duration")
                if isinstance(duration_val, (int, float)) and float(duration_val) > 600:
                    stale_ops.append(op)
        if stale_ops:
            logger.warning(f"Found {len(stale_ops)} stale operations: {stale_ops}")
            monitoring.alert("warning", f"Found {len(stale_ops)} stale operations")
        cleanup_dict["stale_operations"] = len(stale_ops)

        # 6. Clean up unused indexes (if enabled)
        try:
            from src.index_cleanup import find_unused_indexes
            
            # Check if index cleanup is enabled
            cleanup_enabled = _config_loader.get_bool("features.index_cleanup.enabled", True) if _config_loader else True
            if cleanup_enabled:
                min_scans = _config_loader.get_int("features.index_cleanup.min_scans", 10) if _config_loader else 10
                days_unused = _config_loader.get_int("features.index_cleanup.days_unused", 7) if _config_loader else 7
                
                unused_indexes = find_unused_indexes(min_scans=min_scans, days_unused=days_unused)
                if unused_indexes:
                    logger.info(f"Found {len(unused_indexes)} unused indexes")
                    cleanup_dict["unused_indexes_found"] = len(unused_indexes)
                    # Note: Actual cleanup requires explicit call to cleanup_unused_indexes(dry_run=False)
                    # This is intentional - cleanup is destructive and should be manual or scheduled separately
        except Exception as e:
            logger.debug(f"Could not check for unused indexes: {e}")

        # 7. Monitor index health (if enabled)
        try:
            from src.index_health import monitor_index_health, find_bloated_indexes
            
            # Check if index health monitoring is enabled
            health_enabled = _config_loader.get_bool("features.index_health.enabled", True) if _config_loader else True
            if health_enabled:
                bloat_threshold = _config_loader.get_float("features.index_health.bloat_threshold", 20.0) if _config_loader else 20.0
                min_size_mb = _config_loader.get_float("features.index_health.min_size_mb", 1.0) if _config_loader else 1.0
                
                health_data = monitor_index_health(
                    bloat_threshold_percent=bloat_threshold,
                    min_size_mb=min_size_mb
                )
                if health_data.get("indexes"):
                    summary = health_data.get("summary", {})
                    logger.info(
                        f"Index health: {summary.get('healthy', 0)} healthy, "
                        f"{summary.get('bloated', 0)} bloated, "
                        f"{summary.get('underutilized', 0)} underutilized"
                    )
                    cleanup_dict["index_health"] = summary
                    
                    # Check for bloated indexes
                    bloated = find_bloated_indexes(
                        bloat_threshold_percent=bloat_threshold,
                        min_size_mb=min_size_mb
                    )
                    if bloated:
                        logger.info(f"Found {len(bloated)} bloated indexes that may need REINDEX")
                        cleanup_dict["bloated_indexes_found"] = len(bloated)
                        # Note: Actual REINDEX requires explicit call to reindex_bloated_indexes(dry_run=False)
                        # This is intentional - REINDEX is resource-intensive and should be scheduled carefully
        except Exception as e:
            logger.debug(f"Could not monitor index health: {e}")

        # 8. Learn query patterns from history (if enabled)
        try:
            from src.query_pattern_learning import learn_from_slow_queries, learn_from_fast_queries
            
            # Check if pattern learning is enabled
            pattern_learning_enabled = _config_loader.get_bool("features.pattern_learning.enabled", True) if _config_loader else True
            if pattern_learning_enabled:
                # Learn patterns every hour (configurable)
                import time
                global _last_pattern_learning
                if not hasattr(run_maintenance_tasks, '_last_pattern_learning'):
                    run_maintenance_tasks._last_pattern_learning = 0.0
                
                current_time = time.time()
                pattern_interval = _config_loader.get_int("features.pattern_learning.interval", 3600) if _config_loader else 3600
                
                if current_time - run_maintenance_tasks._last_pattern_learning >= pattern_interval:
                    logger.info("Learning query patterns from history...")
                    slow_patterns = learn_from_slow_queries(time_window_hours=24, min_occurrences=3)
                    fast_patterns = learn_from_fast_queries(time_window_hours=24, min_occurrences=10)
                    
                    cleanup_dict["pattern_learning"] = {
                        "slow_patterns": slow_patterns.get("summary", {}).get("total_patterns", 0),
                        "fast_patterns": fast_patterns.get("summary", {}).get("total_patterns", 0),
                    }
                    
                    run_maintenance_tasks._last_pattern_learning = current_time
                    logger.info(
                        f"Learned {slow_patterns.get('summary', {}).get('total_patterns', 0)} slow patterns "
                        f"and {fast_patterns.get('summary', {}).get('total_patterns', 0)} fast patterns"
                    )
        except Exception as e:
            logger.debug(f"Could not learn query patterns: {e}")

        # 9. Report safeguard metrics (if enabled)
        try:
            from src.safeguard_monitoring import get_safeguard_metrics, get_safeguard_status
            
            safeguard_metrics = get_safeguard_metrics()
            safeguard_status = get_safeguard_status()
            
            cleanup_dict["safeguard_metrics"] = safeguard_metrics
            cleanup_dict["safeguard_status"] = safeguard_status.get("overall_status", "unknown")
            
            # Log summary
            if safeguard_metrics["index_creation"]["attempts"] > 0:
                success_rate = safeguard_metrics["index_creation"]["success_rate"]
                logger.info(
                    f"Safeguard metrics: Index creation success rate: {success_rate:.1%}, "
                    f"Rate limit triggers: {safeguard_metrics['rate_limiting']['triggers']}, "
                    f"CPU throttles: {safeguard_metrics['cpu_throttling']['triggers']}"
                )
        except Exception as e:
            logger.debug(f"Could not get safeguard metrics: {e}")

        logger.info("Maintenance tasks completed successfully")

    except Exception as e:
        logger.error(f"Maintenance tasks failed: {e}")
        results["status"] = "error"
        results["error"] = str(e)
        monitoring.alert("error", f"Maintenance tasks failed: {e}")

    return results


def schedule_maintenance(interval_seconds: int = 3600):
    """
    Schedule periodic maintenance tasks.

    Args:
        interval_seconds: Interval between maintenance runs (default: 1 hour)
    """
    global _maintenance_interval
    _maintenance_interval = interval_seconds
    logger.info(f"Maintenance scheduled to run every {interval_seconds}s")


def get_maintenance_status() -> dict[str, JSONValue]:
    """
    Get status of maintenance system.

    Returns:
        dict with maintenance status
    """
    global _last_maintenance_run, _maintenance_interval

    time_since_last = time.time() - _last_maintenance_run if _last_maintenance_run > 0 else None

    status: JSONDict = {
        "last_run": datetime.fromtimestamp(_last_maintenance_run).isoformat()
        if _last_maintenance_run > 0
        else None,
        "time_since_last": time_since_last,
        "interval_seconds": _maintenance_interval,
        "next_run_in": max(0, _maintenance_interval - time_since_last) if time_since_last else 0,
    }
    return status
