# Publishing IndexPilot

IndexPilot `1.1.0a3` is published on PyPI as an alpha. Releases use PyPI Trusted Publishing rather
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
   pipx install "indexpilot==1.1.0a3"
   indexpilot --version
   indexpilot review --help
   ```

   Replace `1.1.0a3` with the package version from the release being verified.

Never upload from an uncommitted local checkout and never store a PyPI token in the repository.
