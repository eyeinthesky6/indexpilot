# Query Timeout & Structured Logging Integration - Complete

**Date**: 08-12-2025  
**Status**: ✅ **COMPLETE**  
**Task**: Integrate query timeout and structured logging features

---

## Summary

Successfully integrated **query timeout management** and **structured logging** into IndexPilot. Both features are now active and configurable.

---

## 1. Query Timeout Integration ✅

### What Was Integrated

**Query timeout management** is now integrated into:
- ✅ Database connection handling (`src/db.py`)
- ✅ Long-running operations (REINDEX, VACUUM)
- ✅ Configurable per-operation timeouts

### Integration Points

#### 1. Database Connection Timeout

**File**: `src/db.py` → `get_connection()`

**What It Does**:
- Added `timeout_seconds` parameter to `get_connection()`
- Automatically sets PostgreSQL `statement_timeout` when specified
- Uses `query_timeout` module for proper timeout management

**Usage**:
```python
# Use default timeout from config
with get_connection() as conn:
    cursor.execute("SELECT * FROM table")

# Use custom timeout
with get_connection(timeout_seconds=60.0) as conn:
    cursor.execute("SELECT * FROM large_table")
```

#### 2. REINDEX Operations Timeout

**File**: `src/maintenance.py` → `schedule_automatic_reindex()`

**What It Does**:
- Uses `query_timeout` context manager for REINDEX operations
- Prevents REINDEX from hanging indefinitely
- Uses `max_reindex_time_seconds` from config

**Integration**:
```python
from src.query_timeout import query_timeout

with query_timeout(timeout_seconds=max_reindex_time_seconds):
    # REINDEX operations here
    cursor.execute(f'REINDEX INDEX CONCURRENTLY "{index_name}"')
```

#### 3. VACUUM Operations Timeout

**File**: `src/index_lifecycle_manager.py` → `perform_vacuum_analyze_for_indexes()`

**What It Does**:
- Uses `query_timeout` context manager for VACUUM operations
- Configurable timeout (default: 5 minutes)
- Prevents VACUUM from hanging

**Configuration**:
```yaml
features:
  index_lifecycle:
    vacuum_timeout_seconds: 300.0  # 5 minutes default
```

---

### Configuration

**File**: `indexpilot_config.yaml`

```yaml
features:
  query_timeout:
    enabled: true  # Enable query timeout management
    default_query_timeout_seconds: 30.0  # Default timeout for queries (30 seconds)
    default_statement_timeout_seconds: 60.0  # Default timeout for statements (60 seconds)
```

**Environment Variables**:
- `QUERY_TIMEOUT` - Default query timeout (from `production_config.py`)

---

## 2. Structured Logging Integration ✅

### What Was Integrated

**Structured logging** is now set up at application startup:
- ✅ API server startup (`src/api_server.py`)
- ✅ Simulator startup (`src/simulation/simulator.py`)
- ✅ Auto-indexer startup (`src/auto_indexer.py`)

### Integration Points

#### 1. API Server Startup

**File**: `src/api_server.py`

**What It Does**:
- Calls `setup_structured_logging()` at module import
- Sets up JSON logging if enabled in config
- Falls back to standard logging if disabled or unavailable

**Integration**:
```python
# Set up structured logging at startup (if enabled)
try:
    from src.structured_logging import setup_structured_logging
    setup_structured_logging()
except Exception as e:
    logger.debug(f"Could not set up structured logging: {e}, using standard logging")
```

#### 2. Simulator Startup

**File**: `src/simulation/simulator.py`

**What It Does**:
- Sets up structured logging before system initialization
- Ensures all simulation logs use structured format if enabled

#### 3. Auto-Indexer Startup

**File**: `src/auto_indexer.py`

**What It Does**:
- Sets up structured logging at module level
- Ensures index creation logs use structured format if enabled

---

### Configuration

**File**: `indexpilot_config.yaml`

```yaml
features:
  structured_logging:
    enabled: false  # Enable structured logging (JSON format) - disabled by default
    format: "json"  # Log format: "json" or "text"
    include_context: true  # Include context in log entries
    include_stack_trace: false  # Include stack traces in logs
```

**Enable Structured Logging**:
```yaml
features:
  structured_logging:
    enabled: true  # Enable JSON logging
    format: "json"
```

---

## Usage Examples

### Query Timeout

#### Default Timeout (from config)
```python
from src.db import get_connection

# Uses default timeout from config (30 seconds)
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM table")
```

