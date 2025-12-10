# Project-specific bashrc for IndexPilot
# This file ensures UTF-8 encoding and venv activation
# It's sourced automatically when Git Bash starts in this project
# CRITICAL: Also sourced by AI shell for every command

# Set UTF-8 encoding environment variables (ensure they're always set)
# These MUST be exported so they're available to Python subprocesses
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
export PYTHONUNBUFFERED=1
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export LC_CTYPE=en_US.UTF-8

# Change to project directory if we're not already there
PROJECT_DIR="/c/Projects/indexpilot"
if [ -d "$PROJECT_DIR" ] && [ "$PWD" != "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR" 2>/dev/null || true
fi

# Activate venv if it exists
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi

