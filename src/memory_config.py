"""Dynamic memory configuration for PostgreSQL based on available system RAM"""

import logging
import platform

import psutil

from src.config_loader import ConfigLoader
from src.type_definitions import JSONDict

logger = logging.getLogger(__name__)

# Load configuration with error handling
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    _config_loader = ConfigLoader()

# Memory configuration
MEMORY_PERCENT = _config_loader.get_float("features.memory_config.memory_percent", 50.0)
MIN_MEMORY_MB = _config_loader.get_int("features.memory_config.min_memory_mb", 512)
MAX_MEMORY_MB = _config_loader.get_int("features.memory_config.max_memory_mb", 8192)
AUTO_ADJUST_ENABLED = _config_loader.get_bool("features.memory_config.auto_adjust_enabled", True)

# Windows shared memory limit (per segment)
WINDOWS_SHARED_MEMORY_LIMIT_MB = 64  # Windows default limit per segment


def get_available_memory_mb() -> float:
    """Get available system memory in MB"""
    try:
        mem = psutil.virtual_memory()
        return mem.available / (1024 * 1024)  # Convert to MB
    except Exception as e:
        logger.warning(f"Failed to get available memory: {e}")
        return 4096.0  # Default fallback


def get_total_memory_mb() -> float:
    """Get total system memory in MB"""
    try:
        mem = psutil.virtual_memory()
        return mem.total / (1024 * 1024)  # Convert to MB
    except Exception as e:
        logger.warning(f"Failed to get total memory: {e}")
        return 8192.0  # Default fallback


def calculate_postgres_memory_config() -> JSONDict:
    """
    Calculate optimal PostgreSQL memory configuration based on available RAM.

    Uses 50% of available RAM by default, with intelligent limits for Windows.

    Returns:
        dict with PostgreSQL memory settings in MB
    """
    if not AUTO_ADJUST_ENABLED:
        logger.debug("Auto-adjust memory configuration disabled")
        return _get_default_config()

    available_mb = get_available_memory_mb()
    total_mb = get_total_memory_mb()

    # Calculate target memory (50% of available by default)
    target_memory_mb = (available_mb * MEMORY_PERCENT) / 100.0

    # Apply min/max limits
    target_memory_mb = max(MIN_MEMORY_MB, min(target_memory_mb, MAX_MEMORY_MB))

    # Detect Windows and adjust for shared memory limits
    is_windows = platform.system() == "Windows"

    if is_windows:
        # On Windows, shared memory segments are limited to ~64MB each
        # We need to be conservative with maintenance_work_mem
        # But can use more for shared_buffers (which uses different mechanism)

        # shared_buffers: Can use more (25% of target, but max 1GB for Windows)
        shared_buffers_mb = min(int(target_memory_mb * 0.25), 1024)

        # maintenance_work_mem: Must stay under Windows segment limit
        # Use 32MB to leave headroom (Windows limit is ~64MB per segment)
        maintenance_work_mem_mb = min(32, int(target_memory_mb * 0.05))

        # work_mem: Per-operation memory, can be smaller
        work_mem_mb = min(4, int(target_memory_mb * 0.01))

        # effective_cache_size: Can be larger (OS cache estimate)
        effective_cache_size_mb = int(target_memory_mb * 0.75)

        logger.info(
            f"Windows detected - adjusting for shared memory limits. "
            f"Available: {available_mb:.0f}MB, Target: {target_memory_mb:.0f}MB, "
            f"shared_buffers: {shared_buffers_mb}MB, maintenance_work_mem: {maintenance_work_mem_mb}MB"
        )
    else:
        # Linux/Unix: Can use more aggressive settings
        shared_buffers_mb = int(target_memory_mb * 0.25)
        maintenance_work_mem_mb = min(1024, int(target_memory_mb * 0.10))  # Max 1GB
        work_mem_mb = min(64, int(target_memory_mb * 0.02))  # Max 64MB per operation
        effective_cache_size_mb = int(target_memory_mb * 0.75)

        logger.info(
            f"Linux/Unix detected - using standard memory settings. "
            f"Available: {available_mb:.0f}MB, Target: {target_memory_mb:.0f}MB"
        )

    config: JSONDict = {
        "shared_buffers": f"{shared_buffers_mb}MB",
        "maintenance_work_mem": f"{maintenance_work_mem_mb}MB",
        "work_mem": f"{work_mem_mb}MB",
        "effective_cache_size": f"{effective_cache_size_mb}MB",
        "max_connections": 100,  # Keep reasonable default
        "calculated_from_available_mb": available_mb,
        "calculated_from_total_mb": total_mb,
        "target_memory_mb": target_memory_mb,
        "is_windows": is_windows,
    }

    logger.info(
        f"Calculated PostgreSQL memory config: "
        f"shared_buffers={shared_buffers_mb}MB, "
        f"maintenance_work_mem={maintenance_work_mem_mb}MB, "
        f"work_mem={work_mem_mb}MB, "
        f"effective_cache_size={effective_cache_size_mb}MB"
    )

    return config


