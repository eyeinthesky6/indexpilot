# Benchmarking Datasets

**Location**: `data/benchmarking/`  
**Purpose**: Test databases for IndexPilot benchmarking and validation

---

## Available Datasets

### 1. Employees Database ✅

**File**: `employees_db.zip` (35MB)  
**Source**: https://github.com/datacharmer/test_db  
**Description**: Employee management database with realistic HR data  
**Size**: 6 tables, ~4 million rows

**Setup**:
```bash
python scripts/benchmarking/setup_employees.py
```

---

### 2. Sakila Database ⚠️

**File**: `sakila-pg.zip` (manual download needed)  
**Source**: https://www.postgresqltutorial.com/postgresql-sample-database/  
**Description**: DVD rental store database  
**Size**: ~15 tables, ~16,000 rows

**Download**: Visit the source URL and download `dvdrental.zip`, save as `sakila-pg.zip`

**Setup**:
```bash
python scripts/benchmarking/setup_sakila.py
```

---

### 3. World Database ⚠️

**File**: `world.sql` (manual download needed)  
**Source**: https://www.postgresqltutorial.com/postgresql-sample-database/  
**Description**: Country, city, and language data  
**Size**: 3 tables, ~5,000 rows

**Download**: Visit the source URL and download `world.sql`

**Setup**:
```bash
psql -U indexpilot -d indexpilot -f data/benchmarking/world.sql
```

---

## Downloading Datasets

### Automatic Download
```bash
# Linux/Mac
bash scripts/benchmarking/download_datasets.sh

# Windows
scripts\benchmarking\download_datasets.bat
```

### Manual Download

If automatic download fails:

1. **Employees**: https://github.com/datacharmer/test_db/releases
2. **Sakila**: https://www.postgresqltutorial.com/postgresql-sample-database/
3. **World**: https://www.postgresqltutorial.com/postgresql-sample-database/

Save files to this directory: `data/benchmarking/`

---

## Usage

After downloading and setting up:

1. **Point IndexPilot to test database**:
   ```bash
   export INDEXPILOT_DATABASE_URL=postgres://indexpilot:indexpilot@localhost:5432/[database_name]
   ```

2. **Initialize IndexPilot**:
   ```bash
   python -c "from src.schema import discover_and_bootstrap_schema; discover_and_bootstrap_schema()"
   ```

3. **Run analysis**:
   ```bash
   python -m src.auto_indexer analyze_and_create_indexes
   ```

---

## File Structure

```
data/benchmarking/
├── README.md (this file)
├── employees_db.zip
├── sakila-pg.zip (if downloaded)
└── world.sql (if downloaded)
```

---

## Notes

- Datasets are not committed to git (see `.gitignore`)
- Large files may take time to download
- Some datasets require manual download due to website restrictions

---

**Last Updated**: 08-12-2025

