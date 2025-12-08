# Type Generation Refactor Scope Assessment

**Date**: 08-12-2025  
**Question**: How much of a refactor is generating types for IndexPilot's metadata tables?

---

## Executive Summary

**Refactor Scope: ⚠️ MEDIUM** (2-3 days of work)

**Breakdown:**
- **Low Risk**: TypedDict is compatible with existing dict access patterns
- **Medium Effort**: 35 files to review, mostly type annotation updates
- **High Value**: Better type safety, catches schema mismatches at type-check time

---

## Current State Analysis

### How Metadata Tables Are Accessed

**Pattern 1: Direct dict access (most common)**
```python
# src/genome.py
cursor.execute("SELECT * FROM genome_catalog WHERE table_name = %s", (table_name,))
rows = cursor.fetchall()  # Returns list[dict[str, object]]
for row in rows:
    table_name = row["table_name"]  # dict access
    field_name = row["field_name"]
```

**Pattern 2: RealDictCursor usage**
```python
# src/expression.py
cursor = conn.cursor(cursor_factory=RealDictCursor)
cursor.execute("SELECT * FROM expression_profile WHERE tenant_id = %s", (tenant_id,))
fields = cursor.fetchall()  # Returns list[RealDictRow] (dict-like)
for field in fields:
    table_name = field["table_name"]  # dict access
```

**Pattern 3: Function return types**
```python
# src/genome.py
def get_genome_fields(table_name=None):
    # Returns list[dict[str, object]] (no specific type)
    return cursor.fetchall()
```

### Current Type Usage

**Files accessing metadata tables:**
- 35 files total
- 264 matches (some files access multiple tables)
- Most use: `dict[str, object]`, `JSONDict`, or no type annotation

**Key files:**
- `src/genome.py` - genome_catalog access
- `src/expression.py` - expression_profile access
- `src/stats.py` - query_stats access
- `src/auto_indexer.py` - mutation_log access
- `src/schema_evolution.py` - all metadata tables
- `src/api_server.py` - all metadata tables for API
- ... 29 more files

---

## What Needs to Change

### 1. Create Type Generator Tool (NEW)

**File:** `tools/generate_types_from_schema.py` (NEW)

**Effort:** 4-6 hours
- Query `information_schema` for table structures
- Map PostgreSQL types to Python types
- Generate TypedDict classes
- Handle TIMESTAMP → str (ISO format) conversion
- Write to `src/generated_types.py`

**Complexity:** Medium
- Need to handle nullable fields
- Need to map PostgreSQL types correctly
- Need to handle TIMESTAMP conversion

### 2. Generate Types File (NEW)

**File:** `src/generated_types.py` (NEW, auto-generated)

**Content:**
```python
"""Auto-generated types from IndexPilot metadata tables"""

from typing import TypedDict
from datetime import datetime

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

class MutationLogRow(TypedDict):
    id: int
    tenant_id: int | None
    mutation_type: str
    table_name: str | None
    field_name: str | None
    details_json: dict[str, object] | None  # JSONB
    created_at: str

class QueryStatsRow(TypedDict):
    id: int
    tenant_id: int | None
    table_name: str
    field_name: str | None
    query_type: str
    duration_ms: float  # NUMERIC
    created_at: str

class IndexVersionsRow(TypedDict):
    id: int
    index_name: str
    table_name: str
    index_definition: str
    created_by: str
    metadata_json: dict[str, object] | None  # JSONB
    created_at: str
```

**Effort:** Auto-generated (0 hours after tool is created)

### 3. Update Function Return Types (MEDIUM EFFORT)

**Files to update:** ~15-20 functions

**Example changes:**
```python
# BEFORE
def get_genome_fields(table_name=None):
    # No return type annotation
    return cursor.fetchall()

# AFTER
from src.generated_types import GenomeCatalogRow

def get_genome_fields(table_name=None) -> list[GenomeCatalogRow]:
    return cursor.fetchall()
```

**Effort:** 2-3 hours
- Update function signatures
- Add imports
- Handle list vs single row returns

### 4. Update Code That Accesses Rows (LOW EFFORT)

**Files to review:** 35 files

**Good news:** Most code already uses dict access, which works with TypedDict!

**Example:**
```python
# This code works with both dict and TypedDict
for row in rows:
    table_name = row["table_name"]  # ✅ Works with TypedDict
    field_name = row["field_name"]  # ✅ Works with TypedDict
```

**Changes needed:**
- Add type annotations where missing
- Handle TIMESTAMP conversion (already partially done in some files)
- Add type narrowing where needed

**Effort:** 4-6 hours
- Most files need no changes (dict access works)
- Some files need type annotations
- Some files need TIMESTAMP handling

### 5. Handle TIMESTAMP Conversion (PARTIALLY DONE)

**Current state:**
- Some files already handle datetime conversion (`src/index_cleanup.py`, `src/api_server.py`)
- Most files don't handle it

