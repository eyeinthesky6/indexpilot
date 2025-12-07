# npm install Issue Analysis
**Date**: 07-12-2025

## Problem
npm install appears to stop or hang during execution.

## Root Cause Analysis

### 1. ⚠️ **prepare Script Issue**

**Location**: `ui/package.json` line 12
```json
"prepare": "husky install || true"
```

**Problem**: 
- The `prepare` script runs automatically after `npm install`
- It tries to run `husky install` which requires:
  - Git repository to be initialized
  - `.git` directory to exist
  - Proper git configuration

**Impact**:
- If git is not initialized, `husky install` may hang or fail
- The `|| true` should prevent failure, but may still cause delays
- On Windows, husky installation can be slow

### 2. ⚠️ **Husky Pre-commit Hook**

**Location**: `ui/.husky/pre-commit`

**Problem**:
- Pre-commit hook runs `npm run generate:types`
- This tries to connect to API server at `http://localhost:8000`
- If API is not running, it may timeout or hang

**Impact**:
- During `npm install`, husky setup may trigger hooks
- If API server is not running, `generate:types` may hang

### 3. ⚠️ **Type Generation Script**

**Location**: `ui/scripts/generate-types.js`

**Problem**:
- Script tries to fetch from API server
- If API is not running, it creates fallback types
- But the connection attempt may timeout (default timeout can be long)

## Solutions

### Solution 1: Skip prepare script during install (Quick Fix)

```bash
cd ui
npm install --ignore-scripts
```

Then manually run husky setup:
```bash
npm run prepare
```

### Solution 2: Make prepare script more robust

Update `package.json`:
```json
"prepare": "node -e \"try { require('husky').install() } catch(e) { console.log('Husky install skipped:', e.message) }\" || true"
```

### Solution 3: Disable prepare script temporarily

Temporarily remove or comment out the prepare script:
```json
// "prepare": "husky install || true"
```

Then install:
```bash
npm install
```

Then manually setup husky:
```bash
npx husky install
```

### Solution 4: Ensure Git is initialized

If git is not initialized, husky will fail:
```bash
cd C:\Projects\indexpilot
git init  # If not already a git repo
```

### Solution 5: Start API server before install

If you want type generation to work:
```bash
# Terminal 1: Start API server
python run_api.py

# Terminal 2: Install dependencies
cd ui
npm install
```

## Recommended Approach

**For first-time setup**:
```bash
cd ui
npm install --ignore-scripts
npx husky install || echo "Husky setup skipped (git may not be initialized)"
```

**For normal development**:
```bash
cd ui
npm install
# If it hangs, press Ctrl+C and use --ignore-scripts
```

## Configuration Files Checked

✅ **package.json**: Has `prepare` script that runs husky
✅ **.husky/pre-commit**: Exists and runs type generation
✅ **scripts/generate-types.js**: Tries to connect to API
❌ **.npmrc**: Not found (no custom npm config)
❌ **.git**: Need to verify git is initialized

## Next Steps

1. **Check if git is initialized**:
   ```bash
   git rev-parse --git-dir
   ```

2. **Try install with ignore-scripts**:
   ```bash
   cd ui
   npm install --ignore-scripts
   ```

3. **If successful, setup husky manually**:
   ```bash
   npx husky install || echo "Skipped"
   ```

4. **Generate types separately** (when API is running):
   ```bash
   npm run generate:types
   ```

## Summary

**Most Likely Cause**: `prepare` script running `husky install` during npm install

**Quick Fix**: Use `npm install --ignore-scripts` then setup husky manually

**Long-term Fix**: Make prepare script more robust or conditional

