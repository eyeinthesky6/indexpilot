# Type System Documentation

**Date**: 08-12-2025  
**Purpose**: Complete guide to IndexPilot's type system, including type aliases, TypedDict definitions, type safety improvements, and migration guide

---

## Summary

IndexPilot uses a comprehensive type system to replace `Any` usage with specific types and type aliases. This improves type safety, IDE autocomplete, and catches errors at development time.

All type definitions are centralized in `src/type_definitions.py`.

---

## Type Definitions Module

### Location

All types are defined in `src/type_definitions.py` using `TypeAlias` to satisfy strict Any checking.

### What's Included

- **TypedDict definitions** for structured data (verification results, audit trails, health checks)
- **Type aliases** for common patterns (JSONValue, DatabaseRow, TenantID, etc.)
- **Specific types** replacing `Any` where possible

---

## Core Type Aliases

### Identity Types

```python
TenantID: TypeAlias = int
TableName: TypeAlias = str
FieldName: TypeAlias = str
```

**Usage**: Use these instead of raw `int` or `str` when the semantic meaning is important.

```python
# Before
def get_tenant_data(tenant_id: int) -> dict:
    ...

# After
from src.type_definitions import TenantID
def get_tenant_data(tenant_id: TenantID) -> dict:
    ...
```

---

## List Type Aliases

### String Lists
```python
StringList: TypeAlias = list[str]
```

**Usage**: For error messages, warnings, log entries, etc.

```python
from src.type_definitions import StringList

def validate_data(data: dict) -> tuple[bool, StringList]:
    errors: StringList = []
    # ... validation logic
    return len(errors) == 0, errors
```

### Integer Lists
```python
IntList: TypeAlias = list[int]
TenantIDList: TypeAlias = list[TenantID]
```

**Usage**: For collections of IDs, counts, etc.

```python
from src.type_definitions import TenantIDList

def verify_tenants(tenant_ids: TenantIDList) -> VerificationResult:
    ...
```

---

## Dictionary Type Aliases

### String Dictionary
```python
StringDict: TypeAlias = dict[str, str]
```

**Usage**: For key-value mappings where both are strings.

### Boolean Dictionary
```python
BoolDict: TypeAlias = dict[str, bool]
```

**Usage**: For feature flags, enabled/disabled maps.

### Nested Boolean Dictionary
```python
StringBoolDict: TypeAlias = dict[str, dict[str, bool]]
```

**Usage**: For nested feature configurations.

```python
from src.type_definitions import StringBoolDict

features: StringBoolDict = {
    'auto_indexing': {'enabled': True},
    'stats_collection': {'enabled': False}
}
```

### Health Status Dictionary
```python
HealthDict: TypeAlias = dict[str, str | float | None]
```

**Usage**: For health check results, status dictionaries.

```python
from src.type_definitions import HealthDict

def get_health_status() -> HealthDict:
    return {
        'status': 'healthy',
        'latency_ms': 12.5,
        'error': None
    }
```

---

## Tuple Type Aliases

### Boolean-String Tuple (Result Pattern)
```python
BoolStrTuple: TypeAlias = tuple[bool, str | None]
```

**Usage**: For functions that return (success, message) pattern.

```python
from src.type_definitions import BoolStrTuple

def can_create_index(table: str) -> BoolStrTuple:
    if condition:
        return True, None
    return False, "Too many indexes already exist"
```

**Used in**: `src/write_performance.py::can_create_index_for_table()`

### Boolean-Float Tuple (Rate Limit Pattern)
```python
BoolFloatTuple: TypeAlias = tuple[bool, float]
```

**Usage**: For rate limiting functions that return (allowed, retry_after).

```python
from src.type_definitions import BoolFloatTuple

def is_allowed(key: str) -> BoolFloatTuple:
    if rate_limit_exceeded:
        return False, 60.0  # Retry after 60 seconds
    return True, 0.0
```

**Used in**: `src/rate_limiter.py::is_allowed()`

---

## Query Types

### Query Parameters
```python
QueryParam: TypeAlias = str | int | float | bool | None | list[str | int | float]
QueryParams: TypeAlias = tuple[QueryParam, ...]
```

**Usage**: For SQL query parameters.

```python
from src.type_definitions import QueryParams

def execute_query(query: str, params: QueryParams | None = None) -> QueryResults:
    ...
```

### Query Results
```python
QueryResult: TypeAlias = dict[str, JSONValue]
QueryResults: TypeAlias = list[QueryResult]
```

**Usage**: For database query results.

```python
from src.type_definitions import QueryResults

def fetch_users() -> QueryResults:
    return execute_query("SELECT * FROM users")
```

