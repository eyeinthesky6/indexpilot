# How to Install - Copy Over Mode
**Date**: 05-12-2025 (Updated: 08-12-2025)  
**Purpose**: Step-by-step guide for copying IndexPilot files into your project

---

## Overview

This guide explains how to integrate IndexPilot into your existing project using **copy-over mode**. The system includes 12 academic algorithms and many advanced features.

**Two Copy Methods:**
- **Method A: Copy Entire `src/` Directory** (Recommended) - Simplest, includes everything
- **Method B: Selective File Copy** - Copy only specific files you need

**Two Integration Options:**
- **Option 1: Direct Integration** - Copy files and modify schema in code
- **Option 2: Configuration-Based** - Copy files and use schema config file

---

## Prerequisites

- Python 3.8+
- PostgreSQL 12+ (or other supported database)
- Existing database with your application schema
- Your project directory structure

---

## Step 1: Copy Required Files

### Method A: Copy Entire `src/` Directory (Recommended)

**Best for:** Most users, ensures you have all dependencies including all 12 algorithms

```bash
# Clone or download IndexPilot repository
git clone https://github.com/eyeinthesky6/indexpilot
cd indexpilot

# Copy entire src/ directory to your project
cp -r src your_project/indexpilot

# Or on Windows:
xcopy /E /I src your_project\indexpilot
```

**Then update imports** (see Step 1.5 below).

### Method B: Selective File Copy (Advanced)

**Best for:** Minimal installations, custom integrations

#### Essential Core Files (Required)

```bash
# Create directory in your project
mkdir -p your_project/indexpilot
mkdir -p your_project/indexpilot/algorithms
mkdir -p your_project/indexpilot/database/adapters
mkdir -p your_project/indexpilot/schema

# Copy essential core files
cp src/db.py your_project/indexpilot/
cp src/genome.py your_project/indexpilot/
cp src/expression.py your_project/indexpilot/
cp src/auto_indexer.py your_project/indexpilot/
cp src/stats.py your_project/indexpilot/
cp src/audit.py your_project/indexpilot/
cp src/schema.py your_project/indexpilot/
cp src/validation.py your_project/indexpilot/
cp src/type_definitions.py your_project/indexpilot/  # Required for types
```

#### Algorithms (Required - All 12 Used by System)

**All 12 algorithms are automatically used by the system**, so copy all of them:

```bash
# Copy all algorithms
cp src/algorithms/__init__.py your_project/indexpilot/algorithms/
cp src/algorithms/cert.py your_project/indexpilot/algorithms/
cp src/algorithms/qpg.py your_project/indexpilot/algorithms/
cp src/algorithms/cortex.py your_project/indexpilot/algorithms/
cp src/algorithms/predictive_indexing.py your_project/indexpilot/algorithms/
cp src/algorithms/xgboost_classifier.py your_project/indexpilot/algorithms/
cp src/algorithms/pgm_index.py your_project/indexpilot/algorithms/
cp src/algorithms/alex.py your_project/indexpilot/algorithms/
cp src/algorithms/radix_string_spline.py your_project/indexpilot/algorithms/
cp src/algorithms/fractal_tree.py your_project/indexpilot/algorithms/
cp src/algorithms/idistance.py your_project/indexpilot/algorithms/
cp src/algorithms/bx_tree.py your_project/indexpilot/algorithms/
cp src/algorithms/constraint_optimizer.py your_project/indexpilot/algorithms/
```

#### Query Optimization Files (Recommended)

```bash
cp src/query_analyzer.py your_project/indexpilot/
cp src/query_executor.py your_project/indexpilot/
cp src/query_interceptor.py your_project/indexpilot/
cp src/query_patterns.py your_project/indexpilot/
cp src/query_timeout.py your_project/indexpilot/
cp src/query_pattern_learning.py your_project/indexpilot/
```

#### Production Features (Recommended)

