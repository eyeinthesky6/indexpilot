# First Run Setup Guide

**Date**: 2025-12-08  
**Purpose**: Guide users through post-installation assessment and first-run setup, especially when multiple databases are present

---

## Overview

After installing IndexPilot, you need to:
1. **Assess** your current database setup
2. **Choose** which database to use (if multiple exist)
3. **Initialize** IndexPilot metadata tables
4. **Bootstrap** the genome catalog from your schema

This guide helps you through each step, especially when you have multiple databases on your PostgreSQL host.

---

## Step 1: Run Setup Assessment

**First, assess your current setup:**

```bash
python scripts/assess_setup.py
```

Or in interactive mode (lists all available databases):

```bash
python scripts/assess_setup.py --interactive
```

### What the Assessment Shows

The assessment tool checks:

1. **Environment Configuration**
   - Whether database connection is configured
   - Which database is currently selected

2. **Database Connection**
   - Tests connectivity to PostgreSQL
   - Shows PostgreSQL version

3. **Available Databases** (interactive mode)
   - Lists all databases on the host
   - Highlights currently selected database

4. **IndexPilot Initialization Status**
   - ✅/⚠️ Metadata tables exist?
   - ✅/⚠️ Genome catalog bootstrapped?
   - ✅/⚠️ Business schema discovered?

5. **Recommendations**
   - Next steps based on current state
   - Commands to run for initialization

---

## Step 2: Configure Database Connection

If no database is configured, or you want to use a different database:

### Option A: Environment Variables (Recommended)

```bash
# Set database connection details
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=your_database_name
export DB_USER=your_username
export DB_PASSWORD=your_password
```

### Option B: Connection String

```bash
# Using INDEXPILOT_DATABASE_URL
export INDEXPILOT_DATABASE_URL=postgres://user:password@host:port/dbname

# Or Supabase
export SUPABASE_DB_URL=postgres://user:password@host:port/dbname
```

### Option C: Multiple Databases

**If you have multiple databases on the host:**

1. Run assessment in interactive mode to see all databases:
   ```bash
   python scripts/assess_setup.py --interactive
   ```

2. Choose which database to use and set `DB_NAME` accordingly:
   ```bash
   export DB_NAME=your_chosen_database
   ```

3. Re-run assessment to verify:
   ```bash
   python scripts/assess_setup.py
   ```

**Note**: IndexPilot connects to **one database at a time**. If you need to manage multiple databases, you'll need to:
- Run IndexPilot separately for each database
- Use different environment configurations
- Or use different connection pools via adapters

---

## Step 3: Initialize IndexPilot

Based on the assessment results, follow the recommended steps:

### Scenario A: Fresh Database (No Tables)

If your database is empty or new:

```bash
# 1. Initialize metadata tables
python -c "from src.schema import init_schema; init_schema()"

# 2. If you have a schema config file, bootstrap from it:
python -c "from src.schema.loader import load_schema; from src.schema import init_schema_from_config; from src.genome import bootstrap_genome_catalog_from_schema; config = load_schema('schema_config.yaml'); init_schema_from_config(config); bootstrap_genome_catalog_from_schema(config)"
```

### Scenario B: Existing Database with Tables

If your database already has business tables:

```bash
# 1. Initialize metadata tables (does NOT touch your schema)
python -c "from src.schema import init_schema; init_schema()"

# 2. Auto-discover schema and bootstrap genome catalog
python -c "from src.schema import discover_and_bootstrap_schema; discover_and_bootstrap_schema()"
```

This will:
- ✅ Create IndexPilot metadata tables (`genome_catalog`, `expression_profile`, `mutation_log`, `query_stats`)
- ✅ Discover your existing tables and columns
- ✅ Bootstrap the genome catalog with discovered schema
- ✅ **NOT modify** your existing tables or data

### Scenario C: Already Initialized

If assessment shows everything is initialized:

```bash
# You're ready to use IndexPilot!

# Run in advisory mode (safe, no DDL changes)
python -c "from src.auto_indexer import analyze_and_create_indexes; analyze_and_create_indexes()"

# Check candidate indexes
psql -d your_database -c "SELECT * FROM mutation_log WHERE mutation_type = 'CREATE_INDEX' AND details_json->>'mode' = 'advisory';"
```

---

## Step 4: Verify Setup

Re-run the assessment to verify everything is set up correctly:

```bash
python scripts/assess_setup.py
```

You should see:
- ✅ Database connected
- ✅ Metadata tables exist
- ✅ Genome catalog bootstrapped
- ✅ Business schema discovered

---

## Common Issues

### Issue: "Connection failed"

**Solutions:**
- Check PostgreSQL is running: `pg_isready` or `docker ps` (if using Docker)
- Verify credentials: `psql -h localhost -U your_user -d your_database`
- Check firewall/network settings
- Verify `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

### Issue: "Multiple databases found, which one?"

**Solution:**
- Use `--interactive` mode to see all databases
- Choose the database that contains your application schema
- Set `DB_NAME` environment variable
- Re-run assessment

### Issue: "Metadata tables not found"

**Solution:**
- Run: `python -c "from src.schema import init_schema; init_schema()"`
- Verify with assessment tool

### Issue: "Genome catalog not bootstrapped"

**Solution:**
- If you have existing tables: `python -c "from src.schema import discover_and_bootstrap_schema; discover_and_bootstrap_schema()"`
- If you have schema config: Use `init_schema_from_config()` and `bootstrap_genome_catalog_from_schema()`

---

## Next Steps

After successful setup:

1. **Run in Advisory Mode** (safe, no changes):
   ```bash
   python -c "from src.auto_indexer import analyze_and_create_indexes; analyze_and_create_indexes()"
   ```

2. **Review Candidate Indexes**:
   ```bash
   psql -d your_database -c "SELECT * FROM mutation_log WHERE mutation_type = 'CREATE_INDEX';"
   ```

3. **Enable Index Creation** (after review):
   ```bash
   export INDEXPILOT_AUTO_INDEXER_MODE=apply
   # Or edit indexpilot_config.yaml: features.auto_indexer.mode: "apply"
   ```

4. **Monitor Performance**:
   - Check `query_stats` table for query patterns
   - Review `mutation_log` for index creation history
   - Monitor query performance improvements

---

## Integration with Host Codebase

**For production deployments**, see:
- `docs/installation/HOW_TO_INSTALL.md` - Copy-over integration guide
- `docs/installation/ADAPTERS_USAGE_GUIDE.md` - Host adapter integration
- `docs/installation/DEPLOYMENT_INTEGRATION_GUIDE.md` - Production deployment

---

**Last Updated**: 2025-12-08

