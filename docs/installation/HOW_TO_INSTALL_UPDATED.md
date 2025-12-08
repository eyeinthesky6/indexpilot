# How to Install - Copy Over Mode (Updated)
**Date**: 08-12-2025  
**Purpose**: Updated step-by-step guide for copying IndexPilot files into your project (includes all algorithms and advanced features)

---

## Overview

This guide explains how to integrate IndexPilot into your existing project using **copy-over mode**. The system has grown significantly with 12 academic algorithms and many production features, so this guide provides complete file lists.

**Two Integration Options:**
- **Option 1: Copy Entire `src/` Directory** (Recommended) - Simplest, includes everything
- **Option 2: Selective File Copy** - Copy only specific files you need

---

## Prerequisites

- Python 3.8+
- PostgreSQL 12+ (or other supported database)
- Existing database with your application schema
- Your project directory structure

---

## Step 1: Choose Copy Method

### Option A: Copy Entire `src/` Directory (Recommended)

**Best for:** Most users, ensures you have all dependencies

```bash
# Clone or download IndexPilot repository
git clone https://github.com/eyeinthesky6/indexpilot
cd indexpilot

# Copy entire src/ directory to your project
cp -r src your_project/dna_layer

# Or on Windows:
xcopy /E /I src your_project\dna_layer
```

**Result:** Your project will have:
```
your_project/
├── dna_layer/              # Complete IndexPilot system
│   ├── __init__.py
│   ├── algorithms/         # All 12 academic algorithms
│   │   ├── __init__.py
│   │   ├── cert.py
│   │   ├── qpg.py
│   │   ├── cortex.py
│   │   ├── predictive_indexing.py
│   │   ├── xgboost_classifier.py
│   │   ├── pgm_index.py
│   │   ├── alex.py
│   │   ├── radix_string_spline.py
│   │   ├── fractal_tree.py
│   │   ├── idistance.py
│   │   ├── bx_tree.py
│   │   └── constraint_optimizer.py
│   ├── database/           # Database adapters
│   ├── schema/            # Schema loading utilities
│   ├── db.py
│   ├── genome.py
│   ├── expression.py
│   ├── auto_indexer.py
│   ├── stats.py
│   ├── audit.py
│   ├── schema.py
│   ├── validation.py
│   └── [all other files]
```

**Update imports:** Change all `from src.` to `from dna_layer.` in your code:
```python
# Old (in IndexPilot repo)
from src.db import get_connection

# New (in your project)
from dna_layer.db import get_connection
```

### Option B: Selective File Copy (Advanced)

**Best for:** Minimal installations, custom integrations

If you only want specific features, copy these files:

#### Core Files (Required)

```bash
mkdir -p your_project/dna_layer
mkdir -p your_project/dna_layer/algorithms
mkdir -p your_project/dna_layer/database/adapters
mkdir -p your_project/dna_layer/schema

# Core system files
cp src/db.py your_project/dna_layer/
cp src/genome.py your_project/dna_layer/
cp src/expression.py your_project/dna_layer/
cp src/auto_indexer.py your_project/dna_layer/
cp src/stats.py your_project/dna_layer/
cp src/audit.py your_project/dna_layer/
cp src/schema.py your_project/dna_layer/
cp src/validation.py your_project/dna_layer/
cp src/type_definitions.py your_project/dna_layer/  # Required for types
```

#### Algorithms (Required for Advanced Features)

**All 12 algorithms are used by the system**, so copy all of them:

```bash
# Copy all algorithms
cp src/algorithms/__init__.py your_project/dna_layer/algorithms/
cp src/algorithms/cert.py your_project/dna_layer/algorithms/
cp src/algorithms/qpg.py your_project/dna_layer/algorithms/
cp src/algorithms/cortex.py your_project/dna_layer/algorithms/
cp src/algorithms/predictive_indexing.py your_project/dna_layer/algorithms/
cp src/algorithms/xgboost_classifier.py your_project/dna_layer/algorithms/
cp src/algorithms/pgm_index.py your_project/dna_layer/algorithms/
cp src/algorithms/alex.py your_project/dna_layer/algorithms/
cp src/algorithms/radix_string_spline.py your_project/dna_layer/algorithms/
cp src/algorithms/fractal_tree.py your_project/dna_layer/algorithms/
cp src/algorithms/idistance.py your_project/dna_layer/algorithms/
cp src/algorithms/bx_tree.py your_project/dna_layer/algorithms/
cp src/algorithms/constraint_optimizer.py your_project/dna_layer/algorithms/
```

#### Query Optimization (Recommended)

