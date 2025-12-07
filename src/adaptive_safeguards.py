"""Adaptive safeguards: adaptive thresholds, circuit breakers, canary deployments"""

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from src.rollback import is_system_enabled

logger = logging.getLogger(__name__)

# Adaptive threshold state
_adaptive_thresholds: dict[str, dict[str, Any]] = {}
_threshold_lock = threading.Lock()

# Circuit breaker state
_circuit_breakers: dict[str, "CircuitBreaker"] = {}
_circuit_lock = threading.Lock()

# Canary deployment state
_canary_deployments: dict[str, "CanaryDeployment"] = {}
_canary_lock = threading.Lock()

# Performance history for adaptive thresholds
_performance_history: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
_history_lock = threading.Lock()


class CircuitBreaker:
    """Circuit breaker pattern for index creation operations."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.opened_at: float | None = None

    def record_success(self) -> None:
        """Record a successful operation."""
        if self.state == "half_open":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = "closed"
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name} closed (recovered)")
        elif self.state == "closed":
            self.failure_count = 0  # Reset on success

    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == "half_open":
            # Failed during half-open, open again
            self.state = "open"
            self.opened_at = time.time()
            self.success_count = 0
            logger.warning(f"Circuit breaker {self.name} opened (failed during recovery)")
        elif self.state == "closed" and self.failure_count >= self.failure_threshold:
            # Open the circuit
            self.state = "open"
            self.opened_at = time.time()
            logger.warning(
                f"Circuit breaker {self.name} opened "
                f"({self.failure_count} failures >= {self.failure_threshold})"
            )

    def can_proceed(self) -> bool:
        """Check if operation can proceed."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            # Check if timeout has passed
            if self.opened_at and (time.time() - self.opened_at) >= self.timeout_seconds:
                # Transition to half-open
                self.state = "half_open"
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name} half-open (testing recovery)")
                return True
            return False
        else:  # half_open
            return True

    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "opened_at": datetime.fromtimestamp(self.opened_at).isoformat()
            if self.opened_at
            else None,
            "time_since_opened": (time.time() - self.opened_at) if self.opened_at else None,
        }


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    with _circuit_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name)
        return _circuit_breakers[name]


def check_circuit_breaker(name: str) -> bool:
    """Check if circuit breaker allows operation."""
    breaker = get_circuit_breaker(name)
    return breaker.can_proceed()


def record_circuit_success(name: str) -> None:
    """Record success for circuit breaker."""
    breaker = get_circuit_breaker(name)
    breaker.record_success()


def record_circuit_failure(name: str) -> None:
    """Record failure for circuit breaker."""
    breaker = get_circuit_breaker(name)
    breaker.record_failure()


def get_circuit_breaker_status(name: str | None = None) -> dict[str, Any]:
    """Get circuit breaker status."""
    with _circuit_lock:
        if name:
            if name in _circuit_breakers:
                return _circuit_breakers[name].get_status()
            return {"error": "Circuit breaker not found"}
        else:
            return {name: breaker.get_status() for name, breaker in _circuit_breakers.items()}


def update_adaptive_threshold(
    threshold_name: str,
    current_value: float,
    target_percentile: float = 0.95,
    min_samples: int = 10,
) -> float:
    """
    Update adaptive threshold based on historical performance.

    Args:
        threshold_name: Name of the threshold (e.g., "rate_limit", "cpu_threshold")
        current_value: Current metric value
        target_percentile: Target percentile (0.95 = allow 95% of operations)
        min_samples: Minimum samples before adapting

    Returns:
        Updated threshold value
    """
    if not is_system_enabled():
        return current_value

    # Record current value
    with _history_lock:
        _performance_history[threshold_name].append(current_value)

    # Calculate adaptive threshold
    with _threshold_lock:
        history = list(_performance_history[threshold_name])

        if len(history) < min_samples:
            # Not enough data, use current value
            _adaptive_thresholds[threshold_name] = {
                "value": current_value,
                "samples": len(history),
                "method": "insufficient_data",
            }
            return current_value

        # Calculate percentile
        sorted_history = sorted(history)
        index = int(len(sorted_history) * target_percentile)
        index = min(index, len(sorted_history) - 1)
        adaptive_value = sorted_history[index]

        _adaptive_thresholds[threshold_name] = {
            "value": adaptive_value,
            "samples": len(history),
            "method": "percentile",
            "percentile": target_percentile,
            "min": min(history),
            "max": max(history),
            "mean": sum(history) / len(history),
        }

        logger.debug(
            f"Updated adaptive threshold {threshold_name}: {adaptive_value:.2f} "
            f"(from {len(history)} samples, {target_percentile:.0%} percentile)"
        )

        return adaptive_value


