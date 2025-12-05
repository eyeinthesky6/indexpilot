# Deployment and Integration Guide
**Date**: 05-12-2025  
**Purpose**: Step-by-step guide for integrating DNA system into existing projects

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Integration Approaches](#integration-approaches)
3. [File Copy Checklist](#file-copy-checklist)
4. [Configuration Guide](#configuration-guide)
5. [Integration Examples](#integration-examples)
6. [Production Deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+ (or other supported database)
- Existing database with your application schema

### 5-Minute Integration

1. **Copy core files to your project:**
   
   **For complete file copy instructions, see `docs/installation/HOW_TO_INSTALL.md`**
   
   Quick summary:
   ```bash
   mkdir -p your_project/dna_layer
   cp src/db.py src/genome.py src/expression.py src/auto_indexer.py \
      src/stats.py src/schema.py src/validation.py your_project/dna_layer/
   ```

2. **Install dependencies:**
   ```bash
   pip install psycopg2-binary python-dotenv
   ```

3. **Set environment variables:**
   ```bash
   export DB_HOST=localhost
   export DB_PORT=5432
   export DB_NAME=your_database
   export DB_USER=your_user
   export DB_PASSWORD=your_password
   ```

4. **Initialize DNA system:**
   ```python
   # your_project/init_dna.py
   from dna_layer.schema import init_schema
   from dna_layer.genome import bootstrap_genome_catalog
   
   # Initialize metadata tables
   init_schema()
   
   # Bootstrap genome catalog (modify for your schema)
   bootstrap_genome_catalog()
   ```

5. **Use in your application:**
   ```python
   from dna_layer.stats import log_query_stat
   from dna_layer.auto_indexer import analyze_and_create_indexes
   
   # Log query performance (batched automatically)
   log_query_stat(
       tenant_id=1,
       table_name='users',
       field_name='email',
       query_type='READ',
       duration_ms=45.2
   )
   
   # Auto-create indexes (run periodically in background)
   analyze_and_create_indexes()
   ```
   
   **Note**: `query_stats.py` is now `stats.py` in current codebase. See `docs/installation/HOW_TO_INSTALL.md` for complete file list.

---

## Integration Approaches

### Approach 1: Direct Integration (Simplest)

**Best for:** Small to medium projects, single database

**Steps:**
1. Copy DNA files into your project
2. Modify schema definitions for your tables
3. Initialize on application startup
4. Integrate query logging into your ORM/query layer

**Pros:**
- Simple and straightforward
- No external dependencies
- Full control

**Cons:**
- Requires code modifications
- Schema changes need code updates

### Approach 2: Configuration-Based (Recommended)

**Best for:** Projects wanting flexibility without code changes

**Steps:**
1. Copy DNA files + schema loader
2. Create `schema_config.yaml` with your schema
3. Use schema loader to bootstrap

**Pros:**
- Schema changes via config file
- No code changes for schema updates
- More maintainable

**Cons:**
- Requires schema loader implementation (see Extensibility Audit)

### Approach 3: Standalone Service

**Best for:** Large deployments, multiple applications

**Steps:**
1. Deploy DNA system as separate service
2. Configure to monitor your database
3. Use API for genome/expression management

**Pros:**
- Centralized management
- Multiple apps can use same system
- Independent scaling

**Cons:**
- More complex setup
- Requires service infrastructure

---

## File Copy Checklist

### Required Core Files

#### **Essential (Must Have)**
```
✅ src/db.py                    # Database connection pooling
✅ src/genome.py                # Genome catalog operations
✅ src/expression.py            # Expression profile management
✅ src/auto_indexer.py          # Auto-indexing logic
✅ src/stats.py                  # Query statistics collection
✅ src/audit.py                  # Mutation tracking and audit trail
✅ src/schema.py                # Schema initialization (modify for your schema)
```

#### **Recommended (Should Have)**
```
✅ src/query_optimizer.py        # Query optimization
✅ src/query_analyzer.py         # Query analysis
✅ src/lock_manager.py           # Locking for concurrent operations
✅ src/monitoring.py             # System monitoring
✅ src/error_handler.py          # Error handling
```

#### **Optional (Nice to Have)**
```
⚪ src/index_cleanup.py          # Index cleanup utilities
⚪ src/index_scheduler.py        # Scheduled indexing
⚪ src/maintenance.py            # Maintenance operations
⚪ src/health_check.py           # Health check endpoints
⚪ src/reporting.py              # Performance reporting
```

### Dependencies

**Required:**
```txt
psycopg2-binary>=2.9.0
python-dotenv>=1.0.0
```

**Optional:**
```txt
psutil>=5.9.0          # For system monitoring
pytest>=7.4.0          # For testing
```

---

## Configuration Guide

### Database Configuration

#### **Environment Variables**
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

#### **Connection Pool Configuration**
```python
from dna_layer.db import init_connection_pool

# Initialize with custom pool size
init_connection_pool(min_conn=2, max_conn=20)
```

### Schema Configuration

#### **Option 1: Modify `genome.py` Directly**

Edit `bootstrap_genome_catalog()` in `genome.py`:

```python
def bootstrap_genome_catalog():
    """Bootstrap with YOUR schema"""
    genome_fields = [
        # Your tables
        ('users', 'id', 'SERIAL', True, True, True, 'core'),
        ('users', 'email', 'TEXT', True, True, True, 'core'),
        ('users', 'name', 'TEXT', False, True, True, 'core'),
        ('products', 'id', 'SERIAL', True, True, True, 'core'),
        ('products', 'name', 'TEXT', True, True, True, 'core'),
        # ... more fields
    ]
    # ... rest of function
```

#### **Option 2: Use Schema Config (Future)**

```yaml
# schema_config.yaml
schema:
  tables:
    - name: "users"
      fields:
        - name: "id"
          type: "SERIAL"
          required: true
          indexable: true
```

### Auto-Indexer Configuration

```python
from dna_layer.auto_indexer import analyze_and_create_indexes

# Run for specific tenant
analyze_and_create_indexes(tenant_id=1)

# Run for all tenants
analyze_and_create_indexes(tenant_id=None)

# With custom thresholds
from dna_layer.auto_indexer import get_optimization_strategy

strategy = get_optimization_strategy(
    min_queries_per_hour=100,
    cost_benefit_ratio=2.0
)
```

---

## Integration Examples

### Example 1: Django Integration

```python
# your_project/django_app/dna_integration.py
from django.db import connection
from django.core.management.base import BaseCommand
from dna_layer.stats import log_query_stat
from dna_layer.auto_indexer import analyze_and_create_indexes
import time

class DNAQueryMiddleware:
    """Django middleware to log queries"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration_ms = (time.time() - start_time) * 1000
        
        # Log query stats (extract from Django query log)
        # This is simplified - you'd parse Django's query log
        log_query_stat(
            tenant_id=getattr(request, 'tenant_id', None),
            table_name='unknown',  # Parse from query
            field_name=None,
            query_type='SELECT',
            duration_ms=duration_ms
        )
        
        return response

# Background task (Celery/cron)
def run_auto_indexer():
    analyze_and_create_indexes()
```

### Example 2: Flask Integration

```python
# your_project/app.py
from flask import Flask, g
from dna_layer.stats import log_query_stat
from dna_layer.auto_indexer import analyze_and_create_indexes
import time

app = Flask(__name__)

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    duration_ms = (time.time() - g.start_time) * 1000
    
    # Log query stats
    log_query_stat(
        tenant_id=g.get('tenant_id'),
        table_name='api_request',
        field_name=None,
        query_type='SELECT',
        duration_ms=duration_ms
    )
    
    return response

# Background task
@app.cli.command()
def auto_index():
    """Run auto-indexer"""
    analyze_and_create_indexes()
```

### Example 3: SQLAlchemy Integration

```python
# your_project/db_integration.py
from sqlalchemy import event
from sqlalchemy.engine import Engine
from dna_layer.stats import log_query_stat
import time

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration_ms = (time.time() - context._query_start_time) * 1000
    
    # Parse table name from statement (simplified)
    table_name = extract_table_name(statement)
    
    log_query_stat(
        tenant_id=get_current_tenant_id(),
        table_name=table_name,
        field_name=None,
        query_type='SELECT',  # Parse from statement
        duration_ms=duration_ms
    )
```

### Example 4: Raw SQL Integration

```python
# your_project/db_queries.py
from dna_layer.db import get_cursor
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

## Production Deployment

### Pre-Deployment Checklist

- [ ] Database credentials configured via environment variables
- [ ] Connection pooling configured appropriately
- [ ] Schema definitions match your database
- [ ] Genome catalog bootstrapped
- [ ] Query logging integrated
- [ ] Auto-indexer scheduled (cron/background job)
- [ ] Monitoring configured
- [ ] Error handling tested
- [ ] Backup strategy for metadata tables

### Deployment Steps

1. **Initialize Metadata Tables**
   ```python
   from dna_layer.schema import init_schema
   
   # Run once on deployment
   init_schema()
   ```

2. **Bootstrap Genome Catalog**
   ```python
   from dna_layer.genome import bootstrap_genome_catalog
   
   # Run once on deployment
   bootstrap_genome_catalog()
   ```

3. **Configure Auto-Indexer Schedule**
   ```python
   # Using cron (Linux/Mac)
   # Add to crontab: 0 */6 * * * python -m dna_layer.auto_indexer
   
   # Or using Celery (Python)
   from celery import Celery
   
   @celery_app.task
   def run_auto_indexer():
       from dna_layer.auto_indexer import analyze_and_create_indexes
       analyze_and_create_indexes()
   
   # Schedule: Every 6 hours
   run_auto_indexer.apply_async(countdown=21600)
   ```

4. **Set Up Monitoring**
   ```python
   from dna_layer.monitoring import get_system_health
   
   # Health check endpoint
   def health_check():
       health = get_system_health()
       return health
   ```

### Production Configuration

```python
# production_config.py
import os

# Database
os.environ['DB_HOST'] = os.getenv('DB_HOST')
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = os.getenv('DB_NAME')
os.environ['DB_USER'] = os.getenv('DB_USER')
os.environ['DB_PASSWORD'] = os.getenv('DB_PASSWORD')  # From secrets
os.environ['ENVIRONMENT'] = 'production'

# Connection pool (adjust for your load)
from dna_layer.db import init_connection_pool
init_connection_pool(min_conn=5, max_conn=20)

# Auto-indexer settings
AUTO_INDEXER_ENABLED = True
AUTO_INDEXER_INTERVAL_HOURS = 6
MIN_QUERIES_PER_HOUR = 100
```

### Scaling Considerations

**Small Deployment (< 10 tenants):**
- Connection pool: 2-5 connections
- Auto-indexer: Run every 12 hours
- Minimal monitoring

**Medium Deployment (10-100 tenants):**
- Connection pool: 5-10 connections
- Auto-indexer: Run every 6 hours
- Basic monitoring

**Large Deployment (100+ tenants):**
- Connection pool: 10-20 connections
- Auto-indexer: Run every 1-3 hours
- Comprehensive monitoring
- Consider standalone service approach

---

## Troubleshooting

### Common Issues

#### **Issue: "Connection pool exhausted"**
**Solution:**
```python
# Increase pool size
init_connection_pool(min_conn=5, max_conn=30)

# Or check for connection leaks
from dna_layer.db import get_pool_stats
stats = get_pool_stats()
print(stats)
```

#### **Issue: "Schema mismatch"**
**Solution:**
- Verify genome catalog matches your actual schema
- Re-bootstrap genome catalog:
  ```python
  from dna_layer.genome import clear_genome_catalog, bootstrap_genome_catalog
  clear_genome_catalog()
  bootstrap_genome_catalog()
  ```

#### **Issue: "Indexes not being created"**
**Solution:**
- Check query stats are being logged
- Verify query volume meets thresholds
- Check mutation log for errors:
  ```python
  from dna_layer.audit import get_recent_mutations
  mutations = get_recent_mutations(limit=10)
  ```

#### **Issue: "Performance degradation"**
**Solution:**
- Check index overhead (should be < 50% of table size)
- Review auto-indexer thresholds
- Check for too many indexes on small tables

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# DNA system will log detailed information
```

### Health Checks

```python
from dna_layer.health_check import check_dna_system_health

health = check_dna_system_health()
if not health['healthy']:
    print(f"Issues: {health['issues']}")
```

---

## Next Steps

1. **Review Extensibility Audit** (`docs/EXTENSIBILITY_AUDIT.md`)
   - Understand current limitations
   - Plan for schema abstraction
   - Consider multi-database support

2. **Customize for Your Schema**
   - Modify `genome.py` for your tables
   - Update `schema.py` for your table definitions
   - Test with your query patterns

3. **Integrate Query Logging**
   - Add to your ORM/query layer
   - Ensure tenant_id is captured
   - Test query stat collection

4. **Set Up Auto-Indexer**
   - Schedule background job
   - Monitor index creation
   - Adjust thresholds as needed

5. **Monitor and Optimize**
   - Review mutation log
   - Check query performance
   - Adjust configuration

---

## Support and Resources

- **Extensibility Audit**: `docs/EXTENSIBILITY_AUDIT.md`
- **Architecture Overview**: `README.md`
- **Production Guide**: `PRODUCTION_DEPLOYMENT_ANALYSIS.md`
- **Adapter Integration Guide**: `docs/ADAPTERS_USAGE_GUIDE.md` ⚠️ **CRITICAL for production**

For questions or issues, refer to the main documentation or create an issue in the repository.

