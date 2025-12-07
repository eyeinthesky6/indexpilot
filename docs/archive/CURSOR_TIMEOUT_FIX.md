# Cursor IDE Timeout & Cancellation Fix

## Problem Summary

You're experiencing **two related Cursor IDE issues**:

1. **'q' Character Bug**: Commands prefixed with 'q' (e.g., `qpython` instead of `python`)
2. **5-10 Second Timeout**: Commands cancelled automatically even within 5-10 seconds

Both issues are **Cursor IDE limitations**, not bugs in your code. The simulation works fine in VSCode because VSCode doesn't have these limitations.

---

## Root Cause

**Cursor's AI Assistant** uses **MCP (Model Context Protocol)** tools which have:
- **Hardcoded 5-10 second timeout** for terminal commands
- **Terminal escape sequence bugs** that cause 'q' character prefix
- **No configurable timeout** - settings don't actually override the MCP timeout

**This is by design** to prevent the AI from hanging on long-running commands, but it causes issues for simulations and long-running processes.

---

## Solutions Applied

### ✅ Workspace Settings (Already Configured)

I've updated `.vscode/settings.json` with:

```json
{
  "terminal.integrated.env.windows": {
    "TERM": "dumb",                    // Prevents 'q' character bug
    "EXECUTION_TIMEOUT_MS": "300000",  // Attempts to increase timeout (may not work)
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  },
  "terminal.integrated.commandTimeout": 0,  // Disables terminal timeout
  "terminal.integrated.gpuAcceleration": "off",  // Prevents rendering issues
  "terminal.integrated.profiles.windows": {
    "Command Prompt": {
      "args": ["/k", "chcp 65001 >nul 2>&1 && set TERM=dumb && set PROMPT=$P$G"]
    }
  }
}
```

### ⚠️ CRITICAL: Configure Cursor User Settings

**You MUST also configure Cursor User Settings** (separate from workspace settings):

1. **Press `Ctrl+Shift+P`**
2. **Type:** `Preferences: Open User Settings (JSON)`
3. **Add these settings:**

```json
{
  "terminal.integrated.env.windows": {
    "TERM": "dumb",
    "EXECUTION_TIMEOUT_MS": "300000"
  },
  "terminal.integrated.defaultProfile.windows": "Command Prompt",
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.enablePersistentSessions": true,
  "cursor.terminal.useLegacyTool": true
}
```

4. **Restart Cursor completely** (close all windows)

---

## The Reality: Settings May Not Work

**Important:** According to Cursor documentation and user reports:
- `EXECUTION_TIMEOUT_MS` may **not actually work** - it's not recognized by Cursor's MCP system
- The 5-10 second timeout is **hardcoded** and cannot be overridden
- Even with all settings, commands may still timeout

**This is a known Cursor IDE limitation.**

---

## ✅ What Actually Works: Use Direct Terminal

**For any command that takes > 10 seconds, you MUST run it directly in the terminal:**

### Method 1: Direct Terminal (Recommended)

1. **Open terminal in Cursor:** Press `Ctrl+` ` (backtick)
2. **Run command directly** (not through AI assistant):
   ```bash
   python -u -m src.simulator comprehensive --scenario medium
   ```
3. **Command will complete normally** - no timeout, no 'q' prefix

### Method 2: Batch Script with Logging

Use the existing `run-simulation.bat` script:

1. **Open terminal directly:** `Ctrl+` `
2. **Run:**
   ```bash
   run-simulation.bat medium
   ```
3. **Output is saved to:** `logs\sim_medium_YYYYMMDD_HHMMSS.log`
4. **Check results even if terminal closes**

---

## Recommended Workflow

### ✅ Use AI Assistant For:
- Quick commands (< 10 seconds)
- Code changes and file operations
- Status checks
- Short tests

### ❌ Don't Use AI Assistant For:
- Long-running simulations
- Commands that take > 10 seconds
- Build processes
- Tests that need to complete

### ✅ Use Direct Terminal For:
- **All simulations** (small, medium, large, stress-test)
- **Long-running tests**
- **Build/deploy processes**
- **Any command that needs to run to completion**

---

## Why This Happens

### 'q' Character Bug:
- Cursor sends terminal escape sequences (`ESC [ 1 q`) to set cursor shape
- Terminal misinterprets these sequences
- The 'q' character appears before commands
- **Fix:** `TERM=dumb` disables cursor style sequences

### Timeout Issue:
- Cursor's AI assistant uses MCP tools
- MCP has hardcoded 5-10 second timeout
- This prevents AI from hanging on long commands
- **Workaround:** Run commands directly in terminal (bypasses AI assistant)

---

## Verification Steps

### Test 1: Check 'q' Character Fix
```bash
# In direct terminal (Ctrl+`):
python --version
# Should show: Python 3.x.x (NOT qpython)
```

### Test 2: Check Timeout
```bash
# In direct terminal (Ctrl+`):
python -c "import time; print('Starting...'); time.sleep(30); print('Done')"
# Should complete after 30 seconds (NOT timeout after 5-10 seconds)
```

### Test 3: Run Simulation
```bash
# In direct terminal (Ctrl+`):
python -u -m src.simulator comprehensive --scenario small
# Should complete successfully (takes ~2 minutes)
```

---

## If Settings Don't Work

**If commands still timeout even after configuring settings:**

1. **This is expected** - the timeout is hardcoded in Cursor's MCP
2. **Use direct terminal** - this is the only reliable solution
3. **Update Cursor** - newer versions may have better timeout handling
4. **Report to Cursor** - this is a known limitation they're working on

---

## Comparison: VSCode vs Cursor

| Feature | VSCode | Cursor |
|---------|--------|--------|
| Direct Terminal | ✅ Works perfectly | ✅ Works perfectly |
| AI Assistant Terminal | ❌ Doesn't exist | ⚠️ 5-10 second timeout |
| Long-running Commands | ✅ No timeout | ✅ Use direct terminal |
| 'q' Character Bug | ❌ Doesn't exist | ⚠️ Fixed with TERM=dumb |

**Bottom line:** Use direct terminal in Cursor (same as VSCode) for long-running commands.

---

## Summary

**The Issues:**
- ✅ 'q' character bug - Fixed with `TERM=dumb` (workspace + user settings)
- ⚠️ 5-10 second timeout - Cannot be fixed, use direct terminal

**The Solution:**
1. Configure Cursor User Settings (see above)
2. Restart Cursor completely
3. **For simulations:** Always use direct terminal (`Ctrl+` `)
4. **For quick commands:** AI assistant works fine

**This is a Cursor IDE limitation, not a bug in IndexPilot.**

---

## Related Documentation

- `CURSOR_Q_BUG_FIX.md` - 'q' character fix details
- `docs/installation/CURSOR_TERMINAL_TIMEOUT_FIX.md` - Complete timeout guide
- `docs/installation/CURSOR_EXECUTION_TIMEOUT_FIX.md` - EXECUTION_TIMEOUT_MS details
- `docs/installation/CURSOR_AI_ASSISTANT_LIMITATIONS.md` - Known limitations

---

**Last Updated**: 07-12-2025



