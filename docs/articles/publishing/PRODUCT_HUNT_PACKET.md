# IndexPilot Product Hunt Launch Packet

Status: awaiting exact-copy, asset, account, and launch-date approval

Last researched: 2026-07-15

No Product Hunt draft has been created or scheduled from this packet.

## Launch Decision

Launch IndexPilot as a free, open-source alpha for PostgreSQL developers. The DNA-storage idea is
the origin story, not the product claim. The product claim stays narrow:

> IndexPilot's public alpha is a read-only evidence gate for PostgreSQL index migrations.

The primary destination is the live product page, not an article or a raw repository URL:

`https://eyeinthesky6.github.io/indexpilot/`

## Exact Product Hunt Listing Fields

- Product name: `IndexPilot`
- Tagline: `Make a Postgres index prove itself before merge`
- Tagline length: 47 characters
- Website: `https://eyeinthesky6.github.io/indexpilot/`
- Description: `IndexPilot reviews supported CREATE INDEX statements in a migration against real
  pg_stat_statements workload, comparable indexes, and optional HypoPG plans. It returns cautious
  JSON and Markdown evidence, plus optional SARIF, without applying the migration.`
- Description length: 257 characters without Markdown wrapping
- Pricing: `Free`
- Availability: live alpha; do not select a waitlist or not-yet-available state
- Maker: `@jaithakur`
- Suggested topics: `Databases and backend frameworks`, `Developer Tools`, `Open Source`
- Promo code: none
- Product X account: none; do not create one merely for launch
- Video or interactive demo: omit unless a real walkthrough is completed before scheduling

Use the public product page as the primary URL. If Product Hunt offers a separate GitHub field,
add `https://github.com/eyeinthesky6/indexpilot` as a secondary open-source link.

## Maker Profile

Public profile verified before browser changes:

