# Trusted CI and GitHub pull requests

IndexPilot can review index migrations in CI, but the current release reads a live PostgreSQL
workload. Run it only in a trusted branch or protected environment whose database credentials are
not available to untrusted fork code.

## Safe first workflow

The bundled composite Action keeps installation and artifact names consistent. Pin it to the
versioned `v1` ref or a full commit SHA before using it in a real repository.

```yaml
name: index migration review

on:
  workflow_dispatch:
  push:
    branches: [main]
    paths:
      - "migrations/**.sql"

permissions:
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    environment: indexpilot-readonly
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Check workload evidence
        env:
          DB_HOST: ${{ secrets.INDEXPILOT_DB_HOST }}
          DB_PORT: ${{ secrets.INDEXPILOT_DB_PORT }}
          DB_NAME: ${{ secrets.INDEXPILOT_DB_NAME }}
          DB_USER: ${{ secrets.INDEXPILOT_DB_USER }}
          DB_PASSWORD: ${{ secrets.INDEXPILOT_DB_PASSWORD }}
          DB_SSLMODE: require
        run: indexpilot doctor --min-calls 10

      - name: Review the trusted migration
        uses: eyeinthesky6/indexpilot@v1
        with:
          migration-file: migrations/20260714_add_indexes.sql
          schema: public
          hypopg: true
          fail-on: inconclusive,existing_overlap
        env:
          DB_HOST: ${{ secrets.INDEXPILOT_DB_HOST }}
          DB_PORT: ${{ secrets.INDEXPILOT_DB_PORT }}
          DB_NAME: ${{ secrets.INDEXPILOT_DB_NAME }}
          DB_USER: ${{ secrets.INDEXPILOT_DB_USER }}
          DB_PASSWORD: ${{ secrets.INDEXPILOT_DB_PASSWORD }}
          DB_SSLMODE: require
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: indexpilot-review
          path: indexpilot-review.*
```

Use a database role limited to catalog/statistics reads and the `SELECT` privileges needed for
optional `EXPLAIN`. The role does not need `CREATE`, table writes, or ownership.

## Why ordinary fork pull requests are excluded

A public `pull_request` workflow executes code from contributors. Giving that job production or
staging database secrets would let untrusted code read those secrets and database metadata. Do not
work around this with `pull_request_target`; that event has a different trust model and is easy to
misconfigure when checking out contributor code.

For now, use one of these patterns:

- run on a protected branch after human review;
- use `workflow_dispatch` against a reviewed commit;
- run locally and attach the Markdown/JSON artifacts to the pull request;
- run against a throwaway sanitized database that contains no sensitive workload or credentials.

The bundled Action is not fork-safe when connected to a private workload database. A fork-safe mode
remains deferred until IndexPilot supports a versioned, sanitized offline workload snapshot. SARIF
output today is suitable for artifacts; uploading it to GitHub Code Scanning should be a separate,
least-privilege decision for trusted events.

## Exit behavior

- `0`: report completed and no configured verdict gate matched;
- `1`: database, file, extension, or runtime failure;
- `2`: unsupported command or index SQL;
- `3`: reports were written, but a repeated `--fail-on` verdict matched.

Keep gating opt-in. An `inconclusive` report is valid evidence output, not automatically a broken
tool run.
