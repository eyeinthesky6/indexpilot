"""Configuration file loader with environment variable overrides"""

import logging
import os
from pathlib import Path

from src.type_definitions import ConfigDict, JSONValue

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore[assignment]
    YAML_AVAILABLE = False
    logging.getLogger(__name__).warning("PyYAML not installed. Install with: pip install pyyaml")

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads configuration from YAML file with environment variable overrides"""

    def __init__(self, config_file: str | None = None):
        self.config_file = config_file or self._find_config_file()
        self.config: ConfigDict = {}
        self.load()

    def _find_config_file(self) -> str:
        """Find config file in standard locations"""
        # 1. Environment variable
        env_file = os.getenv("INDEXPILOT_CONFIG_FILE")
        if env_file and Path(env_file).exists():
            return env_file

        # 2. Current directory
        current_dir = Path.cwd() / "indexpilot_config.yaml"
        if current_dir.exists():
            return str(current_dir)

        # 3. Project root (parent of src/)
        try:
            project_root = Path(__file__).parent.parent / "indexpilot_config.yaml"
            if project_root.exists():
                return str(project_root)
        except Exception:
            pass

        # 4. Default location
        return str(Path.cwd() / "indexpilot_config.yaml")

    def load(self) -> ConfigDict:
        """Load configuration from file"""
        if not Path(self.config_file).exists():
            logger.debug(f"Config file not found: {self.config_file}, using defaults")
            self.config = self._get_defaults()
            return self.config

        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available, using defaults")
            self.config = self._get_defaults()
            return self.config

        try:
            with open(self.config_file, encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    # Empty file, use defaults
                    logger.warning(f"Config file {self.config_file} is empty, using defaults")
                    self.config = self._get_defaults()
                    return self.config

                if yaml is None:
                    raise ImportError("PyYAML is required but not installed")
                loaded_config: object = yaml.safe_load(content)
                if loaded_config is None:
                    loaded_config = {}
                if not isinstance(loaded_config, dict):
                    raise ValueError(f"Config file {self.config_file} must contain a dictionary")
                # Type narrowing: isinstance check ensures it's a dict
                # yaml.safe_load returns Any, but we've validated it's a dict at runtime
                self.config = loaded_config

            # Validate and merge with defaults
            self.config = self._merge_with_defaults(self.config)

            # Apply environment variable overrides
            self._apply_env_overrides()

            logger.info(f"Configuration loaded from: {self.config_file}")
            return self.config
        except OSError as e:
            # File I/O errors
            logger.error(f"Failed to read config file {self.config_file}: {e}, using defaults")
            self.config = self._get_defaults()
            return self.config
        except Exception as e:
            # Check if it's a YAML error
            if yaml is not None and isinstance(e, yaml.YAMLError):
                # YAML parsing error
                logger.error(f"Invalid YAML in config file {self.config_file}: {e}, using defaults")
            elif yaml is None:
                raise ImportError("PyYAML is required but not installed") from e
            else:
                # Any other error
                logger.error(
                    f"Unexpected error loading config file {self.config_file}: {e}, using defaults"
                )
            self.config = self._get_defaults()
            return self.config

    def _apply_env_overrides(self):
        """Apply environment variable overrides"""
        # Complete bypass
        if os.getenv("INDEXPILOT_BYPASS_MODE", "").lower() in ("true", "1", "yes"):
            self._set_nested("bypass.system.enabled", True)
            self._set_nested("bypass.system.reason", "Environment variable INDEXPILOT_BYPASS_MODE")

        # Feature-level bypasses
        for feature in [
            "auto_indexing",
            "stats_collection",
            "expression_checks",
            "mutation_logging",
        ]:
            env_key = f"INDEXPILOT_BYPASS_{feature.upper()}"
            value = os.getenv(env_key, "").lower()
            if value in ("false", "0", "no", "off"):
                self._set_nested(f"bypass.features.{feature}.enabled", False)
                self._set_nested(
                    f"bypass.features.{feature}.reason", f"Environment variable {env_key}"
                )

        # Startup bypass
        if os.getenv("INDEXPILOT_BYPASS_SKIP_INIT", "").lower() in ("true", "1", "yes"):
            self._set_nested("bypass.startup.skip_initialization", True)
            self._set_nested(
                "bypass.startup.reason", "Environment variable INDEXPILOT_BYPASS_SKIP_INIT"
            )

    def _set_nested(self, path: str, value: JSONValue) -> None:
        """Set nested dictionary value using dot notation"""
        if not path:
            return
        keys = path.split(".")
        d: ConfigDict = self.config
        for key in keys[:-1]:
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            nested_val = d.get(key)
            if isinstance(nested_val, dict):
                d = nested_val
            else:
                # Create new dict and assign it
                new_dict: ConfigDict = {}
                d[key] = new_dict
                d = new_dict
        d[keys[-1]] = value

    def get(self, path: str, default: JSONValue | None = None) -> JSONValue | None:
        """Get configuration value using dot notation"""
        if not path:
            return default
        keys = path.split(".")
        value: JSONValue = self.config
        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    def get_bool(self, path: str, default: bool = False) -> bool:
        """Get boolean configuration value"""
        value = self.get(path, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    def get_int(self, path: str, default: int = 0) -> int:
        """Get integer configuration value"""
        value = self.get(path, default)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        if isinstance(value, float):
            return int(value)
        # For other types (list, dict), return default
        return default

    def get_float(self, path: str, default: float = 0.0) -> float:
        """Get float configuration value"""
        value = self.get(path, default)
        if isinstance(value, float):
            return value
        if isinstance(value, int):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return default
        # For other types (list, dict, None), return default
        return default

    def _merge_with_defaults(self, config: ConfigDict) -> ConfigDict:
        """Merge loaded config with defaults to ensure all keys exist"""
        defaults = self._get_defaults()

        # Deep merge: config values override defaults, but defaults fill missing keys
        def deep_merge(default: ConfigDict, override: ConfigDict) -> ConfigDict:
            result: ConfigDict = default.copy()
            for key, value in override.items():
                existing_val = result.get(key)
                if (
                    existing_val is not None
                    and isinstance(existing_val, dict)
                    and isinstance(value, dict)
                ):
                    result[key] = deep_merge(existing_val, value)
                else:
                    result[key] = value
            return result

        return deep_merge(defaults, config)

    def _get_defaults(self) -> ConfigDict:
        """Get default configuration"""
        return {
            "bypass": {
                "features": {
                    "auto_indexing": {"enabled": True, "reason": ""},
                    "stats_collection": {"enabled": True, "reason": ""},
                    "expression_checks": {"enabled": True, "reason": ""},
                    "mutation_logging": {"enabled": True, "reason": ""},
                },
                "modules": {"optimization_features": {"enabled": True, "reason": ""}},
                "system": {"enabled": False, "reason": "", "use_direct_connections": True},
                "startup": {"skip_initialization": False, "reason": ""},
                "emergency": {"enabled": False, "reason": "", "auto_recover_after_seconds": 0},
            },
            "features": {
                "query_interceptor": {
                    "max_query_cost": 10000.0,
                    "max_seq_scan_cost": 1000.0,
                    "max_planning_time_ms": 100.0,
                    "enable_blocking": True,
                    "enable_rate_limiting": True,
                    "enable_plan_cache": True,
                    "plan_cache_ttl": 300,
                    "plan_cache_max_size": 1000,
                    "query_preview_length": 200,
                    "safety_score_unsafe_threshold": 0.3,
                    "safety_score_warning_threshold": 0.7,
                    "safety_score_high_cost_penalty": 0.5,
                    "safety_score_seq_scan_penalty": 0.7,
                    "safety_score_nested_loop_penalty": 0.8,
                },
                "auto_indexer": {
                    "build_cost_per_1000_rows": 1.0,
                    "query_cost_per_10000_rows": 1.0,
                    "min_query_cost": 0.1,
                    "index_type_costs": {
                        "partial": 0.5,
                        "expression": 0.7,
                        "standard": 1.0,
                        "multi_column": 1.2,
                    },
                    "min_selectivity_for_index": 0.01,
                    "high_selectivity_threshold": 0.5,
                    "min_improvement_pct": 20.0,
                    "sample_query_runs": 5,
                    "use_real_query_plans": True,
                    "min_plan_cost_for_index": 100.0,
                    "small_table_row_count": 1000,
                    "medium_table_row_count": 10000,
                    "small_table_min_queries_per_hour": 1000,
                    "small_table_max_index_overhead_pct": 50.0,
                    "medium_table_max_index_overhead_pct": 60.0,
                    "large_table_cost_reduction_factor": 0.8,
                    "max_wait_for_maintenance_window": 3600,
                },
                "cpu_throttle": {
                    "cpu_threshold": 80.0,
                    "cpu_cooldown": 30.0,
                    "max_cpu_during_creation": 95.0,
                    "min_delay_between_indexes": 60.0,
                    "cpu_monitoring_window": 60,
                    "cpu_check_interval": 5.0,
                    "max_cooldown_wait": 300,
                },
                "rate_limiter": {
                    "query": {"max_requests": 1000, "time_window_seconds": 60.0},
                    "index_creation": {"max_requests": 10, "time_window_seconds": 3600.0},
                    "connection": {"max_requests": 100, "time_window_seconds": 60.0},
                },
                "production_safeguards": {
                    "maintenance_window": {
                        "enabled": True,
                        "start_hour": 2,
                        "end_hour": 6,
                        "days_of_week": [0, 1, 2, 3, 4, 5, 6],  # All days
                    },
                    "write_performance": {
                        "enabled": True,
                        "max_indexes_per_table": 10,
                        "warn_indexes_per_table": 7,
                        "write_overhead_threshold": 0.2,
                    },
                },
                "operational": {
                    "health_checks": {"enabled": True},
                    "maintenance_tasks": {"enabled": True},
                    "reporting": {"enabled": True},
                    "schema_evolution": {"enabled": True},
                },
            },
        }
