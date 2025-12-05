# IndexPilot - Focused Enhancement Roadmap

## Philosophy: Focused Development

This roadmap is **ruthlessly prioritized** to enhance IndexPilot from a working system to a production-ready autopilot in **2-3 weeks**, not 4-6 months.

**Core Principle**: Only build what proves the concept. Everything else is "someday maybe."

---

## Phase 1: Core Enhancements (2-3 Weeks)

These 4 enhancements will make the system **measurably better** without over-engineering:

### ✅ Enhancement 1: EXPLAIN-Based Query Plan Analysis

**Why**: Stop guessing, start measuring. Real query plans tell us what's actually happening.

**What to Build**:
- Parse `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` output
- Detect sequential scans (bad), index scans (good), nested loops (maybe slow)
- Use actual plan costs, not estimates
- Flag queries that would benefit from indexes

**Implementation**:
```python
def analyze_query_plan(query, params):
    """Get real query execution plan"""
    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
    plan_json = execute_query(explain_query, params)
    plan = json.loads(plan_json[0][0])
    
    # Extract key metrics
    total_cost = plan['Plan']['Total Cost']
    actual_time = plan['Execution Time']
    node_type = plan['Plan']['Node Type']  # Seq Scan, Index Scan, etc.
    
    return {
        'cost': total_cost,
        'time_ms': actual_time,
        'node_type': node_type,
        'needs_index': node_type == 'Seq Scan' and total_cost > threshold
    }
```

**Action Items**:
- [ ] Implement EXPLAIN parsing
- [ ] Detect sequential scans
- [ ] Use real costs in index decision logic
- [ ] Add plan analysis to query stats

---

### ✅ Enhancement 2: Micro-Indexes (Partial & Expression)

**Why**: Not all indexes are created equal. Partial and expression indexes are often better, especially for small-medium tables.

**What to Build**:
- Detect query patterns (exact match vs LIKE vs range)
- Create partial indexes for filtered queries
- Create expression indexes for pattern matching (e.g., `LOWER(email)`)
- Monitor index size vs. benefit

**Implementation**:
```python
def create_smart_index(table_name, field_name, row_count, query_patterns):
    """Create optimized index based on usage patterns"""
    
    # Check if queries use LIKE (pattern matching)
    has_like_queries = any('LIKE' in p for p in query_patterns)
    
    # Check if field has many NULLs
    null_ratio = get_null_ratio(table_name, field_name)
    
    if has_like_queries:
        # Expression index for text search
        return f"""
            CREATE INDEX idx_{table_name}_{field_name}_lower
            ON {table_name}(LOWER({field_name}))
        """
    elif null_ratio > 0.5:
        # Partial index: only index non-null values
        return f"""
            CREATE INDEX idx_{table_name}_{field_name}_partial
            ON {table_name}({field_name})
            WHERE {field_name} IS NOT NULL
        """
    else:
        # Standard index
        return f"""
            CREATE INDEX idx_{table_name}_{field_name}_tenant
            ON {table_name}(tenant_id, {field_name})
        """
```

**Action Items**:
- [ ] Detect query patterns (exact, LIKE, range)
- [ ] Calculate NULL ratio for fields
- [ ] Create partial indexes when appropriate
- [ ] Create expression indexes for text search
- [ ] Track index size and effectiveness

---

### ✅ Enhancement 3: Adaptive Strategy by Row Count

**Why**: Small tables need different optimization than large ones. But don't be dogmatic - let measurement decide.

**What to Build**:
- Detect table size
- Choose strategy: caching-focused (small) vs. indexing-focused (large)
- **But still allow indexes for small tables if they help**
- Measure actual impact, not just size

**Implementation**:
```python
def get_optimization_strategy(table_name, row_count):
    """Choose strategy, but don't hard-ban anything"""
    if row_count < 1000:
        return {
            'primary': 'caching',  # Focus on caching
            'secondary': 'micro_indexes',  # But still allow smart indexes
            'skip_traditional_indexes': True  # Skip big indexes
        }
    elif row_count < 10000:
        return {
            'primary': 'micro_indexes',  # Partial/expression indexes
            'secondary': 'caching',
            'skip_traditional_indexes': False
        }
    else:
        return {
            'primary': 'indexing',  # Full indexing
            'secondary': 'caching',
            'skip_traditional_indexes': False
        }
```

**Key Insight**: Don't say "no indexes < 10k rows". Say "prefer caching, but create indexes if they measurably help."

**Action Items**:
- [ ] Add row count detection
- [ ] Implement strategy selection
- [ ] Add caching layer (simple in-memory first)
- [ ] Measure impact regardless of strategy

---

### ✅ Enhancement 4: Real Before/After Measurement

