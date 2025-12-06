"""Bypass configuration manager integrated with config file"""

import logging
import threading

from src.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Global config loader instance (thread-safe)
_config_loader: ConfigLoader | None = None
_config_lock = threading.Lock()


def get_bypass_config() -> ConfigLoader:
    """Get global bypass configuration loader (thread-safe)"""
    global _config_loader
    if _config_loader is None:
        with _config_lock:
            # Double-check pattern to avoid race condition
            if _config_loader is None:
                _config_loader = ConfigLoader()
    return _config_loader


def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled via config"""
    config = get_bypass_config()
    return config.get_bool(f"bypass.features.{feature_name}.enabled", True)


def is_system_bypassed() -> bool:
    """Check if complete system bypass is enabled"""
    config = get_bypass_config()
    return config.get_bool("bypass.system.enabled", False)


def should_skip_initialization() -> bool:
    """Check if system initialization should be skipped"""
    config = get_bypass_config()
    return config.get_bool("bypass.startup.skip_initialization", False)


def get_bypass_reason(feature_name: str | None = None) -> str:
    """Get reason for bypass (if any)"""
    config = get_bypass_config()
    if feature_name:
        value = config.get(f"bypass.features.{feature_name}.reason", "")
        return str(value) if value is not None else ""
    value = config.get("bypass.system.reason", "")
    return str(value) if value is not None else ""


def reload_config():
    """Reload configuration from file (for runtime updates) - thread-safe"""
    global _config_loader
    with _config_lock:
        _config_loader = None  # Force reload
        config = get_bypass_config()
    logger.info("Configuration reloaded from file")
    return config
