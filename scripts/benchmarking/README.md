# Benchmarking Scripts

**Location**: `scripts/benchmarking/`  
**Purpose**: Scripts for downloading, setting up, and testing with benchmark databases

---

## Scripts

### Download Scripts

- **`download_datasets.sh`** (Linux/Mac) - Downloads test databases
- **`download_datasets.bat`** (Windows) - Downloads test databases

**Usage**:
```bash
# Linux/Mac
bash scripts/benchmarking/download_datasets.sh

# Windows
scripts\benchmarking\download_datasets.bat
```

**Downloads**:
- Employees database (GitHub)
- Sakila database (PostgreSQL tutorial)
- World database (PostgreSQL tutorial)

**Output**: Files saved to `data/benchmarking/`

---

### Setup Scripts

- **`setup_sakila.py`** - Sets up Sakila (DVD Rental) database
- **`setup_employees.py`** - Sets up Employees database

**Usage**:
```bash
# Setup Sakila
python scripts/benchmarking/setup_sakila.py

# Setup Employees
python scripts/benchmarking/setup_employees.py
```

**What they do**:
1. Check if database files exist in `data/benchmarking/`
2. Extract archives if needed
3. Create test databases in PostgreSQL
4. Import SQL schemas and data

---

## Prerequisites

- Docker running (PostgreSQL container)
- Python 3.8+
- `psql` command-line tool (or use Docker exec)

---

## Data Location

All datasets are stored in: `data/benchmarking/`

---

## Documentation

- **Quick Start**: `docs/testing/benchmarking/QUICK_START_BENCHMARKING.md`
- **Dataset Setup**: `docs/testing/benchmarking/DATASET_SETUP.md`
- **Benchmarking Tools**: `docs/testing/benchmarking/BENCHMARKING_TOOLS.md`

---

**Last Updated**: 08-12-2025