def get_adaptive_threshold(threshold_name: str, default: float = 100.0) -> float:
    """Get current adaptive threshold value."""
    with _threshold_lock:
        if threshold_name in _adaptive_thresholds:
            value = _adaptive_thresholds[threshold_name].get("value", default)
            if isinstance(value, (int, float)):
                return float(value)
            return default
        return default


def get_adaptive_threshold_status() -> dict[str, Any]:
    """Get status of all adaptive thresholds."""
    with _threshold_lock:
        return {
            name: {
                "value": info["value"],
                "samples": info["samples"],
                "method": info.get("method", "unknown"),
            }
            for name, info in _adaptive_thresholds.items()
        }


class CanaryDeployment:
    """Canary deployment for index creation."""

    def __init__(
        self,
        deployment_id: str,
        index_name: str,
        table_name: str,
        canary_percent: float = 10.0,
        success_threshold: float = 0.95,
        min_queries: int = 100,
    ):
        self.deployment_id = deployment_id
        self.index_name = index_name
        self.table_name = table_name
        self.canary_percent = canary_percent  # % of traffic to test
        self.success_threshold = success_threshold  # Success rate to consider good
        self.min_queries = min_queries
        self.status = "active"  # active, promoted, rolled_back
        self.created_at = time.time()
        self.canary_queries = 0
        self.canary_successes = 0
        self.canary_failures = 0
        self.control_queries = 0
        self.control_successes = 0
        self.control_failures = 0

    def should_use_canary(self) -> bool:
        """Determine if this query should use canary (based on percentage)."""
        import random

        return random.random() * 100 < self.canary_percent

    def record_canary_result(self, success: bool) -> None:
        """Record a result from canary traffic."""
        self.canary_queries += 1
        if success:
            self.canary_successes += 1
        else:
            self.canary_failures += 1

        self._evaluate()

    def record_control_result(self, success: bool) -> None:
        """Record a result from control traffic."""
        self.control_queries += 1
        if success:
            self.control_successes += 1
        else:
            self.control_failures += 1

    def _evaluate(self) -> None:
        """Evaluate canary results and decide on promotion/rollback."""
        if self.canary_queries < self.min_queries:
            return  # Not enough data

        canary_success_rate = (
            self.canary_successes / self.canary_queries if self.canary_queries > 0 else 0.0
        )

        if canary_success_rate >= self.success_threshold:
            # Promote to full deployment
            self.status = "promoted"
            logger.info(
                f"Canary deployment {self.deployment_id} promoted "
                f"(success rate: {canary_success_rate:.1%})"
            )
        elif canary_success_rate < (self.success_threshold * 0.8):
            # Rollback
            self.status = "rolled_back"
            logger.warning(
                f"Canary deployment {self.deployment_id} rolled back "
                f"(success rate: {canary_success_rate:.1%} < {self.success_threshold * 0.8:.1%})"
            )

    def get_status(self) -> dict[str, Any]:
        """Get canary deployment status."""
        canary_success_rate = (
            self.canary_successes / self.canary_queries if self.canary_queries > 0 else 0.0
        )
        control_success_rate = (
            self.control_successes / self.control_queries if self.control_queries > 0 else 0.0
        )

        return {
            "deployment_id": self.deployment_id,
            "index_name": self.index_name,
            "table_name": self.table_name,
            "status": self.status,
            "canary_percent": self.canary_percent,
            "canary_queries": self.canary_queries,
            "canary_success_rate": canary_success_rate,
            "control_queries": self.control_queries,
            "control_success_rate": control_success_rate,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
        }


def create_canary_deployment(
    deployment_id: str,
    index_name: str,
    table_name: str,
    canary_percent: float = 10.0,
) -> CanaryDeployment:
    """Create a new canary deployment."""
    canary = CanaryDeployment(
        deployment_id=deployment_id,
        index_name=index_name,
        table_name=table_name,
        canary_percent=canary_percent,
    )

    with _canary_lock:
        _canary_deployments[deployment_id] = canary

    logger.info(
        f"Created canary deployment {deployment_id} for index {index_name} "
        f"({canary_percent}% traffic)"
    )
    return canary


def get_canary_deployment(deployment_id: str) -> CanaryDeployment | None:
    """Get canary deployment."""
    with _canary_lock:
        return _canary_deployments.get(deployment_id)


def get_all_canary_deployments() -> dict[str, dict[str, Any]]:
    """Get all canary deployment statuses."""
    with _canary_lock:
        return {
            dep_id: deployment.get_status() for dep_id, deployment in _canary_deployments.items()
        }
