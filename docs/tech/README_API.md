# IndexPilot API Server

FastAPI backend server for the IndexPilot Dashboard UI.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the API server:
```bash
python run_api.py
```

Or using uvicorn directly:
```bash
uvicorn src.api_server:app --host 0.0.0.0 --port 8000 --reload
```

3. API will be available at: `http://localhost:8000`

## API Endpoints

### GET `/`
Health check endpoint.

### GET `/api/performance`
Returns performance metrics for the dashboard:
- `performance`: Hourly query performance data (last 24 hours)
- `indexImpact`: Index impact analysis from mutation_log
- `explainStats`: EXPLAIN integration statistics

### GET `/api/health`
Returns index health monitoring data:
- `indexes`: List of all indexes with health status, bloat, size, usage
- `summary`: Health summary statistics

### GET `/api/explain-stats`
Returns EXPLAIN integration statistics:
- Success rate
- Cache hit rate
- Fast vs ANALYZE EXPLAIN usage

## API Documentation

FastAPI automatically generates interactive API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## CORS

The API is configured to allow requests from:
- `http://localhost:3000` (Next.js dev server)
- `http://127.0.0.1:3000`

## Integration

The Next.js frontend proxies `/api/*` requests to this backend server.

