# Utility Adapters Usage Guide

## Overview

IndexPilot now supports integration with host application utilities through adapters. This allows the system to use host monitoring, database connections, audit systems, logging, and error tracking while maintaining backward compatibility with internal utilities.

## What Does "Configure" Mean?

**"Configure"** means telling IndexPilot how to integrate with your existing application systems. When you use IndexPilot in your codebase, you need to:

1. **Call `configure_adapters()`** at your application startup
2. **Pass your existing utilities** (monitoring, database pool, error tracking, etc.)
3. **IndexPilot will use them** instead of its internal utilities

**Where to Configure**: In your application's startup code:
- `main.py` or `app.py` (Flask/FastAPI)
- `__init__.py` (Django apps)
- Startup script or initialization module
- Any code that runs once when your application starts

**Example - Application Startup**:
```python
# your_project/main.py (or app.py, startup script, etc.)
from indexpilot.adapters import configure_adapters
import datadog
import sentry_sdk
from your_project.db import get_db_pool  # Your existing database pool

def startup():
    """Configure IndexPilot to use your host utilities"""
    
    # Configure adapters (do this ONCE at startup)
    configure_adapters(
        monitoring=datadog.statsd,      # Your monitoring system
        database=get_db_pool(),           # Your existing database pool
        error_tracker=sentry_sdk,        # Your error tracking
        validate=True                    # Validate interfaces (recommended)
    )
    
    # Verify configuration
    from indexpilot.adapters import get_monitoring_adapter
    if get_monitoring_adapter().is_healthy():
        print("✅ IndexPilot adapters configured successfully")

if __name__ == '__main__':
    startup()
    # ... rest of your application
```

**After Configuration**: IndexPilot will automatically use your host utilities for all operations. No need to change how you use IndexPilot - it just works with your systems.

## Quick Start

### Basic Usage (No Integration)

The system works out of the box with its own utilities:

```python
from src.auto_indexer import analyze_and_create_indexes

# Uses internal utilities automatically
analyze_and_create_indexes()
```

### With Host Integration

Configure adapters to use host utilities:

```python
from src.adapters import configure_adapters
from src.auto_indexer import analyze_and_create_indexes
import datadog
import sentry_sdk

# Configure adapters
configure_adapters(
    monitoring=datadog.statsd,      # Host monitoring
    database=host_db_pool,           # Host database pool
    audit=host_audit_system,         # Host audit system
    error_tracker=sentry_sdk,       # Host error tracking
    logger_config={'version': 1, ...}  # Host logger config
)

# System now uses host utilities
analyze_and_create_indexes()
```

---

## Adapter Details

### 1. Monitoring Adapter (CRITICAL)

**Purpose**: Send alerts and metrics to host monitoring systems (Datadog, Prometheus, New Relic, etc.)

**Why Critical**: Internal monitoring is in-memory and loses alerts on restart. Host monitoring ensures alerts are persisted.

**Supported Interfaces**:
- Standard: `alert(level, message)`, `gauge(metric, value)`
- Datadog: `event(title, text, alert_type)`
- Prometheus: `gauge(metric, value)`
- Generic: Callable functions

**Example - Datadog**:
```python
import datadog

configure_adapters(
    monitoring=datadog.statsd
)
```

**Example - Prometheus**:
```python
from prometheus_client import Counter, Gauge

class PrometheusMonitoring:
    def alert(self, level, message, **kwargs):
        # Send to Prometheus alerting
        pass
    
    def gauge(self, metric, value, **kwargs):
        gauge = Gauge(metric, 'IndexPilot metric')
        gauge.set(value)

configure_adapters(monitoring=PrometheusMonitoring())
```

**Example - Custom**:
```python
class CustomMonitoring:
    def alert(self, level, message, **kwargs):
        # Your custom alerting logic
        send_slack_alert(level, message)
    
    def gauge(self, metric, value, **kwargs):
        # Your custom metrics
        send_to_metrics_db(metric, value)

configure_adapters(monitoring=CustomMonitoring())
```

---

### 2. Database Adapter (HostDatabaseAdapter)

**Purpose**: Reuse host application's database connection pool to avoid resource waste and inherit RLS/RBAC policies.

**Why Important**: 
- Separate connection pools waste database connections and resources
- **Security**: Using host pool inherits RLS/RBAC policies automatically
- **Efficiency**: Single connection pool for both host app and IndexPilot

