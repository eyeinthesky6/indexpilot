# Configuration Guide - IndexPilot

**Date**: 05-12-2025  
**Purpose**: Complete guide for configuring IndexPilot system settings, bypass system, adapters, and feature-specific options

---

## Overview

IndexPilot can be configured via:
1. **Configuration File** (`indexpilot_config.yaml`) - Recommended for most settings
2. **Environment Variables** - Override config file settings
3. **Runtime API** - Programmatic control for emergency situations

**Priority Order** (highest to lowest):
1. Runtime API overrides
2. Environment variables
3. Configuration file
4. Code defaults

---

## Configuration File

### File Location

**Default**: `indexpilot_config.yaml` in project root

**Override**: Set `INDEXPILOT_CONFIG_FILE` environment variable:
```bash
export INDEXPILOT_CONFIG_FILE=/path/to/custom_config.yaml
```

### Complete Configuration Template

See `indexpilot_config.yaml.example` in project root for complete template.

---

## Bypass System Configuration

The bypass system provides 4 levels of control for production safety.

### Level 1: Feature-Level Bypasses

Disable individual features:

```yaml
bypass:
  features:
    auto_indexing:
      enabled: true  # Set to false to disable auto-indexing
      reason: ""     # Optional: reason for current state
    
    stats_collection:
      enabled: true  # Set to false to disable query stats collection
      reason: ""
    
    expression_checks:
      enabled: true  # Set to false to disable expression profile checks
      reason: ""
    
    mutation_logging:
      enabled: true  # Set to false to disable mutation logging
      reason: ""
```

**Environment Variables:**
```bash
export INDEXPILOT_BYPASS_AUTO_INDEXING=false
export INDEXPILOT_BYPASS_STATS_COLLECTION=false
export INDEXPILOT_BYPASS_EXPRESSION_CHECKS=false
export INDEXPILOT_BYPASS_MUTATION_LOGGING=false
```

**Runtime API:**
```python
from src.rollback import disable_auto_indexing, enable_auto_indexing

disable_auto_indexing(reason="Emergency: High CPU usage")
# ... later ...
enable_auto_indexing()
```

---

### Level 2: Module-Level Bypass

Disable entire modules:

```yaml
bypass:
  modules:
    optimization_features:
      enabled: true  # Set to false to disable all optimization features
      reason: ""
```

---

### Level 3: System-Level Bypass

Disable the entire system:

```yaml
bypass:
  system:
    enabled: false  # Set to true to completely bypass the system
    reason: ""
    use_direct_connections: true  # Use direct DB connections when bypassed
```

**Environment Variable:**
```bash
export INDEXPILOT_BYPASS_MODE=true
```

**Runtime API:**
```python
from src.rollback import disable_system, enable_system

disable_system(reason="Emergency: Database issues")
# ... later ...
enable_system()
```

---

### Level 4: Startup Bypass

Skip system initialization entirely:

```yaml
bypass:
  startup:
    skip_initialization: false  # Set to true to skip initialization
    reason: ""
```

**Environment Variable:**
```bash
export INDEXPILOT_BYPASS_SKIP_INIT=true
```

---

### Emergency Bypass (Runtime Override)

Emergency bypass with auto-recovery:

```yaml
bypass:
  emergency:
    enabled: false  # Set to true for emergency bypass
    reason: ""
    auto_recover_after_seconds: 0  # 0 = manual recovery, >0 = auto-recover
```

**Runtime API:**
```python
from src.rollback import emergency_disable, emergency_recover

emergency_disable(reason="Critical issue detected", auto_recover_after=300)
# System will auto-recover after 300 seconds
```

---

### Checking Bypass Status

**Programmatic:**
```python
from src.rollback import get_system_status

status = get_system_status()
print(status['summary']['any_bypass_active'])
print(status['features']['auto_indexing']['enabled'])
```

**Human-Readable Display:**
```python
from src.bypass_status import display_bypass_status

display_bypass_status()
```

**Output:**
```
Bypass Status:
  System: ENABLED
  Auto-Indexing: ENABLED
  Stats Collection: DISABLED (Reason: High CPU usage)
  Expression Checks: ENABLED
  Mutation Logging: ENABLED
```

---

## System Configuration

### Database Connection

```yaml
system:
  database:
    host: "localhost"
    port: 5432
    name: "indexpilot"
    user: "indexpilot"
    # password: ""  # NEVER in config file - use DB_PASSWORD environment variable
```