```bash
# Production safety
cp src/rollback.py your_project/indexpilot/
cp src/config_loader.py your_project/indexpilot/
cp src/bypass_config.py your_project/indexpilot/
cp src/bypass_status.py your_project/indexpilot/
cp src/production_config.py your_project/indexpilot/
cp src/production_cache.py your_project/indexpilot/

# Monitoring and health
cp src/monitoring.py your_project/indexpilot/
cp src/health_check.py your_project/indexpilot/
cp src/error_handler.py your_project/indexpilot/
cp src/resilience.py your_project/indexpilot/

# Rate limiting and throttling
cp src/rate_limiter.py your_project/indexpilot/
cp src/cpu_throttle.py your_project/indexpilot/
cp src/lock_manager.py your_project/indexpilot/
cp src/maintenance_window.py your_project/indexpilot/

# Performance monitoring
cp src/write_performance.py your_project/indexpilot/
cp src/pattern_detection.py your_project/indexpilot/
cp src/workload_analysis.py your_project/indexpilot/
```

### Integration Files (For Production - Recommended)

**⚠️ IMPORTANT**: For production deployments, copy the adapter system to integrate with your host application utilities:

```bash
# Adapter system (CRITICAL for production)
cp src/adapters.py your_project/indexpilot/
```

**Why This Matters**: The adapter system allows integration with your host monitoring (Datadog, Prometheus, etc.), database connections, error tracking (Sentry, Rollbar), and audit systems. **Internal monitoring loses alerts on restart** - host monitoring is critical for production.

**See**: `docs/ADAPTERS_USAGE_GUIDE.md` for complete integration guide.

### New Extensibility Files (For Option 2)

If using **Option 2: Configuration-Based**, also copy:

```bash
# Schema abstraction
cp src/schema/loader.py your_project/indexpilot/schema/
cp src/schema/validator.py your_project/indexpilot/schema/
cp src/schema/__init__.py your_project/indexpilot/schema/

# Database adapter (PostgreSQL)
cp src/database/adapters/base.py your_project/indexpilot/database/adapters/
cp src/database/adapters/postgresql.py your_project/indexpilot/database/adapters/
cp src/database/adapters/__init__.py your_project/indexpilot/database/adapters/
cp src/database/detector.py your_project/indexpilot/database/
cp src/database/__init__.py your_project/indexpilot/database/
```

### Step 1.5: Update Import Statements

After copying files, update all imports from `src.` to `indexpilot.`:

**Linux/Mac:**
```bash
find your_project/indexpilot -name "*.py" -type f -exec sed -i 's/from src\./from indexpilot./g' {} \;
find your_project/indexpilot -name "*.py" -type f -exec sed -i 's/import src\./import indexpilot./g' {} \;
```

**Windows (PowerShell):**
```powershell
Get-ChildItem -Path your_project\indexpilot -Recurse -Filter *.py | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.', 'from indexpilot.' -replace 'import src\.', 'import indexpilot.' | Set-Content $_.FullName
}
```

**Manual:** Search and replace:
- `from src.` → `from indexpilot.`
- `import src.` → `import indexpilot.`

### Directory Structure After Copy

Your project should have:

```
your_project/
├── indexpilot/
│   ├── __init__.py              # Create this file (can be empty)
│   ├── algorithms/              # All 12 algorithms
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
│   ├── database/                # Database adapters
│   │   ├── __init__.py
│   │   ├── detector.py
│   │   └── adapters/
│   │       ├── __init__.py
│   │       ├── base.py
│   │       └── postgresql.py
│   ├── schema/                  # Schema loading (for Option 2)
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── validator.py
│   ├── db.py
│   ├── genome.py
│   ├── expression.py
│   ├── auto_indexer.py
│   ├── stats.py
│   ├── audit.py
│   ├── schema.py
│   ├── validation.py
│   └── [all other files]
└── schema_config.yaml           # For Option 2 (create this)
```

---