#### Custom Timeout
```python
from src.db import get_connection

# Use custom timeout (60 seconds)
with get_connection(timeout_seconds=60.0) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM large_table")
```

#### Long-Running Operations
```python
from src.query_timeout import query_timeout

# Use context manager for long-running operations
with query_timeout(timeout_seconds=300.0):  # 5 minutes
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("VACUUM ANALYZE large_table")
```

---

### Structured Logging

#### Enable in Config
```yaml
features:
  structured_logging:
    enabled: true
    format: "json"
```

#### Log Output

**Standard Logging** (default):
```
2025-12-08 10:00:00 - INFO - Index created successfully for tenant 1
```

**Structured Logging** (JSON format):
```json
{
  "timestamp": "2025-12-08T10:00:00Z",
  "level": "INFO",
  "logger": "src.auto_indexer",
  "message": "Index created successfully for tenant 1",
  "module": "auto_indexer",
  "function": "create_index",
  "line": 1234
}
```

#### Log with Context
```python
from src.structured_logging import log_with_context

log_with_context(
    logging.INFO,
    "Index created",
    context={"tenant_id": 1, "index_name": "idx_contacts_email"},
    extra_fields={"table": "contacts", "field": "email"}
)
```

---

## Benefits

### Query Timeout

1. **Prevents Hanging Queries**:
   - Long-running queries are automatically cancelled
   - Prevents resource exhaustion
   - Better system stability

2. **Configurable Per Operation**:
   - Different timeouts for different operations
   - REINDEX: Configurable (default: based on schedule)
   - VACUUM: 5 minutes default
   - Regular queries: 30 seconds default

3. **Production Safety**:
   - Prevents runaway queries
   - Protects against DoS attacks
   - Better resource management

### Structured Logging

1. **Log Aggregation Ready**:
   - JSON format works with ELK, Splunk, Datadog
   - Easy to parse and analyze
   - Better log search capabilities

2. **Structured Context**:
   - Consistent log format
   - Easy to extract fields
   - Better log analysis

3. **Production Monitoring**:
   - Integrates with log management systems
   - Better observability
   - Compliance-ready logging

---

## Files Modified

1. **`src/db.py`**:
   - Added `timeout_seconds` parameter to `get_connection()`
   - Integrated query timeout setting

2. **`src/api_server.py`**:
   - Added structured logging setup at startup

3. **`src/simulation/simulator.py`**:
   - Added structured logging setup at startup

4. **`src/auto_indexer.py`**:
   - Added structured logging setup at module level

5. **`src/maintenance.py`**:
   - Integrated query timeout for REINDEX operations

6. **`src/index_lifecycle_manager.py`**:
   - Integrated query timeout for VACUUM operations

7. **`indexpilot_config.yaml`**:
   - Added `query_timeout` configuration section
   - Added `structured_logging` configuration section
   - Added `vacuum_timeout_seconds` to lifecycle config

---

## Testing

### Test Query Timeout

```python
# Test default timeout
from src.db import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    # This should timeout after 30 seconds (default)
    cursor.execute("SELECT pg_sleep(60)")  # Will timeout
```

### Test Structured Logging

```python
# Enable in config, then check logs
# Standard format: text logs
# JSON format: structured JSON logs
```

---

## Configuration Summary

### Query Timeout

```yaml
features:
  query_timeout:
    enabled: true  # ✅ Enabled by default
    default_query_timeout_seconds: 30.0
    default_statement_timeout_seconds: 60.0

  index_lifecycle:
    vacuum_timeout_seconds: 300.0  # 5 minutes for VACUUM
```

### Structured Logging

```yaml
features:
  structured_logging:
    enabled: false  # Disabled by default (can enable when needed)
    format: "json"
    include_context: true
    include_stack_trace: false
```

---

## Conclusion

✅ **Both features are now integrated and ready to use!**

**Query Timeout**:
- ✅ Integrated into database connections
- ✅ Integrated into long-running operations (REINDEX, VACUUM)
- ✅ Configurable per operation
- ✅ Enabled by default

**Structured Logging**:
- ✅ Set up at application startup
- ✅ Works with all entry points (API, simulator, auto-indexer)
- ✅ Configurable (disabled by default, can enable when needed)
- ✅ Ready for log aggregation systems

**Both features are production-ready and can be enabled/configured as needed.**

---

**Document Created**: 08-12-2025  
**Status**: ✅ Complete  
**Integration**: Ready for use

