# Safe Database Result Handling

## Problem

Accessing database query results using tuple indices (e.g., `row[0]`, `row[1]`) can cause "tuple index out of range" errors when:
- Queries return fewer columns than expected
- Results are empty
- Cursor type changes (RealDictCursor vs regular cursor)

## Solution

**Always use `safe_get_row_value()` from `src.db`** when accessing database query results.

## Usage

### Import

```python
from src.db import safe_get_row_value, safe_get_row_values
```

### Single Value Extraction

```python
# Works with both dict (RealDictCursor) and tuple results
row = cursor.fetchone()

# For dict results (RealDictCursor)
name = safe_get_row_value(row, "name", "")

# For tuple results (regular cursor)
name = safe_get_row_value(row, 0, "")

# Automatically handles both
name = safe_get_row_value(row, "name", "") or safe_get_row_value(row, 0, "")
```

### Multiple Values Extraction

```python
# Extract multiple values at once
id_val, name_val, age_val = safe_get_row_values(row, "id", "name", "age", default=0)
# Or with tuple indices
id_val, name_val, age_val = safe_get_row_values(row, 0, 1, 2, default=0)
```

## Enforcement

### Code Review Checklist

- [ ] All `row[0]`, `row[1]`, etc. accesses use `safe_get_row_value()`
- [ ] All database cursors use `RealDictCursor` when fetching data
- [ ] No direct tuple index access without bounds checking

### Linting

The codebase should use `RealDictCursor` consistently. When tuple access is unavoidable, use `safe_get_row_value()`.

## Examples

### ❌ Bad (Unsafe)

```python
row = cursor.fetchone()
name = row[0]  # Can raise "tuple index out of range"
```

### ✅ Good (Safe)

```python
from src.db import safe_get_row_value

row = cursor.fetchone()
name = safe_get_row_value(row, "name", "") or safe_get_row_value(row, 0, "")
```

### ✅ Best (Use RealDictCursor)

```python
cursor = conn.cursor(cursor_factory=RealDictCursor)
row = cursor.fetchone()
name = row.get("name", "")  # Safe with RealDictCursor
```

## Migration Guide

1. Import `safe_get_row_value` from `src.db`
2. Replace `row[0]` with `safe_get_row_value(row, "column_name", default) or safe_get_row_value(row, 0, default)`
3. Replace `row[1]` with `safe_get_row_value(row, "column_name_2", default) or safe_get_row_value(row, 1, default)`
4. Continue for all tuple index accesses

## Why This Matters

- Prevents runtime errors ("tuple index out of range")
- Works with both RealDictCursor (dict) and regular cursor (tuple) results
- Makes code more resilient to schema changes
- Consistent error handling across the codebase

