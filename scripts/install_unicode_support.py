#!/usr/bin/env python3
"""Install Unicode/UTF-8 support at workspace level

This script installs sitecustomize.py in the virtual environment to ensure
UTF-8 encoding is set globally for all Python processes, eliminating the need
for file-level encoding fixes.
"""

import os
import shutil
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sitecustomize_source = project_root / "sitecustomize.py"

# Determine venv location
venv_lib = None
if Path("venv/Lib/site-packages").exists():
    venv_lib = Path("venv/Lib/site-packages")
elif Path("venv/lib").exists():
    # Find the Python version directory
    for item in Path("venv/lib").iterdir():
        if item.is_dir() and item.name.startswith("python"):
            venv_lib = item / "site-packages"
            break

if not venv_lib or not venv_lib.exists():
    print("[ERROR] Virtual environment not found. Please create a venv first.")
    print("   Run: python -m venv venv")
    sys.exit(1)

sitecustomize_dest = venv_lib / "sitecustomize.py"

if not sitecustomize_source.exists():
    print(f"[ERROR] Source file not found: {sitecustomize_source}")
    sys.exit(1)

try:
    shutil.copy2(sitecustomize_source, sitecustomize_dest)
    print(f"[SUCCESS] Installed sitecustomize.py to: {sitecustomize_dest}")
    print("   UTF-8 encoding is now set globally for all Python processes in this venv.")
    print("   No file-level encoding changes needed!")
except Exception as e:
    print(f"[ERROR] Failed to install sitecustomize.py: {e}")
    sys.exit(1)

