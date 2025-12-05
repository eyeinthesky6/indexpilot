# Configurable Features Analysis

**Date**: 05-12-2025  
**Purpose**: Identify which features should be configurable vs hardcoded for security/system defense

---

## Summary

**Currently Configurable** (via config file): 
- ✅ 4 core features (auto_indexing, stats_collection, expression_checks, mutation_logging)
- ✅ Rate limiting (fully configurable via `features.rate_limiter.*`)
- ✅ CPU throttling (fully configurable via `features.cpu_throttle.*`)
- ✅ Query interceptor (fully configurable via `features.query_interceptor.*`)
- ✅ Auto-indexer cost config (fully configurable via `features.auto_indexer.*`)
- ✅ Maintenance task interval (via env var + config)

**Hardcoded as Constants** (not in config, should be moved):
- ⚠️ Maintenance windows (start/end hours, days - only max_wait is configurable)
- ⚠️ Write performance thresholds (MAX_INDEXES_PER_TABLE, WARN_INDEXES_PER_TABLE, WRITE_PERFORMANCE_THRESHOLD)
- ⚠️ Monitoring alert thresholds (ALERT_THRESHOLDS dict)
- ⚠️ Pattern detection constants (MIN_DAYS_SUSTAINED, MIN_QUERIES_PER_DAY, etc.)
- ⚠️ Resilience constants (MAX_OPERATION_DURATION)
- ⚠️ Lock manager constants (MAX_LOCK_DURATION)

**Still Needs Feature Toggles** (enable/disable):
- ⚠️ Health checks (enable/disable)
- ⚠️ Reporting (enable/disable)
- ⚠️ Schema evolution (enable/disable)

**Must Stay Hardcoded**: Security, system defense, and critical stability features

---

## Decision Criteria

**Keep as Constants** (if not expensive or DB-breaking):
- Monitoring alert thresholds - Just alerting, no DB impact
- Pattern detection constants - Analysis thresholds, no DB impact
- Resilience constants - Timeout values, operational only
- Lock manager constants - Timeout values, operational only

**Add Toggles + Config** (if expensive or DB-breaking):
- Maintenance windows - Can delay index creation (expensive)
- Write performance thresholds - Can block index creation (DB-breaking)
- Schema evolution - Alters database schema (DB-breaking)

**Add Toggles Only** (if expensive or operational overhead):
- Health checks - Operational overhead
- Reporting - Runs queries (expensive)
- Maintenance tasks - Operational overhead

---

## Features That Should Be Configurable

### 1. Production Safeguards (Thresholds & Settings)

These have hardcoded thresholds that should be configurable:

#### Maintenance Windows
- **Status**: ⚠️ **NEEDS TOGGLE + CONFIG** (expensive - delays index creation)
- **Current**: Hardcoded default in `src/maintenance_window.py`:
  - `_default_window = MaintenanceWindow(start_hour=2, end_hour=6)` (constants)
- **Already Configurable**: `max_wait_for_maintenance_window` (via `features.auto_indexer.max_wait_for_maintenance_window`)
- **Needs**: 
  - **Toggle**: Enable/disable maintenance window enforcement
  - **Config**: Start/end hours, days of week configuration
- **Why**: Can delay index creation significantly (expensive), different environments have different low-traffic periods

#### Rate Limiting
- **Status**: ✅ **ALREADY CONFIGURABLE**
- **Config Path**: `features.rate_limiter.query.*`, `features.rate_limiter.index_creation.*`, `features.rate_limiter.connection.*`
- **Implementation**: `src/rate_limiter.py` reads from config loader
- **Settings**: max_requests, time_window_seconds for each operation type

#### CPU Throttling
- **Status**: ✅ **ALREADY CONFIGURABLE**
- **Config Path**: `features.cpu_throttle.*`
- **Implementation**: `src/cpu_throttle.py` reads from config loader
- **Settings**: cpu_threshold, cpu_cooldown, max_cpu_during_creation, min_delay_between_indexes, etc.

#### Write Performance Monitoring
- **Status**: ⚠️ **NEEDS TOGGLE + CONFIG** (DB-breaking - limits index creation)
- **Current**: Constants in `src/write_performance.py`:
  - `MAX_INDEXES_PER_TABLE = 10`
  - `WARN_INDEXES_PER_TABLE = 7`
  - `WRITE_PERFORMANCE_THRESHOLD = 0.2`
- **Needs**: 
  - **Toggle**: Enable/disable write performance monitoring (can block index creation)
  - **Config**: Move thresholds to config file
