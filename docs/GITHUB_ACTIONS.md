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

## Fork-safe offline pull-request workflow

A public `pull_request` workflow executes code from contributors. Giving that job production or
staging database secrets would let untrusted code read those secrets and database metadata. Do not
work around this with `pull_request_target`; that event has a different trust model and is easy to
misconfigure when checking out contributor code.

IndexPilot's versioned sanitized snapshot lets the untrusted job run without a database. First,
refresh the snapshot on a trusted machine or protected branch:

```bash
indexpilot snapshot --schema public --output .indexpilot/workload-snapshot.json
```

Review it before committing. It contains no raw workload SQL, credentials, or database identity,
but it still contains object names, aggregate workload counts, sizes, activity, and index shapes.
Treat those fields according to your own disclosure policy.

The pull-request job must read the snapshot from the trusted base commit. Do not use the copy from
the contributor checkout, because the contributor could replace or weaken its evidence.

```yaml
name: fork-safe index migration review

on:
  pull_request:
    paths:
      - "migrations/**.sql"

permissions:
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Check out the proposed migration
        uses: actions/checkout@v7
        with:
          path: change
          persist-credentials: false

      - name: Check out trusted snapshot from the base commit
        uses: actions/checkout@v7
        with:
          ref: ${{ github.event.pull_request.base.sha }}
          path: trusted-base
          persist-credentials: false
          sparse-checkout: .indexpilot/workload-snapshot.json
          sparse-checkout-cone-mode: false

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install a reviewed IndexPilot release
        run: python -m pip install "indexpilot==<reviewed-version-with-snapshot-support>"

      - name: Review with no database or secrets
        run: >-
          indexpilot review
          --migration-file change/migrations/20260714_add_indexes.sql
          --snapshot-file trusted-base/.indexpilot/workload-snapshot.json
          --output indexpilot-review.json
          --markdown-output indexpilot-review.md
          --sarif-output indexpilot-review.sarif
          --fail-on existing_overlap
          --fail-on inconclusive

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: indexpilot-review
          path: indexpilot-review.*
```

Replace the install placeholder with an exact reviewed release. For higher assurance, pin the
installer source and every third-party Action to immutable commit SHAs.

The offline job cannot use HypoPG or refresh evidence. Keep one of these protected patterns when
live planner or newer workload evidence is required:

- run on a protected branch after human review;
- use `workflow_dispatch` against a reviewed commit;
- run locally and attach the Markdown/JSON artifacts to the pull request;
- run against a throwaway sanitized database that contains no sensitive workload or credentials.

The bundled composite Action remains the protected live path. Do not give it private database
credentials on `pull_request`. SARIF output is suitable for artifacts; uploading it to GitHub Code
Scanning should be a separate, least-privilege decision.

## Exit behavior

- `0`: report completed and no configured verdict gate matched;
- `1`: database, file, extension, or runtime failure;
- `2`: unsupported command or index SQL;
- `3`: reports were written, but a repeated `--fail-on` verdict matched.

Keep gating opt-in. An `inconclusive` report is valid evidence output, not automatically a broken
tool run.
