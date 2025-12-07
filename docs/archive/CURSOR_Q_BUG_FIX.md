# Cursor 'q' Character Bug - Fix Instructions

## Problem
Commands executed in Cursor IDE are being prepended with 'q' character (e.g., `qpython` instead of `python`). This is a known Cursor IDE bug.

## Root Cause
This happens because:
1. Cursor IDE has a bug where terminal escape sequences are misinterpreted
2. Using "stop" or "skip" in Cursor causes the next command to be prepended with 'q'
3. The AI assistant's terminal integration layer adds the 'q' character

## Solution (CRITICAL - Do This Now!)

### Step 1: Configure Cursor User Settings

**⚠️ IMPORTANT:** Cursor has separate user settings that MUST be configured. Workspace settings alone are not enough.

1. **Open Cursor User Settings:**
   - Press `Ctrl+Shift+P`
   - Type: `Preferences: Open User Settings (JSON)`
   - Press Enter

2. **Add these settings to the JSON file:**

```json
{
  "terminal.integrated.env.windows": {
    "TERM": "dumb"
  },
  "terminal.integrated.defaultProfile.windows": "Command Prompt",
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.enablePersistentSessions": true
}
```

3. **Save the file** (`Ctrl+S`)

### Step 2: Restart Cursor

1. **Close Cursor completely** (close all windows, not just minimize)
2. **Reopen Cursor**
3. **Close and reopen terminal** (`Ctrl+` `)

### Step 3: Verify Fix

Run this command:
```bash
python --version
```

Should show: `Python 3.x.x` (NOT `qpython`)

## Alternative Solutions

### Option 1: Use Git Bash Terminal

If Command Prompt doesn't work, try Git Bash:

In Cursor User Settings, change:
```json
{
  "terminal.integrated.defaultProfile.windows": "Git Bash"
}
```

### Option 2: Use Direct Terminal (Workaround)

For critical commands, use Cursor's terminal directly instead of AI assistant:
1. Press `Ctrl+` ` to open terminal
2. Type commands directly (not through AI)
3. This bypasses the bug entirely

### Option 3: Restart Terminal After Stop/Skip

If you use Cursor's "stop" or "skip" functions:
1. Close the terminal (`Ctrl+Shift+` `)
2. Open a new terminal (`Ctrl+` `)
3. This prevents the 'q' character from appearing

## What's Already Configured

✅ Workspace settings (`.vscode/settings.json`) are configured with:
- Terminal stability settings
- `TERM=dumb` environment variable
- Command Prompt profile configuration

## Additional Resources

- Full documentation: `docs/installation/CURSOR_TERMINAL_Q_CHARACTER_FIX.md`
- User settings sync guide: `docs/installation/CURSOR_USER_SETTINGS_SYNC.md`

## Why This Works

Setting `TERM=dumb` disables cursor style sequences (`ESC [ 1 q`) that Cursor uses, preventing the terminal from misinterpreting them as the 'q' character.

**Note:** This may disable some terminal features like cursor shape changes, but it fixes the command execution bug.

## Still Having Issues?

1. **Update Cursor:** `Help > Check for Updates`
2. **Try Git Bash** as default terminal
3. **Disable agent terminal integration** (if available in your Cursor version)
4. **Use direct terminal** for all commands
5. **Report to Cursor support** with your Cursor version and OS

---

**This is a Cursor IDE bug, not an issue with your code or IndexPilot.**



