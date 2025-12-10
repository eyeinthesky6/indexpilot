# Cursor IDE Terminal Commands Getting Cancelled - Latest Fix

**Date**: 07-12-2025  
**Issue**: Terminal commands are being automatically cancelled in Cursor IDE

---

## Problem

Terminal commands executed through Cursor's AI assistant are being automatically cancelled, even after applying previous fixes. This is a recurring issue with multiple potential causes.

**Symptoms:**
- Commands work fine when run directly in terminal
- Commands get cancelled when executed through AI assistant
- Commands may be cancelled when switching tabs
- Commands may hang indefinitely in Agent Mode
- Error: "Command was canceled by the user" (but user didn't cancel)

---

## Root Causes (Latest Research)

Based on latest community reports, there are several causes:

1. **Tab Switching**: Commands get cancelled when switching tabs during execution
2. **Agent Mode Command Detection**: Agent fails to detect command completion, especially with custom shell configs
3. **Legacy Terminal Tool Not Enabled**: The newer terminal tool has issues that the legacy version doesn't
4. **Shell Configuration Interference**: Custom shell configs (oh-my-zsh, etc.) interfere with completion detection
5. **MCP Timeout**: Still a 5-10 second timeout limitation in MCP system

**References:**
- [Cursor Forum - Commands in agent get auto-cancelled](https://forum.cursor.com/t/commands-in-agent-get-auto-cancelled/140950)
- [GitHub Issue #3416](https://github.com/cursor/cursor/issues/3416) - Agent Mode commands hang
- [Dredyson Blog - Cursor Agent Hanging Fix](https://dredyson.com/why-my-cursor-ide-agent-was-hanging-after-terminal-commands-and-how-i-fixed-it/)

---

## Solutions (In Order of Priority)

### Solution 1: Enable Legacy Terminal Tool (CRITICAL - Do This First!)

**This is the most effective fix according to recent reports.**

**Method 1: Settings UI**
1. Open Cursor Settings (`Ctrl+,`)
2. Navigate to: `Agents > Inline Editing & Terminal`
3. Enable **"Legacy Terminal Tool"** or **"Use Legacy Terminal"**
4. Restart Cursor completely

**Method 2: User Settings JSON**
1. Press `Ctrl+Shift+P`
2. Type: `Preferences: Open User Settings (JSON)`
3. Add:
   ```json
   {
     "cursor.terminal.useLegacyTool": true
   }
   ```
4. Restart Cursor completely

**Note:** This setting must be in **Cursor User Settings**, not workspace settings!

---

### Solution 2: Fix Shell Configuration (If Using Custom Shell)

**If you're using oh-my-zsh, zsh, or other custom shell configs:**

Add this to the **top** of your shell config file (`.zshrc`, `.bashrc`, etc.):

```bash
# Bypass shell config during Cursor agent executions
if [[ "$PAGER" == "head -n 10000 | cat" || "$COMPOSER_NO_INTERACTION" == "1" ]]; then
  return
fi
```

**Why this works:** Cursor agent uses these environment variables to detect when it's running. Bypassing the rest of the config helps the agent detect command completion.

**Files to modify:**
- `~/.zshrc` (for zsh)
- `~/.bashrc` (for bash)
- `~/.bash_profile` (for bash on macOS)

**After modifying:**
1. Save the file
2. Restart Cursor completely
3. Test terminal commands

---

### Solution 3: Verify EXECUTION_TIMEOUT_MS is Set

**Check that `EXECUTION_TIMEOUT_MS` is configured:**

In `.vscode/settings.json`:
```json
{
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000"
  }
}
```

**Value:** `300000` = 5 minutes (adjust as needed)

**Also set in Cursor User Settings:**
1. Open User Settings (`Ctrl+Shift+P` > "Preferences: Open User Settings (JSON)")
2. Add the same setting:
   ```json
   {
     "terminal.integrated.env.windows": {
       "EXECUTION_TIMEOUT_MS": "300000"
     }
   }
   ```

**Restart Cursor after setting this.**

---

### Solution 4: Avoid Tab Switching During Command Execution

**If commands are cancelled when switching tabs:**

1. **Don't switch tabs** while a command is running
2. **Keep the terminal tab active** during command execution
3. **Use multiple Cursor windows** if you need to work on other files during long commands

---

### Solution 5: Use Direct Terminal (Most Reliable)

**For any command that takes more than a few seconds:**

1. **Open terminal directly** (`Ctrl+` `)
2. **Type commands manually** (not through AI assistant)
3. **This completely bypasses the cancellation issue**

**This is the only 100% reliable solution for long-running commands.**

---

### Solution 6: Check Current Settings

**Verify these settings are in both workspace AND user settings:**

**Workspace (`.vscode/settings.json`):**
```json
{
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  },
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.enablePersistentSessions": true,
  "terminal.integrated.commandTimeout": 0,
  "terminal.integrated.killOnExit": "never"
}
```

**Cursor User Settings:**
```json
{
  "cursor.terminal.useLegacyTool": true,
  "terminal.integrated.env.windows": {
    "EXECUTION_TIMEOUT_MS": "300000"
  },
  "terminal.integrated.shellIntegration.enabled": true,
  "terminal.integrated.enablePersistentSessions": true
}
```

---

## Complete Action Checklist

1. ✅ **Enable Legacy Terminal Tool** in Cursor User Settings
2. ✅ **Set EXECUTION_TIMEOUT_MS** in both workspace and user settings
3. ✅ **Fix shell configuration** if using custom shell (oh-my-zsh, etc.)
4. ✅ **Restart Cursor completely** after all changes
5. ✅ **Test with a short command** first
6. ✅ **Use direct terminal** for long-running commands

---

## Troubleshooting

### Commands Still Getting Cancelled

1. **Check Legacy Terminal Tool is enabled:**
   - Settings > Agents > Inline Editing & Terminal
   - Should show "Legacy Terminal Tool" enabled

2. **Verify User Settings:**
   - Open User Settings JSON
   - Check `cursor.terminal.useLegacyTool` is `true`
   - Check `EXECUTION_TIMEOUT_MS` is set

3. **Check Shell Config:**
   - If using custom shell, add the bypass code at the top
   - Restart terminal after modifying shell config

4. **Try Direct Terminal:**
   - If all else fails, use terminal directly
   - This always works regardless of settings

### Commands Hang Indefinitely

1. **Check shell integration:**
   - Ensure `terminal.integrated.shellIntegration.enabled` is `true`
   - This helps Cursor detect command completion

2. **Simplify shell prompt:**
   - Complex prompts can interfere with detection
   - Try a simple prompt: `PROMPT=$P$G` (for CMD)

3. **Check for shell config issues:**
   - Add the bypass code to shell config
   - This is especially important for oh-my-zsh users

---

## Why This Keeps Happening

**The cancellation issue has multiple causes:**
1. **MCP System Limitation**: Built-in 5-10 second timeout (hard to override)
2. **Command Detection Issues**: Agent can't detect when commands complete
3. **Tab Switching Bug**: Commands cancelled when focus changes
4. **Shell Config Interference**: Custom configs break detection

**The Legacy Terminal Tool fixes most of these issues by using a more reliable terminal implementation.**

---

## Related Documentation

- `CURSOR_LEGACY_TERMINAL_FIX.md` - Legacy terminal setup
- `CURSOR_TERMINAL_TIMEOUT_FIX.md` - Timeout issues
- `CURSOR_EXECUTION_TIMEOUT_FIX.md` - EXECUTION_TIMEOUT_MS setup
- `CURSOR_USER_SETTINGS_SYNC.md` - User settings configuration

---

## Conclusion

**Most Important Fixes:**
1. **Enable Legacy Terminal Tool** (in Cursor User Settings)
2. **Fix shell configuration** (if using custom shell)
3. **Set EXECUTION_TIMEOUT_MS** (in both workspace and user settings)
4. **Use direct terminal** for long-running commands

**The Legacy Terminal Tool is the most effective fix according to recent community reports.**

---

**Last Updated**: 07-12-2025

