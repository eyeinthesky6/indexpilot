# Your database has DNA. Its workload decides what gets expressed.

Suggested channels: project blog, Dev.to, Hashnode
Status: draft

A database schema tells us what a system *can* store. It does not tell us how the system is actually
used.

Two applications can have the same `orders` table and need different indexes. One may usually look
up an order by its external ID. Another may show each customer's newest orders. The schema is the
same, but the workload is different.

That is the idea behind IndexPilot's DNA language:

- The **genome** is the schema: tables and fields that exist.
- **Expression** is the workload: the fields that real queries filter, join, and sort.
- A **mutation** is a proposed index change.
- **Selection** is the evidence step: keep only changes that prove useful.

The metaphor is not the product by itself. The useful part is the audit trail it encourages. A
recommendation should say which fields were active, how often the pattern ran, which indexes already
exist, and what change is being proposed.

The first open-source workflow is intentionally small. It reads PostgreSQL's
`pg_stat_statements`, looks for repeated equality-plus-range or equality-plus-sort patterns, checks
whether an existing index already has the same leading fields, and writes an advisory report. It
does not apply the index.

For example, a repeated query shaped like this:

```sql
SELECT timestamp, price
FROM tick_data
WHERE symbol = $1 AND timestamp >= $2
ORDER BY timestamp;
```

may express the field sequence `(symbol, timestamp)`. If the table is large enough and no existing
index starts with those fields, IndexPilot records a candidate mutation for review.

This is deliberately less dramatic than “AI manages your database.” It is also more honest. Index
design depends on table size, write volume, selectivity, query plans, and operational constraints.
A parser can find an opportunity; only plan validation and measurement can prove it.

The long-term idea is a database control layer that remembers why every index exists and whose
workload caused it to be considered. The current release is the first narrow slice: read the
workload, explain the candidate, change nothing automatically.
