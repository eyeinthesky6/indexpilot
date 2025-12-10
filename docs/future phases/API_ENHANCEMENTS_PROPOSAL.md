# IndexPilot - API Enhancements Proposal

**Date**: 07-12-2025  
**Status**: 📋 Future Enhancement Proposal  
**Priority**: Medium (Internal API) / High (Public API)

---

## Executive Summary

This document proposes API enhancement strategies for IndexPilot, focusing on contract-first development, API versioning, and improved API design patterns. These enhancements would be valuable if IndexPilot evolves to support public APIs, multiple consumers, or multi-team development.

**Current State**: FastAPI code-first approach with auto-generated OpenAPI documentation  
**Proposed State**: Enhanced API design with optional contract-first workflow

---

## 1. Contract-First API Development

### Overview

**Contract-First Approach**: Define API contracts (OpenAPI/Swagger specs) before implementing endpoints, enabling parallel development and better API design.

### Current Approach (Code-First)

- ✅ FastAPI auto-generates OpenAPI at `/docs` and `/redoc`
- ✅ Simple internal API (3 endpoints for dashboard UI)
- ✅ Works well for small team/single developer
- ⚠️ No explicit contract versioning
- ⚠️ No client SDK generation

### Proposed Contract-First Benefits

1. **Parallel Development**: Frontend/backend teams work independently
2. **API Versioning**: Explicit versioning strategy (`/api/v1/`, `/api/v2/`)
3. **Client SDK Generation**: Auto-generate TypeScript/Python clients
4. **Contract Testing**: Validate API contracts (Pact, Dredd)
5. **Better API Design**: Forces upfront API design thinking
6. **Documentation**: Single source of truth for API contracts

### Implementation Strategy

#### Phase 1: Export Current OpenAPI Spec (Quick Win)

```yaml
# Action Items:
1. Export OpenAPI spec from FastAPI: GET /openapi.json
2. Save to: docs/api/openapi.yaml
3. Version control the spec
4. Update on each API change
```

**Effort**: Low (1-2 hours)  
**Value**: Medium - Establishes baseline contract

---

#### Phase 2: Explicit Pydantic Models (Improvement)

**Current**: Using `JSONDict` (flexible but loose typing)

**Proposed**: Explicit request/response models

```python
# Example: src/api/models.py
from pydantic import BaseModel
from typing import List
from datetime import datetime

class PerformanceDataPoint(BaseModel):
    timestamp: datetime
    queryCount: int
    avgLatency: float
    p95Latency: float
    indexHits: int
    indexMisses: int

class IndexImpact(BaseModel):
    indexName: str
    tableName: str
    fieldName: str
    improvement: float
    queryCount: int
    beforeCost: float
    afterCost: float

class PerformanceResponse(BaseModel):
    performance: List[PerformanceDataPoint]
    indexImpact: List[IndexImpact]
    explainStats: dict
```

**Benefits**:
- Better type safety
- Auto-generated OpenAPI schemas
- Request/response validation
- IDE autocomplete support

**Effort**: Medium (1-2 days)  
**Value**: High - Better type safety and documentation

---

#### Phase 3: Full Contract-First Workflow (Future)

**When to Implement**: If planning public APIs or multi-team development

**Workflow**:
1. Design API contract in `docs/api/openapi.yaml`
2. Generate FastAPI code from spec (using `openapi-python-client` or similar)
3. Implement business logic
4. Validate against contract (contract testing)
5. Generate client SDKs for consumers

**Tools**:
- **OpenAPI Generator**: Generate client SDKs (TypeScript, Python, etc.)
- **Pact**: Contract testing between services
- **Dredd**: API contract validation
- **Spectral**: OpenAPI linting

**Effort**: High (1-2 weeks)  
**Value**: Very High - If multiple consumers or public API

---

## 2. API Versioning Strategy

### Current State

- ⚠️ No versioning strategy
- ⚠️ All endpoints at `/api/*`
- ⚠️ Breaking changes would affect all consumers

### Proposed Versioning Approach

