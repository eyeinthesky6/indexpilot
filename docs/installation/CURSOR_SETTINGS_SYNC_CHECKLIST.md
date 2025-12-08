# Cursor Terminal Settings Sync Checklist

**Date**: 07-12-2025  
**Quick Reference**: Check all settings are synchronized

---

## ✅ Workspace Settings (`.vscode/settings.json`)

**Status:** ✅ Already configured

**Required Settings:**
- [x] `EXECUTION_TIMEOUT_MS`: `"300000"`
- [x] `defaultProfile.windows`: `"Git Bash"`
- [x] `automationProfile.windows`: `"Git Bash"`
- [x] `shellIntegration.enabled`: `true`
- [x] `enablePersistentSessions`: `true`
- [x] `commandTimeout`: `0`
- [x] `killOnExit`: `"never"`

---

## ⚠️ Cursor User Settings (YOU MUST DO THIS)

**Location:** `%APPDATA%\Cursor\User\settings.json`  
**How to access:** `Ctrl+Shift+P` > "Preferences: Open User Settings (JSON)"

**Required Settings:**
- [ ] `terminal.integrated.env.windows.EXECUTION_TIMEOUT_MS`: `"300000"`
- [ ] `cursor.terminal.useLegacyTool`: `true`
- [ ] `terminal.integrated.defaultProfile.windows`: `"Git Bash"`
- [ ] `terminal.integrated.automationProfile.windows`: `"Git Bash"`
- [ ] `terminal.integrated.shellIntegration.enabled`: `true`
- [ ] `terminal.integrated.enablePersistentSessions`: `true`

**Copy this to User Settings (Git Bash is default, not CMD):**
```json
{
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  },
  "terminal.integrated.defaultProfile.windows": "Git Bash",
  "terminal.integrated.automationProfile.windows": "Git Bash",
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.enablePersistentSessions": true,
  "terminal.integrated.commandTimeout": 0,
  "terminal.integrated.killOnExit": "never",
  "cursor.terminal.useLegacyTool": true
}
```

**Note:** `defaultProfile.windows` is set to `"Git Bash"` (not `"Command Prompt"`). This ensures Bash is the default terminal.

---

## ⚠️ System Environment Variable (YOU MUST DO THIS)

**How to set:**
1. Run `set-execution-timeout.bat` as Administrator, OR
2. Press `Win+R`, type `sysdm.cpl`, go to Environment Variables, add:
   - Name: `EXECUTION_TIMEOUT_MS`
   - Value: `300000`

**Verify:**
- [ ] Open new terminal in Cursor
- [ ] Run: `echo $EXECUTION_TIMEOUT_MS` (Git Bash) or `echo %EXECUTION_TIMEOUT_MS%` (CMD)
- [ ] Should output: `300000`

---

## 🔄 Sync Steps

1. [ ] **Set Cursor User Settings** (see above)
2. [ ] **Set System Environment Variable** (run `set-execution-timeout.bat` or use GUI)
3. [ ] **Restart Cursor completely** (close all windows)
4. [ ] **Open new terminal** (`Ctrl+` `)
5. [ ] **Verify environment variable** (`echo $EXECUTION_TIMEOUT_MS`)
6. [ ] **Test with long command:**
   ```bash
   python -c "import time; print('Test'); time.sleep(10); print('Done')"
   ```

---

## 📋 Complete Settings Reference

See `SYNC_CURSOR_TERMINAL_SETTINGS.md` for detailed instructions.

---

**Last Updated**: 07-12-2025

