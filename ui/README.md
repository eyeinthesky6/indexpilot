# IndexPilot web and operator UI

This Next.js 16 application has two deliberately separate surfaces:

- `/` is the static, API-free public project site deployed to GitHub Pages.
- `/dashboard` is the experimental local operator UI. It expects the authenticated IndexPilot API
  at `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` is configured.

The public site never imports dashboard API clients and makes no database requests.

## Local development

Requirements: Node.js 22 and pnpm 10.

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Open <http://localhost:3000>. To use the operator dashboard, start the Python API separately and
visit <http://localhost:3000/login>.

## Checks

```bash
pnpm lint
pnpm build
```

To verify the same static export deployed by GitHub Pages:

```bash
GITHUB_PAGES=true NEXT_PUBLIC_BASE_PATH=/indexpilot NEXT_PUBLIC_OPERATOR_UI=disabled pnpm build
```

On PowerShell:

```powershell
$env:GITHUB_PAGES = "true"
$env:NEXT_PUBLIC_BASE_PATH = "/indexpilot"
$env:NEXT_PUBLIC_OPERATOR_UI = "disabled"
pnpm build
```

The static export is written to `out/`. The GitHub Actions workflow owns deployment; no API token
or database credential belongs in the Pages build. The workflow also disables the token form and
operator dashboard in the public artifact; local builds keep those routes available.

## Stack

- Next.js 16 App Router
- React 19 and TypeScript
- Tailwind CSS 3
- shadcn-style primitives and Recharts for the operator dashboard