---

## JSON Types

### JSON Values
```python
JSONValue: TypeAlias = str | int | float | bool | None | list['JSONValue'] | dict[str, 'JSONValue']
JSONDict: TypeAlias = dict[str, 'JSONValue']
```

**Usage**: For JSON-serializable data structures.

```python
from src.type_definitions import JSONDict

def serialize_config(config: JSONDict) -> str:
    return json.dumps(config)
```

---

## Configuration Types

### Configuration Dictionary
```python
ConfigDict: TypeAlias = dict[str, JSONValue]
```

**Usage**: For configuration data structures.

```python
from src.type_definitions import ConfigDict

class ConfigLoader:
    def __init__(self):
        self.config: ConfigDict = {}
```

---

## Database Types

### Database Row
```python
DatabaseRow: TypeAlias = dict[str, str | int | float | bool | None]
```

**Usage**: For database row results from RealDictCursor.

```python
from src.type_definitions import DatabaseRow

def fetch_row() -> DatabaseRow | None:
    cursor.execute("SELECT * FROM users LIMIT 1")
    return cursor.fetchone()
```

---

## TypedDict Definitions

For structured data, use TypedDict instead of type aliases:

```python
class VerificationResult(TypedDict):
    passed: bool
    errors: StringList
    warnings: StringList
    details: VerificationDetails
```

**Key TypedDicts**:
- `VerificationResult` - Verification function results
- `VerificationDetails` - Detailed verification information
- `VerificationSummary` - Summary of verification results
- `ComprehensiveVerificationResults` - Complete verification results
- `DatabaseHealthStatus` - Database health checks
- `SystemHealthStatus` - System health checks
- `AuditDetails` - Audit trail entries
- `IndexCreationResult` - Index creation results
- `MutationLogEntry` - Mutation log entries

### Verification Types

```python
from src.type_definitions import (
    VerificationResult,
    VerificationDetails,
    VerificationSummary,
    ComprehensiveVerificationResults
)

# Before (using Any):
def verify_mutation_log(...) -> dict[str, Any]:
    results: dict[str, Any] = {...}

# After (using TypedDict):
def verify_mutation_log(...) -> VerificationResult:
    results: VerificationResult = {...}
```

---

## What Was Implemented

### Updated Files

- ✅ `src/simulation_verification.py` - All `Any` replaced with specific types
- ✅ `mypy.ini` - Added warnings for Any usage
- ✅ `src/type_definitions.py` - Centralized type definitions module
- ✅ `src/query_executor.py` - Uses `QueryParams`, `QueryResults`
- ✅ `src/health_check.py` - Uses `DatabaseHealthStatus`, `SystemHealthStatus`
- ✅ `src/audit.py` - Uses `AuditDetails`, `MutationLogEntry`, `JSONDict`
- ✅ `src/config_loader.py` - Uses `ConfigDict`, `JSONValue`
- ✅ `src/write_performance.py` - Uses `BoolStrTuple`
- ✅ `src/rate_limiter.py` - Uses `BoolFloatTuple`
- ✅ `src/pattern_detection.py` - Uses `JSONDict`

---

## Migration Guide

### Step 1: Identify Any Usage

Find files using `Any`:

```bash
grep -r "from typing import.*Any" src/
grep -r ": Any" src/
```

### Step 2: Create Type Definitions

For structured data, use `TypedDict`:

```python
from typing import TypedDict

class MyResult(TypedDict):
    """Result structure"""
    success: bool
    data: dict[str, str | int]
    errors: list[str]
```

For simple aliases, use type aliases:

```python
# In src/types.py
MyCustomType = dict[str, list[int]]
```

### Step 3: Replace Any

```python
# Before
def my_function() -> dict[str, Any]:
    return {'key': 'value'}

# After
from src.type_definitions import MyResult

def my_function() -> MyResult:
    return {'key': 'value'}
```

### Step 4: Update Function Signatures

```python
# Before
def process_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    ...

# After
from src.type_definitions import JSONDict, QueryResults

def process_data(data: JSONDict) -> QueryResults:
    ...
```

---

## Mypy Configuration

Current settings in `mypy.ini`:

```ini
warn_return_any = True          # Warn when functions return Any
check_untyped_defs = True        # Check untyped function definitions
no_implicit_optional = True      # Require explicit Optional
strict_equality = True           # Strict type equality checks
```

### Future: Ban Any Usage

To completely ban `Any` usage, enable these options:

