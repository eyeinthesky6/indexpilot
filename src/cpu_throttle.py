"""CPU-aware throttling for index creation"""

import logging
import time
from threading import Lock

import psutil

from src.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Load configuration with error handling
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()

# CPU monitoring
_cpu_lock = Lock()
_last_cpu_check = 0
_cpu_usage_history = []

# Throttling configuration (loaded from config file)
CPU_THRESHOLD = _config_loader.get_float("features.cpu_throttle.cpu_threshold", 80.0)
CPU_COOLDOWN = _config_loader.get_float("features.cpu_throttle.cpu_cooldown", 30.0)
MAX_CPU_DURING_CREATION = _config_loader.get_float(
    "features.cpu_throttle.max_cpu_during_creation", 95.0
)
MIN_DELAY_BETWEEN_INDEXES = _config_loader.get_float(
    "features.cpu_throttle.min_delay_between_indexes", 60.0
)
CPU_MONITORING_WINDOW = _config_loader.get_int("features.cpu_throttle.cpu_monitoring_window", 60)
CPU_CHECK_INTERVAL = _config_loader.get_float("features.cpu_throttle.cpu_check_interval", 5.0)
MAX_COOLDOWN_WAIT = _config_loader.get_int("features.cpu_throttle.max_cooldown_wait", 300)
_last_index_creation_time: float = 0.0


def get_cpu_usage():
    """Get current CPU usage percentage"""
    try:
        return psutil.cpu_percent(interval=0.1)
    except Exception as e:
        logger.warning(f"Failed to get CPU usage: {e}")
        return 0.0


def get_average_cpu_usage(window_seconds=None):
    """Get average CPU usage over a time window"""
    if window_seconds is None:
        window_seconds = CPU_MONITORING_WINDOW
    global _cpu_usage_history

    current_time = time.time()
    current_cpu = get_cpu_usage()

    with _cpu_lock:
        # Add current reading
        _cpu_usage_history.append((current_time, current_cpu))

        # Remove old readings (older than window)
        cutoff_time = current_time - window_seconds
        _cpu_usage_history = [(t, cpu) for t, cpu in _cpu_usage_history if t >= cutoff_time]

        if not _cpu_usage_history:
            return current_cpu

        # Calculate average
        avg_cpu = sum(cpu for _, cpu in _cpu_usage_history) / len(_cpu_usage_history)
        return avg_cpu


def should_throttle_index_creation():
    """
    Check if index creation should be throttled due to high CPU.

    Returns:
        (should_throttle, reason, wait_seconds)
    """
    global _last_index_creation_time

    current_time = time.time()

    # Check if enough time has passed since last index creation
    time_since_last = current_time - _last_index_creation_time
    if time_since_last < MIN_DELAY_BETWEEN_INDEXES:
        wait_seconds = MIN_DELAY_BETWEEN_INDEXES - time_since_last
        return (
            True,
            f"Too soon after last index creation ({time_since_last:.1f}s < {MIN_DELAY_BETWEEN_INDEXES}s)",
            wait_seconds,
        )

    # Check current CPU usage
    current_cpu = get_cpu_usage()
    if current_cpu > CPU_THRESHOLD:
        # Track CPU throttle trigger
        try:
            from src.safeguard_monitoring import track_cpu_throttle
            track_cpu_throttle(operations_throttled=1)
        except Exception:
            pass  # Don't fail if monitoring unavailable
        return True, f"CPU usage too high ({current_cpu:.1f}% > {CPU_THRESHOLD}%)", CPU_COOLDOWN

    # Check average CPU usage over monitoring window
    avg_cpu = get_average_cpu_usage()
    if avg_cpu > CPU_THRESHOLD:
        # Track CPU throttle trigger
        try:
            from src.safeguard_monitoring import track_cpu_throttle
            track_cpu_throttle(operations_throttled=1)
        except Exception:
            pass  # Don't fail if monitoring unavailable
        return True, f"Average CPU usage too high ({avg_cpu:.1f}% > {CPU_THRESHOLD}%)", CPU_COOLDOWN

    return False, None, 0


