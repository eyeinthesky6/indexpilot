# Simulation Guide

## Overview

This is the **main guide** for running simulations with IndexPilot. The simulator supports **real-world scenarios** with realistic traffic patterns, including occasional spikes. The simulator has been **optimized for performance** with bulk inserts and connection reuse, making it **1.7-2x faster** than before. This makes it easy to test the system under different load conditions efficiently.

**Related Documentation:**
- `docs/installation/EXECUTION_GUIDE.md` - Step-by-step execution instructions
- `docs/SIMULATOR_OPTIMIZATIONS.md` - Detailed performance optimization analysis
- `docs/reports/PERFORMANCE_EXPLANATION.md` - Why simulations seem slow vs production

## Available Scenarios

### Small (Startup SaaS)
- **Description**: Small SaaS (startup, 10-50 customers)
- **Configuration**:
  - 10 tenants
  - 500 contacts per tenant
  - 200 queries per tenant
  - 10% spike probability (3x multiplier)
- **Estimated time**: ~2 minutes
- **Use case**: Quick testing, development validation

### Medium (Growing Business) - **DEFAULT**
- **Description**: Medium SaaS (growing business, 100-500 customers)
- **Configuration**:
  - 50 tenants
  - 2,000 contacts per tenant
  - 500 queries per tenant
  - 15% spike probability (4x multiplier)
- **Estimated time**: ~10 minutes
- **Use case**: Standard testing, production-like validation

### Large (Established Business)
- **Description**: Large SaaS (established business, 1000+ customers)
- **Configuration**:
  - 100 tenants
  - 10,000 contacts per tenant
  - 1,000 queries per tenant
  - 20% spike probability (5x multiplier)
- **Estimated time**: ~45 minutes
- **Use case**: Scale testing, performance validation

### Stress Test (Maximum Load)
- **Description**: Stress test (maximum load, 10,000+ customers)
- **Configuration**:
  - 200 tenants
  - 50,000 contacts per tenant
  - 2,000 queries per tenant
  - 30% spike probability (10x multiplier)
- **Estimated time**: ~3 hours
- **Use case**: Maximum load testing, capacity planning

## Traffic Spikes

All scenarios include **realistic traffic spikes** that simulate:
- Marketing campaigns
- Product launches
- Viral content
- Scheduled events

**Spike characteristics:**
- Random occurrence based on probability
- Multiplier effect (3x-10x normal traffic)
- Limited duration (20-100 queries)
- Visual indicators during simulation

## Usage Examples

### Basic Usage (Medium Scenario - Default)

```bash
# Baseline simulation
python -m src.simulation.simulator baseline

# Auto-index simulation
python -m src.simulation.simulator autoindex

# Both (scaled)
python -m src.simulation.simulator scaled

# Comprehensive mode (tests all features)
python -m src.simulation.simulator comprehensive --scenario medium
```

### Comprehensive Mode

The comprehensive mode runs both baseline and auto-index simulations, then verifies all product features:

```bash
# Small scenario (quick comprehensive test)
python -m src.simulation.simulator comprehensive --scenario small

# Medium scenario (standard comprehensive test)
python -m src.simulation.simulator comprehensive --scenario medium

# Large scenario (comprehensive test at scale)
python -m src.simulation.simulator comprehensive --scenario large

# Stress test (comprehensive test at maximum load)
python -m src.simulation.simulator comprehensive --scenario stress-test
```

**What Comprehensive Mode Tests:**
- ✅ Mutation log verification (schema lineage tracking)
- ✅ Expression profile verification (per-tenant field activation)
- ✅ Production safeguards (maintenance windows, rate limiting, CPU throttling, write performance)
- ✅ Bypass system verification
- ✅ Health checks verification

**Results:** Saves comprehensive results to `docs/audit/toolreports/results_comprehensive.json`

### Specific Scenarios

```bash
# Small scenario (quick test)
python -m src.simulation.simulator baseline --scenario small

# Large scenario
python -m src.simulation.simulator baseline --scenario large

# Stress test
python -m src.simulation.simulator baseline --scenario stress-test
```

### Custom Parameters

You can override scenario parameters:

```bash
# Use medium scenario but with custom tenant count
python -m src.simulation.simulator baseline --scenario medium --tenants 25

# Custom everything
python -m src.simulation.simulator baseline --tenants 20 --queries 500 --contacts 2000
```

## Command-Line Options

```
positional arguments:
  {baseline,autoindex,scaled,comprehensive}
                        Simulation mode

options:
  --scenario {small,medium,large,stress-test}
                        Scenario to run (default: medium)
  --tenants TENANTS     Number of tenants (overrides scenario)
  --queries QUERIES     Queries per tenant (overrides scenario)
  --contacts CONTACTS   Contacts per tenant (overrides scenario)
  --orgs ORGS           Organizations per tenant (overrides scenario)
  --interactions INTERACTIONS
                        Interactions per tenant (overrides scenario)
```

## Spike Simulation Details

### How Spikes Work

