# Type Generation: What, Where, and Who

**Date**: 08-12-2025  
**Purpose**: Clarify what exists, what's proposed, and where type generation happens

---

## Current State vs Proposed

### ✅ What EXISTS Now

**IndexPilot's Types:**
- ✅ **Manually defined** in `src/type_definitions.py`
- ✅ **Static types** (TypedDict, type aliases)
- ✅ **Self-contained** (no generation)
- ✅ **Used internally** by IndexPilot

**Example:**
```python
# src/type_definitions.py (EXISTS)
type JSONValue = str | int | float | bool | None | list["JSONValue"] | dict[str, "JSONValue"]
type JSONDict = dict[str, "JSONValue"]
type TenantID = int
# ... manually maintained
```

**Database Schema:**
- ✅ **Defined in SQL DDL** in `src/schema/initialization.py`
- ✅ **Separate from types** (can drift out of sync)

**Example:**
```python
# src/schema/initialization.py (EXISTS)
CREATE TABLE genome_catalog (
    id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    # ... separate definition
)
```

### ❌ What Does NOT Exist

**Type Generation Tool:**
- ❌ **No `tools/generate_types_from_schema.py`** (proposed, not implemented)
- ❌ **No `src/generated_types.py`** (proposed, not implemented)
- ❌ **No Makefile target `make generate-types`** (proposed, not implemented)

**Status:** Type generation is **PROPOSED** in `docs/tech/TYPE_SYSTEM_IMPROVEMENTS.md`, but **NOT IMPLEMENTED**.

---

## What Should Be Generated and Where

### IndexPilot's Internal Types (THIS CODEBASE)

**What:** Types for IndexPilot's own metadata tables:
- `genome_catalog` → `GenomeCatalogRow`
- `expression_profile` → `ExpressionProfileRow`
- `mutation_log` → `MutationLogRow`
- `query_stats` → `QueryStatsRow`
- `index_versions` → `IndexVersionsRow`
- etc.

**Where:** **THIS CODEBASE** (IndexPilot repository)

**Why:** 
- IndexPilot controls its own metadata tables
- Types should match IndexPilot's schema
- Generated in IndexPilot's build process

**How (Proposed):**
```python
# tools/generate_types_from_schema.py (TO BE CREATED)
def generate_indexpilot_metadata_types():
    """Generate types for IndexPilot's metadata tables"""
    tables = [
        'genome_catalog',
        'expression_profile',
        'mutation_log',
        'query_stats',
        'index_versions',
        # ... all IndexPilot metadata tables
    ]
    
    for table in tables:
        # Query information_schema
        # Generate TypedDict class
        # Write to src/generated_types.py
```

**Output:** `src/generated_types.py` (auto-generated, gitignored)

**When to run:** 
- After IndexPilot schema changes
- As part of IndexPilot's build process
- Via `make generate-types` (in IndexPilot repo)

### Host's Business Types (HOST CODEBASE)

**⚠️ IMPORTANT: IndexPilot does NOT provide type generation for host tables**

**What:** Types for host's business tables:
- `users` → `UsersRow`
- `orders` → `OrdersRow`
- `products` → `ProductsRow`
- etc.

