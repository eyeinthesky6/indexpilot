# IndexPilot - Feature Implementation Plan

**Date**: 07-12-2025  
**Purpose**: Phase-wise implementation plan for remaining features  
**Status**: ✅ Complete Plan

---

## Executive Summary

**Current Status**: ✅ **Integration Complete** (100% as of today)

**Remaining Work**: 
- **2 Critical Features** (Constraint Programming, Automatic REINDEX Scheduling)
- **2 Algorithm Integrations** (iDistance, Bx-tree - code exists, needs verification)
- **3 Advanced Features** (Cross-Tenant Learning, Predictive Maintenance, Query Plan Evolution)
- **1 Specialized Feature** (Materialized View Support)

**No UI Work**: All UI features deferred (dashboards, monitoring UI, etc.)

---

## Phase 1: Critical Features (Weeks 1-4) - HIGH PRIORITY

### 1.1 Constraint Programming for Index Selection ⚠️ **CRITICAL**

**Status**: Not implemented  
**Competitor Gap**: pganalyze uses constraint programming  
**Priority**: **HIGH**

**What's Needed**:
- Multi-objective optimization (storage, performance, workload constraints)
- Constraint solver integration (OR-Tools or custom)
- Systematic trade-off handling
- Optimal solutions for complex scenarios
- Integration into `should_create_index()`

**Academic Research**:
- Constraint programming for database optimization
- Multi-objective optimization algorithms
- Integer programming for index selection

**Implementation**:
```python
# src/algorithms/constraint_optimizer.py
def optimize_index_selection_with_constraints(
    candidate_indexes: list[dict],
    storage_budget: float,
    performance_targets: dict,
    workload_constraints: dict,
) -> list[dict]:
    """
    Use constraint programming to find optimal index set.
    
    Constraints:
    - Total storage < storage_budget
    - Query performance > performance_targets
    - Write performance < workload_constraints.max_write_overhead
    - Index count < workload_constraints.max_indexes_per_table
    """
    # Use OR-Tools or custom constraint solver
    # Multi-objective: maximize query performance, minimize storage
    pass
```

**Integration Point**: `src/auto_indexer.py` - `should_create_index()`

**Effort**: High (3-4 weeks)  
**Value**: Very High - Competitive advantage

**Configuration**:
```yaml
features:
  constraint_optimization:
    enabled: true
    solver: "or_tools"  # or "custom"
    storage_budget_mb: 10000.0
    max_indexes_per_table: 10
```

---

### 1.2 Automatic REINDEX Scheduling ⚠️ **CRITICAL**

**Status**: Detection exists, scheduling missing  
**User Pain Point**: #1 Index Bloat and Fragmentation  
**Priority**: **HIGH**

**What Exists**:
- ✅ `src/index_health.py` - `find_bloated_indexes()` - Detection
- ✅ `src/index_health.py` - `reindex_bloated_indexes()` - REINDEX function
- ✅ `src/index_lifecycle_advanced.py` - `predict_reindex_needs()` - Prediction

**What's Missing**:
- ⚠️ Automatic scheduling in maintenance workflow
- ⚠️ Configurable scheduling (weekly/monthly)
- ⚠️ Per-tenant bloat tracking

**Implementation**:
```python
# Add to src/maintenance.py (Step 7 enhancement)
def schedule_automatic_reindex(
    bloat_threshold_percent: float = 20.0,
    min_size_mb: float = 10.0,
    dry_run: bool = False,
) -> dict:
    """
    Automatically REINDEX bloated indexes during maintenance.
    
    Only runs if:
    - Auto-reindex enabled in config
    - Maintenance window active
    - System not under load
    """
    from src.index_health import reindex_bloated_indexes
    
    # Check if auto-reindex enabled
    auto_reindex_enabled = _config_loader.get_bool(
        "features.index_health.auto_reindex", False
    )
    
    if not auto_reindex_enabled:
        return {"skipped": True, "reason": "auto_reindex_disabled"}
    
    # Check maintenance window
    from src.maintenance_window import is_in_maintenance_window
    if not is_in_maintenance_window():
        return {"skipped": True, "reason": "not_in_maintenance_window"}
    
    # Check system load
    from src.cpu_throttle import should_throttle
    if should_throttle():
        return {"skipped": True, "reason": "system_under_load"}
    
    # Run REINDEX
    reindexed = reindex_bloated_indexes(
        bloat_threshold_percent=bloat_threshold_percent,
        min_size_mb=min_size_mb,
        dry_run=dry_run,
    )
    
    return {"reindexed": len(reindexed), "indexes": reindexed}
```

