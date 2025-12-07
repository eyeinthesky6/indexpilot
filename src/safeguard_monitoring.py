"""Production safeguard monitoring and metrics"""

import logging
import threading
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Safeguard metrics (thread-safe)
_safeguard_metrics: dict[str, Any] = {
    "rate_limiting": {
        "triggers": 0,
        "queries_blocked": 0,
        "last_trigger": None,
    },
    "cpu_throttling": {
        "triggers": 0,
        "operations_throttled": 0,
        "last_trigger": None,
    },
    "maintenance_window": {
        "checks": 0,
        "waits": 0,
        "last_wait": None,
    },
    "write_performance": {
        "checks": 0,
        "degradations": 0,
        "last_degradation": None,
    },
    "index_creation": {
        "attempts": 0,
        "successes": 0,
        "throttled": 0,
        "blocked": 0,
    },
}
_metrics_lock = threading.Lock()


def track_rate_limit_trigger(queries_blocked: int = 1):
    """Track rate limiting trigger."""
    with _metrics_lock:
        _safeguard_metrics["rate_limiting"]["triggers"] += 1
        _safeguard_metrics["rate_limiting"]["queries_blocked"] += queries_blocked
        _safeguard_metrics["rate_limiting"]["last_trigger"] = datetime.now().isoformat()


def track_cpu_throttle(operations_throttled: int = 1):
    """Track CPU throttling trigger."""
    with _metrics_lock:
        _safeguard_metrics["cpu_throttling"]["triggers"] += 1
        _safeguard_metrics["cpu_throttling"]["operations_throttled"] += operations_throttled
        _safeguard_metrics["cpu_throttling"]["last_trigger"] = datetime.now().isoformat()


def track_maintenance_window_wait():
    """Track maintenance window wait."""
    with _metrics_lock:
        _safeguard_metrics["maintenance_window"]["checks"] += 1
        _safeguard_metrics["maintenance_window"]["waits"] += 1
        _safeguard_metrics["maintenance_window"]["last_wait"] = datetime.now().isoformat()


def track_write_performance_degradation():
    """Track write performance degradation."""
    with _metrics_lock:
        _safeguard_metrics["write_performance"]["checks"] += 1
        _safeguard_metrics["write_performance"]["degradations"] += 1
        _safeguard_metrics["write_performance"]["last_degradation"] = datetime.now().isoformat()


def track_index_creation_attempt(success: bool, throttled: bool = False, blocked: bool = False):
    """Track index creation attempt."""
    with _metrics_lock:
        _safeguard_metrics["index_creation"]["attempts"] += 1
        if success:
            _safeguard_metrics["index_creation"]["successes"] += 1
        if throttled:
            _safeguard_metrics["index_creation"]["throttled"] += 1
        if blocked:
            _safeguard_metrics["index_creation"]["blocked"] += 1


def get_safeguard_metrics() -> dict[str, Any]:
    """Get all safeguard metrics."""
    with _metrics_lock:
        # Calculate effectiveness rates
        metrics = _safeguard_metrics.copy()

        # Rate limiting effectiveness
        if metrics["rate_limiting"]["triggers"] > 0:
            metrics["rate_limiting"]["effectiveness"] = min(
                1.0,
                metrics["rate_limiting"]["queries_blocked"] / metrics["rate_limiting"]["triggers"],
            )
        else:
            metrics["rate_limiting"]["effectiveness"] = 0.0

        # CPU throttling effectiveness
        if metrics["cpu_throttling"]["triggers"] > 0:
            metrics["cpu_throttling"]["effectiveness"] = min(
                1.0,
                metrics["cpu_throttling"]["operations_throttled"]
                / metrics["cpu_throttling"]["triggers"],
            )
        else:
            metrics["cpu_throttling"]["effectiveness"] = 0.0

        # Index creation success rate
        if metrics["index_creation"]["attempts"] > 0:
            metrics["index_creation"]["success_rate"] = (
                metrics["index_creation"]["successes"] / metrics["index_creation"]["attempts"]
            )
        else:
            metrics["index_creation"]["success_rate"] = 0.0

        return metrics


def get_safeguard_status() -> dict[str, Any]:
    """Get current safeguard status and health."""
    metrics = get_safeguard_metrics()

    status = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "healthy",
        "safeguards": {},
    }

    # Check each safeguard
    for safeguard_name, safeguard_data in metrics.items():
        safeguard_status = {
            "enabled": True,
            "triggers": safeguard_data.get("triggers", 0) + safeguard_data.get("checks", 0),
            "last_activity": safeguard_data.get("last_trigger") or safeguard_data.get("last_wait"),
        }

        # Determine health status
        if safeguard_name == "index_creation":
            success_rate = safeguard_data.get("success_rate", 0.0)
            if success_rate < 0.5:
                safeguard_status["health"] = "degraded"
                status["overall_status"] = "degraded"
            elif success_rate < 0.8:
                safeguard_status["health"] = "warning"
            else:
                safeguard_status["health"] = "healthy"
        else:
            # For other safeguards, high trigger count might indicate issues
            triggers = safeguard_data.get("triggers", 0)
            if triggers > 100:
                safeguard_status["health"] = "warning"
            else:
                safeguard_status["health"] = "healthy"

        status["safeguards"][safeguard_name] = safeguard_status

    return status
