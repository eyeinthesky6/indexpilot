# Windows Unicode Encoding Fix
**Date**: 06-12-2025  
**Issue**: Unicode encoding not working on Windows in Cursor IDE terminals

---

## Problem

On Windows, Python defaults to `cp1252` encoding for console output, causing Unicode errors when running Python scripts in Cursor IDE terminals.

---

## Root Cause

The issue occurs because:
1. Windows Command Prompt defaults to code page 850/437 (not UTF-8)
2. Python's `sys.stdout.encoding` defaults to the console's code page
3. Cursor/VSCode terminal environment variables may not be set correctly
4. Terminal needs to be configured to use UTF-8 code page

---

## Solution

### Option 1: Workspace Settings (Recommended)

Created `.vscode/settings.json` with UTF-8 configuration:

```json
{
  "terminal.integrated.env.windows": {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  },
  "terminal.integrated.profiles.windows": {
    "Command Prompt": {
      "path": ["${env:windir}\\System32\\cmd.exe"],
      "args": ["/k", "chcp 65001 >nul 2>&1"],
      "icon": "terminal-cmd"
    },
    "PowerShell": {
      "source": "PowerShell",
      "args": [
        "-NoExit",
        "-Command",
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONUTF8='1'"
      ],
      "icon": "terminal-powershell"
    },
    "Git Bash": {
      "path": ["${env:ProgramFiles}\\Git\\bin\\bash.exe"],
      "args": [],
      "env": {
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1"
      },
      "icon": "terminal-bash"
    }
  },
  "terminal.integrated.defaultProfile.windows": "Command Prompt",
  "files.encoding": "utf8",
  "files.autoGuessEncoding": true
}
```

**Important**: `.vscode/` is in `.gitignore`, so this file won't be tracked. You may need to:
- Remove `.vscode/` from `.gitignore` if you want to share settings
- Or configure it in user settings instead (see Option 2)

### Option 2: User Settings (Global)

Configure in Cursor's user settings (applies to all workspaces):

1. Open Cursor Settings (Ctrl+,)
2. Search for "terminal integrated env windows"
3. Add:
   - `PYTHONIOENCODING` = `utf-8`
   - `PYTHONUTF8` = `1`
4. Or edit `settings.json` directly:
   - Press `Ctrl+Shift+P`
   - Type "Preferences: Open User Settings (JSON)"
   - Add the configuration

### Option 3: Batch Script (Fallback)

The `run.bat` file has been updated with UTF-8 configuration:

```batch
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
```

This ensures UTF-8 encoding when using `run.bat` commands.

---

## Why It Wasn't Working

1. **Settings Location**: Configuration might have been in user settings, but terminal wasn't restarted
2. **Terminal Profile**: Terminal profile needs explicit UTF-8 code page configuration
3. **Environment Variables**: Variables need to be set before Python starts
4. **Terminal Restart**: Terminal must be restarted after changing settings

---

## Verification

After applying the fix, verify it's working:

```python
import sys
print(f"stdout encoding: {sys.stdout.encoding}")
print(f"default encoding: {sys.getdefaultencoding()}")
# Should output: utf-8 for both
```

Or test with Unicode characters:

```python
print("Test: 你好世界 🌍")
# Should display correctly without errors
```

---

## Troubleshooting

### Settings Not Applying

1. **Restart Terminal**: Close and reopen the terminal in Cursor
2. **Restart Cursor**: Fully restart Cursor IDE
3. **Check Settings**: Verify settings are in the correct location (workspace vs user)
4. **Check Terminal Profile**: Ensure the correct terminal profile is selected

### Still Getting Encoding Errors

1. **Check Python Version**: Python 3.7+ required for `PYTHONUTF8=1`
2. **Verify Environment Variables**: Run `echo %PYTHONIOENCODING%` in terminal
3. **Check Code Page**: Run `chcp` in terminal (should show 65001)
4. **Use Batch Script**: Fall back to using `run.bat` which has explicit configuration

---

## Files Modified

1. **`.vscode/settings.json`** - Created with UTF-8 terminal configuration
2. **`run.bat`** - Added UTF-8 encoding setup at start

---

## Notes

- `.vscode/` directory is in `.gitignore` by default
- If you want to share settings, remove `.vscode/` from `.gitignore`
- User settings apply globally, workspace settings apply only to this project
- Terminal must be restarted after changing settings

---

**Last Updated**: 06-12-2025

