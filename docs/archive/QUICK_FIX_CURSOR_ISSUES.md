# Quick Fix: Cursor IDE Issues

## Two Issues You're Experiencing

1. **'q' Character Bug**: Commands show `qpython` instead of `python`
2. **5-10 Second Timeout**: Commands cancelled automatically

## Quick Fix (5 Minutes)

### Step 1: Configure Cursor User Settings

1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Add this:

```json
{
  "terminal.integrated.env.windows": {
    "TERM": "dumb",
    "EXECUTION_TIMEOUT_MS": "300000"
  },
  "terminal.integrated.defaultProfile.windows": "Command Prompt",
  "terminal.integrated.shellIntegration.enabled": true,
  "cursor.terminal.useLegacyTool": true
}
```

4. Save (`Ctrl+S`)
5. **Restart Cursor completely** (close all windows)

### Step 2: For Simulations - Use Direct Terminal

**Important:** Even with settings, long commands (> 10 seconds) MUST run in direct terminal:

1. Press `Ctrl+` ` (backtick) to open terminal
2. Run command directly:
   ```bash
   python -u -m src.simulator comprehensive --scenario small
   ```

**This bypasses the AI assistant timeout completely.**

---

## Why This Happens

- **'q' Bug**: Terminal escape sequences misinterpreted → Fixed with `TERM=dumb`
- **Timeout**: Cursor AI assistant has hardcoded 5-10 second limit → **Cannot be fixed**, use direct terminal

---

## What's Already Done

✅ Workspace settings (`.vscode/settings.json`) configured
✅ Batch scripts (`run-simulation.bat`) created
✅ Documentation created

---

## Test It

```bash
# In direct terminal (Ctrl+`):
python --version
# Should show: Python 3.x.x (NOT qpython)

python -u -m src.simulator comprehensive --scenario small
# Should complete successfully (~2 minutes)
```

---

## Full Documentation

- `CURSOR_TIMEOUT_FIX.md` - Complete guide
- `CURSOR_Q_BUG_FIX.md` - 'q' character fix
- `docs/installation/CURSOR_TERMINAL_TIMEOUT_FIX.md` - Detailed timeout info

---

**Remember:** For simulations, always use direct terminal (`Ctrl+` `), not AI assistant.



