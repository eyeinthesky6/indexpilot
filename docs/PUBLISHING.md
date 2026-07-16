# Publishing IndexPilot

IndexPilot `1.1.0a4` is the current alpha release. Releases use PyPI Trusted Publishing rather
than a long-lived API token, and the public installation is verified before any stable release.

## Current PyPI setup

The `indexpilot` PyPI project trusts the `eyeinthesky6/indexpilot` repository, the
`.github/workflows/publish.yml` workflow, and the `pypi` GitHub environment. The workflow runs only
when a GitHub release is published, builds from that tagged source, and authenticates with a short-
lived identity token.

Changing the trusted publisher or the protected `pypi` environment is deliberately manual because
those settings control external publishing authority.

## Release sequence

1. Update the version in `pyproject.toml` and `CHANGELOG.md`.
2. Run the package, backend, and dashboard jobs from `.github/workflows/ci.yml`.
3. Create and push the version tag.
4. Publish the GitHub release for that tag.
5. The trusted workflow builds from the tagged source and publishes the distributions.
6. Verify in a clean environment:

   ```bash
   pipx install "indexpilot==1.1.0a4"
   indexpilot --version
   indexpilot review --help
   ```

   Replace `1.1.0a4` with the package version from the release being verified.

Never upload from an uncommitted local checkout and never store a PyPI token in the repository.

## Recurring release and community maintenance

Automation may collect public project signals, dependency or workflow status, and draft maintenance
recommendations. It must not publish releases, change permissions, resolve security reports, apply
conduct sanctions, or post community replies without human approval.

Use this lightweight cadence after publication:

- **Daily during an active launch:** inspect failed installs, new questions, and repeated user pain;
  turn only validated, in-scope work into focused Issues.
- **Weekly:** triage Discussions and issue forms, link duplicates, confirm or release stale claims,
  review dependency and CI status, and record which questions need documentation.
- **Monthly:** review supported Python and PostgreSQL versions, public links, crawler files, package
  metadata, contributor labels, and whether deferred roadmap items gained real evidence.
- **Before every release:** run the full release sequence above and review open security, correctness,
  packaging, and documentation blockers manually.

An idea begins in [Ideas Discussions](https://github.com/eyeinthesky6/indexpilot/discussions/categories/ideas)
when its problem or evidence is still unclear. Once the expected decision, boundary, and acceptance
criteria are concrete, create or link a focused Issue. Contributors claim unassigned work by
commenting with an approach and waiting for assignment or maintainer confirmation before substantial
overlapping work.
