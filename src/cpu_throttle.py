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

# Hardware detection
try:
    cpu_cores_raw = psutil.cpu_count(logical=True)  # Logical cores (includes hyperthreading)
    cpu_physical_cores_raw = psutil.cpu_count(logical=False)  # Physical cores only
    CPU_CORES = cpu_cores_raw if cpu_cores_raw is not None else 4
    CPU_PHYSICAL_CORES = cpu_physical_cores_raw if cpu_physical_cores_raw is not None else 4
    logger.info(f"Detected CPU: {CPU_PHYSICAL_CORES} physical cores, {CPU_CORES} logical cores")
except Exception as e:
    logger.warning(f"Failed to detect CPU cores: {e}, assuming 4 cores")
    CPU_CORES = 4
    CPU_PHYSICAL_CORES = 4

# Hardware-aware configuration
HARDWARE_AWARE_ENABLED = _config_loader.get_bool(
    "features.cpu_throttle.hardware_aware_enabled", True
)
USE_PER_CORE_THRESHOLD = _config_loader.get_bool(
    "features.cpu_throttle.use_per_core_threshold", False
)

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

# Hardware-aware threshold adjustments
# On systems with more cores, we can be more lenient (more headroom)
# On systems with fewer cores, we should be more conservative
if HARDWARE_AWARE_ENABLED:
    if CPU_CORES <= 2:
        # Single/dual core: very conservative (high CPU is critical)
        CPU_THRESHOLD_MULTIPLIER = 0.85  # 15% more conservative
        MAX_CPU_MULTIPLIER = 0.90  # 10% more conservative
        logger.info(
            f"Hardware-aware: {CPU_CORES} cores detected, using conservative thresholds "
            f"(threshold: {CPU_THRESHOLD * CPU_THRESHOLD_MULTIPLIER:.1f}%, "
            f"max: {MAX_CPU_DURING_CREATION * MAX_CPU_MULTIPLIER:.1f}%)"
        )
    elif CPU_CORES <= 4:
        # Quad core: slightly conservative
        CPU_THRESHOLD_MULTIPLIER = 0.95  # 5% more conservative
        MAX_CPU_MULTIPLIER = 0.95
        logger.info(
            f"Hardware-aware: {CPU_CORES} cores detected, using slightly conservative thresholds"
        )
    elif CPU_CORES <= 8:
        # 4-8 cores: standard thresholds
        CPU_THRESHOLD_MULTIPLIER = 1.0
        MAX_CPU_MULTIPLIER = 1.0
        logger.info(f"Hardware-aware: {CPU_CORES} cores detected, using standard thresholds")
    elif CPU_CORES <= 16:
        # 8-16 cores: slightly more lenient (more headroom available)
        CPU_THRESHOLD_MULTIPLIER = 1.05  # 5% more lenient
        MAX_CPU_MULTIPLIER = 1.05
        logger.info(
            f"Hardware-aware: {CPU_CORES} cores detected, using slightly lenient thresholds"
        )
    else:
        # 16+ cores: more lenient (plenty of headroom)
        CPU_THRESHOLD_MULTIPLIER = 1.10  # 10% more lenient
        MAX_CPU_MULTIPLIER = 1.10
        logger.info(
            f"Hardware-aware: {CPU_CORES} cores detected, using lenient thresholds "
            f"(threshold: {CPU_THRESHOLD * CPU_THRESHOLD_MULTIPLIER:.1f}%, "
            f"max: {MAX_CPU_DURING_CREATION * MAX_CPU_MULTIPLIER:.1f}%)"
        )

    # Apply multipliers
    CPU_THRESHOLD = CPU_THRESHOLD * CPU_THRESHOLD_MULTIPLIER
    MAX_CPU_DURING_CREATION = MAX_CPU_DURING_CREATION * MAX_CPU_MULTIPLIER
else:
    CPU_THRESHOLD_MULTIPLIER = 1.0
    MAX_CPU_MULTIPLIER = 1.0
    logger.info("Hardware-aware CPU throttling disabled, using configured thresholds")


def get_cpu_usage(per_core: bool = False) -> float | list[float]:
    """
    Get current CPU usage percentage.

    Args:
        per_core: If True, return per-core usage list. If False, return system-wide average.

    Returns:
        float: System-wide CPU usage (0-100%), or
        list[float]: Per-core CPU usage if per_core=True
    """
    try:
        if per_core and USE_PER_CORE_THRESHOLD:
            # Get per-core usage
            per_core_usage = psutil.cpu_percent(interval=0.1, percpu=True)
            return per_core_usage
        else:
            # Get system-wide average
            return psutil.cpu_percent(interval=0.1)
    except Exception as e:
        logger.warning(f"Failed to get CPU usage: {e}")
        return 0.0 if not per_core else [0.0] * CPU_CORES


