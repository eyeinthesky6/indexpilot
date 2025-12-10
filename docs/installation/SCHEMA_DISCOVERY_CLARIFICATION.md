# Schema Discovery - Two Different Functions

**Date**: 2025-12-08

---

## Two Different Discovery Functions

There are **TWO different discovery functions** that serve different purposes:

### 1. `src/schema/discovery.py` - **File Discovery**
**Purpose**: Discovers schema **CONFIG FILES** in the codebase

**What it does**:
- Searches for `schema_config*.yaml`, `schema_config*.json`, `schema_config*.py` files
- Finds schema definition files on disk
- Loads schema from those files

**Use case**: When you have schema defined in YAML/JSON/Python files

**Functions**:
- `discover_schema_files()` - Find schema config files
- `load_discovered_schema()` - Load a discovered file
- `auto_discover_and_load_schema()` - Find and load automatically

**Example**:
```python
from src.schema.discovery import auto_discover_and_load_schema

# Finds schema_config_stock_market.yaml and loads it
schema = auto_discover_and_load_schema("stock_market")
```

---

### 2. `src/schema/auto_discovery.py` - **Database Discovery**
**Purpose**: Discovers schema **FROM THE DATABASE** itself

**What it does**:
- Queries PostgreSQL's `information_schema`
- Reads actual database structure (tables, columns, types, constraints)
- Generates schema definition from live database

**Use case**: When you have an existing database and want to auto-discover its structure

**Functions**:
- `discover_schema_from_database()` - Discover schema from database
- `discover_and_bootstrap_schema()` - Discover and bootstrap genome catalog

**Example**:
```python
from src.schema.auto_discovery import discover_and_bootstrap_schema

# Reads schema from database and bootstraps genome catalog
result = discover_and_bootstrap_schema()
```

---

## Comparison

| Feature | File Discovery (`discovery.py`) | Database Discovery (`auto_discovery.py`) |
|---------|----------------------------------|------------------------------------------|
| **Source** | Schema config files (YAML/JSON/Python) | PostgreSQL database (`information_schema`) |
| **When to use** | Schema defined in files | Existing database, no schema files |
| **Requires** | Schema config files exist | Database connection |
| **Output** | Schema definition dict | Schema definition dict |

---

## Which One to Use?

### Use File Discovery (`discovery.py`) when:
- ✅ You have schema defined in YAML/JSON/Python files
- ✅ You want to version control your schema
- ✅ You're setting up a new database from config

### Use Database Discovery (`auto_discovery.py`) when:
- ✅ You have an existing database
- ✅ You don't have schema config files
- ✅ You want to discover schema automatically
- ✅ You're integrating IndexPilot with an existing system

---

## They Work Together

You can use both:

```python
# First, try to discover from files
from src.schema.discovery import auto_discover_and_load_schema
from src.schema.auto_discovery import discover_schema_from_database

# Try file discovery first
schema = auto_discover_and_load_schema()

# If no files found, discover from database
if not schema:
    schema = discover_schema_from_database()
```

---

## Summary

**NOT duplicates** - they serve different purposes:
- `discovery.py` = Find schema **files** in codebase
- `auto_discovery.py` = Discover schema **from database**

Both are useful and complement each other!

