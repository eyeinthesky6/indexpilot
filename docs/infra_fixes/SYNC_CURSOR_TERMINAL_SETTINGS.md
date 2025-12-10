# Complete Cursor Terminal Settings Sync Guide

**Date**: 07-12-2025  
**Purpose**: Keep all terminal settings synchronized across workspace, user settings, and system

---

## Overview

To fix immediate command cancellation, `EXECUTION_TIMEOUT_MS` must be set in **three places**:
1. ✅ Workspace settings (`.vscode/settings.json`) - Already done
2. ⚠️ Cursor User Settings - **YOU MUST DO THIS**
3. ⚠️ System Environment Variable - **YOU MUST DO THIS**

---

## Step 1: Set Cursor User Settings

### Method A: Via Settings UI

1. Press `Ctrl+,` (or `Cmd+,` on Mac)
2. Search for: `terminal.integrated.env.windows`
3. Click "Edit in settings.json"
4. Add the configuration below

### Method B: Via Command Palette (Recommended)

1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Press Enter
4. Add this configuration:

```json
{
  // Terminal timeout and environment settings
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  },
  
  // Terminal profiles - Git Bash is default (not Command Prompt)
  "terminal.integrated.defaultProfile.windows": "Git Bash",
  "terminal.integrated.automationProfile.windows": "Git Bash",
  
  // Terminal stability settings
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.enablePersistentSessions": true,
  "terminal.integrated.commandTimeout": 0,
  "terminal.integrated.killOnExit": "never",
  
  // Cursor-specific settings
  "cursor.terminal.useLegacyTool": true
}
```

5. **Save the file** (`Ctrl+S`)
6. **Restart Cursor completely** (close all windows)

---

## Step 2: Set System Environment Variable

### Method A: Using Windows GUI

1. Press `Win + R`
2. Type: `sysdm.cpl`
3. Press Enter
4. Click "Advanced" tab
5. Click "Environment Variables" button
6. Under "User variables", click "New"
7. Enter:
   - **Variable name:** `EXECUTION_TIMEOUT_MS`
   - **Variable value:** `300000`
8. Click OK on all dialogs
9. **Restart Cursor completely**

### Method B: Using PowerShell (Run as Administrator)

Open PowerShell as Administrator and run:

```powershell
[System.Environment]::SetEnvironmentVariable("EXECUTION_TIMEOUT_MS", "300000", "User")
```

Then restart Cursor.

### Method C: Using Command Prompt (Run as Administrator)

Open Command Prompt as Administrator and run:

```cmd
setx EXECUTION_TIMEOUT_MS "300000" /M
```

**Note:** `/M` sets it for all users. Remove `/M` for user-only.

Then restart Cursor.

---

## Step 3: Verify All Settings Are Synced

### Check Workspace Settings

File: `.vscode/settings.json`

Should contain:
```json
{
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  },
  "terminal.integrated.defaultProfile.windows": "Git Bash"
}
```

✅ **Already configured**

### Check Cursor User Settings

1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Verify these settings exist:
   - `terminal.integrated.env.windows.EXECUTION_TIMEOUT_MS` = `"300000"`
   - `cursor.terminal.useLegacyTool` = `true`
   - `terminal.integrated.defaultProfile.windows` = `"Git Bash"`

### Check System Environment Variable

**In Git Bash:**
```bash
echo $EXECUTION_TIMEOUT_MS
```
Should output: `300000`

**In Command Prompt:**
```cmd
echo %EXECUTION_TIMEOUT_MS%
```
Should output: `300000`

**In PowerShell:**
```powershell
$env:EXECUTION_TIMEOUT_MS
```
Should output: `300000`

---

## Step 4: Complete Settings Checklist

### Workspace Settings (`.vscode/settings.json`)
- ✅ `EXECUTION_TIMEOUT_MS`: `"300000"`
- ✅ `defaultProfile.windows`: `"Git Bash"`
- ✅ `automationProfile.windows`: `"Git Bash"`
- ✅ `shellIntegration.enabled`: `true`
- ✅ `enablePersistentSessions`: `true`
- ✅ `commandTimeout`: `0`
- ✅ `killOnExit`: `"never"`

### Cursor User Settings
- ⚠️ `EXECUTION_TIMEOUT_MS`: `"300000"` - **YOU MUST ADD THIS**
- ⚠️ `cursor.terminal.useLegacyTool`: `true` - **YOU MUST ADD THIS**
- ⚠️ `defaultProfile.windows`: `"Git Bash"` - **YOU MUST ADD THIS**
- ⚠️ `shellIntegration.enabled`: `true` - **YOU MUST ADD THIS**

### System Environment Variable
- ⚠️ `EXECUTION_TIMEOUT_MS` = `300000` - **YOU MUST ADD THIS**

---

## Step 5: Restart Everything

After making all changes:

1. **Close Cursor completely** (close all windows)
2. **Close all terminal windows**
3. **Reopen Cursor**
4. **Open a new terminal** (`Ctrl+` `)
5. **Verify environment variable:**
   ```bash
   echo $EXECUTION_TIMEOUT_MS
   ```
   Should show: `300000`

---

## Step 6: Test

Run a test command that takes more than a few seconds:

```bash
python -c "import time; print('Starting...'); time.sleep(10); print('Done after 10 seconds')"
```

**Expected:** Command runs for 10 seconds without cancellation.

**If cancelled:** Check that all three locations have `EXECUTION_TIMEOUT_MS` set.

---

## Troubleshooting

### Commands Still Cancelled Immediately

1. **Verify User Settings:**
   - Open User Settings JSON
   - Check `EXECUTION_TIMEOUT_MS` is set
   - Check `cursor.terminal.useLegacyTool` is `true`

2. **Verify System Environment:**
   - Open new terminal
   - Run: `echo $EXECUTION_TIMEOUT_MS` (or `%EXECUTION_TIMEOUT_MS%` in CMD)
   - Should show: `300000`
   - If not, restart Cursor after setting environment variable

3. **Check Legacy Terminal Tool:**
   - Settings > Agents > Inline Editing & Terminal
   - Should show "Legacy Terminal Tool" enabled

4. **Restart Cursor:**
   - Close completely
   - Reopen
   - Test again

### Environment Variable Not Showing

1. **Set it again** using one of the methods above
2. **Restart Cursor completely** (not just terminal)
3. **Open new terminal** (not existing one)
4. **Check again**

### Settings Not Applying

1. **Check JSON syntax** - No trailing commas, proper quotes
2. **Save files** - Make sure you saved User Settings JSON
3. **Restart Cursor** - Must restart after changes
4. **Check file location** - User Settings should be in `%APPDATA%\Cursor\User\settings.json`

---

## Quick Reference

### Cursor User Settings Location
**Windows:** `%APPDATA%\Cursor\User\settings.json`  
**Full path:** `C:\Users\<YourUsername>\AppData\Roaming\Cursor\User\settings.json`

### Workspace Settings Location
**Project:** `.vscode/settings.json`

### System Environment Variable
**User variables:** Set via `sysdm.cpl` or `setx` command

---

## Summary

**To fix immediate cancellation, you MUST:**

1. ✅ **Set EXECUTION_TIMEOUT_MS in Cursor User Settings** (Step 1)
2. ✅ **Set EXECUTION_TIMEOUT_MS as system environment variable** (Step 2)
3. ✅ **Enable Legacy Terminal Tool in User Settings** (Step 1)
4. ✅ **Restart Cursor completely** (Step 5)
5. ✅ **Test** (Step 6)

**Workspace settings alone are NOT enough!**

---

**Last Updated**: 07-12-2025

