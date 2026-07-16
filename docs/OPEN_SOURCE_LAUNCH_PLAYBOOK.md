# How to launch and grow an open-source project

This is the reusable process behind IndexPilot's public launch preparation. It combines the work we
actually completed with current guidance from GitHub, Open Source Guides, OpenSSF, PyPA, OpenAI, and
Anthropic. It is intentionally stricter than a “create a README and post it” checklist.

## The central lesson

Open sourcing exposes code. It does not create a product, prove demand, or produce distribution.

A credible launch needs four things in order:

1. **Value:** a known user has a painful job.
2. **Proof:** the supported path works and produces an understandable result.
3. **Trust:** a stranger can install, evaluate, and contribute safely.
4. **Reach:** the right people can find it and understand why it matters.

Promotion cannot repair a weak product promise. More features cannot repair a broken installation.

## What IndexPilot taught us

IndexPilot began as a short DNA-inspired database experiment. The first useful work was not marketing;
it was establishing what the code really did. We traced the live paths, tested the algorithms and
math, compared existing PostgreSQL indexing tools, and used a real trading-system workload without
editing its data. That work narrowed the product from a broad autonomous indexer to a safer promise:

> Stop bad PostgreSQL indexes before they reach production.

That correction drove the rest of the launch work:

- unsafe or unproven behavior was removed from the public promise;
- SQL parsing and planner evidence were strengthened;
- redundant-index, bloat, write-cost, audit, and comparison features were exposed only with honest
  evidence boundaries;
- the CLI became the supported entry point while the dashboard and legacy automation stayed clearly
  experimental;
- installation, usage, architecture, security, publishing, and roadmap documentation were aligned;
- the README was rewritten around the user outcome, quick start, proof, safety, and limits;
- license, contribution, conduct, security, issue, PR, and agent guidance were made visible;
- CI, branch protection, Discussions, topics, homepage metadata, a social/demo asset, and GitHub Pages
  were configured;
- a release workflow and PyPI Trusted Publishing path were prepared without storing a registry token;
- `robots.txt`, `sitemap.xml`, `llms.txt`, semantic metadata, `AGENTS.md`, and explicit ChatGPT and Claude
  search-crawler rules made the project easier for humans and agents to discover;
- the build story, Product Hunt packet, channel copy, screenshots, response rules, and measurement plan
  were prepared without inventing adoption or publishing unapproved claims.

The result is coherent because every public surface points to the same narrow product. That alignment
matters more than the number of launch assets.

## The complete launch process

### 1. Decide whether the code should launch

Start in the repository. Identify the supported entry point, actual callers, tests, current users,
runtime evidence, stale modules, unsafe defaults, and broken claims. Run the main user journey in a
clean environment.

Then research the market:

- Who experiences the pain and when does it become urgent?
- What do they use today, including scripts and doing nothing?
- Where do they complain or ask for help?
- What do mature competitors solve well?
- What narrow job remains expensive, risky, or awkward?
- Can this code prove a better outcome for that job today?

Choose one promise that fits the evidence. Document major pivots for later. Do not add weeks of scope
to rescue a launch unless users have demonstrated the need.

### 2. Make publication safe and legal

- Confirm ownership of source, assets, data, fonts, models, and copied snippets.
- Check employer IP obligations where relevant.
- Select an OSI-approved license and include its full text.
- Scan the current tree, Git history, Actions logs, issues, PRs, and release assets for secrets and
  private data.
- Revoke exposed credentials before removing them.
- Review third-party licenses and generated artifacts.
- Preserve unrelated working-tree changes and runtime evidence.
- Never move or edit another product's data just to create a case study.

### 3. Repair only real launch blockers

Prioritize:

1. security and destructive defaults;
2. correctness of the primary path;
3. clean installation and first run;
4. misleading claims or stale documentation;
5. understandable errors and rollback;
6. small additive features that complete the promised job.

Put broad refactors, speculative integrations, hosted multi-user controls, and attractive but unproven
algorithms on a roadmap. A focused alpha with honest limits is more useful than an imaginary platform.

