# IndexPilot Integration in Host Codebase

**Date**: 08-12-2025  
**Purpose**: Explain how IndexPilot's database setup and type generation work when integrated into a host codebase

---

## What Does "Application-Level Business Logic" Mean?

### The Distinction

**PostgreSQL (Database Engine):**
- Provides: Tables, indexes, queries, transactions
- Stores: Your business data (users, orders, products, etc.)
- Manages: Data persistence, ACID guarantees, query execution

**IndexPilot (Control Layer):**
- Provides: **Decision-making logic** about indexes
- Stores: **Metadata about your schema** and **decisions made**
- Manages: **When to create indexes**, **which fields to track**, **per-tenant configurations**

### Example: "Application-Level Business Logic"

**PostgreSQL doesn't know:**
- ❌ Which fields should be indexed (business decision)
- ❌ Which fields are "core" vs "custom" (business categorization)
- ❌ Per-tenant field activation (multi-tenant business logic)
- ❌ Cost-benefit thresholds (business rules)
- ❌ Why an index was created (business context)

**IndexPilot stores this in its metadata tables:**
```sql
-- genome_catalog: Business logic about schema
is_indexable = TRUE  -- Business decision: "This field should be indexed"
feature_group = 'core'  -- Business categorization
default_expression = TRUE  -- Business rule: "Enabled by default"

-- expression_profile: Per-tenant business logic
is_enabled = TRUE  -- Business decision: "This field is active for tenant 5"

-- mutation_log: Business context
details_json = {
  "reason": "high_query_volume",
  "cost_benefit_ratio": 2.5,
  "queries_analyzed": 1500
}  -- Business context: "Why we created this index"
```

**Analogy:**
- PostgreSQL = The car engine (provides power)
- IndexPilot = The ECU (Engine Control Unit) that:
  - Tracks fuel efficiency (query_stats)
  - Decides when to shift gears (create indexes)
  - Stores driving patterns (genome_catalog)
  - Remembers maintenance history (mutation_log)

---

## How Database Tables Are Auto-Created in Host Codebase

### Integration Model: "Copy-Over"

IndexPilot uses a **"copy-over" integration model** - you copy files into your project, not install as a package.

### Step-by-Step: Database Setup in Host Codebase

#### 1. **Copy IndexPilot Files**

```bash
# In your host codebase
cp -r indexpilot/src your_project/indexpilot
# Or copy specific files you need
```

#### 2. **Install Dependencies**

```bash
# In your host codebase
pip install psycopg2-binary python-dotenv pyyaml psutil
```

#### 3. **Configure Database Connection**

```bash
# Set environment variables (or use your existing config)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=your_database
export DB_USER=your_user
export DB_PASSWORD=your_password
```

#### 4. **Initialize IndexPilot Tables (One-Time Setup)**

**⚠️ Important:** In a host codebase, your business tables **already exist**. IndexPilot only needs to create its **metadata tables**.

**Option A: Auto-Discover from Existing Database (Recommended)**
```python
# your_project/init_indexpilot.py
from indexpilot.schema import discover_and_bootstrap_schema

# Automatically discovers your existing schema and creates IndexPilot metadata tables
result = discover_and_bootstrap_schema()
# This:
# 1. Creates IndexPilot metadata tables ONLY (genome_catalog, expression_profile, etc.)
# 2. Discovers your existing business tables from information_schema
# 3. Populates genome_catalog with your schema
# 4. Does NOT create/modify your business tables
```

