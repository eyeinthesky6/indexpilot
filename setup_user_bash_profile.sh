#!/bin/bash
# Script to add auto-sourcing of project .bashrc to user's ~/.bash_profile
# This ensures project-specific setup runs automatically

USER_BASH_PROFILE="$HOME/.bash_profile"
MARKER="# IndexPilot auto-source project .bashrc"
SETUP_CODE="
$MARKER
# Auto-source project-specific .bashrc if it exists
if [ -f .bashrc ] && [ -r .bashrc ]; then
    source .bashrc
fi
"

# Check if marker already exists
if [ -f "$USER_BASH_PROFILE" ] && grep -q "$MARKER" "$USER_BASH_PROFILE"; then
    echo "✓ Auto-source code already exists in ~/.bash_profile"
    exit 0
fi

# Append the setup code
echo "$SETUP_CODE" >> "$USER_BASH_PROFILE"
echo "✓ Added auto-source code to ~/.bash_profile"
echo "  Restart your terminal or run: source ~/.bash_profile"

