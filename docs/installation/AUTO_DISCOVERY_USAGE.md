# Schema Auto-Discovery Usage Guide

**Date**: 2025-12-08  
**Status**: ✅ **FULLY FUNCTIONAL**

---

## Overview

IndexPilot can now **automatically discover** your database schema from an existing PostgreSQL database. No manual schema definition required!

---

## Quick Start

### Option 1: Discover and Bootstrap in One Step

```python
from src.schema import discover_and_bootstrap_schema

# Discover schema and bootstrap genome catalog
result = discover_and_bootstrap_schema()

if result['success']:
    print(f"Discovered {result['tables_count']} tables")
    print(f"Bootstrapped {result['fields_count']} fields")
else:
    print(f"Error: {result['error']}")
```

### Option 2: Discover Schema Only

```python
from src.schema import discover_schema_from_database
from src.genome import bootstrap_genome_catalog_from_schema

# Discover schema
schema = discover_schema_from_database()

# Bootstrap genome catalog
bootstrap_genome_catalog_from_schema(schema)
```

---

## What Gets Discovered

The auto-discovery function reads from PostgreSQL's `information_schema` to discover:

1. **Tables**: All base tables in the schema
2. **Columns**: All columns with:
   - Data types (mapped to schema format)
   - Nullable/required status
   - Default values
3. **Primary Keys**: Automatically marked as required
4. **Foreign Keys**: Relationships between tables
5. **Indexes**: Existing indexes (for reference)

---

## Examples

### Example 1: Discover from Default Schema

```python
from src.schema import discover_and_bootstrap_schema

# Discover from 'public' schema (default)
result = discover_and_bootstrap_schema()
```

### Example 2: Discover from Custom Schema

```python
from src.schema import discover_schema_from_database

# Discover from 'my_schema'
schema = discover_schema_from_database(schema_name="my_schema")
```

### Example 3: Exclude Specific Tables

```python
from src.schema import discover_schema_from_database

# Exclude certain tables
exclude = {"temp_table", "log_table"}
schema = discover_schema_from_database(exclude_tables=exclude)
```

### Example 4: Include System Tables

```python
from src.schema import discover_schema_from_database

# Include PostgreSQL system tables
schema = discover_schema_from_database(include_system_tables=True)
```

---

## What Gets Excluded by Default

The following tables are automatically excluded:
- `genome_catalog` (IndexPilot metadata)
- `expression_profile` (IndexPilot metadata)
- `mutation_log` (IndexPilot metadata)
- `query_stats` (IndexPilot metadata)
- `index_versions` (IndexPilot metadata)
- `ab_experiments` (IndexPilot metadata)
- `ab_experiment_results` (IndexPilot metadata)
- System tables (starting with `pg_`)

---

## Type Mapping

PostgreSQL types are automatically mapped to schema format:

| PostgreSQL Type | Schema Format |
|----------------|---------------|
| `INTEGER`, `INT`, `INT4` | `INTEGER` |
| `BIGINT`, `INT8` | `BIGINT` |
| `SERIAL` | `SERIAL` |
| `NUMERIC`, `DECIMAL` | `NUMERIC` |
| `TEXT`, `VARCHAR` | `TEXT` |
| `TIMESTAMP` | `TIMESTAMP` |
| `JSONB` | `JSONB` |
| `BOOLEAN` | `BOOLEAN` |
| ... and more | ... |

---

## Integration with Existing Workflow

### For New Databases

1. **Create your tables** (using your existing migration tools)
2. **Run auto-discovery**:
   ```python
   from src.schema import discover_and_bootstrap_schema
   discover_and_bootstrap_schema()
   ```
3. **Start using IndexPilot** - it will automatically work with your schema!

### For Existing Databases

1. **Connect to your database**
2. **Run auto-discovery**:
   ```python
   from src.schema import discover_and_bootstrap_schema
   discover_and_bootstrap_schema()
   ```
3. **IndexPilot is ready** - no schema definition needed!

---

## Command-Line Usage

You can also use it from the command line:

```python
# Create a simple script: discover_schema.py
from src.schema import discover_and_bootstrap_schema

if __name__ == "__main__":
    result = discover_and_bootstrap_schema()
    if result['success']:
        print(f"Success! Discovered {result['tables_count']} tables")
    else:
        print(f"Error: {result['error']}")
```

Then run:
```bash
python discover_schema.py
```

---

## Testing

The auto-discovery has been tested and verified:

```
✓ Discovery successful!
  Tables discovered: 6
  Total fields: 54

✓ Bootstrap successful!
  Tables: 6
  Fields: 54

✓ Genome catalog verified
  Fields in genome_catalog: 54
  Tables in genome_catalog: 6
```

---

## Error Handling

The function handles errors gracefully:

```python
from src.schema import discover_and_bootstrap_schema

result = discover_and_bootstrap_schema()

if not result['success']:
    print(f"Error: {result.get('error', 'Unknown error')}")
    # Handle error appropriately
```

Common errors:
- Database connection issues
- Schema doesn't exist
- No tables found
- Permission issues

---

## Performance

- **Fast**: Uses efficient `information_schema` queries
- **Single transaction**: All discovery happens in one database connection
- **Minimal overhead**: Only reads metadata, not data

---

## Limitations

1. **PostgreSQL only**: Uses PostgreSQL-specific `information_schema`
2. **Schema-level**: Discovers one schema at a time (default: `public`)
3. **No data discovery**: Only discovers structure, not data
4. **Index details**: Existing indexes are discovered but not fully analyzed

---

## Next Steps

After auto-discovery:

1. **Verify genome catalog**: Check that all tables/fields are registered
2. **Run simulations**: Test with your schema
3. **Monitor queries**: IndexPilot will start analyzing query patterns
4. **Auto-indexing**: Indexes will be created automatically based on usage

---

## Summary

✅ **Auto-discovery is fully functional**  
✅ **Works with any PostgreSQL schema**  
✅ **No manual schema definition required**  
✅ **Tested and verified**

The system is now **truly schema-agnostic** - just point it at your database and it will discover everything automatically!