**Integration Point**: `src/maintenance.py` (Step 7 - after health monitoring)

**Effort**: Low-Medium (3-5 days)  
**Value**: Very High - Addresses critical user pain point

**Configuration**:
```yaml
features:
  index_health:
    enabled: true
    bloat_threshold: 20.0
    min_size_mb: 10.0
    auto_reindex: false  # Safety: requires explicit enable
    reindex_schedule: "weekly"  # weekly, monthly, or "on_demand"
```

---

## Phase 2: Algorithm Integration Verification (Week 5) - MEDIUM PRIORITY

### 2.1 iDistance Integration Verification ⚠️

**Status**: Code exists and IS integrated in `src/pattern_detection.py`  
**Priority**: **LOW** - Already integrated

**Verification Needed**:
- ✅ Check integration in `src/pattern_detection.py` (line 270-317)
- ✅ Verify configuration options
- ✅ Test multi-dimensional pattern detection

**Current Integration**: ✅ **VERIFIED** - Already integrated in `detect_multi_dimensional_pattern()`

**Action**: ✅ **NO ACTION NEEDED** - Already integrated

---

### 2.2 Bx-tree Integration Verification ⚠️

**Status**: Code exists and IS integrated in `src/pattern_detection.py`  
**Priority**: **LOW** - Already integrated

**Verification Needed**:
- ✅ Check integration in `src/pattern_detection.py` (line 338-416)
- ✅ Verify configuration options
- ✅ Test temporal pattern detection

**Current Integration**: ✅ **VERIFIED** - Already integrated in `detect_temporal_pattern()`

**Action**: ✅ **NO ACTION NEEDED** - Already integrated

---

## Phase 3: Advanced Features (Weeks 6-10) - MEDIUM PRIORITY

### 3.1 Cross-Tenant Pattern Learning ⚠️ **HIGH VALUE**

**Status**: Not implemented  
**Unique Advantage**: IndexPilot has multi-tenant awareness  
**Priority**: **MEDIUM-HIGH**

**What's Needed**:
- Learn from similar tenants
- Cross-tenant pattern recognition
- Tenant clustering based on query patterns
- Shared learning across tenants
- Privacy-preserving aggregation

**Implementation**:
```python
# src/cross_tenant_learning.py
def cluster_tenants_by_patterns(
    time_window_hours: int = 24,
) -> dict:
    """
    Cluster tenants by query patterns.
    
    Returns:
    - tenant_clusters: dict - Clusters of similar tenants
    - shared_patterns: dict - Patterns common to clusters
    """
    # Analyze query patterns per tenant
    # Use clustering algorithm (k-means, DBSCAN)
    # Identify shared patterns
    pass

def learn_from_tenant_cluster(
    tenant_id: int,
    cluster_id: int,
) -> dict:
    """
    Learn index patterns from tenant's cluster.
    
    Uses patterns from similar tenants to improve recommendations.
    """
    # Get cluster patterns
    # Apply to current tenant
    # Refine recommendations
    pass
```

**Integration Point**: `src/auto_indexer.py` - `should_create_index()`

**Effort**: High (3-4 weeks)  
**Value**: Very High - Unique competitive advantage

**Configuration**:
```yaml
features:
  cross_tenant_learning:
    enabled: true
    clustering_method: "kmeans"  # or "dbscan"
    min_cluster_size: 3
    privacy_preserving: true
```

---

### 3.2 Predictive Index Maintenance ⚠️

**Status**: Partial - Prediction exists, scheduling missing  
**Priority**: **MEDIUM**

**What Exists**:
- ✅ `src/index_lifecycle_advanced.py` - `predict_index_bloat()` - Bloat prediction
- ✅ `src/index_lifecycle_advanced.py` - `predict_reindex_needs()` - REINDEX prediction

**What's Missing**:
- ⚠️ Automatic scheduling based on predictions
- ⚠️ Proactive maintenance before bloat occurs
- ⚠️ Maintenance window optimization

