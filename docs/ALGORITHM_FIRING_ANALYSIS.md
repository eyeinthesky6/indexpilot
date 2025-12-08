# Algorithm Firing Analysis

**Date**: 2025-12-08  
**Status**: ⚠️ **ALGORITHMS NOT FIRING**

---

## Problem Summary

**Finding**: `algorithm_usage` table has **0 records** after comprehensive simulation.

This means:
- ❌ Algorithms are NOT being tracked
- ⚠️ Algorithms may not be firing, OR tracking is failing silently

---

## Algorithm Integration Points

### ✅ CERT (Cardinality Estimation)
**Location**: `src/auto_indexer.py::get_field_selectivity()` (line 1819)
- **Called when**: Field selectivity is calculated
- **Condition**: `validate_with_cert=True` (default)
- **Tracking**: Line 904-912
- **Issue**: Only fires if `get_field_selectivity()` is called AND selectivity calculation succeeds

### ✅ Predictive Indexing
**Location**: `src/auto_indexer.py::should_create_index()` (line 1914)
- **Called when**: Index creation decision is made
- **Condition**: Always fires (in cost-benefit analysis)
- **Tracking**: Line 530-541
- **Issue**: Only fires if `should_create_index()` is called

### ✅ XGBoost
**Location**: `src/auto_indexer.py::should_create_index()` → `query_pattern_learning.get_index_recommendation_score()`
- **Called when**: Field usage stats available
- **Condition**: Requires `table_name`, `field_name`, and usage stats
- **Tracking**: Line 781-795
- **Issue**: Only fires if usage stats exist

### ⚠️ QPG (Query Plan Guidance)
**Location**: `src/query_analyzer.py::analyze_query_plan()` and `analyze_query_plan_fast()`
- **Called when**: EXPLAIN is used
- **Condition**: Only fires when EXPLAIN is performed
- **Tracking**: Line 590-600 in `query_analyzer.py`
- **Issue**: May not fire if `USE_REAL_QUERY_PLANS=False` or queries don't trigger EXPLAIN

### ⚠️ Cortex
**Location**: `src/composite_index_detection.py::detect_composite_index_opportunities()`
- **Called when**: Composite index detection runs
- **Condition**: Only fires when composite index opportunities are detected
- **Tracking**: Line 150-160 in `composite_index_detection.py`
- **Issue**: May not fire if no composite index opportunities exist

---

## Why Algorithms May Not Fire

### 1. **Early Exit Conditions**
Many fields are skipped BEFORE algorithms are called:
- Index already exists (line 1711)
- Rate limiting (line 1751)
- Maintenance window (line 1764)
- Pattern checks (line 1736)
- Query threshold (line 1790)
- Index overhead limit (line 1804)

**Impact**: If fields are skipped early, `get_field_selectivity()` and `should_create_index()` are never called, so algorithms never fire.

### 2. **Tracking Failures**
Tracking uses `logger.debug()` for errors, which may be silent:
```python
except Exception as e:
    logger.debug(f"Could not track algorithm usage: {e}")
```

**Impact**: If tracking fails, algorithms may fire but not be recorded.

### 3. **Missing Conditions**
- **QPG**: Requires EXPLAIN to be used
- **Cortex**: Requires composite index opportunities
- **XGBoost**: Requires usage stats

---

## Verification Steps

### Step 1: Check if indexes are being created
```sql
SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE 'idx_%';
```

### Step 2: Check if algorithms are called but tracking fails
- Add logging before algorithm calls
- Check for exceptions in tracking

### Step 3: Verify algorithm execution paths
- Ensure `get_field_selectivity()` is called
- Ensure `should_create_index()` is called
- Check if early exits prevent algorithm execution

---

## Recommendations

### 1. **Add Algorithm Execution Logging**
Add explicit logging when algorithms are called:
```python
logger.info(f"[ALGORITHM] Calling {algorithm_name} for {table_name}.{field_name}")
```

### 2. **Fix Tracking Failures**
Change tracking error handling to log warnings:
```python
except Exception as e:
    logger.warning(f"Could not track algorithm usage: {e}", exc_info=True)
```

### 3. **Ensure Algorithms Fire**
- Reduce early exit conditions for testing
- Force algorithm execution in comprehensive mode
- Add algorithm execution verification

### 4. **Track Algorithm Calls Separately**
Create a separate table to track algorithm calls (not just usage):
```sql
CREATE TABLE algorithm_calls (
    id SERIAL PRIMARY KEY,
    algorithm_name TEXT,
    table_name TEXT,
    field_name TEXT,
    called_at TIMESTAMP,
    execution_time_ms FLOAT,
    success BOOLEAN,
    error_message TEXT
);
```

---

## Next Steps

1. ✅ Verify indexes are being created
2. ✅ Add algorithm execution logging
3. ✅ Fix tracking error handling
4. ✅ Ensure algorithms fire during comprehensive simulation
5. ✅ Update verification to check actual algorithm execution