```bash
cp src/query_analyzer.py your_project/dna_layer/
cp src/query_executor.py your_project/dna_layer/
cp src/query_interceptor.py your_project/dna_layer/
cp src/query_patterns.py your_project/dna_layer/
cp src/query_timeout.py your_project/dna_layer/
cp src/query_pattern_learning.py your_project/dna_layer/
```

#### Production Features (Recommended)

```bash
# Production safety
cp src/rollback.py your_project/dna_layer/
cp src/config_loader.py your_project/dna_layer/
cp src/bypass_config.py your_project/dna_layer/
cp src/bypass_status.py your_project/dna_layer/
cp src/production_config.py your_project/dna_layer/
cp src/production_cache.py your_project/dna_layer/

# Monitoring and health
cp src/monitoring.py your_project/dna_layer/
cp src/health_check.py your_project/dna_layer/
cp src/error_handler.py your_project/dna_layer/
cp src/resilience.py your_project/dna_layer/

# Rate limiting and throttling
cp src/rate_limiter.py your_project/dna_layer/
cp src/cpu_throttle.py your_project/dna_layer/
cp src/lock_manager.py your_project/dna_layer/
cp src/maintenance_window.py your_project/dna_layer/

# Performance monitoring
cp src/write_performance.py your_project/dna_layer/
cp src/pattern_detection.py your_project/dna_layer/
cp src/workload_analysis.py your_project/dna_layer/
```

#### Advanced Features (Optional but Recommended)

```bash
# Index management
cp src/index_cleanup.py your_project/dna_layer/
cp src/index_health.py your_project/dna_layer/
cp src/index_lifecycle_manager.py your_project/dna_layer/
cp src/index_lifecycle_advanced.py your_project/dna_layer/
cp src/index_type_selection.py your_project/dna_layer/
cp src/index_retry.py your_project/dna_layer/

# Composite and pattern detection
cp src/composite_index_detection.py your_project/dna_layer/
cp src/redundant_index_detection.py your_project/dna_layer/

# ML and learning
cp src/ml_query_interception.py your_project/dna_layer/

# Schema evolution
cp src/schema_evolution.py your_project/dna_layer/

# Maintenance
cp src/maintenance.py your_project/dna_layer/
cp src/statistics_refresh.py your_project/dna_layer/

# Storage and budget
cp src/storage_budget.py your_project/dna_layer/

# Reporting
cp src/scaled_reporting.py your_project/dna_layer/
cp src/before_after_validation.py your_project/dna_layer/
cp src/simulation_verification.py your_project/dna_layer/

# Advanced features
cp src/adaptive_safeguards.py your_project/dna_layer/
cp src/approval_workflow.py your_project/dna_layer/
cp src/concurrent_index_monitoring.py your_project/dna_layer/
cp src/foreign_key_suggestions.py your_project/dna_layer/
cp src/materialized_view_support.py your_project/dna_layer/
cp src/per_tenant_config.py your_project/dna_layer/
cp src/safeguard_monitoring.py your_project/dna_layer/

# Utilities
cp src/paths.py your_project/dna_layer/
cp src/graceful_shutdown.py your_project/dna_layer/
cp src/structured_logging.py your_project/dna_layer/
```

#### Integration Files (Production - Critical)

```bash
# Adapter system (CRITICAL for production)
cp src/adapters.py your_project/dna_layer/

# Schema loading (for Option 2: Configuration-Based)
cp src/schema/__init__.py your_project/dna_layer/schema/
cp src/schema/loader.py your_project/dna_layer/schema/
cp src/schema/validator.py your_project/dna_layer/schema/
cp src/schema/initialization.py your_project/dna_layer/schema/

# Database adapters
cp src/database/__init__.py your_project/dna_layer/database/
cp src/database/detector.py your_project/dna_layer/database/
cp src/database/type_detector.py your_project/dna_layer/database/
cp src/database/adapters/__init__.py your_project/dna_layer/database/adapters/
cp src/database/adapters/base.py your_project/dna_layer/database/adapters/
cp src/database/adapters/postgresql.py your_project/dna_layer/database/adapters/
```

#### Create `__init__.py` Files

```bash
# Create main __init__.py
touch your_project/dna_layer/__init__.py  # Can be empty
```

---

## Step 2: Update Import Statements

After copying files, you need to update import statements from `src.` to `dna_layer.`:

### Option 1: Find and Replace (Recommended)

```bash
# In your project directory
find your_project/dna_layer -name "*.py" -type f -exec sed -i 's/from src\./from dna_layer./g' {} \;
find your_project/dna_layer -name "*.py" -type f -exec sed -i 's/import src\./import dna_layer./g' {} \;
```