1. **Random Detection**: During normal query execution, there's a probability (10-30%) of entering a spike
2. **Multiplier Effect**: During a spike, multiple queries run per iteration (3x-10x normal rate)
3. **Limited Duration**: Spikes last for a fixed number of queries (20-100)
4. **Visual Feedback**: Console shows when spikes start and end

### Example Output

```
Tenant 5: 🚀 SPIKE DETECTED at query 150 (will last 30 queries)
Tenant 5: Completed 180/500 queries (🚀 SPIKE)
Tenant 5: ✅ Spike ended at query 180
```

### Real-World Patterns

Spikes simulate:
- **Marketing campaigns**: Sudden traffic increase
- **Product launches**: Initial burst of activity
- **Viral content**: Exponential traffic growth
- **Scheduled events**: Predictable traffic spikes

## Scenario Comparison

| Scenario | Tenants | Contacts/Tenant | Queries/Tenant | Total Queries | Spike Prob | Spike Mult | Est. Time |
|----------|---------|-----------------|----------------|--------------|------------|------------|-----------|
| Small | 10 | 500 | 200 | 2,000 | 10% | 3x | ~2 min |
| Medium | 50 | 2,000 | 500 | 25,000 | 15% | 4x | ~6 min |
| Large | 100 | 10,000 | 1,000 | 100,000 | 20% | 5x | ~25 min |
| Stress-test | 200 | 50,000 | 2,000 | 400,000 | 30% | 10x | ~1.5 hours |

**Note**: Times are approximate and reflect performance optimizations (bulk inserts, connection reuse). Actual times may vary based on hardware.

## Best Practices

### For Development
- Use **small** scenario for quick validation
- Run after code changes to verify functionality

### For Testing
- Use **medium** scenario for standard testing
- Validates production-like conditions

### For Performance Testing
- Use **large** scenario for scale testing
- Validates system under heavy load

### For Capacity Planning
- Use **stress-test** scenario for maximum load
- Identifies system limits and bottlenecks

## Integration with Reports

All scenarios generate the same report format:
- `results_baseline.json` - Baseline results
- `results_with_auto_index.json` - Auto-index results

Reports include:
- Scenario name
- Spike statistics
- Performance metrics
- Index creation details

## Tips

1. **Start Small**: Begin with small scenario to verify setup
2. **Progress Gradually**: Move to medium, then large as needed
3. **Monitor Spikes**: Watch for spike indicators during simulation
4. **Check Reports**: Review generated reports for insights
5. **Customize**: Override parameters for specific test cases

## Troubleshooting

### Simulation Too Slow
- Use smaller scenario (small instead of large)
- Reduce number of tenants with `--tenants`
- Reduce queries with `--queries`

### Need More Realistic Spikes
- Spikes are already included in all scenarios
- Adjust spike parameters in code if needed

### Want Different Patterns
- Use `--scenario` to switch between scenarios
- Override individual parameters as needed

## Performance Optimizations

The simulator has been optimized for significantly better performance. Key improvements:

- **Data Seeding**: 10x faster using bulk inserts (`executemany()`)
- **Query Execution**: 1.4-1.8x faster by reusing database connections
- **Overall**: 1.7-2x faster simulation time

For detailed technical analysis of all optimizations, see `docs/SIMULATOR_OPTIMIZATIONS.md`.

## Comprehensive Mode

The comprehensive mode (`comprehensive`) is a special simulation mode that tests **all product features** in addition to performance testing. It's recommended for validating production readiness.

### What It Tests

1. **Mutation Log Verification** - Verifies that all index operations are logged to mutation_log with complete details
2. **Expression Profile Verification** - Verifies that per-tenant field activation is working correctly
3. **Production Safeguards** - Tests maintenance windows, rate limiting, CPU throttling, and write performance monitoring
4. **Bypass System** - Verifies that the 4-level bypass system is functioning correctly
5. **Health Checks** - Verifies that health check endpoints return correct status

### Usage

```bash
# Small scenario (quick comprehensive test - ~5 minutes)
python -m src.simulation.simulator comprehensive --scenario small

# Medium scenario (standard comprehensive test - ~15 minutes)
python -m src.simulation.simulator comprehensive --scenario medium

# Large scenario (comprehensive test at scale - ~60 minutes)
python -m src.simulation.simulator comprehensive --scenario large

# Stress test (comprehensive test at maximum load - ~4 hours)
python -m src.simulation.simulator comprehensive --scenario stress-test
```

### Output

Comprehensive mode generates:
- Standard simulation results (baseline and auto-index)
- Feature verification results
- Comprehensive report saved to `docs/audit/toolreports/results_comprehensive.json`

The verification results include:
- [OK]/[ERROR] status for each feature
- Error and warning counts
- Detailed verification information

### When to Use

- **Before Production Deployment**: Verify all features work correctly
- **After Code Changes**: Ensure no regressions
- **Regular Testing**: Periodic comprehensive testing (weekly/monthly)
- **Scale Testing**: Test features at different database sizes

## Next Steps

1. Run a small scenario to verify setup
2. Run medium scenario for standard testing
3. **Run comprehensive mode to test all features** (recommended)
4. Generate reports and analyze results
5. Scale up to large/stress-test as needed