#### Option 1: URL Versioning (Recommended)

```
/api/v1/performance
/api/v1/health
/api/v2/performance  # New version
```

**Pros**: Clear, explicit, easy to deprecate  
**Cons**: URL clutter

#### Option 2: Header Versioning

```
GET /api/performance
Accept: application/vnd.indexpilot.v1+json
```

**Pros**: Clean URLs  
**Cons**: Less discoverable, requires header management

#### Option 3: Query Parameter

```
/api/performance?version=1
```

**Pros**: Simple  
**Cons**: Not RESTful, easy to forget

### Implementation

```python
# src/api/v1/router.py
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

@v1_router.get("/performance")
async def get_performance_v1():
    # V1 implementation
    pass

# src/api/v2/router.py
v2_router = APIRouter(prefix="/api/v2", tags=["v2"])

@v2_router.get("/performance")
async def get_performance_v2():
    # V2 implementation with improvements
    pass

# src/api_server.py
app.include_router(v1_router)
app.include_router(v2_router)
```

**Effort**: Medium (2-3 days)  
**Value**: High - Future-proofs API evolution

---

## 3. API Documentation Enhancements

### Current State

- ✅ FastAPI auto-generates Swagger UI at `/docs`
- ✅ Basic endpoint descriptions
- ⚠️ No examples
- ⚠️ No detailed response schemas
- ⚠️ No error response documentation

### Proposed Enhancements

#### 1. Response Examples

```python
@app.get(
    "/api/performance",
    response_model=PerformanceResponse,
    responses={
        200: {
            "description": "Performance metrics",
            "content": {
                "application/json": {
                    "example": {
                        "performance": [
                            {
                                "timestamp": "2025-12-07T10:00:00Z",
                                "queryCount": 150,
                                "avgLatency": 45.2,
                                "p95Latency": 120.5,
                                "indexHits": 120,
                                "indexMisses": 30
                            }
                        ],
                        "indexImpact": [...],
                        "explainStats": {...}
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Database connection failed"}
                }
            }
        }
    }
)
```

#### 2. OpenAPI Tags and Grouping

```python
app = FastAPI(
    title="IndexPilot API",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Performance",
            "description": "Query performance metrics and analysis"
        },
        {
            "name": "Health",
            "description": "Index health monitoring and diagnostics"
        },
        {
            "name": "Index Management",
            "description": "Index creation, deletion, and management"
        }
    ]
)
```

#### 3. Export OpenAPI Spec

```python
# Add endpoint to export spec
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_spec():
    return app.openapi()
```

**Effort**: Low-Medium (1 day)  
**Value**: Medium - Better developer experience

---

## 4. API Security Enhancements

### Current State

- ✅ CORS configured for Next.js frontend
- ⚠️ No authentication/authorization
- ⚠️ No rate limiting on API endpoints
- ⚠️ No API key management

### Proposed Enhancements