**Windows (PowerShell):**
```powershell
Get-ChildItem -Path your_project\dna_layer -Recurse -Filter *.py | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.', 'from dna_layer.' -replace 'import src\.', 'import dna_layer.' | Set-Content $_.FullName
}
```

### Option 2: Manual Update

Search for all occurrences of:
- `from src.` → `from dna_layer.`
- `import src.` → `import dna_layer.`

---

## Step 3: Install Dependencies

Add to your project's `requirements.txt`:

```txt
# Core dependencies
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
pyyaml>=6.0.1  # Required for bypass system config file support
psutil>=5.9.0  # For CPU throttling and system monitoring

# ML dependencies (for XGBoost and predictive indexing)
scikit-learn>=1.0.0
xgboost>=1.5.0
numpy>=1.21.0

# Type stubs (recommended for development)
types-psycopg2>=2.9.21
types-psutil>=7.1.3
```

Install:
```bash
pip install -r requirements.txt
```

---

## Step 4: Configure Database Connection

### Set Environment Variables

Create `.env` file or set environment variables:

```bash
# PostgreSQL connection
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password

# Or Supabase connection string
SUPABASE_DB_URL=postgresql://user:password@host:port/database

# Optional
ENVIRONMENT=production  # Enables SSL requirement
```

### Initialize Connection Pool

In your application startup:

```python
from dna_layer.db import init_connection_pool

# Initialize connection pool
init_connection_pool(min_conn=2, max_conn=20)
```

### Configure Adapters (Production - Critical)

**⚠️ CRITICAL for Production**: Configure adapters to integrate with your host application utilities.

```python
# your_project/app.py (or main.py, startup script, etc.)
from dna_layer.adapters import configure_adapters
import datadog
import sentry_sdk

# Your existing database connection pool
from your_project.db import get_db_pool  # Your existing pool

# Configure adapters (do this ONCE at application startup)
configure_adapters(
    monitoring=datadog.statsd,      # Host monitoring (CRITICAL for production)
    database=get_db_pool(),         # Your existing database pool (optional but recommended)
    error_tracker=sentry_sdk,       # Host error tracking (recommended)
    validate=True                   # Validate interfaces (default: True)
)
```

**Why This Matters**: Internal monitoring loses alerts on restart - host monitoring is required for production.

**See**: `docs/installation/ADAPTERS_USAGE_GUIDE.md` for complete integration guide.

---

## Step 5: Choose Integration Option

### Option 1: Direct Integration (Modify Code)

**Best for:** Quick integration, simple schemas

1. **Modify `dna_layer/schema.py`:** Edit `create_business_tables()` function to match your schema
2. **Modify `dna_layer/genome.py`:** Edit `bootstrap_genome_catalog()` function
3. **Initialize in your application:**

```python
from dna_layer.schema import init_schema
from dna_layer.genome import bootstrap_genome_catalog

# One-time setup
init_schema()  # Creates metadata tables + your business tables
bootstrap_genome_catalog()  # Registers your schema
```

### Option 2: Configuration-Based (Use Config File)

**Best for:** Flexible schemas, no code changes for schema updates

1. **Create `schema_config.yaml`:** Define your schema in YAML
2. **Initialize using schema loader:**

```python
from dna_layer.schema.loader import load_schema
from dna_layer.schema import init_schema_from_config
from dna_layer.genome import bootstrap_genome_catalog_from_schema

# Load schema from config
schema_config = load_schema('schema_config.yaml')

# Initialize using config
init_schema_from_config(schema_config)
bootstrap_genome_catalog_from_schema(schema_config)
```

---

## Step 6: Integrate Query Logging

Add query statistics logging to your ORM/query layer.

### Example: Raw SQL

```python
from dna_layer.stats import log_query_stat
import time

def query_users_by_email(email, tenant_id):
    start_time = time.time()
    
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM users WHERE email = %s AND tenant_id = %s",
            (email, tenant_id)
        )
        results = cursor.fetchall()
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Log query stats
    log_query_stat(
        tenant_id=tenant_id,
        table_name='users',
        field_name='email',
        query_type='SELECT',
        duration_ms=duration_ms
    )
    
    return results
```

---

## Step 7: Set Up Auto-Indexer

Schedule the auto-indexer to run periodically.

### Option A: Background Job (Celery)

```python
from celery import Celery
from dna_layer.auto_indexer import analyze_and_create_indexes

@celery_app.task
def run_auto_indexer():
    """Run auto-indexer every 6 hours"""
    analyze_and_create_indexes(tenant_id=None)  # All tenants

# Schedule: Every 6 hours
run_auto_indexer.apply_async(countdown=21600)
```

