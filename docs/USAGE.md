# Using IndexPilot

The public command is `indexpilot review`. It always stays advisory and writes machine-readable JSON
plus a human-readable Markdown report.

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

The file must contain exactly one supported statement. This is not a migration-file parser.

IndexPilot parses the SQL locally, normalizes its identifiers, verifies that the table and columns
exist, and rebuilds the HypoPG statement from those identifiers. It never sends the supplied string
to PostgreSQL and never executes physical DDL.

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

This preview does not use verdicts as CI failures.

## Compatibility commands

`indexpilot dna` and `indexpilot-dna` remain as aliases for the older JSON workload-DNA report:

```bash
indexpilot dna --hypopg --output workload-dna.json
```

The experimental authenticated API remains available through `indexpilot api` or `indexpilot-api`,
but it is not required for CLI review.

## Privacy boundary

Raw SQL is held in memory only long enough to parse or run read-only `EXPLAIN`. JSON and Markdown
reports contain short canonical fingerprints instead. Review generated artifacts before sharing
them because schema, table, column, index, database, and workload-volume metadata can still be
sensitive.
