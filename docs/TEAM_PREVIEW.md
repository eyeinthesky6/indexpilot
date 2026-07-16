# Team workflow preview

IndexPilot is testing one narrow question: do PostgreSQL teams need the same advisory index-review
evidence applied repeatedly in pull requests and retained as a decision record?

This page separates what exists now, what is only a hypothesis, and what public responses actually
ask for.

## Current capability: available today

The free, open-source alpha can:

- review a proposed `CREATE INDEX` with the local CLI;
- compare it with aggregated `pg_stat_statements`, existing indexes, and optional HypoPG plans;
- emit JSON, Markdown, and optional SARIF evidence;
- run in trusted GitHub Actions or against a sanitized offline snapshot; and
- apply explicit advisory verdict gates through existing CLI and Action inputs.

It remains read-only. It does not create or drop indexes, run `EXPLAIN ANALYZE`, prove production
latency, provide multi-user accounts, retain organization-wide history, or offer a paid team plan.

## Hypothesis: not built or validated

The hypothesis is that repeated team use may need a self-serve, repository-owned workflow around the
free engine:

1. find every changed index migration;
2. apply the same review policy;
3. show one readable pull-request or CI summary;
4. retain why a proposal was accepted, rejected, or waived; and
5. compare the pre-deploy decision with later recorded evidence.

That is not a roadmap commitment or current product claim. A hosted dashboard, automatic DDL,
SSO/RBAC, support service, or billing system is not part of this preview.

## How close is the repository today?

The proposed workflow is adjacent to working pieces, but it is not already a team product.

| Team need | What exists now | Missing work |
|---|---|---|
| Review one migration | The Action accepts one migration file; the CLI reviews every supported `CREATE INDEX` inside that file | No team-specific work for this narrow case |
| Review safely without pull-request database secrets | The CLI accepts a sanitized offline snapshot, and the trusted/fork-safe recipe is documented | The bundled Action has no snapshot input; the fork-safe recipe currently uses explicit CLI steps |
| Find all changed migrations | A caller can pass one known file | No changed-file discovery or aggregate multi-file run |
| Put a readable result in the pull request | Markdown, JSON, and SARIF files are produced | No native GitHub job summary or aggregate pull-request summary |
| Keep the same policy | `--fail-on` and the Action's `fail-on` input provide explicit verdict gates | Policy still lives in each workflow; there is no shared team policy file or cross-repository distribution |
| Retain the decision and waiver | Stable report files can be stored by the caller | No repository-owned decision/waiver ledger or retention convention |
| Check what happened later | `indexpilot compare` compares before/after reports for recorded scans on the exact index shape | No automatic link from the original pull-request decision to a later observation |

This makes a single-repository free preview plausible without a hosted service, but the workflow
still needs product work. The demand form exists to learn which missing row matters before building
all of them.

## Share a real repeated pain

Use the public [Team workflow preview form](https://github.com/eyeinthesky6/indexpilot/issues/new?template=team_workflow.yml)
if your team repeatedly reviews PostgreSQL index migrations. The form asks for:

- the review trigger and frequency;
- fixed-choice workflow pains;
- a sanitized description of the present workaround;
- the smallest CI result worth installing;
- whether a 30-day self-serve trial is realistic; and
- an optional annual price signal if the workflow works.

Do not submit raw SQL, credentials, object or repository names, company identifiers, customer data,
or other confidential information. The issue and its free-text answers are public.

Each matching issue receives one deterministic acknowledgement. It is not a personal reply and does
not promise a response time. A separate [aggregate rollup workflow](https://github.com/eyeinthesky6/indexpilot/actions/workflows/team-preview-rollup.yml)
recomputes fixed-choice counts after issue changes and once a week.

## Actual aggregate asks

The latest workflow run is the source of truth for aggregate answers. The rollup publishes only:

- total structurally valid submissions;
- counts for each review trigger and frequency;
- counts for each fixed workflow pain;
- trial-readiness counts; and
- optional price-band counts.

It never publishes or derives usernames, issue numbers, titles, URLs, timestamps, comments, textarea
answers, company or repository identifiers, SQL, object names, or customer/database metadata.
Unknown or edited fixed-choice values are ignored. The rollup is rebuilt from public issues rather
than appended, so rerunning it does not create duplicate records.

The automation deliberately does not decide whether a request is qualified. A human must read the
sanitized workaround and smallest useful result, check that the pain is repeated, and distinguish a
team-workflow need from an unsupported core index shape or installation bug.

## Evidence gates

Within 45 days of making the form visible, build a free team preview only if all four conditions are
met:

- five qualified submissions from distinct GitHub accounts;
- three report at least three reviews per month;
- three independently converge on the same workflow pain; and
- two commit to trying the preview within 30 days.

If the form receives little meaningful exposure, the result is **distribution unknown**, not proof
that no market exists. Do not build paid packaging from that result.

Consider paid packaging only after a free preview produces:

- three completed, sanitized team trials;
- repeat use by two teams on a second pull request within 30 days;
- two explicit price signals of at least USD200 per team per year; and
- repeated pain around team policy, history, or decisions rather than missing core syntax support.

If trials do not repeat, keep the workflow free and stop paid packaging. If unsupported index shapes
dominate, improve the free core first. If teams repeat but reject every price, test the packaging
once before building billing.

## Public activity

The README and project site show live package downloads, GitHub stars and forks, and Team preview
rollup status. The Team preview form and its aggregate rollup are the public path for learning which
repeated team pain is worth solving next.
