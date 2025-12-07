# IndexPilot - Implementation Routing

**Last Updated**: 07-12-2025 (Updated with feature discovery workflow after algorithm completion)

---

## Workflow

1. Read Research → 2. Read Features/Tech → 3. Understand Codebase → 4. Identify Feature → **4.5. Discover Features from Research/Features** → **4.6. Check Duplicates/Conflicts** → 5. Write Code → 6. Wire Up → 7. Integrate → 8. Fix Errors → 9. Update Docs → 10. Next Feature

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

## Step 4.5: Discover Features from Research & Features Folders ⭐ **NEW**

**When to Use**: After all algorithms are integrated (✅ 10/11 algorithms complete), discover additional features from research and features documentation.

### 4.5.1 Scan Research Folder for Remaining Work

**Read**: `docs/research/`
- `RESEARCH_SUMMARY_AND_STATUS.md` - **CRITICAL** - Lists all remaining valuable work
  - Section 4: "What's Left (Remaining Valuable Work)"
  - Section 5: "Priority Matrix: Remaining Work"
  - Section 6: "Value Assessment: What Will Add Most Value"
- `COMPETITOR_UPGRADE_PLAN.md` - Competitive enhancements needed
  - Section 1: Deep EXPLAIN Integration (CRITICAL)
  - Section 2: Index Lifecycle Management (CRITICAL)
  - Section 3: Constraint Programming (CRITICAL)
  - Section 4-6: High priority enhancements
- `NON_ALGORITHM_IMPROVEMENTS.md` - Non-algorithm improvements
  - Feature integration items
  - Operational enhancements
  - Configuration improvements

**Key Remaining Features from Research**:
1. ⚠️ **Deep EXPLAIN Integration** (CRITICAL) - `COMPETITOR_UPGRADE_PLAN.md` Section 1
2. ⚠️ **Index Lifecycle Management Integration** (CRITICAL) - `COMPETITOR_UPGRADE_PLAN.md` Section 2
3. ⚠️ **Constraint Programming** (CRITICAL) - `ALGORITHM_TO_FEATURE_MAPPING.md` Phase 5
4. ⚠️ **Workload-Aware Indexing Integration** (HIGH) - `COMPETITOR_UPGRADE_PLAN.md` Section 4
5. ⚠️ **Production Battle-Testing** (HIGH) - `COMPETITOR_UPGRADE_PLAN.md` Section 5
6. ⚠️ **Enhanced Query Plan Analysis** (HIGH) - `COMPETITOR_UPGRADE_PLAN.md` Section 6

### 4.5.2 Scan Features Folder for Implementation Plans

**Read**: `docs/features/`
- `FEATURE_IMPLEMENTATION_PLAN.md` - **CRITICAL** - Phase-wise implementation plan
  - Phase 1: Critical Features (Constraint Programming, REINDEX Scheduling)
  - Phase 2: Algorithm Integrations (iDistance, Bx-tree verification)
  - Phase 3: Advanced Features (Cross-Tenant Learning, Predictive Maintenance)
  - Phase 4: Specialized Features (Materialized View Support, Query Plan Evolution)
- `ENHANCEMENT_ROADMAP.md` - Focused enhancement roadmap
  - Phase 1: Core Enhancements (EXPLAIN, Micro-Indexes, Adaptive Strategy, Measurement)
- `FUTURE_EXPERIMENTAL_FEATURES.md` - Experimental features (deferred)
- `FEATURE_STATUS_CHECK.md` - Status of advanced features

**Key Remaining Features from Features Folder**:
1. ⚠️ **Constraint Programming** - `FEATURE_IMPLEMENTATION_PLAN.md` Section 1.1
2. ⚠️ **Automatic REINDEX Scheduling** - `FEATURE_IMPLEMENTATION_PLAN.md` Section 1.2
3. ⚠️ **Cross-Tenant Pattern Learning** - `FEATURE_IMPLEMENTATION_PLAN.md` Section 3.1
4. ⚠️ **Predictive Index Maintenance** - `FEATURE_IMPLEMENTATION_PLAN.md` Section 3.2
5. ⚠️ **Materialized View Support** - `FEATURE_IMPLEMENTATION_PLAN.md` Section 3.3
6. ⚠️ **Query Plan Evolution Tracking** - `FEATURE_IMPLEMENTATION_PLAN.md` Section 4.1

### 4.5.3 Priority-Based Feature Selection

**Priority Order** (from `RESEARCH_SUMMARY_AND_STATUS.md` Section 5):

**CRITICAL (Do First)**:
1. Deep EXPLAIN Integration (2-3 weeks)
2. Index Lifecycle Management Integration (2-3 weeks)
3. Constraint Programming (3-4 weeks)
4. Runtime Testing and Validation (2-3 weeks)

**HIGH (Do Soon)**:
5. Workload-Aware Indexing Integration (1-2 weeks)
6. Production Battle-Testing (2-3 weeks)
7. Enhanced Query Plan Analysis (1-2 weeks)

**MEDIUM (Nice to Have)**:
8. Performance Dashboards (2-3 weeks) - UI work, may defer
9. Index Health Monitoring Dashboard (1-2 weeks) - UI work, may defer
10. Decision Explanation UI (1-2 weeks) - UI work, may defer

