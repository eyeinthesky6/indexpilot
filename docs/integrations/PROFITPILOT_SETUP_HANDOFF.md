# ProfitPilot Advisory Setup Handoff

IndexPilot did not change ProfitPilot. If you want live planner-backed recommendations there, set up
the following in ProfitPilot as a separate, reviewed task.

## Recommended tools

1. Keep `pg_stat_statements` enabled and preserve it across restarts. The previous workload window
   reset after a database restart, so a healthy extension alone is not enough evidence.
2. Install HypoPG in the database only if the production-local Supabase/PostgreSQL image supports
   it. HypoPG uses session-local virtual indexes and `EXPLAIN` without `ANALYZE`.
3. Run Dexter in recommendation mode first. Do not use `--create` until the proposed index has a
   production-copy latency, space, write, and rollback result.
4. Feed IndexPilot's resulting planner recommendations into advisory review; leave ProfitPilot's
   current index creation owner unchanged until the integration contract is reviewed there.

## Suggested order

```text
pg_stat_statements window
  -> Dexter and/or IndexPilot candidate
  -> HypoPG planner evidence
  -> production-copy benchmark
  -> operator approval
  -> ProfitPilot's existing migration/index owner
```

## First candidates from the current evidence

- `action_audit (timestamp)` is the strongest candidate. On the isolated copy it reduced median
  query latency by about 97.8% and was much smaller/cheaper to write than the composite.
- `tick_data (timestamp)` is a conservative candidate, but the table is small and baseline latency
  was already 1.67 ms. Do not create it unless the real query frequency justifies the write cost.

Do not copy IndexPilot's apply mode into ProfitPilot as a second DDL owner. Let ProfitPilot's
existing migration/control path own any approved physical index.
