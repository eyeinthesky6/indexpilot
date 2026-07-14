# IndexPilot - Database DNA Advisor

> **Project status: open-source preview.** The PostgreSQL backend and demo API are working and
> database-backed tests pass, but IndexPilot is not yet a drop-in production service. It is
> advisory by default. Review every recommendation before explicitly enabling DDL changes.

## What Is Ready Today

- PostgreSQL schema discovery or schema-file bootstrapping
- A read-only workload DNA report sourced from `pg_stat_statements`
- PostgreSQL AST parsing for CTEs, aliases, joins, quoted identifiers, and placeholders
- Optional HypoPG comparison of smaller and composite index shapes
- Auto-indexer admission of planner-backed evidence with explicit tenant scope
- Explicit query-stat collection and cost-based index recommendations
- Advisory recommendations with mutation/audit history
- Optional index application with maintenance, rate, storage, and rollback controls
- A FastAPI read dashboard backend and a Next.js dashboard

## Important Limits

- The standalone DNA report reads `pg_stat_statements`. The full auto-indexer still requires
  `log_query_stat()` or another integration that supplies field-level workload statistics.
- `pg_stat_statements` can be empty after a reset/restart or before representative traffic. The
  report exposes that state; zero candidates must not be read as proof that no index is needed.
- The DNA/HypoPG path proves tenant-keyed indexes from query predicates. The legacy field-stat loop
  still aggregates across tenants and should not be marketed as tenant-specific.
- The API uses a required bearer token by default. This is a private, single-operator control, not
  multi-user accounts or role-based access.
- The repository builds an installable wheel, but no release has been published to PyPI yet.

## Concept

IndexPilot is a **thin control layer on top of Postgres** that recommends indexes and can apply
approved changes using DNA-inspired concepts:

1. **Genome**: A canonical global schema (can be auto-discovered from existing databases or defined via config)
2. **Gene Expression**: Per-tenant activation/deactivation of fields/features
3. **Evolution/Mutations**: Index recommendations based on supplied query patterns, with lineage tracking
4. **Measurement**: Before/after performance comparison to evaluate the approach

IndexPilot uses collected query patterns to produce explainable recommendations. Applying those
recommendations is an explicit operator choice.

## Read-only workload DNA report

The smallest useful IndexPilot workflow does not install metadata tables and cannot apply DDL. It
reads PostgreSQL's aggregate workload statistics, combines equality fields with range/sort fields,
checks existing index prefixes, and writes reviewable candidate mutations:

```bash
# From a source checkout:
python -m pip install -e .

# Supply DB_HOST, DB_PORT, DB_NAME, DB_USER, and DB_PASSWORD for the database to inspect.
indexpilot-dna \
  --min-calls 100 \
  --min-table-rows 10000 \
  --output docs/audit/toolreports/workload_dna.json
```

The command starts an explicitly read-only transaction. Reports contain query fingerprints rather
than raw SQL. A candidate is evidence to investigate, not proof of improvement.

If HypoPG is already installed in the inspected database, IndexPilot can compare the original
DNA candidate with smaller alternatives:

```bash
indexpilot-dna --hypopg
```

This option uses `EXPLAIN` without `ANALYZE`, creates only session-local hypothetical indexes, and
still emits advisory SQL. It never installs HypoPG. Planner cost is not measured latency, so test a
selected index on a production copy before applying it.

## Authenticated API

Install the API extra, set a process-level token, and run on loopback:

```bash
python -m pip install -e ".[api]"
indexpilot-api
```

`INDEXPILOT_API_TOKEN` must be supplied to access API, OpenAPI, or documentation routes. The `/`
liveness route remains public. Non-loopback startup is refused unless auth mode is `required` and a
token is configured. Use HTTPS or a trusted reverse proxy when sending a bearer token over a
network. Authentication can be explicitly disabled for isolated local development with
`INDEXPILOT_API_AUTH_MODE=disabled`; do not use that mode for hosting.

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

The full system can recommend indexes, and can create them only after apply mode is enabled:
- Analyzes query patterns from `query_stats`
- Estimates build cost (proportional to table size)
- Estimates query cost without index (full scan overhead)
- Creates index if: `queries × query_cost > build_cost`

## Academic-Inspired Analysis

