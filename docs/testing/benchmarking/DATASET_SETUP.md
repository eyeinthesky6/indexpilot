# Dataset Setup Guide for IndexPilot Testing

**Date**: 08-12-2025  
**Purpose**: Guide to downloading and setting up test databases for IndexPilot benchmarking

---

## Available Test Databases

### 1. Sakila Database (DVD Rental Store) ✅ **RECOMMENDED**

**Description**: Standard PostgreSQL test database representing a DVD rental store  
**Size**: ~15 tables, ~16,000 rows  
**Use Case**: Real-world schema with customers, rentals, films, payments

**Download**:
```bash
# Option 1: Automatic download
bash scripts/benchmarking/download_datasets.sh
# or on Windows:
scripts\benchmarking\download_datasets.bat

# Option 2: Manual download
# Visit: https://www.postgresqltutorial.com/postgresql-sample-database/
# Download: dvdrental.zip
# Save to: data/benchmarking/sakila-pg.zip
```

**Setup**:
```bash
# Extract and import
python scripts/benchmarking/setup_sakila.py

# Or manually:
unzip data/benchmarking/sakila-pg.zip -d data/benchmarking/
psql -U indexpilot -d indexpilot -f data/benchmarking/dvdrental/dvdrental.sql
```

**Schema Config**: See `schema_config_sakila.yaml` (to be created)

---

### 2. Employees Database ✅ **RECOMMENDED**

**Description**: Employee management database with realistic HR data  
**Size**: 6 tables, ~4 million rows  
**Use Case**: Large dataset testing, complex relationships

**Download**:
```bash
# Automatic download
bash scripts/download_datasets.sh

# Or manual:
# Visit: https://github.com/datacharmer/test_db
# Download latest release
# Save to: datasets/employees_db-full-1.0.6.tar.bz2
```

**Setup**:
```bash
python scripts/setup_employees.py
```

**Schema Config**: See `schema_config_employees.yaml` (to be created)

---

### 3. World Database

**Description**: Country, city, and language data  
**Size**: 3 tables, ~5,000 rows  
**Use Case**: Simple schema testing, geographic queries

**Download**:
```bash
# Automatic download
bash scripts/download_datasets.sh

# Or manual:
# Visit: https://www.postgresqltutorial.com/postgresql-sample-database/
# Download: world.sql
```

**Setup**:
```bash
# Create database
psql -U indexpilot -c "CREATE DATABASE world_test"

# Import
psql -U indexpilot -d world_test -f datasets/world.sql
```

---

## Quick Start

### Step 1: Download All Datasets
```bash
# Linux/Mac
bash scripts/download_datasets.sh

# Windows
scripts\download_datasets.bat
```

### Step 2: Setup Sakila (Recommended First)
```bash
python scripts/setup_sakila.py
```

### Step 3: Setup Employees
```bash
python scripts/setup_employees.py
```

### Step 4: Create Schema Configs
```bash
# For Sakila
python scripts/create_sakila_config.py

# For Employees
python scripts/create_employees_config.py
```

### Step 5: Run IndexPilot Analysis
```bash
# Point to Sakila database
export INDEXPILOT_DATABASE_URL=postgres://indexpilot:indexpilot@localhost:5432/sakila_test

# Initialize IndexPilot metadata
python -c "from src.schema import discover_and_bootstrap_schema; discover_and_bootstrap_schema()"

# Run analysis
python -m src.auto_indexer analyze_and_create_indexes
```

---

## Manual Download Links

If automatic download fails, use these direct links:

1. **Sakila (DVD Rental)**:
   - https://www.postgresqltutorial.com/wp-content/uploads/2019/05/dvdrental.zip
   - Alternative: https://dev.mysql.com/doc/sakila/en/

2. **Employees Database**:
   - https://github.com/datacharmer/test_db/releases
   - Direct: https://github.com/datacharmer/test_db/archive/refs/heads/master.zip

3. **World Database**:
   - https://www.postgresqltutorial.com/wp-content/uploads/2019/05/world.sql

---

## Troubleshooting

### Issue: psql not found
**Solution**: Use Docker exec instead:
```bash
docker exec -i indexpilot_postgres psql -U indexpilot -d sakila_test < data/benchmarking/dvdrental.sql
```

### Issue: Download fails
**Solution**: Download manually using links above, then run setup scripts

### Issue: Import errors
**Solution**: Check PostgreSQL logs:
```bash
docker logs indexpilot_postgres
```

### Issue: Permission denied
**Solution**: Ensure Docker container is running:
```bash
docker-compose up -d
```

---

## Next Steps

After setting up databases:

1. **Create Schema Configs**: Generate YAML configs for each database
2. **Run Baseline Tests**: Measure performance without IndexPilot
3. **Run IndexPilot**: Let IndexPilot analyze and create indexes
4. **Compare Results**: Generate performance reports
5. **Create Case Studies**: Document results in case study library

See `docs/case_studies/README.md` for case study templates.

---

**Last Updated**: 08-12-2025

