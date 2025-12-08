# IndexPilot API Documentation

**Date**: 08-12-2025  
**Version**: 1.0.0  
**Status**: ✅ Complete

---

## Overview

IndexPilot provides a REST API via FastAPI for the Next.js dashboard UI. The API server runs on port 8000 by default and provides endpoints for performance metrics, health monitoring, and decision explanations.

**Base URL**: `http://localhost:8000`  
**API Documentation**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc)  
**OpenAPI Spec**: Available at `/openapi.json`

---

## Authentication

Currently, the API does not require authentication. In production, you should add authentication middleware.

---

## CORS Configuration

The API is configured to accept requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

To modify CORS settings, edit `src/api_server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Endpoints

### 1. Health Check

**Endpoint**: `GET /`

**Description**: Simple health check endpoint to verify API is running.

**Request**:
```http
GET / HTTP/1.1
Host: localhost:8000
```

**Response**:
```json
{
  "status": "ok",
  "service": "IndexPilot API"
}
```

**Status Codes**:
- `200 OK`: API is running

---

### 2. Performance Data

**Endpoint**: `GET /api/performance`

**Description**: Get performance metrics for the dashboard, including query performance over time, index impact analysis, and EXPLAIN integration statistics.

**Request**:
```http
GET /api/performance HTTP/1.1
Host: localhost:8000
```

**Response**:
```json
{
  "performance": [
    {
      "timestamp": "2025-12-08T10:00:00",
      "queryCount": 150,
      "avgLatency": 12.5,
      "p95Latency": 45.2,
      "indexHits": 0,
      "indexMisses": 0
    }
  ],
  "indexImpact": [
    {
      "indexName": "idx_contacts_email",
      "tableName": "contacts",
      "fieldName": "email",
      "improvement": 75.5,
      "queryCount": 500,
      "beforeCost": 1000.0,
      "afterCost": 245.0
    }
  ],
  "explainStats": {
    "total_explains": 1000,
    "successful_explains": 950,
    "failed_explains": 50,
    "success_rate": 0.95,
    "explain_usage_coverage": {
      "coverage_percent": 85.0,
      "queries_with_explain": 850,
      "total_queries": 1000
    }
  }
}
```

**Response Fields**:

**performance** (array):
- `timestamp` (string): ISO 8601 timestamp for the hour
- `queryCount` (integer): Number of queries in this hour
- `avgLatency` (float): Average query latency in milliseconds
- `p95Latency` (float): 95th percentile latency in milliseconds
- `indexHits` (integer): Estimated index hits (currently 0, requires EXPLAIN analysis)
- `indexMisses` (integer): Estimated index misses (currently 0, requires EXPLAIN analysis)

**indexImpact** (array):
- `indexName` (string): Name of the created index
- `tableName` (string): Table name
- `fieldName` (string): Field name
- `improvement` (float): Performance improvement percentage
- `queryCount` (integer): Number of queries analyzed
- `beforeCost` (float): Estimated query cost before index
- `afterCost` (float): Estimated query cost after index

**explainStats** (object):
- `total_explains` (integer): Total EXPLAIN operations
- `successful_explains` (integer): Successful EXPLAIN operations
- `failed_explains` (integer): Failed EXPLAIN operations
- `success_rate` (float): Success rate (0.0-1.0)
- `explain_usage_coverage` (object): EXPLAIN usage coverage statistics

**Status Codes**:
- `200 OK`: Success
- `500 Internal Server Error`: Database error or processing failure

**Time Range**: Returns data for the last 24 hours (hourly buckets)

---

### 3. Health Data

**Endpoint**: `GET /api/health`

**Description**: Get index health monitoring data, including bloat percentages, usage statistics, and health status for all indexes.

**Request**:
```http
GET /api/health HTTP/1.1
Host: localhost:8000
```

**Response**:
```json
{
  "indexes": [
    {
      "indexName": "idx_contacts_email",
      "tableName": "contacts",
      "bloatPercent": 15.2,
      "sizeMB": 45.8,
      "usageCount": 1250,
      "lastUsed": "2025-12-08T10:30:00",
      "healthStatus": "healthy"
    },
    {
      "indexName": "idx_contacts_phone",
      "tableName": "contacts",
      "bloatPercent": 52.3,
      "sizeMB": 120.5,
      "usageCount": 50,
      "lastUsed": "2025-12-07T15:20:00",
      "healthStatus": "critical"
    }
  ],
  "summary": {
    "totalIndexes": 25,
    "healthyIndexes": 20,
    "warningIndexes": 3,
    "criticalIndexes": 2,
    "totalSizeMB": 1250.5,
    "avgBloatPercent": 18.5
  }
}
```

**Response Fields**:

**indexes** (array):
- `indexName` (string): Name of the index
- `tableName` (string): Table name
- `bloatPercent` (float): Estimated bloat percentage (0-100)
- `sizeMB` (float): Index size in megabytes
- `usageCount` (integer): Number of index scans
- `lastUsed` (string): ISO 8601 timestamp of last usage
- `healthStatus` (string): One of `"healthy"`, `"warning"`, `"critical"`

**summary** (object):
- `totalIndexes` (integer): Total number of indexes
- `healthyIndexes` (integer): Number of healthy indexes
- `warningIndexes` (integer): Number of indexes with warnings
- `criticalIndexes` (integer): Number of critical indexes
- `totalSizeMB` (float): Total size of all indexes in MB
- `avgBloatPercent` (float): Average bloat percentage

**Health Status Logic**:
- `healthy`: Bloat < 20% and actively used
- `warning`: Bloat 20-50% or underutilized
- `critical`: Bloat >= 50% or severely underutilized

**Status Codes**:
- `200 OK`: Success
- `500 Internal Server Error`: Database error or processing failure

**Configuration**: Uses `bloat_threshold_percent=20.0` and `min_size_mb=1.0` by default

---

### 4. EXPLAIN Statistics

**Endpoint**: `GET /api/explain-stats`

**Description**: Get EXPLAIN integration statistics, including success rates and usage coverage metrics.

**Request**:
```http
GET /api/explain-stats HTTP/1.1
Host: localhost:8000
```

**Response**:
```json
{
  "total_explains": 1000,
  "successful_explains": 950,
  "failed_explains": 50,
  "success_rate": 0.95,
  "explain_usage_coverage": {
    "coverage_percent": 85.0,
    "queries_with_explain": 850,
    "total_queries": 1000
  }
}
```

**Response Fields**:
- `total_explains` (integer): Total EXPLAIN operations performed
- `successful_explains` (integer): Successful EXPLAIN operations
- `failed_explains` (integer): Failed EXPLAIN operations
- `success_rate` (float): Success rate (0.0-1.0)
- `explain_usage_coverage` (object): EXPLAIN usage coverage statistics
  - `coverage_percent` (float): Percentage of queries with EXPLAIN analysis
  - `queries_with_explain` (integer): Number of queries with EXPLAIN
  - `total_queries` (integer): Total number of queries

**Status Codes**:
- `200 OK`: Success
- `500 Internal Server Error`: Database error or processing failure

---

### 5. Decision Explanations

**Endpoint**: `GET /api/decisions`

**Description**: Get detailed explanations for index creation decisions, including cost-benefit analysis, confidence scores, and query patterns that triggered the decision.

**Query Parameters**:
- `limit` (integer, optional): Maximum number of decisions to return (default: 50)

**Request**:
```http
GET /api/decisions?limit=50 HTTP/1.1
Host: localhost:8000
```

**Response**:
```json
{
  "decisions": [
    {
      "id": 123,
      "tenantId": 1,
      "tableName": "contacts",
      "fieldName": "email",
      "indexName": "idx_contacts_email",
      "mutationType": "CREATE_INDEX",
      "wasCreated": true,
      "reason": "Cost-benefit analysis: queries × query_cost > build_cost",
      "confidence": 0.85,
      "queriesAnalyzed": 500,
      "buildCost": 1250.0,
      "queryCostBefore": 1000.0,
      "queryCostAfter": 245.0,
      "improvementPct": 75.5,
      "costBenefitRatio": 400.0,
      "queryPatterns": ["SELECT queries", "WHERE email = ..."],
      "createdAt": "2025-12-08T10:00:00",
      "mode": "apply"
    }
  ],
  "summary": {
    "totalDecisions": 50,
    "totalCreated": 35,
    "totalSkipped": 15,
    "creationRate": 70.0
  }
}
```

**Response Fields**:

**decisions** (array):
- `id` (integer): Mutation log ID
- `tenantId` (integer, nullable): Tenant ID (null for system-wide)
- `tableName` (string): Table name
- `fieldName` (string): Field name
- `indexName` (string): Name of the created index
- `mutationType` (string): Mutation type (e.g., "CREATE_INDEX")
- `wasCreated` (boolean): Whether index was actually created (vs advisory mode)
- `reason` (string): Human-readable reason for the decision
- `confidence` (float): Confidence score (0.0-1.0)
- `queriesAnalyzed` (integer): Number of queries analyzed
- `buildCost` (float): Estimated index build cost
- `queryCostBefore` (float): Estimated query cost without index
- `queryCostAfter` (float): Estimated query cost with index
- `improvementPct` (float): Performance improvement percentage
- `costBenefitRatio` (float): Cost-benefit ratio (queries × query_cost / build_cost)
- `queryPatterns` (array of strings): Query patterns that triggered the decision
- `createdAt` (string): ISO 8601 timestamp of decision
- `mode` (string): Decision mode ("apply", "advisory", "dry_run")

**summary** (object):
- `totalDecisions` (integer): Total number of decisions
- `totalCreated` (integer): Number of indexes created
- `totalSkipped` (integer): Number of indexes skipped
- `creationRate` (float): Creation rate percentage

**Status Codes**:
- `200 OK`: Success
- `500 Internal Server Error`: Database error or processing failure

**Time Range**: Returns decisions from the last 30 days

---

## Error Responses

All endpoints may return the following error responses:

### 500 Internal Server Error

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Causes**:
- Database connection failure
- SQL query errors
- Missing configuration
- Internal processing errors

---

## Running the API Server

### Development

```bash
# Using uvicorn directly
uvicorn src.api_server:app --reload --host 0.0.0.0 --port 8000

