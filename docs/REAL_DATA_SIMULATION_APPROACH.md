# Real Data Simulation Approach

**Date**: 08-12-2025  
**Purpose**: Use real stock market backtesting data to create realistic database scenarios for IndexPilot testing and model training

---

## Overview

This document outlines the approach to integrate real stock market historical data into IndexPilot's simulation and testing framework. The goal is to provide IndexPilot with realistic data patterns that mirror production workloads, enabling better model training and more accurate performance testing.

---

## Data Analysis

### Data Structure

The backtesting data contains:
- **Format**: CSV files with OHLCV (Open, High, Low, Close, Volume) stock market data
- **Timeframes**: 
  - 1-minute intervals (high-frequency)
  - 5-minute intervals (medium-frequency)
  - 1-day intervals (daily)
- **Stocks**: 100+ Indian stocks (NSE/BSE)
- **Columns**: `timestamp`, `open`, `high`, `low`, `close`, `volume`
- **Data Points**: ~1000-1200 rows per file

### Data Characteristics

1. **Realistic Patterns**: Real market data contains:
   - Natural volatility and trends
   - Time-based patterns (market hours, weekends)
   - Volume spikes and lulls
   - Price movements that create realistic query patterns

2. **Query Patterns**: This data will generate:
   - Time-range queries (filter by timestamp)
   - Aggregation queries (OHLCV calculations)
   - Multi-stock comparisons
   - Volume-based filtering
   - Price-based filtering

---

## Proposed Approach

### Phase 1: Database Schema Design

Create a stock market database schema using IndexPilot's config-based schema system (`init_schema_from_config`):

**Schema Configuration** (`schema_config_stock_market.yaml`):
```yaml
tables:
  - name: stocks
    fields:
      - name: id
        type: SERIAL
        required: true
      - name: symbol
        type: TEXT
        required: true
      - name: name
        type: TEXT
        required: false
      - name: sector
        type: TEXT
        required: false
      - name: created_at
        type: TIMESTAMP
        required: false
    indexes:
      - fields: [symbol]
        type: btree
      - fields: [sector]
        type: btree

  - name: stock_prices
    fields:
      - name: id
        type: SERIAL
        required: true
      - name: stock_id
        type: INTEGER
        required: true
        foreign_key:
          table: stocks
          column: id
          on_delete: CASCADE
      - name: timestamp
        type: TIMESTAMP
        required: true
      - name: open
        type: NUMERIC
        required: false
      - name: high
        type: NUMERIC
        required: false
      - name: low
        type: NUMERIC
        required: false
      - name: close
        type: NUMERIC
        required: false
      - name: volume
        type: BIGINT
        required: false
      - name: created_at
        type: TIMESTAMP
        required: false
    indexes:
      - fields: [stock_id]
        type: btree
      # IndexPilot will create additional indexes based on query patterns
```

**Genome Catalog Integration**: 
- Bootstrap genome catalog with stock schema fields using `bootstrap_genome_catalog()` pattern
- Register fields in `genome_catalog` table for IndexPilot awareness
- Enable expression profiles for stock fields (no tenant_id needed for single-tenant stock data)

### Phase 2: Data Loading Strategy

#### Split Strategy

1. **Initial Load (50% of data)**:
   - Load first half chronologically for each stock
   - Creates "existing database" state
   - IndexPilot sees this as baseline data

2. **Live Updates (50% of data)**:
   - Simulate real-time inserts of remaining data
   - Mimics production data growth
   - Tests IndexPilot's ability to adapt to new data

#### Implementation

```python
# Pseudo-code approach
def load_stock_data():
    # 1. Parse CSV files
    # 2. Sort by timestamp
    # 3. Split at midpoint
    # 4. Load first half as initial data
    # 5. Queue second half for live simulation
```

### Phase 3: Simulation Mode

Add new simulation mode: `real-data` to existing simulator modes (`baseline`, `autoindex`, `comprehensive`)

**Integration with Existing Simulator**:
- Follow pattern of `run_baseline_simulation()` and `run_autoindex_simulation()`
- Add `run_real_data_simulation()` function
- Integrate with existing command-line argument parser
- Use existing `query_stats` table for tracking (already exists)
- Use existing `log_query_stat()` function for query logging
- Follow existing scenario pattern (small/medium/large) but for stock data

**Features**:
- Uses real stock data instead of synthetic CRM data
- Simulates realistic query patterns:
  - Time-range queries: "Get prices for last 7 days"
  - Aggregation queries: "Average volume by stock"
  - Comparison queries: "Compare WIPRO vs TCS prices"
  - Filter queries: "Stocks with volume > 1M"