#### 1. API Key Authentication (For Public API)

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    # Validate API key against database
    if not is_valid_api_key(api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.get("/api/performance", dependencies=[Depends(verify_api_key)])
async def get_performance():
    pass
```

#### 2. Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/performance")
@limiter.limit("100/minute")
async def get_performance(request: Request):
    pass
```

#### 3. Request Validation

```python
from pydantic import validator

class PerformanceRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
```

**Effort**: Medium (2-3 days)  
**Value**: High - Required for public API

---

## 5. API Testing Strategy

### Current State

- ⚠️ No dedicated API tests
- ⚠️ No contract testing
- ⚠️ No integration tests for API endpoints

### Proposed Testing Approach

#### 1. Unit Tests for API Endpoints

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from src.api_server import app

client = TestClient(app)

def test_get_performance():
    response = client.get("/api/performance")
    assert response.status_code == 200
    data = response.json()
    assert "performance" in data
    assert "indexImpact" in data
```

#### 2. Contract Testing (Pact)

```python
# tests/contract/test_api_contract.py
# Validate API contract against OpenAPI spec
```

#### 3. Integration Tests

```python
# tests/integration/test_api_integration.py
# Test API with real database
```

**Effort**: Medium (2-3 days)  
**Value**: High - Ensures API reliability

---

## 6. Client SDK Generation

### Overview

Auto-generate client SDKs from OpenAPI spec for TypeScript, Python, and other languages.

### Implementation

#### 1. Generate TypeScript Client

```bash
# Using openapi-generator
openapi-generator generate \
  -i docs/api/openapi.yaml \
  -g typescript-axios \
  -o ui/lib/generated-api-client
```

#### 2. Generate Python Client

```bash
openapi-generator generate \
  -i docs/api/openapi.yaml \
  -g python \
  -o clients/python
```

#### 3. Integration

```typescript
// ui/lib/api.ts - Use generated client
import { IndexPilotApi } from './generated-api-client';

const api = new IndexPilotApi({
  baseURL: process.env.NEXT_PUBLIC_API_URL
});

const data = await api.getPerformance();
```

**Effort**: Medium (1-2 days)  
**Value**: High - Better developer experience for API consumers

---

## 7. API Monitoring and Observability

### Current State

- ✅ Basic error logging
- ⚠️ No API metrics (request rate, latency, errors)
- ⚠️ No distributed tracing
- ⚠️ No API usage analytics

### Proposed Enhancements

#### 1. API Metrics

```python
from prometheus_client import Counter, Histogram

api_requests = Counter('api_requests_total', 'Total API requests', ['endpoint', 'method'])
api_latency = Histogram('api_request_duration_seconds', 'API request latency', ['endpoint'])

@app.middleware("http")
async def track_api_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    api_requests.labels(endpoint=request.url.path, method=request.method).inc()
    api_latency.labels(endpoint=request.url.path).observe(duration)
    
    return response
```

#### 2. Request/Response Logging

```python
import structlog

logger = structlog.get_logger()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("api_request", path=request.url.path, method=request.method)
    response = await call_next(request)
    logger.info("api_response", status_code=response.status_code)
    return response
```

**Effort**: Medium (1-2 days)  
**Value**: Medium - Better observability

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 weeks)

1. ✅ Export OpenAPI spec to version control
2. ✅ Add explicit Pydantic models for request/response
3. ✅ Enhance API documentation with examples
4. ✅ Add basic API unit tests

**Value**: Medium | **Effort**: Low-Medium

---

### Phase 2: API Improvements (2-3 weeks)

1. ✅ Implement API versioning strategy
2. ✅ Add rate limiting
3. ✅ Improve error handling and responses
4. ✅ Add API metrics and logging

**Value**: High | **Effort**: Medium

---

### Phase 3: Advanced Features (4-6 weeks)

1. ✅ Full contract-first workflow (if needed)
2. ✅ Client SDK generation
3. ✅ Contract testing (Pact)
4. ✅ API key authentication
5. ✅ Advanced monitoring and tracing

**Value**: Very High | **Effort**: High

**When to Implement**: Only if planning public APIs or multi-consumer scenarios

---

## Decision Matrix

### When to Use Contract-First

| Scenario | Recommendation |
|----------|---------------|
| Internal API only (current) | ❌ Not needed - Code-first is fine |
| Public API planned | ✅ Contract-first recommended |
| Multiple teams consuming API | ✅ Contract-first recommended |
| Client SDKs needed | ✅ Contract-first recommended |
| API versioning critical | ✅ Contract-first recommended |
| Single developer/small team | ❌ Code-first is sufficient |

---

## Conclusion

**Current Recommendation**: 
- ✅ **Keep code-first approach** for internal dashboard API
- ✅ **Implement Phase 1 quick wins** (Pydantic models, better docs)
- ⚠️ **Consider contract-first** only if planning public APIs or multi-consumer scenarios

**Future Considerations**:
- Monitor API usage and consumer needs
- Implement contract-first when multiple consumers emerge
- Add versioning when breaking changes are needed
- Generate client SDKs when external consumers appear

---

**Last Updated**: 07-12-2025  
**Status**: 📋 Proposal - Awaiting Decision on Public API Strategy