# Or run the module
python -m src.api_server
```

### Production

```bash
# Using gunicorn with uvicorn workers
gunicorn src.api_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## API Integration Examples

### JavaScript/TypeScript (Fetch API)

```typescript
// Get performance data
const response = await fetch('http://localhost:8000/api/performance');
const data = await response.json();
console.log(data.performance);
console.log(data.indexImpact);
```

### Python (requests)

```python
import requests

# Get health data
response = requests.get('http://localhost:8000/api/health')
data = response.json()
print(data['summary'])
```

### cURL

```bash
# Get decision explanations
curl http://localhost:8000/api/decisions?limit=10

# Get health data
curl http://localhost:8000/api/health
```

---

## OpenAPI/Swagger Documentation

The API includes automatic OpenAPI documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

These provide interactive documentation where you can:
- View all endpoints
- See request/response schemas
- Test endpoints directly
- Download OpenAPI specification

---

## Implementation Details

### Database Queries

All endpoints query the PostgreSQL database directly:
- `query_stats` table for performance metrics
- `mutation_log` table for index creation decisions
- `pg_stat_user_indexes` for index health monitoring
- System catalogs for EXPLAIN statistics

### Caching

Currently, no caching is implemented. All queries are executed on-demand. For production, consider adding:
- Redis caching for frequently accessed data
- Query result caching with TTL
- Index health data caching (refresh every 5 minutes)

### Performance Considerations

- **Performance Endpoint**: Queries last 24 hours of data (can be slow on large datasets)
- **Health Endpoint**: Scans all indexes (can be slow with many indexes)
- **Decisions Endpoint**: Queries last 30 days of mutation log (can be slow with many decisions)

**Recommendations**:
- Add pagination for large result sets
- Implement result caching
- Add database indexes on `created_at` columns
- Consider materialized views for aggregated data

---

## Future Enhancements

Planned API enhancements:
- [ ] Authentication/authorization
- [ ] Rate limiting
- [ ] Pagination for large result sets
- [ ] Filtering and sorting options
- [ ] WebSocket support for real-time updates
- [ ] Bulk operations endpoints
- [ ] Configuration management endpoints
- [ ] Maintenance task triggers

---

**Last Updated**: 08-12-2025  
**API Version**: 1.0.0

