# PostgreSQL Shared Memory Limit Analysis

**Date**: 08-12-2025  
**Issue**: PostgreSQL shared memory errors during VACUUM ANALYZE operations

---

## Error Message

```
Database error (DiskFull): could not resize shared memory segment "/PostgreSQL.1997143920" to 67145216 bytes: No space left on device
```

---

## Understanding the Issue

### Windows vs Linux Shared Memory

**On Windows (Your System):**
- PostgreSQL uses **named shared memory segments** (not System V IPC like Linux)
- Each segment has a maximum size limit
- Windows has a default limit of **64MB per shared memory segment**
- Error occurs when PostgreSQL tries to allocate more than this limit

**On Linux:**
- Uses System V IPC shared memory
- Controlled by `SHMMAX` and `SHMALL` kernel parameters
- Typically much higher limits (can be GBs)

### Current System Resources

From system check:
- **Total RAM**: 31.77 GB
- **Available RAM**: 20.18 GB
- **Used RAM**: 11.59 GB (36.5%)

**Hardware is NOT the limit** - you have plenty of RAM available.

---

## Root Cause

The error occurs because:

1. **PostgreSQL Docker Container** (postgres:15-alpine) is running on Windows
2. **Windows shared memory limit** is ~64MB per segment
3. **VACUUM ANALYZE** operations require temporary shared memory
4. When multiple VACUUM operations run concurrently, they try to allocate segments that exceed the Windows limit

### Why This Happens

- **Multiple tenants** being processed simultaneously
- Each **VACUUM ANALYZE** operation needs shared memory
- **Windows limit** is per-segment, not total system memory
- Docker on Windows has additional constraints

---

## Current PostgreSQL Configuration

**Docker Setup:**
- Image: `postgres:15-alpine`
- No explicit shared memory configuration
- Uses PostgreSQL defaults

**PostgreSQL Defaults (approximate):**
- `shared_buffers`: ~128MB (default for small instances)
- `work_mem`: 4MB per operation
- `maintenance_work_mem`: 64MB per operation
- `max_connections`: 100 (default)

**VACUUM ANALYZE Memory Usage:**
- Each VACUUM ANALYZE can use up to `maintenance_work_mem` (64MB)
- Multiple concurrent operations = multiple 64MB segments
- Windows limit: 64MB per segment → **conflict!**

---

## Solutions

### Option 1: Reduce Concurrent VACUUM Operations (Recommended)

**Current Code**: Already handles this gracefully
- Error is caught and logged as warning
- Operation is skipped, not failed
- System continues to work

**Improvement**: Add throttling to prevent too many concurrent VACUUM operations

```python
# In src/index_lifecycle_manager.py
# Limit concurrent VACUUM operations to 1-2 at a time
_vacuum_semaphore = threading.Semaphore(2)  # Max 2 concurrent

with _vacuum_semaphore:
    # Run VACUUM ANALYZE
```

### Option 2: Reduce PostgreSQL Memory Settings

**For Docker on Windows**, reduce memory settings:

```yaml
# docker-compose.yml
services:
  postgres:
    environment:
      POSTGRES_INITDB_ARGS: "-E UTF8"
    command: >
      postgres
      -c shared_buffers=64MB
      -c maintenance_work_mem=32MB
      -c work_mem=2MB
      -c max_connections=50
```

**Or create `postgresql.conf` override:**

```conf
shared_buffers = 64MB
maintenance_work_mem = 32MB
work_mem = 2MB
max_connections = 50
```

### Option 3: Increase Windows Shared Memory (Advanced)

**For Windows Host:**
- Edit registry: `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\SubSystems\Windows`
- Modify `SharedSection` parameter
- **Warning**: Requires system restart and can affect other applications

**Not recommended** for Docker setup - better to configure PostgreSQL instead.

### Option 4: Use Linux Container (If Possible)

**If running on WSL2 or Linux:**
- Linux has much higher shared memory limits
- Can configure `SHMMAX` and `SHMALL` via `sysctl`
- More flexible memory management

---

## Recommended Fix

### Immediate: Add VACUUM Throttling

Limit concurrent VACUUM operations to prevent hitting Windows limits:

```python
# src/index_lifecycle_manager.py
import threading

# Limit concurrent VACUUM operations (Windows shared memory limit)
_vacuum_semaphore = threading.Semaphore(1)  # Only 1 at a time on Windows

def perform_vacuum_analyze_for_indexes(...):
    # ...
    for table_name in tables_to_analyze:
        with _vacuum_semaphore:  # Serialize VACUUM operations
            try:
                # VACUUM ANALYZE code
```

### Long-term: Configure PostgreSQL for Windows/Docker

Add to `docker-compose.yml`:

```yaml
services:
  postgres:
    command: >
      postgres
      -c shared_buffers=64MB
      -c maintenance_work_mem=32MB
      -c work_mem=2MB
```

---

## Current Status

✅ **Error Handling**: Already implemented
- Errors are caught and logged as warnings
- Operations are skipped gracefully
- System continues to function

⚠️ **Performance Impact**: 
- Some VACUUM ANALYZE operations fail
- Statistics may not be refreshed for all tables
- No data corruption, just maintenance operations skipped

---

## Verification

To check current PostgreSQL settings:

```sql
SHOW shared_buffers;
SHOW max_connections;
SHOW maintenance_work_mem;
SHOW work_mem;
```

To check system memory:

```python
import psutil
mem = psutil.virtual_memory()
print(f"Available: {mem.available / (1024**3):.2f} GB")
```

---

## Conclusion

**This is NOT a hardware limit** - you have 31GB RAM available.

**This IS a Windows/Docker configuration limit** - Windows restricts shared memory segments to ~64MB each.

**Solution**: 
1. ✅ Error handling already in place (graceful degradation)
2. 🔧 Add VACUUM throttling to prevent concurrent operations
3. 🔧 Reduce PostgreSQL memory settings for Windows/Docker environment

The system is working correctly - errors are handled gracefully and don't cause failures.