**Why**: Stop estimating, start measuring. Only keep optimizations that actually help.

**What to Build**:
- Run query before optimization, measure time
- Apply optimization (index/cache)
- Run query after, measure time
- Calculate actual improvement
- Only keep if improvement > threshold (e.g., 20%)

**Implementation**:
```python
def measure_optimization_impact(query, params, optimization_func):
    """Measure real before/after impact"""
    
    # Warm up (run once to avoid cold start)
    execute_query(query, params)
    
    # Measure before
    before_times = []
    for _ in range(10):  # Run 10 times, take median
        start = time.time()
        execute_query(query, params)
        before_times.append((time.time() - start) * 1000)
    before_median = sorted(before_times)[5]
    
    # Apply optimization
    optimization_func()
    
    # Wait for index to be ready (if index was created)
    time.sleep(1)
    
    # Measure after
    after_times = []
    for _ in range(10):
        start = time.time()
        execute_query(query, params)
        after_times.append((time.time() - start) * 1000)
    after_median = sorted(after_times)[5]
    
    improvement = (before_median - after_median) / before_median
    
    return {
        'before_ms': before_median,
        'after_ms': after_median,
        'improvement_pct': improvement * 100,
        'worth_it': improvement > 0.2  # 20% improvement threshold
    }
```

**Action Items**:
- [ ] Implement before/after measurement
- [ ] Add improvement threshold (only keep if > 20% better)
- [ ] Auto-rollback if no improvement
- [ ] Store measurement results

---

## What We're NOT Building (For Now)

These are **conceptually good** but **over-scoped for Phase 1**:

### ❌ Multi-Database Adapter
- **Why skip**: Lock to PostgreSQL. Adding MySQL/SQL Server = 2-3 weeks of edge cases.
- **When to add**: Only if this becomes a real product with paying customers.

### ❌ Predictive Indexing / ML
- **Why skip**: First prove heuristics work. ML is "PhD addon" not "core validation".
- **When to add**: After you have real users and clear evidence heuristics hit limits.

### ❌ Full A/B Testing Framework
- **Why skip**: Your simulator IS the A/B test. No need for complex infra.
- **When to add**: If this becomes a service with multiple customers.

### ❌ Real-Time Monitoring Stack
- **Why skip**: Basic logging is enough. Full TSDB + dashboards = overkill.
- **When to add**: If this becomes a product needing 24/7 monitoring.

### ❌ Full Cost-Aware Optimization
- **Why skip**: Simple cost model works for now. Real cost tracking = complex.
- **When to add**: If you need to justify ROI to customers.

---

## Implementation Plan

### Week 1: Foundation
- [ ] Day 1-2: EXPLAIN plan analysis
- [ ] Day 3-4: Micro-indexes (partial/expression)
- [ ] Day 5: Adaptive strategy selection

### Week 2: Measurement & Caching
- [ ] Day 1-2: Before/after measurement
- [ ] Day 3-4: Simple caching layer
- [ ] Day 5: Integration & testing

### Week 3: Polish & Validation
- [ ] Day 1-2: Fix bugs, improve accuracy
- [ ] Day 3-4: Rerun full performance tests
- [ ] Day 5: Document results

---

## Success Criteria

**Phase 1 is successful if:**
1. ✅ System uses real query plans (not estimates)
2. ✅ Creates smarter indexes (partial/expression when appropriate)
3. ✅ Measures actual impact (only keeps optimizations that help)
4. ✅ Works better for small DBs (caching + smart indexes)

**If Phase 1 succeeds**, then consider Phase 2 (but not before).

---

## Future Directions (Someday Maybe)

Keep these in mind, but **don't build them now**:

- Multi-database support (PostgreSQL → MySQL → SQL Server)
- Predictive indexing based on tenant similarity
- ML-powered optimization
- Full monitoring dashboard
- A/B testing infrastructure
- Cost-aware optimization with real cloud costs

These are **valid long-term goals**, but they're **scope creep for the current development phase**.

---

## Key Principles

1. **Measure, don't guess**: Use EXPLAIN, measure before/after
2. **Be adaptive, not dogmatic**: Small DBs can still use indexes if they help
3. **Focus on value**: If Phase 1 doesn't show value, reassess before building Phase 2-4.
4. **Keep it simple**: In-memory cache is fine. Don't need Redis yet.
5. **PostgreSQL only**: One database is enough for now.

---

## Conclusion

This roadmap is **focused, implementable, and testable** in 2-3 weeks.

If these 4 enhancements don't show clear value, the concept might not be worth pursuing further.

If they do show value, you have a solid foundation to build on (or decide it's good enough as-is).

**The goal**: Move from "working system" to "production-ready tool" without building a database company.
