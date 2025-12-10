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
# CRITICAL: This must run before any Unicode output to ensure proper encoding

# Set environment variables FIRST (before any imports that might use them)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

if sys.platform == "win32":
    # On Windows, force UTF-8 encoding
    import io
    
    # Reconfigure stdio streams to use UTF-8
    # This handles cases where the console encoding is not UTF-8
    # We use errors="replace" to prevent crashes, but ideally the terminal should be UTF-8
    try:
        # Only reconfigure if not already UTF-8
        if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except (AttributeError, ValueError, TypeError):
        # If stdout doesn't have a buffer or can't be reconfigured, continue
        pass
    
    try:
        if sys.stderr.encoding and sys.stderr.encoding.lower() not in ('utf-8', 'utf8'):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except (AttributeError, ValueError, TypeError):
        pass
    
    try:
        if sys.stdin.encoding and sys.stdin.encoding.lower() not in ('utf-8', 'utf8'):
            sys.stdin = io.TextIOWrapper(
                sys.stdin.buffer, encoding="utf-8", errors="replace"
            )
    except (AttributeError, ValueError, TypeError):
        pass

