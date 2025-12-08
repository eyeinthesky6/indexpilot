# Case Study: Small_Scenario

**Date**: 08-12-2025  
**Database**: indexpilot  
**Schema**: [Schema description - e.g., "Multi-tenant CRM with 4 tables"]  
**Size**: 4 tables, ~5,000-50,000 rows  
**IndexPilot Version**: [Version if applicable]

---

## Executive Summary

[One paragraph summary of the case study - problem, solution, key results]

**Key Results**:
- ✅ [Improvement 1]
- ✅ [Improvement 2]
- ✅ [Improvement 3]

---


## Performance Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Queries | 1290 | 2000 | - |
| Average Latency | 0 ms | 0 ms | 0.0% |
| P95 Latency | 0 ms | 0 ms | - |
| P99 Latency | 0 ms | 0 ms | - |

## Indexes Analyzed

- **Total**: 0
- **Advisory Mode**: 0
- **Applied**: 0

## Problem Statement

[Describe the performance problem in detail]

### Context
- **Application**: IndexPilot CRM Simulation
- **Workload**: [Type of workload - OLTP, OLAP, mixed]
- **Scale**: 1290 queries

### Symptoms
- [Symptom 1 - e.g., "Slow queries on contacts table"]
- [Symptom 2 - e.g., "High CPU usage during peak hours"]
- [Symptom 3 - e.g., "Timeouts on complex joins"]

### Impact
- [Business impact - e.g., "User complaints", "Revenue loss", etc.]

---

## Initial State

### Database Schema
```
[Describe schema or include diagram]
- Table 1: [description]
- Table 2: [description]
```

### Existing Indexes
- Primary keys only (baseline)
- [Why they exist]

### Performance Metrics (Before IndexPilot)

| Metric | Value | Notes |
|--------|-------|-------|
| Average Query Time | 0 ms | [Details] |
| P95 Query Time | 0 ms | [Details] |
| P99 Query Time | 0 ms | [Details] |
| Throughput | X qps | [Details] |
| Slow Queries (>1s) | X per hour | [Details] |
| Database Size | X GB | [Details] |
| Index Size | X GB | [Details] |

### Query Patterns
[Describe common query patterns]
```sql
-- Example query 1
SELECT * FROM contacts WHERE tenant_id = ? AND email = ?;

-- Example query 2
SELECT * FROM interactions WHERE tenant_id = ? AND occurred_at > ?;
```

### Pain Points
1. [Pain point 1]
2. [Pain point 2]
3. [Pain point 3]

---

## Solution

### IndexPilot Configuration

**Mode**: [advisory / apply]  
**Settings**:
```yaml
# Relevant config settings
```

### Setup Process

1. **Schema Discovery**: [How schema was discovered]
2. **Genome Bootstrapping**: [How genome catalog was created]
3. **Query Statistics Collection**: [How queries were logged]
4. **Index Analysis**: [How IndexPilot analyzed patterns]
5. **Index Creation**: [How indexes were created]

### Timeline
- **Day 1**: [Setup]
- **Day 2-7**: [Query collection]
- **Day 8**: [Index analysis]
- **Day 9**: [Index creation]
- **Day 10+**: [Monitoring]

---

## Indexes Created by IndexPilot

### Indexes Created

| Table | Columns | Type | Reason | Impact |
|-------|---------|------|--------|--------|
| contacts | (tenant_id, email) | btree | High query volume | High |
| interactions | (tenant_id, occurred_at) | btree | Time-range queries | Medium |

### Index Creation Details

**Index 1**: `contacts_tenant_id_email_idx`
- **Created**: [Date]
- **Reason**: Query pattern analysis
- **Query Pattern**: Multi-tenant CRM queries
- **Cost-Benefit**: Cost-benefit analysis passed

**Index 2**: [Similar details]

### Indexes NOT Created

[Indexes IndexPilot considered but didn't create, and why]

---

## Results

### Performance Improvements

| Metric | Before | After | Improvement | Notes |
|--------|--------|-------|-------------|-------|
| Average Query Time | 0 ms | 0 ms | N/A | [Details] |
| P95 Query Time | 0 ms | 0 ms | N/A | [Details] |
| P99 Query Time | 0 ms | 0 ms | N/A | [Details] |
| Throughput | X qps | Y qps | N/A | [Details] |
| Slow Queries (>1s) | X/hour | Y/hour | N/A | [Details] |
| Index Size | X GB | Y GB | +Z GB | [Details] |

### Query-Specific Improvements

| Query Pattern | Before | After | Improvement |
|---------------|--------|-------|-------------|
| Contact lookup by email | 0 ms | 0 ms | N/A |
| Time-range queries | 0 ms | 0 ms | N/A |
| Multi-table joins | 0 ms | 0 ms | N/A |

### Resource Usage

| Resource | Before | After | Change |
|----------|--------|-------|--------|
| CPU Usage | X% | Y% | [Change] |
| Memory Usage | X GB | Y GB | [Change] |
| Disk I/O | X IOPS | Y IOPS | [Change] |

---

## Analysis

### What Worked Well

1. [Success 1]
2. [Success 2]
3. [Success 3]

### What Didn't Work

1. [Issue 1 - if any]
2. [Issue 2 - if any]

### Surprises

1. [Unexpected finding 1]
2. [Unexpected finding 2]

### IndexPilot's Decisions

[Analysis of IndexPilot's index creation decisions]
- **Correct Decisions**: [Indexes that were good]
- **Questionable Decisions**: [Indexes that might not be optimal]
- **Missed Opportunities**: [Indexes that should have been created but weren't]

---

## Lessons Learned

### Technical Lessons

1. [Lesson 1]
2. [Lesson 2]
3. [Lesson 3]

### Best Practices

1. [Best practice 1]
2. [Best practice 2]

### Recommendations

1. [Recommendation 1]
2. [Recommendation 2]

---

## Comparison with Manual Indexing

[If applicable, compare with manual index creation]

| Aspect | Manual | IndexPilot |
|--------|--------|------------|
| Time to Create | X hours | Y hours |
| Indexes Created | X | Y |
| Performance Gain | X% | Y% |
| Maintenance | [Details] | [Details] |

---

## Future Improvements

[What could be improved in IndexPilot based on this case study]

1. [Improvement 1]
2. [Improvement 2]

---

## Files and Resources

### Configuration Files
- **Schema Config**: `schema_config_[name].yaml`
- **IndexPilot Config**: `indexpilot_config.yaml`

### Results Files
- **Baseline Results**: `results_baseline_[name].json`
- **IndexPilot Results**: `results_autoindex_[name].json`
- **Performance Report**: `report_[name].md`

### Scripts
- **Setup Script**: `scripts/setup_[name].py`
- **Analysis Script**: `scripts/analyze_[name].py`

---

## Conclusion

[Summary paragraph]

**Key Takeaways**:
1. [Takeaway 1]
2. [Takeaway 2]
3. [Takeaway 3]

**Would we use IndexPilot again?** [Yes/No/Maybe] - [Why]

---

**Case Study Author**: [Name/Team]  
**Review Status**: [Draft / Review / Published]  
**Last Updated**: 08-12-2025

