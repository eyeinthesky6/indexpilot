# Execution Guide

## Prerequisites

1. **Docker Desktop** must be running on your system
2. Python 3.8+ installed
3. Virtual environment created and activated (recommended)
4. Dependencies installed: `pip install -r requirements.txt`

**Note**: It's recommended to use a virtual environment. If you haven't created one yet:
```bash
python -m venv venv
# On Windows (Git Bash):
source venv/Scripts/activate
# On Windows (CMD):
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

## Step-by-Step Execution

### 1. Initialize Database

Start Postgres and set up the schema:

**On Linux/Mac (using Make):**
```bash
make init-db
```

**On Windows (using batch script):**
```bash
run.bat init-db
```

**Or manually:**
```bash
docker-compose up -d
sleep 5  # Wait for Postgres to be ready
python -m src.schema
python -m src.genome
```

### 2. Run Tests

Verify everything is working:

**On Linux/Mac:**
```bash
make run-tests
```

**On Windows:**
```bash
run.bat test
```

**Or manually:**
```bash
pytest tests/ -v
```

### 3. Run Baseline Simulation

Run simulation without auto-indexing to establish baseline:

**On Linux/Mac:**
```bash
make run-sim-baseline
```

**On Windows:**
```bash
run.bat sim-baseline
```

**Or manually:**
```bash
# Default: Medium scenario (~6 minutes)
python -m src.simulation.simulator baseline

# Small scenario for quick testing (~2 minutes)
python -m src.simulation.simulator baseline --scenario small

# Large scenario for scale testing (~25 minutes)
python -m src.simulation.simulator baseline --scenario large
```

This will:
- Create tenants based on selected scenario (default: 50 tenants for medium)
- Seed data for each tenant (optimized with bulk inserts)
- Run queries per tenant with different patterns and traffic spikes
- Save results to `docs/audit/toolreports/results_baseline.json`

**Available scenarios**: `small`, `medium` (default), `large`, `stress-test`

**For complete scenario details and usage, see `docs/installation/SCENARIO_SIMULATION_GUIDE.md`**

### 4. Run Auto-Index Simulation

Run simulation with auto-indexing enabled:

**On Linux/Mac:**
```bash
make run-sim-autoindex
```

**On Windows:**
```bash
run.bat sim-autoindex
```

**Or manually:**
```bash
# Default: Medium scenario
python -m src.simulation.simulator autoindex

# Specific scenario
python -m src.simulation.simulator autoindex --scenario small
```

This will:
- Create tenants and seed data (optimized with bulk inserts)
- Run warmup queries to collect statistics
- Analyze patterns and create indexes automatically
- Run queries again with indexes in place (with traffic spikes)
- Save results to `docs/audit/toolreports/results_with_auto_index.json`

**Note**: The simulator now includes realistic traffic spikes and has been optimized for 1.7-2x better performance.

**For complete simulation guide with all scenarios and options, see `docs/installation/SCENARIO_SIMULATION_GUIDE.md`**

### 4a. Run Comprehensive Simulation (Recommended)

Run comprehensive simulation that tests all product features:

**On Linux/Mac:**
```bash
make run-sim-comprehensive
```

**On Windows:**
```bash
run.bat sim-comprehensive medium
```

**Or manually:**
```bash
# Medium scenario (default)
python -m src.simulation.simulator comprehensive --scenario medium

# Small scenario (quick test)
python -m src.simulation.simulator comprehensive --scenario small

# Large scenario
python -m src.simulation.simulator comprehensive --scenario large
```

This will:
- Run baseline simulation (without auto-indexing)
- Run auto-index simulation (with auto-indexing)
- Verify mutation log entries (schema lineage tracking)
- Verify expression profiles (per-tenant field activation)
- Verify production safeguards (maintenance windows, rate limiting, CPU throttling, write performance)
- Verify bypass system
- Verify health checks
- Save comprehensive results to `docs/audit/toolreports/results_comprehensive.json`

**This is the recommended mode for testing all product features across different database sizes.**

**For complete simulation guide with all scenarios and options, see `docs/installation/SCENARIO_SIMULATION_GUIDE.md`**

### 5. Generate Report

Compare baseline vs auto-index results:

**On Linux/Mac:**
```bash
make report
```

**On Windows:**
```bash
run.bat report
```

**Or manually:**
```bash
python -m src.reporting
```

### 6. Clean Up (Optional)

Stop containers and remove result files:

**On Linux/Mac:**
```bash
make clean
```

**On Windows:**
```bash
docker-compose down
del results_*.json
```

## Troubleshooting

### Docker not running
If you see errors about Docker, make sure Docker Desktop is running.

### Connection errors
If you see connection errors, wait a few seconds after starting Docker and try again. Postgres needs time to initialize.

### Port already in use
If port 5432 is already in use, modify `docker-compose.yml` to use a different port.

## Expected Output

After running both simulations and the report, you should see:

1. **Mutation Summary**: How many indexes were created
2. **Query Performance**: Statistics for different query patterns
3. **Evaluation**: Whether the auto-indexing showed benefits

## Notes

- The simulations may take several minutes to complete (see scenario guide for estimated times)
- Use `--scenario small` for quick testing (~2 minutes)
- Use `--scenario medium` for standard testing (~6 minutes) - this is the default
- The simulator has been optimized with bulk inserts and connection reuse for 1.7-2x better performance
- Results are saved as JSON files for later analysis
- **Main simulation guide**: `docs/installation/SCENARIO_SIMULATION_GUIDE.md` (complete reference)