## Step 2: Install Dependencies

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
```

**Type Stubs (Recommended for Development)**:
```txt
types-psycopg2>=2.9.21  # Type stubs for psycopg2 (enables better type checking)
types-psutil>=7.1.3     # Type stubs for psutil (enables better type checking)
```

**Note**: PyYAML is now required (not optional) for the bypass system configuration file support. The system will work without it but will use defaults and log warnings.

Install:

**Important**: It's recommended to use a virtual environment. If you haven't created one yet:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (Git Bash):
source venv/Scripts/activate
# On Windows (CMD):
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

Then install dependencies:
```bash
pip install -r requirements.txt
```

**Why Type Stubs?**
- Better IDE autocomplete and type checking
- Catches type errors at development time
- Improves code quality and maintainability

---

## Step 3: Configure Database Connection

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
from indexpilot.db import init_connection_pool

# Initialize connection pool
init_connection_pool(min_conn=2, max_conn=20)
```

### Configure Adapters (Production - Recommended)

**⚠️ CRITICAL for Production**: Configure adapters to integrate with your host application utilities.

**What "Configure" Means**: When you use IndexPilot in your codebase, you need to tell it how to integrate with your existing systems (monitoring, database, error tracking). This is done by calling `configure_adapters()` at your application startup.

**Where to Configure**: In your application's startup code (e.g., `main.py`, `app.py`, `__init__.py`, or startup script):

```python
# your_project/app.py (or main.py, startup script, etc.)
from indexpilot.adapters import configure_adapters
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

# Now IndexPilot will use your host utilities
```

**Complete Example - Application Startup**:

```python
# your_project/main.py
import os
from indexpilot.db import init_connection_pool
from indexpilot.adapters import configure_adapters
import datadog
import sentry_sdk

def startup():
    """Application startup - configure IndexPilot"""
    
    # 1. Initialize IndexPilot's own connection pool (if not using host pool)
    init_connection_pool(min_conn=2, max_conn=20)
    
    # 2. Configure adapters to use your host utilities
    configure_adapters(
        monitoring=datadog.statsd,      # Your monitoring system
        database=your_existing_db_pool, # Your existing pool (optional)
        error_tracker=sentry_sdk,       # Your error tracking
        validate=True                    # Check interfaces match (recommended)
    )
    
    # 3. Verify adapters are working
    from indexpilot.adapters import get_monitoring_adapter, get_adapter_fallback_metrics
    
    monitoring = get_monitoring_adapter()
    if monitoring.is_healthy():
        print("✅ Monitoring adapter configured and healthy")
    else:
        print("⚠️ Monitoring adapter not healthy - check configuration")
    
    # 4. Check for any fallback metrics (adapter issues)
    fallback_metrics = get_adapter_fallback_metrics()
    if fallback_metrics:
        print(f"⚠️ Adapter fallbacks detected: {fallback_metrics}")

if __name__ == '__main__':
    startup()
    # ... rest of your application
```

**Why This Matters**:
- ⚠️ **CRITICAL**: Internal monitoring loses alerts on restart - host monitoring is required for production
- 💰 **Efficiency**: Reuse host database connections (reduces resource waste, inherits RLS/RBAC)
- 📊 **Observability**: Unified monitoring and error tracking
- ✅ **Security**: Using host database pool inherits RLS/RBAC policies automatically

**Full Guide**: See `docs/installation/ADAPTERS_USAGE_GUIDE.md` for complete integration examples.

**Note**: Adapters are optional - system works without them, but production deployments should configure at least the monitoring adapter.

---

## Step 4: Choose Integration Option

### Option 1: Direct Integration (Modify Code)

**Best for:** Quick integration, simple schemas

1. **Modify `indexpilot/schema.py`:**

   Edit `create_business_tables()` function to match your schema:

   ```python
   def create_business_tables(cursor):
       """Create YOUR business tables"""
       
       # Example: Users table
       cursor.execute("""
           CREATE TABLE IF NOT EXISTS users (
               id SERIAL PRIMARY KEY,
               tenant_id INTEGER NOT NULL,
               email TEXT NOT NULL,
               name TEXT,
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )
       """)
       
       # Add your other tables...
   ```