**Environment Variables:**
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=indexpilot
export DB_USER=indexpilot
export DB_PASSWORD=your_password  # REQUIRED in production
```

**Supabase Connection:**
```bash
export SUPABASE_DB_URL=postgresql://user:password@host:port/database
```

---

### Connection Pool

```yaml
system:
  connection_pool:
    min_connections: 2   # Minimum pool size
    max_connections: 20  # Maximum pool size
```

**Environment Variables:**
```bash
export DB_POOL_MIN=2
export DB_POOL_MAX=20
```

**Note**: For Supabase, use smaller pool sizes (1-5 connections).

---

### Query Timeout

```yaml
system:
  query:
    timeout_seconds: 30  # Query timeout in seconds
```

**Environment Variable:**
```bash
export DB_QUERY_TIMEOUT=30
```

---

### Maintenance

```yaml
system:
  maintenance:
    interval_seconds: 3600  # Maintenance task interval (1 hour)
```

---

### Logging

```yaml
system:
  logging:
    level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Environment Variable:**
```bash
export LOG_LEVEL=INFO
```

---

## Feature-Specific Configuration

### Auto-Indexing

```yaml
features:
  auto_indexing:
    # Cost-benefit threshold multiplier (higher = less aggressive)
    threshold_multiplier: 1.0
    
    # Minimum queries per hour to consider indexing
    min_queries_per_hour: 100
    
    # Maximum indexes per table
    max_indexes_per_table: 10
```

**Tuning Tips:**
- **Higher `threshold_multiplier`** = Less aggressive indexing (fewer indexes created)
- **Lower `threshold_multiplier`** = More aggressive indexing (more indexes created)
- **Higher `min_queries_per_hour`** = Only index heavily-used fields
- **Lower `min_queries_per_hour`** = Index more fields

---

### Stats Collection

```yaml
features:
  stats_collection:
    # Batch size for stats flushing
    batch_size: 100
    
    # Flush interval in seconds
    flush_interval_seconds: 5
    
    # Maximum buffer size
    max_buffer_size: 10000
```

**Tuning Tips:**
- **Higher `batch_size`** = Fewer database writes, more memory usage
- **Lower `batch_size`** = More database writes, less memory usage
- **Higher `flush_interval_seconds`** = Less frequent flushing, more memory usage
- **Lower `flush_interval_seconds`** = More frequent flushing, less memory usage

---

### Expression Profiles

```yaml
features:
  expression_profiles:
    # Default field expression (if no profile exists)
    default_expression: true
    
    # Cache expression checks (performance optimization)
    cache_enabled: true
    cache_ttl_seconds: 300  # Cache TTL in seconds
```

---

## Adapter Configuration

### Monitoring Adapter (CRITICAL)

**Purpose**: Integrate with host monitoring (Datadog, Prometheus, etc.)

**Why Critical**: Internal monitoring loses alerts on restart. Host monitoring ensures alerts are persisted.

**Configuration:**
```python
from src.adapters import configure_adapters, get_monitoring_adapter, get_adapter_fallback_metrics
import datadog

# Configure with validation (recommended)
configure_adapters(
    monitoring=datadog.statsd,
    validate=True  # Check interface matches (default: True)
)

# Verify it's working
monitoring = get_monitoring_adapter()
if monitoring.is_healthy():
    print("✅ Monitoring adapter configured and healthy")
else:
    print("⚠️ Monitoring adapter not healthy - check configuration")

# Check for fallback issues
fallback_metrics = get_adapter_fallback_metrics()
if fallback_metrics:
    print(f"⚠️ Adapter fallbacks detected: {fallback_metrics}")
```

**See**: `docs/installation/ADAPTERS_USAGE_GUIDE.md` for complete adapter configuration.

---

### Database Adapter (HostDatabaseAdapter)

**Purpose**: Reuse host database connection pool and inherit RLS/RBAC policies

**Why Important**: 
- Reduces resource waste (single connection pool)
- **Security**: Inherits RLS/RBAC policies from host database automatically
- Better integration with host application

**Configuration:**
```python
from src.adapters import configure_adapters, get_host_database_adapter

# Configure adapter
configure_adapters(
    database=host_db_pool,  # Your existing connection pool
    validate=True            # Validate interface (recommended)
)

# Verify it's working
adapter = get_host_database_adapter()
if adapter.is_healthy():
    print("✅ Database adapter configured and healthy")
```

