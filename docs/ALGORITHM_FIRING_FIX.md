# Algorithm Firing Investigation & Fix

**Date**: 08-12-2025  
**Status**: ✅ **LOGGING ADDED, TEST MODE IMPLEMENTED**

---

## Problem Summary

Algorithms (CERT, Predictive Indexing, XGBoost) were not firing during simulations because fields were being skipped before algorithm execution due to early exit conditions.

### Root Cause

Fields are evaluated through multiple early exit checks before algorithms are called:

1. **Index already exists** (line 1723)
2. **Write performance limits** (line 1735)
3. **Pattern check fails** (line 1748)
4. **Rate limiting** (line 1763)
5. **Maintenance window** (line 1776)
6. **Query threshold** (line 1802) ⚠️ **Most common skip reason**
7. **Index overhead limit** (line 1816)

**Algorithms are only called AFTER all these checks pass:**
- `get_field_selectivity()` → Calls CERT (line 1831)
- `should_create_index()` → Calls Predictive Indexing & XGBoost (line 1926)

---

## Changes Made

### 1. ✅ Added Detailed Skip Logging

Added `[SKIP]` INFO-level logging for each early exit condition to track why fields are being skipped:

```python
logger.info(f"[SKIP] {table_name}.{field_name}: {reason} (queries: {total_queries:.0f})")
```

**Skip reasons logged:**
- `already_exists` - Index already exists
- `write_performance_limit` - Can't create index due to write performance
- `pattern_check_failed` - Pattern detection failed (spike, not sustained)
- `rate_limit_exceeded` - Rate limiting active
- `outside_maintenance_window` - Outside maintenance window
- `below_size_based_threshold` - Query count below threshold
- `index_overhead_limit_exceeded` - Too many indexes on table

### 2. ✅ Added Algorithm Execution Logging

Added logging to confirm when algorithms are reached:

```python
# Before algorithm calls
logger.info(f"[ALGORITHM] Field {table_name}.{field_name} passed all early checks, calling algorithms")
logger.info(f"[ALGORITHM] Calling should_create_index() for {table_name}.{field_name}")
```

**Algorithm calls logged:**
- `[ALGORITHM] Calling CERT for {table}.{field}` (in `get_field_selectivity()`)
- `[ALGORITHM] Calling Predictive Indexing for {table}.{field}` (in `should_create_index()`)

### 3. ✅ Added Test Mode for Algorithm Testing

Added configuration option `features.auto_indexer.algorithm_test_mode` to reduce thresholds for testing:

**How to enable:**

Edit `indexpilot_config.yaml`:
```yaml
features:
  auto_indexer:
    algorithm_test_mode: true
    algorithm_test_threshold_reduction: 0.1  # 10x reduction (default)
```

Then run simulation:
```bash
python -m src.simulation.simulator baseline --scenario small
```

**What it does:**
- Reduces query thresholds by configurable factor (default: **10x**, e.g., 100 → 10, 1000 → 100)
- Forces more fields to pass early exit checks
- Allows algorithms to execute for testing purposes
- Logs: `[TEST_MODE] Algorithm test mode enabled - thresholds reduced by {factor}x`

**Configuration options:**
- `algorithm_test_mode`: `true`/`false` - Enable/disable test mode
- `algorithm_test_threshold_reduction`: `0.1` (default) = 10x reduction, `0.2` = 5x reduction, etc.

**Note:** Test mode is for testing only. Do not use in production.

---

## How to Investigate Skip Reasons

### Step 1: Run Simulation with Logging

```bash
# Normal mode (see actual skip reasons)
python -m src.simulation.simulator baseline --scenario small

# Test mode (force algorithm execution)
# First, edit indexpilot_config.yaml and set:
#   features.auto_indexer.algorithm_test_mode: true
python -m src.simulation.simulator baseline --scenario small
```

### Step 2: Check Logs for Skip Reasons

Look for `[SKIP]` and `[ALGORITHM]` log entries:

```bash
# Filter skip reasons
grep "\[SKIP\]" logs/simulation.log | head -20

# Filter algorithm calls
grep "\[ALGORITHM\]" logs/simulation.log | head -20
```

### Step 3: Analyze Skip Patterns

Common skip reasons in simulations:
- **`below_size_based_threshold`** - Most common. Fields don't have enough queries.
- **`pattern_check_failed`** - Query pattern is a spike, not sustained.
- **`already_exists`** - Index already created in previous run.

---

## Expected Behavior

### Normal Mode (Production)
- Fields must meet all thresholds
- Algorithms only fire for fields that pass all checks
- Conservative indexing (fewer indexes created)
- `algorithm_test_mode: false` (default)

### Test Mode (Testing Only)
- Thresholds reduced by configurable factor (default: 10x)
- More fields pass early checks
- Algorithms fire more frequently
- Useful for verifying algorithm integration
- Configure via `features.auto_indexer.algorithm_test_mode: true`

---

## Next Steps

1. **Run test simulation** with `INDEXPILOT_ALGORITHM_TEST_MODE=1` to verify algorithms fire
2. **Check logs** for `[ALGORITHM]` entries to confirm algorithm execution
3. **Review skip reasons** to understand why fields are skipped in normal mode
4. **Adjust thresholds** if needed based on actual workload patterns

---

## Files Modified

- `src/auto_indexer.py`:
  - Added skip reason logging (lines 1723-1825)
  - Added algorithm execution logging (lines 1827-1930)
  - Added test mode support via config (lines 1597-1606, 1833-1845)
- `src/config_loader.py`:
  - Added `algorithm_test_mode` and `algorithm_test_threshold_reduction` defaults
- `indexpilot_config.yaml`:
  - Added test mode configuration options
- `indexpilot_config.yaml.example`:
  - Added test mode configuration options (both auto_indexer sections)

---

## Verification

To verify algorithms are firing:

```bash
# 1. Enable test mode in indexpilot_config.yaml:
#    features.auto_indexer.algorithm_test_mode: true

# 2. Run simulation
python -m src.simulation.simulator baseline --scenario small

# 3. Check for algorithm logs
grep "\[ALGORITHM\]" logs/simulation.log

# 4. Check algorithm_usage table
psql -d indexpilot -c "SELECT COUNT(*) FROM algorithm_usage;"
psql -d indexpilot -c "SELECT algorithm_name, COUNT(*) FROM algorithm_usage GROUP BY algorithm_name;"
```

Expected output:
- `[ALGORITHM]` log entries present
- `algorithm_usage` table has records
- Multiple algorithms tracked (CERT, predictive_indexing, etc.)

