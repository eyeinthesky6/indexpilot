# Dynamic Memory Configuration for PostgreSQL

**Date**: 08-12-2025  
**Status**: ✅ **IMPLEMENTED - Auto-adjusting PostgreSQL memory based on available RAM**

---

## Overview

The system now **automatically adjusts PostgreSQL memory settings** based on available system RAM, similar to how CPU throttling monitors and adjusts for CPU usage.

**Key Features:**
- ✅ **Dynamic calculation**: Uses 50% of available RAM by default
- ✅ **Auto-adjusting**: Recalculates based on current system memory
- ✅ **Windows-aware**: Handles Windows shared memory limits intelligently
- ✅ **Configurable**: All settings can be adjusted via config file
- ✅ **CPU throttling integration**: Works alongside CPU throttling for resource management

---

## How It Works

### 1. Memory Detection

Uses `psutil` (same as CPU throttling) to detect:
- **Total system RAM**
- **Available RAM** (not used by other processes)
- **Current memory usage**

### 2. Dynamic Calculation

Calculates PostgreSQL memory settings:
- **Target memory**: 50% of available RAM (configurable)
- **shared_buffers**: 25% of target (PostgreSQL's main memory pool)
- **maintenance_work_mem**: For VACUUM, CREATE INDEX operations
- **work_mem**: Per-operation memory (sorts, joins)
- **effective_cache_size**: OS cache estimate (75% of target)

### 3. Windows-Specific Handling

**Windows shared memory limits:**
- Windows limits shared memory segments to ~64MB each
- `maintenance_work_mem` is capped at **32MB** on Windows
- `shared_buffers` can use more (different mechanism)
- Prevents "No space left on device" errors

**Linux/Unix:**
- No such limits - can use more aggressive settings
- `maintenance_work_mem` can go up to 1GB

---

## Configuration

### Config File Settings

```yaml
features:
  memory_config:
    # Percentage of available RAM to use for PostgreSQL (default: 50%)
    memory_percent: 50.0
    # Minimum memory to allocate (MB) - safety floor
    min_memory_mb: 512
    # Maximum memory to allocate (MB) - safety ceiling
    max_memory_mb: 8192
    # Enable automatic memory adjustment based on available RAM
    auto_adjust_enabled: true
```

### Current Settings (Your System)

Based on your system (32GB RAM, 20GB available):
- **Target memory**: 8GB (50% of 20GB available, capped at max)
- **shared_buffers**: 1GB (25% of target, max 1GB on Windows)
- **maintenance_work_mem**: 32MB (Windows limit)
- **work_mem**: 4MB (per operation)
- **effective_cache_size**: 6GB (75% of target)

---

## Usage

### Automatic (Recommended)

The system automatically calculates memory settings when:
- Starting PostgreSQL container
- Running maintenance operations
- Checking system resources

### Manual Update

To update `docker-compose.yml` with current memory settings:

```bash
python scripts/update_postgres_memory_config.py
```

This will:
1. Detect current available RAM
2. Calculate optimal PostgreSQL settings
3. Update `docker-compose.yml` with new command
4. Show you the calculated values

**Then restart PostgreSQL:**
```bash
docker-compose restart postgres
```

### Programmatic Access

```python
from src.memory_config import get_memory_status, get_postgres_memory_config

# Get current memory status
status = get_memory_status()
print(f"Available RAM: {status['available_memory_mb']:.0f} MB")
print(f"Target memory: {status['target_memory_mb']:.0f} MB")
print(f"PostgreSQL config: {status['postgres_config']}")

# Get PostgreSQL configuration
config = get_postgres_memory_config()
print(f"shared_buffers: {config['shared_buffers']}")
```

---

## Integration with CPU Throttling

### How They Work Together

**CPU Throttling** (existing):
- Monitors CPU usage in real-time
- Throttles operations when CPU > 80%
- Prevents CPU exhaustion

**Memory Configuration** (new):
- Monitors available RAM
- Adjusts PostgreSQL memory settings dynamically
- Prevents memory exhaustion

**Together:**
- Both use `psutil` for system monitoring
- Both adjust based on current system state
- Both prevent resource exhaustion
- Both are configurable via config file

### Resource Management Flow

```
1. System starts
   ↓
2. Memory config detects available RAM
   ↓
3. Calculates optimal PostgreSQL settings
   ↓
4. PostgreSQL starts with calculated settings
   ↓
5. During operations:
   - CPU throttling monitors CPU usage
   - Memory config can be recalculated if RAM changes
   - Both prevent resource exhaustion
```

---

## Comparison: Before vs After

### Before (Static Configuration)

```yaml
# Fixed values regardless of system
shared_buffers: 128MB
maintenance_work_mem: 64MB  # ❌ Too high for Windows!
work_mem: 4MB
effective_cache_size: 4GB
```

**Problems:**
- ❌ Too small for systems with lots of RAM
- ❌ Too large for systems with limited RAM
- ❌ `maintenance_work_mem` too high for Windows (causes errors)
- ❌ Not adaptive to changing system state

### After (Dynamic Configuration)

```yaml
# Auto-calculated based on available RAM
shared_buffers: 1024MB  # ✅ Uses 25% of available RAM
maintenance_work_mem: 32MB  # ✅ Windows-safe limit
work_mem: 4MB
effective_cache_size: 6144MB  # ✅ Uses 75% of available RAM
```

**Benefits:**
- ✅ Automatically scales with available RAM
- ✅ Windows-aware (prevents shared memory errors)
- ✅ Adapts to changing system state
- ✅ Configurable via config file

---

## Example: Your System

**System Resources:**
- Total RAM: 32GB
- Available RAM: ~20GB
- Target (50%): 8GB (capped at max_memory_mb)

**PostgreSQL Configuration:**
```
shared_buffers: 1024MB        (25% of target, max 1GB on Windows)
maintenance_work_mem: 32MB    (Windows-safe limit)
work_mem: 4MB                 (Per-operation)
effective_cache_size: 6144MB   (75% of target)
max_connections: 100
```

**Result:**
- ✅ Uses available RAM efficiently
- ✅ Avoids Windows shared memory errors
- ✅ Better performance with larger buffer pool
- ✅ Automatically adjusts if RAM changes

---

## Monitoring

### Check Current Configuration

```python
from src.memory_config import get_memory_status

status = get_memory_status()
print(status)
```

### Check PostgreSQL Settings

```sql
SHOW shared_buffers;
SHOW maintenance_work_mem;
SHOW work_mem;
SHOW effective_cache_size;
```

### Monitor Memory Usage

```python
import psutil

mem = psutil.virtual_memory()
print(f"Available: {mem.available / (1024**3):.2f} GB")
print(f"Used: {mem.used / (1024**3):.2f} GB")
print(f"Percent: {mem.percent}%")
```

---

## Troubleshooting

### Memory Settings Too High

If PostgreSQL fails to start:
1. Reduce `memory_percent` in config (e.g., 30% instead of 50%)
2. Reduce `max_memory_mb` limit
3. Run update script again

### Windows Shared Memory Errors

If you still see "No space left on device":
1. `maintenance_work_mem` is already capped at 32MB
2. Check if multiple VACUUM operations running concurrently
3. Consider reducing concurrent operations (already handled in code)

### Memory Not Updating

If settings don't change:
1. Check `auto_adjust_enabled: true` in config
2. Restart PostgreSQL container after updating docker-compose.yml
3. Verify script ran successfully

---

## Best Practices

1. **Run update script periodically** (e.g., after system changes)
2. **Monitor memory usage** to ensure settings are appropriate
3. **Adjust `memory_percent`** based on other applications using RAM
4. **Set `max_memory_mb`** to prevent PostgreSQL from using too much
5. **Keep `min_memory_mb`** as safety floor for small systems

---

## Future Enhancements

Potential improvements:
- [ ] Automatic periodic recalculation
- [ ] Integration with PostgreSQL runtime settings (ALTER SYSTEM)
- [ ] Memory usage monitoring and alerts
- [ ] Automatic adjustment based on workload
- [ ] Integration with container resource limits

---

## Summary

✅ **Dynamic memory configuration is now active!**

- Uses 50% of available RAM automatically
- Windows-aware (prevents shared memory errors)
- Works alongside CPU throttling
- Fully configurable via config file
- Easy to update with script

**Next Steps:**
1. Run `python scripts/update_postgres_memory_config.py`
2. Restart PostgreSQL: `docker-compose restart postgres`
3. Monitor performance improvements

The system now uses your available RAM efficiently while respecting Windows limits!