- Account: [Jai Thakur, `@jaithakur`](https://www.producthunt.com/@jaithakur)
- Headline: `Builder at Six Ideas`
- Existing maker history: three listed products and a Top 5 Launch badge
- Public followers on 2026-07-15: 48
- Existing About text mentions practical web products, open-source experiments, and ArtistPass

Proposed About text:

> I make practical web products and open-source experiments. Currently building ArtistPass and
> IndexPilot, a read-only PostgreSQL index evidence gate.

Proposed profile link:

- Label: `IndexPilot`
- URL: `https://eyeinthesky6.github.io/indexpilot/`

Keep the existing ArtistPass and LinkedIn links. If Product Hunt does not allow another link, add
IndexPilot to the existing personal projects page instead of deleting a personal link.

## Origin Story Fact Sheet

The maker writes the first Product Hunt comment in his own words. Use these verified facts:

1. DNA data storage sparked the idea because DNA offers exceptional information density and
   durability.
2. DNA storage is currently aimed at archival use. Synthesis and sequencing remain too slow,
   expensive, and complex for a millisecond database path.
3. IndexPilot never put application data into physical DNA. The prototype borrowed a metaphor:
   schema as genome, live query patterns as expression, and an index proposal as a mutation.
4. The first prototype grew into a broad automatic index manager before its evidence justified
   that scope.
5. At the same time, the maker was building an algorithmic-trading system and needed to understand
   the cost and value of PostgreSQL indexes under a real workload.
6. A read-only trial inspected 114 tables, 480 indexes, and 187 `pg_stat_statements` rows.
7. The first heuristic proposed a plausible `(action_type, timestamp)` index. Dexter, HypoPG, and a
   controlled reproduction showed that `(timestamp)` was the better balanced choice for the large
   audit case.
8. That failure caused the final pivot: review the exact `CREATE INDEX` already proposed in a
   migration instead of pretending to be an autonomous DBA.
9. The current public review path is read-only and advisory. It does not apply the migration or
   declare an index safe to remove.
10. A useful closing question is: where should this evidence gate sit in a real workflow, migration
    CI, DBA review, or the step before a production-copy benchmark?

Primary background sources:

- [Microsoft Research DNA Storage](https://www.microsoft.com/en-us/research/project/dna-storage/overview/)
- [DNA data storage and sequencing, arXiv:2205.05488](https://arxiv.org/abs/2205.05488)
- [`PROFITPILOT_HYPOPG_DEXTER_COMPARISON.md`](../../case_studies/PROFITPILOT_HYPOPG_DEXTER_COMPARISON.md)
- [`PROFITPILOT_PRODUCTION_COPY_BENCHMARK.md`](../../case_studies/PROFITPILOT_PRODUCTION_COPY_BENCHMARK.md)

## First Comment and Replies

Product Hunt asks makers to start the conversation, but its current commenting rules reject
AI-generated comments. The maker should write a short first comment from the fact sheet above.

Write rough answers to these prompts before opening the Product Hunt editor:

- What about DNA storage made the original idea worth a weekend experiment?
- What showed that synthesis and sequencing could not serve the trading system's live database?
- Which index looked reasonable at first, and what did the controlled evidence show instead?
- Why did that result make a review gate more useful than an automatic index manager?
- What kind of PostgreSQL migration would you like an early user to test?

Suggested structure, not ready-to-paste copy:

1. Two sentences on the DNA-storage inspiration.
2. Two sentences on why the original direction did not fit a live trading database.
3. The real index recommendation that failed the tradeoff test.
4. What IndexPilot does now and what it deliberately does not do.
5. One specific request for feedback.

Voice rules:

- first person and plain language;
- no em dash or en dash characters;
- no inflated launch language, fake reactions, or invented adoption;
- no request for upvotes;
- no claim that IndexPilot uses molecular storage, is production ready, or beats Dexter or
  pganalyze;
- no generated maker replies. The maker responds personally.

## Asset Plan

Product Hunt currently recommends a square 240x240 thumbnail and 1270x760 gallery images. A gallery
needs at least two images before it becomes visible.

1. Thumbnail: export the existing `ui/public/brand/indexpilot-mark.svg` exactly as a 240x240 PNG.
2. Gallery 1: recapture the public hero at 1270x760. Keep the advisory and never-applies-DDL text
   visible.
3. Gallery 2: show one real `indexpilot review` command beside its JSON and Markdown verdict. Use
   sanitized identifiers only.
4. Gallery 3: show real SARIF output uploaded as an artifact by the documented trusted-CI recipe.
   Do not depict a Code Scanning annotation or untrusted-fork run; neither is shipped yet. Make
   clear that CI failure is opt-in.
5. Optional gallery 4: show the controlled timestamp-versus-composite result. Label it as one
   controlled reproduction, not a general speed claim.

Existing source assets:

- `ui/public/brand/indexpilot-mark.svg`, square vector source
- `ui/public/brand/indexpilot-social.png`, 1280x640 public-site capture

The launch branch adds the DNA-to-trading-system pivot and links to the sanitized build story and
controlled benchmark. Verify that the deployed page contains it before using that section in a
gallery capture.

Do not lead with the historical dashboard. The supported product is the CLI and evidence report.
Do not use private ProfitPilot screenshots, raw queries, credentials, customer data, or trading
signals.

## Product Hunt Fit and Launch Risks

Why it fits:

- it is a live, installable digital product rather than a waitlist;
- the exact-migration evidence gate is narrower than a general index adviser and easy to explain;
- the read-only boundary, inspectable reports, and open source code make the claim testable;
- the failed composite-index assumption gives the launch a real engineering correction, not a
  fabricated founder story.

Risks to handle honestly:

- it is an alpha for a narrow PostgreSQL audience;
- it has very little public adoption evidence today;
- the current release is installed from GitHub rather than PyPI;
- HypoPG planner evidence is one representative query, not a production workload replay;
- Product Hunt featuring is editorial and cannot be promised.

Do not schedule until the profile link, two real gallery images, maker-written first comment, and
complete preview have been checked.

## Draft and Scheduling Checklist

- [ ] Verify the browser is signed in as `@jaithakur`.
- [ ] Apply the approved About text and IndexPilot profile link.
- [ ] Confirm the product page returns HTTP 200 and its GitHub/install links work.
- [ ] Upload the exact square mark and at least two real gallery images.
- [ ] Paste the approved name, tagline, description, price, topics, maker, and URLs.
- [ ] Mark the product as a live alpha, not a waitlist.
- [ ] Save a native draft first. A draft is not approval to schedule.
- [ ] The maker writes and reviews the first comment personally.
- [ ] Choose a launch date when the maker can answer throughout Product Hunt's Pacific-time day.
- [ ] Verify the desktop and mobile preview.
- [ ] Request final action-time approval before scheduling.

Product Hunt allows scheduling within 30 days. Its launch day begins at 12:01 AM Pacific. Confirm
the India-time conversion shown in the scheduling interface rather than relying on a hand-converted
time.

## Launch-Day Rules

- Share the live post normally with relevant existing communities.
- Ask people to look, try the product, or give specific feedback. Do not ask for an upvote.
- Do not mass-message, incentivize votes, coordinate votes, or use automated engagement.
- The maker answers Product Hunt comments personally.
- Record the live URL and launch time in `CONTENT_MANIFEST.csv`.
- Review useful comments and issues after 24 hours, seven days, and four weeks.

## Baseline and Success Measures

Baseline captured on 2026-07-15:

- Product Hunt `@jaithakur`: 48 followers
- GitHub: 0 stars, 1 fork, 0 watchers
- `v1.1.0a1` wheel downloads: 2
- `v1.1.0a1` source-archive downloads: 0
- public product page: HTTP 200

Primary success signals:

- qualified product-page and GitHub visits;
- release downloads;
- users who complete or attempt one supported migration review;
- useful issues, compatibility reports, or pull requests.

Product Hunt points and rank are secondary. Product Hunt now considers several forms of genuine
engagement, not only raw upvotes.

## Current Official Product Hunt Sources

- [How to post a product](https://help.producthunt.com/en/articles/479557-how-to-post-a-product)
- [How to schedule a post](https://help.producthunt.com/en/articles/2724119-how-to-schedule-a-post)
- [Featuring guidelines](https://help.producthunt.com/en/articles/9883485-product-hunt-featuring-guidelines)
- [Community guidelines](https://help.producthunt.com/en/articles/3615694-community-guidelines)
- [Commenting guidelines](https://help.producthunt.com/en/articles/10030102-commenting-guidelines)
- [How to share a post](https://help.producthunt.com/en/articles/2690626-how-do-i-share-my-post)
- [How Product Hunt points work](https://help.producthunt.com/en/articles/10275873-what-are-points)