def get_average_cpu_usage(window_seconds=None):
    """Get average CPU usage over a time window"""
    if window_seconds is None:
        window_seconds = CPU_MONITORING_WINDOW
    global _cpu_usage_history

    current_time = time.time()
    cpu_usage = get_cpu_usage()
    current_cpu = cpu_usage if isinstance(cpu_usage, float) else 0.0

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

    # Check current CPU usage (hardware-aware)
    if USE_PER_CORE_THRESHOLD:
        # Check per-core usage - throttle if any core exceeds threshold
        per_core_usage = get_cpu_usage(per_core=True)
        if isinstance(per_core_usage, list):
            max_core_usage = max(per_core_usage) if per_core_usage else 0.0
            if max_core_usage > CPU_THRESHOLD:
                # Track CPU throttle trigger
                try:
                    from src.safeguard_monitoring import track_cpu_throttle

                    track_cpu_throttle(operations_throttled=1)
                except Exception:
                    pass  # Don't fail if monitoring unavailable
                return (
                    True,
                    f"CPU core usage too high (max core: {max_core_usage:.1f}% > {CPU_THRESHOLD}%)",
                    CPU_COOLDOWN,
                )
            current_cpu = sum(per_core_usage) / len(per_core_usage) if per_core_usage else 0.0
        else:
            # Fallback if per_core_usage is not a list
            current_cpu = per_core_usage if isinstance(per_core_usage, float) else 0.0
    else:
        cpu_usage = get_cpu_usage()
        current_cpu = cpu_usage if isinstance(cpu_usage, float) else 0.0

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
        cpu_usage = get_cpu_usage()
        current_cpu = cpu_usage if isinstance(cpu_usage, float) else 0.0
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
    Also throttles operations when CPU exceeds threshold.

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
    consecutive_high_cpu = 0
    MAX_CONSECUTIVE_HIGH_CPU = 3  # Abort after 3 consecutive checks above threshold

    def monitor_cpu():
        nonlocal cpu_exceeded, max_cpu_seen, consecutive_high_cpu
        while not cpu_exceeded:
            cpu_usage = get_cpu_usage()
            cpu = cpu_usage if isinstance(cpu_usage, float) else 0.0
            max_cpu_seen = max(max_cpu_seen, cpu)

            # Track consecutive high CPU readings
            if cpu > MAX_CPU_DURING_CREATION:
                consecutive_high_cpu += 1
                logger.warning(
                    f"CPU exceeded threshold during {operation_name}: {cpu:.1f}% "
                    f"(consecutive: {consecutive_high_cpu}/{MAX_CONSECUTIVE_HIGH_CPU})"
                )

                # Abort if CPU consistently exceeds threshold
                if consecutive_high_cpu >= MAX_CONSECUTIVE_HIGH_CPU:
                    logger.error(
                        f"Aborting {operation_name}: CPU consistently above threshold "
                        f"({cpu:.1f}% > {MAX_CPU_DURING_CREATION}%)"
                    )
                    cpu_exceeded = True
                    return
            else:
                consecutive_high_cpu = 0  # Reset counter when CPU drops

            # Also check if CPU exceeds 100% (should never happen, but handle it)
            if cpu > 100.0:
                logger.error(
                    f"CRITICAL: CPU usage exceeds 100% during {operation_name}: {cpu:.1f}%"
                )
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

        if max_cpu_seen > 100.0:
            monitoring.alert(
                "critical",
                f"{operation_name} caused CPU usage above 100%: {max_cpu_seen:.1f}% - "
                "This should never happen and indicates a monitoring issue",
            )

        return result
    except Exception:
        cpu_exceeded = True
        monitor_thread.join(timeout=2.0)
        raise
    finally:
        if max_cpu_seen > CPU_THRESHOLD:
            logger.warning(f"{operation_name} completed with max CPU: {max_cpu_seen:.1f}%")
        if max_cpu_seen > 100.0:
            logger.error(
                f"{operation_name} completed with invalid CPU reading: {max_cpu_seen:.1f}% "
                "(CPU cannot exceed 100% - check monitoring system)"
            )


def record_index_creation():
    """Record that an index was created (for throttling)"""
    global _last_index_creation_time
    _last_index_creation_time = time.time()


def get_throttle_status():
    """Get current throttling status"""
    should_throttle, reason, wait_seconds = should_throttle_index_creation()
    cpu_usage = get_cpu_usage()
    current_cpu = cpu_usage if isinstance(cpu_usage, float) else 0.0
    avg_cpu = get_average_cpu_usage()

    # Get hardware info
    from src.type_definitions import JSONDict

    hardware_info: JSONDict = {
        "cpu_cores": CPU_CORES,
        "physical_cores": CPU_PHYSICAL_CORES,
        "hardware_aware_enabled": HARDWARE_AWARE_ENABLED,
        "use_per_core_threshold": USE_PER_CORE_THRESHOLD,
    }

    if USE_PER_CORE_THRESHOLD:
        per_core_usage = get_cpu_usage(per_core=True)
        if isinstance(per_core_usage, list):
            from typing import cast

            from src.type_definitions import JSONValue

            hardware_info["per_core_usage"] = cast(list[JSONValue], per_core_usage)
            hardware_info["max_core_usage"] = max(per_core_usage) if per_core_usage else 0.0
        else:
            hardware_info["per_core_usage"] = []
            hardware_info["max_core_usage"] = 0.0

    return {
        "throttled": should_throttle,
        "reason": reason,
        "wait_seconds": wait_seconds,
        "current_cpu": current_cpu,
        "avg_cpu_60s": avg_cpu,
        "threshold": CPU_THRESHOLD,
        "max_cpu_during_creation": MAX_CPU_DURING_CREATION,
        "time_since_last_index": time.time() - _last_index_creation_time,
        "hardware": hardware_info,
    }
