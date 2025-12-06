"""Production configuration validation and hardening"""

import logging
import os

from src.type_definitions import ConfigDict, JSONValue

logger = logging.getLogger(__name__)


class ProductionConfig:
    """Production configuration validator and manager"""

    REQUIRED_ENV_VARS = {
        'production': ['DB_PASSWORD'],
        'all': []
    }

    OPTIONAL_ENV_VARS = {
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'indexpilot',
        'DB_USER': 'indexpilot',
        'ENVIRONMENT': 'development',
        'LOG_LEVEL': 'INFO',
        'MAX_CONNECTIONS': '20',
        'MIN_CONNECTIONS': '2',
        'QUERY_TIMEOUT': '30',
        'MAINTENANCE_INTERVAL': '3600',
    }

    def __init__(self):
        self.is_production = self._check_production()
        self.config: ConfigDict = {}
        self.validated = False

    def _check_production(self) -> bool:
        """Check if running in production environment"""
        env = os.getenv('ENVIRONMENT', '').lower()
        return env in ('production', 'prod')

    def validate(self) -> ConfigDict:
        """
        Validate production configuration.

        Returns:
            dict: Validated configuration

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        if self.validated:
            return self.config

        errors: list[str] = []
        warnings: list[str] = []

        # Check required environment variables
        required = self.REQUIRED_ENV_VARS.get('all', [])
        if self.is_production:
            required.extend(self.REQUIRED_ENV_VARS.get('production', []))

        for var in required:
            value = os.getenv(var)
            if not value:
                errors.append(f"Required environment variable {var} is not set")

        # Validate optional variables with defaults
        for var, default in self.OPTIONAL_ENV_VARS.items():
            value = os.getenv(var, default)
            self.config[var] = value

            # Validate specific variables
            if var == 'DB_PORT':
                try:
                    port = int(value)
                    if not (1 <= port <= 65535):
                        errors.append(f"DB_PORT must be between 1 and 65535, got {port}")
                except ValueError:
                    errors.append(f"DB_PORT must be a number, got {value}")

            elif var == 'MAX_CONNECTIONS':
                try:
                    max_conn = int(str(value))
                    min_conn_val = self.config.get('MIN_CONNECTIONS', '2')
                    min_conn = int(str(min_conn_val))
                    if max_conn < min_conn:
                        errors.append(f"MAX_CONNECTIONS ({max_conn}) must be >= MIN_CONNECTIONS ({min_conn})")
                    if max_conn > 100:
                        warnings.append(f"MAX_CONNECTIONS ({max_conn}) is very high, consider reducing")
                except (ValueError, TypeError):
                    errors.append(f"MAX_CONNECTIONS must be a number, got {value}")

            elif var == 'QUERY_TIMEOUT':
                try:
                    timeout = float(value)
                    if timeout < 1 or timeout > 3600:
                        errors.append(f"QUERY_TIMEOUT must be between 1 and 3600 seconds, got {timeout}")
                except ValueError:
                    errors.append(f"QUERY_TIMEOUT must be a number, got {value}")

            elif var == 'LOG_LEVEL':
                valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
                if not isinstance(value, str) or value.upper() not in valid_levels:
                    errors.append(f"LOG_LEVEL must be one of {valid_levels}, got {value}")

        # Production-specific checks
        if self.is_production:
            # Check for development defaults
            if self.config.get('DB_PASSWORD') == 'indexpilot':
                errors.append("Cannot use default password 'indexpilot' in production")

            # Warn about development settings
            if self.config.get('DB_HOST') == 'localhost':
                warnings.append("DB_HOST is 'localhost' - ensure this is correct for production")

            log_level = self.config.get('LOG_LEVEL', 'INFO')
            if isinstance(log_level, str) and log_level.upper() == 'DEBUG':
                warnings.append("LOG_LEVEL is DEBUG in production - consider using INFO or higher")

        # Report errors and warnings
        if warnings:
            for warning in warnings:
                logger.warning(f"Configuration warning: {warning}")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

        self.validated = True
        logger.info("Configuration validated successfully")
        if self.is_production:
            logger.info("Running in PRODUCTION mode")
        else:
            logger.info("Running in DEVELOPMENT mode")

        return self.config

    def get(self, key: str, default: JSONValue | None = None) -> JSONValue | None:
        """Get configuration value"""
        if not self.validated:
            self.validate()
        return self.config.get(key, default)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get configuration value as integer"""
        value = self.get(key, default)
        try:
            return int(str(value))
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get configuration value as float"""
        value = self.get(key, default)
        try:
            return float(str(value))
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get configuration value as boolean"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)


# Global configuration instance
_config: ProductionConfig | None = None


def get_config() -> ProductionConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = ProductionConfig()
        _config.validate()
    return _config


def validate_production_config() -> ConfigDict:
    """
    Validate production configuration at startup.

    Should be called early in application startup.

    Returns:
        dict: Validated configuration

    Raises:
        ValueError: If configuration is invalid
    """
    return get_config().validate()

