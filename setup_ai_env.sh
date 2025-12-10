#!/bin/bash
# Setup script for AI shell - ensures Unicode and venv are always set
# This should be sourced before running Python commands in AI shell

# Always set UTF-8 encoding environment variables
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export LC_CTYPE=en_US.UTF-8

# Change to project directory
cd /c/Projects/indexpilot 2>/dev/null || true

# Activate venv if it exists
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi

