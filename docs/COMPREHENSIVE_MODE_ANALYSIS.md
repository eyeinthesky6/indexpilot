# Comprehensive Mode Analysis

**Date**: 2025-12-08  
**Status**: Analysis Complete

---

## Current Behavior

**Comprehensive mode runs ONE scenario with ALL features tested.**

### What Comprehensive Mode Does:

1. **Baseline Simulation** (one scenario: small/medium/large/stress-test)
2. **Auto-Index Simulation** (same scenario, same tenants)
3. **Schema Mutations Testing** (add/drop columns, schema evolution)
4. **Feature Verification** (all product features)
5. **A/B Testing** (index strategy experiments)
6. **Predictive Maintenance** (index lifecycle management)

### What Comprehensive Mode Does NOT Do:

- ❌ Does NOT run all scenarios (small, medium, large, stress-test)
- ❌ Only runs the scenario specified with `--scenario` flag (default: medium)

---

## Example Usage

```bash
# Run comprehensive mode with small scenario
python -m src.simulation.simulator comprehensive --scenario small

# Run comprehensive mode with medium scenario (default)
python -m src.simulation.simulator comprehensive

# Run comprehensive mode with large scenario
python -m src.simulation.simulator comprehensive --scenario large
```

---

## Recommendation

**If you want to test all scenarios**, you need to run comprehensive mode multiple times:

```bash
# Test all scenarios sequentially
python -m src.simulation.simulator comprehensive --scenario small
python -m src.simulation.simulator comprehensive --scenario medium
python -m src.simulation.simulator comprehensive --scenario large
```

**OR** we could enhance comprehensive mode to optionally run all scenarios:

```bash
# Proposed: Run all scenarios in one command
python -m src.simulation.simulator comprehensive --all-scenarios
```

---

## Current Implementation

```python
# src/simulation/simulator.py line 1691-2017
elif args.mode == "comprehensive":
    # Runs ONE scenario (args.scenario)
    # Tests ALL features within that scenario
    # Does NOT iterate through all scenarios
```

---

## Summary

- ✅ Comprehensive mode tests **all features** (baseline, autoindex, schema, A/B, maintenance)
- ❌ Comprehensive mode does **NOT** test all scenarios (only one scenario per run)
- 💡 To test all scenarios, run comprehensive mode multiple times with different `--scenario` values

