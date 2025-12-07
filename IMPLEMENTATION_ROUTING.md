# IndexPilot - Implementation Routing

**Last Updated**: 07-12-2025

---

## Workflow

1. Read Research → 2. Read Features/Tech → 3. Understand Codebase → 4. Identify Feature → **4.5. Check Duplicates/Conflicts** → 5. Write Code → 6. Wire Up → 7. Integrate → 8. Fix Errors → 9. Update Docs → 10. Next Feature

---

## Step 1: Read Research Docs

**Read**: `docs/research/`
- `IMPLEMENTATION_GUIDE.md`
- `IMPLEMENTATION_QUICK_START.md`
- `ALGORITHM_TO_FEATURE_MAPPING.md`
- `USER_PAIN_POINTS_AND_WISHLIST.md`

**Note**: Priorities, requirements, integration points, dependencies

---

## Step 2: Read Features/Tech Docs

**Read**: 
- `docs/features/FEATURES.md`, `ENHANCEMENT_ROADMAP.md`
- `docs/tech/ARCHITECTURE.md` (CRITICAL)
- `agents.yaml` (project structure)

**Note**: Current features, architecture, constraints

---

## Step 3: Understand Codebase

**Read**:
- `README.md`, `src/schema.py`, `src/genome.py`, `src/expression.py`
- `src/auto_indexer.py`, `src/stats.py`

**Understand**: DNA architecture, multi-tenant design, cost-benefit analysis, integration patterns

---

## Step 4: Identify Feature

**Check**:
- `docs/features/FEATURES.md` (exists? status?)
- `docs/features/ENHANCEMENT_ROADMAP.md` (priorities)
- Related code (similar functionality?)

**Scope**: What to implement, affected modules, dependencies

---

## Step 4.5: ⚠️ Check for Duplicates & Conflicts (CRITICAL)

**Before writing code, check for existing implementations:**

### Check Existing Algorithms
```bash
grep -r "INTEGRATION NOTE" src/
grep -r "arXiv:" src/
ls src/algorithms/
```

**Check**:
- `src/algorithms/` - Does algorithm exist?
- `docs/research/ALGORITHM_OVERLAP_ANALYSIS.md` - Overlaps/conflicts?
- `docs/audit/DUPLICATIONS_CONFLICTS_OVERLAPS_AUDIT.md` - Known conflicts?
- Integration notes in code (search "INTEGRATION NOTE")

### Check Similar Functionality
```bash
grep -r "def.*[algorithm_name]" src/ --include="*.py"
grep -r "[algorithm_name]" src/ --include="*.py" -i
```

### Decision Matrix
| Situation | Action |
|-----------|--------|
| Algorithm exists in `src/algorithms/` | ✅ Enhance existing, don't duplicate |
| Integration note exists | ✅ Follow integration plan |
| Similar functionality exists | ⚠️ Review overlap, enhance vs replace |
| Conflict documented | ⚠️ Review conflict resolution |
| No existing implementation | ✅ Proceed with new implementation |

**If duplicate/conflict found**: Document decision, explain enhancement vs replacement, update integration notes

---

## Step 5: Write Code

**Setup**: `pip install -r requirements.txt`, `make init-db`

**Write**:
- Follow existing patterns
- Use type hints (`docs/tech/TYPE_SAFETY_IMPROVEMENTS.md`)
- Add docstrings
- Use utilities: `db.py`, `validation.py`, `rollback.py`, `audit.py`, `config_loader.py`

**Rules**: No mocks/stubs, full implementation, thread-safe, SQL injection safe

### Algorithm Implementation Structure

**✅ DO**: Implement in `src/algorithms/` for cleaner structure:
- `src/algorithms/cert.py` - CERT algorithm
- `src/algorithms/qpg.py` - QPG algorithm  
- `src/algorithms/cortex.py` - Cortex algorithm
- etc.

**Pattern**:
```python
# src/algorithms/cert.py
"""CERT (Cardinality Estimation Restriction Testing) Algorithm Implementation
Based on "CERT: Continuous Evaluation of Cardinality Estimation" arXiv:2306.00355
"""

def validate_cardinality_with_cert(...):
    pass

# src/algorithms/__init__.py
from src.algorithms.cert import validate_cardinality_with_cert
__all__ = ["validate_cardinality_with_cert"]

# Integration point (e.g., src/auto_indexer.py)
from src.algorithms.cert import validate_cardinality_with_cert
result = validate_cardinality_with_cert(...)
```

**❌ DON'T**: Implement algorithms directly in `auto_indexer.py` or other core files

---

## Step 6: Wire Up

**Update**:
- Functions calling new code
- `indexpilot_config.yaml.example` (if needed)
- Integration points (stats, auto-indexer, monitoring, audit)
- `agents.yaml` (if new modules)
- `src/algorithms/__init__.py` (if new algorithm module)

---

## Step 7: Integrate

**Test**:
- With existing features
- With simulator (`src/simulator.py`)
- Error cases

**Verify**: Data flow, audit logging, config loading, bypass system, thread safety

---

## Step 8: Fix Errors

**Run**:
```bash
make lint      # Auto-fix linting
make format    # Auto-format
make typecheck # Type errors
make run-tests # Tests
```

**Fix**: All errors, verify fixes

---

## Step 9: Update Docs

**Update**:
- `docs/features/FEATURES.md` (if new feature)
- `docs/tech/ARCHITECTURE.md` (if architecture changed)
- `docs/research/` (if algorithm implemented)
- `README.md` (if needed)
- `docs/AITracking/AIAction_DD-MM-YYYY_task_name.md` (append implementation log)

**Rules**: Append don't overwrite, check existing first, get approval for canonical docs

---

## Step 10: Next Feature

**Check**:
- `docs/features/ENHANCEMENT_ROADMAP.md`
- `docs/features/FEATURES.md` (incomplete features)
- Dependencies, priorities, user needs

---

## Quick Reference

**Key Files**: `agents.yaml`, `docs/tech/ARCHITECTURE.md`, `docs/features/FEATURES.md`

**Key Modules**: `auto_indexer.py`, `stats.py`, `genome.py`, `expression.py`, `schema.py`

**Algorithm Modules**: `src/algorithms/` (CERT, QPG, Cortex, etc.)

**Commands**: `make init-db`, `make run-tests`, `make lint`, `make typecheck`

**Config**: `indexpilot_config.yaml.example`, `schema_config.yaml.example`

---

## Principles

- No mocks/stubs, full implementation only
- Follow existing patterns
- Production-ready (error handling, logging)
- Append to docs, don't overwrite
- Fix all errors before completion
- **⭐ Implement algorithms in `src/algorithms/` for cleaner structure**
- **⭐ Always check for duplicates/conflicts before implementing (Step 4.5)**

---