- Simulates live data inserts (second half of data)
- Generates `query_stats` entries using existing `log_query_stat()` function
- Works with existing `analyze_and_create_indexes()` function
- Integrates with existing features (expression profiles, genome catalog, mutation log)

**Query Patterns**:
```sql
-- Pattern 1: Time-range queries
SELECT * FROM stock_prices 
WHERE stock_id = ? AND timestamp BETWEEN ? AND ?;

-- Pattern 2: Aggregation
SELECT stock_id, AVG(volume), MAX(high), MIN(low)
FROM stock_prices 
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY stock_id;

-- Pattern 3: Price filtering
SELECT * FROM stock_prices 
WHERE close > ? AND volume > ? 
ORDER BY timestamp DESC;

-- Pattern 4: Multi-stock comparison
SELECT s.symbol, sp.close, sp.volume
FROM stock_prices sp
JOIN stocks s ON s.id = sp.stock_id
WHERE s.symbol IN (?, ?, ?)
AND sp.timestamp = ?;
```

---

## Integration Points

### 1. Existing Systems Integration

**Schema System**:
- Use `init_schema_from_config()` for stock schema creation
- Leverage `create_table_from_definition()` for flexible table creation
- Integrate with database adapter system for cross-DB support

**Genome Catalog**:
- Bootstrap stock fields using `bootstrap_genome_catalog()` pattern
- Register all stock fields in `genome_catalog` table
- Enable expression profiles for stock fields (optional tenant_id)

**Query Tracking**:
- Use existing `query_stats` table (no changes needed)
- Use existing `log_query_stat()` function
- Query patterns automatically tracked for IndexPilot analysis

**Mutation Log**:
- Index creations logged to existing `mutation_log` table
- Works with existing audit trail system
- Compatible with rollback system

### 2. Model Training

**XGBoost Classifier**:
- Use real query patterns from stock data in `query_stats`
- Train on actual query performance metrics
- Better feature engineering with real data distributions
- `_load_training_data()` already queries `query_stats` - no changes needed

**Benefits**:
- Realistic feature distributions
- Actual query patterns (not synthetic)
- Better model accuracy
- Works with existing XGBoost integration

### 3. Index Recommendations

**Realistic Scenarios**:
- Time-based indexes on `timestamp` (via `auto_indexer.py`)
- Composite indexes on `(stock_id, timestamp)` (composite index detection)
- Volume-based indexes for filtering
- Multi-column indexes for aggregations
- All handled by existing `analyze_and_create_indexes()` function

### 4. Performance Testing

**Realistic Workloads**:
- Actual data volumes (not synthetic)
- Real query patterns
- Natural data growth patterns
- Time-based access patterns
- Results saved via existing reporting system

---

## Implementation Plan

### Step 1: Data Preparation
- [ ] Copy backtesting data to `data/backtesting/` (gitignored)
- [ ] Create data loader script
- [ ] Parse and validate CSV files
- [ ] Implement data splitting logic

### Step 2: Schema Creation
- [ ] Create `schema_config_stock_market.yaml` using config-based system
- [ ] Add stock schema creation function to `src/schema/initialization.py`
- [ ] Create `src/stock_genome.py` to bootstrap genome catalog (follow `genome.py` pattern)
- [ ] Register stock fields in `genome_catalog` table
- [ ] Test schema initialization with `init_schema_from_config()`

### Step 3: Simulation Mode
- [ ] Add `run_real_data_simulation()` function to `src/simulator.py`
- [ ] Add `real-data` mode to command-line argument parser
- [ ] Implement `load_stock_initial_data()` (first 50% of data)
- [ ] Implement `simulate_stock_workload()` (query generation)
- [ ] Implement `simulate_live_stock_updates()` (second 50% of data)
- [ ] Integrate with existing `log_query_stat()` for query tracking
- [ ] Use existing `analyze_and_create_indexes()` for index recommendations
- [ ] Follow existing result reporting pattern (`get_report_path()`)

### Step 4: Query Generation
- [ ] Time-range queries
- [ ] Aggregation queries
- [ ] Filter queries
- [ ] Multi-stock queries

### Step 5: Integration
- [ ] Update XGBoost `_load_training_data()` to support stock data queries
- [ ] Ensure `query_stats` table captures stock query patterns
- [ ] Test with existing `simulation_verification.py` framework
- [ ] Update tests to support real-data mode
- [ ] Document usage in installation guides
- [ ] Add to `.gitignore`: `data/backtesting/`

---

## File Structure

