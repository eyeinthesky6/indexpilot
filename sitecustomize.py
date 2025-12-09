"""Site-wide Python customization for IndexPilot

This file is automatically imported by Python on startup and sets UTF-8 encoding
globally for all Python processes. This ensures Unicode characters and emojis
work correctly throughout the application without requiring file-level changes.

Location: This file should be in the project root or in a directory on PYTHONPATH.
For virtual environments, place it in: venv/Lib/site-packages/sitecustomize.py
For system-wide: place it in Python's site-packages directory.
"""

import sys
import os

# Set UTF-8 encoding for stdin, stdout, stderr
if sys.platform == "win32":
    # On Windows, force UTF-8 encoding
    import io
    
    # Set default encoding to UTF-8
    if hasattr(sys, "setdefaultencoding"):
        sys.setdefaultencoding("utf-8")
    
    # Reconfigure stdio streams to use UTF-8
    # This handles cases where the console encoding is not UTF-8
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
        except (AttributeError, ValueError):
            pass
    
    if sys.stderr.encoding != "utf-8":
        try:
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
        except (AttributeError, ValueError):
            pass
    
    if sys.stdin.encoding != "utf-8":
        try:
            sys.stdin = io.TextIOWrapper(
                sys.stdin.buffer, encoding="utf-8", errors="replace"
            )
        except (AttributeError, ValueError):
            pass

# Set environment variables for subprocess calls
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