IndexPilot uses ideas from **12 papers and algorithms** to score or explain recommendations:
- **QPG** (Query Plan Guidance) - arXiv:2312.17510
- **CERT** (Cardinality Estimation Restriction Testing) - arXiv:2306.00355
- **Cortex** (Data Correlation Exploitation) - arXiv:2012.06683
- **Predictive Indexing** - arXiv:1901.07064
- **XGBoost Classifier** - arXiv:1603.02754
- **PGM-Index** - arXiv:1910.06169
- **ALEX** (Adaptive Learned Index) - arXiv:1905.08898
- **RadixStringSpline** - arXiv:2111.14905
- **Fractal Tree**, **iDistance**, **Bx-tree**, **Constraint Optimizer**

Most of these modules are suitability analyses that map research ideas onto PostgreSQL-supported
indexes; they are not native implementations of learned index structures such as ALEX or PGM.
See `docs/THIRD_PARTY_ATTRIBUTIONS.md` for attributions and licensing information.

---

## Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Make (or use commands directly)
- Node.js 20.9+ and pnpm 10+ (dashboard only)

### Installation

#### For Using IndexPilot in Your Own Project

Build and install the package from a tagged checkout or wheel. IndexPilot has not been published to
PyPI yet, so `pip install indexpilot` is not advertised as a working public command.

```bash
git clone https://github.com/eyeinthesky6/indexpilot
cd indexpilot
python -m pip install .

# Include the API server only when needed
python -m pip install ".[api]"
```

The older copy-over guides remain for historical integrations, but copying `src/` is no longer the
recommended installation path.

#### For Development/Testing (IndexPilot Repository)

1. Clone the repository:
```bash
git clone https://github.com/eyeinthesky6/indexpilot
cd indexpilot
```

2. Create and activate a virtual environment (recommended):
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Windows CMD:
venv\Scripts\activate.bat
# On Linux/Mac:
source venv/bin/activate
```

3. Install the package and development dependencies:
```bash
python -m pip install -e ".[dev,api]"
```

4. Initialize the database:
```bash
make init-db
```

This will:
- Start Postgres in Docker
- Create all tables (business + metadata)
- Bootstrap the genome catalog

**For existing databases or multiple databases**, see `docs/installation/FIRST_RUN_SETUP.md`:
```bash
# Assess your setup (especially useful if you have multiple databases)
python scripts/assess_setup.py --interactive
```

## Usage

### Use with Your Own Database

IndexPilot works with **any Postgres database**, not just the demo CRM schema.

**Quick Start - Three Options:**

**Option 1: Auto-Discover from Existing Database** (Recommended)
```python
from src.schema import discover_and_bootstrap_schema

