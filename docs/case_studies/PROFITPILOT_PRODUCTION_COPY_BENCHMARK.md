# ProfitPilot Production-Copy Index Benchmark

## Safety boundary

ProfitPilot was a read-only source. The benchmark copied only `action_type`, `symbol`, and timestamp
fields into a dedicated IndexPilot database, then added synthetic padding to approximate heap row
width. No ProfitPilot rows, indexes, extensions, code, or environment settings were changed.

The source proof matched before and after: 645,358 `action_audit` rows, 21,037 `tick_data` rows,
zero HypoPG extensions, and zero `_dna` indexes. The throwaway database was deleted after the run.

## Method

- PostgreSQL source: ProfitPilot production-local PostgreSQL 17
- Query measurements: 5 warmups, then 30 timed runs
- Write measurements: seven 1,000-row insert batches, each rolled back
- Rollback: drop each candidate, prove the index is absent, and re-run the query/plan
- Representative values: selected in the clone and redacted from the report

## Results

### `action_audit` — 645,358 rows

Representative filter: action type plus recent timestamp, ordered newest first, limit 100.

| Shape | Median | p95 | Index size | Build | Write change vs no candidate |
|---|---:|---:|---:|---:|---:|
| No candidate | 49.741 ms | 53.953 ms | — | — | baseline |
| `(timestamp)` | 1.105 ms | 2.230 ms | 13.9 MiB | 1,277 ms | -5.25% (measurement noise/no penalty) |
| `(action_type, timestamp)` | 1.174 ms | 1.620 ms | 26.1 MiB | 771 ms | +19.51% |

Both indexes changed the plan from parallel sequential scan + sort to index scan. Timestamp-only is
the better balanced choice here: equal practical read latency, roughly half the storage, and no
measured write penalty. After each drop, the index was absent and the sequential-scan plan returned.

### `tick_data` — 21,037 rows

Representative filter: symbol plus recent timestamp, ordered newest first, limit 100.

| Shape | Median | p95 | Index size | Build | Write change vs no candidate |
|---|---:|---:|---:|---:|---:|
| No candidate | 1.670 ms | 2.165 ms | — | — | baseline |
| `(timestamp)` | 0.801 ms | 1.368 ms | 384 KiB | 13 ms | +12.97% |
| `(symbol, timestamp)` | 0.653 ms | 0.964 ms | 648 KiB | 34 ms | +28.56% |

The composite saved another 0.148 ms over timestamp-only, but almost doubled the observed write
penalty and used more space. On this small table, the decision depends on query frequency and write
rate; timestamp-only is the safer default, and no index is also reasonable if this query is rare.

## What this proves

- The first equality-first DNA heuristic is not automatically the best physical index.
- HypoPG/Dexter's timestamp-only suggestion was correct for the large audit case.
- IndexPilot adds value when it explains workload shape, planner evidence, storage, writes, and
  rollback together; it does not add value by pretending its custom heuristic beats mature tools.

The machine-readable report is generated at
`docs/audit/toolreports/profitpilot_production_copy_benchmark.json` and is intentionally gitignored
because tool reports are runtime artifacts.
