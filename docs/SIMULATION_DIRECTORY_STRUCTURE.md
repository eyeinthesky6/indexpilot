# Simulation Directory Structure

**Date**: 08-12-2025  
**Purpose**: Document the simulation module organization for easy removal in production

---

## Overview

All simulation-related code has been moved to `src/simulation/` directory to make it easy to identify and remove simulation code for production deployments.

---

## Directory Structure

```
src/simulation/
├── __init__.py                    # Module initialization
├── simulator.py                   # Main simulation harness
├── stock_simulator.py              # Stock market data simulation
├── simulation_verification.py      # Feature verification during simulation
├── simulation_enhancements.py     # Enhanced simulation patterns
└── advanced_simulation.py          # Advanced patterns (e-commerce, analytics, chaos)
```

---

## Files in Simulation Directory

### Core Simulation Files

1. **`simulator.py`** - Main simulation harness
   - Entry point: `python -m src.simulation.simulator [mode]`
   - Modes: `baseline`, `autoindex`, `scaled`, `comprehensive`, `real-data`
   - Generates test workloads and benchmarks IndexPilot

2. **`stock_simulator.py`** - Stock market data simulation
   - Real-data mode query patterns
   - Time-range, aggregation, filter, comparison queries
   - Used by `real-data` simulation mode

3. **`simulation_verification.py`** - Feature verification
   - Verifies all IndexPilot features during comprehensive simulation
   - Tests mutation log, expression profiles, safeguards, etc.
   - Used by `comprehensive` simulation mode

4. **`simulation_enhancements.py`** - Enhanced patterns
   - Data skew simulation (80/20 rule)
   - Tenant diversity patterns
   - Realistic data distributions

5. **`advanced_simulation.py`** - Advanced patterns
   - E-commerce query patterns
   - Analytics query patterns
   - Chaos engineering scenarios

---

## Production Removal

### For Production Deployments

To remove simulation code for production:

1. **Delete simulation directory**:
   ```bash
   rm -rf src/simulation/
   ```

2. **Remove simulation-related scripts** (optional):
   ```bash
   rm run_simulations.py
   rm run-simulation.bat
   rm test_small_sim.py
   ```

3. **Update imports** (if any remain):
   - Search for `from src.simulation` or `import src.simulation`
   - Remove or comment out these imports

### What Stays in Production

The following files are **NOT** simulation-only and should remain:

- `src/stock_data_loader.py` - Can be used for loading real data
- `src/stock_genome.py` - Genome catalog bootstrap (not simulation-specific)
- `schema_config_stock_market.yaml` - Schema configuration (not simulation-specific)

---

## Integration Points

### Files That Import Simulation Code

1. **`run_simulations.py`** - Simulation runner script
2. **`run-simulation.bat`** - Windows batch script
3. **`test_small_sim.py`** - Quick simulation test
4. **`tests/test_simulator.py`** - Simulator unit tests
5. **`Makefile`** - Make targets for simulations
6. **`run.bat`** - Windows run script with simulation commands

### Core IndexPilot Code

**No core IndexPilot code imports simulation modules.** The simulation code only imports from core modules (e.g., `src.auto_indexer`, `src.db`, `src.stats`), not the other way around.

This means:
- ✅ Safe to remove `src/simulation/` in production
- ✅ No breaking changes to core functionality
- ✅ Simulation is completely optional

---

## Updated References

All references have been updated to use the new path:

### Command-Line Usage

**Before**:
```bash
python -m src.simulator baseline
```

**After**:
```bash
python -m src.simulation.simulator baseline
```

### Python Imports

**Before**:
```python
from src.simulator import create_tenant
from src.advanced_simulation import generate_ecommerce_patterns
```

**After**:
```python
from src.simulation.simulator import create_tenant
from src.simulation.advanced_simulation import generate_ecommerce_patterns
```

---

## Benefits

1. **Clear Separation**: Simulation code is clearly separated from production code
2. **Easy Removal**: Can delete entire `src/simulation/` directory for production
3. **No Dependencies**: Core code doesn't depend on simulation code
4. **Better Organization**: Related simulation files are grouped together
5. **Maintainability**: Easier to find and maintain simulation code

---

## Verification

To verify simulation code is properly isolated:

```bash
# Check if any core code imports simulation
grep -r "from src.simulation\|import.*simulation" src/ --exclude-dir=simulation

# Should return no results (or only test files)
```

---

**Status**: Complete - All simulation code moved to `src/simulation/` directory

