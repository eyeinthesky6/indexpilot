# IndexPilot documentation

The public launch path is the read-only PostgreSQL index review CLI. Start with these current docs:

1. [README](../README.md) — value, five-minute run, safety boundary
2. [Installation](INSTALLATION.md) — package, database access, `pg_stat_statements`, HypoPG
3. [Usage](USAGE.md) — commands, verdicts, outputs, supported SQL
4. [Trusted CI recipe](GITHUB_ACTIONS.md) — migration review without exposing database secrets
5. [Roadmap](ROADMAP.md) — evidence work planned after the preview
6. [Architecture](codebase/ARCHITECTURE.md) — current runtime owners and flow
7. [Known concerns](codebase/CONCERNS.md) — honest gaps and deferred production proof
8. [Security policy](../SECURITY.md) and [contribution guide](../CONTRIBUTING.md)
9. [Contributor and coding-agent guide](../AGENTS.md) — current owners, checks, and safety rules
10. [Publishing](PUBLISHING.md) — release process and PyPI Trusted Publishing setup
11. [AI discovery](AI_DISCOVERY.md) — ChatGPT, Claude, sitemap, and crawler access
12. [Open-source launch playbook](OPEN_SOURCE_LAUNCH_PLAYBOOK.md) — reusable product, repository, release, discovery, and growth process

## Documentation status

| Area | Status | Use it for |
|------|--------|------------|
| Root README and `docs/INSTALLATION.md`, `docs/USAGE.md`, `docs/ROADMAP.md` | Current | Public CLI install and operation |
| `docs/GITHUB_ACTIONS.md` | Current | Trusted migration-review CI recipe and secret boundary |
| `docs/codebase/` | Current | Code-rooted architecture, stack, tests, and concerns |
| `docs/research/2026-07-14_SQL_PARSER_ADOPTION.md` | Current decision record | Why SQLGlot replaced regex parsing |
| `docs/articles/` | Public drafts | Generic PostgreSQL education without private project evidence |
| `docs/features/`, `docs/installation/`, `docs/tech/`, `docs/case_studies/` | Mostly historical sprint material | Experiments and context, not current launch claims |

## Product boundaries

### Public launch path

```text
pg_stat_statements + PostgreSQL catalogs
  -> SQLGlot PostgreSQL AST
  -> exact proposal, migration proposals, or workload candidate
  -> comparable existing-index check
  -> optional session-local HypoPG EXPLAIN
  -> cautious verdict + JSON/Markdown/SARIF
```

This path is read-only and never executes physical index DDL.

`indexpilot doctor`, `indexpilot audit`, and `indexpilot compare` reuse this factual evidence
boundary. The audit never emits drop advice, and comparison reports observed use rather than causal
performance improvement.

### Experimental compatibility surfaces

The repository still includes:

- the historical auto-indexer and metadata tables
- a demo CRM simulator and benchmark scripts
- an authenticated single-operator FastAPI dashboard backend
- a Next.js dashboard
- research-inspired scoring modules

These can help contributors explore future work, but they are not the focused CLI’s installation or
support promise. A file’s existence is not proof that a feature is production-ready.

## Documentation rules

- Prefer the current public docs over older completion reports.
- State whether evidence is parser-only, planner-only, or measured runtime behavior.
- Use `not_measured` instead of a guessed bloat or write-overhead percentage.
- Never describe planner-cost reduction as measured latency.
- Keep advisory and apply behavior separate.
- Do not publish raw workload SQL, credentials, customer data, or private database metadata.
- Link to real callers, tests, or report receipts when claiming that code works.

If a historical page conflicts with the root README or `docs/codebase/`, treat the current focused
docs as authoritative and open an issue or pull request to mark the drift.