**LOW (Polish)**:
11. Bx-tree Integration Verification (2-3 days)
12. Additional Test Coverage (1-2 weeks)

### 4.5.4 Feature Discovery Checklist

**Before implementing, verify**:
- [ ] Feature is listed in `RESEARCH_SUMMARY_AND_STATUS.md` Section 4
- [ ] Feature has clear implementation plan in `FEATURE_IMPLEMENTATION_PLAN.md` or `COMPETITOR_UPGRADE_PLAN.md`
- [ ] Feature is not already implemented (check `FEATURES.md` status)
- [ ] Feature has clear integration point identified
- [ ] Feature has effort estimate and value assessment
- [ ] Feature priority aligns with current sprint goals

**Decision Matrix**:
| Situation | Action |
|-----------|--------|
| Feature in CRITICAL priority | ✅ Implement immediately |
| Feature in HIGH priority | ✅ Implement after CRITICAL |
| Feature in MEDIUM priority | ⚠️ Evaluate business value first |
| Feature in LOW priority | ⚠️ Defer until higher priority complete |
| Feature not in any doc | ⚠️ Review with team before implementing |

---

## Step 4.6: ⚠️ Check for Duplicates & Conflicts (CRITICAL)

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

**⭐ NEW: Feature Discovery Process** (After algorithms are complete):

### 10.1 Scan Research Folder for Remaining Work

**Primary Source**: `docs/research/RESEARCH_SUMMARY_AND_STATUS.md`
- Section 4: "What's Left (Remaining Valuable Work)"
- Section 5: "Priority Matrix: Remaining Work"
- Section 6: "Value Assessment: What Will Add Most Value"

**Secondary Sources**:
- `docs/research/COMPETITOR_UPGRADE_PLAN.md` - Competitive enhancements
- `docs/research/NON_ALGORITHM_IMPROVEMENTS.md` - Non-algorithm improvements

### 10.2 Scan Features Folder for Implementation Plans

**Primary Source**: `docs/features/FEATURE_IMPLEMENTATION_PLAN.md`
- Phase 1: Critical Features
- Phase 2: Algorithm Integrations
- Phase 3: Advanced Features
- Phase 4: Specialized Features

**Secondary Sources**:
- `docs/features/ENHANCEMENT_ROADMAP.md` - Focused enhancements
- `docs/features/FEATURE_STATUS_CHECK.md` - Feature status

### 10.3 Feature Selection Workflow

1. **Check Priority**: Use `RESEARCH_SUMMARY_AND_STATUS.md` Section 5 priority matrix
2. **Check Status**: Verify feature not already implemented in `FEATURES.md`
3. **Check Plan**: Review implementation plan in `FEATURE_IMPLEMENTATION_PLAN.md` or `COMPETITOR_UPGRADE_PLAN.md`
4. **Check Integration**: Identify integration point and affected modules
5. **Check Dependencies**: Verify dependencies are met
6. **Select Feature**: Choose highest priority feature with clear plan

### 10.4 Quick Reference: Top Remaining Features

**CRITICAL Priority** (from `RESEARCH_SUMMARY_AND_STATUS.md`):
1. Deep EXPLAIN Integration - `COMPETITOR_UPGRADE_PLAN.md` Section 1
2. Index Lifecycle Management Integration - `COMPETITOR_UPGRADE_PLAN.md` Section 2
3. Constraint Programming - `FEATURE_IMPLEMENTATION_PLAN.md` Section 1.1
4. Runtime Testing and Validation - `RESEARCH_SUMMARY_AND_STATUS.md` Section 4.5.1

**HIGH Priority**:
5. Workload-Aware Indexing Integration - `COMPETITOR_UPGRADE_PLAN.md` Section 4
6. Production Battle-Testing - `COMPETITOR_UPGRADE_PLAN.md` Section 5
7. Automatic REINDEX Scheduling - `FEATURE_IMPLEMENTATION_PLAN.md` Section 1.2

---

## Quick Reference

**Key Files**: `agents.yaml`, `docs/tech/ARCHITECTURE.md`, `docs/features/FEATURES.md`

**Key Modules**: `auto_indexer.py`, `stats.py`, `genome.py`, `expression.py`, `schema.py`

**Algorithm Modules**: `src/algorithms/` (CERT, QPG, Cortex, etc.) - ✅ 10/11 algorithms complete

**Feature Discovery**:
- `docs/research/RESEARCH_SUMMARY_AND_STATUS.md` - **CRITICAL** - Remaining work summary
- `docs/research/COMPETITOR_UPGRADE_PLAN.md` - Competitive enhancements
- `docs/features/FEATURE_IMPLEMENTATION_PLAN.md` - **CRITICAL** - Implementation plans
- `docs/research/NON_ALGORITHM_IMPROVEMENTS.md` - Non-algorithm improvements

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
- **⭐ Always check for duplicates/conflicts before implementing (Step 4.6)**
- **⭐ After algorithms are complete, discover features from research/features folders (Step 4.5)**

---
