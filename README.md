# IndexPilot - Automatic Database Index Management

## Concept

IndexPilot is a **thin control layer on top of Postgres** that automatically manages database indexes using DNA-inspired concepts:

1. **Genome**: A canonical global schema for a multi-tenant mini-CRM application
2. **Gene Expression**: Per-tenant activation/deactivation of fields/features
3. **Evolution/Mutations**: Automatic index creation based on query patterns, with full lineage tracking
4. **Measurement**: Before/after performance comparison to evaluate the approach

IndexPilot automatically manages database indexes based on actual query patterns, providing measurable performance improvements.

## Architecture

### Business Schema (Mini-CRM)

We use a simplified multi-tenant CRM schema with the following tables:
- `tenants`: Multi-tenant isolation
- `contacts`: Customer contacts with optional custom fields
- `organizations`: Companies/organizations
- `interactions`: Activity tracking (calls, emails, meetings, etc.)

This schema is inspired by common CRM patterns (similar to Django-CRM, BottleCRM, and other open-source CRMs) but kept minimal for demonstration. The schema is defined directly in `src/schema.py` rather than importing from an external CRM repository, as we only need the database structure, not the full application framework.

### Metadata Tables (DNA-Inspired Architecture)

1. **genome_catalog**: Canonical schema definition at the field level
2. **expression_profile**: Per-tenant field activation (which "genes" are expressed)
3. **mutation_log**: Complete lineage of all schema/index changes
4. **query_stats**: Query performance metrics for auto-indexing decisions

### Auto-Indexing Logic

The system automatically creates indexes based on a simple cost-benefit analysis:
- Analyzes query patterns from `query_stats`
- Estimates build cost (proportional to table size)
- Estimates query cost without index (full scan overhead)
- Creates index if: `queries × query_cost > build_cost`

## Setup

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- Make (or use commands directly)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/eyeinthesky6/indexpilot
cd indexpilot
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

**Note**: The system requires `pyyaml>=6.0.1` for bypass system configuration file support. This is included in `requirements.txt`.

3. Initialize the database:
```bash
make init-db
```

This will:
- Start Postgres in Docker
- Create all tables (business + metadata)
- Bootstrap the genome catalog

## Usage

### Run Tests

```bash
make run-tests
```

### Run Baseline Simulation

Run simulation without auto-indexing to establish baseline performance:

```bash
make run-sim-baseline
```

This creates multiple tenants, seeds data, and runs various query patterns.

### Run Auto-Index Simulation

Run simulation with auto-indexing enabled:

```bash
make run-sim-autoindex
```

This:
1. Runs a warmup phase to collect query statistics
2. Analyzes patterns and creates indexes automatically
3. Runs queries again with indexes in place
4. Saves results to `docs/audit/toolreports/results_with_auto_index.json`

### Generate Report

Compare baseline vs auto-index results:

```bash
make report
```

### Clean Up

Stop containers and remove result files:

```bash
make clean
```

## Project Structure

```
indexpilot/
├── docker-compose.yml      # Postgres setup
├── Makefile                # Build commands
├── requirements.txt        # Python dependencies
├── indexpilot_config.yaml  # Bypass system configuration (optional)
├── src/
│   ├── db.py              # Database connection helpers
│   ├── schema.py          # Schema setup and migrations
│   ├── genome.py          # Genome catalog operations
│   ├── expression.py      # Per-tenant expression logic
│   ├── stats.py           # Query stats collection
│   ├── auto_indexer.py    # Auto-indexing logic
│   ├── simulator.py       # Load generation and benchmarks
│   ├── reporting.py       # Performance reporting
│   ├── rollback.py        # Bypass system (enable/disable features)
│   ├── config_loader.py   # Configuration file loader
│   ├── bypass_config.py   # Bypass configuration manager
│   └── bypass_status.py   # Bypass status display
├── tests/
│   ├── test_genome.py
│   ├── test_auto_indexer.py
│   └── test_simulator.py
└── README.md
```

## Evaluation

After running both simulations, the report will show:

- **Mutation Summary**: How many indexes were created and for which fields
- **Query Performance**: Average, P95, and P99 latencies for different query patterns
- **Cost-Benefit Analysis**: Which fields met the threshold for indexing

### Success Criteria

IndexPilot succeeds when:
1. ✅ Query latencies for heavily-used filters decrease after auto-indexing
2. ✅ Indexes are NOT created for rarely-used fields (avoiding bloat)
3. ✅ Mutation log provides useful lineage of all changes

### System Benefits

