"""Maintenance window scheduling for index creation"""

import logging
import typing
from datetime import datetime

logger = logging.getLogger(__name__)

# Load config for maintenance window settings
try:
    from src.config_loader import ConfigLoader

    _config_loader: ConfigLoader | None = ConfigLoader()
except Exception:
    _config_loader = None


class MaintenanceWindow:
    """Define maintenance windows for low-impact operations"""

    def __init__(
        self, start_hour: int = 2, end_hour: int = 6, days_of_week: list[int] | None = None
    ):
        """
        Initialize maintenance window.

        Args:
            start_hour: Start hour (0-23), default 2 AM
            end_hour: End hour (0-23), default 6 AM
            days_of_week: List of days (0=Monday, 6=Sunday), None = all days
        """
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.days_of_week = days_of_week or list(range(7))  # All days by default

    def is_in_window(self, check_time: datetime | None = None) -> bool:
        """
        Check if current time (or specified time) is in maintenance window.

        Args:
            check_time: Time to check (default: now)

        Returns:
            True if in maintenance window
        """
        if check_time is None:
            check_time = datetime.now()

        current_hour = check_time.hour
        current_day = check_time.weekday()  # 0=Monday, 6=Sunday

        # Check day of week
        if current_day not in self.days_of_week:
            return False

        # Check hour (handle wrap-around)
        if self.start_hour <= self.end_hour:
            # Normal case: 2 AM to 6 AM
            return self.start_hour <= current_hour < self.end_hour
        else:
            # Wrap-around case: 22 PM to 2 AM
            return current_hour >= self.start_hour or current_hour < self.end_hour

    def time_until_window(self, check_time: datetime | None = None) -> float:
        """
        Calculate seconds until next maintenance window.

        Args:
            check_time: Time to check from (default: now)

        Returns:
            Seconds until next window (0 if in window)
        """
        if check_time is None:
            check_time = datetime.now()

        if self.is_in_window(check_time):
            return 0.0

        # Find next window
        next_window = check_time.replace(hour=self.start_hour, minute=0, second=0, microsecond=0)

        # If we've passed today's window, move to tomorrow
        if next_window <= check_time:
            from datetime import timedelta

            next_window += timedelta(days=1)

        # Skip days not in window
        while next_window.weekday() not in self.days_of_week:
            from datetime import timedelta

            next_window += timedelta(days=1)

        delta = next_window - check_time
        return delta.total_seconds()

    def should_wait_for_window(
        self, operation_type: str = "index_creation", max_wait_hours: float = 24.0
    ) -> tuple[bool, float]:
        """
        Determine if operation should wait for maintenance window.

        Args:
            operation_type: Type of operation
            max_wait_hours: Maximum hours to wait

        Returns:
            (should_wait, seconds_to_wait)
        """
        if self.is_in_window():
            return False, 0.0

        seconds_to_wait = self.time_until_window()
        hours_to_wait = seconds_to_wait / 3600.0

        if hours_to_wait > max_wait_hours:
            logger.info(
                f"Maintenance window too far away ({hours_to_wait:.1f}h), "
                f"proceeding with {operation_type}"
            )
            return False, 0.0

        logger.info(f"Waiting {hours_to_wait:.1f}h for maintenance window before {operation_type}")
        return True, seconds_to_wait


# Load maintenance window from config or use defaults
def _load_maintenance_window() -> MaintenanceWindow:
    """Load maintenance window from config"""
    if _config_loader is None:
        return MaintenanceWindow(start_hour=2, end_hour=6)

    enabled = _config_loader.get_bool("production_safeguards.maintenance_window.enabled", True)
    if not enabled:
        # If disabled, return a window that's always active (no waiting)
        return MaintenanceWindow(start_hour=0, end_hour=23, days_of_week=list(range(7)))

    start_hour = _config_loader.get_int("production_safeguards.maintenance_window.start_hour", 2)
    end_hour = _config_loader.get_int("production_safeguards.maintenance_window.end_hour", 6)
    days_of_week_value = _config_loader.get(
        "production_safeguards.maintenance_window.days_of_week", None
    )

    if days_of_week_value is None:
        days_of_week = list(range(7))  # All days
    elif isinstance(days_of_week_value, list):
        # Convert to list[int], filtering out non-integer values
        days_of_week = [
            int(d) for d in days_of_week_value if isinstance(d, (int, str)) and str(d).isdigit()
        ]
        if not days_of_week:
            days_of_week = list(range(7))  # Default if conversion failed
    else:
        days_of_week = list(range(7))  # Default to all days if invalid

    return MaintenanceWindow(start_hour=start_hour, end_hour=end_hour, days_of_week=days_of_week)


