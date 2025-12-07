# Cursor IDE User Settings Sync Guide

**Date**: 07-12-2025  
**Issue**: Cursor IDE has separate user settings from workspace settings that may need configuration

---

## Problem

Cursor IDE has **two separate settings locations**:
1. **Workspace settings**: `.vscode/settings.json` (project-specific)
2. **User settings**: Cursor's global settings (applies to all workspaces)

The 'q' character bug and other terminal issues may require configuration in **both** locations, not just workspace settings.

---

## Cursor User Settings Location

**Windows:**
```
%APPDATA%\Cursor\User\settings.json
```

**Full path example:**
```
C:\Users\<YourUsername>\AppData\Roaming\Cursor\User\settings.json
```

**macOS:**
```
~/Library/Application Support/Cursor/User/settings.json
```

**Linux:**
```
~/.config/Cursor/User/settings.json
```

---

## How to Access Cursor User Settings

### Method 1: Command Palette (Recommended)

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type: `Preferences: Open User Settings (JSON)`
3. This opens Cursor's user settings file

### Method 2: Settings UI

1. Press `Ctrl+,` (or `Cmd+,` on Mac)
2. Click the `{}` icon in the top-right to open JSON view
3. This shows your user settings

### Method 3: Direct File Access

1. Navigate to the settings location above
2. Open `settings.json` in a text editor

---

## Required Cursor User Settings for 'q' Character Fix

Add these settings to your **Cursor user settings** (not workspace settings):

```json
{
  // Terminal configuration to prevent 'q' character bug
  "terminal.integrated.env.windows": {
    "TERM": "dumb"
  },
  
  // Disable problematic terminal features
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.enablePersistentSessions": true,
  
  // Cursor-specific agent terminal settings
  // These may help prevent agent from sending stray 'q' characters
  "cursor.terminal.useLegacyTool": false,
  "cursor.agent.terminal.enabled": true,
  
  // Alternative: Try disabling agent terminal integration if issue persists
  // "cursor.agent.terminal.enabled": false
}
```

---

## Complete Settings Sync Checklist

### Step 1: Check Cursor User Settings

1. Open Cursor user settings (Method 1 above)
2. Check if terminal settings exist
3. Compare with workspace settings in `.vscode/settings.json`

### Step 2: Add Missing Settings

Add any missing terminal settings from workspace to user settings, especially:
- `TERM=dumb`
- `terminal.integrated.shellIntegration.enabled`
- Terminal profile configurations

### Step 3: Verify Terminal Profile

Ensure your default terminal profile matches in both:
- User settings: `terminal.integrated.defaultProfile.windows`
- Workspace settings: `terminal.integrated.defaultProfile.windows`

**Note:** Some users report that using **Git Bash** instead of Command Prompt or PowerShell helps with the 'q' character issue.

### Step 4: Restart Cursor

After making changes:
1. **Close Cursor completely** (not just the window)
2. **Reopen Cursor**
3. **Close and reopen terminal** (`Ctrl+` `)

---

## Alternative: Change Default Terminal to Git Bash

If the issue persists, try changing the default terminal to Git Bash:

**In Cursor User Settings:**
```json
{
  "terminal.integrated.defaultProfile.windows": "Git Bash"
}
```

**In Workspace Settings (`.vscode/settings.json`):**
```json
{
  "terminal.integrated.defaultProfile.windows": "Git Bash"
}
```

Some users report this resolves the 'q' character issue.

---

## Cursor-Specific Terminal Settings

Cursor has some settings that don't exist in VSCode:

### Agent Terminal Integration

```json
{
  // Enable/disable Cursor's agent terminal integration
  "cursor.agent.terminal.enabled": true,
  
  // Use legacy terminal tool (if available in your Cursor version)
  "cursor.terminal.useLegacyTool": false
}
```

### Terminal Command Execution

```json
{
  // Timeout for agent-executed commands (in milliseconds)
  "cursor.agent.terminal.timeout": 300000,
  
  // Whether to show terminal output in chat
  "cursor.agent.terminal.showOutput": true
}
```

**Note:** These setting names may vary by Cursor version. Check Cursor's settings UI for exact names.

---

## Verification Steps

After syncing settings:

1. **Check User Settings:**
   - Open user settings (`Ctrl+Shift+P` > "Preferences: Open User Settings (JSON)")
   - Verify terminal settings are present

2. **Check Workspace Settings:**
   - Open `.vscode/settings.json`
   - Verify terminal settings match user settings where appropriate

3. **Test Terminal:**
   - Open new terminal (`Ctrl+` `)
   - Run: `echo %TERM%` (should show `dumb` on Windows)
   - Run: `python --version` (should NOT show `qpython`)

4. **Test After Stop/Skip:**
   - Use Cursor's stop/skip function
   - Run a command
   - Verify no 'q' character appears

---

## Troubleshooting

### Settings Not Applying

1. **Restart Cursor completely** (close all windows)
2. **Close and reopen terminal** after restart
3. **Check for syntax errors** in settings JSON
4. **Verify file location** - make sure you're editing the correct settings file

### Issue Persists After Sync

1. **Try Git Bash** as default terminal
2. **Disable agent terminal integration:**
   ```json
   {
     "cursor.agent.terminal.enabled": false
   }
   ```
3. **Use direct terminal** instead of AI assistant
4. **Update Cursor** to latest version (fixes are being released)

### Conflicting Settings

If user settings and workspace settings conflict:
- **Workspace settings override user settings** for that project
- Make sure both are configured consistently
- Or remove conflicting settings from one location

---

## Settings Priority

1. **Workspace settings** (`.vscode/settings.json`) - Highest priority for project
2. **User settings** (`%APPDATA%\Cursor\User\settings.json`) - Applies to all workspaces
3. **Default settings** - Cursor defaults

**Best Practice:** Configure terminal settings in **both** locations to ensure consistency.

---

## Related Documentation

- `CURSOR_TERMINAL_Q_CHARACTER_FIX.md` - Main fix guide
- `CURSOR_TERMINAL_TIMEOUT_FIX.md` - Timeout issues
- `WINDOWS_UNICODE_FIX.md` - Encoding issues

---

## Conclusion

**The 'q' character bug may require configuration in both:**
1. **Workspace settings** (`.vscode/settings.json`) - Already configured
2. **Cursor user settings** - May need to be configured separately

**Action Items:**
1. Open Cursor user settings
2. Add terminal configuration (especially `TERM=dumb`)
3. Consider changing default terminal to Git Bash
4. Restart Cursor completely
5. Test terminal commands

**This is a Cursor IDE-specific issue that requires Cursor user settings configuration, not just workspace settings.**

---

**Last Updated**: 07-12-2025

