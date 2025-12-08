# Tuple Index Access Enforcement

**Date**: 08-12-2025  
**Purpose**: Prevent "tuple index out of range" errors through automated linting

## Overview

To prevent "tuple index out of range" errors, we have **multi-level enforcement** that catches unsafe database result access patterns before code reaches production.

## Enforcement Levels

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
- **Fails build** if violations found (removed `|| true`)
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

## Detected Patterns

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

## Safe Patterns (Allowed)

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

## Summary

✅ **Multi-level enforcement is in place**:
- Pre-commit hooks catch violations before commit
- Makefile quality checks catch violations in CI/manual runs
- Script can be run standalone for verification

✅ **Build fails on violations**:
- Removed `|| true` from Makefile
- Pre-commit blocks commits
- Script returns exit code 1

✅ **Pattern detection enhanced**:
- Detects `fetchone()[0]` patterns
- Detects nested tuple access
- Ignores safe patterns correctly

**Result**: "tuple index out of range" errors should not happen again if developers follow the pre-commit hooks and quality checks.

