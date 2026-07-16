"""Locate the prebuilt dashboard files bundled with the Python package."""

from __future__ import annotations

from pathlib import Path


def dashboard_static_root() -> Path:
    """Return the package-owned static dashboard directory."""
    return Path(__file__).resolve().parent / "dashboard_static"


def dashboard_entry_path() -> Path:
    """Return the operator dashboard entry page."""
    return dashboard_static_root() / "dashboard" / "index.html"


def dashboard_assets_available() -> bool:
    """Report whether this installation contains a usable dashboard build."""
    return dashboard_entry_path().is_file()


def resolve_dashboard_asset(request_path: str) -> Path | None:
    """Resolve an existing static request path without allowing path traversal."""
    root = dashboard_static_root().resolve()
    relative_path = request_path.lstrip("/")
    if not relative_path or relative_path == "api" or relative_path.startswith("api/"):
        return None

    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None

    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate if candidate.is_file() else None
