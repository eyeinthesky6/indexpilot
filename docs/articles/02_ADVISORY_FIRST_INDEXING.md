# Automatic indexing should begin with “do nothing”

Suggested channels: project blog, Medium, LinkedIn article
Status: draft

Creating a PostgreSQL index sounds safe. It is not free.

An index consumes storage, adds work to inserts and updates, can compete for I/O while it builds,
and may never help the query that inspired it. Dropping an index automatically can be worse because
the next important workload may depend on it.

That is why IndexPilot's open-source default is advisory mode.

The read-only workload DNA command performs four steps:

1. Read aggregate query statistics from `pg_stat_statements`.
2. Find repeated filter-plus-range or filter-plus-sort field sequences.
3. Check whether an existing index already has those fields as its leading prefix.
4. Write reviewable SQL text and evidence without executing DDL.

The report also skips small tables by default. A table with ten rows may be scanned thousands of
times and still not need another index. PostgreSQL can read those ten rows cheaply, while an extra
index adds write and maintenance cost.

Even a plausible candidate is not proof. A safe review should ask:

- Does `EXPLAIN` show the expected scan and filter?
- Is the table large or growing?
- Does a hypothetical index improve the plan in HypoPG?
- Is an equivalent or wider index already present?
- Is the table write-heavy?
- Can the build run concurrently within the operating window?

Tools such as Dexter already combine real workloads with HypoPG, and mature commercial products go
much further. IndexPilot's near-term distinction is not “a smarter index oracle.” It is an
embeddable, lineage-first experiment: connect workload expression to a proposed mutation and retain
the reason.

The safest first action for an automatic indexing tool is no action. Observe, explain, validate,
then let an operator decide.
