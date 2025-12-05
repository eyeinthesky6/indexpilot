"""Rollback mechanism for quick disable"""

import logging

from src.monitoring import get_monitoring

logger = logging.getLogger(__name__)

# Global flags for system enable/disable (runtime overrides)
_system_enabled = True
_stats_collection_enabled = True
_expression_checks_enabled = True
_mutation_logging_enabled = True
_enable_lock = None


def init_rollback():
    """Initialize rollback mechanism"""
    global _enable_lock
    import threading
    _enable_lock = threading.Lock()


def is_system_enabled():
    """Check if the system is enabled (considers config file and runtime overrides)"""
    # Check runtime override first (highest priority)
    if not _system_enabled:
        return False

    # Check config file (lazy import to avoid circular dependencies)
    try:
        from src.bypass_config import is_feature_enabled, is_system_bypassed
        if is_system_bypassed():
            return False
        # Check feature-level config
        if not is_feature_enabled('auto_indexing'):
            return False
    except ImportError:
        # Config system not available, use runtime flag only
        pass

    return True


def is_stats_collection_enabled():
    """Check if stats collection is enabled (Level 3 bypass overrides Level 1)"""
    # Check runtime override first (highest priority)
    if not _stats_collection_enabled:
        return False

    # Level 3 override: System bypass disables all features
    if not _system_enabled:
        return False

    # Check Level 3 config bypass (system-level)
    try:
        from src.bypass_config import is_system_bypassed
        if is_system_bypassed():
            return False  # Level 3 overrides Level 1
    except (ImportError, Exception):
        pass

    # Check Level 1 config (feature-level)
    try:
        from src.bypass_config import is_feature_enabled
        return is_feature_enabled('stats_collection')
    except (ImportError, Exception):
        # Config system not available or error, default to enabled
        return True


def is_expression_checks_enabled():
    """Check if expression checks are enabled (Level 3 bypass overrides Level 1)"""
    # Check runtime override first (highest priority)
    if not _expression_checks_enabled:
        return False

    # Level 3 override: System bypass disables all features
    if not _system_enabled:
        return False

    # Check Level 3 config bypass (system-level)
    try:
        from src.bypass_config import is_system_bypassed
        if is_system_bypassed():
            return False  # Level 3 overrides Level 1
    except (ImportError, Exception):
        pass

    # Check Level 1 config (feature-level)
    try:
        from src.bypass_config import is_feature_enabled
        return is_feature_enabled('expression_checks')
    except (ImportError, Exception):
        # Config system not available or error, default to enabled
        return True


def is_mutation_logging_enabled():
    """Check if mutation logging is enabled (Level 3 bypass overrides Level 1)"""
    # Check runtime override first (highest priority)
    if not _mutation_logging_enabled:
        return False

    # Level 3 override: System bypass disables all features
    if not _system_enabled:
        return False

    # Check Level 3 config bypass (system-level)
    try:
        from src.bypass_config import is_system_bypassed
        if is_system_bypassed():
            return False  # Level 3 overrides Level 1
    except (ImportError, Exception):
        pass

    # Check Level 1 config (feature-level)
    try:
        from src.bypass_config import is_feature_enabled
        return is_feature_enabled('mutation_logging')
    except (ImportError, Exception):
        # Config system not available or error, default to enabled
        return True


def disable_system(reason="Manual disable"):
    """
    Disable the auto-indexing system immediately.

    Args:
        reason: Reason for disabling
    """
    global _system_enabled

    if _enable_lock:
        _enable_lock.acquire()

    try:
        _system_enabled = False
        logger.warning(f"Auto-indexing system DISABLED: {reason}")

        monitoring = get_monitoring()
        monitoring.alert('warning', f'Auto-indexing system disabled: {reason}')

        # Log the disable action to audit trail
        try:
            from src.audit import log_audit_event
            log_audit_event(
                'SYSTEM_DISABLE',
                details={'reason': reason, 'action': 'disable'},
                severity='warning'
            )
        except Exception as e:
            logger.error(f"Failed to log system disable: {e}")
    finally:
        if _enable_lock:
            _enable_lock.release()

    return True


def disable_stats_collection(reason="Manual disable"):
    """Disable query statistics collection"""
    global _stats_collection_enabled

    if _enable_lock:
        _enable_lock.acquire()

    try:
        _stats_collection_enabled = False
        logger.warning(f"Stats collection DISABLED: {reason}")

        monitoring = get_monitoring()
        monitoring.alert('warning', f'Stats collection disabled: {reason}')

        try:
            from src.audit import log_audit_event
            log_audit_event(
                'STATS_COLLECTION_DISABLE',
                details={'reason': reason, 'action': 'disable'},
                severity='warning'
            )
        except Exception as e:
            logger.error(f"Failed to log stats disable: {e}")
    finally:
        if _enable_lock:
            _enable_lock.release()

    return True


def enable_stats_collection(reason="Manual enable"):
    """Re-enable query statistics collection"""
    global _stats_collection_enabled

    if _enable_lock:
        _enable_lock.acquire()

    try:
        _stats_collection_enabled = True
        logger.info(f"Stats collection ENABLED: {reason}")

        monitoring = get_monitoring()
        monitoring.alert('info', f'Stats collection enabled: {reason}')

        try:
            from src.audit import log_audit_event
            log_audit_event(
                'STATS_COLLECTION_ENABLE',
                details={'reason': reason, 'action': 'enable'},
                severity='info'
            )
        except Exception as e:
            logger.error(f"Failed to log stats enable: {e}")
    finally:
        if _enable_lock:
            _enable_lock.release()

    return True


