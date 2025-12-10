# Safe Database Result Handling

**Date**: 08-12-2025  
**Purpose**: Guide to safe database result handling and tuple index enforcement

---

## Problem

Accessing database query results using tuple indices (e.g., `row[0]`, `row[1]`) can cause "tuple index out of range" errors when:
- Queries return fewer columns than expected
- Results are empty
- Cursor type changes (RealDictCursor vs regular cursor)

## Solution

**Always use `safe_get_row_value()` from `src.db`** when accessing database query results.

---

## Enforcement Mechanisms

To prevent "tuple index out of range" errors, we have **multi-level enforcement** that catches unsafe database result access patterns before code reaches production.

### 1. ✅ Pre-commit Hooks (Automatic)

**Location**: `.pre-commit-config.yaml`

The check runs automatically before every commit:

```yaml
- id: check-unsafe-db-access
  name: Check for unsafe database result access
  entry: python scripts/check_unsafe_db_access.py
  always_run: true
```

**How it works**:
- Runs automatically on `git commit`
- Blocks commit if violations found
- Can be run manually: `pre-commit run check-unsafe-db-access --all-files`

**Installation** (if not already installed):
```bash
pip install pre-commit
pre-commit install
```

### 2. ✅ Makefile Quality Checks (Manual/CI)

**Location**: `Makefile`

The check is part of the `quality` target:

```makefile
quality: format lint-check typecheck pylint-check pyright-check circular-check check-db-access
```

**How to run**:
```bash
make check-db-access        # Run only this check
make quality                # Run all quality checks (includes this)
```

**Behavior**:
- **Fails build** if violations found
- Output saved to `docs/audit/toolreports/db_access_check.txt`
- Also displays in terminal

### 3. ✅ Standalone Script (Manual)

**Location**: `scripts/check_unsafe_db_access.py`

Run directly:
```bash
python scripts/check_unsafe_db_access.py
```

**Features**:
- Detects unsafe patterns: `row[0]`, `result[0]`, `fetchone()[0]`, etc.
- Checks all Python files in `src/` and `tests/`
- Ignores test files and safe patterns
- Returns exit code 1 if violations found

### Detected Patterns

The script detects and flags:

1. **Direct tuple access**:
   - `row[0]`, `row[1]`, etc.
   - `result[0]`, `result[1]`, etc.
   - `table_row[0]`, `query_row[0]`, etc.

2. **Direct fetch access**:
   - `cursor.fetchone()[0]`
   - `cursor.fetchall()[0]`
   - `cursor.fetchone()[0][0]` (nested)

3. **Unsafe len checks**:
   - `row[0] if len(row) > 0 else None` (should use helper)

### Safe Patterns (Allowed)

The script **ignores** these safe patterns:

1. **Safe helper usage**:
   ```python
   safe_get_row_value(row, 0, "")
   ```

2. **Dict access**:
   ```python
   row.get("column_name")
   ```

3. **Type checking**:
   ```python
   isinstance(row, dict)
   len(row)  # Just checking length
   ```

4. **Comments**:
   ```python
   # row[0]  # Comment is OK
   ```

---

## How to Fix Violations

When a violation is detected:

1. **Import the helper**:
   ```python
   from src.db import safe_get_row_value
   ```

2. **Replace unsafe access**:
   ```python
   # Before (unsafe):
   value = row[0]
   
   # After (safe):
   value = safe_get_row_value(row, 0, "") or safe_get_row_value(row, "column_name", "")
   ```

3. **For fetchone()**:
   ```python
   # Before (unsafe):
   version = cursor.fetchone()[0]
   
   # After (safe):
   row = cursor.fetchone()
   version = safe_get_row_value(row, 0, "") or safe_get_row_value(row, "version", "")
   ```

---

## Integration with CI/CD

### Current Status

- ✅ **Pre-commit hooks**: Configured and active
- ✅ **Makefile**: Part of quality checks
- ⚠️ **CI/CD**: Not yet configured (no GitHub Actions found)

### Recommended CI/CD Setup

If you add GitHub Actions or other CI/CD, include:

```yaml
- name: Check unsafe database access
  run: make check-db-access
```

Or directly:
```yaml
- name: Check unsafe database access
  run: python scripts/check_unsafe_db_access.py
```

---

## Verification

To verify enforcement is working:

1. **Test the script**:
   ```bash
   python scripts/check_unsafe_db_access.py
   # Should show: "OK: No unsafe database access patterns found"
   ```

2. **Test pre-commit**:
   ```bash
   pre-commit run check-unsafe-db-access --all-files
   ```

3. **Test Makefile**:
   ```bash
   make check-db-access
   ```

---

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

---

## Summary

✅ **Multi-level enforcement is in place**:
- Pre-commit hooks catch violations before commit
- Makefile quality checks catch violations in CI/manual runs
- Script can be run standalone for verification

✅ **Build fails on violations**:
- Pre-commit blocks commits
- Makefile quality checks fail on violations
- Script returns exit code 1

✅ **Pattern detection enhanced**:
- Detects `fetchone()[0]` patterns
- Detects nested tuple access
- Ignores safe patterns correctly

**Result**: "tuple index out of range" errors should not happen again if developers follow the pre-commit hooks and quality checks.

---

**Last Updated**: 08-12-2025

