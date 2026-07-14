# ProfitPilot comparison: IndexPilot, HypoPG, and Dexter

Date: 2026-07-13
Status: offline advisory trial; no ProfitPilot index or extension was created

## Bottom line

IndexPilot found a real workload problem, but its first composite-index rule was too confident.
Dexter and direct HypoPG testing showed that a smaller `(timestamp)` index can be cheaper than the
suggested equality-first composite. The useful product is therefore not a new automatic indexer. It
is a small **database DNA evidence layer** that uses mature PostgreSQL tooling for planner truth.

For teams that only want the best index recommendation, use Dexter or pganalyze. Use IndexPilot when
you want local JSON evidence, query fingerprints instead of raw SQL, review-only mutation SQL, and
an application-owned approval/audit flow.

## Trial boundary

- Source: ProfitPilot production-local PostgreSQL 17.6
- Workload evidence: 187 `pg_stat_statements` rows and 11 heuristic candidates
- Trial copy: 637,117 `action_audit` `(action_type, timestamp)` pairs and 21,037 `tick_data`
  `(symbol, timestamp)` pairs
- Sensitive columns were not copied
- HypoPG 1.4.1 was installed only in a temporary `indexpilot_trial` database
- Dexter 0.6.3 ran in its official Docker image with no `--create` flag
- The original ProfitPilot database received no extension, index, schema, environment, or data
  change

## What the tools found

| Query shape | IndexPilot first heuristic | Dexter | HypoPG comparison |
| --- | --- | --- | --- |
| `action_audit`: equality on action type, timestamp range/order, limit | `(action_type, timestamp)` | `(timestamp)` | `(timestamp)` had lower cost than the composite |
| `tick_data`: equality on symbol, timestamp range/order, limit | `(symbol, timestamp)` | `(timestamp)` | The winner changed between generic and representative-value plans |

The second row is important. Parameter values and selectivity can change which index is best. A
regex rule cannot settle that safely.

## Measured planner evidence

These numbers are PostgreSQL planner cost units, not milliseconds or promised speedups.

### Generic parameterized plan

| Table | No new index | `(timestamp)` | Equality + timestamp |
| --- | ---: | ---: | ---: |
| `action_audit` | 9,391.92 | 898.48 | 1,088.97 |
| `tick_data` | 466.38 | 29.40 | 45.46 |

### Representative common value with a 30-day range and limit 100

| Table | No new index | `(timestamp)` | Equality + timestamp |
| --- | ---: | ---: | ---: |
| `action_audit` | 17,101.65 | 4.97 | 8.28 |
| `tick_data` | 814.95 | 12.15 | 10.56 |

The original trial copy contains only the selected, non-sensitive columns, so the absolute costs do
not reproduce ProfitPilot's full 558 MB audit table. The ranking is useful evidence, not a
production benchmark.

## Upgrade made from the trial

`python scripts/workload_dna_report.py --hypopg` now:

1. Keeps the heuristic workload-DNA candidates as explainable observations.
2. Tests the composite, its prefixes, and individual equality/range/order columns one at a time.
3. Uses PostgreSQL 16+ generic `EXPLAIN` in a read-only transaction.
4. Emits deduplicated `planner_recommendations` only when a hypothetical index is used and lowers
   planner cost.
5. Stores compact costs, node types, and fingerprints rather than raw SQL or complete plans.
6. Never installs HypoPG and never creates a real index.

## Honest competitor position

- [HypoPG](https://github.com/HypoPG/hypopg) is the planner-proof engine IndexPilot should reuse,
  not rebuild.
- [Dexter](https://github.com/ankane/dexter) remains the better focused CLI for automatic missing
  index selection. It has a real PostgreSQL parser and multiple workload inputs.
- [pganalyze](https://pganalyze.com/docs/indexing-engine) is substantially more advanced for
  workload-wide optimization, write overhead, and constraint-based selection, but it is a hosted
  commercial product rather than an embeddable open-source report layer.
- [PostgreSQL.ai pg_index_pilot](https://github.com/postgres-ai/postgresai/tree/main/components/index_pilot)
  currently provides serious reindexing and bloat lifecycle machinery. Its own roadmap describes
  missing-index creation and optimization as future work, so it is adjacent rather than a direct
  replacement for this preview report.

## Ship or stop?

Ship this as an open-source preview if the promise stays narrow:

> Turn PostgreSQL workload expression into privacy-conscious, planner-backed, review-only index
> evidence.

Do not market it as autonomous, smarter than established advisers, or production ready. Packaging,
proper SQL parsing, real before/after benchmarks, and proven tenant-aware decisions remain later
work only if users adopt the evidence/report layer.
