# Publishing IndexPilot

IndexPilot currently ships as a GitHub prerelease. PyPI publishing is the next distribution step,
but it must use Trusted Publishing rather than a long-lived API token.

## One-time PyPI setup

1. Create or claim the `indexpilot` project on PyPI.
2. Add a Trusted Publisher for `eyeinthesky6/indexpilot`.
3. Set the workflow name to `publish.yml` and the environment to `pypi`.
4. The GitHub `pypi` environment already restricts deployment to tags matching `v*`; verify that
   rule before the first stable release.
5. Keep the release prerelease until installation from PyPI is verified in a clean environment.

These account and environment steps are deliberately manual because they establish external
publishing authority.

## Release sequence

1. Update the version in `pyproject.toml` and `CHANGELOG.md`.
2. Run the package, backend, and dashboard jobs from `.github/workflows/ci.yml`.
3. Create and push the signed version tag.
4. Publish the GitHub release for that tag.
5. The trusted workflow builds from the tagged source and publishes the distributions.
6. Verify in a clean environment:

   ```bash
   pipx install indexpilot
   indexpilot --version
   indexpilot review --help
   ```

Never upload from an uncommitted local checkout and never store a PyPI token in the repository.
