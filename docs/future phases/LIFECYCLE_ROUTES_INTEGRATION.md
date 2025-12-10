# Lifecycle Management Routes - Future Integration

**Date**: 10-12-2025  
**Status**: ⚠️ Backend Ready, Frontend Integration Pending  
**Priority**: Medium (When lifecycle management UI is needed)

---

## Summary

Four lifecycle management API routes are fully implemented in the backend but not yet integrated in the frontend UI. These routes are ready for integration when lifecycle management features are built.

---

## Available Routes (Backend Ready)

### 1. `GET /api/lifecycle/status`
- **Purpose**: Get current status of index lifecycle management
- **Backend**: `src/api_server.py:803-818`
- **Returns**: Lifecycle status including scheduled tasks, last run times, and configuration
- **Status**: ✅ Backend implemented and tested

### 2. `POST /api/lifecycle/weekly`
- **Purpose**: Manually trigger weekly lifecycle management
- **Backend**: `src/api_server.py:821-839`
- **Parameters**: `dry_run` (boolean, default: true)
- **Returns**: Weekly lifecycle operation results
- **Status**: ✅ Backend implemented and tested

### 3. `POST /api/lifecycle/monthly`
- **Purpose**: Manually trigger monthly lifecycle management
- **Backend**: `src/api_server.py:842-860`
- **Parameters**: `dry_run` (boolean, default: true)
- **Returns**: Monthly lifecycle operation results
- **Status**: ✅ Backend implemented and tested

### 4. `POST /api/lifecycle/tenant/{tenant_id}`
- **Purpose**: Manually trigger lifecycle management for a specific tenant
- **Backend**: `src/api_server.py:863-882`
- **Parameters**: `tenant_id` (path), `dry_run` (boolean, default: true)
- **Returns**: Tenant-specific lifecycle operation results
- **Status**: ✅ Backend implemented and tested

---

## What's Needed for Integration

### 1. API Client Functions
Add to `ui/lib/api.ts`:
```typescript
export async function fetchLifecycleStatus(): Promise<LifecycleStatusResponse>
export async function runWeeklyLifecycle(dryRun: boolean = true): Promise<LifecycleResponse>
export async function runMonthlyLifecycle(dryRun: boolean = true): Promise<LifecycleResponse>
export async function runTenantLifecycle(tenantId: number, dryRun: boolean = true): Promise<LifecycleResponse>
```

### 2. UI Components
- **Lifecycle Status Dashboard**: Display current lifecycle status
- **Manual Trigger Buttons**: Buttons to trigger weekly/monthly lifecycle
- **Dry-Run Preview**: Show what would happen before executing
- **Tenant Selector**: UI for tenant-specific lifecycle management

### 3. New Dashboard Page
Create `ui/app/dashboard/lifecycle/page.tsx` for lifecycle management interface.

---

## When to Integrate

These routes should be integrated when:
- Lifecycle management UI features are prioritized
- Users need manual control over lifecycle operations
- Multi-tenant lifecycle management is required
- Admin dashboard needs lifecycle status monitoring

---

## Current Status

- ✅ **Backend**: All 4 routes implemented and working
- ✅ **API Documentation**: Available at `/docs` (Swagger UI)
- ✅ **Error Handling**: Proper error handling in place
- ❌ **Frontend**: Not yet integrated
- ❌ **API Client**: Functions not yet added
- ❌ **UI Components**: Not yet built

---

## Testing

All routes can be tested directly via:
- Swagger UI: `http://localhost:8000/docs`
- cURL commands
- Postman/Insomnia

---

**Note**: These routes are not blocking current functionality. They are ready for integration when lifecycle management UI becomes a priority.

