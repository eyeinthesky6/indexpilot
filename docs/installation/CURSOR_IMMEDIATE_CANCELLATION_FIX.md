# Cursor IDE Commands Cancelled Within Seconds - Immediate Fix

**Date**: 07-12-2025  
**Issue**: Commands are being cancelled within seconds of execution (not tab switching)

---

## Problem

Terminal commands executed through Cursor's AI assistant are being **cancelled within seconds** of starting, not after 5-10 seconds. This indicates the MCP timeout is even shorter than expected, or command detection is failing immediately.

**Symptoms:**
- Commands cancelled within 1-3 seconds
- Not related to tab switching
- Commands work fine in direct terminal
- Error: "Command was canceled by the user" appears almost immediately

---

## Root Cause

**The MCP timeout is triggering immediately** because:
1. **Command detection fails** - Cursor can't detect command start/completion
2. **EXECUTION_TIMEOUT_MS not applied** - Setting may not be in the right location
3. **Shell integration not working** - Command completion detection broken
4. **Terminal profile incompatibility** - Current profile doesn't work with MCP

---

## Immediate Fixes (In Order)

### Fix 1: Set EXECUTION_TIMEOUT_MS in Cursor User Settings (CRITICAL)

**The workspace setting alone is NOT enough. It MUST be in Cursor User Settings.**

1. **Open Cursor User Settings:**
   - Press `Ctrl+Shift+P`
   - Type: `Preferences: Open User Settings (JSON)`
   - Press Enter

2. **Add this setting:**
   ```json
   {
     "terminal.integrated.env.windows": {
       "EXECUTION_TIMEOUT_MS": "300000"
     }
   }
   ```

3. **Also add these for command detection:**
   ```json
   {
     "terminal.integrated.shellIntegration.enabled": true,
     "terminal.integrated.enablePersistentSessions": true,
     "cursor.terminal.useLegacyTool": true
   }
   ```

4. **Restart Cursor completely** (close all windows)

**Value:** `300000` = 5 minutes. You can increase:
- `600000` = 10 minutes
- `1800000` = 30 minutes
- `3600000` = 60 minutes

---

### Fix 2: Set EXECUTION_TIMEOUT_MS as System Environment Variable

**This ensures it's available to all processes, not just Cursor.**

**Windows:**
1. Press `Win + R`
2. Type: `sysdm.cpl`
3. Press Enter
4. Go to "Advanced" tab > "Environment Variables"
5. Under "User variables", click "New":
   - **Variable name:** `EXECUTION_TIMEOUT_MS`
   - **Variable value:** `300000`
6. Click OK on all dialogs
7. **Restart Cursor completely**

**Verify it's set:**
- Open new terminal in Cursor
- Run: `echo $EXECUTION_TIMEOUT_MS` (Git Bash) or `echo %EXECUTION_TIMEOUT_MS%` (CMD)
- Should show: `300000`

---

### Fix 3: Enable Legacy Terminal Tool (If Not Already Done)

**This uses a more reliable terminal implementation.**

1. Open Cursor Settings (`Ctrl+,`)
2. Navigate to: `Agents > Inline Editing & Terminal`
3. Enable **"Legacy Terminal Tool"**
4. **Or add to User Settings JSON:**
   ```json
   {
     "cursor.terminal.useLegacyTool": true
   }
   ```
5. Restart Cursor completely

---

### Fix 4: Fix Shell Configuration (If Using Git Bash or Custom Shell)

**If using Git Bash, add this to `~/.bashrc` or `~/.bash_profile`:**

```bash
# Bypass shell config during Cursor agent executions
if [[ "$PAGER" == "head -n 10000 | cat" || "$COMPOSER_NO_INTERACTION" == "1" ]]; then
  return
fi
```

**Why:** This helps Cursor detect command completion by bypassing custom shell configs.

**After modifying:**
1. Save the file
2. Restart Cursor completely
3. Test terminal commands

---

### Fix 5: Verify Terminal Profile is Git Bash

**Git Bash has better command detection than Command Prompt.**

**In Cursor User Settings:**
```json
{
  "terminal.integrated.defaultProfile.windows": "Git Bash",
  "terminal.integrated.automationProfile.windows": "Git Bash"
}
```

**In Workspace Settings (`.vscode/settings.json`):**
Already set to Git Bash ✅

**Restart Cursor after changing.**

---

### Fix 6: Simplify Git Bash Prompt (For Better Detection)

**Complex prompts can interfere with command detection.**

Add to `~/.bashrc`:
```bash
# Simple prompt for Cursor command detection
if [[ "$COMPOSER_NO_INTERACTION" == "1" ]]; then
  export PS1='$ '
fi
```

This gives a simple `$ ` prompt when Cursor agent is running, making completion detection easier.

---

## Complete Checklist

1. ✅ **Set EXECUTION_TIMEOUT_MS in Cursor User Settings** (most important)
2. ✅ **Set EXECUTION_TIMEOUT_MS as system environment variable**
3. ✅ **Enable Legacy Terminal Tool in User Settings**
4. ✅ **Fix shell configuration** (add bypass code to `.bashrc`)
5. ✅ **Verify terminal profile is Git Bash**
6. ✅ **Simplify prompt for agent** (optional but helpful)
7. ✅ **Restart Cursor completely** after all changes

---

## Verification

After applying all fixes:

1. **Restart Cursor completely**

2. **Test with a short command:**
   ```bash
   python -c "import time; print('Starting...'); time.sleep(10); print('Done after 10 seconds')"
   ```
   Should run for 10 seconds without cancellation.

3. **Test with longer command:**
   ```bash
   python -c "import time; print('Starting...'); time.sleep(60); print('Done after 60 seconds')"
   ```
   Should run for 60 seconds without cancellation.

4. **Check environment variable:**
   ```bash
   echo $EXECUTION_TIMEOUT_MS
   ```
   Should show: `300000`

---

## Why Commands Are Cancelled Immediately

**The immediate cancellation happens because:**

1. **MCP timeout triggers instantly** - Default timeout is very short (1-3 seconds)
2. **Command detection fails** - Cursor can't detect command started, so it cancels
3. **EXECUTION_TIMEOUT_MS not applied** - Setting only in workspace, not user/system
4. **Shell integration broken** - Can't detect command state

**The fixes above address all these issues.**

---

## If Still Not Working

### Last Resort: Use Direct Terminal

**For any command that needs to run:**

1. **Open terminal directly** (`Ctrl+` `)
2. **Type commands manually** (not through AI assistant)
3. **This completely bypasses MCP timeout**

**This is the only 100% reliable solution until Cursor fixes the MCP timeout issue.**

---

## Related Documentation

- `CURSOR_EXECUTION_TIMEOUT_FIX.md` - EXECUTION_TIMEOUT_MS setup
- `CURSOR_LEGACY_TERMINAL_FIX.md` - Legacy terminal tool
- `CURSOR_USER_SETTINGS_SYNC.md` - User settings configuration
- `CURSOR_TERMINAL_CANCELLATION_FIX.md` - General cancellation issues

---

## Summary

**Most Important Actions:**
1. **Set EXECUTION_TIMEOUT_MS in Cursor User Settings** (not just workspace)
2. **Set EXECUTION_TIMEOUT_MS as system environment variable**
3. **Enable Legacy Terminal Tool**
4. **Fix shell configuration** (add bypass code)
5. **Use direct terminal** for critical commands

**The key issue is that EXECUTION_TIMEOUT_MS must be set in multiple places, not just workspace settings.**

---

**Last Updated**: 07-12-2025