**What needs to change:**
- Convert TIMESTAMP columns to ISO strings when reading
- Or use `datetime` type and handle conversion at usage sites

**Effort:** 2-3 hours
- Add conversion helper function
- Update code that reads TIMESTAMP columns

### 6. Add Makefile Target (LOW EFFORT)

**File:** `Makefile`

**Add:**
```makefile
generate-types:
	python tools/generate_types_from_schema.py
```

**Effort:** 5 minutes

---

## Refactor Breakdown

### Phase 1: Create Type Generator (4-6 hours)

**Tasks:**
1. Create `tools/generate_types_from_schema.py`
2. Implement schema querying
3. Implement type mapping
4. Implement TypedDict generation
5. Test with all metadata tables

**Risk:** Low (isolated new code)

### Phase 2: Update Core Functions (2-3 hours)

**Tasks:**
1. Update `src/genome.py` functions
2. Update `src/expression.py` functions
3. Update `src/stats.py` functions
4. Update `src/auto_indexer.py` functions
5. Update other core functions

**Risk:** Low (type annotations only, no logic changes)

### Phase 3: Update All Access Points (4-6 hours)

**Tasks:**
1. Review all 35 files
2. Add type annotations where needed
3. Handle TIMESTAMP conversion
4. Add type narrowing where needed
5. Run type checker and fix errors

**Risk:** Low (mostly type annotations)

### Phase 4: Testing & Validation (2-3 hours)

**Tasks:**
1. Run full test suite
2. Run type checker (mypy, pyright)
3. Verify no runtime changes
4. Update documentation

**Risk:** Low (no runtime changes expected)

---

## Total Effort Estimate

**Total Time:** 12-18 hours (1.5-2.5 days)

**Breakdown:**
- Type generator tool: 4-6 hours
- Core function updates: 2-3 hours
- All access points: 4-6 hours
- Testing & validation: 2-3 hours

**Risk Level:** ⚠️ **LOW**
- TypedDict is compatible with dict access
- No runtime logic changes needed
- Mostly type annotation updates

---

## Benefits vs Effort

### Benefits

1. ✅ **Type Safety**: Catch schema mismatches at type-check time
2. ✅ **IDE Support**: Better autocomplete and type hints
3. ✅ **Documentation**: Types serve as documentation
4. ✅ **Refactoring Safety**: Type checker catches breaking changes
5. ✅ **Single Source of Truth**: Types generated from actual schema

### Effort

1. ⚠️ **12-18 hours** of development time
2. ⚠️ **35 files** to review
3. ⚠️ **New tool** to maintain
4. ⚠️ **Build step** added (generate types before type checking)

### Value Assessment

**High Value, Medium Effort**

- ✅ Worth doing for long-term maintainability
- ✅ Low risk (no runtime changes)
- ⚠️ Not urgent (current manual types work)
- ⚠️ Requires ongoing maintenance (regenerate on schema changes)

---

## Implementation Strategy

### Option 1: Incremental (Recommended)

**Phase 1:** Generate types, don't use them yet
- Create generator tool
- Generate types file
- Add to gitignore
- No code changes

**Phase 2:** Update core functions
- Update `genome.py`, `expression.py`, `stats.py`
- Test thoroughly
- Verify no regressions

**Phase 3:** Update remaining files
- Update all 35 files incrementally
- Run tests after each batch
- Fix type errors as they appear

**Phase 4:** Full adoption
- All code uses generated types
- Type checker passes
- Documentation updated

### Option 2: All at Once

**Do everything in one go:**
- Create generator
- Generate types
- Update all files
- Test everything
- Deploy

**Risk:** Higher (more changes at once)

---

## Recommendations

### ✅ Should Do

1. **Create type generator tool** - High value, reusable
2. **Generate types for metadata tables** - Better type safety
3. **Update core functions first** - Highest impact, lowest risk
4. **Incremental rollout** - Lower risk, easier to test

### ⚠️ Consider

1. **TIMESTAMP handling** - Decide on str vs datetime early
2. **Build integration** - Add to CI/CD pipeline
3. **Documentation** - Update docs to mention generated types

### ❌ Don't Do

1. **Don't change runtime logic** - Types only, no behavior changes
2. **Don't break existing code** - Maintain backward compatibility
3. **Don't over-engineer** - Keep it simple

---

## Conclusion

**Refactor Scope: ⚠️ MEDIUM (12-18 hours)**

**Key Points:**
- ✅ Low risk (no runtime changes)
- ✅ High value (better type safety)
- ⚠️ Medium effort (35 files to review)
- ✅ Worth doing for long-term maintainability

**Recommendation:** 
- ✅ **Do it incrementally** over 2-3 days
- ✅ **Start with core functions** (highest impact)
- ✅ **Test thoroughly** after each phase
- ✅ **Add to build process** (regenerate on schema changes)

**Not urgent, but valuable for code quality.**