**Option B: Metadata Tables Only (If you don't want auto-discovery)**
```python
# your_project/init_indexpilot.py
from indexpilot.schema.initialization import create_metadata_tables
from indexpilot.schema.auto_discovery import discover_schema_from_database
from indexpilot.genome import bootstrap_genome_catalog_from_schema
from indexpilot.db import get_connection
from psycopg2.extras import RealDictCursor

# 1. Create metadata tables only (doesn't touch your business tables)
with get_connection() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    create_metadata_tables(cursor)  # Only creates IndexPilot metadata tables
    conn.commit()

# 2. Discover your existing schema
schema = discover_schema_from_database()

# 3. Bootstrap genome catalog with your schema
bootstrap_genome_catalog_from_schema(schema)
```

**Option C: Use Schema Config File**
```python
# your_project/init_indexpilot.py
from indexpilot.schema.initialization import create_metadata_tables, init_schema_from_config
from indexpilot.schema.loader import load_schema
from indexpilot.genome import bootstrap_genome_catalog_from_schema
from indexpilot.db import get_connection
from psycopg2.extras import RealDictCursor

# 1. Create metadata tables only
with get_connection() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    create_metadata_tables(cursor)
    conn.commit()

# 2. Load your schema from config (optional - for validation)
schema = load_schema('schema_config.yaml')  # Your schema definition

# 3. Bootstrap genome catalog with your schema
bootstrap_genome_catalog_from_schema(schema)
```

**❌ Don't Use:** `init_schema()` - This creates BOTH business tables AND metadata tables (for demo/testing only, not for host codebases)

#### 5. **Run Initialization (One-Time)**

```bash
# In your host codebase
python your_project/init_indexpilot.py
```

**What Happens:**
1. ✅ Connects to **your existing database**
2. ✅ Creates **IndexPilot metadata tables** (genome_catalog, expression_profile, mutation_log, query_stats)
3. ✅ **Does NOT modify your business tables** (they already exist)
4. ✅ Populates genome_catalog with your schema information

---

## Database Management in Host Codebase

### What IndexPilot Creates

**IndexPilot creates ONLY its metadata tables:**
- `genome_catalog` - Schema metadata
- `expression_profile` - Per-tenant field activation
- `mutation_log` - Index change history
- `query_stats` - Query performance metrics
- `index_versions` - Index version tracking
- `ab_experiments` - A/B testing metadata
- (Other metadata tables as needed)

**IndexPilot does NOT create:**
- ❌ Your business tables (they already exist)
- ❌ Your indexes (it creates them automatically later)
- ❌ Your data (you manage that)

### Ongoing Management

**IndexPilot manages its own tables automatically:**
- ✅ Auto-creates indexes (adds to your database)
- ✅ Logs changes to `mutation_log`
- ✅ Tracks queries in `query_stats`
- ✅ Updates `genome_catalog` when schema changes detected

**You manage:**
- Your business tables (create/modify as needed)
- Your business data (insert/update/delete as needed)
- IndexPilot configuration (via `indexpilot_config.yaml`)

### Schema Sync

**IndexPilot can auto-detect schema changes:**
```python
from indexpilot.schema.change_detection import detect_and_sync_schema_changes

# Detects if you added/removed tables/columns
# Updates genome_catalog to match
result = detect_and_sync_schema_changes(auto_update=True)
```

**When to run:**
- After migrations
- After schema changes
- Periodically (cron job)
- On application startup (optional)

---

## Auto Type Generation in Host Codebase

### Current State: Manual Types

**Currently:**
- Types are manually defined in `type_definitions.py`
- No automatic generation from database schema
- Types can drift from actual database

### Proposed: Auto Type Generation

**How it would work in host codebase:**

#### Option 1: Generate Types at Build Time (Recommended)

```python
# your_project/tools/generate_types.py
from indexpilot.tools.generate_types_from_schema import generate_all_types

# Generate types from your database schema
generate_all_types(
    output_file='your_project/indexpilot/generated_types.py',
    tables=['users', 'orders', 'products']  # Your business tables + IndexPilot metadata
)

# Generated file (auto-created):
# your_project/indexpilot/generated_types.py
```

**Usage in host codebase:**
```python
# your_project/your_app.py
from indexpilot.generated_types import UsersRow, OrdersRow, GenomeCatalogRow

def get_user(user_id: int) -> UsersRow | None:
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    return row  # Type-safe: TypeScript knows exact structure
```

**When to run:**
- After schema migrations
- As part of build process
- Via Makefile target: `make generate-types`

#### Option 2: Generate Types at Runtime (Not Recommended)

```python
# Runtime generation (slower, but always up-to-date)
from indexpilot.tools.generate_types_from_schema import generate_types_for_table

# Generate types on-demand
UserRow = generate_types_for_table('users')
```

**Why not recommended:**
- Performance overhead
- Type checking happens at runtime (defeats purpose)
- IDE autocomplete doesn't work

#### Option 3: Generate Types in Host Codebase Build Process

**In your host codebase Makefile:**
```makefile
# your_project/Makefile
generate-indexpilot-types:
	python tools/generate_indexpilot_types.py

# Run after migrations
migrate: apply-migrations generate-indexpilot-types
	@echo "Migration complete, types regenerated"
```

**In your host codebase CI/CD:**
```yaml
# .github/workflows/ci.yml
- name: Generate IndexPilot types
  run: |
    python tools/generate_indexpilot_types.py
    git diff --exit-code  # Fail if types changed (schema changed)
```

---

## Complete Integration Example

### Host Codebase Structure

```
your_project/
├── your_app/
│   ├── models.py          # Your business models
│   ├── database.py        # Your database connection
│   └── main.py            # Your application entry point
├── indexpilot/            # Copied from IndexPilot
│   ├── src/               # IndexPilot source code
│   ├── generated_types.py # Auto-generated (gitignored)
│   └── ...
├── tools/
│   └── generate_indexpilot_types.py  # Type generator script
├── schema_config.yaml      # Your schema definition
├── indexpilot_config.yaml  # IndexPilot configuration
└── Makefile
```

### Initialization Script

```python
# your_project/init_indexpilot.py
"""
One-time IndexPilot initialization for host codebase.
Run this once after copying IndexPilot files.

This script:
1. Creates IndexPilot metadata tables (genome_catalog, expression_profile, etc.)
2. Discovers your existing business tables
3. Populates genome_catalog with your schema
4. Does NOT modify your existing business tables
"""

from indexpilot.schema import discover_and_bootstrap_schema
from indexpilot.db import init_connection_pool

def setup_indexpilot():
    """Initialize IndexPilot in host codebase"""
    
    # 1. Initialize connection pool (or use your existing pool)
    init_connection_pool()
    
    # 2. Auto-discover schema and create metadata tables ONLY
    # This creates IndexPilot's metadata tables and discovers your existing schema
    result = discover_and_bootstrap_schema()
    
    if result.get("success"):
        print(f"✅ IndexPilot initialized:")
        print(f"   - {result.get('tables_count', 0)} business tables discovered")
        print(f"   - {result.get('fields_count', 0)} fields registered in genome_catalog")
        print(f"   - Metadata tables created: genome_catalog, expression_profile, mutation_log, query_stats")
    else:
        print(f"❌ Initialization failed: {result.get('error')}")

if __name__ == '__main__':
    setup_indexpilot()
```

### Type Generation Script

```python
# your_project/tools/generate_indexpilot_types.py
"""
Generate Python types from database schema.
Run this after schema migrations or as part of build process.
"""

from indexpilot.tools.generate_types_from_schema import (
    generate_types_for_table,
    generate_all_indexpilot_types
)

def generate_types():
    """Generate types for IndexPilot metadata tables + your business tables"""
    
    # Generate types for IndexPilot metadata tables
    indexpilot_tables = [
        'genome_catalog',
        'expression_profile',
        'mutation_log',
        'query_stats',
        'index_versions',
    ]
    
    # Generate types for your business tables (from config or discovery)
    your_tables = [
        'users',
        'orders',
        'products',
        # ... your tables
    ]
    
    all_tables = indexpilot_tables + your_tables
    
    # Generate all types
    output = generate_all_indexpilot_types(all_tables)
    
    # Write to generated_types.py
    with open('indexpilot/generated_types.py', 'w') as f:
        f.write(output)
    
    print(f"✅ Generated types for {len(all_tables)} tables")

if __name__ == '__main__':
    generate_types()
```

### Application Startup

```python
# your_project/your_app/main.py
from indexpilot.db import init_connection_pool
from indexpilot.schema.change_detection import detect_and_sync_schema_changes
from indexpilot.auto_indexer import analyze_and_create_indexes

def startup():
    """Application startup - initialize IndexPilot"""
    
    # 1. Initialize connection pool
    init_connection_pool()
    
    # 2. Sync schema (detect any changes since last run)
    detect_and_sync_schema_changes(auto_update=True)
    
    # 3. Start background auto-indexer (optional)
    # analyze_and_create_indexes()  # Run periodically via cron/celery

if __name__ == '__main__':
    startup()
    # ... rest of your application
```

---

## Answers to Your Questions

### 1. "What does application-level business logic mean?"

**Answer:** IndexPilot stores **decisions and metadata** about your schema, not just the schema itself:
- Which fields should be indexed (business decision)
- Per-tenant field activation (business logic)
- Why indexes were created (business context)
- Cost-benefit thresholds (business rules)

PostgreSQL provides the engine; IndexPilot provides the **control system** that makes decisions.

### 2. "How will the db be auto-created, setup and managed in a host codebase?"

**Answer:**

**Auto-Created:**
- ✅ IndexPilot metadata tables are created automatically via `init_schema()`
- ✅ Your business tables are **NOT** created by IndexPilot (they already exist)

**Setup:**
- ✅ One-time: Run `discover_and_bootstrap_schema()` or `init_schema() + bootstrap_genome_catalog()`
- ✅ This creates IndexPilot's metadata tables in **your existing database**
- ✅ Populates `genome_catalog` with your schema information

**Managed:**
- ✅ IndexPilot manages its own metadata tables automatically
- ✅ You manage your business tables (as usual)
- ✅ IndexPilot can auto-detect schema changes and sync `genome_catalog`

**Integration:**
```python
# In your host codebase startup
from indexpilot.schema import discover_and_bootstrap_schema
discover_and_bootstrap_schema()  # One-time setup
```

### 3. "Will the auto type generation also be done in host codebase?"

**Answer:** **Yes, in the host codebase**

**How it works:**
1. **Type generator script** runs in your host codebase
2. **Connects to your database** (same connection IndexPilot uses)
3. **Queries `information_schema`** to discover table structures
4. **Generates Python TypedDict classes** for each table
5. **Writes to `indexpilot/generated_types.py`** in your project

**When to run:**
- After schema migrations
- As part of build process
- Via Makefile target: `make generate-types`
- In CI/CD pipeline (verify types match schema)

**Example:**
```bash
# In your host codebase
python tools/generate_indexpilot_types.py
# Generates: indexpilot/generated_types.py
```

**Usage:**
```python
# In your host codebase code
from indexpilot.generated_types import UsersRow, OrdersRow

def get_user(id: int) -> UsersRow | None:
    # Type-safe database access
    ...
```

---

## Summary

**IndexPilot in Host Codebase:**

1. ✅ **Copy files** → `your_project/indexpilot/`
2. ✅ **One-time setup** → `discover_and_bootstrap_schema()` creates metadata tables
3. ✅ **Uses your existing database** → No separate database needed
4. ✅ **Type generation** → Run in host codebase, generates types from your schema
5. ✅ **Auto-managed** → IndexPilot manages its metadata tables automatically

**Key Points:**
- IndexPilot tables are created **in your database**, not a separate database
- Setup is **one-time** (after copying files)
- Type generation is **optional** but recommended (run in host codebase)
- IndexPilot **doesn't interfere** with your existing tables/data

**It's a library you integrate, not a separate service.**