**Note**: This is `HostDatabaseAdapter` (renamed from `DatabaseAdapter` for clarity). A backward compatibility alias exists.

**Supported Interfaces**:
- Context manager: `with get_connection() as conn:`
- psycopg2 pool: `pool.getconn()`, `pool.putconn(conn)`
- Generic: Any object with `get_connection()` method

**Health Checks**:
```python
from indexpilot.adapters import get_host_database_adapter

adapter = get_host_database_adapter()
if adapter.is_healthy():
    print("Database adapter is working correctly")
```

**Example - Django**:
```python
from django.db import connections

def get_django_connection():
    """Get Django database connection"""
    return connections['default'].cursor().connection

configure_adapters(database=get_django_connection)
```

**Example - SQLAlchemy**:
```python
from sqlalchemy import create_engine

engine = create_engine('postgresql://...')

class SQLAlchemyAdapter:
    @contextmanager
    def get_connection(self):
        conn = engine.connect()
        try:
            yield conn
        finally:
            conn.close()

configure_adapters(database=SQLAlchemyAdapter())
```

**Example - psycopg2 Pool**:
```python
from psycopg2 import pool

connection_pool = pool.ThreadedConnectionPool(5, 20, ...)

configure_adapters(database=connection_pool)
```

---

### 3. Audit Adapter

**Purpose**: Write audit events to host audit system for unified compliance tracking.

**Why Important**: Compliance may require unified audit trail across all systems.

**Supported Interfaces**:
- Standard: `log(event_type, **kwargs)`
- Standard: `log_event(event_type, **kwargs)`
- Generic: Callable functions

**Example - Custom Audit System**:
```python
class HostAuditSystem:
    def log(self, event_type, **kwargs):
        # Write to host audit database
        audit_db.insert({
            'event_type': event_type,
            'timestamp': datetime.now(),
            **kwargs
        })

configure_adapters(audit=HostAuditSystem())
```

**Note**: Internal audit trail (`mutation_log` table) is always written regardless of adapter configuration.

---

### 4. Logger Adapter

**Purpose**: Configure logging from host application (levels, handlers, formatters).

**Why Useful**: Unified logging configuration across application and IndexPilot.

**Example**:
```python
import logging.config

host_log_config = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'app.log',
            'level': 'DEBUG',
        },
    },
    'loggers': {
        'src': {
            'level': 'INFO',
            'handlers': ['console', 'file'],
        },
    },
}

configure_adapters(logger_config=host_log_config)
```

---

### 5. Error Handler Adapter

**Purpose**: Send errors to host error tracking (Sentry, Rollbar, etc.).

**Why Useful**: Better error tracking and debugging in production.

**Supported Interfaces**:
- Sentry: `capture_exception(exception, **kwargs)`
- Rollbar: `report_exc_info(exc_info, **kwargs)`
- Generic: Callable functions

**Example - Sentry**:
```python
import sentry_sdk

sentry_sdk.init(dsn="your-sentry-dsn")

configure_adapters(error_tracker=sentry_sdk)
```

**Example - Rollbar**:
```python
import rollbar

rollbar.init('your-rollbar-token', 'production')

configure_adapters(error_tracker=rollbar)
```

**Example - Custom**:
```python
class CustomErrorTracker:
    def capture_exception(self, exception, **kwargs):
        # Send to your error tracking system
        send_to_error_db(exception, **kwargs)

configure_adapters(error_tracker=CustomErrorTracker())
```

---

## Complete Integration Example

