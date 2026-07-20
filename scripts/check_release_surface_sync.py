from __future__ import annotations

import os
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

PUBLIC_SURFACE_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "action.yml",
    REPO_ROOT / "docs" / "DOCUMENTATION_INDEX.md",
    REPO_ROOT / "docs" / "GITHUB_ACTIONS.md",
    REPO_ROOT / "docs" / "INSTALLATION.md",
    REPO_ROOT / "docs" / "USAGE.md",
    REPO_ROOT / "docs" / "PUBLISHING.md",
    REPO_ROOT / "docs" / "ROADMAP.md",
    REPO_ROOT / "docs" / "TEAM_PREVIEW.md",
    REPO_ROOT / "ui" / "app" / "page.tsx",
    REPO_ROOT / "ui" / "app" / "layout.tsx",
    REPO_ROOT / "ui" / "app" / "robots.ts",
    REPO_ROOT / "ui" / "app" / "sitemap.ts",
    REPO_ROOT / "ui" / "app" / "use-cases" / "useCases.ts",
    REPO_ROOT / "ui" / "public" / "llms.txt",
    REPO_ROOT / "indexpilot" / "dashboard_static" / "index.html",
]

EXPECTED_PROJECT_URLS = {
    "Homepage": "https://eyeinthesky6.github.io/indexpilot/",
    "Repository": "https://github.com/eyeinthesky6/indexpilot",
    "Issues": "https://github.com/eyeinthesky6/indexpilot/issues",
    "Documentation": "https://github.com/eyeinthesky6/indexpilot#readme",
    "Changelog": "https://github.com/eyeinthesky6/indexpilot/blob/main/CHANGELOG.md",
}

RAW_REPO_URL_RE = re.compile(
    r"https://raw\.githubusercontent\.com/eyeinthesky6/indexpilot/main/(?P<path>[^)\s\\\"'>]+)"
)
REPO_BLOB_URL_RE = re.compile(
    r"https://github\.com/eyeinthesky6/indexpilot/blob/main/(?P<path>[^)#\s\\\"'>]+)(?:#[^)\s\\\"'>]*)?"
)
SITE_URL_RE = re.compile(
    r"https://eyeinthesky6\.github\.io/indexpilot(?P<path>/[^)\s\"'>]*)?"
)
PACKAGE_VERSION_RE = re.compile(r'indexpilot(?:\[api\])?==(?P<version>[A-Za-z0-9.\-]+)')
TAG_VERSION_RE = re.compile(r"/releases/tag/v(?P<version>[A-Za-z0-9.\-]+)")
INIT_VERSION_RE = re.compile(r'^__version__ = "(?P<version>[^"]+)"$', re.MULTILINE)
PYPROJECT_URL_RE = re.compile(r'^(?P<key>[A-Za-z]+) = "(?P<value>[^"]+)"$', re.MULTILINE)
USE_CASE_SLUG_RE = re.compile(r'slug:\s*"(?P<slug>[^"]+)"')


def read_project_version() -> str:
    with PYPROJECT_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["version"]


def collect_site_paths() -> set[str]:
    site_paths = {"/", "/llms.txt"}
    use_cases_text = (REPO_ROOT / "ui" / "app" / "use-cases" / "useCases.ts").read_text(encoding="utf-8")
    for match in USE_CASE_SLUG_RE.finditer(use_cases_text):
        site_paths.add(f"/use-cases/{match.group('slug')}/")
    public_root = REPO_ROOT / "ui" / "public"
    for file_path in public_root.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(public_root).as_posix()
            site_paths.add(f"/{rel_path}")
    return site_paths


def normalize_site_path(raw_path: str) -> str:
    site_path = raw_path.replace("\\/", "/").replace("\\", "")
    if "${" in site_path:
        return ""
    if not site_path.startswith("/"):
        site_path = f"/{site_path}"
    if site_path != "/" and not site_path.endswith("/") and "." not in site_path.rsplit("/", 1)[-1]:
        site_path = f"{site_path}/"
    return site_path


def check_public_urls(file_path: Path, text: str, valid_site_paths: set[str]) -> list[str]:
    errors: list[str] = []

    for match in RAW_REPO_URL_RE.finditer(text):
        rel_path = Path(match.group("path"))
        target = REPO_ROOT / rel_path
        if not target.exists():
            errors.append(
                f"{file_path.relative_to(REPO_ROOT)} references missing repo asset {rel_path.as_posix()}"
            )

    for match in REPO_BLOB_URL_RE.finditer(text):
        rel_path = Path(match.group("path"))
        target = REPO_ROOT / rel_path
        if not target.exists():
            errors.append(
                f"{file_path.relative_to(REPO_ROOT)} references missing repo document {rel_path.as_posix()}"
            )

    for match in SITE_URL_RE.finditer(text):
        site_path = normalize_site_path(match.group("path") or "/")
        if not site_path:
            continue
        if site_path not in valid_site_paths:
            errors.append(
                f"{file_path.relative_to(REPO_ROOT)} references unknown site path {site_path}"
            )

    return errors


def collect_file_errors(version: str, file_path: Path, valid_site_paths: set[str]) -> list[str]:
    text = file_path.read_text(encoding="utf-8")
    errors: list[str] = []

    package_versions = sorted({match.group("version") for match in PACKAGE_VERSION_RE.finditer(text)})
    if package_versions and package_versions != [version]:
        errors.append(
            f"{file_path.relative_to(REPO_ROOT)} contains package install versions {package_versions}, expected only {version}"
        )

    tag_versions = sorted({match.group("version") for match in TAG_VERSION_RE.finditer(text)})
    if tag_versions and any(found != version for found in tag_versions):
        errors.append(
            f"{file_path.relative_to(REPO_ROOT)} contains release tag versions {tag_versions}, expected only {version}"
        )

    errors.extend(check_public_urls(file_path, text, valid_site_paths))

    return errors


def main() -> int:
    version = read_project_version()
    errors: list[str] = []
    valid_site_paths = collect_site_paths()

    for file_path in PUBLIC_SURFACE_FILES:
        errors.extend(collect_file_errors(version, file_path, valid_site_paths))

    pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")
    project_urls = {match.group("key"): match.group("value") for match in PYPROJECT_URL_RE.finditer(pyproject_text)}
    for key, expected in EXPECTED_PROJECT_URLS.items():
        found = project_urls.get(key)
        if found != expected:
            errors.append(f"pyproject.toml {key} URL is {found or 'missing'}, expected {expected}")

    init_text = (REPO_ROOT / "indexpilot" / "__init__.py").read_text(encoding="utf-8")
    init_match = INIT_VERSION_RE.search(init_text)
    if init_match is None or init_match.group("version") != version:
        found = init_match.group("version") if init_match else "missing"
        errors.append(f"indexpilot/__init__.py version is {found}, expected {version}")

    changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {version} -" not in changelog_text:
        errors.append(f"CHANGELOG.md has no release heading for {version}")

    action_text = (REPO_ROOT / "action.yml").read_text(encoding="utf-8")
    if 'python -m pip install "${{ github.action_path }}"' not in action_text:
        errors.append("action.yml does not install the exact checked-out Action source")
    if 'python -m pip install "indexpilot==' in action_text:
        errors.append("action.yml still installs a hardcoded PyPI version")

    release_tag = os.environ.get("INDEXPILOT_RELEASE_TAG")
    if release_tag and release_tag != f"v{version}":
        errors.append(f"release tag is {release_tag}, expected v{version}")

    if errors:
        print("release-surface sync check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"release-surface sync check passed for version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
