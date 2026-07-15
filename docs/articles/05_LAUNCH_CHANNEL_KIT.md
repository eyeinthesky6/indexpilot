# IndexPilot launch channel kit

These are channel-specific drafts, not one identical announcement pasted everywhere. The evidence
below comes from the sanitized ProfitPilot production-copy benchmark in this repository.

## Show HN

**Title:** Show HN: IndexPilot checks a proposed PostgreSQL index before merge

I built IndexPilot after running into a decision that EXPLAIN alone did not settle: someone had
proposed an index, but did our observed workload give us enough evidence to spend time benchmarking
it?

IndexPilot is a read-only CLI. It parses the exact simple `CREATE INDEX` in a migration, reads
aggregate `pg_stat_statements` and catalog data, checks comparable indexes, and can create a
session-local hypothetical index with HypoPG. It writes JSON, Markdown, and optional SARIF.

The positive verdict is deliberately `worth_benchmarking`. It does not execute the migration,
claim planner cost is latency, or tell you an index is safe to drop.

In a controlled copy of a 645,358-row audit table, the plausible composite index and a smaller
timestamp-only alternative both reduced median reads from 49.741 ms to roughly 1.1 ms. The smaller
index used 13.9 MiB instead of 26.1 MiB and avoided the composite's measured 19.51% write penalty.
That result is why the tool stops at evidence and asks for a benchmark instead of shipping DDL.

I would value criticism from people who review PostgreSQL migrations: which evidence would you
need before this became useful in a real pull request?

Repository: https://github.com/eyeinthesky6/indexpilot

## r/PostgreSQL

**Title:** I wanted evidence before adding another PostgreSQL index, so I built a read-only migration reviewer

A missing index can be expensive, but every new index also adds write, storage, cache, backup, and
maintenance cost. The awkward review question is whether an exact proposed index deserves a real
benchmark.

I built a small open-source CLI around that decision. It reads aggregate workload evidence from
`pg_stat_statements`, checks existing B-tree prefixes, and optionally asks HypoPG whether PostgreSQL
would select the hypothetical shape. It never applies the migration.

One controlled copy exposed the tradeoff clearly. A composite `(action_type, timestamp)` index
looked reasonable and reduced median reads from 49.741 ms to 1.174 ms. A timestamp-only index
reached 1.105 ms, used about half the space, and did not show the composite's measured 19.51% write
penalty. The first recommendation was plausible, but the smaller index was the better choice for
that workload.

Current limits are intentional: simple non-unique ascending B-trees, one representative query per
candidate, and planner-cost evidence rather than latency proof. The next useful upgrade is broader
fingerprint coverage and production-copy replay evidence.

I am looking for feedback from people who review migrations: is the verdict boundary cautious
enough, and what evidence is still missing?

Source: https://github.com/eyeinthesky6/indexpilot

## DEV / personal blog

Use `04_BUILDING_INDEXPILOT_WITH_EVIDENCE.md` as the canonical long-form article. Add a short
opening field result, keep every limitation, and use the tags `postgres`, `opensource`,
`performance`, and `productivity`.

Suggested title: **Before another PostgreSQL index reaches production, make it prove its case**

## Short X post

A proposed PostgreSQL index should not reach production on instinct alone.

IndexPilot checks the exact migration against observed workload, existing indexes, and optional
HypoPG plans. It returns evidence, not automatic DDL.

Positive verdict: worth benchmarking. Not safe to ship.

https://github.com/eyeinthesky6/indexpilot

## Submission checklist

- Use a current sanitized report, not illustrative numbers.
- Link to the tagged release or `main`, never a temporary branch.
- Stay available for technical questions after posting.
- Do not cross-post identical copy on the same day.
- Record installs, completed reviews, issues, repeat users, and external case studies; stars alone
  are not product proof.
