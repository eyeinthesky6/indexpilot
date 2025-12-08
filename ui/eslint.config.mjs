import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import tseslint from "typescript-eslint";

const eslintConfig = defineConfig([
  // Override default ignores of eslint-config-next (must be first)
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "dist/**",
    "next-env.d.ts",
    // Generated types (excluded from strict checks)
    "**/lib/api-types.ts",
    "**/lib/api-types.d.ts",
    "**/scripts/**",
    // Dependencies
    "node_modules/**",
    // Config files (already handled by default, but explicit for clarity)
    "*.config.js",
    "*.config.mjs",
    "*.config.ts",
  ]),
  ...nextVitals,
  ...nextTs,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        project: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // Strict rules for 'any' types
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-return": "warn", // Allow with explicit cast
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/no-unsafe-enum-comparison": "error",
      "@typescript-eslint/no-require-imports": "warn", // Allow for dynamic type loading
    },
  },
]);

export default eslintConfig;