# Default maintenance window: loaded from config or 2-6 AM, all days
_default_window = _load_maintenance_window()


def get_maintenance_window() -> MaintenanceWindow:
    """Get default maintenance window"""
    return _default_window


def set_maintenance_window(window: MaintenanceWindow):
    """Set custom maintenance window"""
    global _default_window
    _default_window = window


def is_maintenance_window_enabled() -> bool:
    """Check if maintenance window enforcement is enabled"""
    if _config_loader is None:
        return True  # Default enabled
    return _config_loader.get_bool("production_safeguards.maintenance_window.enabled", True)


def is_in_maintenance_window(check_time: datetime | None = None) -> bool:
    """Check if current time is in maintenance window"""
    if not is_maintenance_window_enabled():
        return True  # If disabled, always return True (no waiting)
    return _default_window.is_in_window(check_time)


def should_wait_for_maintenance_window(
    operation_type: str = "index_creation", max_wait_hours: float = 24.0, tenant_id: int | None = None
) -> tuple[bool, float]:
    """
    Check if operation should wait for maintenance window.
    
    Args:
        operation_type: Type of operation
        max_wait_hours: Maximum hours to wait
        tenant_id: Tenant ID (for per-tenant windows)
    
    Returns:
        (should_wait, seconds_to_wait)
    """
    if not is_maintenance_window_enabled():
        return False, 0.0  # If disabled, don't wait
    
    # Check for per-tenant maintenance window
    if tenant_id:
        try:
            from src.per_tenant_config import get_tenant_maintenance_window
            
            tenant_window_config = get_tenant_maintenance_window(tenant_id)
            if tenant_window_config:
                # Create tenant-specific window
                tenant_window = MaintenanceWindow(
                    start_hour=tenant_window_config.get("start_hour", 2),
                    end_hour=tenant_window_config.get("end_hour", 6),
                    days_of_week=tenant_window_config.get("days_of_week", list(range(7))),
                )
                return tenant_window.should_wait_for_window(operation_type, max_wait_hours)
        except Exception as e:
            logger.debug(f"Could not get tenant maintenance window: {e}")
    
    # Use default window
    return _default_window.should_wait_for_window(operation_type, max_wait_hours)


def get_next_maintenance_window(tenant_id: int | None = None) -> dict[str, typing.Any] | None:
    """
    Get next maintenance window time.
    
    Args:
        tenant_id: Tenant ID (for per-tenant windows)
    
    Returns:
        dict with next window info or None
    """
    if tenant_id:
        try:
            from src.per_tenant_config import get_tenant_maintenance_window
            
            tenant_window_config = get_tenant_maintenance_window(tenant_id)
            if tenant_window_config:
                tenant_window = MaintenanceWindow(
                    start_hour=tenant_window_config.get("start_hour", 2),
                    end_hour=tenant_window_config.get("end_hour", 6),
                    days_of_week=tenant_window_config.get("days_of_week", list(range(7))),
                )
                seconds_until = tenant_window.time_until_window()
                from datetime import timedelta
                
                next_window_time = datetime.now() + timedelta(seconds=seconds_until)
                return {
                    "next_window": next_window_time.isoformat(),
                    "seconds_until": seconds_until,
                    "hours_until": seconds_until / 3600.0,
                    "is_tenant_specific": True,
                }
        except Exception:
            pass
    
    # Default window
    seconds_until = _default_window.time_until_window()
    from datetime import timedelta
    
    next_window_time = datetime.now() + timedelta(seconds=seconds_until)
    return {
        "next_window": next_window_time.isoformat(),
        "seconds_until": seconds_until,
        "hours_until": seconds_until / 3600.0,
        "is_tenant_specific": False,
    }
