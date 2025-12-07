# Type Generation from Backend Schema

This project uses auto-generated TypeScript types from the FastAPI backend OpenAPI schema.

## How It Works

1. **FastAPI automatically generates OpenAPI schema** at `/openapi.json`
2. **Type generation script** (`scripts/generate-types.js`) fetches the schema and generates TypeScript types
3. **Pre-commit hook** automatically regenerates types before each commit
4. **Frontend uses generated types** for type-safe API calls

## Generating Types

### Manual Generation

```bash
npm run generate:types
```

This will:
- Fetch OpenAPI schema from `http://localhost:8000/openapi.json`
- Generate TypeScript types using `openapi-typescript`
- Save to `lib/api-types.ts`

### Automatic Generation

Types are automatically generated on every commit via the pre-commit hook.

## Requirements

1. **Backend API must be running** on `http://localhost:8000` (or set `API_URL` env var)
2. **openapi-typescript** must be installed (auto-installed if missing)

## Fallback Types

If the API server is not running, the script creates fallback types based on the current API structure. These are basic types and should be regenerated once the API is available.

## Using Generated Types

```typescript
import type { components } from '@/lib/api-types';

// Use generated types
type PerformanceResponse = components['schemas']['PerformanceResponse'];
type HealthResponse = components['schemas']['HealthResponse'];
```

## Troubleshooting

### Types not generating

1. Make sure the API server is running: `python run_api.py`
2. Check that `/openapi.json` is accessible: `curl http://localhost:8000/openapi.json`
3. Run manually: `npm run generate:types`

### ESLint errors about 'any'

- Generated types file (`lib/api-types.ts`) is excluded from strict `any` checks
- If you see errors, make sure the file is in `.eslintignore`

### Pre-commit hook not running

1. Install husky: `npm run prepare`
2. Make sure `.husky/pre-commit` is executable: `chmod +x .husky/pre-commit`

