# Using IndexPilot

The public commands stay advisory. They read workload/catalog evidence, write portable reports, and
never apply physical index DDL.

## Check readiness first

```bash
indexpilot doctor --schema public --min-calls 10
```

The doctor checks the read-only transaction, PostgreSQL version, `pg_stat_statements`, visible
catalog rows, representative workload, and optional HypoPG support. It writes JSON and Markdown and
returns 1 only when required evidence is not ready.

## Review an exact proposed index

```bash
indexpilot review \
  --candidate-sql 'CREATE INDEX ON public.orders (tenant_id, created_at)' \
  --hypopg
```

You can keep the statement in a file instead:

```bash
indexpilot review --candidate-file proposed-index.sql --hypopg
```

The candidate file must contain exactly one supported statement.

IndexPilot parses the SQL locally, normalizes its identifiers, verifies that the table and columns
exist, and rebuilds the HypoPG statement from those identifiers. It never sends the supplied string
to PostgreSQL and never executes physical DDL.

## Review a migration file

```bash
indexpilot review \
  --migration-file migrations/20260714_add_indexes.sql \
  --hypopg \
  --output artifacts/index-review.json \
  --markdown-output artifacts/index-review.md \
  --sarif-output artifacts/index-review.sarif
```

IndexPilot parses all statements and reviews every supported `CREATE INDEX`. Non-index statements
are counted and ignored. If any `CREATE INDEX` uses an unsupported physical shape, parsing stops
with the exact statement number instead of silently approximating it. Proposals in the same schema
share one catalog/workload snapshot, while every proposed index gets its own verdict.

The combined report also flags schema-wide duplicate index names, exact duplicate shapes, and
leading-prefix overlap inside the migration. Those findings match the `existing_overlap` CI gate
and appear in SARIF. They mean “manual review,” never “safe to drop.”

## Discover candidates from the workload

```bash
indexpilot review \
  --schema public \
  --min-calls 100 \
  --min-table-rows 10000 \
  --limit 200 \
  --hypopg
```

Discovery looks for repeated equality predicates combined with range or ordering columns. It checks
whether a comparable existing B-tree already has the same leading prefix. With HypoPG, it may find
that a smaller alternative has better planner evidence than the initial composite shape.

## Outputs

Defaults:

```text
./indexpilot-review.json
./indexpilot-review.md
```

Choose other paths:

```bash
indexpilot review \
  --output artifacts/index-review.json \
  --markdown-output artifacts/index-review.md
```

Add `--stdout` to print the Markdown report after the terminal summary. Files are still written so
the evidence can be reviewed or attached to a pull request.

Add `--sarif-output path.sarif` for SARIF 2.1.0. SARIF messages contain normalized object names,
columns, verdicts, and statement numbers, but no raw workload SQL.

The report includes:

- source database version and the `pg_stat_statements` reset time
- thresholds and workload row counts
- query fingerprints, never raw workload SQL
- table size and scan counters
- relevant existing index metadata
- sanitized candidate SQL
- baseline and hypothetical planner-cost evidence when available
- the existing auto-indexer’s advisory threshold decision
- explicit limitations and next steps
- database and workload-statistics reset times so later observations can reject mismatched windows

## Audit existing index overlap

```bash
indexpilot audit \
  --schema public \
  --output artifacts/index-audit.json \
  --markdown-output artifacts/index-audit.md
```

This compares valid, ready, ordinary B-trees with default operator classes, collations, and sort
order. It distinguishes exact shapes from leading-prefix overlap and includes constraint ownership,
size, and cumulative scan counters. Partial, expression, invalid, building, non-B-tree, and custom
physical shapes are skipped. No drop SQL is generated.

## Observe post-deploy usage

After an operator deploys an index outside IndexPilot, capture the same exact review again:

```bash
indexpilot compare before.json after.json \
  --output index-observation.json \
  --markdown-output index-observation.md
```

The command runs offline. It requires the same proposal and source database and chronological
reports. It reports `usage_observed`, `no_usage_observed`, or `inconclusive`; workload and table
activity deltas are included only when their reset epochs match and counters do not regress. A scan
proves use, not lower latency. Zero scans do not prove safe deletion.

## Verdicts

### `worth_benchmarking`

HypoPG completed, the exact candidate was used by the representative plan, and its planner-cost
reduction passed the existing advisory threshold (20% by default).

This does not prove lower latency. Benchmark the candidate on a production copy and include write
overhead, index size, warm/cold cache behavior, latency distribution, and rollback.

### `existing_overlap`

A valid, ready, ordinary non-partial B-tree already has the same leading-column prefix and uses the
columns' default operator classes and collations in ascending order. Expression, partial, invalid,
not-ready, custom-opclass, custom-collation, descending, GIN, GiST, and BRIN indexes do not count as
equivalent coverage.

### `not_supported_by_current_planner_evidence`

HypoPG completed, but the exact candidate was unused or below the configured threshold. This is not
the same as “harmful”; it only says the current evidence does not justify benchmarking priority.

### `inconclusive`

The workload was empty, no observed query used the proposed leading key, HypoPG was missing,
PostgreSQL was too old for the generic-plan path, or `EXPLAIN` could not complete.

## Supported proposal syntax

Accepted:

```sql
CREATE INDEX idx_orders_tenant_created
ON public.orders (tenant_id, created_at);
```

Also accepted: optional `CONCURRENTLY`, `IF NOT EXISTS`, an omitted index name, and an unqualified
table that uses `--schema` as its default.

Rejected in this preview:

- `UNIQUE`
- partial `WHERE` clauses
- expression keys
- `INCLUDE`
- descending or mixed ordering
- GIN, GiST, BRIN, operator classes, storage parameters, and tablespaces
- quoted mixed-case identifiers
- multiple statements

Rejecting these shapes is intentional. The current hypothetical builder cannot preserve all their
physical meaning, so pretending to review them would be misleading.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | The evidence report completed, including an inconclusive verdict |
| `1` | Connection, extension, file, or runtime failure prevented a report |
| `2` | Command syntax or proposed index input is unsupported |
| `3` | The report was written, but an opt-in `--fail-on` verdict gate matched |

Verdict gating is opt-in and repeatable:

```bash
indexpilot review \
  --migration-file migration.sql \
  --fail-on inconclusive \
  --fail-on existing_overlap
```

See [the trusted GitHub workflow recipe](GITHUB_ACTIONS.md). Do not expose a production database
secret to untrusted fork pull requests.

## Compatibility commands

`indexpilot dna` and `indexpilot-dna` remain as aliases for the older JSON workload-DNA report:

```bash
indexpilot dna --hypopg --output workload-dna.json
```

The experimental authenticated API remains available through `indexpilot api` or `indexpilot-api`,
but it is not required for CLI review.

Legacy cleanup, automatic REINDEX, inferred bloat percentage, and estimated per-index write cost
are not public recommendation features. Cleanup/reindex mutation entry points are disabled;
inventory reports use `not_measured` when PostgreSQL evidence cannot support the claim.

## Privacy boundary

Raw SQL is held in memory only long enough to parse or run read-only `EXPLAIN`. JSON and Markdown
reports contain short canonical fingerprints instead. Review generated artifacts before sharing
them because schema, table, column, index, database, and workload-volume metadata can still be
sensitive.
