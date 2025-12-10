# Type System Improvements - Models and Contracts

**Date**: 08-12-2025  
**Status**: Proposal

## Current State

### Types Are NOT Derived from Models

**Current Architecture:**
- Types manually defined in `src/type_definitions.py` using `TypedDict`
- Database schema defined separately in SQL DDL (`src/schema/initialization.py`)
- No automatic type generation from schema
- Types and schema can drift out of sync

**Example:**
```python
# type_definitions.py - Manual type definition
class VerificationDetails(TypedDict, total=False):
    total_index_mutations: int
    # ... manually maintained

# schema/initialization.py - Separate schema definition
CREATE TABLE genome_catalog (
    id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    # ... separate definition
)
```

## Recommendations

### Option 1: Generate Types from Database Schema (Recommended)

**Approach:** Automatically generate Python types from PostgreSQL schema

**Benefits:**
- ✅ Types always match database schema
- ✅ Single source of truth (database schema)
- ✅ Catches schema changes at type-check time
- ✅ Reduces manual maintenance

**Implementation:**
```python
# tools/generate_types_from_schema.py
from typing import get_type_hints
import psycopg2
from psycopg2.extras import RealDictCursor

def generate_typedict_from_table(table_name: str) -> str:
    """Generate TypedDict from PostgreSQL table schema"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        type_def = f"class {table_name.capitalize()}Row(TypedDict):\n"
        for col in columns:
            py_type = _map_postgres_to_python_type(col['data_type'])
            if col['is_nullable'] == 'YES':
                py_type = f"{py_type} | None"
            type_def += f"    {col['column_name']}: {py_type}\n"
        return type_def
```

**Usage:**
```python
# Generated types (auto-updated)
from src.generated_types import GenomeCatalogRow, ExpressionProfileRow

def get_genome_entry(table: str, field: str) -> GenomeCatalogRow | None:
    # Type-safe access
    row = cursor.fetchone()
    return row  # Type checker knows exact structure
```

### Option 2: Use Pydantic Models (Alternative)

**Approach:** Define Pydantic models that match database schema

**Benefits:**
- ✅ Runtime validation
- ✅ Automatic serialization/deserialization
- ✅ Better error messages
- ✅ Can generate from schema

**Trade-offs:**
- ⚠️ Adds dependency (pydantic)
- ⚠️ Slight performance overhead
- ⚠️ Different from current TypedDict approach

**Example:**
```python
from pydantic import BaseModel

class GenomeCatalogRow(BaseModel):
    id: int
    table_name: str
    field_name: str
    field_type: str
    is_required: bool = False
    is_indexable: bool = True
    # ... with validation
```

### Option 3: Design-by-Contract (Useful Addition)

**Approach:** Add contract validation for critical functions

**Benefits:**
- ✅ Runtime validation of preconditions/postconditions
- ✅ Better error messages
- ✅ Documents function contracts explicitly
- ✅ Catches bugs early

**Implementation Options:**

#### A. Using `icontract` library:
```python
import icontract

@icontract.require(lambda tenant_id: tenant_id > 0)
@icontract.ensure(lambda result: result is not None or len(result) == 0)
def get_expression_profile(tenant_id: int) -> list[ExpressionProfileRow]:
    """Get expression profile for tenant"""
    # Precondition: tenant_id must be positive
    # Postcondition: result is never None
    ...
```

#### B. Using custom decorators:
```python
def contract(pre=None, post=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if pre:
                assert pre(*args, **kwargs), f"Precondition failed: {pre.__name__}"
            result = func(*args, **kwargs)
            if post:
                assert post(result), f"Postcondition failed: {post.__name__}"
            return result
        return wrapper
    return decorator

@contract(
    pre=lambda tenant_id: tenant_id > 0,
    post=lambda result: isinstance(result, list)
)
def get_expression_profile(tenant_id: int) -> list[ExpressionProfileRow]:
    ...
```

#### C. Using type guards (already partially used):
```python
from typing import TypeGuard

def is_valid_tenant_id(value: object) -> TypeGuard[int]:
    """Type guard for valid tenant ID"""
    return isinstance(value, int) and value > 0

def get_expression_profile(tenant_id: int) -> list[ExpressionProfileRow]:
    if not is_valid_tenant_id(tenant_id):
        raise ValueError(f"Invalid tenant_id: {tenant_id}")
    ...
```

## Recommended Approach

### Phase 1: Generate Types from Schema (High Value, Low Risk)

1. Create `tools/generate_types_from_schema.py`
2. Generate TypedDict classes from `information_schema`
3. Auto-generate on schema changes
4. Use in codebase for type safety

**Files to create:**
- `tools/generate_types_from_schema.py` - Type generator
- `src/generated_types.py` - Generated types (gitignored, auto-generated)
- `Makefile` target: `make generate-types`

### Phase 2: Add Contracts for Critical Functions (Medium Value)

1. Add contracts to critical functions:
   - `get_expression_profile()` - Validate tenant_id > 0
   - `analyze_and_create_indexes()` - Validate query_stats structure
   - `bootstrap_genome_catalog()` - Validate schema structure

2. Use lightweight approach (custom decorators or type guards)

**Files to create:**
- `src/contracts.py` - Contract decorators
- Update critical functions with contracts

## Example: Generated Types

```python
# src/generated_types.py (auto-generated)
"""Auto-generated types from database schema"""

from typing import TypedDict

class GenomeCatalogRow(TypedDict):
    id: int
    table_name: str
    field_name: str
    field_type: str
    is_required: bool
    is_indexable: bool
    default_expression: bool
    feature_group: str | None
    created_at: str  # TIMESTAMP as ISO string
    updated_at: str

class ExpressionProfileRow(TypedDict):
    id: int
    tenant_id: int | None
    table_name: str
    field_name: str
    is_enabled: bool
    created_at: str

# Usage in code:
from src.generated_types import GenomeCatalogRow

def get_genome_entry(table: str, field: str) -> GenomeCatalogRow | None:
    cursor.execute(
        "SELECT * FROM genome_catalog WHERE table_name = %s AND field_name = %s",
        (table, field)
    )
    row = cursor.fetchone()
    return row  # Type-safe: TypeScript knows exact structure
```

## Contracts Example

```python
# src/contracts.py
from typing import Callable, TypeVar, ParamSpec
from functools import wraps

P = ParamSpec('P')
T = TypeVar('T')

def requires(condition: Callable[P, bool], message: str = ""):
    """Precondition decorator"""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            if not condition(*args, **kwargs):
                raise ValueError(f"Precondition failed: {message or condition.__name__}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def ensures(condition: Callable[[T], bool], message: str = ""):
    """Postcondition decorator"""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            result = func(*args, **kwargs)
            if not condition(result):
                raise ValueError(f"Postcondition failed: {message or condition.__name__}")
            return result
        return wrapper
    return decorator

# Usage:
from src.contracts import requires, ensures

@requires(lambda tenant_id: tenant_id > 0, "tenant_id must be positive")
@ensures(lambda result: result is not None, "result must not be None")
def get_expression_profile(tenant_id: int) -> list[ExpressionProfileRow]:
    ...
```

## Conclusion

**Types from Models:** ✅ **Highly Recommended**
- Generate types from database schema
- Single source of truth
- Prevents type/schema drift

**Contracts:** ✅ **Useful Addition**
- Add contracts to critical functions
- Lightweight implementation (custom decorators)
- Better error messages and validation

**Priority:**
1. **High**: Generate types from schema
2. **Medium**: Add contracts to critical functions
3. **Low**: Consider Pydantic (only if runtime validation needed)

