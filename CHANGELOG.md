# Changelog

All notable changes to the focused public package are documented here.

## Unreleased

- Keep public lifecycle API operations advisory by rejecting `dry_run=false` before legacy
  lifecycle helpers can perform database maintenance.
- Run release-surface synchronization in normal CI and include the canonical agent skill,
  structured website metadata, supported Python range, and Action examples.
- Align public Python/PostgreSQL support, virtual-environment commands, and proposed-index wording
  with the implemented review path.

## 1.1.0a8 - 2026-07-20

### Fixed

- The release-surface check now handles JSON-escaped repository links in the generated Next.js
  dashboard without treating the escape character as part of the file path.

### Release process

- `1.1.0a7` remains an immutable GitHub prerelease record, but its protected publication stopped
  before build or upload when the new link check exposed this parser bug. No `1.1.0a7` package was
  published to PyPI.

## 1.1.0a7 - 2026-07-20

### Changed

- The composite GitHub Action now installs IndexPilot from the exact pinned Action ref instead of a
  hardcoded PyPI prerelease, so reviewed tags and commit SHAs keep code and runtime aligned.
- CI now runs the composite Action itself against the sanitized quick-start snapshot and verifies
  the advisory overlap receipt.

### Security

- The trusted PyPI workflow now checks out the exact release tag, rejects a tag/version mismatch,
  and pins every publication Action to a full commit SHA.

### Docs

- The GitHub Actions guide now recommends reviewed release tags, explains when the moving `v1` ref
  should be refreshed, and records the plan to consider optional Marketplace publication after the
  next release is complete.

## 1.1.0a6 - 2026-07-17

### Added

- The CLI now prints one optional post-success invitation to star IndexPilot or share a sanitized
  first-value receipt after the first interactive review.

### Privacy

- The invitation uses only a local one-time marker, makes no network request, collects no telemetry,
  stays out of CI and `--stdout` output, and supports the `INDEXPILOT_NO_COMMUNITY_PROMPT=1` opt-out.

## 1.1.0a5 - 2026-07-16

### Added

- `indexpilot dashboard` serves the bundled operator UI and API in one local process, selects a
  free loopback port, and opens the browser without requiring Node.js at runtime.
- Python wheels and source distributions now include the prebuilt operator dashboard.

### Changed

- The one-command loopback dashboard is passwordless, while explicit bearer-token authentication
  and fail-closed startup remain required for non-loopback API hosting.
- The dashboard shows a clear disconnected-database state while PostgreSQL is being configured,
  without turning expected connection failures into a Next.js development overlay.

## 1.1.0a4 - 2026-07-16

### Added

- `indexpilot snapshot` exports versioned aggregate workload and catalog evidence without raw SQL
  or database identity.
- `indexpilot review --snapshot-file` reviews an exact candidate or migration offline without a
  PostgreSQL connection or database secret.
- A fork-safe CI job proves the sanitized offline path and is required by the protected `main`
  ruleset.
- Problem-led public guides for index justification, planner selection, overlap, hypothetical
  testing, and trusted CI review.
- A standards-compatible agent skill with concrete trigger phrases and safe verdict handling.
- A composite GitHub Action for protected branches, reviewed commits, and sanitized databases.
- Public request, support, first-value receipt, and contributor-role routes through GitHub
  Discussions and issue forms.

### Changed

- The homepage, sitemap, README, and `llms.txt` now connect user-described PostgreSQL index pains
  directly to the supported IndexPilot workflow.
- Contributor role trials now require consent, role-specific evidence, least privilege, human
  approval, and explicit rollback or inactivity conditions.
- Pip Dependabot updates now avoid lower-bound-only changes when the existing range already permits
  the new release.

## 1.1.0a3 - 2026-07-15

### Changed

- Replaced research-style public copy with a direct outcome: stop bad PostgreSQL indexes before
  they reach production.
- Aligned the package summary, README, website metadata, and agent discovery copy around the same
  user-facing promise.

## 1.1.0a2 - 2026-07-15

### Added

- Public launch documentation, agent guidance, GitHub Pages discovery files, and a reusable
  open-source launch playbook.
- PyPI Trusted Publishing support for alpha releases so the public package can be verified before a
  stable release.

### Changed

- Repository positioning, installation guidance, contributor routes, and search metadata now point
  to the same benchmark-before-merge product boundary.

## 1.1.0a1 - 2026-07-14

### Added

- `indexpilot review` as the public read-only command.
- Exact review for one simple proposed PostgreSQL B-tree index.
- Batch review for supported `CREATE INDEX` statements in a migration file.
- Read-only `doctor` and conservative existing-index `audit` commands.
- Offline before/after usage observation and SARIF output for CI workflows.
- Stable review verdicts and Markdown report output.
- Existing-index comparability checks for validity, readiness, predicates, expressions, access
  method, operator classes, collations, and sort order.
- Pooled-session HypoPG isolation so stale hypothetical indexes cannot contaminate baselines.
- Clean package build and command smoke tests across Python 3.10–3.13 in CI.
- Focused installation, usage, roadmap, issue, contribution, and release documentation.

### Changed

- Public positioning now focuses on local PostgreSQL index review instead of automatic indexing.
- Legacy cleanup, inferred bloat, automatic reindex, and estimated write-cost paths remain outside the
  public recommendation contract; public overlap findings never emit drop advice.
- Migration-internal overlap and duplicate index names now participate in SARIF and the opt-in
  `existing_overlap` CI gate.
- Legacy cleanup ownership requires an exact same-table `mode=apply` audit receipt; lifecycle and
  VACUUM helpers default to dry-run and quote catalog identifiers safely.
- The Husky pre-commit hook now resolves the UI package directory and runs its lint gate without
  requiring a live authenticated API for type generation.
- SQL parsing uses SQLGlot’s PostgreSQL AST boundary.
- Development dependencies no longer rely on known-vulnerable historical pins.
- Python type aliases remain compatible with Python 3.10 while supporting FastAPI/Pydantic runtime
  schema generation.
- Optional academic/ML algorithm exports now load lazily, keeping the core review install light.

### Security

- The API remains fail-closed with a required bearer token by default.
- The public review command never executes supplied candidate SQL or physical DDL.
- Minimum `python-dotenv` and pytest versions include the first patched releases for the two
  default-branch dependency alerts current at launch review time.
- Dashboard dependencies were refreshed within their supported major lines; `pnpm audit` reports no
  known vulnerabilities for the committed lockfile.

## Historical repository tag

The older `v1.0.0-stable` tag predates the installable focused package and this changelog. It is kept
for history but is not a supported production release line.
