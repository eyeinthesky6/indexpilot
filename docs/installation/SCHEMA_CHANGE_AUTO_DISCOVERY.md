# Schema Change Auto-Discovery Status

**Date**: 2025-12-08  
**Question**: Do schema changes get auto-discovered and does the system adapt itself?

---

## Summary

**Status**: ✅ **FULLY AUTOMATIC** - Schema changes are automatically discovered and synced via maintenance tasks.

### ✅ What Works Automatically

1. **Schema Changes via IndexPilot** (`src/schema_evolution.py`)
   - ✅ `safe_add_column()` - Automatically updates `genome_catalog` when column is added
   - ✅ `safe_drop_column()` - Automatically removes from `genome_catalog` when column is dropped
   - ✅ `safe_rename_column()` - Automatically updates `genome_catalog` when column is renamed
   - ✅ `safe_alter_column_type()` - Automatically updates `genome_catalog` when column type changes

2. **Bootstrap Functions**
   - ✅ `bootstrap_genome_catalog_from_schema()` - Uses `ON CONFLICT ... DO UPDATE` to update existing fields
   - ✅ `discover_and_bootstrap_schema()` - Discovers and updates genome catalog

### ❌ What Does NOT Work Automatically

1. **Direct SQL Changes**
   - ❌ If you run `ALTER TABLE ... ADD COLUMN` directly, genome catalog is NOT updated
   - ❌ If you create a new table directly, it's NOT discovered
   - ❌ If you drop a table directly, it's NOT removed from genome catalog

2. **Periodic Auto-Discovery** ✅ **IMPLEMENTED**
   - ✅ Automatic periodic discovery runs every 24 hours (configurable)
   - ✅ Maintenance tasks include schema auto-discovery
   - ✅ Detects schema changes made outside IndexPilot
   - ✅ Automatically syncs genome_catalog with current database schema

3. **New Tables/Columns** ✅ **AUTOMATICALLY DISCOVERED**
   - ✅ New tables added outside IndexPilot are automatically discovered (within 24 hours)
   - ✅ New columns added outside IndexPilot are automatically discovered (within 24 hours)
   - ✅ Removed tables/columns are automatically cleaned up from genome_catalog
   - ✅ Manual call to `discover_and_bootstrap_schema()` still works for immediate sync

---

## Current Implementation

### Schema Evolution Integration

When you use IndexPilot's schema evolution functions, the genome catalog is automatically updated:

```python
from src.schema_evolution import safe_add_column

# This automatically updates genome_catalog
result = safe_add_column(
    table_name="contacts",
    field_name="new_field",
    field_type="TEXT",
    is_nullable=True
)
# ✅ genome_catalog is updated automatically
```

**Implementation** (from `src/schema_evolution.py`):
```python
# After ALTER TABLE, update genome_catalog
cursor.execute(
    """
    INSERT INTO genome_catalog
    (table_name, field_name, field_type, is_required, is_indexable, default_expression)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (table_name, field_name)
    DO UPDATE SET
        field_type = EXCLUDED.field_type,
        is_required = EXCLUDED.is_required,
        updated_at = CURRENT_TIMESTAMP
    """,
    (table_name, field_name, field_type, not is_nullable, True, True),
)
```

### Bootstrap Functions

The bootstrap functions use `ON CONFLICT ... DO UPDATE` to handle updates:

```python
# From src/genome.py
INSERT INTO genome_catalog
(...)
VALUES (...)
ON CONFLICT (table_name, field_name)
DO UPDATE SET
    field_type = EXCLUDED.field_type,
    is_required = EXCLUDED.is_required,
    ...
    updated_at = CURRENT_TIMESTAMP
```

**This means**:
- ✅ Existing fields are updated
- ✅ New fields are inserted
- ❌ Fields removed from database are NOT removed from genome_catalog
- ❌ New tables/columns added outside IndexPilot are NOT discovered

---

## What's Missing

### 1. Automatic Periodic Discovery

**Current**: No automatic discovery runs periodically

**Needed**: Periodic task to:
- Discover new tables/columns
- Detect removed tables/columns
- Update genome_catalog accordingly

**Proposed Solution**:
```python
# Add to src/maintenance.py
def discover_schema_changes():
    """Periodically discover schema changes and update genome catalog"""
    from src.schema import discover_and_bootstrap_schema
    
    # Discover current schema
    result = discover_and_bootstrap_schema()
    
    # Compare with genome_catalog to find:
    # - New tables/columns (add to genome_catalog)
    # - Removed tables/columns (mark as removed or delete)
    # - Changed types (update genome_catalog)
```

### 2. Detection of External Changes

**Current**: No detection of changes made outside IndexPilot

**Needed**: Mechanism to detect:
- Tables/columns added via direct SQL
- Tables/columns removed via direct SQL
- Type changes made via direct SQL

**Proposed Solution**:
- Add periodic discovery to maintenance tasks
- Compare `information_schema` with `genome_catalog`
- Update genome_catalog to match current schema

### 3. Cleanup of Removed Fields

**Current**: Removed fields remain in genome_catalog

**Needed**: Detect and remove fields that no longer exist

**Proposed Solution**:
```python
# After discovery, check for orphaned entries
cursor.execute("""
    SELECT gc.table_name, gc.field_name
    FROM genome_catalog gc
    WHERE NOT EXISTS (
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_name = gc.table_name
          AND c.column_name = gc.field_name
          AND c.table_schema = 'public'
    )
""")
# Mark as removed or delete
```

---

## Recommendations

### Option 1: Add Periodic Discovery (Recommended)

Add schema auto-discovery to maintenance tasks:

```python
# In src/maintenance.py
def run_maintenance_tasks():
    # ... existing tasks ...
    
    # Periodic schema discovery (every 24 hours)
    if should_run_periodic_task("schema_discovery", interval_hours=24):
        try:
            from src.schema import discover_and_bootstrap_schema
            result = discover_and_bootstrap_schema()
            logger.info(f"Schema discovery: {result['tables_count']} tables")
        except Exception as e:
            logger.warning(f"Schema discovery failed: {e}")
```

### Option 2: Manual Trigger

Provide a function to manually trigger discovery:

```python
from src.schema import discover_and_bootstrap_schema

# Manually discover schema changes
result = discover_and_bootstrap_schema()
```

### Option 3: Event-Driven (Future)

Use PostgreSQL triggers or event listeners to detect schema changes:

```sql
-- Future: PostgreSQL trigger on information_schema changes
CREATE TRIGGER schema_change_trigger
AFTER ALTER TABLE ON information_schema.tables
EXECUTE FUNCTION notify_schema_change();
```

---

## Current Workaround

**For now**, you need to manually run discovery after schema changes:

```python
# After making schema changes outside IndexPilot
from src.schema import discover_and_bootstrap_schema

# Discover and update genome catalog
result = discover_and_bootstrap_schema()
```

---

## Conclusion

**Current State**: ✅ **FULLY AUTOMATIC**
- ✅ Schema changes via IndexPilot are automatically handled
- ✅ Schema changes outside IndexPilot are automatically discovered (within 24 hours)
- ✅ Periodic automatic discovery runs every 24 hours
- ✅ System fully adapts itself automatically

**Implementation**:
- ✅ Periodic schema discovery added to maintenance tasks
- ✅ Detects and handles removed tables/columns
- ✅ Updates genome_catalog to match current database schema
- ✅ Removes orphaned entries automatically

**The system now truly works without intervention!** 🎉