# Automatically discover schema from your database and bootstrap genome catalog
result = discover_and_bootstrap_schema()
```

**Option 2: Use Schema Config File**
1. **Copy and edit schema configuration:**
   ```bash
   cp schema_config.yaml.example schema_config.yaml
   # Edit schema_config.yaml to match your tables and columns
   ```

2. **Point to your database via environment variable:**
   ```bash
   export INDEXPILOT_DATABASE_URL=postgres://user:password@host:port/dbname
   ```

3. **Initialize metadata tables (does NOT touch your schema):**
   ```bash
   # Option 1: Using schema config (recommended)
   python -c "from src.schema.loader import load_schema; from src.schema import init_schema_from_config; from src.genome import bootstrap_genome_catalog_from_schema; config = load_schema('schema_config.yaml'); init_schema_from_config(config); bootstrap_genome_catalog_from_schema(config)"
   
   # Option 2: Manual initialization (if you prefer code-based setup)
   python -c "from src.schema import init_schema; from src.genome import bootstrap_genome_catalog; init_schema(); bootstrap_genome_catalog()"
   ```

4. **Run in advisory mode (no DDL, safe for production):**
   ```bash
   # Advisory mode is the default - it analyzes and logs candidate indexes without creating them
   # Check mutation_log table for candidate indexes
   python -c "from src.auto_indexer import analyze_and_create_indexes; analyze_and_create_indexes()"
   ```

5. **Review candidate indexes:**
   ```sql
   SELECT * FROM mutation_log WHERE mutation_type = 'CREATE_INDEX' AND details_json->>'mode' = 'advisory';
   ```

6. **To actually create indexes (after review), set mode to 'apply':**
   ```bash
   # Edit indexpilot_config.yaml and set:
   # features.auto_indexer.mode: "apply"
   # Or use environment variable:
   export INDEXPILOT_AUTO_INDEXER_MODE=apply
   ```

**Note:** The system does not auto-discover arbitrary schemas. You declare what to watch via `schema_config.yaml`. This gives you full control over which tables and columns are monitored.

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
2. Analyzes patterns and **logs candidate indexes** (advisory mode by default)
3. If mode is set to `apply`, actually creates indexes
4. Runs queries again with indexes in place (if created)
5. Saves results to `docs/audit/toolreports/results_with_auto_index.json`

**Note**: By default, IndexPilot runs in **advisory mode** - it analyzes and logs candidate indexes to `mutation_log` without creating them. This is safe for production. Set `features.auto_indexer.mode: apply` in `indexpilot_config.yaml` to enable automatic index creation.

### Generate Report

Compare baseline vs auto-index results:

```bash
make report
```

This generates:
- Performance comparison report (`docs/audit/toolreports/scaled_analysis_report.json`)
- Case study (`docs/case_studies/CASE_STUDY_*.md`)
- Automatic history tracking (`docs/audit/benchmark_history.csv` and `docs/audit/BENCHMARK_DASHBOARD.md`)

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
- See `docs/features/PRACTICAL_GUIDE.md` for detailed use cases and improvement ideas

## Production Deployment

See `docs/reviews/2026-07-13_open_source_launch_architectural_review.md` for the current evidence,
risks, and deferred upgrade plan.

**Current status**: suitable for local evaluation and controlled advisory trials. Bearer-token API
authentication and optional HypoPG planner validation now exist. Before multi-user or public hosting,
replace the single-operator token with host-owned OIDC/RBAC and run deployment tests against a safe
production copy. Keep apply mode behind operator approval.

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

**Full Documentation**: See `docs/installation/ADAPTERS_USAGE_GUIDE.md` for complete integration guide.

**Why This Matters**: Internal monitoring is in-memory and loses alerts on restart. Host monitoring ensures alerts are persisted and visible in your existing monitoring dashboards.

## Why Use This When Advanced Tools Exist?

For pure index selection, mature tools are ahead. Use Dexter or pganalyze when you primarily want
the strongest PostgreSQL index adviser. IndexPilot is useful only when its application-facing
evidence shape is the feature you need.

### Dexter
- **Stronger at**: Parsing real PostgreSQL SQL and using HypoPG to test candidates from query
  statistics, logs, live activity, or SQL files.
- **IndexPilot difference**: A small JSON report that separates observed workload DNA, planner
  evidence, and review-only mutation SQL for an application to consume.
- **Trial result**: On the ProfitPilot sample, Dexter preferred `(timestamp)` where IndexPilot's
  first heuristic proposed wider composites. That finding caused the optional HypoPG upgrade.

### pg_index_pilot (PostgresAI)
- **Stronger at today**: Automated reindexing and bloat-oriented lifecycle work inside Postgres.
- **Different scope**: Its missing-index creation and optimization work is still described as a
  roadmap area, while IndexPilot's preview focuses on advisory workload expression.

### pganalyze Index Advisor
- **Stronger at**: Workload-wide costing, hypothetical alternatives, write overhead, and constraint
  programming.
- **IndexPilot difference**: Open-source local code and a report contract you can adapt without
  sending schema and query statistics to a hosted product.

### IndexPilot's Focus

IndexPilot's defensible preview niche is a local, application-embeddable evidence layer that needs:

1. **Workload DNA**: which equality, range, and ordering fields appear together
2. **Planner evidence**: which small index shape PostgreSQL would actually choose
3. **Mutation lineage**: why review-only SQL was proposed and which query fingerprints support it
4. **Local integration**: JSON output and adapters for host-owned approval and monitoring

The workload-DNA path proves a tenant-keyed *shared physical index* only when `tenant_id` is an
equality predicate in the parsed query. Tenant metadata alone is not evidence, and the older
field-stat auto-indexer still aggregates across tenants. IndexPilot does not yet justify one
physical index per tenant. See `docs/reviews/2026-07-14_launch_readiness_upgrade_review.md` for the
measured boundary.

## Enhancement Roadmap

See `ENHANCEMENT_ROADMAP.md` for detailed plans to:
- Make the system work better for small databases (< 10k rows)
- Add support for MySQL, SQL Server, and other databases
- Implement predictive indexing and ML-based optimization
- Add real-time monitoring and A/B testing

## License

MIT — see [LICENSE](./LICENSE).