def _get_default_config() -> JSONDict:
    """Get default PostgreSQL memory configuration"""
    config: JSONDict = {
        "shared_buffers": "128MB",
        "maintenance_work_mem": "64MB",
        "work_mem": "4MB",
        "effective_cache_size": "4GB",
        "max_connections": 100,
        "calculated_from_available_mb": 0,
        "calculated_from_total_mb": 0,
        "target_memory_mb": 0,
        "is_windows": platform.system() == "Windows",
    }
    return config


def get_postgres_memory_config() -> JSONDict:
    """
    Get PostgreSQL memory configuration (auto-calculated or from config).

    Returns:
        dict with PostgreSQL memory settings
    """
    return calculate_postgres_memory_config()


def generate_docker_compose_postgres_command() -> str:
    """
    Generate PostgreSQL command string for docker-compose.yml.

    Returns:
        Multi-line command string for docker-compose
    """
    config = get_postgres_memory_config()

    command_parts = [
        "postgres",
        f"-c shared_buffers={config['shared_buffers']}",
        f"-c maintenance_work_mem={config['maintenance_work_mem']}",
        f"-c work_mem={config['work_mem']}",
        f"-c effective_cache_size={config['effective_cache_size']}",
        f"-c max_connections={config['max_connections']}",
    ]

    return " ".join(command_parts)


def generate_postgresql_conf_snippet() -> str:
    """
    Generate PostgreSQL configuration snippet for postgresql.conf.

    Returns:
        Configuration snippet as string
    """
    config = get_postgres_memory_config()

    lines = [
        "# Auto-generated memory configuration (dynamic based on available RAM)",
        f"# Generated from {config['calculated_from_available_mb']:.0f}MB available RAM",
        f"# Target memory: {config['target_memory_mb']:.0f}MB ({MEMORY_PERCENT}% of available)",
        "",
        f"shared_buffers = {config['shared_buffers']}",
        f"maintenance_work_mem = {config['maintenance_work_mem']}",
        f"work_mem = {config['work_mem']}",
        f"effective_cache_size = {config['effective_cache_size']}",
        f"max_connections = {config['max_connections']}",
    ]

    if config["is_windows"]:
        lines.append("")
        lines.append(
            "# Windows: maintenance_work_mem limited to 32MB due to shared memory segment limits"
        )

    return "\n".join(lines)


def get_memory_status() -> JSONDict:
    """Get current memory status and configuration"""
    config = get_postgres_memory_config()
    available_mb = get_available_memory_mb()
    total_mb = get_total_memory_mb()

    status: JSONDict = {
        "auto_adjust_enabled": AUTO_ADJUST_ENABLED,
        "memory_percent": MEMORY_PERCENT,
        "total_memory_mb": total_mb,
        "available_memory_mb": available_mb,
        "target_memory_mb": config["target_memory_mb"],
        "postgres_config": {
            "shared_buffers": config["shared_buffers"],
            "maintenance_work_mem": config["maintenance_work_mem"],
            "work_mem": config["work_mem"],
            "effective_cache_size": config["effective_cache_size"],
            "max_connections": config["max_connections"],
        },
        "is_windows": config["is_windows"],
        "windows_shared_memory_limit_mb": WINDOWS_SHARED_MEMORY_LIMIT_MB
        if config["is_windows"]
        else None,
    }
    return status
