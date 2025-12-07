# IndexPilot - Bug Fix Flow

**Last Updated**: 07-12-2025

---

## ⚠️ CRITICAL RULE: All Errors Must Be Resolved

**All errors MUST be properly fixed, not suppressed, unless there is an absolute technical necessity that prevents resolution. Type errors, lint errors, and runtime errors must be addressed at their root cause.**

### Error Resolution Policy

1. **No Suppression Without Justification**: Type ignores (`# type: ignore`) and suppressions are ONLY allowed when:
   - There is a documented technical limitation (e.g., third-party library type stubs are missing)
   - The error is a false positive that cannot be resolved through proper typing
   - A bug report has been filed with the type checker maintainers

2. **Root Cause Analysis**: For every error:
   - Identify the root cause
   - Fix the underlying issue, not just the symptom
   - Add proper type annotations, type guards, or type narrowing as needed

3. **Documentation**: If an error cannot be resolved:
   - Document why in code comments
   - Add a TODO with a clear path to resolution
   - Update this document with the exception

---

## Flow

`make lint` → `make format` → `make typecheck` → Manual fixes → `make run-tests` → `make check`

---

## Step 1: Auto-Fix

```bash
make lint
# Fixes: imports, unused code, style issues
```

**Requirement**: All lint errors must be resolved. No exceptions.

---

## Step 2: Auto-Format

```bash
make format
# Fixes: indentation, spacing, formatting
```

---

## Step 3: Type Check

```bash
make typecheck
# Identifies: missing type hints, type mismatches, union type issues
```

**Requirement**: All type errors must be resolved through:
- Proper type annotations
- Type narrowing with `isinstance()` checks
- Type guards for union types
- Correct use of `JSONDict`, `JSONValue` instead of `Any`

---

## Step 4: Manual Fixes (CRITICAL)

**Fix ALL errors found in previous steps:**

1. **Type Errors**:
   - Replace `Any` with proper types (`JSONDict`, `JSONValue`, specific types)
   - Add type narrowing for union types using `isinstance()` checks
   - Fix dict type mismatches by ensuring values match `JSONValue` type
   - Add type guards before attribute access on union types

2. **Logic Errors**: Fix incorrect logic, missing checks, wrong assumptions

3. **Import Errors**: Fix missing imports, circular dependencies

4. **Syntax Errors**: Fix syntax issues (usually caught by lint)

5. **Runtime Errors**: Add error handling, validate inputs, check for None

**Check**: `mypy_output.txt`, `ruff_output.txt`, IDE errors

**Root Cause Analysis**: For each error:
- Why does it occur?
- What is the correct type/behavior?
- How can it be fixed properly?

---

## Step 5: Test

```bash
make run-tests
# Verify: all tests pass
```

**Requirement**: All tests must pass. Fix any test failures.

---

## Step 6: Verify

```bash
make check  # lint + typecheck
```

**Check**: 
- ✅ No lint errors
- ✅ No type errors  
- ✅ All tests pass

**If errors remain**: Return to Step 4 and fix them properly. Do not proceed until all errors are resolved.

---

## Quick Commands

```bash
make lint && make format  # Auto-fix all
make check                # Check all
make run-tests            # Test all
make check && make run-tests  # Full verify
```

---

## Common Fixes

### Import Errors
- **Fix**: `make lint` (auto-fixes unused imports)
- **Root Cause**: Unused or missing imports

### Type Errors - Explicit Any
- **Fix**: Replace `dict[str, Any]` with `JSONDict`
- **Fix**: Replace `list[Any]` with `list[JSONValue]`
- **Root Cause**: Using `Any` instead of proper types

### Type Errors - Union Types
- **Fix**: Add `isinstance()` checks before operations
- **Example**: 
  ```python
  value = data.get("key")
  if isinstance(value, (int, float)):
      result = value + 1  # Now type-safe
  ```
- **Root Cause**: Operations on union types without narrowing

### Type Errors - Dict Type Mismatches
- **Fix**: Ensure dict values are `JSONValue` compatible
- **Fix**: Use `cast()` or type narrowing if necessary
- **Root Cause**: Dict values don't match expected `JSONValue` type

### Syntax Errors
- **Fix**: `make lint` (auto-fixes most)
- **Root Cause**: Syntax violations

### Runtime Errors
- **Fix**: Add error handling, check logs, validate inputs
- **Root Cause**: Missing validation or error handling

---

## Error Resolution Examples

### Example 1: Union Type Narrowing

**Error**: `Item "int" of "str | int | float" has no attribute "lower"`

**Root Cause**: Trying to call `.lower()` on a union type without checking if it's a string.

**Fix**:
```python
value = data.get("field")
if isinstance(value, str):
    result = value.lower()  # Type-safe
else:
    result = str(value).lower()  # Convert if needed
```

### Example 2: Dict Type Mismatch

**Error**: `Dict entry has incompatible type "str": "list[str]"`

**Root Cause**: `list[str]` is not directly assignable to `JSONValue` (which expects `list[JSONValue]`).

**Fix**:
```python
from typing import cast
from src.type_definitions import JSONDict, JSONValue

result: JSONDict = {
    "fields": cast(list[JSONValue], field_list)  # Type cast if needed
}
```

### Example 3: Explicit Any

**Error**: `Explicit "Any" is not allowed`

**Root Cause**: Using `Any` type annotation.

**Fix**:
```python
# Before
def func(data: dict[str, Any]) -> dict[str, Any]:
    ...

# After
from src.type_definitions import JSONDict

def func(data: JSONDict) -> JSONDict:
    ...
```

---

## Success Criteria

✅ **All lint errors resolved**  
✅ **All type errors resolved**  
✅ **All tests passing**  
✅ **No suppressions without justification**  
✅ **Root causes identified and fixed**

---

**Remember**: Quality over speed. Fix errors properly, not quickly.