2. **Modify `indexpilot/genome.py`:**

   Edit `bootstrap_genome_catalog()` function:

   ```python
   def bootstrap_genome_catalog():
       """Bootstrap with YOUR schema"""
       
       genome_fields = [
           # Your tables
           ('users', 'id', 'SERIAL', True, True, True, 'core'),
           ('users', 'email', 'TEXT', True, True, True, 'core'),
           ('users', 'name', 'TEXT', False, True, True, 'core'),
           # ... more fields
       ]
       
       # Rest of function stays the same...
   ```

3. **Initialize in your application:**

   ```python
   from indexpilot.schema import init_schema
   from indexpilot.genome import bootstrap_genome_catalog
   
   # One-time setup
   init_schema()  # Creates metadata tables + your business tables
   bootstrap_genome_catalog()  # Registers your schema
   ```

### Option 2: Configuration-Based (Use Config File)

**Best for:** Flexible schemas, no code changes for schema updates

1. **Create `schema_config.yaml`:**

   ```yaml
   schema:
     name: "my_app_schema"
     version: "1.0"
     tables:
       - name: "users"
         fields:
           - name: "id"
             type: "SERIAL"
             required: true
             indexable: true
             default_expression: true
             feature_group: "core"
           - name: "email"
             type: "TEXT"
             required: true
             indexable: true
             default_expression: true
             feature_group: "core"
           - name: "name"
             type: "TEXT"
             required: false
             indexable: true
             default_expression: true
             feature_group: "core"
         indexes:
           - fields: ["tenant_id"]
             type: "btree"
       - name: "products"
         fields:
           # ... define your fields
   ```

2. **Initialize using schema loader:**

   ```python
   from indexpilot.schema.loader import load_schema
   from indexpilot.schema import init_schema_from_config
   from indexpilot.genome import bootstrap_genome_catalog_from_schema
   
   # Load schema from config
   schema_config = load_schema('schema_config.yaml')
   
   # Initialize using config
   init_schema_from_config(schema_config)
   bootstrap_genome_catalog_from_schema(schema_config)
   ```

---

## Step 5: Integrate Query Logging

Add query statistics logging to your ORM/query layer.

### Example: Raw SQL

```python
from indexpilot.stats import log_query_stat
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

### Example: Django Middleware

```python
from django.utils.deprecation import MiddlewareMixin
from indexpilot.stats import log_query_stat
import time

class DNAQueryMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._dna_start_time = time.time()
    
    def process_response(self, request, response):
        if hasattr(request, '_dna_start_time'):
            duration_ms = (time.time() - request._dna_start_time) * 1000
            log_query_stat(
                tenant_id=getattr(request, 'tenant_id', None),
                table_name='api_request',
                field_name=None,
                query_type='SELECT',
                duration_ms=duration_ms
            )
        return response
```

### Example: SQLAlchemy Events

```python
from sqlalchemy import event
from sqlalchemy.engine import Engine
from indexpilot.stats import log_query_stat
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration_ms = (time.time() - context._query_start_time) * 1000
    table_name = extract_table_name(statement)  # Your parsing logic
    
    log_query_stat(
        tenant_id=get_current_tenant_id(),
        table_name=table_name,
        field_name=None,
        query_type='SELECT',
        duration_ms=duration_ms
    )
```

---

## Step 6: Set Up Auto-Indexer

Schedule the auto-indexer to run periodically.

### Option A: Background Job (Celery)

```python
from celery import Celery
from indexpilot.auto_indexer import analyze_and_create_indexes

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
0 */6 * * * cd /path/to/your_project && python -c "from indexpilot.auto_indexer import analyze_and_create_indexes; analyze_and_create_indexes()"
```

### Option C: Application Startup (Development)

```python
# In your application startup (development only)
from threading import Timer
from indexpilot.auto_indexer import analyze_and_create_indexes

def run_auto_indexer_periodically():
    analyze_and_create_indexes()
    # Schedule next run (6 hours)
    Timer(21600, run_auto_indexer_periodically).start()

# Start on application startup
run_auto_indexer_periodically()
```

---

## Step 7: Verify Installation

### Test Database Connection

```python
from indexpilot.db import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    print("Database connection successful!")
```

### Test Schema Initialization

```python
from indexpilot.schema import init_schema

