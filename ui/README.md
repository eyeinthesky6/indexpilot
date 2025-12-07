# IndexPilot UI Dashboard

Next.js dashboard for IndexPilot PostgreSQL auto-indexing system.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Run development server:
```bash
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000)

## Features

- **Performance Dashboard**: Query performance metrics, index impact analysis, EXPLAIN statistics
- **Health Monitoring**: Index bloat, usage statistics, health status

## API Integration

The UI expects a Python backend API running on `http://localhost:8000`. The Next.js config proxies `/api/*` requests to the backend.

## Components

Built with:
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- Recharts for data visualization
