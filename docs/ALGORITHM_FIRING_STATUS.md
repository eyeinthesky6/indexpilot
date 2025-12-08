# Algorithm & Feature Firing Status

**Date**: 2025-12-08  
**Status**: Analysis of which algorithms/features fire during comprehensive simulation

---

## Expected Algorithms (11 total)

### Phase 1: Quick Wins
1. **CERT** (Cardinality Estimation Restriction Testing)
2. **QPG** (Query Plan Guidance)  
3. **Cortex** (Data Correlation Exploitation)

### Phase 2: ML Integration
4. **Predictive Indexing** (ML utility prediction)
5. **XGBoost** (Pattern Classification)

### Phase 3: Advanced Index Types
6. **PGM-Index** (Learned index)
7. **ALEX** (Adaptive learned index)
8. **RadixStringSpline** (String indexing)
9. **Fractal Tree** (Write-optimized)

### Phase 4: Specialized
10. **iDistance** (Multi-dimensional)
11. **Bx-tree** (Temporal)

---

## Integration Points

### ✅ CERT
**Location**: `src/auto_indexer.py::get_field_selectivity()`
- **Called when**: `validate_with_cert=True` (default)
- **Condition**: Always fires when calculating field selectivity
- **Tracking**: ✅ Tracked via `track_algorithm_usage()`

### ✅ Predictive Indexing
**Location**: `src/auto_indexer.py::should_create_index()`
- **Called when**: Always (in cost-benefit analysis)
- **Condition**: Always fires during index decision
- **Tracking**: ✅ Tracked via `track_algorithm_usage()`

### ✅ XGBoost
**Location**: `src/auto_indexer.py::should_create_index()` → `query_pattern_learning.get_index_recommendation_score()`
- **Called when**: Field usage stats available
- **Condition**: Requires `table_name` and `field_name` with usage stats
- **Tracking**: ✅ Tracked via `track_algorithm_usage()`

### ⚠️ QPG (Query Plan Guidance)
**Location**: `src/query_analyzer.py::analyze_query_plan()` and `analyze_query_plan_fast()`
- **Called when**: Query plan analysis is performed
- **Condition**: Only fires when EXPLAIN is used (not always used)
- **Tracking**: ⚠️ Tracked in `query_analyzer.py` but may not fire if EXPLAIN isn't used
- **Issue**: May not fire if `USE_REAL_QUERY_PLANS=False` or queries don't trigger EXPLAIN

### ⚠️ Cortex
**Location**: `src/composite_index_detection.py::detect_composite_index_opportunities()`
- **Called when**: Composite index detection runs
- **Condition**: Only fires when composite index opportunities are detected
- **Tracking**: ✅ Tracked via `track_algorithm_usage()`
- **Issue**: May not fire if no composite index opportunities exist

### ⚠️ Advanced Index Types (PGM, ALEX, RSS, Fractal Tree)
**Location**: `src/index_type_selection.py::select_optimal_index_type()`
- **Called when**: Index type selection is performed
- **Condition**: Only fires when index type selection is enabled and suitable patterns detected
- **Tracking**: ⚠️ May not be tracked separately

### ⚠️ Specialized (iDistance, Bx-tree)
**Location**: `src/index_type_selection.py` (pattern detection)
- **Called when**: Specific query patterns detected
- **Condition**: Only fires for multi-dimensional or temporal patterns
- **Tracking**: ⚠️ May not fire in standard CRM simulation

---

## Why Algorithms May Not Fire

### 1. **QPG** - Requires EXPLAIN Usage
- Only fires when `analyze_query_plan()` or `analyze_query_plan_fast()` is called
- May not fire if:
  - `USE_REAL_QUERY_PLANS=False`
  - Queries don't trigger EXPLAIN analysis
  - Fast path doesn't use QPG

### 2. **Cortex** - Requires Composite Index Opportunities
- Only fires when `detect_composite_index_opportunities()` is called
- May not fire if:
  - No composite index opportunities detected
  - Composite index detection is disabled
  - Not enough multi-field query patterns

### 3. **XGBoost** - Requires Usage Stats
- Only fires when field usage stats are available
- May not fire if:
  - No usage stats for the field
  - `query_pattern_learning` module fails
  - Model not trained

### 4. **Advanced Index Types** - Pattern-Dependent
- Only fire when specific patterns are detected
- May not fire in standard CRM simulation (no string patterns, no temporal data, etc.)

---

## Verification Results

From comprehensive simulation:
```
algorithm_usage: [OK] PASSED (0 errors, 1 warnings)
  Warnings: Some expected algorithms not found in usage: 
    ['predictive_indexing', 'cert', 'qpg', 'cortex', 'xgboost_classifier']
```

**This indicates algorithms are NOT being tracked properly or NOT firing.**

---

## Recommendations

### 1. **Ensure Algorithm Tracking Works**
- Verify `algorithm_usage` table is populated
- Check if `track_algorithm_usage()` is being called
- Verify tracking happens even when algorithms return early

### 2. **Force Algorithm Execution**
- Ensure QPG fires by using EXPLAIN in all index decisions
- Ensure Cortex fires by checking composite indexes
- Ensure XGBoost fires by providing usage stats

### 3. **Add Algorithm Execution Logging**
- Log when each algorithm is called
- Log when algorithms return early (and why)
- Track algorithm execution separately from usage tracking

### 4. **Test Algorithm Firing**
- Create test scenarios that trigger each algorithm
- Verify algorithms fire in comprehensive mode
- Document conditions required for each algorithm

---

## Next Steps

1. ✅ Check if `algorithm_usage` table exists and is populated
2. ✅ Verify `track_algorithm_usage()` is being called
3. ✅ Add logging to see when algorithms are called
4. ✅ Ensure all algorithms fire during comprehensive simulation
5. ✅ Update verification to check actual algorithm execution, not just tracking