### Option B: Cron Job

```bash
# Add to crontab (Linux/Mac)
0 */6 * * * cd /path/to/your_project && python -c "from dna_layer.auto_indexer import analyze_and_create_indexes; analyze_and_create_indexes()"
```

---

## Complete File List Summary

### If Copying Entire `src/` Directory

**Just copy everything:**
```bash
cp -r src your_project/dna_layer
```

### If Selective Copy

**Minimum required files:**
- Core: `db.py`, `genome.py`, `expression.py`, `auto_indexer.py`, `stats.py`, `audit.py`, `schema.py`, `validation.py`, `type_definitions.py`
- Algorithms: All 12 files in `algorithms/` directory
- Database: `database/` directory structure
- Schema: `schema/` directory structure (if using Option 2)

**Recommended additional files:**
- All query optimization files
- All production features
- All advanced features
- Adapter system

---

## File Placement Summary

### Where to Place Files

```
your_project/
├── dna_layer/              # All IndexPilot files go here
│   ├── __init__.py
│   ├── algorithms/         # All 12 algorithms
│   │   ├── __init__.py
│   │   └── [12 algorithm files]
│   ├── database/          # Database adapters
│   │   ├── __init__.py
│   │   └── adapters/
│   ├── schema/            # Schema loading
│   │   ├── __init__.py
│   │   └── [schema files]
│   ├── db.py
│   ├── genome.py
│   ├── expression.py
│   ├── auto_indexer.py
│   ├── stats.py
│   ├── audit.py
│   ├── schema.py
│   ├── validation.py
│   └── [all other files]
├── schema_config.yaml      # For Option 2 only
├── .env                    # Database credentials
└── requirements.txt        # Dependencies
```

### Import in Your Code

```python
# Import from dna_layer module
from dna_layer.db import get_connection
from dna_layer.stats import log_query_stat
from dna_layer.auto_indexer import analyze_and_create_indexes
from dna_layer.algorithms.cert import validate_cardinality_with_cert
```

---

## Important Notes

### Algorithms Are Integrated

All 12 algorithms are **automatically used** by the system:
- **CERT** - Used in auto_indexer for cardinality validation
- **QPG** - Used in query_analyzer for plan guidance
- **Cortex** - Used in composite_index_detection
- **Predictive Indexing** - Used in auto_indexer for ML predictions
- **XGBoost** - Used in pattern detection and maintenance
- **Others** - Used in index_type_selection and pattern_detection

**You don't need to call them directly** - they're integrated into the core system.

### Dependencies

The system requires:
- **psycopg2-binary** - PostgreSQL driver
- **pyyaml** - Configuration file support
- **psutil** - CPU throttling
- **scikit-learn, xgboost, numpy** - ML algorithms

---

## Troubleshooting

### Issue: Import Errors After Copy

**Solution:** 
1. Ensure all `from src.` changed to `from dna_layer.`
2. Check `__init__.py` files exist in all directories
3. Verify directory structure matches

### Issue: Algorithm Import Errors

**Solution:**
- Ensure all 12 algorithm files are copied
- Check `algorithms/__init__.py` exists
- Verify import paths are updated

### Issue: Missing Dependencies

**Solution:**
- Install all dependencies from `requirements.txt`
- Check ML dependencies (scikit-learn, xgboost) are installed

---

## Next Steps

1. **Review Documentation:**
   - `docs/installation/DEPLOYMENT_INTEGRATION_GUIDE.md` - Advanced integration examples
   - `docs/installation/ADAPTERS_USAGE_GUIDE.md` - Adapter integration
   - `docs/PRODUCTION_HARDENING.md` - Production deployment

2. **Customize:**
   - Modify schema for your tables
   - Adjust auto-indexer thresholds
   - Configure monitoring
   - Set up bypass configuration file

3. **Production:**
   - Set up proper environment variables
   - Configure connection pooling
   - Schedule auto-indexer
   - Set up monitoring
   - Configure bypass system for safety

---

## Quick Reference

### Essential Commands

```bash
# Copy entire src/ directory (recommended)
cp -r src your_project/dna_layer

# Update imports
find your_project/dna_layer -name "*.py" -type f -exec sed -i 's/from src\./from dna_layer./g' {} \;

# Install dependencies
pip install -r requirements.txt

# Initialize (one-time)
python -c "from dna_layer.schema import init_schema; from dna_layer.genome import bootstrap_genome_catalog; init_schema(); bootstrap_genome_catalog()"
```

---

**For detailed integration examples, see `docs/installation/DEPLOYMENT_INTEGRATION_GUIDE.md`.**

