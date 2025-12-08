# Benchmarking Resources Index

**Date**: 08-12-2025  
**Purpose**: Quick index of all benchmarking-related resources

---

## 📁 Folder Structure

```
indexpilot/
├── scripts/benchmarking/          # Setup and download scripts
│   ├── README.md
│   ├── download_datasets.sh
│   ├── download_datasets.bat
│   ├── setup_sakila.py
│   └── setup_employees.py
│
├── data/benchmarking/             # Test databases
│   ├── README.md
│   ├── employees_db.zip
│   ├── sakila-pg.zip
│   └── world.sql
│
└── docs/testing/benchmarking/    # Documentation
    ├── README.md
    ├── QUICK_START_BENCHMARKING.md
    ├── DATASET_SETUP.md
    ├── BENCHMARKING_TOOLS.md
    ├── BENCHMARKING_SUMMARY.md
    └── TESTING_WITH_REAL_DATABASES.md
```

---

## 🚀 Quick Start

**New to benchmarking?** Start here:
1. Read: `docs/testing/benchmarking/QUICK_START_BENCHMARKING.md`
2. Run: `bash scripts/benchmarking/download_datasets.sh`
3. Setup: `python scripts/benchmarking/setup_employees.py`

---

## 📚 Documentation

### Getting Started
- **Quick Start**: `docs/testing/benchmarking/QUICK_START_BENCHMARKING.md`
- **Dataset Setup**: `docs/testing/benchmarking/DATASET_SETUP.md`

### Tools & Resources
- **Benchmarking Tools**: `docs/testing/benchmarking/BENCHMARKING_TOOLS.md`
- **Research Summary**: `docs/testing/benchmarking/TESTING_WITH_REAL_DATABASES.md`
- **Quick Reference**: `docs/testing/benchmarking/BENCHMARKING_SUMMARY.md`

### Case Studies
- **Case Study Library**: `docs/case_studies/README.md`
- **Case Study Template**: `docs/case_studies/TEMPLATE.md`

---

## 🛠️ Scripts

### Download Scripts
- **Linux/Mac**: `scripts/benchmarking/download_datasets.sh`
- **Windows**: `scripts/benchmarking/download_datasets.bat`

### Setup Scripts
- **Sakila**: `scripts/benchmarking/setup_sakila.py`
- **Employees**: `scripts/benchmarking/setup_employees.py`

**See**: `scripts/benchmarking/README.md` for details

---

## 💾 Datasets

### Available
- ✅ **Employees Database** (35MB) - `data/benchmarking/employees_db.zip`
- ⚠️ **Sakila Database** - Manual download needed
- ⚠️ **World Database** - Manual download needed

**See**: `data/benchmarking/README.md` for download links

---

## 📊 Benchmarking Tools

1. **pgbench** ✅ - Built into PostgreSQL (easiest)
2. **HammerDB** ⚠️ - Industry-standard (requires installation)
3. **IndexPilot Simulation** ✅ - Native benchmarking

**See**: `docs/testing/benchmarking/BENCHMARKING_TOOLS.md`

---

## 🎯 Workflow

1. **Choose tool** (pgbench recommended for quick start)
2. **Run baseline** (measure without IndexPilot)
3. **Enable IndexPilot** (let it analyze and create indexes)
4. **Measure improvement** (compare before/after)
5. **Document results** (create case study)

---

## 📝 Creating Case Studies

1. Run benchmark and collect results
2. Copy template: `docs/case_studies/TEMPLATE.md`
3. Fill in details (problem, solution, results)
4. Add to index: `docs/case_studies/README.md`

**See**: `docs/case_studies/README.md` for complete guide

---

## 🔗 Related Resources

- **Main Testing Docs**: `docs/testing/`
- **Case Studies**: `docs/case_studies/`
- **Scripts**: `scripts/benchmarking/`
- **Data**: `data/benchmarking/`

---

**Last Updated**: 08-12-2025