### 4. Make first success easy

The README should answer, in this order:

- What outcome does this create?
- Who has this problem?
- Why use this instead of the existing options?
- What proof is available?
- How do I install and see a result in five minutes?
- What can it change, and what can it never change automatically?
- What is incomplete?
- Where do I ask, contribute, report a vulnerability, or read the roadmap?

Build the exact release artifact and install it in a clean environment. Run the documented commands
verbatim. Test package contents, supported runtimes, version output, normal failure behavior, and public
download links. “It works in the maintainer checkout” is not release evidence.

### 5. Create trust and contribution routes

At minimum, add and maintain:

- `README.md`, `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md`;
- focused bug, feature, and question forms;
- a PR template with tests, docs, safety, and evidence checks;
- a support location such as GitHub Discussions;
- passing CI and a protected default branch or ruleset;
- dependency alerts, secret scanning, code scanning, and private vulnerability reporting when supported;
- a few real `good first issue` or `help wanted` tasks with acceptance criteria;
- `AGENTS.md` when coding agents are expected to work in the repository.

Use GitHub's community profile as a presence check, not a quality score. Read every template and ensure
its contacts, commands, and promises are real. For a solo project, keep an emergency admin path while
still preventing accidental force pushes, deletion, and untested merges.

Give requests a visible path instead of treating every message as implementation-ready:

1. questions go to a Q&A surface or focused help form;
2. early ideas stay in a Discussion while the user pain, evidence, alternatives, and product boundary
   are tested;
3. validated work becomes a focused Issue with acceptance criteria and a link to the Discussion;
4. a contributor comments with an approach and receives assignment or maintainer confirmation before
   substantial work, which avoids duplicate effort.

Do not promise response times that the maintainer cannot sustain. During an active launch, inspect
questions and install failures daily; triage community and maintenance work weekly; review supported
versions, public links, discovery surfaces, and contributor tasks monthly. Publishing, releases,
security decisions, permissions, conduct enforcement, and irreversible moderation remain human-owned.

### 6. Package and release professionally

- Keep the package name, tag, version output, and release title aligned.
- Build from a clean tag in CI.
- Prefer trusted publishing or workload identity over long-lived tokens.
- Publish wheels, archives, containers, checksums, signatures, attestations, or provenance appropriate
  to the ecosystem.
- Write user-facing release notes and known issues.
- Install and run the package from the public registry after publication.
- Document rollback, yanking, compatibility, and supported versions.

For Python, PyPA recommends Trusted Publishing for supported CI providers. IndexPilot therefore prepared
a GitHub environment and publish workflow instead of placing a PyPI API token in repository secrets.

### 7. Make it discoverable to people and agents

On GitHub:

- use a concrete description, homepage, accurate topics, social preview, and published release;
- pin the repository on the maintainer profile;
- enable Discussions and seed a useful welcome topic;
- create useful `good first issue` labels because GitHub surfaces them;
- cross-link the repository, package, docs, live demo, and latest release.

On the public site:

- use semantic, accessible, text-first pages;
- add accurate titles, descriptions, canonical URLs, Open Graph data, and structured metadata;
- publish `robots.txt` and `sitemap.xml`, avoid accidental `noindex`, and verify HTTPS and live URLs;
- optionally publish `llms.txt` as a map, while remembering it does not replace normal indexing.

For agent discovery:

- make installation, owners, supported paths, safety rules, and test commands easy to extract;
- add repository-specific `AGENTS.md` guidance;
- explicitly allow the search crawlers you want;
- keep search-crawler policy separate from model-training policy;
- verify that a fresh agent can explain the product without relying on old experimental docs.

For IndexPilot, `OAI-SearchBot`, `Claude-SearchBot`, and `Claude-User` are explicitly allowed. `GPTBot`
and `ClaudeBot` are separate model-development crawlers and are not required for search visibility.

### 8. Launch with a real story

A strong solo-builder story is not “I made another tool.” It is:

