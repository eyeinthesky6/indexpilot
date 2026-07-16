# API type generation

The operator UI keeps its API types in `lib/api-types.ts`. Regenerate that file deliberately when
the FastAPI response schema changes; normal commits do not contact a local API or rewrite types.

## Generate types

1. Install the UI dependencies with `pnpm install --frozen-lockfile`.
2. Start the IndexPilot API at `http://localhost:8000`, or set `API_URL` to its local URL.
3. From `ui/`, run:

```bash
pnpm generate:types
```

The script reads `${API_URL}/openapi.json` through `openapi-typescript` and writes
`lib/api-types.ts`. Review the generated diff before committing it. Do not point this command at a
production API or commit credentials.

## Commit checks

The repository's Husky hook runs root pre-commit checks, including staged skill routing, UI lint,
secret scanning, and database-safety checks. It intentionally does not start the API or regenerate
types. This keeps commits deterministic and avoids silently replacing the checked-in API contract.

If generation fails, confirm the API is reachable at `/openapi.json` and that the UI dependencies
were installed with pnpm. Keep the existing checked-in types until a real schema can be generated
and reviewed; do not substitute guessed response fields.
