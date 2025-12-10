# Simulator Multi-Schema Support

**Date**: 2025-12-08  
**Status**: ✅ **FULLY SUPPORTED**

---

## Summary

**YES, the simulator can now run on:**
- ✅ **CRM Schema** (tenants, contacts, organizations, interactions)
- ✅ **Stock Market Schema** (stocks, stock_prices)
- ✅ **Any Other Schema** (via schema_config.yaml)

The simulator automatically detects which schema to use based on the mode selected.

---

## How It Works

### Schema Detection

The simulator uses **mode-based schema selection**:

1. **CRM Modes** (`baseline`, `autoindex`, `scaled`, `comprehensive`):
   - Uses CRM schema (tenants, contacts, organizations, interactions)
   - Generates CRM-style queries (email, phone, industry lookups)
   - Works with existing `init-db` setup

2. **Stock Market Mode** (`real-data`):
   - Uses stock market schema (stocks, stock_prices)
   - Generates stock market queries (time-range, aggregation, filtering)
   - Requires `scripts/setup_stock_data.py` setup

3. **Future Schemas**:
   - Can add new modes for other schemas
   - Each mode can have its own query patterns
   - All use the same `query_stats` table for ML training

---

## Modes and Schemas

| Mode | Schema | Tables | Query Patterns | Setup |
|------|--------|--------|----------------|-------|
| `baseline` | CRM | tenants, contacts, orgs, interactions | Email, phone, industry | `make init-db` |
| `autoindex` | CRM | tenants, contacts, orgs, interactions | Email, phone, industry | `make init-db` |
| `scaled` | CRM | tenants, contacts, orgs, interactions | Email, phone, industry | `make init-db` |
| `comprehensive` | CRM | tenants, contacts, orgs, interactions | Email, phone, industry | `make init-db` |
| `real-data` | Stock Market | stocks, stock_prices | Time-range, aggregation, filtering | `python scripts/setup_stock_data.py` |

---

## Running Simulations

### CRM Schema (Default)

```bash
# Small simulation
python -m src.simulation.simulator baseline --scenario small

# Medium simulation
python -m src.simulation.simulator baseline --scenario medium

# Auto-index simulation
python -m src.simulation.simulator autoindex --scenario small

# Comprehensive (all features)
python -m src.simulation.simulator comprehensive --scenario small
```

### Stock Market Schema

```bash
# Small simulation with stock data
python -m src.simulation.simulator real-data --scenario small --timeframe 5min

# With specific stocks
python -m src.simulation.simulator real-data --stocks WIPRO,TCS,ITC --queries 200
```

---

## Code Structure

### Schema-Agnostic Components

These components work with **any schema**:

1. **Query Statistics** (`query_stats` table):
   - Logs all queries regardless of schema
   - Used by ML training (XGBoost)
   - Schema-agnostic

2. **Auto-Indexer** (`src/auto_indexer.py`):
   - Analyzes `query_stats` patterns
   - Creates indexes based on query patterns
   - Works with any table/field combination

3. **ML Training** (`src/algorithms/xgboost_classifier.py`):
   - Reads from `query_stats` and `mutation_log`
   - Pattern-based, not schema-specific
   - Works with CRM, stock, or any other schema

### Schema-Specific Components

1. **CRM Simulation** (`src/simulation/simulator.py`):
   - Functions: `run_baseline_simulation()`, `run_autoindex_simulation()`
   - Generates CRM queries
   - Uses CRM tables

2. **Stock Simulation** (`src/simulation/stock_simulator.py`):
   - Functions: `simulate_stock_workload()`, `run_stock_time_range_query()`
   - Generates stock market queries
   - Uses stock tables

---

## Adding New Schemas

To add support for a new schema:

1. **Create Schema Config**:
   ```yaml
   # schema_config_my_schema.yaml
   tables:
     - name: my_table
       fields:
         - name: id
           type: SERIAL
   ```

2. **Create Genome Bootstrap**:
   ```python
   # src/my_schema_genome.py
   def bootstrap_my_schema_genome_catalog():
       # Register fields in genome_catalog
   ```

3. **Create Simulator Functions**:
   ```python
   # src/simulation/my_schema_simulator.py
   def simulate_my_schema_workload():
       # Generate queries for your schema
   ```

4. **Add Mode to Simulator**:
   ```python
   # In src/simulation/simulator.py
   elif args.mode == "my-schema":
       from src.simulation.my_schema_simulator import simulate_my_schema_workload
       # Run simulation
   ```

---

## ML Training Compatibility

**XGBoost automatically works with all schemas** because:

1. **Query Stats are Schema-Agnostic**:
   - `query_stats` table stores: `table_name`, `field_name`, `query_type`, `duration_ms`
   - Works with any table/field combination

2. **Pattern-Based Training**:
   - ML model learns query patterns, not schema structure
   - Features: query frequency, duration, table size, etc.
   - Labels: index improvement percentages

3. **Unified Training Data**:
   - All schemas write to the same `query_stats` table
   - Training data includes patterns from all schemas
   - Model learns general indexing patterns

---

## Example: Running Both Schemas

```bash
# 1. Setup CRM schema
make init-db

# 2. Run CRM simulation
python -m src.simulation.simulator baseline --scenario small

# 3. Setup stock schema (in same or different DB)
python scripts/setup_stock_data.py --timeframe 5min --stocks WIPRO,TCS

# 4. Run stock simulation
python -m src.simulation.simulator real-data --stocks WIPRO,TCS --queries 200

# 5. ML training uses query_stats from BOTH schemas
#    XGBoost automatically trains on all query patterns
```

---

## Benefits

1. **Flexibility**: Test IndexPilot with different data patterns
2. **Real-World Testing**: Use real stock data instead of synthetic CRM
3. **ML Training**: Model learns from diverse query patterns
4. **Extensibility**: Easy to add new schemas for testing

---

## Current Status

- ✅ CRM schema: Fully supported (baseline, autoindex, scaled, comprehensive)
- ✅ Stock market schema: Fully supported (real-data mode)
- ✅ ML training: Works with all schemas automatically
- ✅ Query stats: Unified across all schemas

---

**The simulator is ready to run on CRM, stock market, and any other schema!**

