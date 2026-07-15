# IndexPilot Launch Article Campaign

## Outcome

- Objective: explain the product correction honestly and attract technically useful early users.
- Audience: PostgreSQL developers, database-minded application engineers, and OSS contributors.
- Desired action: understand the engineering correction and visit the author's profile if the
  project itself is relevant.
- Time horizon: four weeks after the first article is published.
- Primary KPI: engaged reads and author-profile visits.
- Guardrail metrics: reading time, saves, useful discussion, and no misleading product claims.
  Record article and profile baselines immediately before publication.

## Brand and Boundaries

- Voice: first person, plain, specific, willing to admit where the first design was weaker.
- Visual system: reuse the IndexPilot Evidence Gate mark and public launch image.
- Approved facts and claims: only facts supported by the repository, tests, sanitized case studies,
  and linked primary sources.
- Topics to avoid: production-ready claims, generic speed claims, private query text, customer data,
  autonomous database management, and claims that IndexPilot beats mature index advisers.
- Writing constraints: no em dash or en dash characters, no stock wonder-language, no fake quotes, no fake
  reactions, and no generic AI marketing phrases.
- Privacy constraints: publish only the aggregate, already documented benchmark evidence. Do not
  publish source values, credentials, schema details beyond the existing sanitized case study, or
  runtime artifacts.
- Approval owner: repository owner. Exact final copy must be approved before publication.
- AI disclosure: required for the current Medium draft because an AI assistant helped organize and
  edit it. A later DEV version must disclose any generated text that remains.
- Pre-approved response classes: none. Draft replies may be prepared, but public replies need user
  approval.

## Channel Plan

| Platform | Account | Role | Format | Frequency | KPI | Scheduler |
|---|---|---|---|---|---|---|
| DEV Community | Confirm before publishing | Human-written retrospective only | New author draft | Optional | Useful technical discussion | Native draft |
| Medium | Confirm before publishing | Engineering retrospective | Edited article | One launch article | Engaged reads and profile visits | Native draft |

## Content Pillars

| Pillar | Audience value | Brand connection | Formats | Test hypothesis |
|---|---|---|---|---|
| A reasonable index can still be wrong | Shows why planner and workload evidence matter | Core product correction | Benchmark table and explanation | Concrete failure earns more trust than a feature list |
| Exact migration review | Gives the product a clear job | Current public wedge | Command and verdict example | Readers understand when to use IndexPilot |
| Honest open source limits | Prevents false expectations | Advisory-only design | Explicit limits and contribution asks | Narrow claims attract better early issues |

## Publication Plan

1. Approve the repository source article and signed-in Medium identity.
2. Save it as a Medium draft and verify the cover, code blocks, disclosure, links, and topics.
3. Request final approval again after the Medium preview exists and before publishing.
4. Do not post this exact draft to DEV. [DEV's current AI-assisted article guidance](https://dev.to/guidelines-for-ai-assisted-articles-on-dev/)
   says such posts should not promote the author's own program. A later DEV version needs a
   genuinely human-written account whose purpose is technical discussion rather than project
   promotion.

## Review Rhythm

- Weekly operations review: verify links, comments, issues, and repository traffic evidence.
- Monthly strategy review: decide whether the correction story produced useful trials or should not
  be repeated.
- Decision log location: this file and `CONTENT_MANIFEST.csv`.
