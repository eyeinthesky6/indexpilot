"""Periodic maintenance tasks for database integrity"""

import logging
import time
from datetime import datetime
from src.type_definitions import JSONDict, JSONValue

from src.monitoring import get_monitoring
from src.resilience import (
    check_database_integrity,
    cleanup_invalid_indexes,
    cleanup_orphaned_indexes,
    cleanup_stale_advisory_locks,
    get_active_operations,
)

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
    return _config_loader.get_bool('operational.maintenance_tasks.enabled', True)

# Last maintenance run time
_last_maintenance_run: float = 0.0
_maintenance_interval = 3600  # 1 hour

# Get maintenance interval from config if available
try:
    from src.production_config import get_config
    _prod_config = get_config()
    _maintenance_interval = _prod_config.get_int('MAINTENANCE_INTERVAL', 3600)
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
        return {'skipped': True, 'reason': 'maintenance_tasks_disabled'}

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
        return {'skipped': True, 'reason': 'interval_not_passed'}

    logger.info("Running maintenance tasks...")
    _last_maintenance_run = current_time

    cleanup_dict: JSONDict = {}
    results: JSONDict = {
        'timestamp': datetime.now().isoformat(),
        'integrity_check': {},
        'cleanup': cleanup_dict,
        'status': 'success'
    }

    monitoring = get_monitoring()

    try:
        # 1. Check database integrity
        integrity_results = check_database_integrity()
        results['integrity_check'] = integrity_results

        if integrity_results.get('status') != 'healthy':
            issues_val = integrity_results.get('issues', [])
            issues_list = issues_val if isinstance(issues_val, list) else []
            logger.warning(f"Database integrity check found issues: {issues_list}")
            monitoring.alert('warning', f"Database integrity issues detected: {len(issues_list)} issues")

        # 2. Clean up orphaned indexes
        orphaned = cleanup_orphaned_indexes()
        if orphaned:
            logger.info(f"Cleaned up {len(orphaned)} orphaned indexes")
            monitoring.alert('info', f'Cleaned up {len(orphaned)} orphaned indexes')
        cleanup_dict['orphaned_indexes'] = len(orphaned)

        # 3. Clean up invalid indexes
        invalid = cleanup_invalid_indexes()
        if invalid:
            logger.info(f"Cleaned up {len(invalid)} invalid indexes")
            monitoring.alert('warning', f'Cleaned up {len(invalid)} invalid indexes')
        cleanup_dict['invalid_indexes'] = len(invalid)

        # 4. Clean up stale advisory locks
        stale_locks = cleanup_stale_advisory_locks()
        if stale_locks > 0:
            logger.info(f"Cleaned up {stale_locks} stale advisory locks")
            monitoring.alert('info', f'Cleaned up {stale_locks} stale advisory locks')
        cleanup_dict['stale_advisory_locks'] = stale_locks

        # 5. Check for stale operations
        active_ops = get_active_operations()
        stale_ops = []
        for op in active_ops:
            if isinstance(op, dict):
                duration_val = op.get('duration')
                if isinstance(duration_val, (int, float)) and float(duration_val) > 600:
                    stale_ops.append(op)
        if stale_ops:
            logger.warning(f"Found {len(stale_ops)} stale operations: {stale_ops}")
            monitoring.alert('warning', f'Found {len(stale_ops)} stale operations')
        cleanup_dict['stale_operations'] = len(stale_ops)

        # 6. Log bypass status periodically (for user visibility)
        try:
            from src.bypass_status import log_bypass_status
            log_bypass_status(include_details=False)  # Less verbose for periodic logs
        except Exception as e:
            logger.debug(f"Could not log bypass status: {e}")

        logger.info("Maintenance tasks completed successfully")

    except Exception as e:
        logger.error(f"Maintenance tasks failed: {e}")
        results['status'] = 'error'
        results['error'] = str(e)
        monitoring.alert('error', f'Maintenance tasks failed: {e}')

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
        'last_run': datetime.fromtimestamp(_last_maintenance_run).isoformat() if _last_maintenance_run > 0 else None,
        'time_since_last': time_since_last,
        'interval_seconds': _maintenance_interval,
        'next_run_in': max(0, _maintenance_interval - time_since_last) if time_since_last else 0
    }
    return status

