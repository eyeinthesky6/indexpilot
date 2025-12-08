# Simulation Run Log - 08-12-2025

**Status**: In Progress  
**Started**: 2025-12-08

---

## Completed Simulations

### ✅ 1. baseline - small (CRM)
- **Status**: SUCCESS
- **Duration**: ~20 seconds
- **Queries**: 1,280
- **Avg Latency**: 2.72ms
- **P95**: 7.95ms
- **P99**: 12.19ms
- **Errors**: None (expected warnings only)
- **Report**: `docs/audit/toolreports/results_baseline.json`

### ✅ 2. autoindex - small (CRM)
- **Status**: SUCCESS
- **Duration**: ~1.5 minutes
- **Queries**: 2,000
- **Avg Latency**: 2.66ms
- **P95**: 7.47ms
- **P99**: 12.77ms
- **Algorithms**: 35 calls (constraint_optimizer: 10, predictive_indexing: 20, cert: 5)
- **Indexes Created**: 0 (all skipped - already exist or pattern checks failed)
- **Errors**: None (expected warnings only)
- **Report**: `docs/audit/toolreports/results_with_auto_index.json`

### ✅ 3. scaled - small (CRM)
- **Status**: SUCCESS
- **Duration**: ~1.5 minutes
- **Baseline Queries**: 1,280
- **Autoindex Queries**: 2,000
- **Algorithms**: 42 calls (constraint_optimizer: 12, predictive_indexing: 24, cert: 6)
- **Errors**: 
  - Some tuple index errors during EXPLAIN parsing (non-fatal, handled)
  - Foreign key suggestions working (4 found)
- **Report**: `docs/audit/toolreports/results_with_auto_index.json` (updated)

### ✅ 4. comprehensive - small (CRM)
- **Status**: SUCCESS
- **Duration**: ~3 minutes
- **Features Tested**: All (mutation_log, expression_profiles, safeguards, bypass, health, schema_evolution, query_interception, algorithms, A/B testing, predictive_maintenance)
- **Verification**: PASSED (0 errors, 2 warnings)
- **Algorithms**: 42 calls tracked
- **Errors**: 
  - Tuple index errors in EXPLAIN parsing (non-fatal)
  - A/B testing warning (non-critical)
- **Report**: `docs/audit/toolreports/results_comprehensive.json`

### ✅ 5. baseline - medium (CRM)
- **Status**: SUCCESS
- **Duration**: ~19 minutes
- **Queries**: 27,772
- **Avg Latency**: 3.93ms
- **P95**: 13.72ms
- **P99**: 26.00ms
- **Errors**: None (expected shutdown warnings only)
- **Report**: `docs/audit/toolreports/results_baseline.json` (updated)

---

## Remaining Simulations

- [ ] autoindex - medium (CRM)
- [ ] scaled - medium (CRM)
- [ ] comprehensive - medium (CRM)
- [ ] real-data - small equivalent (Backtesting)
- [ ] real-data - medium equivalent (Backtesting)

---

## Errors Found (To Fix)

### 1. Tuple Index Errors in EXPLAIN Parsing
- **Location**: `src/query_analyzer.py`
- **Error**: `Database error (IndexError): tuple index out of range`
- **Impact**: Non-fatal, EXPLAIN fails for some queries but simulation continues
- **Status**: Needs investigation - may be RealDictCursor issue with EXPLAIN queries

### 2. Cursor Already Closed (Expected)
- **Location**: `src/statistics_refresh.py`
- **Error**: `cursor already closed`
- **Impact**: None - happens during graceful shutdown
- **Status**: Expected behavior

---

## Notes

- All simulations generating reports successfully
- Algorithms firing correctly
- System handling errors gracefully
- Shutdown errors are expected and non-critical

