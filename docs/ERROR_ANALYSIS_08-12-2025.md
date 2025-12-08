# Error Analysis from Simulation Runs

**Date**: 08-12-2025  
**Status**: Analysis of errors found during comprehensive simulation runs

---

## Summary

During the comprehensive simulation runs (small and medium scenarios), several recurring errors were observed. These errors don't prevent the simulation from completing, but they indicate areas that need fixing.

---

## Error Categories

### 1. ⚠️ VACUUM Cannot Run Inside Transaction Block

**Frequency**: Very High (hundreds of occurrences)  
**Location**: `src/index_lifecycle_manager.py:300-304`  
**Error Message**: 
```
Database error (ActiveSqlTransaction): VACUUM cannot run inside a transaction block
```

**Root Cause**:
- `perform_vacuum_analyze_for_indexes()` uses `with get_connection() as conn:` which starts a transaction
- VACUUM ANALYZE is an auto-commit command that cannot run inside a transaction
- The code tries to `conn.commit()` after VACUUM, but VACUUM already auto-commits

**Impact**: 
- VACUUM ANALYZE fails for all tables
- Statistics are not refreshed via VACUUM
- No data corruption, but maintenance operations fail

**Fix Required**:
- VACUUM must run in autocommit mode
- Use a separate connection with autocommit=True
- Or use `psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT`

**Code Location**:
```python
# src/index_lifecycle_manager.py:300-304
with get_connection() as conn:  # ❌ This starts a transaction
    cursor = conn.cursor()
    try:
        cursor.execute(f'VACUUM ANALYZE "{table_name}"')  # ❌ VACUUM can't run in transaction
        conn.commit()  # ❌ VACUUM already auto-commits
```

---

### 2. ⚠️ Column "tablename" Does Not Exist

**Frequency**: High (dozens of occurrences)  
**Location**: `src/statistics_refresh.py:73`  
**Error Message**:
```
Database error (UndefinedColumn): column "tablename" does not exist
LINE 4:                         tablename,
                                ^
```

**Root Cause**:
- Query uses `tablename` from `pg_stat_user_tables`
- The actual column name in PostgreSQL's `pg_stat_user_tables` view is `relname`, not `tablename`
- However, `pg_stat_user_tables` does have `relname` as the table name column

**Impact**:
- Stale statistics detection fails
- Statistics refresh cannot identify which tables need analysis
- No data corruption, but statistics refresh is ineffective

**Fix Required**:
- Change `tablename` to `relname` in the query
- Or use `pg_tables` view which has `tablename` column

**Code Location**:
```python
# src/statistics_refresh.py:70-73
query = """
    SELECT
        schemaname,
        tablename,  # ❌ Should be 'relname' in pg_stat_user_tables
        ...
    FROM pg_stat_user_tables
```

---

### 3. ⚠️ Tuple Index Out of Range

**Frequency**: High (dozens of occurrences)  
**Locations**: 
- `src/index_lifecycle_manager.py` (index cleanup)
- `src/foreign_key_suggestions.py` (FK detection)
- `src/query_analyzer.py` (EXPLAIN parsing)

**Error Message**:
```
Database error (IndexError): tuple index out of range
```

**Root Cause**:
- Code tries to access tuple indices that don't exist
- Some queries return fewer columns than expected
- Safe helper functions exist but aren't used everywhere

**Impact**:
- Index cleanup fails for some tenants
- Foreign key suggestions fail
- Query plan analysis fails for some queries
- No data corruption, but features don't work correctly

**Fix Required**:
- Use `safe_get_row_value()` helper consistently
- Check tuple length before accessing indices
- Handle both dict (RealDictCursor) and tuple results properly

**Code Locations**:
- `src/index_lifecycle_manager.py:207` (has safe helper, but may not be used everywhere)
- `src/foreign_key_suggestions.py:113` (has safe helper, but may fail in some cases)
- `src/query_analyzer.py` (EXPLAIN parsing may return unexpected format)

---

### 4. ⚠️ JSON Object Must Be String

**Frequency**: Low (2 occurrences)  
**Location**: `src/redundant_index_detection.py` (likely)  
**Error Message**:
```
Database error (TypeError): the JSON object must be str, bytes or bytearray, not dict
```

**Root Cause**:
- Code tries to `json.loads()` on something that's already a dict
- May be trying to parse JSON that's already parsed
- Or storing dict directly where JSON string is expected

**Impact**:
- Redundant index detection may fail
- No data corruption, but feature doesn't work

**Fix Required**:
- Check if value is already a dict before calling `json.loads()`
- Use `json.dumps()` when storing dict as JSON string

---