```python
"""
Complete example of integrating DNA DB with host application utilities.
"""

import datadog
import sentry_sdk
from src.adapters import configure_adapters
from src.auto_indexer import analyze_and_create_indexes

# Initialize host utilities
datadog.initialize(api_key='...', app_key='...')
sentry_sdk.init(dsn='your-sentry-dsn')

# Host database pool (example)
from psycopg2 import pool
host_db_pool = pool.ThreadedConnectionPool(5, 20, ...)

# Host audit system (example)
class HostAudit:
    def log(self, event_type, **kwargs):
        # Your audit logic
        pass

# Configure adapters (with validation)
configure_adapters(
    monitoring=datadog.statsd,      # Datadog monitoring
    database=host_db_pool,          # Host database pool
    audit=HostAudit(),              # Host audit system
    error_tracker=sentry_sdk,       # Sentry error tracking
    logger_config={                 # Logger configuration
        'version': 1,
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
            },
        },
    },
    validate=True                    # Validate interfaces (recommended)
)

# Verify adapters are working
from src.adapters import (
    get_monitoring_adapter,
    get_host_database_adapter,
    get_adapter_fallback_metrics
)

monitoring = get_monitoring_adapter()
db_adapter = get_host_database_adapter()

if monitoring.is_healthy():
    print("✅ Monitoring adapter healthy")
else:
    print("⚠️ Monitoring adapter not healthy")

if db_adapter.is_healthy():
    print("✅ Database adapter healthy")
else:
    print("⚠️ Database adapter not healthy")

# Check for fallback issues
fallback_metrics = get_adapter_fallback_metrics()
if fallback_metrics:
    print(f"⚠️ Adapter fallbacks detected: {fallback_metrics}")
else:
    print("✅ All adapters working correctly")
        },
        'loggers': {
            'src': {
                'level': 'INFO',
                'handlers': ['console'],
            },
        },
    }
)

# System now uses host utilities
analyze_and_create_indexes()
```

---

## Backward Compatibility

**All adapters are optional**. The system works perfectly without any adapters configured:

- ✅ Uses internal monitoring (in-memory)
- ✅ Uses internal database connection pool
- ✅ Uses internal audit trail (`mutation_log` table)
- ✅ Uses Python standard logging
- ✅ Uses internal error handling

**Adapters enhance the system** but are not required for basic operation.

---

## Production Recommendations

### Required for Production

1. **Monitoring Adapter** ⚠️ **CRITICAL**
   - Internal monitoring loses alerts on restart
   - Must configure for production deployments
   - Recommended: Datadog, Prometheus, New Relic

### Recommended for Production

2. **Database Adapter**
   - Reduces resource waste (separate connection pools)
   - Recommended for integrated deployments

3. **Error Handler Adapter**
   - Better error tracking and debugging
   - Recommended: Sentry, Rollbar

### Optional

4. **Audit Adapter**
   - Only needed if compliance requires unified audit trail

5. **Logger Adapter**
   - Only needed for unified logging configuration

---

## Troubleshooting

### Adapter Not Working

**Problem**: Host utility not being used

**Solution**: Check adapter configuration
```python
from src.adapters import get_monitoring_adapter

adapter = get_monitoring_adapter()
print(f"Using host monitoring: {adapter.use_host}")
```

### Adapter Errors

**Problem**: Adapter throws exceptions

**Solution**: Adapters are designed to fail gracefully. Errors are logged but don't break the system. Check logs for adapter errors.

### Fallback Behavior

**Problem**: Want to ensure fallback to internal utilities

**Solution**: Adapters automatically fall back to internal utilities if host utilities fail or are not configured.

---

## API Reference

See `src/adapters.py` for complete API documentation.

**Key Functions**:
- `configure_adapters()` - Configure all adapters (with optional validation)
- `get_monitoring_adapter()` - Get monitoring adapter
- `get_host_database_adapter()` - Get host database adapter (renamed from DatabaseAdapter)
- `get_audit_adapter()` - Get audit adapter
- `get_error_handler_adapter()` - Get error handler adapter
- `get_adapter_fallback_metrics()` - Get fallback metrics
- `reset_adapter_fallback_metrics()` - Reset fallback metrics

**Adapter Methods**:
- `is_healthy()` - Check if adapter is working correctly (all adapters)

**Note**: `DatabaseAdapter` is now `HostDatabaseAdapter` for clarity. A backward compatibility alias is provided.
- `get_host_database_adapter()` - Get host database adapter (for connection pooling)
- `get_audit_adapter()` - Get audit adapter
- `get_error_handler_adapter()` - Get error handler adapter

**Note**: For database operations (PostgreSQL, MySQL, etc.), use `get_database_adapter()` from `src.database` instead.

---

## Migration Guide

### From Standalone to Integrated

1. **Identify host utilities** in your application
2. **Configure adapters** using `configure_adapters()`
3. **Test integration** in development/staging
4. **Deploy to production** with adapters configured

### No Code Changes Required

The system automatically uses adapters when configured. No changes needed to existing code that uses:
- `get_monitoring()`
- `get_connection()`
- `log_audit_event()`
- `handle_errors()`

---

**Last Updated**: 05-12-2025

