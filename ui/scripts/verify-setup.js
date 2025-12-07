#!/usr/bin/env node
/**
 * Verify that the setup is working correctly
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

console.log('🔍 Verifying setup...\n');

let allGood = true;

// Check 1: Types file exists
console.log('1. Checking types file...');
const typesFile = path.join(__dirname, '../lib/api-types.ts');
if (fs.existsSync(typesFile)) {
  console.log('   ✅ api-types.ts exists');
} else {
  console.log('   ❌ api-types.ts missing');
  allGood = false;
}

// Check 2: API file uses generated types
console.log('\n2. Checking API file...');
const apiFile = path.join(__dirname, '../lib/api.ts');
const apiContent = fs.readFileSync(apiFile, 'utf8');
if (apiContent.includes("import type { components } from './api-types'")) {
  console.log('   ✅ api.ts imports generated types');
} else {
  console.log('   ❌ api.ts not using generated types');
  allGood = false;
}

// Check 3: ESLint config has strict rules
console.log('\n3. Checking ESLint config...');
const eslintFile = path.join(__dirname, '../eslint.config.mjs');
const eslintContent = fs.readFileSync(eslintFile, 'utf8');
if (eslintContent.includes('@typescript-eslint/no-explicit-any')) {
  console.log('   ✅ ESLint has strict any rules');
} else {
  console.log('   ❌ ESLint missing strict any rules');
  allGood = false;
}

// Check 4: Pre-commit hook exists
console.log('\n4. Checking pre-commit hook...');
const preCommitFile = path.join(__dirname, '../../.husky/pre-commit');
if (fs.existsSync(preCommitFile)) {
  console.log('   ✅ Pre-commit hook exists');
  const hookContent = fs.readFileSync(preCommitFile, 'utf8');
  if (hookContent.includes('generate:types')) {
    console.log('   ✅ Pre-commit hook includes type generation');
  } else {
    console.log('   ⚠️  Pre-commit hook missing type generation');
  }
} else {
  console.log('   ⚠️  Pre-commit hook not found (run: npm run prepare)');
}

// Check 5: Package.json has scripts
console.log('\n5. Checking package.json scripts...');
const packageJson = JSON.parse(fs.readFileSync(path.join(__dirname, '../package.json'), 'utf8'));
if (packageJson.scripts['generate:types']) {
  console.log('   ✅ generate:types script exists');
} else {
  console.log('   ❌ generate:types script missing');
  allGood = false;
}

if (packageJson.scripts['prepare']) {
  console.log('   ✅ prepare script exists');
} else {
  console.log('   ⚠️  prepare script missing');
}

// Check 6: Try to run type generation (dry run)
console.log('\n6. Testing type generation script...');
try {
  // Just check if script is valid
  const scriptContent = fs.readFileSync(path.join(__dirname, 'generate-types.js'), 'utf8');
  if (scriptContent.includes('openapi-typescript')) {
    console.log('   ✅ Type generation script looks valid');
  } else {
    console.log('   ⚠️  Type generation script may have issues');
  }
} catch (e) {
  console.log('   ❌ Type generation script not found');
  allGood = false;
}

console.log('\n' + '='.repeat(50));
if (allGood) {
  console.log('✅ Setup verification complete!');
  console.log('\nNext steps:');
  console.log('1. Install dependencies: npm install');
  console.log('2. Initialize husky: npm run prepare');
  console.log('3. Generate types: npm run generate:types');
  console.log('4. Test linting: npm run lint');
} else {
  console.log('⚠️  Some issues found. Please review above.');
}
console.log('='.repeat(50));

process.exit(allGood ? 0 : 1);