**Implementation**:
```python
# Enhance src/index_lifecycle_advanced.py
def schedule_predictive_maintenance(
    prediction_days: int = 7,
    bloat_threshold_percent: float = 20.0,
) -> dict:
    """
    Schedule maintenance based on predictions.
    
    Predicts which indexes will need maintenance in next N days
    and schedules maintenance proactively.
    """
    # Get predictions
    predicted_needs = predict_reindex_needs(
        bloat_threshold_percent=bloat_threshold_percent,
        prediction_days=prediction_days,
    )
    
    # Schedule maintenance for predicted needs
    # Optimize maintenance windows
    # Return schedule
    pass
```

**Integration Point**: `src/maintenance.py` (enhance Step 13)

**Effort**: Medium (1-2 weeks)  
**Value**: High - Operational efficiency

---

### 3.3 Materialized View Support ⚠️

**Status**: Code exists (`src/materialized_view_support.py`) but needs integration  
**Priority**: **MEDIUM**

**What Exists**:
- ✅ `src/materialized_view_support.py` - MV support functions
- ✅ `src/maintenance.py` (Step 14) - MV support check

**What's Missing**:
- ⚠️ Integration into query analysis
- ⚠️ MV index recommendations
- ⚠️ MV refresh scheduling

**Implementation**:
```python
# Enhance src/query_analyzer.py
def analyze_materialized_view_query(
    query: str,
    mv_name: str,
) -> dict:
    """
    Analyze query on materialized view.
    
    Recommends indexes for materialized views.
    """
    # Analyze MV query
    # Recommend indexes
    # Consider MV refresh patterns
    pass
```

**Integration Point**: `src/query_analyzer.py` - `analyze_query_plan()`

**Effort**: Medium (1-2 weeks)  
**Value**: Medium - Specialized feature

---

## Phase 4: Query Plan Evolution (Weeks 11-12) - LOW PRIORITY

### 4.1 Query Plan Evolution Tracking ⚠️

**Status**: Not implemented  
**Priority**: **LOW**

**What's Needed**:
- Store query plans over time
- Track plan changes
- Correlate with index changes
- Optimize for plan stability

**Implementation**:
```python
# src/query_plan_evolution.py
def track_query_plan_evolution(
    query: str,
    plan: dict,
) -> dict:
    """
    Track how query plans evolve over time.
    
    Stores plan history and detects regressions.
    """
    # Store plan in history
    # Compare with previous plans
    # Detect regressions
    # Correlate with index changes
    pass
```

**Integration Point**: `src/query_analyzer.py` - `analyze_query_plan()`

**Effort**: Medium (1-2 weeks)  
**Value**: Medium - Continuous improvement

---

## Implementation Timeline

### Month 1: Critical Features
- **Week 1-2**: Constraint Programming research and design
- **Week 3-4**: Constraint Programming implementation
- **Week 4**: Automatic REINDEX scheduling

### Month 2: Advanced Features
- **Week 5**: Algorithm verification (iDistance, Bx-tree) - ✅ Already done
- **Week 6-7**: Cross-Tenant Pattern Learning
- **Week 8-9**: Predictive Index Maintenance
- **Week 10**: Materialized View Support

### Month 3: Polish
- **Week 11-12**: Query Plan Evolution Tracking

---

## Configuration Summary

All features are configurable via `indexpilot_config.yaml`:

```yaml
features:
  constraint_optimization:
    enabled: true
    solver: "or_tools"
    storage_budget_mb: 10000.0
  
  index_health:
    enabled: true
    auto_reindex: false  # Safety: explicit enable
    reindex_schedule: "weekly"
  
  cross_tenant_learning:
    enabled: true
    clustering_method: "kmeans"
    privacy_preserving: true
  
  predictive_maintenance:
    enabled: true
    prediction_days: 7
  
  materialized_view_support:
    enabled: true
  
  query_plan_evolution:
    enabled: true
```

---

## Success Metrics

### Constraint Programming
- Optimal index sets selected
- Storage budget respected
- Performance targets met
- Competitive with pganalyze

### Automatic REINDEX
- Bloat detected automatically
- REINDEX scheduled proactively
- Zero manual intervention
- Production-safe scheduling

### Cross-Tenant Learning
- Tenant clusters identified
- Shared patterns learned
- Recommendations improved
- Privacy preserved

---

**Plan Generated**: 07-12-2025  
**Status**: ✅ Complete  
**Next Review**: After Phase 1 completion

