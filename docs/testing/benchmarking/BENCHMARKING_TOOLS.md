# Benchmarking Tools for IndexPilot

**Date**: 08-12-2025  
**Purpose**: Guide to benchmarking tools compatible with PostgreSQL and IndexPilot

---

## Compatible Benchmarking Tools

### 1. pgbench (Built-in PostgreSQL) ✅ **RECOMMENDED**

**Status**: ✅ **Ready to use** - Built into PostgreSQL, no installation needed

**What it does**:
- Generates synthetic OLTP workloads
- Tests transaction throughput
- Measures queries per second (TPS)
- Can be customized with custom SQL scripts

**How to use with IndexPilot**:
```bash
# Initialize pgbench database
pgbench -i -s 10 indexpilot  # Scale factor 10 (10x default size)

# Run benchmark (baseline)
pgbench -c 10 -j 2 -T 60 indexpilot

# After IndexPilot creates indexes, run again
pgbench -c 10 -j 2 -T 60 indexpilot

# Compare results
```

**Advantages**:
- ✅ No installation needed (comes with PostgreSQL)
- ✅ Fast and lightweight
- ✅ Easy to integrate
- ✅ Standard PostgreSQL benchmark

**Limitations**:
- ❌ Limited to simple OLTP patterns
- ❌ Doesn't test complex analytical queries
- ❌ Synthetic data only

**Integration with IndexPilot**:
- Can run before/after IndexPilot to measure improvement
- Results can be logged to IndexPilot's `query_stats` table
- Can be automated in test scripts

---

### 2. HammerDB ✅ **RECOMMENDED for Complex Workloads**

**Status**: ⚠️ **Requires installation** - Download from https://www.hammerdb.com/

**What it does**:
- Industry-standard database benchmarking
- Supports TPC-C and TPC-H benchmarks
- Creates realistic OLTP and OLAP workloads
- Supports PostgreSQL

**How to install**:
```bash
# Download from https://www.hammerdb.com/download.html
# Or use package manager (if available)
```

**How to use with IndexPilot**:
1. Create test schema using HammerDB
2. Load data
3. Run baseline benchmark
4. Enable IndexPilot
5. Run benchmark again
6. Compare results

**Advantages**:
- ✅ Industry-standard benchmarks (TPC-C, TPC-H)
- ✅ Realistic workloads
- ✅ Comprehensive metrics
- ✅ Widely recognized

**Limitations**:
- ❌ Requires installation
- ❌ More complex setup
- ❌ GUI-based (less scriptable)

**Integration with IndexPilot**:
- Can generate workloads that IndexPilot can optimize
- Results can be compared with published TPC results
- Good for validation and case studies

---

### 3. Sysbench ⚠️ **Limited PostgreSQL Support**

**Status**: ⚠️ **Limited** - Primarily designed for MySQL, PostgreSQL support is basic

**What it does**:
- Multi-threaded benchmarking
- Tests CPU, memory, I/O, and database performance
- Scriptable workloads

**PostgreSQL Support**:
- Basic support available
- Not as mature as MySQL support
- May require custom scripts

**Recommendation**: ⚠️ **Not recommended** - Use pgbench or HammerDB instead

---

### 4. Custom IndexPilot Benchmarks ✅ **BEST for IndexPilot**

**Status**: ✅ **Already available** - IndexPilot's simulation harness

**What it does**:
- Tests IndexPilot-specific features
- Multi-tenant scenarios
- Query pattern analysis
- Before/after performance comparison

**How to use**:
```bash
# Baseline (without IndexPilot)
python -m src.simulation.simulator baseline --scenario medium

# With IndexPilot
python -m src.simulation.simulator autoindex --scenario medium

# Compare results
make report
```

**Advantages**:
- ✅ Designed specifically for IndexPilot
- ✅ Tests multi-tenant scenarios
- ✅ Measures IndexPilot-specific metrics
- ✅ Already integrated

**Integration**: ✅ **Fully integrated** - This is IndexPilot's native benchmarking

---

## Recommended Testing Strategy

### Phase 1: Quick Validation (pgbench)
1. Use pgbench for quick validation
2. Test basic OLTP performance
3. Measure IndexPilot impact on simple queries

### Phase 2: Real Datasets (Sakila, Employees)
1. Import standard test databases
2. Run IndexPilot analysis
3. Measure improvements on real schemas

### Phase 3: Industry Standards (HammerDB)
1. Run TPC-C or TPC-H benchmarks
2. Compare with published results
3. Validate IndexPilot's effectiveness

### Phase 4: IndexPilot Native (Simulation)
1. Use IndexPilot's simulation harness
2. Test multi-tenant scenarios
3. Generate case studies

---

## Quick Start: pgbench

### Step 1: Initialize pgbench Database
```bash
# Connect to PostgreSQL
docker exec -it indexpilot_postgres psql -U indexpilot -d indexpilot

# Or use pgbench directly
pgbench -i -s 10 -h localhost -U indexpilot -d indexpilot
```

### Step 2: Run Baseline
```bash
pgbench -c 10 -j 2 -T 60 -h localhost -U indexpilot -d indexpilot
```

### Step 3: Enable IndexPilot
```bash
# Let IndexPilot analyze and create indexes
python -m src.auto_indexer analyze_and_create_indexes
```

### Step 4: Run Again
```bash
pgbench -c 10 -j 2 -T 60 -h localhost -U indexpilot -d indexpilot
```

### Step 5: Compare Results
Compare TPS (transactions per second) before and after.

---

## Next Steps

1. **Set up pgbench** (easiest, built-in)
2. **Download and test with Sakila database** (real schema)
3. **Download and test with Employees database** (real schema)
4. **Consider HammerDB** for industry-standard validation

See `DATASET_SETUP.md` for instructions on setting up test databases.

---

**Last Updated**: 08-12-2025