```ini
disallow_any_generics = True     # Ban Any in generic types
disallow_any_unimported = True   # Ban Any from unimported modules
disallow_any_expr = True         # Ban Any expressions
disallow_any_decorated = True    # Ban Any in decorated functions
disallow_any_explicit = True     # Ban explicit Any annotations
```

**Note**: Enable gradually to avoid breaking existing code.

---

## Benefits

### 1. Type Safety

- Catch type errors at development time
- Prevent runtime type mismatches
- Better IDE autocomplete and error detection

### 2. Documentation

- Types serve as inline documentation
- Clear contracts for function parameters and returns
- Easier to understand code structure

### 3. Refactoring Safety

- Type checker catches breaking changes
- Safer large-scale refactoring
- Better code navigation

### 4. Team Collaboration

- Clearer code contracts
- Reduced need for runtime type checking
- Better code reviews

---

## Examples

### Example 1: Verification Results

**Before:**
```python
def verify_feature() -> dict[str, Any]:
    return {
        'passed': True,
        'errors': [],
        'warnings': [],
        'details': {}
    }
```

**After:**
```python
from src.type_definitions import VerificationResult

def verify_feature() -> VerificationResult:
    return {
        'passed': True,
        'errors': [],
        'warnings': [],
        'details': {}
    }
```

### Example 2: Query Results

**Before:**
```python
def execute_query(query: str) -> list[dict[str, Any]]:
    ...
```

**After:**
```python
from src.type_definitions import QueryResults

def execute_query(query: str) -> QueryResults:
    ...
```

### Example 3: Configuration Values

**Before:**
```python
def get_config(key: str) -> Any:
    ...
```

**After:**
```python
from src.type_definitions import JSONValue

def get_config(key: str) -> JSONValue:
    ...
```

---

## Files to Migrate (Priority Order)

### High Priority (New/Critical Files)
1. ✅ `src/simulation_verification.py` - **DONE**
2. `src/query_executor.py` - Replace `Any` in query results
3. `src/health_check.py` - Use `DatabaseHealthStatus`, `SystemHealthStatus`
4. `src/audit.py` - Use `AuditDetails`, `MutationLogEntry`

### Medium Priority (Core Features)
5. `src/auto_indexer.py` - Use `IndexCreationResult`
6. `src/scaled_reporting.py` - Use specific result types
7. `src/config_loader.py` - Use `JSONValue`, `JSONDict`
8. `src/monitoring.py` - Use specific health check types

### Low Priority (Supporting Files)
9. `src/schema_evolution.py` - Use specific schema types
10. `src/maintenance.py` - Use specific maintenance types
11. Other files as needed

---

## Best Practices

### 1. Use TypedDict for Structured Data

```python
# Good
class UserData(TypedDict):
    id: int
    name: str
    email: str

# Avoid
UserData = dict[str, Any]
```

### 2. Use Type Aliases for Common Patterns

```python
# Good
TenantID = int
TableName = str

# Avoid
def process(tenant: Any, table: Any):
    ...
```

### 3. Prefer Union Types Over Any

```python
# Good
def process(value: str | int | None) -> str:
    ...

# Avoid
def process(value: Any) -> str:
    ...
```

### 4. Use total=False for Optional TypedDict Fields

```python
# Good
class Details(TypedDict, total=False):
    optional_field: str
    required_field: int  # Still required if present

# Avoid
class Details(TypedDict):
    optional_field: str | None  # Less clear
```

---

## Checking Type Safety

### Run Type Checker

```bash
# Check specific files
python -m mypy src/simulation_verification.py --config-file mypy.ini

# Check all files
python -m mypy src/ --config-file mypy.ini

# Check with strict Any warnings
python -m mypy src/ --config-file mypy.ini --warn-return-any
```

### Find Any Usage

```bash
# Find files using Any
grep -r "from typing import.*Any" src/
grep -r ": Any" src/
grep -r "Any\]" src/
```

---

## Migration Checklist

For each file:

- [ ] Identify all `Any` usage
- [ ] Create or use existing type definitions in `src/types.py`
- [ ] Replace `Any` with specific types
- [ ] Update function signatures
- [ ] Run type checker: `mypy filename.py`
- [ ] Run tests: `pytest tests/`
- [ ] Verify no regressions

---

## Current Status

- ✅ Type definitions module created (`src/types.py`)
- ✅ `simulation_verification.py` fully migrated
- ✅ Mypy configuration updated
- ⏳ Other files: 19 files still using `Any` (95 total occurrences)

---

## Next Steps

1. **Migrate high-priority files** (query_executor, health_check, audit)
2. **Add more type definitions** as needed
3. **Enable stricter mypy settings** gradually
4. **Document type patterns** for team reference

---

**Last Updated**: 05-12-2025

