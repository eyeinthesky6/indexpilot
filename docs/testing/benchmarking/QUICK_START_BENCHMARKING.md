# Quick Start: Benchmarking IndexPilot

**Date**: 08-12-2025  
**Purpose**: Get started with benchmarking IndexPilot in 5 minutes

---

## Option 1: pgbench (Fastest - No Downloads) ✅

### Step 1: Initialize Test Database
```bash
docker exec -it indexpilot_postgres pgbench -i -s 10 -U indexpilot -d indexpilot
```
*This creates test tables with ~1 million rows*

### Step 2: Run Baseline Benchmark
```bash
docker exec -it indexpilot_postgres pgbench -c 10 -j 2 -T 60 -U indexpilot -d indexpilot
```
*Note the TPS (transactions per second) value*

### Step 3: Let IndexPilot Analyze
```bash
python -m src.auto_indexer analyze_and_create_indexes
```

### Step 4: Run Benchmark Again
```bash
docker exec -it indexpilot_postgres pgbench -c 10 -j 2 -T 60 -U indexpilot -d indexpilot
```
*Compare TPS - should be higher*

**Time**: ~5 minutes  
**Result**: Quick validation that IndexPilot works

---

## Option 2: Employees Database (Real Schema) ✅

### Step 1: Setup Database
```bash
# Extract and import (if not done)
python scripts/benchmarking/setup_employees.py
```

### Step 2: Point IndexPilot to Employees DB
```bash
export INDEXPILOT_DATABASE_URL=postgres://indexpilot:indexpilot@localhost:5432/employees_test
```

### Step 3: Initialize IndexPilot
```bash
python -c "from src.schema import discover_and_bootstrap_schema; discover_and_bootstrap_schema()"
```

### Step 4: Run Some Queries (to generate query_stats)
```bash
# Connect to database
docker exec -it indexpilot_postgres psql -U indexpilot -d employees_test

# Run some queries
SELECT * FROM employees WHERE first_name = 'Georgi' LIMIT 10;
SELECT * FROM salaries WHERE salary > 50000 LIMIT 10;
SELECT * FROM dept_emp WHERE dept_no = 'd001' LIMIT 10;
```

### Step 5: Let IndexPilot Analyze
```bash
python -m src.auto_indexer analyze_and_create_indexes
```

### Step 6: Check Results
```bash
# Check mutation_log for indexes created
docker exec -it indexpilot_postgres psql -U indexpilot -d employees_test -c "SELECT * FROM mutation_log;"
```

**Time**: ~10 minutes  
**Result**: Real-world schema test

---

## Option 3: IndexPilot Simulation (Native) ✅

### Step 1: Run Baseline
```bash
python -m src.simulation.simulator baseline --scenario small
```

### Step 2: Run with IndexPilot
```bash
python -m src.simulation.simulator autoindex --scenario small
```

### Step 3: Generate Report
```bash
make report
```

**Time**: ~5 minutes  
**Result**: IndexPilot-specific metrics

---

## Which Option to Choose?

| Option | Time | Complexity | Use Case |
|--------|------|------------|----------|
| pgbench | 5 min | Easy | Quick validation |
| Employees DB | 10 min | Medium | Real schema test |
| Simulation | 5 min | Easy | IndexPilot features |

**Recommendation**: Start with **pgbench** for quick validation, then try **Employees DB** for real-world testing.

---

## Creating a Case Study

After running any benchmark:

1. **Copy Template**:
   ```bash
   cp docs/case_studies/TEMPLATE.md docs/case_studies/CASE_STUDY_[NAME].md
   ```

2. **Fill in Details**:
   - Problem statement
   - Performance metrics (before/after)
   - Indexes created
   - Results analysis

3. **Add to Index**:
   - Update `docs/case_studies/README.md`

See `docs/case_studies/TEMPLATE.md` for complete template.

---

## Troubleshooting

### pgbench: "command not found"
**Solution**: Use Docker exec:
```bash
docker exec -it indexpilot_postgres pgbench ...
```

### Employees: "Database not found"
**Solution**: Run setup script:
```bash
python scripts/benchmarking/setup_employees.py
```

### IndexPilot: "No queries in query_stats"
**Solution**: Run some queries first, or use simulation mode which generates queries automatically.

---

## Next Steps

1. ✅ Run one of the benchmarks above
2. ✅ Document results in a case study
3. ✅ Share with community

---

**Last Updated**: 08-12-2025

