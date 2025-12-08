# Benchmarking Documentation

**Location**: `docs/testing/benchmarking/`  
**Purpose**: Documentation for benchmarking IndexPilot with real databases

---

## Documentation Files

### Quick Start Guides

- **`QUICK_START_BENCHMARKING.md`** - Get started in 5 minutes
  - pgbench quick test
  - Employees database setup
  - IndexPilot simulation

### Setup Guides

- **`DATASET_SETUP.md`** - Complete dataset setup instructions
  - Downloading datasets
  - Setting up databases
  - Troubleshooting

### Tool Guides

- **`BENCHMARKING_TOOLS.md`** - Benchmarking tools overview
  - pgbench (built-in PostgreSQL)
  - HammerDB
  - IndexPilot simulation

### Research & Summary

- **`TESTING_WITH_REAL_DATABASES.md`** - Research summary
  - Available datasets
  - Testing approaches
  - Community resources

- **`BENCHMARKING_SUMMARY.md`** - Quick reference
  - What's available
  - Status of downloads
  - Next steps

---

## Quick Links

### Start Here
1. **New to benchmarking?** → `QUICK_START_BENCHMARKING.md`
2. **Setting up databases?** → `DATASET_SETUP.md`
3. **Choosing tools?** → `BENCHMARKING_TOOLS.md`

### Related Documentation

- **Case Studies**: `docs/case_studies/` - Real-world results
- **Scripts**: `scripts/benchmarking/` - Setup scripts
- **Data**: `data/benchmarking/` - Test databases

---

## Workflow

1. **Choose a tool** (pgbench, Employees DB, or simulation)
2. **Run baseline** (measure performance without IndexPilot)
3. **Enable IndexPilot** (let it analyze and create indexes)
4. **Measure improvement** (compare before/after)
5. **Document results** (create case study)

---

## File Locations

- **Scripts**: `scripts/benchmarking/`
- **Datasets**: `data/benchmarking/`
- **Documentation**: `docs/testing/benchmarking/` (this folder)
- **Case Studies**: `docs/case_studies/`

---

**Last Updated**: 08-12-2025

