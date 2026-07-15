# IndexPilot Launch Campaign

## Outcome

- Objective: launch the usable open-source alpha and explain the product correction honestly.
- Audience: PostgreSQL developers, database-minded application engineers, and OSS contributors.
- Desired action: understand the engineering correction and visit the author's profile if the
  project itself is relevant.
- Time horizon: four weeks after the Product Hunt launch.
- Primary KPI: qualified product-page visits, release downloads, and useful issues.
- Guardrail metrics: Product Hunt discussion, article reading time, profile visits, and no misleading
  product claims. Record repository, release, product-page, and profile baselines before launch.

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
- AI boundary: the Product Hunt listing fields may use approved assisted copy. Product Hunt comments,
  including the maker's first comment and replies, must be written by the maker.
- Pre-approved response classes: none. Product Hunt comments are never automated.

## Channel Plan

| Platform | Account | Role | Format | Frequency | KPI | Scheduler |
|---|---|---|---|---|---|---|
| Product Hunt | `@jaithakur`, verify before saving | Primary product launch | Native product post | One alpha launch | Qualified visits, downloads, and issues | Native draft |
| DEV Community | Confirm before publishing | Human-written retrospective only | New author draft | Optional | Useful technical discussion | Native draft |
| Medium | Confirm before publishing | Engineering retrospective | Edited article | One launch article | Engaged reads and profile visits | Native draft |

## Content Pillars

| Pillar | Audience value | Brand connection | Formats | Test hypothesis |
|---|---|---|---|---|
| A reasonable index can still be wrong | Shows why planner and workload evidence matter | Core product correction | Benchmark table and explanation | Concrete failure earns more trust than a feature list |
| Exact migration review | Gives the product a clear job | Current public wedge | Command and verdict example | Readers understand when to use IndexPilot |
| Honest open source limits | Prevents false expectations | Advisory-only design | Explicit limits and contribution asks | Narrow claims attract better early issues |

## Product Hunt Launch Plan

1. Approve the exact listing fields and profile update in `PRODUCT_HUNT_PACKET.md`.
2. Verify the signed-in account is the existing `@jaithakur` personal maker account.
3. Add the IndexPilot product link to the maker profile without removing existing personal links.
4. Export the existing brand mark as a 240x240 thumbnail and prepare at least two real product
   gallery images at Product Hunt's recommended 1270x760 size.
5. Create a native Product Hunt draft. Do not schedule it yet.
6. The maker writes the first comment in his own words from the verified fact sheet.
7. Choose a date within Product Hunt's 30-day scheduling window when the maker can answer comments.
8. Verify the complete preview and request action-time approval before scheduling.

## Article Plan

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
