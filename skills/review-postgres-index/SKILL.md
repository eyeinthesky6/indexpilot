---
name: review-postgres-index
description: Install and set up IndexPilot, run its database-free first review, report whether it works and what value it demonstrated, or review proposed PostgreSQL CREATE INDEX migrations against observed workload, existing indexes, and optional HypoPG plans. Use when deciding whether to add an index, checking a migration for overlapping indexes, testing an index without creating it, adding index review to CI, or validating an agent-generated index before merge.
---

# Review a PostgreSQL index

Use IndexPilot as a read-only evidence gate. Prove the installation with the bundled offline review
before asking the user for database access. Do not present any verdict as production-latency proof.

## First use

1. Locate the IndexPilot repository root and confirm these files exist:
   `examples/quickstart/migration.sql` and `examples/quickstart/workload-snapshot.json`.
2. Reuse an installed `indexpilot` command when its version is current. Otherwise use `uvx` when
   available, then `pipx`. If neither exists, confirm Python 3.10+ and install `pipx` at user scope
   with `python -m pip install --user pipx`; never add IndexPilot to the application's dependency
   file merely to run this check. Do not edit an environment file.
3. Run the database-free first review from the repository root:

   ```bash
   uvx --from "indexpilot==1.1.0a4" indexpilot review --migration-file examples/quickstart/migration.sql --snapshot-file examples/quickstart/workload-snapshot.json --output artifacts/first-review.json --markdown-output artifacts/first-review.md --stdout
   ```

   With `pipx`, replace the prefix through `indexpilot` with
   `python -m pipx run --spec "indexpilot==1.1.0a4" indexpilot`. With an installed command, run the
   same arguments after `indexpilot review`. Never add `--hypopg` to an offline snapshot review.
4. Treat the first review as successful only when the command exits zero and the JSON report shows:
   - `source_mode: sanitized_offline_snapshot`
   - one reviewed index
   - one `existing_overlap` verdict
   - at least one matching workload fingerprint
5. Report the receipt in plain language:
   - installed version and runner used;
   - whether the database-free test passed;
   - the redundant `(tenant_id, created_at)` proposal it caught;
   - JSON and Markdown report paths;
   - that this proves installation and advisory behavior, not value on the user's database.

If installation or the first review fails, report the command, exit code, and first useful error.
Do not call the setup successful and do not hide the failure behind a generic summary.

## Review a real database

1. Confirm the target is PostgreSQL and the proposal is a supported B-tree `CREATE INDEX`.
2. Use only a user-approved, read-only connection. Never print credentials, copy them into a
   report, edit `.env`, or connect to production merely because credentials are present.
3. Check evidence readiness:

   ```bash
   indexpilot doctor --schema public --min-calls 10
   ```

4. Run the first live review without HypoPG:

   ```bash
   indexpilot review --migration-file migration.sql \
     --output indexpilot-review.json \
     --markdown-output indexpilot-review.md \
     --sarif-output indexpilot-review.sarif
   ```

5. Add `--hypopg` only when `doctor` reports compatible PostgreSQL and an installed HypoPG
   extension, and the review role has the required relation privileges.
6. Interpret the result:
   - `worth_benchmarking`: benchmark latency, writes, size, build time, and rollback next.
   - `existing_overlap`: inspect both shapes; never drop automatically.
   - `not_supported_by_current_planner_evidence`: current planner evidence did not support the exact proposal.
   - `inconclusive`: repair workload, permissions, or planner evidence before deciding.

Report live readiness separately from the bundled first test. State the reviewed migration,
verdict counts, evidence source, report paths, and the next safe decision. Never translate a
successful fixture into a claim that the user's database is optimized.

## Add review to GitHub Actions

Use the existing composite Action instead of rebuilding the CLI invocation. For an untrusted pull
request, check the sanitized snapshot out from the trusted base commit and pass it with
`snapshot-file`; never read that evidence from the contributor checkout. Snapshot mode is
database-free and must not enable HypoPG. Omit `snapshot-file` for the protected live path, where
repository secrets and optional HypoPG remain isolated from forked code. Pin the Action to an
immutable reviewed commit until a maintainer separately approves moving the supported major tag.

Do not use IndexPilot as an automatic index creator, drop-index tool, general SQL tuner, or replacement for production-copy benchmarks. It never applies the migration, creates a physical index, runs `EXPLAIN ANALYZE`, or proves an index is safe to ship.

Never expose production or staging credentials to untrusted pull-request code. Run CI review on a protected branch, against a reviewed commit, or with a sanitized disposable database.
