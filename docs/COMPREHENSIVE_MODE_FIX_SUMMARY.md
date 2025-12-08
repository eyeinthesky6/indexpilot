# Comprehensive Mode Fix Summary

**Date**: 2025-12-08  
**Status**: In Progress

---

## Issue

Comprehensive mode was only running **ONE scenario** (the one specified with `--scenario`), but it should run **ALL scenarios** (small, medium, large, stress-test) to test all features across different database sizes.

---

## Current Behavior

```bash
python -m src.simulation.simulator comprehensive --scenario small
# Only runs small scenario with all features
```

## Expected Behavior

```bash
python -m src.simulation.simulator comprehensive
# Runs ALL scenarios (small, medium, large, stress-test)
# Each scenario tests ALL features:
#   - Baseline simulation
#   - Auto-index simulation  
#   - Schema mutations
#   - A/B testing
#   - Predictive maintenance
#   - Feature verification
```

---

## Implementation Plan

1. **Extract feature testing into helper function** - `_run_comprehensive_features_for_scenario()`
2. **Loop through all scenarios** - Run helper for each scenario
3. **Aggregate results** - Collect results from all scenarios
4. **Save combined results** - One JSON file with all scenario results

---

## Schema Auto-Discovery

**Created**: `src/schema/discovery.py`

Functions:
- `discover_schema_files()` - Find schema config files in codebase
- `load_discovered_schema()` - Load a discovered schema file
- `auto_discover_and_load_schema()` - Auto-discover and load (with preferred name support)

**Usage**:
```python
from src.schema.discovery import auto_discover_and_load_schema

# Auto-discover and load first schema file found
schema = auto_discover_and_load_schema()

# Or specify preferred name
schema = auto_discover_and_load_schema("stock_market")
```

---

## Hardcoded CRM References

### ✅ Fixed (Production Code)
- `src/index_lifecycle_manager.py` - Now discovers tenant tables dynamically

### ⚠️ OK (Simulation/Testing Only)
- `src/simulation/simulator.py` - Hardcoded CRM queries (for testing)
- `src/simulation/simulation_verification.py` - Test queries use CRM tables
- These are **testing tools**, not production code

### 📝 Note
Simulation code can have hardcoded references because it's a **testing harness**, not production code. The core system (auto-indexer, query stats, etc.) is fully schema-agnostic.

---

## Next Steps

1. Complete comprehensive mode refactor (extract helper function)
2. Test comprehensive mode runs all scenarios
3. Update documentation

