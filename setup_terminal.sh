#!/bin/bash
# Terminal setup script for Unicode support and venv activation
# This script is sourced automatically when Git Bash starts in Cursor
# It ensures UTF-8 encoding and activates the virtual environment

# Set UTF-8 encoding environment variables (override any existing values)
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export LC_CTYPE=en_US.UTF-8

# Change to workspace directory if we're not already there
# This ensures relative paths work correctly
if [ -n "${workspaceFolder:-}" ] && [ -d "${workspaceFolder}" ]; then
    cd "${workspaceFolder}" 2>/dev/null || true
fi

# Activate venv if it exists (check current directory first, then workspace)
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -n "${workspaceFolder:-}" ] && [ -f "${workspaceFolder}/venv/Scripts/activate" ]; then
    source "${workspaceFolder}/venv/Scripts/activate"
fi