- **Why**: Can prevent index creation (DB-breaking), different tables have different write patterns and requirements

### 2. Operational Features (Enable/Disable)

These might need to be disabled in some environments:

#### Health Checks
- **Status**: ⚠️ **NEEDS TOGGLE** (operational feature)
- **Should Configure**: Enable/disable health check endpoints
- **Why**: Some test environments might not need health checks, can add overhead

#### Maintenance Tasks
- **Status**: ⚠️ **PARTIALLY CONFIGURABLE**
- **Already Configurable**: Interval via `MAINTENANCE_INTERVAL` env var and `production_config`
- **Still Needs**: Enable/disable toggle
- **Why**: Some environments might want to disable maintenance tasks entirely

#### Monitoring & Logging
- **Status**: ✅ **KEEP AS CONSTANTS** (not expensive/DB-breaking - just alerting)
- **Current**: Constants dict in `src/monitoring.py`:
  - `ALERT_THRESHOLDS = {'query_latency_p95_ms': 100, 'query_latency_p99_ms': 200, ...}`
- **Decision**: Keep as constants - these are just alert thresholds, not expensive or DB-breaking
- **Optional**: Could move to config if users need to tune alert thresholds, but low priority

#### Reporting & Analytics
- **Status**: ⚠️ **NEEDS TOGGLE** (expensive - runs queries)
- **Should Configure**: Enable/disable reporting generation
- **Why**: Can be expensive (runs queries), not all environments need reporting overhead

#### Safe Live Schema Evolution
- **Status**: ⚠️ **NEEDS TOGGLE** (DB-breaking - alters schema)
- **Should Configure**: Enable/disable schema evolution features
- **Why**: Can alter database schema (DB-breaking), some environments might want to disable automatic schema changes

---

## Features That Must Stay Hardcoded

### Security & System Defense (Always Enabled)

1. **Security Hardening**
   - SQL injection prevention (parameterized queries)
   - Input validation
   - Credential protection
   - Error message sanitization
   - **Reason**: Critical security - must never be disabled

2. **Error Handling & Recovery**
   - Graceful degradation
   - Error recovery mechanisms
   - Comprehensive error logging
   - **Reason**: Critical for system stability

3. **Thread Safety**
   - Thread-safe buffers
   - Lock management
   - Connection pool thread safety
   - **Reason**: Critical for correctness - disabling would cause data corruption

4. **Configuration Validation**
   - Startup validation
   - Type validation
   - Bounds checking
   - Security checks
   - **Reason**: Prevents misconfiguration that could cause security issues

5. **Graceful Shutdown**
   - Signal handling
   - Resource cleanup
   - **Reason**: Critical for clean operations and data integrity

6. **Resource Management**
   - Connection pooling (limits)
   - Buffer size limits
   - Memory protection
   - Query timeouts
   - **Reason**: Prevents resource exhaustion attacks

### Core Infrastructure (Always Enabled)

7. **Schema Abstraction**
   - Dynamic schema loading
   - Schema validation
   - **Reason**: Core functionality - system wouldn't work without it

8. **Database Adapter Pattern**
   - Database type detection
   - SQL generation
   - **Reason**: Core functionality

9. **Dynamic Validation**
   - Validation from genome_catalog
   - **Reason**: Core functionality

---

## Recommended Configuration Structure

```yaml
# Production Safeguards Configuration
production_safeguards:
  # Maintenance Windows - Toggle + Config (expensive - delays index creation)
  maintenance_window:
    enabled: true  # Toggle: enable/disable maintenance window enforcement
    start_hour: 2
    end_hour: 6
    days_of_week: [0, 1, 2, 3, 4, 5, 6]  # All days
    max_wait_hours: 24.0  # Already configurable via features.auto_indexer.max_wait_for_maintenance_window
  
  # Rate Limiting - Already configurable ✅
  rate_limiting:
    # Already in features.rate_limiter.*
  
  # CPU Throttling - Already configurable ✅
  cpu_throttling:
    # Already in features.cpu_throttle.*
  
  # Write Performance - Toggle + Config (DB-breaking - limits index creation)
  write_performance:
    enabled: true  # Toggle: enable/disable write performance monitoring
    max_indexes_per_table: 10
    warn_indexes_per_table: 7
    write_overhead_threshold: 0.2  # 20%

# Operational Features Configuration
operational:
  # Health Checks - Toggle (operational overhead)
  health_checks:
    enabled: true  # Toggle: enable/disable health check endpoints
  
  # Maintenance Tasks - Already has interval config, needs toggle
  maintenance_tasks:
    enabled: true  # Toggle: enable/disable maintenance tasks
    interval_seconds: 3600  # Already configurable via MAINTENANCE_INTERVAL env var
  
  # Reporting - Toggle (expensive - runs queries)
  reporting:
    enabled: true  # Toggle: enable/disable reporting generation
  
  # Schema Evolution - Toggle (DB-breaking - alters schema)
  schema_evolution:
    enabled: true  # Toggle: enable/disable schema evolution features

# Note: Monitoring alert thresholds, pattern detection, resilience, and lock manager
# constants are kept as constants (not expensive/DB-breaking)
```