# This should create metadata tables
init_schema()
print("Schema initialized successfully!")
```

### Test Genome Catalog

```python
from indexpilot.genome import get_all_genome_fields

fields = get_all_genome_fields()
print(f"Genome catalog has {len(fields)} fields")
```

### Test Query Logging

```python
from indexpilot.stats import log_query_stat

log_query_stat(
    tenant_id=1,
    table_name='test',
    field_name='test_field',
    query_type='SELECT',
    duration_ms=10.5
)
print("Query stat logged successfully!")
```

---

## File Placement Summary

### Where to Place Files

```
your_project/
├── indexpilot/              # All IndexPilot files go here
│   ├── __init__.py
│   ├── db.py
│   ├── genome.py
│   ├── expression.py
│   ├── auto_indexer.py
│   ├── stats.py
│   ├── audit.py
│   ├── schema.py
│   └── [other files]
├── schema_config.yaml      # For Option 2 only
├── .env                    # Database credentials
└── requirements.txt        # Dependencies
```

### Import in Your Code

```python
# Import from indexpilot module
from indexpilot.db import get_connection
from indexpilot.stats import log_query_stat
from indexpilot.auto_indexer import analyze_and_create_indexes
```

---

## Troubleshooting

### Issue: Import Errors

**Solution:** 
- Ensure `indexpilot/__init__.py` exists (can be empty)
- Check all imports updated from `src.` to `indexpilot.`
- Verify all algorithm files are copied if using selective copy
- Check `algorithms/__init__.py` exists

### Issue: Database Connection Fails

**Solution:** 
- Check environment variables are set
- Verify database credentials
- Ensure PostgreSQL is running

### Issue: Schema Mismatch

**Solution:**
- Verify `schema.py` matches your actual database schema
- Re-run `init_schema()` if needed
- Check genome catalog matches your fields
- Clear validation cache if schema changed: `from indexpilot.validation import clear_validation_cache; clear_validation_cache()`
- Clear tenant field cache if needed: `from indexpilot.auto_indexer import clear_tenant_field_cache; clear_tenant_field_cache()`

### Issue: Indexes Not Being Created

**Solution:**
- Verify query stats are being logged
- Check query volume meets thresholds
- Review mutation log for errors

### Issue: Algorithm Import Errors

**Solution:**
- Ensure all 12 algorithm files are copied
- Check `algorithms/__init__.py` exists
- Verify import paths are updated (`from indexpilot.algorithms.` not `from src.algorithms.`)

### Issue: Missing ML Dependencies

**Solution:**
- Install ML dependencies: `pip install scikit-learn xgboost numpy`
- Check XGBoost version compatibility

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

### System Works with Any Schema ✅

The system is **fully extensible** and works with any production database schema:
- ✅ **No hardcoded schema assumptions** - Dynamic validation from genome_catalog
- ✅ **Multi-tenant or single-tenant** - Auto-detects tenant field presence
- ✅ **Configurable foreign keys** - Define in schema config (Option 2)
- ✅ **No tenants table required** - Works with or without it

### Performance Optimizations

The system includes built-in caching for performance:
- **Validation cache**: Caches allowed tables/fields from genome_catalog
- **Tenant field cache**: Caches tenant field detection results
- **Database adapter cache**: Caches database type detection

If you modify your schema, clear caches:
```python
from indexpilot.validation import clear_validation_cache
from indexpilot.auto_indexer import clear_tenant_field_cache

clear_validation_cache()  # After schema changes
clear_tenant_field_cache()  # After schema changes
```

## Bypass System Configuration

The system includes a comprehensive bypass mechanism for production safety. This allows you to disable system features if they cause issues.

### Configuration File

Create `indexpilot_config.yaml` in your project root (or set `INDEXPILOT_CONFIG_FILE` environment variable):

```yaml
# indexpilot_config.yaml
bypass:
  features:
    auto_indexing:
      enabled: true
      reason: ""
    stats_collection:
      enabled: true
      reason: ""
    expression_checks:
      enabled: true
      reason: ""
    mutation_logging:
      enabled: true
      reason: ""
  system:
    enabled: false
    reason: ""
  startup:
    skip_initialization: false
    reason: ""