1. the problem or inspiration;
2. the first assumption;
3. what failed;
4. the correction;
5. what now works, with proof;
6. the honest limit;
7. the feedback or contribution requested.

Write one canonical source, then adapt it to GitHub, ecosystem forums, Hacker News, DEV/Medium/Hashnode,
Product Hunt, newsletters, awesome lists, and the maintainer's existing social network where relevant.
Do not paste the same promotion everywhere. Do not invent users, benchmarks, reactions, or personal
comments. Do not coordinate votes. Be available to answer questions yourself.

Launch timing matters less than relevance and responsiveness. Choose a time when the maintainer can
support users, watch errors, fix the quick start, and participate in the discussion.

### 9. Measure learning, not applause

Record a baseline, then review at one day, seven days, and thirty days:

- qualified repository and documentation visits;
- package or release downloads;
- successful installs and first outputs;
- install failures and time to first success;
- repeat use, dependents, and real workloads;
- useful issues, discussions, pull requests, and new contributors;
- which messages and channels brought relevant users.

Stars and impressions are useful attention signals, but they are not proof of product value. Turn
repeated setup failures into product fixes and repeated questions into documentation. Archive or mark
the project unmaintained honestly if support stops.

## Reusable readiness checklist

### Product

- [ ] One user and painful job are named.
- [ ] Alternatives and the “do nothing” option are compared.
- [ ] One narrow promise is proven by a clean run.
- [ ] Experiments and deferred work are clearly separated.

### Safety and legality

- [ ] Source and asset ownership are confirmed.
- [ ] An OSI-approved license is present.
- [ ] Tree and history have been checked for secrets and private data.
- [ ] Destructive behavior is not the default.

### Adoption

- [ ] README explains value, proof, install, usage, safety, and limits.
- [ ] The public artifact installs in a clean environment.
- [ ] Quick-start commands work verbatim.
- [ ] Errors guide users to a fix.

### Trust and community

- [ ] Contribution, conduct, security, support, issue, and PR routes exist.
- [ ] Main CI passes and the default branch is protected appropriately.
- [ ] Security and dependency features are enabled where supported.
- [ ] Real beginner contribution tasks exist.

### Distribution and discovery

- [ ] A tagged release and ecosystem package exist or the temporary install route is explicit.
- [ ] Publishing uses short-lived identity or trusted publishing.
- [ ] GitHub metadata, topics, social preview, profile pin, and homepage are current.
- [ ] Public docs, metadata, sitemap, robots policy, and live links are verified.
- [ ] Agent guidance and desired AI crawler access are explicit.

### Launch and follow-through

- [ ] The story is factual and channel-specific.
- [ ] Screenshots/demo show the real supported path.
- [ ] The maintainer can respond during launch.
- [ ] Baselines and 1/7/30-day reviews are defined.

## Sources and why they matter

- [GitHub repository best practices](https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories) — core repository and security guidance.
- [GitHub community profiles](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories) — recognized community health files.
- [Open Source Guides: Starting a Project](https://opensource.guide/starting-a-project/) — goals, licensing, documentation, conduct, and pre-launch checks.
- [GitHub repository topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics) — GitHub discovery metadata.
- [GitHub good-first-issue guidance](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/encouraging-helpful-contributions-to-your-project-with-labels) — contributor discovery.
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases) — distributable versions and release notes.
- [GitHub social previews](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview) — shareable repository identity.
- [OpenSSF Scorecard](https://securityscorecards.dev/) — automated supply-chain posture checks after the basics.
- [PyPA tool recommendations](https://packaging.python.org/en/latest/guides/tool-recommendations/) — secure Python packaging and Trusted Publishing.
- [OpenAI publishers and developers FAQ](https://help.openai.com/en/articles/12627856-publishers-and-developers-faq) — ChatGPT search and agent accessibility.
- [Anthropic crawler controls](https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler) — Claude search and user-fetch agents.

Platform behavior changes. Recheck official documentation before changing permissions, publishing, or
scheduling a launch.