def disable_expression_checks(reason="Manual disable"):
    """Disable expression profile checks"""
    global _expression_checks_enabled

    if _enable_lock:
        _enable_lock.acquire()

    try:
        _expression_checks_enabled = False
        logger.warning(f"Expression checks DISABLED: {reason}")

        monitoring = get_monitoring()
        monitoring.alert('warning', f'Expression checks disabled: {reason}')

        try:
            from src.audit import log_audit_event
            log_audit_event(
                'EXPRESSION_CHECKS_DISABLE',
                details={'reason': reason, 'action': 'disable'},
                severity='warning'
            )
        except Exception as e:
            logger.error(f"Failed to log expression disable: {e}")
    finally:
        if _enable_lock:
            _enable_lock.release()

    return True


def enable_expression_checks(reason="Manual enable"):
    """Re-enable expression profile checks"""
    global _expression_checks_enabled

    if _enable_lock:
        _enable_lock.acquire()

    try:
        _expression_checks_enabled = True
        logger.info(f"Expression checks ENABLED: {reason}")

        monitoring = get_monitoring()
        monitoring.alert('info', f'Expression checks enabled: {reason}')

        try:
            from src.audit import log_audit_event
            log_audit_event(
                'EXPRESSION_CHECKS_ENABLE',
                details={'reason': reason, 'action': 'enable'},
                severity='info'
            )
        except Exception as e:
            logger.error(f"Failed to log expression enable: {e}")
    finally:
        if _enable_lock:
            _enable_lock.release()

    return True


def enable_complete_bypass(reason="Complete system bypass"):
    """Enable complete system bypass (disables all features)"""
    disable_system(reason)
    disable_stats_collection(reason)
    disable_expression_checks(reason)
    logger.warning(f"Complete system bypass ENABLED: {reason}")
    return True


def enable_system(reason="Manual enable"):
    """
    Re-enable the auto-indexing system.

    Args:
        reason: Reason for enabling
    """
    global _system_enabled

    if _enable_lock:
        _enable_lock.acquire()

    try:
        _system_enabled = True
        logger.info(f"Auto-indexing system ENABLED: {reason}")

        monitoring = get_monitoring()
        monitoring.alert('info', f'Auto-indexing system enabled: {reason}')

        # Log the enable action to audit trail
        try:
            from src.audit import log_audit_event
            log_audit_event(
                'SYSTEM_ENABLE',
                details={'reason': reason, 'action': 'enable'},
                severity='info'
            )
        except Exception as e:
            logger.error(f"Failed to log system enable: {e}")
    finally:
        if _enable_lock:
            _enable_lock.release()

    return True


def get_system_status():
    """Get comprehensive system status including bypass information"""
    try:
        from src.bypass_config import (
            get_bypass_reason,
            is_feature_enabled,
            is_system_bypassed,
            should_skip_initialization,
        )

        system_bypassed = is_system_bypassed()
        skip_init = should_skip_initialization()

        # Get effective status (after all overrides)
        effective_status = {
            'auto_indexing': is_system_enabled(),
            'stats_collection': is_stats_collection_enabled(),
            'expression_checks': is_expression_checks_enabled(),
            'mutation_logging': is_mutation_logging_enabled(),
        }

        # Get config status (before overrides)
        config_status = {}
        for feature in ['auto_indexing', 'stats_collection', 'expression_checks', 'mutation_logging']:
            try:
                config_status[feature] = {
                    'enabled': is_feature_enabled(feature),
                    'reason': get_bypass_reason(feature)
                }
            except Exception:
                config_status[feature] = {'enabled': True, 'reason': ''}

        return {
            'effective_status': effective_status,
            'config_status': config_status,
            'bypass_levels': {
                'level_3_system': {
                    'bypassed': system_bypassed,
                    'reason': get_bypass_reason() if system_bypassed else ''
                },
                'level_4_startup': {
                    'skip_initialization': skip_init,
                    'reason': get_bypass_reason() if skip_init else ''
                }
            },
            'runtime_overrides': {
                'system': _system_enabled,
                'stats_collection': _stats_collection_enabled,
                'expression_checks': _expression_checks_enabled,
                'mutation_logging': _mutation_logging_enabled
            },
            'summary': {
                'any_bypass_active': (
                    not effective_status['auto_indexing'] or
                    not effective_status['stats_collection'] or
                    not effective_status['expression_checks'] or
                    not effective_status['mutation_logging'] or
                    system_bypassed or skip_init
                ),
                'system_fully_bypassed': system_bypassed or skip_init
            }
        }
    except (ImportError, Exception) as e:
        # Fallback if config system unavailable
        return {
            'effective_status': {
                'auto_indexing': is_system_enabled(),
                'stats_collection': is_stats_collection_enabled(),
                'expression_checks': is_expression_checks_enabled(),
                'mutation_logging': is_mutation_logging_enabled(),
            },
            'runtime_overrides': {
                'system': _system_enabled,
                'stats_collection': _stats_collection_enabled,
                'expression_checks': _expression_checks_enabled,
                'mutation_logging': _mutation_logging_enabled
            },
            'error': f'Config system unavailable: {e}'
        }


def require_enabled(func):
    """Decorator to require system to be enabled"""
    def wrapper(*args, **kwargs):
        if not is_system_enabled():
            logger.warning(f"Operation {func.__name__} skipped: system is disabled")
            return {'skipped': True, 'reason': 'system_disabled'}
        return func(*args, **kwargs)
    return wrapper

