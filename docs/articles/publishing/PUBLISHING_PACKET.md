# IndexPilot Launch Article Approval Packet

Status: Medium awaiting approval; DEV blocked pending a human-written version

No external draft or public post has been created. Confirm the signed-in account identity and the
exact article before any browser action that saves or publishes content.

## Source Body for Approval

Use the complete text in [`../04_BUILDING_INDEXPILOT_WITH_EVIDENCE.md`](../04_BUILDING_INDEXPILOT_WITH_EVIDENCE.md).
Do not remove its disclosure paragraph.

## DEV Community

Do not publish this exact draft to DEV. [DEV's current guidance for AI-assisted articles](https://dev.to/guidelines-for-ai-assisted-articles-on-dev/)
says they should not promote the author's own program. The repository article has an explicit
project CTA, so posting it there would put the account in an avoidable grey area.

A later DEV article should be written by the author from personal experience. This repository
draft and the linked case studies can be used as a fact sheet, followed by a normal factual and
grammar review. Do not paste or lightly disguise the current copy.

Suggested metadata for a genuinely human-written version:

- Title: `I built an automatic PostgreSQL indexer. Then a real workload made me cut it down`
- Description: `A real workload showed why a plausible composite index was not the best tradeoff,
  and why IndexPilot became a review gate instead of an automatic DBA.`
- Tags: `postgres`, `database`, `opensource`, `devtools`
- Cover: `ui/public/brand/indexpilot-social.png`
- Cover alt text: `IndexPilot reviews a proposed PostgreSQL index before merge.`
- State on first save: draft
- CTA: none in the article; discovery happens through the author profile
- Primary metric: useful technical discussion and author-profile visits

DEV front matter:

```yaml
---
title: I built an automatic PostgreSQL indexer. Then a real workload made me cut it down
published: false
description: A real workload showed why a plausible composite index was not the best tradeoff, and why IndexPilot became a review gate instead of an automatic DBA.
tags: postgres,database,opensource,devtools
cover_image: https://raw.githubusercontent.com/eyeinthesky6/indexpilot/main/ui/public/brand/indexpilot-social.png
---
```

Before publication, verify the unpublished preview, SQL and shell blocks, links, image crop, and
account identity. Disclose any generated text that remains. Publishing requires a separate
approval after the final preview exists.

## Medium

Create a normal Medium draft from the approved source body. Keep the disclosure in the second
paragraph, as required for generated text under
[Medium's current policy](https://help.medium.com/hc/en-us/articles/22576852947223-Artificial-Intelligence-AI-content-policy).

- Title: `The useful part of my PostgreSQL indexer was the review step`
- Subtitle: `A real workload turned a broad automatic indexer into a smaller evidence gate for
  CREATE INDEX migrations.`
- Topics: `PostgreSQL`, `Open Source`, `Databases`, `Developer Tools`, `Software Engineering`
- Featured image: use the same IndexPilot launch image and verify its focal point
- CTA: none in the article; place the project link only in the author profile or personal website
- Primary metric: engaged reads and author-profile visits

Shorten the competitor paragraph if Medium's preview feels dense. Do not change the benchmark
numbers, safety boundary, unsupported shapes, or disclosure. Verify every code block after paste.
Publishing the Medium version also requires a separate final approval.

## Claim and Safety Check

- The benchmark is identified as one controlled reproduction, not a general speed claim.
- ProfitPilot was a read-only source and no source database object or environment setting changed.
- The article does not claim production readiness, automatic DDL, tenant-specific decisions, bloat
  measurement, or superiority over Dexter or pganalyze.
- The article states the supported index-shape limits.
- The article contains no direct project, repository, or project-site link.
- AI assistance is disclosed within the first two paragraphs.
- The article contains no em dash or en dash characters and does not use the word prohibited by the
  campaign voice rules.
