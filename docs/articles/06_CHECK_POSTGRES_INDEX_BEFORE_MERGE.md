# Before you merge `CREATE INDEX`, check whether PostgreSQL already has it

An index migration is one of the easiest pull requests to approve too quickly.

The statement is short. The intent is usually sensible. A query was slow, somebody added an index,
and the test suite stayed green.

The cost arrives later. Every unnecessary index takes disk space and adds work to inserts, updates,
vacuum, backups, cache management, and future schema maintenance. If an existing index already
covers the same leading columns, the new one may add cost without adding a useful access path.

The useful time to catch that is not during a quarterly index cleanup. It is while the migration is
still a pull request.

## Exact duplicates are the easy case

Assume a database already contains:

```sql
CREATE INDEX orders_customer_created_idx
ON public.orders (customer_id, created_at);
```

A new migration proposes the same columns under another name:

```sql
CREATE INDEX orders_customer_history_idx
ON public.orders (customer_id, created_at);
```

The names differ, but the access path does not. PostgreSQL still has to maintain both physical
indexes.

Catalog queries can find exact duplicates after they exist. The more interesting review question is
whether the proposed index duplicates an existing shape before the migration runs.

## Leading-prefix overlap is less obvious

Now suppose the database already contains:

```sql
CREATE INDEX orders_customer_created_idx
ON public.orders (customer_id, created_at);
```

The pull request adds:

```sql
CREATE INDEX orders_customer_idx
ON public.orders (customer_id);
```

For a normal B-tree, the existing composite index can support lookups using its leading
`customer_id` column. That does not prove the smaller index is useless. A smaller index can have
different cache and scan characteristics. It does mean the pull request needs evidence stronger
than “this query filters by customer_id.”

The reverse is different. An index on `(customer_id)` does not cover a query that needs the ordered
pair `(customer_id, created_at)` in the same way. Column order matters.

Partial indexes, expressions, operator classes, sort direction, uniqueness, and included columns
make the comparison more complicated. A reviewer should not flatten those differences into a
simple list of column names.

## Check the proposal, not only the current database

There are three separate questions:

1. Does the proposed index overlap an index that already exists?
2. Do the queries the database actually runs support the proposed leading key?
3. Would PostgreSQL select the exact proposed shape in a hypothetical plan?

Most index-maintenance scripts answer the first question after deployment. HypoPG can help with the
third question for a query you supply. Neither automatically connects the exact migration in a pull
request to aggregate workload evidence.

That gap is why I built IndexPilot as a read-only review tool.

```bash
pipx install indexpilot

indexpilot review \
  --migration-file migrations/20260715_add_orders_index.sql \
  --hypopg \
  --markdown-output indexpilot-review.md \
  --sarif-output indexpilot-review.sarif \
  --fail-on existing_overlap
```

IndexPilot parses each supported `CREATE INDEX`, reads visible PostgreSQL catalog information,
matches the leading shape against aggregate `pg_stat_statements` patterns, and can ask HypoPG
whether the planner selects the hypothetical index. It does not execute the migration or create a
physical index.

An overlap produces the verdict `existing_overlap`. That verdict means “inspect these two shapes.”
It does not mean “drop the old index” or “reject the new index without discussion.”

## Why workload evidence matters

A structurally unique index can still be weakly justified.

Imagine a migration proposes:

```sql
CREATE INDEX orders_status_idx ON public.orders (status);
```

If almost every row has one of two status values, PostgreSQL may prefer a sequential scan. If the
table is small, reading it directly may be cheaper than visiting both an index and the heap. If the
important query also filters and orders by other columns, `(status)` may be the wrong shape.

This is why representative data and current statistics matter. PostgreSQL's planner makes decisions
from table statistics and cost estimates. A plausible index definition is not proof that the live
workload needs it.

IndexPilot's strongest positive verdict is deliberately named `worth_benchmarking`. It is not
`safe_to_ship`.

A planner estimate cannot measure real latency, write amplification, index build time, deployed
size, cache effects, or rollback behavior. Those still need a controlled benchmark on a
production-like copy.

## Put the check in a trusted CI path

The repository includes a composite GitHub Action:

```yaml
- uses: eyeinthesky6/indexpilot@v1
  with:
    migration-file: migrations/add_orders_index.sql
    hypopg: true
    fail-on: existing_overlap,inconclusive
```

Do not give an untrusted fork pull request credentials for a production or staging database. Run
the check on a protected branch, against a reviewed commit, or with a sanitized disposable
database. Database review does not justify weakening normal secret boundaries.

The generated Markdown gives a reviewer a portable explanation. SARIF can locate the finding beside
the migration. JSON keeps the evidence available for later comparison.

## A practical review rule

When a pull request adds an index, ask for four things:

1. The query shape that needs it.
2. Evidence that the shape occurs in a representative workload.
3. A comparison with existing leading-prefix indexes.
4. A production-like benchmark before the final rollout decision.

If the author cannot provide the first two, the index is a guess. If an existing index covers the
same leading shape, the proposal needs a clear reason to coexist. If HypoPG does not select it, the
planner evidence is weak. None of those observations replaces benchmarking, but they stop weak
proposals from becoming permanent database baggage by default.

The focused guide is available at
[Does this migration add a duplicate PostgreSQL index?](https://eyeinthesky6.github.io/indexpilot/use-cases/duplicate-postgres-index/).
The source, limits, and install instructions are in the
[IndexPilot repository](https://github.com/eyeinthesky6/indexpilot).
