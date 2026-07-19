# Installing IndexPilot

IndexPilot needs Python 3.10+. The bundled first review runs without a database; a live review or
snapshot refresh needs reachable PostgreSQL. Docker, Node.js, the API, and the dashboard are not
required for normal CLI use.

## Try it before connecting a database

From a clone of the repository, run the published package against the bundled sanitized workload:

```bash
uvx --from "indexpilot==1.1.0a6" indexpilot review --migration-file examples/quickstart/migration.sql --snapshot-file examples/quickstart/workload-snapshot.json --output artifacts/first-review.json --markdown-output artifacts/first-review.md --stdout
```

The command should exit successfully, review one index, and return one `existing_overlap` verdict.
It demonstrates that installation, parsing, offline evidence review, and report generation work. It
does not inspect or optimize your database. Install
[`uv`](https://docs.astral.sh/uv/getting-started/installation/) if `uvx` is unavailable, or install
the CLI with `pipx` below and replace the command prefix with `indexpilot`.

## Recommended: isolated CLI install

Install the current release from PyPI with `pipx`:

```bash
pipx install "indexpilot==1.1.0a6"
indexpilot --version
indexpilot review --help
indexpilot doctor --help
```

Or install directly from the release tag:

```bash
pipx install "git+https://github.com/eyeinthesky6/indexpilot.git@v1.1.0a6"
```

`pipx` keeps the CLI and its dependencies out of your global Python environment. See the
[Python Packaging User Guide](https://packaging.python.org/en/latest/guides/installing-stand-alone-command-line-tools/).

If `pipx` is not installed and your Python installation permits user packages, bootstrap it with:

```bash
python -m pip install --user pipx
python -m pipx ensurepath
```

Open a new terminal after `ensurepath`, then run the install command above. On managed Python
installations, use the platform-specific method in the linked Packaging User Guide.

## Install from a clone

```bash
git clone https://github.com/eyeinthesky6/indexpilot.git
cd indexpilot
python -m venv .venv
python -m pip install .
python -m indexpilot --help
```

For development:

```bash
python -m pip install -e ".[dev,api,ml]"
```

The `api` and `ml` extras are not needed by the core review command.

## Database connection

IndexPilot uses either individual `DB_*` values or `SUPABASE_DB_URL`.

```text
DB_HOST=database.example.com
DB_PORT=5432
DB_NAME=my_app
DB_USER=indexpilot_reader
DB_PASSWORD=replace-me
DB_SSLMODE=require
DB_CONNECT_TIMEOUT=10
```

Do not commit these values. Production and staging mode require an explicit password. SSL defaults
to `prefer` outside those modes, so set `DB_SSLMODE=require` or your organization’s stronger
verification mode for a remote database.

## Enable workload statistics

IndexPilot reads `pg_stat_statements`. PostgreSQL requires the module to be preloaded and the
extension enabled in each database where its views are used.

```conf
# postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
compute_query_id = on
```

Restart PostgreSQL after changing `shared_preload_libraries`, then run as a database owner:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

This follows the official [PostgreSQL `pg_stat_statements`
setup](https://www.postgresql.org/docs/current/pgstatstatements.html). On managed PostgreSQL, use
your provider’s extension and restart controls.

## Use a least-privilege reader

The review command needs to read:

- `pg_stat_statements` and `pg_stat_statements_info`
- `pg_stat_user_tables`
- `information_schema.columns`
- PostgreSQL index catalogs

PostgreSQL normally restricts other users’ query text and query identifiers. A dedicated reader is
commonly granted `pg_read_all_stats`, but verify the exact access policy with your DBA:

```sql
GRANT pg_read_all_stats TO indexpilot_reader;
```

Do not grant `CREATE`, table writes, or ownership merely for IndexPilot’s review command.

## Optional HypoPG validation

Without HypoPG, IndexPilot can discover workload shapes and check existing indexes, but planner
verdicts remain `inconclusive`.

Install HypoPG using your database platform’s supported package, then enable it as a database owner:

```sql
CREATE EXTENSION IF NOT EXISTS hypopg;
```

IndexPilot never runs that command. The current placeholder-safe path requires PostgreSQL 16+ and
uses `EXPLAIN (FORMAT JSON, GENERIC_PLAN TRUE)` without `ANALYZE`. Hypothetical indexes live only in
the review session.

`EXPLAIN` still applies PostgreSQL's normal privilege checks. The review user therefore needs
`SELECT` on each relation referenced by the representative query (and `EXECUTE` on referenced
functions, when applicable). Grant only those privileges needed for the workload you intend to
review; `--hypopg` reports `explain_failed` when they are missing.

## Verify the setup

```bash
indexpilot doctor --schema public --min-calls 1 --limit 10
```

The doctor writes `indexpilot-readiness.json` and `indexpilot-readiness.md`. `ready` means the
catalog/workload prerequisites and HypoPG availability/version checks passed; it does not execute a
hypothetical plan. A real `--hypopg` review can still report `explain_failed` when relation or
function privileges are missing. `ready_without_planner_validation` means catalog/workload review
works without HypoPG. `needs_workload` means the connection works but the selected statistics
window is empty. `not_ready` returns exit code 1.

Then run a small evidence review:

```bash
indexpilot review --min-calls 1 --limit 10
```

An empty workload is reported as missing evidence; it is not proof that no index is needed.

## Common errors

`pg_stat_statements is not enabled`

: Configure `shared_preload_libraries`, restart PostgreSQL, and create the extension in the target
  database.

`permission denied for view pg_stat_statements`

: Ask the DBA for the smallest suitable monitoring role, commonly `pg_read_all_stats`.

`HypoPG validation: unavailable`

: HypoPG is not installed in that database. The basic read-only report still works.

`postgresql_16_required_for_generic_plan`

: Run the basic report without `--hypopg`, or use PostgreSQL 16+ for this preview’s placeholder-safe
  planner comparison.

Connection refused or timeout

: Check the `DB_*` values, network access, TLS mode, and `DB_CONNECT_TIMEOUT` (allowed range: 1–60
  seconds).

## Optional local dashboard and API

The packaged dashboard and API are a separate optional surface. A normal install needs no Node.js
runtime or second development server:

```bash
pipx install "indexpilot[api]==1.1.0a6"
indexpilot dashboard
```

`indexpilot dashboard` selects a free port, binds to `127.0.0.1`, opens the browser, and serves the
bundled UI plus API in one process. It opens without a login or token and cannot be reached from
another machine. Press `Ctrl+C` to stop it. If PostgreSQL is unavailable, the UI shows a clear
disconnected state; use `indexpilot doctor` to verify the read-only database configuration.

For separate or non-loopback API hosting, run `indexpilot api`. Set
`INDEXPILOT_API_AUTH_MODE=required` and `INDEXPILOT_API_TOKEN` first; a non-loopback bind such as
`--host 0.0.0.0` is refused without that explicit authentication. The token is a shared
single-operator control, not hosted multi-user authentication. Keep it private; see
[SECURITY.md](../SECURITY.md).

The compatibility dashboard reports index size, validity, readiness, and cumulative scan counts.
It intentionally reports physical bloat and index-attributable write overhead as `not_measured`;
automatic cleanup and REINDEX are disabled. Use an operator-approved PostgreSQL maintenance
workflow when those measurements are needed.
