# IndexPilot Case Study Library

**Date**: 08-12-2025  
**Purpose**: Collection of real-world case studies demonstrating IndexPilot's effectiveness

---

## What is a Case Study?

A case study documents:
- **Problem**: Database performance issues
- **Solution**: How IndexPilot addressed the problem
- **Results**: Measurable improvements (query time, throughput, etc.)
- **Lessons**: What we learned

---

## Case Study Structure

Each case study should follow this template:

```markdown
# Case Study: [Database Name / Company Name]

**Date**: DD-MM-YYYY  
**Database**: [Database name]  
**Schema**: [Schema description]  
**Size**: [Number of tables, rows, etc.]

## Problem Statement

[Describe the performance problem]

## Initial State

- **Query Performance**: [Baseline metrics]
- **Indexes**: [Number of indexes, which ones]
- **Pain Points**: [Specific issues]

## Solution

- **IndexPilot Configuration**: [Settings used]
- **Indexes Created**: [Which indexes IndexPilot created]
- **Timeline**: [How long it took]

## Results

### Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Average Query Time | X ms | Y ms | Z% |
| P95 Query Time | X ms | Y ms | Z% |
| Throughput | X qps | Y qps | Z% |

### Indexes Created

- [List of indexes created]
- [Why each was created]

## Analysis

[Detailed analysis of results]

## Lessons Learned

[What we learned from this case study]

## Files

- **Schema Config**: `schema_config_[name].yaml`
- **Results**: `results_[name].json`
- **Report**: `report_[name].md`
```

---

## Available Case Studies

### 1. Sakila Database
- **Status**: ⏳ Pending
- **Description**: DVD rental store database
- **File**: `CASE_STUDY_SAKILA.md`

### 2. Employees Database
- **Status**: ⏳ Pending
- **Description**: Employee management database
- **File**: `CASE_STUDY_EMPLOYEES.md`

### 3. CRM Simulation
- **Status**: ✅ Available
- **Description**: Multi-tenant CRM simulation
- **File**: `CASE_STUDY_CRM_SIMULATION.md`

### 4. Stock Market Data
- **Status**: ✅ Available
- **Description**: Real stock market historical data
- **File**: `CASE_STUDY_STOCK_MARKET.md`

---

## Creating a New Case Study

### Step 1: Run Tests
```bash
# Baseline
python -m src.simulation.simulator baseline --scenario medium

# With IndexPilot
python -m src.simulation.simulator autoindex --scenario medium

# Generate report
make report
```

### Step 2: Copy Template
```bash
cp docs/case_studies/TEMPLATE.md docs/case_studies/CASE_STUDY_[NAME].md
```

### Step 3: Fill in Details
- Update problem statement
- Add performance metrics
- Document indexes created
- Analyze results

### Step 4: Add Visualizations
- Create charts (optional)
- Add screenshots (optional)
- Include query plans (optional)

### Step 5: Update Index
- Add to this README
- Link from main documentation

---

## Case Study Best Practices

### 1. Be Specific
- Use actual numbers (not "faster")
- Include query examples
- Show before/after comparisons

### 2. Be Honest
- Document limitations
- Mention edge cases
- Acknowledge when IndexPilot didn't help

### 3. Be Useful
- Explain why indexes were created
- Share configuration tips
- Provide actionable insights

### 4. Be Visual
- Use tables for metrics
- Include charts when helpful
- Show query plans if relevant

---

## Case Study Template

See `TEMPLATE.md` for a complete case study template.

---

## Contributing Case Studies

If you've tested IndexPilot on your database:

1. **Document Results**: Create a case study following the template
2. **Anonymize Data**: Remove sensitive information
3. **Share**: Submit via GitHub or email

We'll review and add to the library!

---

**Last Updated**: 08-12-2025

