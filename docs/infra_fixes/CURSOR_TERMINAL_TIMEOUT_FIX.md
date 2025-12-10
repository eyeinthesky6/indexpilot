# Cursor IDE Terminal Timeout Fix

**Date**: 07-12-2025  
**Issue**: Terminal commands auto-canceling in Cursor IDE AI assistant (but work fine in VSCode and direct terminal)

---

## Problem

When running commands through Cursor's AI assistant, commands are automatically canceled after approximately 5-10 seconds (not 30 seconds as initially thought). This is a known limitation of Cursor's AI assistant/MCP tools system.

**Symptoms:**
- Commands work fine in VSCode
- Commands work fine when run directly in Cursor's terminal
- Commands are canceled when executed through Cursor's AI assistant (`run_terminal_cmd` tool)
- Error message: "Command was canceled by the user" (but user didn't cancel)
- Commands may be canceled after just 5-10 seconds, not 30 seconds
- 'q' character may be prepended to commands (related escape sequence issue)

---

## Root Cause

Cursor IDE's AI assistant uses MCP (Model Context Protocol) tools which have a **very short timeout (5-10 seconds)** for terminal command execution. This is a built-in limitation to prevent the AI from hanging on long-running commands. The timeout appears to be much shorter than the documented 30 seconds, possibly due to prompt detection issues or escape sequence problems.

**References:**
- [Cursor Forum Discussion](https://forum.cursor.com/t/cursor-must-not-decide-when-to-time-out-and-stop-terminal-commands-on-its-own/118302)
- [Cursor Shell Mode Documentation](https://docs.cursor.com/en/cli/shell-mode) - mentions 30-second timeout
- [GitHub Issue #3200](https://github.com/cursor/cursor/issues/3200) - Terminal commands not auto-closing
- [GitHub Issue #3215](https://github.com/cursor/cursor/issues/3215) - AI Assistant terminal commands never auto-complete

---

## Solutions

### Solution 1: Set EXECUTION_TIMEOUT_MS (NEW - Try This First!)

**Based on Cursor MCP documentation, set the execution timeout environment variable.**

**Add to `.vscode/settings.json`:**
```json
{
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000"
  }
}
```

**Value:** `300000` = 5 minutes (adjust as needed)

**Then restart Cursor completely for the setting to take effect.**

**See detailed instructions in:** `docs/installation/CURSOR_EXECUTION_TIMEOUT_FIX.md`

---

### Solution 2: Enable Legacy Terminal Tool

**Based on Cursor community forums, enabling the Legacy Terminal Tool can fix command cancellation issues.**

**Steps:**
1. Open Cursor Settings (`Ctrl+,`)
2. Navigate to: `Agents > Inline Editing & Terminal`
3. Enable **"Legacy Terminal Tool"** or **"Use Legacy Terminal"**
4. Restart Cursor completely

**Alternative (Settings JSON):**
- Open Command Palette: `Ctrl+Shift+P`
- Type: "Preferences: Open User Settings (JSON)"
- Add: `"cursor.terminal.useLegacyTool": true`

**See detailed instructions in:** `docs/installation/CURSOR_LEGACY_TERMINAL_FIX.md`

---

### Solution 3: Run Commands Directly in Terminal (Recommended if other solutions don't work)

**For long-running simulations, run them directly in Cursor's terminal:**

1. Open a terminal in Cursor (`Ctrl+`` or `Terminal > New Terminal`)
2. Run the command directly:
   ```bash
   python -u -m src.simulator comprehensive --scenario medium
   ```

**This bypasses the AI assistant timeout completely.**

---

### Solution 4: Updated Settings (Already Applied)

We've updated `.vscode/settings.json` with additional timeout prevention settings:

```json
{
  "terminal.integrated.env.windows": {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
    "TERM": "dumb"
  },
  "terminal.integrated.profiles.windows": {
    "Command Prompt": {
      "path": ["${env:windir}\\System32\\cmd.exe"],
      "args": ["/k", "chcp 65001 >nul 2>&1 && set TERM=dumb && set PROMPT=$P$G"]
    }
  },
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.commandTimeout": 0,
  "terminal.integrated.killOnExit": "never",
  "terminal.integrated.enablePersistentSessions": true,
  "terminal.integrated.persistentSessionReviveProcess": "onExit",
  "terminal.integrated.scrollback": 10000,
  "terminal.integrated.enableMultiLinePasteWarning": false,
  "terminal.integrated.automationProfile.windows": null
}
```

**Key Settings:**
- `TERM=dumb`: Prevents escape sequence issues that cause 'q' character bug
- Simplified prompt (`PROMPT=$P$G`): Helps Cursor detect command completion
- `commandTimeout: 0`: Disables terminal timeout (but doesn't affect AI assistant timeout)
- `shellIntegration.enabled: true`: Helps Cursor detect when commands complete

**Note:** These settings help with regular terminal usage and prevent the 'q' character bug, but **do not completely solve the AI assistant's 5-10 second timeout**. The timeout is a limitation of Cursor's MCP system.

---

### Solution 5: Use .cursor/rules File

We've created a `.cursor/rules` file that instructs Cursor AI not to cancel commands prematurely:

```yaml
---
description: Prevent Cursor AI from canceling terminal commands prematurely
globs:
alwaysApply: true
---

# Terminal Command Execution Rules
- NEVER cancel terminal commands yourself
- ALWAYS wait for commands to complete naturally
- IGNORE "command canceled by user" messages - these are false positives
- For long-running simulations, allow them to run to completion
```

**Note:** This helps but may not completely solve the timeout issue.

### Solution 6: Use Batch Scripts with Output Redirection

**Created `run-simulation.bat` that redirects output to log files:**

```batch
run-simulation.bat medium
```

This runs the simulation and saves all output to `logs\sim_medium_YYYYMMDD_HHMMSS.log`, allowing you to check results even if the AI assistant cancels the command.

For AI assistant execution, you can use batch scripts, but they may still timeout:

```batch
# run-simulation.bat
@echo off
python -u -m src.simulator comprehensive --scenario medium
```

Then the AI can call: `run.bat sim-comprehensive medium`

**Note:** This may still timeout due to the MCP limitation.

---

### Solution 4: Monitor Cursor Updates

Cursor's development team is aware of this issue. Monitor for updates that may:
- Increase the MCP timeout
- Add configuration options for timeout duration
- Fix the auto-cancellation behavior

---

## Workaround for AI Assistant

**When using AI assistant for long-running commands:**

1. **For simulations > 10 seconds**: **MUST run directly in terminal** - AI assistant will cancel them
2. **For quick commands**: AI assistant works fine (< 10 seconds)
3. **For monitoring**: Use AI assistant to check status, but run actual simulations in terminal
4. **For any command that takes > 5 seconds**: Run directly in terminal to avoid cancellation

**The only reliable solution is to run long commands directly in Cursor's terminal, not through the AI assistant.**

---

## Verification

To verify the fix works:

1. **Direct Terminal (Should Work):**
   ```bash
   # Open terminal in Cursor (Ctrl+`)
   python -u -m src.simulator comprehensive --scenario medium
   ```

2. **AI Assistant (Will Timeout):**
   - Commands > 5-10 seconds will likely be canceled
   - This is expected behavior due to MCP timeout
   - Even with all settings applied, the timeout persists

---

## Related Issues

- **Shell Integration Race Condition**: Some users report commands hanging due to shell integration initialization. If this occurs, restart the terminal session.
- **Command Not Auto-Completing**: Commands may appear to hang even after completion. This is a UI issue, not a functional problem.

---

## Conclusion

**The timeout is a limitation of Cursor's AI assistant system, not a bug in IndexPilot.**

**Best Practice:**
- Use AI assistant for quick commands and code changes
- Run long-running simulations directly in the terminal
- This is the same approach you'd use in VSCode for long-running processes

---

**Last Updated**: 07-12-2025