**Note**: This is `HostDatabaseAdapter` (renamed from `DatabaseAdapter` for clarity). A backward compatibility alias exists.

---

### Error Tracking Adapter

**Purpose**: Integrate with host error tracking (Sentry, Rollbar)

**Configuration:**
```python
from src.adapters import configure_adapters
import sentry_sdk

configure_adapters(
    error_tracker=sentry_sdk
)
```

---

### Audit Adapter

**Purpose**: Unified audit trail with host system

**Configuration:**
```python
from src.adapters import configure_adapters

configure_adapters(
    audit=host_audit_system
)
```

---

## Environment Variables Reference

### System Bypass

```bash
# Complete system bypass
export INDEXPILOT_BYPASS_MODE=true

# Feature-level bypasses
export INDEXPILOT_BYPASS_AUTO_INDEXING=false
export INDEXPILOT_BYPASS_STATS_COLLECTION=false
export INDEXPILOT_BYPASS_EXPRESSION_CHECKS=false
export INDEXPILOT_BYPASS_MUTATION_LOGGING=false

# Startup bypass
export INDEXPILOT_BYPASS_SKIP_INIT=true

# Config file location
export INDEXPILOT_CONFIG_FILE=/path/to/config.yaml
```

### Database Connection

```bash
# Standard connection
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=indexpilot
export DB_USER=indexpilot
export DB_PASSWORD=your_password

# Supabase connection (alternative)
export SUPABASE_DB_URL=postgresql://user:password@host:port/database

# Connection pool
export DB_POOL_MIN=2
export DB_POOL_MAX=20

# Query timeout
export DB_QUERY_TIMEOUT=30
```

### Logging

```bash
export LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Environment

```bash
export ENVIRONMENT=production  # production, development, test
```

---

## Configuration Validation

The system validates configuration at startup:

```python
from src.production_config import validate_production_config

config = validate_production_config()
# Raises ValueError if configuration is invalid
```

**Validation Checks:**
- ✅ Required environment variables (DB_PASSWORD in production)
- ✅ Connection pool size limits
- ✅ Port number ranges
- ✅ Log level values
- ✅ Security checks (default passwords, SSL/TLS)

---

## Configuration Reload

Reload configuration from file:

```python
from src.config_loader import get_config

config = get_config()
config.reload()  # Reload from file
```

---

## Best Practices

### Production

1. **Use Environment Variables for Secrets**
   - Never put passwords in config files
   - Use `DB_PASSWORD` environment variable

2. **Configure Host Monitoring Adapter**
   - Critical for production
   - Prevents alert loss on restart

3. **Set Appropriate Log Levels**
   - Production: `INFO` or `WARNING`
   - Development: `DEBUG`

4. **Configure Bypass System**
   - Set up config file for quick disable
   - Test bypass functionality

5. **Tune Feature Settings**
   - Adjust `threshold_multiplier` based on your needs
   - Monitor index creation patterns
   - Adjust stats collection batch size

### Development

1. **Use Config File**
   - Easier to manage settings
   - Version control friendly

2. **Enable Debug Logging**
   - Set `LOG_LEVEL=DEBUG`
   - More detailed information

3. **Lower Thresholds**
   - Set `min_queries_per_hour` lower for testing
   - More aggressive indexing for testing

---

## Troubleshooting

### Configuration Not Loading

**Issue**: Config file not found

**Solution**:
- Check file location (project root by default)
- Set `INDEXPILOT_CONFIG_FILE` environment variable
- Verify file name is `indexpilot_config.yaml`

### Environment Variables Not Working

**Issue**: Environment variables not overriding config file

**Solution**:
- Check variable names (must start with `INDEXPILOT_` or `DB_`)
- Verify variable values (case-sensitive for some)
- Restart application after setting variables

### Bypass Not Working

**Issue**: Bypass settings not taking effect

**Solution**:
- Check priority order (runtime API > env vars > config file)
- Verify config file syntax (YAML)
- Check bypass status: `from src.rollback import get_system_status`

---

## Related Documentation

- **Adapters**: `docs/installation/ADAPTERS_USAGE_GUIDE.md`
- **Installation**: `docs/installation/HOW_TO_INSTALL.md`
- **Features**: `docs/features/FEATURES.md`
- **Architecture**: `docs/tech/ARCHITECTURE.md`

---

**Last Updated**: 05-12-2025

