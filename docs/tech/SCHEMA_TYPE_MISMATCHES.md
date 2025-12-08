# Database Schema Type Mismatches

**Date**: 08-12-2025  
**Status**: Active Issues

---

## Summary

There are **two types of mismatches** in IndexPilot:

1. ✅ **Schema Drift** - `genome_catalog` out of sync with actual database
2. ⚠️ **Type Mismatch** - TIMESTAMP columns return `datetime` objects, but `JSONValue` doesn't include `datetime`

---

## 1. Schema Drift (genome_catalog vs Database)

### Current Mismatches Detected

**Removed Tables** (in genome_catalog but not in database):
- `ml_model_metadata` - All columns removed
- `algorithm_usage` - All columns removed

**New Tables** (in database but not in genome_catalog):
- `stocks` - Stock market schema
- `stock_prices` - Stock market schema

### Why This Happens

1. **Manual schema changes** - Tables created/dropped outside IndexPilot
2. **Schema evolution** - Tables added via migrations
3. **genome_catalog not updated** - Changes not synced back

### Detection

IndexPilot has `detect_and_sync_schema_changes()` that can detect these:

```python
from src.schema.change_detection import detect_and_sync_schema_changes

result = detect_and_sync_schema_changes(auto_update=False)
# Returns:
# - new_tables: Tables in DB but not in genome_catalog
# - new_columns: Columns in DB but not in genome_catalog
# - removed_tables: Tables in genome_catalog but not in DB
# - removed_columns: Columns in genome_catalog but not in DB
```

### Fix

Run schema sync:
```python
detect_and_sync_schema_changes(auto_update=True)
```

Or manually:
```bash
python -m src.schema.change_detection
```

---

## 2. Type Mismatch (TIMESTAMP → datetime)

### The Problem

**PostgreSQL TIMESTAMP columns** return Python `datetime` objects when queried:
```python
cursor.execute("SELECT created_at FROM genome_catalog")
row = cursor.fetchone()
created_at = row["created_at"]  # This is a datetime object, not a string!
```

**But `JSONValue` type definition** doesn't include `datetime`:
```python
type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
# ❌ No datetime!
```

**Result:** Type checker errors when accessing TIMESTAMP columns.

### Where This Occurs

All tables with TIMESTAMP columns:
- `genome_catalog.created_at`, `genome_catalog.updated_at`
- `expression_profile.created_at`
- `mutation_log.created_at`
- `query_stats.created_at`
- `index_versions.created_at`
- Business tables: `tenants.created_at`, `contacts.created_at`, etc.

### Current Workarounds

**Pattern 1: Type narrowing with object cast**
```python
# src/index_cleanup.py
created_at_raw = safe_get_row_value(creation_record, "created_at", None)
created_at_obj: object = created_at_raw  # Cast to object to allow isinstance
if isinstance(created_at_obj, datetime):
    created_at = created_at_obj
```

**Pattern 2: Type narrowing with cast**
```python
# src/api_server.py
from typing import cast
from datetime import datetime as DatetimeType

created_at_val_check = cast(DatetimeType | JSONValue, created_at_val)
if isinstance(created_at_val_check, DatetimeType):
    created_at_str = created_at_val_check.isoformat()
```

### Root Cause

**PostgreSQL → Python type mapping:**
- `TIMESTAMP` → `datetime.datetime` (Python object)
- `TEXT` → `str`
- `INTEGER` → `int`
- `BOOLEAN` → `bool`
- `JSONB` → `dict` (parsed JSON)

**But `JSONValue` is for JSON-serializable types:**
- JSON doesn't have a datetime type
- Must convert to string (ISO format) for JSON

### Solutions

#### Option 1: Extend JSONValue (Not Recommended)
```python
# ❌ Bad - breaks JSON serialization
type JSONValue = str | int | float | bool | None | datetime | list[...] | dict[...]
```