```

**See `BYPASS_SYSTEM_CONFIG_DESIGN.md` for complete configuration options.**

### Environment Variables

You can override config file settings with environment variables:

```bash
# Complete system bypass
export INDEXPILOT_BYPASS_MODE=true

# Feature-level bypasses
export INDEXPILOT_BYPASS_STATS_COLLECTION=false
export INDEXPILOT_BYPASS_AUTO_INDEXING=false
export INDEXPILOT_BYPASS_EXPRESSION_CHECKS=false
export INDEXPILOT_BYPASS_MUTATION_LOGGING=false

# Skip initialization
export INDEXPILOT_BYPASS_SKIP_INIT=true
```

### Checking Bypass Status

```python
# Programmatic check
from indexpilot.rollback import get_system_status
status = get_system_status()
print(status['summary']['any_bypass_active'])

# Human-readable display
from indexpilot.bypass_status import format_bypass_status_for_display
print(format_bypass_status_for_display())

# Log status (for visibility)
from indexpilot.bypass_status import log_bypass_status
log_bypass_status(include_details=True)
```

**The system automatically logs bypass status at startup and periodically (every hour) for visibility.**

### Runtime Bypass Control

```python
from indexpilot.rollback import (
    disable_system,
    disable_stats_collection,
    enable_complete_bypass
)

# Disable specific feature
disable_stats_collection("High write load detected")

# Complete system bypass
enable_complete_bypass("Emergency: Critical failure")
```

**See `BYPASS_SYSTEM_ANALYSIS.md` and `BYPASS_SYSTEM_VISIBILITY_IMPLEMENTATION.md` for complete documentation.**

## Next Steps

1. **Review Documentation:**
   - `EXTENSIBILITY_AUDIT.md` - Architecture details
   - `DEPLOYMENT_INTEGRATION_GUIDE.md` - Advanced integration examples
   - `EXTENSIBILITY_FIXES.md` - Recent extensibility improvements
   - `BYPASS_SYSTEM_ANALYSIS.md` - Bypass system overview
   - `BYPASS_SYSTEM_CONFIG_DESIGN.md` - Configuration details

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
# Copy files
cp src/db.py your_project/indexpilot/
cp src/genome.py your_project/indexpilot/
# ... (see Step 1)

# Install dependencies (ensure virtual environment is activated)
pip install psycopg2-binary python-dotenv pyyaml

# Initialize (one-time)
python -c "from indexpilot.schema import init_schema; from indexpilot.genome import bootstrap_genome_catalog; init_schema(); bootstrap_genome_catalog()"
```

### Essential Code

```python
# 1. Initialize (at application startup)
from indexpilot.db import init_connection_pool
from indexpilot.schema import init_schema
from indexpilot.genome import bootstrap_genome_catalog
from indexpilot.adapters import configure_adapters
import datadog  # Your monitoring system

# Initialize connection pool (if not using host pool)
init_connection_pool()

# Configure adapters (CRITICAL for production)
configure_adapters(
    monitoring=datadog.statsd,  # Your monitoring
    # database=your_db_pool,   # Optional: your existing pool
    # error_tracker=sentry_sdk # Optional: your error tracking
)

# Initialize schema (one-time setup)
init_schema()
bootstrap_genome_catalog()

# 2. Use in your application
from indexpilot.stats import log_query_stat
from indexpilot.auto_indexer import analyze_and_create_indexes
from indexpilot.query_executor import execute_query

# Log query stats
log_query_stat(
    tenant_id=1,
    table_name='users',
    field_name='email',
    query_type='SELECT',
    duration_ms=45.2
)

# Execute queries (with automatic interception and caching)
results = execute_query(
    "SELECT * FROM users WHERE email = %s",
    params=('user@example.com',),
    tenant_id='1'
)

# Run auto-indexer (periodically in background)
analyze_and_create_indexes()
```

---

For detailed integration examples, see `DEPLOYMENT_INTEGRATION_GUIDE.md`.

