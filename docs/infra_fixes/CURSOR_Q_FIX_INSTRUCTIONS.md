# Quick Fix for Cursor 'q' Character Bug

## Immediate Fix Required

The 'q' character bug in Cursor IDE requires configuration in **Cursor User Settings** (not just workspace settings).

### Step 1: Open Cursor User Settings

1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Press Enter

### Step 2: Add These Settings

Add the following to your Cursor user settings JSON file:

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

### Step 3: Restart Cursor

1. **Close Cursor completely** (close all windows)
2. **Reopen Cursor**
3. **Close and reopen terminal** (`Ctrl+` `)

### Step 4: Test

Run this command to verify:
```bash
python --version
```

Should show: `Python 3.x.x` (NOT `qpython`)

## Alternative: Use Git Bash

If the issue persists, try changing to Git Bash:

In Cursor User Settings, change:
```json
{
  "terminal.integrated.defaultProfile.windows": "Git Bash"
}
```

## Why This Happens

This is a known Cursor IDE bug where:
- Terminal escape sequences (`ESC [ 1 q`) are misinterpreted
- Using "stop" or "skip" in Cursor causes the next command to be prepended with 'q'
- The AI assistant's terminal integration layer adds the 'q' character

## Workaround: Use Direct Terminal

For critical commands, use Cursor's terminal directly instead of the AI assistant:
1. Press `Ctrl+` ` to open terminal
2. Type commands directly (not through AI)
3. This bypasses the bug entirely

## More Information

See `docs/installation/CURSOR_TERMINAL_Q_CHARACTER_FIX.md` for complete details.



