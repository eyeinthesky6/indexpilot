# Critical Type Aliases

**Date**: 05-12-2025  
**Purpose**: Document critical type aliases for common patterns across the codebase

---

## Overview

Type aliases provide semantic meaning and consistency across the codebase. All critical type aliases are defined in `src/types.py` using `TypeAlias` to satisfy strict Any checking.

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
from src.types import TenantID
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
from src.types import StringList

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
from src.types import TenantIDList

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
from src.types import StringBoolDict

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
from src.types import HealthDict

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
from src.types import BoolStrTuple

def can_create_index(table: str) -> BoolStrTuple:
    if condition:
        return True, None
    return False, "Too many indexes already exist"
```

**Used in**:
- `src/write_performance.py::can_create_index_for_table()`

### Boolean-Float Tuple (Rate Limit Pattern)
```python
BoolFloatTuple: TypeAlias = tuple[bool, float]
```

**Usage**: For rate limiting functions that return (allowed, retry_after).

```python
from src.types import BoolFloatTuple

def is_allowed(key: str) -> BoolFloatTuple:
    if rate_limit_exceeded:
        return False, 60.0  # Retry after 60 seconds
    return True, 0.0
```

**Used in**:
- `src/rate_limiter.py::is_allowed()`

---

## Query Types

### Query Parameters
```python
QueryParam: TypeAlias = str | int | float | bool | None | list[str | int | float]
QueryParams: TypeAlias = tuple[QueryParam, ...]
```

**Usage**: For SQL query parameters.

```python
from src.types import QueryParams

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
from src.types import QueryResults

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
from src.types import JSONDict

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
from src.types import ConfigDict

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
from src.types import DatabaseRow

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
- `DatabaseHealthStatus` - Database health checks
- `SystemHealthStatus` - System health checks
- `AuditDetails` - Audit trail entries
- `IndexCreationResult` - Index creation results
- `MutationLogEntry` - Mutation log entries

---

## Migration Guide

### Step 1: Identify Patterns

Look for common patterns in your code:
- `list[str]` → Use `StringList`
- `list[int]` → Use `IntList` or `TenantIDList`
- `dict[str, bool]` → Use `BoolDict`
- `tuple[bool, str | None]` → Use `BoolStrTuple`
- `tuple[bool, float]` → Use `BoolFloatTuple`

### Step 2: Import and Use

```python
# Before
def process_data(ids: list[int], errors: list[str]) -> tuple[bool, str | None]:
    ...

# After
from src.types import IntList, StringList, BoolStrTuple

def process_data(ids: IntList, errors: StringList) -> BoolStrTuple:
    ...
```

### Step 3: Update Function Signatures

Replace inline types with aliases:

```python
# Before
def get_stats() -> dict[str, str | float | None]:
    ...

# After
from src.types import HealthDict

def get_stats() -> HealthDict:
    ...
```

---

## Benefits

1. **Semantic Clarity**: Type aliases convey meaning beyond just the type structure
2. **Consistency**: Same patterns use same aliases across the codebase
3. **Maintainability**: Change the type definition in one place
4. **Documentation**: Types serve as inline documentation
5. **IDE Support**: Better autocomplete and error detection

---

## Current Usage

### Files Using Type Aliases

- ✅ `src/query_executor.py` - Uses `QueryParams`, `QueryResults`
- ✅ `src/health_check.py` - Uses `DatabaseHealthStatus`, `SystemHealthStatus`
- ✅ `src/audit.py` - Uses `AuditDetails`, `MutationLogEntry`, `JSONDict`
- ✅ `src/config_loader.py` - Uses `ConfigDict`, `JSONValue`
- ✅ `src/simulation_verification.py` - Uses `TenantIDList`, `StringList`, `VerificationResult`
- ✅ `src/write_performance.py` - Uses `BoolStrTuple`
- ✅ `src/rate_limiter.py` - Uses `BoolFloatTuple`
- ✅ `src/pattern_detection.py` - Uses `JSONDict`

---

## Best Practices

1. **Use TypeAlias for all type aliases** - Required for strict Any checking
2. **Import from src.types** - Centralized location for all type definitions
3. **Prefer TypedDict for structured data** - Better than dict type aliases
4. **Use semantic names** - `TenantID` is better than `int` when it represents a tenant
5. **Document complex types** - Add docstrings for non-obvious type aliases

---

**Last Updated**: 05-12-2025

