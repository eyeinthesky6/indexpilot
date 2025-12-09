"""Graceful shutdown handling for production"""

import atexit
import logging
import signal
import sys
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Shutdown state
_shutdown_event = threading.Event()
_shutdown_handlers: list[tuple[int, Callable[[], None]]] = []
_shutdown_lock = threading.Lock()
_shutdown_in_progress = False
_simulation_active = False  # Track if simulation is running
_simulation_lock = threading.Lock()


def register_shutdown_handler(handler: Callable[[], None], priority: int = 0):
    """
    Register a handler to be called during graceful shutdown.

    Handlers are called in reverse priority order (higher priority first).

    Args:
        handler: Function to call during shutdown
        priority: Priority (higher = called first, default: 0)
    """
    with _shutdown_lock:
        _shutdown_handlers.append((priority, handler))
        _shutdown_handlers.sort(key=lambda x: x[0], reverse=True)
        logger.debug(f"Registered shutdown handler with priority {priority}")


def unregister_shutdown_handler(handler: Callable[[], None]):
    """Unregister a shutdown handler"""
    with _shutdown_lock:
        _shutdown_handlers[:] = [(p, h) for p, h in _shutdown_handlers if h != handler]
        logger.debug("Unregistered shutdown handler")


def is_shutting_down() -> bool:
    """
    Check if shutdown is in progress.

    For simulations, this is smarter - it won't trigger shutdown during active simulations
    unless explicitly requested (SIGTERM/SIGINT or programmatic shutdown() call).
    """
    # Check if shutdown is explicitly in progress (signal handler or programmatic shutdown)
    with _shutdown_lock:
        if _shutdown_in_progress:
            return True  # Explicit shutdown requested

    # Check if simulation is active (use correct lock)
    with _simulation_lock:
        if _simulation_active:
            # During simulations, only shutdown if explicitly requested
            # Don't shutdown just because event is set (might be from other sources)
            return False

    # Normal shutdown check (event set or in progress)
    return _shutdown_event.is_set() or _shutdown_in_progress


def set_simulation_active(active: bool):
    """Mark simulation as active/inactive to prevent premature shutdowns"""
    global _simulation_active
    with _simulation_lock:
        _simulation_active = active
        if active:
            logger.debug("Simulation marked as active - shutdown checks will be more lenient")
        else:
            logger.debug("Simulation marked as inactive")


def is_simulation_active() -> bool:
    """Check if simulation is currently active"""
    with _simulation_lock:
        return _simulation_active


def wait_for_shutdown(timeout: float | None = None) -> bool:
    """
    Wait for shutdown signal.

    Args:
        timeout: Maximum time to wait (None = wait indefinitely)

    Returns:
        True if shutdown was signaled, False if timeout
    """
    return _shutdown_event.wait(timeout=timeout)


def _execute_shutdown_handlers():
    """Execute all registered shutdown handlers"""
    global _shutdown_in_progress

    with _shutdown_lock:
        if _shutdown_in_progress:
            return
        _shutdown_in_progress = True

    logger.info("Starting graceful shutdown...")

    # Execute handlers in priority order
    errors = []
    for priority, handler in _shutdown_handlers:
        try:
            logger.debug(f"Executing shutdown handler (priority {priority})")
            handler()
        except Exception as e:
            logger.error(f"Error in shutdown handler: {e}", exc_info=True)
            errors.append(str(e))

    if errors:
        logger.warning(f"Shutdown completed with {len(errors)} errors")
    else:
        logger.info("Graceful shutdown completed successfully")


def _signal_handler(signum: int, _frame: object) -> None:
    """Handle shutdown signals"""
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
    _shutdown_event.set()
    _execute_shutdown_handlers()

    # Don't call sys.exit() during tests - let pytest handle it
    # Check if we're in a test environment
    is_test_env = (
        "pytest" in sys.modules
        or "unittest" in sys.modules
        or any("test" in arg.lower() for arg in sys.argv)
    )

    if not is_test_env:
        sys.exit(0)
    else:
        logger.debug("In test environment, not calling sys.exit()")


def _atexit_handler():
    """Handle atexit cleanup"""
    if not _shutdown_in_progress:
        logger.info("Process exiting, executing shutdown handlers...")
        _execute_shutdown_handlers()


def setup_graceful_shutdown():
    """
    Set up graceful shutdown handling.

    Registers signal handlers for SIGTERM and SIGINT,
    and atexit handler for cleanup.
    """
    # Register signal handlers (third-party library types)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # Register atexit handler
    atexit.register(_atexit_handler)

    logger.info("Graceful shutdown handlers registered (SIGTERM, SIGINT)")


def shutdown(timeout: float = 30.0):
    """
    Initiate graceful shutdown programmatically.

    Args:
        timeout: Maximum time to wait for shutdown (seconds)
    """
    logger.info(f"Initiating graceful shutdown (timeout: {timeout}s)...")
    _shutdown_event.set()

    # Execute handlers
    _execute_shutdown_handlers()

    # Wait for any background threads
    logger.info("Waiting for background threads to complete...")
    time.sleep(min(timeout, 5.0))  # Give threads time to finish

    logger.info("Shutdown complete")


class ShutdownContext:
    """Context manager for operations that should be cancelled on shutdown"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.cancelled = False

    def __enter__(self):
        if is_shutting_down():
            self.cancelled = True
            raise RuntimeError(f"Operation {self.operation_name} cancelled: shutdown in progress")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if is_shutting_down():
            self.cancelled = True
        return False

    def check_shutdown(self):
        """Check if shutdown was requested during operation"""
        if is_shutting_down():
            self.cancelled = True
            raise RuntimeError(f"Operation {self.operation_name} cancelled: shutdown requested")
