# I built an automatic PostgreSQL indexer. Then a real workload made me cut it down

I started IndexPilot with a DNA metaphor. The schema was the genome, live query patterns were
expression, and an index was a mutation. A short sprint turned that idea into an automatic index
manager with a dashboard, an API, simulations, lifecycle helpers, tenant metadata, and a long list
of algorithms.

*Disclosure: I used an AI assistant to organize source material and edit this draft. The product
idea, code decisions, tests, and opinions are mine.*

The file tree looked ambitious. That was not the same as having a product people should trust with
a database.

## The first version was bigger than the proof

The prototype did contain working pieces. It could read PostgreSQL statistics, identify repeated
field patterns, produce index candidates, and run simulations. It also contained experimental
modules whose names sounded more complete than their runtime evidence.

A file can exist without having a reliable caller. A feature can return a number without measuring
what its label claims. Tenant metadata can be present without proving that the normal decision path
makes a tenant-specific physical index choice.

Those distinctions matter when the output is a database change. PostgreSQL's own documentation
notes that indexes add overhead and should be used sensibly. An unnecessary index keeps charging
for storage, writes, cache, backups, and maintenance long after the pull request that introduced it
has been forgotten.

The early IndexPilot idea jumped too quickly from pattern detection to action. I needed a real
workload to find out whether the recommendation was any good.

## The first recommendation was plausible

I ran a read-only trial against ProfitPilot, another local project. The scan saw 114 tables, 480
indexes, and 187 rows from `pg_stat_statements`. It produced 11 candidates after skipping 68 query
patterns on small tables.

The strongest candidate targeted an audit table. The repeated query shape filtered by action type,
used a timestamp range, sorted newest first, and returned a small result. The first report proposed
the `(action_type, timestamp)` key shape. Stripped of the prototype's generated name and wrapper,
the proposal was:

```sql
CREATE INDEX CONCURRENTLY idx_action_audit_action_type_timestamp
ON public.action_audit (action_type, timestamp);
```

That proposal made sense. Equality columns often belong before range and ordering columns in a
composite B-tree. It matched the observed query shape. It was also not the best overall tradeoff.

[Dexter](https://github.com/ankane/dexter), a mature PostgreSQL indexer, preferred a smaller index
on `timestamp`. Direct [HypoPG](https://github.com/HypoPG/hypopg) comparisons agreed. HypoPG lets
PostgreSQL plan with a hypothetical index that consumes no disk and never becomes a physical
index.

A later controlled copy made the difference concrete. The copy contained selected, non-sensitive
columns from the audit table plus synthetic padding. It was not a full production clone. Five
warmups and 30 timed reads were used for each shape. Insert batches were rolled back. Every
candidate was dropped and its absence was checked after the run.

| Shape | Median read | Index size | Measured write change |
|---|---:|---:|---:|
| No candidate | 49.741 ms | none | baseline |
| `(timestamp)` | 1.105 ms | 13.9 MiB | -5.25%, treated as noise |
| `(action_type, timestamp)` | 1.174 ms | 26.1 MiB | +19.51% |

Both candidates changed the plan from a parallel sequential scan and sort to an index scan. The
timestamp-only index delivered practically the same read result, used about half the space, and did
not show the composite's write penalty.

The first recommendation was not nonsense. That was the problem. It looked reasonable enough to
ship, while a simpler index was the better choice.

No ProfitPilot row, index, extension, schema, code, or environment setting was changed during the
trial. The benchmark numbers describe one controlled reproduction. They are not a general speed
claim for IndexPilot.

## The product was hiding in the review step

Advanced index tools already exist. Dexter finds missing indexes from workload inputs. HypoPG
supplies planner evidence. Commercial systems such as pganalyze go much further with workload-wide
selection and operational context. Migration linters such as
[Squawk](https://github.com/sbdchd/squawk) focus on whether PostgreSQL migrations are safe to run.

Building a smaller copy of those tools was not a useful open-source position.

The code did expose a narrower question that still caused real friction:

> A pull request already contains `CREATE INDEX`. Does this exact proposal have enough workload and
> planner evidence to deserve a proper benchmark?

That is the current IndexPilot product.

It reviews the index in the migration instead of producing a generic list of indexes somebody may
want. It checks whether observed queries use the proposed leading key, whether a comparable index
already exists, and whether an optional hypothetical plan selects the exact shape. The result is a
review artifact that can live beside the pull request.

## What the current release does

For each supported `CREATE INDEX`, IndexPilot now:

1. Parses PostgreSQL syntax locally with [SQLGlot](https://github.com/tobymao/sqlglot).
2. Reads aggregate workload evidence from
   [`pg_stat_statements`](https://www.postgresql.org/docs/current/pgstatstatements.html).
3. Checks valid and ready B-tree indexes for comparable leading prefixes.
4. Optionally asks HypoPG and generic `EXPLAIN` whether PostgreSQL selects the proposed shape.
5. Writes JSON and Markdown evidence, with optional SARIF, without applying the migration.

A review looks like this:

```bash
indexpilot review \
  --migration-file migrations/20260714_add_orders_index.sql \
  --hypopg \
  --output artifacts/indexpilot.json \
  --markdown-output artifacts/indexpilot.md \
  --sarif-output artifacts/indexpilot.sarif
```

The verdicts are intentionally restrained:

- `worth_benchmarking`
- `existing_overlap`
- `not_supported_by_current_planner_evidence`
- `inconclusive`

The positive verdict does not say "ship it." It says the proposal has enough evidence to justify a
real benchmark covering latency, writes, build time, size, cache effects, and rollback.

IndexPilot can also flag two proposals in one migration that share a leading prefix. It records the
finding in SARIF and can fail an opt-in CI gate. It still does not declare either physical index
safe to remove.

## What I removed from the public promise

The repository still contains historical experiments. The public CLI does not pretend they are all
finished product features.

IndexPilot does not create or drop physical indexes in its review path. It does not report a bloat
percentage unless a trusted source measured one. It does not convert index count into a fictional
write-cost number. It does not claim tenant-specific optimization because a tenant field exists in
metadata.

The current parser accepts plain, non-unique, ascending B-tree proposals. Partial indexes,
expressions, `INCLUDE`, unique indexes, descending keys, GIN, GiST, and BRIN remain outside the
supported review contract. HypoPG planning currently uses one representative query per candidate.

That makes the release smaller. It also makes every public claim easier to inspect.

## Why open source it now

The useful next steps need workloads and edge cases that one repository cannot provide. A migration
from another PostgreSQL version may expose a parser boundary. A real query shape may show that the
current evidence is too weak. A contributor may have a better way to package a sanitized offline
workload for fork-safe CI.

Good contributions do not need another scoring algorithm. A failing test with a real index shape,
a clearer evidence field, a safe offline example, or a reproducible compatibility report is more
valuable.

IndexPilot is an alpha. It is not better at index selection than Dexter or pganalyze. Its job is to
make one proposed index explain itself before it becomes permanent database baggage.

The code, current limits, and contribution guide are at
[github.com/eyeinthesky6/indexpilot](https://github.com/eyeinthesky6/indexpilot). The public project
page is [eyeinthesky6.github.io/indexpilot](https://eyeinthesky6.github.io/indexpilot/).

If you have a sanitized migration that the reviewer handles badly, open an issue. That is the kind
of failure this project needs next.
