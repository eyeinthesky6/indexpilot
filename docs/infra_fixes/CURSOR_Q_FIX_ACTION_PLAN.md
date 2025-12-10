# Cursor 'q' Character Bug - Action Plan

**Date**: 07-12-2025  
**Status**: Issue persists - requires Cursor user settings configuration

---

## ⚠️ CRITICAL: The 'q' Character Has Returned

The 'q' character bug is back. This is a **Cursor IDE agent terminal integration bug** that requires configuration in **Cursor User Settings**, not just workspace settings.

---

## Immediate Actions Required

### Action 1: Check Cursor User Settings (MOST IMPORTANT)

**The workspace settings alone are NOT enough. You MUST configure Cursor user settings.**

1. **Open Cursor User Settings:**
   - Press `Ctrl+Shift+P`
   - Type: `Preferences: Open User Settings (JSON)`
   - Press Enter

2. **Add These Settings:**
   ```json
   {
     "terminal.integrated.defaultProfile.windows": "Git Bash",
     "terminal.integrated.shellIntegration.enabled": true,
     "terminal.integrated.enablePersistentSessions": true
   }
   ```

3. **Try Disabling Agent Terminal Integration:**
   ```json
   {
     "cursor.agent.terminal.enabled": false
   }
   ```
   **Note:** This setting name may vary. Check Cursor Settings UI:
   - `Ctrl+,` (Settings)
   - Search for "agent terminal" or "terminal integration"
   - Look for options to disable agent terminal features

4. **Restart Cursor completely** (close all windows)

---

### Action 2: Workspace Settings Updated

✅ **Already done:** Changed default terminal to Git Bash in workspace settings.

**Current workspace configuration:**
- Default terminal: **Git Bash** (changed from Command Prompt)
- Terminal stability settings: ✅ Configured
- UTF-8 encoding: ✅ Configured

---

### Action 3: Test After Changes

1. **Close Cursor completely**
2. **Reopen Cursor**
3. **Close and reopen terminal** (`Ctrl+` `)
4. **Test command:**
   ```bash
   python --version
   ```
   Should show: `Python 3.x.x` (NOT `qpython`)

---

## Alternative Solutions

### Option A: Use Direct Terminal (Workaround)

**Bypass the AI assistant entirely:**

1. Press `Ctrl+` ` to open terminal directly
2. Type commands manually (not through AI assistant)
3. This completely avoids the bug

**This is the most reliable workaround until Cursor fixes the bug.**

---

### Option B: Try Legacy Terminal Tool

1. Open Cursor Settings (`Ctrl+,`)
2. Search for "Legacy Terminal" or "Terminal Tool"
3. Enable "Use Legacy Terminal Tool" or "Legacy Terminal Tool"
4. Restart Cursor

**Or add to Cursor User Settings:**
```json
{
  "cursor.terminal.useLegacyTool": true
}
```

---

### Option C: Alias 'q' Command (Temporary Workaround)

**For Git Bash, add to `~/.bashrc` or `~/.bash_profile`:**
```bash
alias q=':'
```

**For Command Prompt, add to `%USERPROFILE%\cmd_aliases.bat`:**
```batch
doskey q=rem
```

**Note:** This doesn't fix the root cause but prevents errors when 'q' is sent.

---

## Root Cause

The 'q' character is sent by **Cursor's agent terminal integration layer** when:
1. Using "stop" or "skip" functions in Cursor
2. The AI assistant executes terminal commands
3. Terminal escape sequences are misinterpreted

**This is a Cursor IDE bug, not a configuration issue with your project.**

---

## What We've Tried

✅ Removed TERM=dumb (didn't help)  
✅ Configured terminal stability settings  
✅ Changed default terminal to Git Bash  
❌ **Still need:** Cursor user settings configuration  
❌ **Still need:** Disable agent terminal integration (if available)

---

## Next Steps

1. **Open Cursor User Settings** (`Ctrl+Shift+P` > "Preferences: Open User Settings (JSON)")
2. **Add the settings above** (especially Git Bash as default)
3. **Try disabling agent terminal integration** (check Settings UI for exact option)
4. **Restart Cursor completely**
5. **Test terminal commands**

If issue persists:
- Use direct terminal instead of AI assistant
- Report to Cursor support with version info
- Check for Cursor updates

---

## Related Documentation

- `CURSOR_USER_SETTINGS_SYNC.md` - Complete sync guide
- `CURSOR_TERMINAL_Q_CHARACTER_FIX.md` - Full fix documentation
- `CURSOR_LEGACY_TERMINAL_FIX.md` - Legacy terminal option

---

**Last Updated**: 07-12-2025