#### Option 2: Use DatabaseRow Type (Current Approach)
```python
# ✅ Good - DatabaseRow includes datetime
type DatabaseRow = dict[str, str | int | float | bool | None | datetime]
```

#### Option 3: Always Convert to String (Recommended)
```python
# ✅ Best - Convert datetime to ISO string immediately
created_at = safe_get_row_value(row, "created_at", None)
if isinstance(created_at, datetime):
    created_at_str = created_at.isoformat()
else:
    created_at_str = str(created_at) if created_at else ""
```

#### Option 4: Use psycopg2 Type Casting (Future)
```python
# Could configure psycopg2 to return strings for TIMESTAMP
# But loses datetime object benefits
```

---

## Impact Assessment

### Schema Drift Impact: ⚠️ **MEDIUM**

**Problems:**
- IndexPilot may try to manage non-existent tables/columns
- Missing tables/columns won't be indexed
- Validation may fail on orphaned entries

**Current Status:**
- ✅ Detection works (`detect_and_sync_schema_changes()`)
- ⚠️ Not automatically synced (requires manual call)
- ⚠️ Some orphaned entries exist (`ml_model_metadata`, `algorithm_usage`)

### Type Mismatch Impact: ⚠️ **LOW** (Workarounds in Place)

**Problems:**
- Type checker errors (but runtime works)
- Requires manual type narrowing everywhere
- Inconsistent handling across codebase

**Current Status:**
- ✅ Runtime works (datetime objects handled correctly)
- ✅ Type errors fixed with narrowing
- ⚠️ Still requires manual workarounds

---

## Recommendations

### Immediate Fixes

1. **Sync schema drift:**
   ```python
   from src.schema.change_detection import detect_and_sync_schema_changes
   detect_and_sync_schema_changes(auto_update=True)
   ```

2. **Standardize datetime handling:**
   - Create helper function: `convert_datetime_to_string(value: object) -> str`
   - Use consistently across codebase

### Long-term Solutions

1. **Auto-sync schema changes:**
   - Run `detect_and_sync_schema_changes()` periodically
   - Or on startup
   - Or via event triggers

2. **Fix TIMESTAMP type handling:**
   - Option A: Always convert to string immediately
   - Option B: Use `DatabaseRow` type for raw database results
   - Option C: Configure psycopg2 to return strings (loses datetime benefits)

3. **Generate types from schema:**
   - Auto-generate TypedDict from PostgreSQL schema
   - Include proper datetime handling
   - Single source of truth

---

## Files Affected by Type Mismatch

**Files with TIMESTAMP handling workarounds:**
- `src/index_cleanup.py` - datetime type narrowing
- `src/api_server.py` - datetime conversion to ISO string
- `src/schema_evolution.py` - May need datetime handling
- Any file accessing `created_at`, `updated_at`, `occurred_at` columns

**Files that should be checked:**
- All files using `safe_get_row_value()` on TIMESTAMP columns
- All files accessing mutation_log, query_stats, genome_catalog

---

## Testing for Mismatches

### Check Schema Drift
```python
from src.schema.change_detection import detect_and_sync_schema_changes

result = detect_and_sync_schema_changes(auto_update=False)
if result.get("new_tables") or result.get("removed_tables"):
    print("⚠️ Schema drift detected!")
    print("New tables:", result.get("new_tables"))
    print("Removed tables:", result.get("removed_tables"))
```

### Check Type Mismatches
```bash
# Run type checker - will show datetime type errors
make typecheck

# Look for errors like:
# "Expression has type 'datetime' but expected 'JSONValue'"
```

---

## Conclusion

**Current Status:**
- ✅ Schema drift: **Detected and fixable** (just need to sync)
- ⚠️ Type mismatch: **Workarounds in place** (but not ideal)

**Priority:**
1. **High**: Sync schema drift (remove orphaned entries)
2. **Medium**: Standardize datetime handling (create helper function)
3. **Low**: Generate types from schema (long-term improvement)

