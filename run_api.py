#!/usr/bin/env python3
"""Compatibility wrapper for the installed ``indexpilot-api`` command."""

from indexpilot.cli import api_main

if __name__ == "__main__":
    raise SystemExit(api_main(["--reload"]))