---

## Implementation Priority

### High Priority - Needs Toggles + Config (Expensive/DB-Breaking)
1. **Maintenance Windows** - Toggle + config (expensive - delays index creation)
2. **Write Performance Thresholds** - Toggle + config (DB-breaking - limits index creation)
3. **Schema Evolution** - Toggle (DB-breaking - alters schema)

### Medium Priority - Needs Toggles (Expensive/Operational)
4. **Health Checks** - Toggle (operational overhead)
5. **Reporting** - Toggle (expensive - runs queries)

### Low Priority - Keep as Constants (Not Expensive/DB-Breaking)
6. **Monitoring Alert Thresholds** - Keep as constants (just alerting, not expensive)
7. **Pattern Detection Constants** - Keep as constants (analysis thresholds, not expensive)
8. **Resilience Constants** - Keep as constants (timeout values, not expensive)
9. **Lock Manager Constants** - Keep as constants (timeout values, not expensive)

### Already Implemented ✅
1. **Rate Limiting** - Fully configurable via `features.rate_limiter.*`
2. **CPU Throttling** - Fully configurable via `features.cpu_throttle.*`
3. **Maintenance Task Interval** - Configurable via env var and config

### Medium Priority (Operational Flexibility)
2. **Operational Feature Toggles** - Enable/disable for different environments
   - Health checks
   - Maintenance tasks
   - Monitoring thresholds
   - Reporting
   - Schema evolution

### Low Priority (Already Adequate)
3. **Core Features** - Already configurable via bypass system
   - Auto-indexing
   - Stats collection
   - Expression checks
   - Mutation logging

---

## Conclusion

**Total Features**: 25  
**Currently Configurable** (via config file): 6 (4 core + 2 production safeguards)  
**Needs Toggles + Config**: 2 features (maintenance windows, write performance)  
**Needs Toggles Only**: 3 features (health checks, reporting, schema evolution)  
**Keep as Constants**: 4 features (monitoring, pattern detection, resilience, lock manager)  
**Must Stay Hardcoded**: 13 (security, system defense, core infrastructure)

**Already Moved to Config ✅**:
- Rate limiting (fully configurable via `features.rate_limiter.*`)
- CPU throttling (fully configurable via `features.cpu_throttle.*`)
- Query interceptor (fully configurable via `features.query_interceptor.*`)
- Auto-indexer costs (fully configurable via `features.auto_indexer.*`)
- Maintenance task interval (configurable)

**Needs Toggles + Config** (expensive/DB-breaking) ⚠️:
- Maintenance windows (toggle + config - expensive, delays index creation)
- Write performance thresholds (toggle + config - DB-breaking, limits index creation)
- Schema evolution (toggle - DB-breaking, alters schema)

**Needs Toggles Only** (expensive/operational) ⚠️:
- Health checks (toggle - operational overhead)
- Reporting (toggle - expensive, runs queries)

**Keep as Constants** (not expensive/DB-breaking) ✅:
- Monitoring alert thresholds (just alerting)
- Pattern detection constants (analysis thresholds)
- Resilience constants (timeout values)
- Lock manager constants (timeout values)

**Recommendation**: 
1. **Add toggles + config** for expensive/DB-breaking features:
   - Maintenance windows (toggle + config)
   - Write performance thresholds (toggle + config)
   - Schema evolution (toggle)
2. **Add toggles only** for expensive/operational features:
   - Health checks (toggle)
   - Reporting (toggle)
3. **Keep as constants** (not expensive/DB-breaking):
   - Monitoring alert thresholds
   - Pattern detection constants
   - Resilience constants
   - Lock manager constants
4. **Keep all security and system defense features hardcoded**

---

**Last Updated**: 05-12-2025