**Where:** **HOST CODEBASE** (host's repository)

**Who provides the tool:**
- ❌ **NOT IndexPilot** (outside IndexPilot's scope)
- ✅ **Host uses existing tools** (SQLAlchemy, Pydantic, etc.)
- ✅ **Host writes their own** (if needed)

**Why IndexPilot doesn't provide this:**
- Type generation is outside IndexPilot's scope (index management)
- Better tools exist (SQLAlchemy, Pydantic, etc.)
- Host knows their schema best
- Not IndexPilot's responsibility

**Host options:**
1. Use existing tools (SQLAlchemy, Pydantic, etc.)
2. Write custom type generation script
3. Use manual types (no generation needed)

---

## Who Does What

### IndexPilot (THIS CODEBASE)

**Responsibility:**
1. ✅ **Define IndexPilot's metadata schema** (`src/schema/initialization.py`)
2. ✅ **Define IndexPilot's internal types** (`src/type_definitions.py`)
3. ⚠️ **Generate types for IndexPilot's metadata tables** (PROPOSED, not implemented)
4. ✅ **Provide type generation tool** (PROPOSED: `tools/generate_types_from_schema.py`)

**What IndexPilot provides:**
- ✅ Type generation utility (when implemented)
- ✅ Schema discovery tools (`src/schema/auto_discovery.py`)
- ✅ Type definitions for IndexPilot's own use

**What IndexPilot does NOT do:**
- ❌ Generate types for host's business tables
- ❌ Know about host's schema (except via discovery)
- ❌ Manage host's types

### Host Codebase

**Responsibility:**
1. ✅ **Define host's business schema** (host's migrations/DDL)
2. ⚠️ **Generate types for host's business tables** (OPTIONAL, host decides)
3. ✅ **Use IndexPilot as library** (import and use)

**What host does:**
- ✅ Uses IndexPilot's type generation tool (when available)
- ✅ Generates types for its own tables
- ✅ Manages its own type generation process

**What host does NOT do:**
- ❌ Generate types for IndexPilot's metadata tables (IndexPilot does this)
- ❌ Modify IndexPilot's types

---

## Architecture: What Is Where

### IndexPilot Repository (THIS CODEBASE)

```
indexpilot/
├── src/
│   ├── type_definitions.py          # ✅ EXISTS: Manual types (JSONValue, JSONDict, etc.)
│   ├── generated_types.py           # ❌ PROPOSED: Auto-generated types for metadata tables
│   ├── schema/
│   │   └── initialization.py        # ✅ EXISTS: SQL DDL for metadata tables
│   └── ...
├── tools/
│   └── generate_types_from_schema.py # ❌ PROPOSED: Type generator tool
├── Makefile                          # ✅ EXISTS: Add `generate-types` target (PROPOSED)
└── ...
```

**What happens here:**
1. IndexPilot defines its metadata schema (SQL DDL)
2. IndexPilot generates types from its own schema (PROPOSED)
3. IndexPilot provides type generation tool for hosts to use

### Host Codebase

```
host_project/
├── myapp/
│   ├── models.py                    # Host's business models
│   └── ...
├── indexpilot/                      # Copied from IndexPilot
│   ├── src/
│   │   ├── type_definitions.py      # IndexPilot's internal types
│   │   ├── generated_types.py       # IndexPilot's generated metadata types
│   │   └── ...
│   └── tools/
│       └── generate_types_from_schema.py  # IndexPilot's type generator tool
├── generated_types.py               # ❌ OPTIONAL: Host's generated business types
├── tools/
│   └── generate_host_types.py       # ❌ OPTIONAL: Host's type generator script
└── ...
```

**What happens here:**
1. Host uses IndexPilot's type generation tool (when available)
2. Host generates types for its own business tables (OPTIONAL)
3. Host uses both IndexPilot types and host types

---

## Implementation Status

### ✅ Implemented

1. **Manual type definitions** (`src/type_definitions.py`)
2. **Schema definitions** (`src/schema/initialization.py`)
3. **Schema discovery** (`src/schema/auto_discovery.py`)

### ❌ Not Implemented (Proposed)

1. **Type generation tool** (`tools/generate_types_from_schema.py`)
2. **Generated types file** (`src/generated_types.py`)
3. **Makefile target** (`make generate-types`)

### 📋 Implementation Plan

**Phase 1: IndexPilot's Own Types (THIS CODEBASE)**
1. Create `tools/generate_types_from_schema.py`
2. Generate types for IndexPilot's metadata tables
3. Output to `src/generated_types.py`
4. Add `make generate-types` target
5. Update IndexPilot code to use generated types

**Phase 2: Host Type Generation (HOST CODEBASE)**
1. Host uses IndexPilot's type generation tool
2. Host creates its own type generation script
3. Host generates types for its business tables
4. Host uses generated types in its code

---

## Summary: What, Where, Who

### What

**IndexPilot's Metadata Tables:**
- ✅ Schema defined in `src/schema/initialization.py`
- ✅ Types manually defined in `src/type_definitions.py`
- ❌ Type generation **PROPOSED** (not implemented)

**Host's Business Tables:**
- ✅ Schema defined by host (migrations/DDL)
- ⚠️ Types **OPTIONAL** (host decides)
- ❌ Type generation **OPTIONAL** (host implements if desired)

### Where

**IndexPilot Types:**
- ✅ **THIS CODEBASE** (IndexPilot repository)
- ✅ Generated in IndexPilot's build process
- ✅ Output: `src/generated_types.py` (in IndexPilot repo)

**Host Types:**
- ✅ **HOST CODEBASE** (host's repository)
- ✅ Generated in host's build process (if host chooses)
- ✅ Output: `host_project/generated_types.py` (in host repo)

### Who

**IndexPilot:**
- ✅ Defines its metadata schema
- ✅ Generates types for its metadata tables (PROPOSED)
- ✅ Provides type generation tool for hosts

**Host:**
- ✅ Defines its business schema
- ⚠️ Generates types for its business tables (OPTIONAL, using their own tools)
- ❌ Does NOT use IndexPilot's type generation tool (IndexPilot doesn't provide this)

---

## Bottom Line

**Current State:**
- ✅ Types are **manually defined** (no generation)
- ❌ Type generation is **PROPOSED** but **NOT IMPLEMENTED**
- ❌ Type generation is **NOT a feature** of IndexPilot

**When Implemented (if at all):**
- **IndexPilot's types** → Generated in **THIS CODEBASE** (internal tool only)
- **Host's types** → Generated in **HOST CODEBASE** (using host's own tools)

**Who Does What:**
- **IndexPilot** → Generates types for its own metadata tables (internal tool, not a feature)
- **Host** → Generates types for its own business tables (using existing tools like SQLAlchemy, Pydantic, or custom scripts)

**Key Point:**
- IndexPilot's type generation (if implemented) is **internal only** (this codebase)
- Host's type generation is **host's responsibility** (host codebase, using their own tools)
- **IndexPilot does NOT provide a global type generation tool** (outside scope)

