# IndexPilot as a Library: Type Isolation and Conflicts

**Date**: 08-12-2025  
**Purpose**: Clarify how IndexPilot works as an imported library, type isolation, and potential conflicts

---

## How IndexPilot Works as a Library

### Import Model

**IndexPilot is imported like any Python library:**
```python
# In host codebase
import indexpilot
# or
from indexpilot.auto_indexer import analyze_and_create_indexes
from indexpilot.schema import discover_and_bootstrap_schema
```

**It operates on the host's database:**
```python
# IndexPilot connects to host's database (via environment variables)
from indexpilot.db import get_connection

# Uses host's database connection
with get_connection() as conn:
    # Operates on host's database
    cursor.execute("SELECT * FROM host_table")
```

---

## Type Isolation: IndexPilot Types Are Self-Contained

### IndexPilot's Types Are Namespaced

**All IndexPilot types are in `indexpilot.type_definitions`:**
```python
# IndexPilot's internal types (self-contained)
from indexpilot.type_definitions import (
    JSONValue,
    JSONDict,
    TenantID,
    TableName,
    FieldName,
    VerificationResult,
    VerificationDetails,
    # ... all IndexPilot types
)
```

**These are internal to IndexPilot:**
- ✅ Namespaced under `indexpilot.type_definitions`
- ✅ Do NOT pollute global namespace
- ✅ Do NOT conflict with host types
- ✅ Optional for host codebase (host doesn't need to import them)

### Host Codebase Types Are Separate

**Host codebase has its own types:**
```python
# Host codebase types (separate)
from myapp.models import User, Order, Product
from myapp.types import UserID, OrderID

# IndexPilot types (separate namespace)
from indexpilot.type_definitions import TenantID, TableName
```

**No conflicts because:**
- Different namespaces (`myapp.types` vs `indexpilot.type_definitions`)
- Different type names (host uses `UserID`, IndexPilot uses `TenantID`)
- Python's module system prevents conflicts

---

## Type Conflicts: Will There Be Any?

### ✅ No Type Conflicts

**Why there are no conflicts:**

1. **Namespaced imports:**
   ```python
   # Host codebase
   from indexpilot.type_definitions import JSONValue  # indexpilot.JSONValue
   from myapp.types import JSONValue  # myapp.JSONValue
   # Different namespaces = no conflict
   ```

2. **Internal use only:**
   - IndexPilot types are used **inside IndexPilot code**
   - Host codebase doesn't need to import them
   - Host can use IndexPilot functions without knowing about types

3. **Type aliases are module-scoped:**
   ```python
   # indexpilot/type_definitions.py
   type JSONValue = str | int | float | ...  # Only visible when imported
   
   # Host codebase
   # Doesn't import it = no conflict
   ```

### Example: No Conflicts

```python
# Host codebase (myapp/main.py)
from indexpilot.auto_indexer import analyze_and_create_indexes
from myapp.models import User  # Host's own types

# IndexPilot uses its internal types (JSONValue, JSONDict, etc.)
# Host uses its own types (User, Order, etc.)
# No conflicts - different namespaces

def my_function():
    # Host code - uses host types
    user: User = get_user(1)
    
    # IndexPilot code - uses IndexPilot types internally
    analyze_and_create_indexes()  # IndexPilot uses JSONValue internally, but host doesn't see it
```

---

## Stubs: Are They Needed?

### What Are Stubs?

**Type stubs (`.pyi` files) provide type information for libraries without type hints.**

### IndexPilot's Stubs Directory

**IndexPilot has stubs for third-party libraries:**
```
stubs/
├── psycopg2/          # Stubs for PostgreSQL adapter
├── fastapi.pyi        # Stubs for FastAPI
├── scipy/             # Stubs for scipy
└── sklearn/           # Stubs for sklearn
```

**These are for IndexPilot's dependencies, not IndexPilot itself.**

### Do Host Codebases Need Stubs?

**For IndexPilot: ❌ NO**

**IndexPilot is fully typed:**
- ✅ All IndexPilot code has type hints
- ✅ No stubs needed for IndexPilot itself
- ✅ Host can use IndexPilot without stubs

**For IndexPilot's dependencies: ⚠️ MAYBE**

**If host codebase uses same dependencies:**
- If host uses `psycopg2` → May want stubs (but IndexPilot's stubs are internal)
- If host uses `fastapi` → May want stubs (but IndexPilot's stubs are internal)
- **IndexPilot's stubs are in `stubs/` directory - not installed as package**

### How Stubs Work

**IndexPilot's stubs are internal:**
```
indexpilot/
├── src/              # IndexPilot code (fully typed)
├── stubs/            # Stubs for IndexPilot's dependencies (internal)
│   ├── psycopg2/
│   └── fastapi.pyi
```

**When host imports IndexPilot:**
- Host gets IndexPilot's code (fully typed)
- Host does NOT get IndexPilot's stubs (they're internal)
- Host can install its own stubs if needed: `pip install types-psycopg2`

### Recommendation

**For host codebase:**
1. ✅ **No stubs needed for IndexPilot** - it's fully typed
2. ⚠️ **Install official stubs for shared dependencies:**
   ```bash
   pip install types-psycopg2  # If host uses psycopg2
   pip install types-requests   # If host uses requests
   ```
3. ✅ **IndexPilot's internal stubs don't interfere** - they're in IndexPilot's namespace

---

## Type Generation: What About Host Types?

### IndexPilot Types: Self-Contained ✅

**IndexPilot's types are:**
- ✅ Defined in `indexpilot.type_definitions`
- ✅ Used internally by IndexPilot
- ✅ Not generated - manually maintained
- ✅ Self-contained - no host involvement needed

### Host Types: Separate ✅

**Host codebase types are:**
- ✅ Defined in host's own modules (`myapp.models`, `myapp.types`)
- ✅ Used by host code
- ✅ Can be generated from host's database schema (optional)
- ✅ Separate from IndexPilot types

### No Type Generation Needed for IndexPilot

**IndexPilot types are:**
- ✅ Static (defined in code)
- ✅ Not generated from database
- ✅ Self-contained
- ✅ No generation step needed

**Host types (if generated):**
- ✅ Generated from host's database schema
- ✅ Separate process
- ✅ Optional (host can define manually)
- ✅ Not IndexPilot's concern

---

## Complete Example: Host Codebase Integration

### Host Codebase Structure

```
myapp/
├── myapp/
│   ├── models.py          # Host's types (User, Order, etc.)
│   ├── types.py           # Host's type aliases (UserID, etc.)
│   └── main.py            # Host's application
├── indexpilot/            # Copied IndexPilot library
│   ├── src/
│   │   ├── type_definitions.py  # IndexPilot's types (self-contained)
│   │   ├── auto_indexer.py
│   │   └── ...
│   └── stubs/             # IndexPilot's stubs (internal, not used by host)
└── requirements.txt
```

### Usage: No Conflicts

```python
# myapp/main.py
from myapp.models import User, Order  # Host's types
from myapp.types import UserID         # Host's type aliases

from indexpilot.auto_indexer import analyze_and_create_indexes
from indexpilot.schema import discover_and_bootstrap_schema

# Host code uses host types
def get_user(user_id: UserID) -> User | None:
    # Host's own code
    ...

# IndexPilot code uses IndexPilot types internally
# Host doesn't need to know about IndexPilot's types
analyze_and_create_indexes()  # IndexPilot uses JSONValue, JSONDict internally
```

### Type Checking

**Host codebase type checking:**
```bash
# In host codebase
mypy myapp/  # Checks host code
# IndexPilot types are in indexpilot.type_definitions - no conflicts
```

**IndexPilot type checking:**
```bash
# In IndexPilot repository
mypy src/  # Checks IndexPilot code
# Uses stubs/ for third-party libraries
```

**No conflicts because:**
- Different namespaces
- Different type names
- Python's module system isolates them

---

## Summary

### ✅ IndexPilot as a Library

1. **Imported like numpy:**
   ```python
   import indexpilot
   from indexpilot.auto_indexer import analyze_and_create_indexes
   ```

2. **Operates on host's database:**
   - Connects via environment variables
   - Creates metadata tables in host's database
   - Manages indexes on host's tables

3. **Types are self-contained:**
   - All in `indexpilot.type_definitions`
   - Namespaced (no global pollution)
   - Internal to IndexPilot (host doesn't need to import)

4. **No type conflicts:**
   - Different namespaces (`indexpilot.*` vs `myapp.*`)
   - Different type names
   - Python's module system prevents conflicts

### ✅ Stubs

1. **IndexPilot doesn't need stubs:**
   - Fully typed
   - No stubs needed for IndexPilot itself

2. **IndexPilot's stubs are internal:**
   - In `stubs/` directory
   - For IndexPilot's dependencies (psycopg2, fastapi, etc.)
   - Not installed as package
   - Host doesn't need them

3. **Host can install its own stubs:**
   ```bash
   pip install types-psycopg2  # If host uses psycopg2
   ```

### ✅ Type Generation

1. **IndexPilot types:**
   - Static (defined in code)
   - Self-contained
   - No generation needed

2. **Host types:**
   - Separate from IndexPilot
   - Can be generated from host's schema (optional)
   - Not IndexPilot's concern

---

## Bottom Line

**IndexPilot is a library like numpy:**
- ✅ Import it: `import indexpilot`
- ✅ Use it: `indexpilot.auto_indexer.analyze_and_create_indexes()`
- ✅ Types are self-contained (no conflicts)
- ✅ No stubs needed (fully typed)
- ✅ Operates on host's database
- ✅ Doesn't interfere with host types

**Just like numpy doesn't conflict with your types, IndexPilot doesn't conflict with host types.**