```
indexpilot/
├── data/
│   └── backtesting/              # Gitignored - real stock data
│       ├── WIPRO_5min_historical_data.csv
│       ├── TCS_1min_historical_data.csv
│       └── ...
├── src/
│   ├── stock_data_loader.py      # Load stock data into DB (new)
│   ├── stock_genome.py            # Bootstrap genome catalog for stocks (new)
│   ├── simulator.py               # Add real-data mode (modify existing)
│   ├── schema/
│   │   ├── initialization.py     # Add stock schema creation (modify)
│   │   └── ...
│   └── ...
├── schema_config_stock_market.yaml  # Stock market schema config (new)
└── docs/
    └── REAL_DATA_SIMULATION_APPROACH.md  # This file
```

---

## Benefits

1. **Realistic Testing**: Real data patterns vs synthetic
2. **Better Models**: Train on actual query patterns
3. **Production-like**: Mimics real-world database scenarios
4. **Scalable**: Can add more stocks/data easily
5. **Flexible**: Can simulate different timeframes (1min, 5min, 1d)

---

## Challenges & Solutions

### Challenge 1: Data Volume
- **Issue**: Large CSV files
- **Solution**: Stream processing, batch inserts, progress tracking

### Challenge 2: Timestamp Handling
- **Issue**: Different timezone formats in files
- **Solution**: Normalize to UTC, handle timezone conversion

### Challenge 3: Missing Data
- **Issue**: Some rows may have missing values
- **Solution**: Handle NULLs gracefully, validate before insert

### Challenge 4: Query Pattern Realism
- **Issue**: Need realistic query patterns
- **Solution**: Analyze common stock market queries, implement patterns

---

## Usage Example

```bash
# Initialize database with stock schema (using config-based system)
python -m src.schema --config schema_config_stock_market.yaml

# Bootstrap genome catalog for stock fields
python -m src.stock_genome

# Load initial data (first 50%)
python -m src.stock_data_loader --mode initial --data-dir data/backtesting --timeframe 5min

# Run baseline simulation (no auto-indexing)
python -m src.simulator real-data --mode baseline --stocks WIPRO,TCS,ITC --timeframe 5min

# Run autoindex simulation (with IndexPilot)
python -m src.simulator real-data --mode autoindex --stocks WIPRO,TCS,ITC --timeframe 5min

# Run comprehensive simulation (baseline + autoindex + verification)
python -m src.simulator real-data --mode comprehensive --scenario medium --timeframe 5min

# Simulate live updates (second 50% of data)
python -m src.simulator real-data --mode live-updates --duration 3600 --stocks WIPRO,TCS
```

**Integration with Existing Commands**:
- Follows same pattern as existing modes: `baseline`, `autoindex`, `comprehensive`
- Uses existing `--scenario` argument (small/medium/large)
- Results saved to `docs/audit/toolreports/` via `get_report_path()` utility

---

## Success Criteria

✅ Database populated with real stock data  
✅ IndexPilot can analyze and create indexes on real data  
✅ XGBoost model trains on real query patterns  
✅ Simulation runs without errors  
✅ Query performance improves with IndexPilot recommendations  
✅ Tests pass with real data mode  

---

## Next Steps

1. Review and approve this approach
2. Implement data loader
3. Create stock market schema
4. Implement simulation mode
5. Test with sample data
6. Full integration

---

## Questions to Consider

1. **Data Selection**: Which stocks/timeframes to use initially?
2. **Query Patterns**: What queries are most realistic for stock data?
3. **Performance Metrics**: What KPIs to track?
4. **Scaling**: How to handle 100+ stocks efficiently?

---

## Codebase Alignment Summary

This approach is designed to integrate seamlessly with existing IndexPilot architecture:

### ✅ Existing Systems Used (No Duplication)

1. **Schema System**: Uses `init_schema_from_config()` - no new schema system needed
2. **Genome Catalog**: Extends `bootstrap_genome_catalog()` pattern - no new catalog system
3. **Query Tracking**: Uses existing `query_stats` table and `log_query_stat()` function
4. **Index Creation**: Uses existing `analyze_and_create_indexes()` function
5. **Simulation Framework**: Extends existing `simulator.py` modes - follows same pattern
6. **Reporting**: Uses existing `get_report_path()` utility
7. **Mutation Log**: Uses existing `mutation_log` table for audit trail
8. **Expression Profiles**: Works with existing expression profile system

### ✅ Integration Points

- **No Breaking Changes**: All additions are optional/new modes
- **Follows Patterns**: Uses same patterns as existing CRM simulation
- **Reuses Code**: Leverages existing functions and utilities
- **Compatible**: Works with all existing IndexPilot features

### ✅ Implementation Approach

- **Incremental**: Can be implemented step-by-step
- **Testable**: Each component can be tested independently
- **Maintainable**: Follows existing code structure and patterns
- **Documented**: Integrates with existing documentation system

---

**Status**: Proposal - Aligned with codebase structure, ready for implementation