IndexPilot provides value through:
- ✅ Measurable performance improvements for common query patterns
- ✅ Intelligent index creation based on actual usage
- ✅ Complete audit trail of all schema changes

## What We Learned

### Implementation Summary

IndexPilot was successfully implemented with:

1. **Genome Catalog**: Canonical schema definition with 30 fields across 4 business tables
2. **Expression Profiles**: Per-tenant field activation system
3. **Mutation Log**: Complete lineage tracking of all schema/index changes
4. **Auto-Indexer**: Cost-benefit analysis for automatic index creation
5. **Query Stats**: Performance metrics collection with batched logging

### Summary

IndexPilot successfully:
- Creates indexes automatically based on query patterns
- Tracks all schema changes with complete lineage
- Enables per-tenant field activation
- Provides measurable performance improvements

For detailed performance results and analysis, see `docs/reports/FINAL_REPORT.md`.

## Real-World Applications

This system is designed for **multi-tenant SaaS applications** where:

- You serve many customers (100+) with different usage patterns
- Each customer needs different features/fields enabled
- You need automatic database optimization without manual intervention
- You require complete audit trails for compliance

**Perfect for:**
- CRM systems (Salesforce, HubSpot)
- Project management tools (Asana, Monday.com)
- E-commerce platforms (Shopify, WooCommerce)
- Healthcare/EHR systems
- Financial services platforms
- Any B2B SaaS with multiple customers

**Not ideal for:**
- Single-tenant applications
- Very small datasets (< 1,000 rows)
- Applications with static, predictable query patterns

## Notes

- The CRM schema is simplified for demonstration purposes
- Production deployments should customize the schema to match their needs
- Cost estimation formulas are approximations and can be tuned
- For production use, you would need more sophisticated heuristics
- See `PRACTICAL_GUIDE.md` for detailed use cases and improvement ideas

## Production Deployment

**⚠️ Important**: See `PRODUCTION_DEPLOYMENT_ANALYSIS.md` for:
- Production readiness assessment
- Cost analysis and resource usage
- Side effects and risk mitigation
- Deployment checklist

**Current Status**: Safe for small deployments (< 100 tenants). Needs hardening for larger scale.

### Bypass System

The system includes a comprehensive **4-level bypass mechanism** for production safety:

- **Level 1**: Feature-level bypasses (auto-indexing, stats collection, etc.)
- **Level 2**: Module-level bypasses
- **Level 3**: System-level bypass (complete system bypass)
- **Level 4**: Startup bypass (skip initialization)

**Configuration**:
- **Config File**: `indexpilot_config.yaml` (see example in project root)
- **Environment Variables**: `INDEXPILOT_BYPASS_MODE`, `INDEXPILOT_BYPASS_*_ENABLED`
- **Runtime API**: `disable_system()`, `disable_stats_collection()`, etc.

**Status Visibility**:
- Bypass status is automatically logged at startup
- Periodic status logging (every hour)
- Check status: `from src.rollback import get_system_status`

**Documentation**:
- `BYPASS_SYSTEM_ANALYSIS.md` - Complete analysis and design
- `BYPASS_SYSTEM_CONFIG_DESIGN.md` - Configuration file design
- `BYPASS_SYSTEM_VISIBILITY_IMPLEMENTATION.md` - Status visibility implementation

### Integration with Host Applications

**NEW**: The system now supports integration with host application utilities (monitoring, database, audit, logging, error tracking) through adapters.

**Quick Start**:
```python
from src.adapters import configure_adapters
import datadog
import sentry_sdk

# Configure adapters to use host utilities
configure_adapters(
    monitoring=datadog.statsd,      # Host monitoring
    database=host_db_pool,          # Host database pool
    error_tracker=sentry_sdk        # Host error tracking
)
```

**Benefits**:
- ✅ Use host monitoring (Datadog, Prometheus, etc.) - **CRITICAL for production**
- ✅ Reuse host database connections (reduces resource waste)
- ✅ Unified audit trail with host system
- ✅ Better error tracking (Sentry, Rollbar)
- ✅ Backward compatible (works without adapters)

**Full Documentation**: See `docs/ADAPTERS_USAGE_GUIDE.md` for complete integration guide.

**Why This Matters**: Internal monitoring is in-memory and loses alerts on restart. Host monitoring ensures alerts are persisted and visible in your existing monitoring dashboards.

## Enhancement Roadmap

See `ENHANCEMENT_ROADMAP.md` for detailed plans to:
- Make the system work better for small databases (< 10k rows)
- Add support for MySQL, SQL Server, and other databases
- Implement predictive indexing and ML-based optimization
- Add real-time monitoring and A/B testing

## License

[Add your license here]

