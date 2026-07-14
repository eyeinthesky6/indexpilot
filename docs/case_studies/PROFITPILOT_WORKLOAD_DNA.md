# ProfitPilot workload DNA: a real advisory trial

Date: 2026-07-13
Status: read-only local evidence; no index was applied

## The simple result

IndexPilot found 11 review candidates in a real ProfitPilot workload after discarding 68 patterns
on small tables. The strongest candidate was:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_action_audit_action_type_timestamp_dna"
ON "public"."action_audit" ("action_type", "timestamp");
```

A smaller but clear market-data candidate was:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_tick_data_symbol_timestamp_dna"
ON "public"."tick_data" ("symbol", "timestamp");
```

These were the first heuristic candidates, not completed optimizations. A follow-up HypoPG and
Dexter trial showed why planner comparison is required: Dexter preferred smaller `(timestamp)`
indexes, and HypoPG found that the lower-cost shape changed with selectivity and parameter mode.
See `PROFITPILOT_HYPOPG_DEXTER_COMPARISON.md`.

## Evidence used

The trial inspected ProfitPilot's production-local PostgreSQL 17 database in an explicitly
read-only transaction. No raw rows, tokens, user details, or raw query text were copied into the
report.

- 114 public tables
- 480 public indexes using about 147 MB
- `action_audit`: about 637,345 rows and 558 MB total size
- 193 calls filtered `action_audit` by `action_type`, ranged and sorted by `timestamp`
- Those calls used about 68.85 seconds in total, with a mean near 356.7 ms
- A representative current-plan check showed a parallel sequential scan followed by a sort
- `tick_data`: about 21,010 rows and 3.5 MB total size
- `tick_data`: 5,639 sequential scans and no recorded index scans
- 4,960 recorded calls filtered by `symbol`, ranged and sorted by `timestamp`
- Those calls used about 3.85 seconds in total, with a mean near 0.776 ms
- Existing `tick_data` indexes covered `id`, `broker`, `created_at`, `exchange`, and `trade_id`
- No existing index started with `(symbol, timestamp)`

The tick query is already fast because that table is still small. Its candidate matters mainly as a
growth warning. The audit query is the more important finding because its table and measured time
are already material.

## Why this adds value

ProfitPilot already has its own database optimizer. Its current missing-index path checks tables
with many sequential scans, then proposes an index on `id`. That is too generic here because these
tables already have primary-key indexes. The workload DNA path instead uses the fields that the real
query filters and sorts.

This supports a narrow product claim:

> IndexPilot can turn PostgreSQL workload expression into explainable, advisory index mutations.

It does not support a claim that IndexPilot is a production autonomous index manager or that it is
better than mature tools such as Dexter, pganalyze, or PostgreSQL.ai Index Pilot.

## What the trial deliberately did not do

- It did not create or drop an index.
- It did not change ProfitPilot code, migrations, environment files, or data.
- It did not claim a speedup without a before/after plan.
- It skipped noisy recommendations for tiny tables even when they had many sequential scans.

## Follow-up status

Completed after this first scan:

1. Optional HypoPG-backed planner comparison behind `--hypopg`.
2. A bounded direct trial against Dexter on the same ProfitPilot field distributions.
3. Corrected positioning: Dexter/pganalyze are stronger index selectors; IndexPilot is an evidence
   and lineage layer.

Still deferred:

1. A proper PostgreSQL SQL parser for joins, expressions, partial indexes, and complex CTEs.
2. Tenant-specific decisions in the full auto-indexer.
3. Packaging, API authentication, and production deployment evidence.
4. Actual before/after latency and write-overhead benchmarks on a production copy.
