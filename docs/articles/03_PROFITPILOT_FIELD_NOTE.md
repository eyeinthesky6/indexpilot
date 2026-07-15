# Field note: finding useful field sequences in a database with 480 indexes

Suggested channels: project blog, Dev.to, GitHub discussion
Status: draft

We tested IndexPilot against a real local trading-system database instead of another synthetic CRM
benchmark.

The database belonged to ProfitPilot and contained 114 public tables. Its production-local copy had
480 indexes, roughly 637,000 audit rows, roughly 239,000 scheduler execution rows, and about 21,000
market tick rows. This was already a heavily indexed application, so a useful result was not
guaranteed.

The trial was read-only. It inspected aggregate table and query statistics. It did not copy user
records, credentials, tokens, or raw query text, and it did not create an index.

The read-only scan returned 11 review candidates after dropping 68 patterns on tiny tables. The
strongest workload used the large audit table:

```sql
SELECT id, user_id, actor_id, action_type, timestamp, created_at, details
FROM action_audit
WHERE action_type = $1 AND timestamp >= $2
ORDER BY timestamp;
```

PostgreSQL had recorded 193 calls of this shape, using about 68.85 seconds in total. The table held
roughly 637,000 rows. A representative plan check showed a parallel sequential scan and a sort, and
no current index started with `(action_type, timestamp)`.

IndexPilot produced this advisory candidate:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_action_audit_action_type_timestamp_dna"
ON "public"."action_audit" ("action_type", "timestamp");
```

A smaller market-data workload also stood out:

```sql
SELECT timestamp, price, quantity, direction, broker
FROM tick_data
WHERE symbol = $1 AND timestamp >= $2
ORDER BY timestamp;
```

PostgreSQL had recorded 4,960 calls of this shape. The table had 5,639 sequential scans and no
recorded index scans. Its existing indexes covered the primary key, broker, creation time, exchange,
and trade ID, but not the field sequence used by this query.

For that workload IndexPilot produced:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS "idx_tick_data_symbol_timestamp_dna"
ON "public"."tick_data" ("symbol", "timestamp");
```

The important word is *candidate* for both results. The mean tick query time was already below one
millisecond because that table was only about 21,000 rows, so it is an early growth warning rather
than an urgent fix. The audit finding is more pressing, but it still needs HypoPG or a controlled
before/after plan comparison before changing the database.

This trial changed our view of the product. IndexPilot is not ready to claim autonomous database
optimization. Its useful open-source shape is smaller: a workload-DNA report that explains which
field sequence is active, shows why an index might help, checks current coverage, and leaves the
database untouched.

That is enough value for an honest preview. It is a much better foundation than a large feature list
without real workload evidence.