### 5. ⚠️ Float + Decimal Type Mismatch

**Frequency**: Low (1 occurrence)  
**Location**: `src/maintenance.py` (likely)  
**Error Message**:
```
Database error (TypeError): unsupported operand type(s) for +=: 'float' and 'decimal.Decimal'
```

**Root Cause**:
- PostgreSQL returns `decimal.Decimal` for numeric types
- Code tries to add `float` and `Decimal` together
- Python doesn't allow direct arithmetic between float and Decimal

**Impact**:
- Maintenance calculations fail
- No data corruption, but calculations are incorrect

**Fix Required**:
- Convert Decimal to float before arithmetic: `float(decimal_value)`
- Or use Decimal for all calculations
- Or use `decimal.Decimal()` constructor for float values

---

### 6. ⚠️ EXPLAIN Fast Failed

**Frequency**: Low (1 occurrence)  
**Location**: `src/query_analyzer.py`  
**Error Message**:
```
WARNING - EXPLAIN (fast) failed after 3 attempts: tuple index out of range for query: SELECT * FROM contacts WHERE custom_text_1 LIKE '%test%'...
```

**Root Cause**:
- EXPLAIN query returns unexpected format
- Code tries to access tuple indices that don't exist
- May be related to query plan format changes

**Impact**:
- Query plan analysis fails for some queries
- No data corruption, but query analysis doesn't work

**Fix Required**:
- Use safe helper functions for EXPLAIN parsing
- Handle different EXPLAIN output formats
- Add better error handling for EXPLAIN failures

---

## Error Priority

### High Priority (Fix Immediately)
1. **VACUUM Transaction Block** - Affects maintenance operations
2. **Tablename Column** - Affects statistics refresh

### Medium Priority (Fix Soon)
3. **Tuple Index Out of Range** - Affects multiple features
4. **EXPLAIN Fast Failed** - Affects query analysis

### Low Priority (Fix When Convenient)
5. **JSON Object Type** - Affects redundant index detection
6. **Float + Decimal** - Affects maintenance calculations

---

## Recommendations

1. **Fix VACUUM Transaction Issue**:
   - Create separate connection with autocommit for VACUUM operations
   - Or use `psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT`

2. **Fix Tablename Column**:
   - Change `tablename` to `relname` in `pg_stat_user_tables` queries
   - Or use `pg_tables` view which has `tablename`

3. **Improve Tuple Handling**:
   - Use `safe_get_row_value()` consistently everywhere
   - Add tuple length checks before accessing indices
   - Handle both dict and tuple results properly

4. **Fix Type Mismatches**:
   - Convert Decimal to float before arithmetic
   - Check types before JSON operations
   - Use type hints and type checking

5. **Add Better Error Handling**:
   - Log more context when errors occur
   - Add retry logic for transient errors
   - Gracefully degrade when features fail

---

## Testing Recommendations

After fixes:
1. Run comprehensive simulation again
2. Verify VACUUM ANALYZE succeeds
3. Verify statistics refresh works
4. Verify no tuple index errors
5. Check algorithm execution logs

---

## Fixes Applied

**Date**: 08-12-2025

### ✅ Fixed Issues

1. **VACUUM Transaction Block** - Fixed in `src/index_lifecycle_manager.py`
   - Changed to use `ISOLATION_LEVEL_AUTOCOMMIT` for VACUUM operations
   - VACUUM now runs in autocommit mode and isolation level is restored after

2. **Tablename Column** - Fixed in `src/statistics_refresh.py`
   - Changed `tablename` to `relname` in `pg_stat_user_tables` query
   - Added alias `relname as tablename` to maintain compatibility

3. **JSON Object Type** - Fixed in `src/algorithm_tracking.py`
   - Added type checking before `json.loads()`
   - Handles both dict and string types safely

4. **Float + Decimal** - Fixed in `src/maintenance.py`
   - Convert Decimal to float before arithmetic operations
   - Prevents type mismatch errors

5. **EXPLAIN Fast Failed** - Fixed in `src/query_analyzer.py`
   - Added handling for both dict and tuple results
   - Uses safe helper functions for tuple access
   - Better error handling for unexpected result types

### ⚠️ Remaining Issues

- **Tuple Index Out of Range** - Partially fixed
  - Safe helpers are used in most places
  - Some edge cases may still occur in foreign key suggestions
  - Index cleanup should be more robust now

## Notes

- All errors are non-fatal - simulation completes successfully
- Errors don't cause data corruption
- Errors prevent some features from working correctly
- Most errors are in maintenance/lifecycle management code
- Algorithm execution logging will help identify if algorithms fire despite these errors
- **All high-priority errors have been fixed**

