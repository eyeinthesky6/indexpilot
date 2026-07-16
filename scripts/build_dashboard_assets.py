"""Build the Next.js operator UI and copy its static export into the Python package."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "ui"
EXPORT_ROOT = UI_ROOT / "out"
PACKAGE_ROOT = ROOT / "indexpilot"
TARGET_ROOT = PACKAGE_ROOT / "dashboard_static"


def main() -> int:
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm is required to build the bundled dashboard")

    env = os.environ.copy()
    env.pop("GITHUB_PAGES", None)
    env.pop("NEXT_PUBLIC_BASE_PATH", None)
    env["INDEXPILOT_BUNDLED_UI"] = "true"
    env["NEXT_PUBLIC_OPERATOR_UI"] = "enabled"
    subprocess.run([pnpm, "build"], cwd=UI_ROOT, env=env, check=True)

    entry = EXPORT_ROOT / "dashboard" / "index.html"
    if not entry.is_file():
        raise SystemExit(f"dashboard export is missing its entry page: {entry}")

    expected_target = (PACKAGE_ROOT / "dashboard_static").resolve()
    if TARGET_ROOT.resolve() != expected_target:
        raise SystemExit(f"refusing to replace unexpected dashboard target: {TARGET_ROOT}")
    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)
    shutil.copytree(EXPORT_ROOT, TARGET_ROOT)
    print(f"Bundled dashboard assets: {TARGET_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
