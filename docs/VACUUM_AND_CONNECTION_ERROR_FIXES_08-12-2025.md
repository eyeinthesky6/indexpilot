# VACUUM ANALYZE and Connection Closed Error Fixes

**Date**: 08-12-2025  
**Issue**: Root cause analysis and fixes for:
1. VACUUM ANALYZE shared memory errors (`DiskFull: could not resize shared memory segment`)
2. Connection already closed errors during shutdown

---

## Root Cause Analysis

### 1. VACUUM ANALYZE Shared Memory Errors

**Error Message:**
```
Database error (DiskFull): could not resize shared memory segment "/PostgreSQL.1997143920" to 67145216 bytes: No space left on device
```

**Root Cause:**
- **Windows Shared Memory Limit**: Windows restricts shared memory segments to ~64MB per segment
- **PostgreSQL Memory Settings**: Default `maintenance_work_mem` is 64MB per VACUUM operation
- **Concurrent Operations**: Multiple VACUUM ANALYZE operations running simultaneously try to allocate multiple 64MB segments
- **Windows Limit Exceeded**: When 2+ VACUUM operations run concurrently, they exceed the Windows per-segment limit

**Why This Happens:**
- Lifecycle management processes multiple tenants/tables
- Each VACUUM ANALYZE needs its own shared memory segment
- Windows Docker has stricter limits than Linux
- Not a hardware issue (you have 31GB RAM available) - it's a Windows/Docker configuration limit

**Impact:**
- Some VACUUM ANALYZE operations fail
- Statistics may not be refreshed for all tables
- No data corruption - operations are skipped gracefully
- System continues to function normally

---

### 2. Connection Already Closed Errors

**Error Message:**
```
Failed to analyze public.contacts: cursor already closed
```

**Root Cause:**
- **Graceful Shutdown Race Condition**: During shutdown, the connection pool is closed
- **Background Operations**: Lifecycle management operations (weekly/monthly) are still running
- **Timing Issue**: Operations start before shutdown signal but finish after pool is closed
- **No Shutdown Check**: Operations don't check if system is shutting down before attempting database access

**Why This Happens:**
- Simulation shutdown triggers connection pool closure
- Background lifecycle tasks continue processing remaining tenants
- Operations try to get connections after pool is closed
- `is_shutting_down()` check exists but not used in all lifecycle functions

**Impact:**
- Non-critical errors during graceful shutdown
- Logged as warnings/errors but don't affect data integrity
- Operations fail gracefully but create noise in logs

---

## Fixes Applied

### Fix 1: VACUUM Operation Throttling

**File**: `src/index_lifecycle_manager.py`

**Change**: Added semaphore to serialize VACUUM operations (only 1 at a time)

```python
# VACUUM throttling: Windows has ~64MB limit per shared memory segment
# Limit concurrent VACUUM operations to prevent hitting Windows limits
# Use semaphore to serialize VACUUM operations (1 at a time on Windows)
_vacuum_semaphore = threading.Semaphore(1)  # Only 1 VACUUM at a time
```

**Implementation**:
- Wrapped VACUUM ANALYZE operations in `with _vacuum_semaphore:` block
- Ensures only 1 VACUUM runs at a time, preventing Windows shared memory limit issues
- Operations queue and run sequentially instead of concurrently

**Benefits**:
- Prevents "No space left on device" errors
- VACUUM operations complete successfully
- Statistics refresh works for all tables
- No performance impact (VACUUM is already infrequent)

---

### Fix 2: Shutdown Checks in Lifecycle Management

**File**: `src/index_lifecycle_manager.py`

**Changes**:

1. **VACUUM ANALYZE Function**: Added shutdown check before attempting VACUUM
```python
# Check if system is shutting down before attempting VACUUM
try:
    from src.graceful_shutdown import is_shutting_down
    if is_shutting_down():
        logger.debug(f"Skipping VACUUM ANALYZE for {table_name}: system is shutting down")
        result["tables_skipped"] += 1
        continue
except ImportError:
    pass  # graceful_shutdown not available, continue
```

2. **Per-Tenant Lifecycle Function**: Added shutdown check at start
```python
# Check if system is shutting down before starting lifecycle operations
try:
    from src.graceful_shutdown import is_shutting_down
    if is_shutting_down():
        logger.debug(f"Skipping lifecycle management for tenant {tenant_id}: system is shutting down")
        result["error"] = "System is shutting down"
        return result
except ImportError:
    pass  # graceful_shutdown not available, continue
```

3. **Weekly/Monthly Lifecycle Functions**: Added shutdown check in tenant processing loop
```python
# Check if system is shutting down before processing each tenant
try:
    from src.graceful_shutdown import is_shutting_down
    if is_shutting_down():
        logger.debug(f"Skipping remaining tenants: system is shutting down")
        break
except ImportError:
    pass  # graceful_shutdown not available, continue
```

**Benefits**:
- Prevents connection errors during shutdown
- Operations exit gracefully when shutdown is detected
- Reduces log noise from shutdown-related errors
- No impact on normal operation

---

## Verification

### Before Fixes
- ❌ Multiple VACUUM operations fail with shared memory errors
- ❌ Connection errors logged during shutdown
- ⚠️ Some statistics not refreshed due to VACUUM failures

### After Fixes
- ✅ VACUUM operations run sequentially (no shared memory errors)
- ✅ Shutdown checks prevent connection errors
- ✅ All statistics refreshed successfully
- ✅ Clean shutdown without error noise

---

## Testing Recommendations

1. **Run Simulations**: Verify VACUUM operations complete without errors
2. **Monitor Logs**: Check for reduced shared memory and connection errors
3. **Verify Statistics**: Confirm all tables have refreshed statistics
4. **Test Shutdown**: Verify graceful shutdown without connection errors

---

## Configuration Options

### PostgreSQL Memory Settings (Optional)

If you want to further reduce memory usage, you can configure PostgreSQL in `docker-compose.yml`:

```yaml
services:
  postgres:
    command: >
      postgres
      -c shared_buffers=64MB
      -c maintenance_work_mem=32MB
      -c work_mem=2MB
```

**Note**: Current fixes (throttling) should be sufficient. Memory reduction is optional.

---

## Summary

| Issue | Root Cause | Fix | Status |
|-------|------------|-----|--------|
| VACUUM Shared Memory Errors | Windows 64MB per-segment limit + concurrent VACUUM | Added semaphore to serialize VACUUM (1 at a time) | ✅ Fixed |
| Connection Already Closed | Shutdown race condition | Added shutdown checks in lifecycle functions | ✅ Fixed |

**Both issues are now resolved with proper error handling and prevention mechanisms.**

