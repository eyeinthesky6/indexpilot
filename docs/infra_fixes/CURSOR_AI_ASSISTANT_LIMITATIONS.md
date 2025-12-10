# Cursor AI Assistant Terminal Limitations

**Date**: 07-12-2025  
**Status**: Known Limitation - No Workaround Available

---

## The Problem

Cursor's AI assistant terminal tool (`run_terminal_cmd`) has **hardcoded limitations** that cannot be overridden with settings:

1. **5-10 Second Timeout**: Commands are automatically canceled after 5-10 seconds
2. **'q' Character Bug**: Terminal escape sequences cause commands to be prepended with 'q'
3. **No Configurable Timeout**: Settings like `EXECUTION_TIMEOUT_MS` don't actually work
4. **Legacy Terminal Tool**: Doesn't solve the timeout issue

**This is a Cursor IDE limitation, not a bug in IndexPilot.**

---

## What We've Tried (And Why They Don't Work)

### ❌ Settings That Don't Work:
- `terminal.integrated.commandTimeout: 0` - Doesn't affect AI assistant
- `EXECUTION_TIMEOUT_MS` environment variable - Not recognized by Cursor's MCP
- `TERM=dumb` - Helps with 'q' bug but not timeout
- Legacy Terminal Tool - Already enabled, doesn't help
- `.cursor/rules` - AI can't override MCP timeout

### ✅ What Actually Works:
- **Run commands directly in terminal** (bypasses AI assistant completely)
- **Use batch scripts with output redirection** (allows completion even if canceled)

---

## Practical Workarounds

### Workaround 1: Direct Terminal (Recommended)

**For any command that takes > 10 seconds:**

1. Open terminal directly: `Ctrl+` ` (backtick)
2. Run command directly (not through AI assistant)
3. Command will complete normally

**This is the ONLY reliable solution for long-running commands.**

---

### Workaround 2: Batch Script with Logging

**Created `run-simulation.bat` for simulations:**

```bash
# In direct terminal (not AI assistant):
run-simulation.bat medium
```

**Benefits:**
- Output saved to `logs/` directory
- Can check results even if terminal closes
- Works independently of AI assistant

---

### Workaround 3: AI Assistant for Short Commands Only

**Use AI assistant for:**
- ✅ Quick commands (< 10 seconds)
- ✅ Code changes
- ✅ File operations
- ✅ Status checks

**Don't use AI assistant for:**
- ❌ Long-running simulations
- ❌ Build processes
- ❌ Tests that take > 10 seconds
- ❌ Any command that needs to run to completion

---

## Recommended Workflow

### For Development:
1. **Use AI assistant** for code changes, quick checks, file operations
2. **Use direct terminal** for:
   - Running simulations
   - Running tests
   - Building/deploying
   - Any long-running process

### For Simulations Specifically:
```bash
# Step 1: Open terminal directly (Ctrl+`)
# Step 2: Run simulation
python -u -m src.simulator comprehensive --scenario medium

# Or use batch script with logging:
run-simulation.bat medium
```

---

## Why This Limitation Exists

Cursor's AI assistant uses **MCP (Model Context Protocol)** tools which have built-in timeouts to prevent:
- AI from hanging on long-running commands
- Resource exhaustion
- Unresponsive UI

**These timeouts are hardcoded and cannot be configured.**

---

## Comparison with VSCode

**VSCode:**
- No AI assistant terminal tool
- All commands run directly in terminal
- No timeout limitations
- Works perfectly for long-running commands

**Cursor:**
- AI assistant terminal tool has 5-10 second timeout
- Direct terminal works fine (same as VSCode)
- AI assistant is great for quick operations
- For long operations, use direct terminal

---

## Best Practice

**Think of Cursor's AI assistant as:**
- ✅ Great for code assistance
- ✅ Great for quick commands
- ❌ Not suitable for long-running processes

**For long-running processes:**
- Use the terminal directly (just like you would in VSCode)
- This is the same workflow you'd use in any IDE

---

## Summary

**The limitation:**
- Cursor AI assistant terminal tool has a 5-10 second hardcoded timeout
- This cannot be changed with settings
- This is by design to prevent AI from hanging

**The solution:**
- Use direct terminal for long-running commands
- Use AI assistant for quick operations
- This is the same workflow as VSCode

**It's not a bug - it's a limitation we work around by using the terminal directly.**

---

**Last Updated**: 07-12-2025

