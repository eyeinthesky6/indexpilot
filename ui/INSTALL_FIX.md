# npm install Fix Guide
**Date**: 07-12-2025

## Current Environment

- **Node.js**: v24.11.1 ⚠️ (Very new, may have compatibility issues)
- **npm**: 11.6.2 ⚠️ (Very new)
- **Next.js**: 16.0.0 ✅
- **React**: 19.0.0 ⚠️ (Very new, may have compatibility issues)

## Issues Identified

### 1. ⚠️ **React 19 Compatibility**
- React 19.0.0 is very new and may have compatibility issues with Next.js 16
- Next.js 16 officially supports React 18, React 19 is experimental

### 2. ⚠️ **Node.js 24 Compatibility**
- Node.js v24.11.1 is very new (released recently)
- Next.js 16 recommends Node.js 18.17+ or 20.x
- Node.js 24 may have compatibility issues

### 3. ⚠️ **npm 11 Compatibility**
- npm 11.6.2 is very new
- May have issues with older package versions

### 4. ⚠️ **prepare Script**
- `husky install` runs automatically after install
- May hang if git is not properly configured

## Solutions

### Solution 1: Use Compatible Versions (Recommended)

Update `package.json` to use stable versions:

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    ...
  }
}
```

Or use Next.js 15 with React 18:
```json
{
  "dependencies": {
    "next": "^15.0.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    ...
  }
}
```

### Solution 2: Fix prepare Script

Update `package.json` to make prepare script safer:

```json
{
  "scripts": {
    "prepare": "node -e \"try { require('husky').install() } catch(e) { console.log('Husky skipped') }\" || true"
  }
}
```

### Solution 3: Install with Compatibility Flags

```bash
cd ui

# Clear everything
rm -rf node_modules package-lock.json

# Install with legacy peer deps (for React 19 compatibility)
npm install --legacy-peer-deps --ignore-scripts

# Then setup husky manually
npx husky install || echo "Husky skipped"
```

### Solution 4: Use Node.js 20 (Recommended)

Install Node.js 20.x (LTS) for better compatibility:

```bash
# Using nvm (if available)
nvm install 20
nvm use 20

# Or download from nodejs.org
# Then retry install
cd ui
npm install --ignore-scripts
```

## Step-by-Step Fix

### Option A: Quick Fix (Keep Current Versions)

```bash
cd ui

# Remove existing install
rm -rf node_modules package-lock.json

# Install with flags
npm install --legacy-peer-deps --ignore-scripts

# Setup husky manually
npx husky install || echo "Husky skipped"
```

### Option B: Use Stable Versions (Recommended)

1. **Update package.json**:
   ```json
   {
     "dependencies": {
       "next": "^14.2.0",
       "react": "^18.3.0",
       "react-dom": "^18.3.0"
     }
   }
   ```

2. **Clean install**:
   ```bash
   cd ui
   rm -rf node_modules package-lock.json
   npm install --ignore-scripts
   ```

3. **Setup husky**:
   ```bash
   npx husky install || echo "Husky skipped"
   ```

### Option C: Use Node.js 20

1. **Install Node.js 20** (LTS)
2. **Switch to Node.js 20**:
   ```bash
   nvm use 20  # If using nvm
   # Or use Node.js 20 directly
   ```

3. **Install**:
   ```bash
   cd ui
   npm install --ignore-scripts
   ```

## Recommended Configuration

### package.json Updates

```json
{
  "engines": {
    "node": ">=18.17.0",
    "npm": ">=9.0.0"
  },
  "scripts": {
    "prepare": "node -e \"try { require('husky').install() } catch(e) { console.log('Husky skipped') }\" || true"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  }
}
```

## Testing After Fix

```bash
cd ui

# Test build
npm run build

# Test dev server
npm run dev
```

## Summary

**Most Likely Issues**:
1. React 19 compatibility with Next.js 16
2. Node.js 24 compatibility
3. prepare script hanging

**Recommended Fix**:
1. Use React 18 instead of React 19
2. Use Node.js 20 (LTS) instead of Node.js 24
3. Install with `--ignore-scripts` flag
4. Update prepare script to be more robust