def wait_for_cpu_cooldown(max_wait_seconds=None):
    """
    Wait for CPU to drop below threshold.

    Args:
        max_wait_seconds: Maximum time to wait (None = use config default)

    Returns:
        True if CPU is now acceptable, False if timeout
    """
    if max_wait_seconds is None:
        max_wait_seconds = MAX_COOLDOWN_WAIT
    start_time = time.time()
    check_interval = CPU_CHECK_INTERVAL

    while time.time() - start_time < max_wait_seconds:
        current_cpu = get_cpu_usage()
        avg_cpu = get_average_cpu_usage(window_seconds=30)

        if current_cpu < CPU_THRESHOLD and avg_cpu < CPU_THRESHOLD:
            logger.info(f"CPU cooldown complete (current: {current_cpu:.1f}%, avg: {avg_cpu:.1f}%)")
            return True

        logger.debug(
            f"Waiting for CPU cooldown (current: {current_cpu:.1f}%, avg: {avg_cpu:.1f}%)..."
        )
        time.sleep(check_interval)

    logger.warning(f"CPU cooldown timeout after {max_wait_seconds}s")
    return False


def monitor_cpu_during_operation(operation_name, operation_func, *args, **kwargs):
    """
    Monitor CPU during an operation and abort if CPU spikes too high.

    Args:
        operation_name: Name of operation for logging
        operation_func: Function to execute
        *args, **kwargs: Arguments for operation

    Returns:
        Result of operation or None if aborted
    """
    import threading

    from src.monitoring import get_monitoring

    cpu_exceeded = False
    max_cpu_seen = 0.0

    def monitor_cpu():
        nonlocal cpu_exceeded, max_cpu_seen
        while not cpu_exceeded:
            cpu = get_cpu_usage()
            max_cpu_seen = max(max_cpu_seen, cpu)

            if cpu > MAX_CPU_DURING_CREATION:
                logger.warning(f"CPU exceeded threshold during {operation_name}: {cpu:.1f}%")
                cpu_exceeded = True
                return

            time.sleep(CPU_CHECK_INTERVAL)  # Check at configured interval

    # Start CPU monitoring thread
    monitor_thread = threading.Thread(target=monitor_cpu, daemon=True)
    monitor_thread.start()

    try:
        # Execute operation
        result = operation_func(*args, **kwargs)

        # Stop monitoring
        cpu_exceeded = True
        monitor_thread.join(timeout=2.0)

        # Log CPU metrics
        monitoring = get_monitoring()
        monitoring.record_metric(f"{operation_name}_max_cpu", max_cpu_seen)

        if max_cpu_seen > CPU_THRESHOLD:
            monitoring.alert(
                "warning", f"{operation_name} caused high CPU usage: {max_cpu_seen:.1f}%"
            )

        return result
    except Exception:
        cpu_exceeded = True
        monitor_thread.join(timeout=2.0)
        raise
    finally:
        if max_cpu_seen > CPU_THRESHOLD:
            logger.warning(f"{operation_name} completed with max CPU: {max_cpu_seen:.1f}%")


def record_index_creation():
    """Record that an index was created (for throttling)"""
    global _last_index_creation_time
    _last_index_creation_time = time.time()


def get_throttle_status():
    """Get current throttling status"""
    should_throttle, reason, wait_seconds = should_throttle_index_creation()
    current_cpu = get_cpu_usage()
    avg_cpu = get_average_cpu_usage()

    return {
        "throttled": should_throttle,
        "reason": reason,
        "wait_seconds": wait_seconds,
        "current_cpu": current_cpu,
        "avg_cpu_60s": avg_cpu,
        "threshold": CPU_THRESHOLD,
        "time_since_last_index": time.time() - _last_index_creation_time,
    }
