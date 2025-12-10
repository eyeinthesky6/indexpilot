# IndexPilot - Simulation/Live Mode Toggle Feature

**Date**: 10-12-2025  
**Purpose**: Design document for simulation/live mode toggle in frontend  
**Status**: ⚠️ **PLANNED** - Future Phase Feature

---

## Executive Summary

**Current State**: 
- ✅ Simulation mode exists (`src/simulation/simulator.py`) - runs benchmarks on simulated data
- ✅ Live mode exists (`src/auto_indexer.py`) - operates on real production database
- ⚠️ No unified interface to switch between modes
- ⚠️ No way to compare simulation vs live performance
- ⚠️ Simulation results stored separately from live performance data

**Proposed Feature**: Add a frontend toggle to switch between Simulation and Live modes, with unified management interface for both modes.

---

## Feature Overview

### Core Functionality

1. **Mode Toggle**: Switch between Simulation and Live modes in the frontend
2. **Unified Dashboard**: View and manage both simulation and live performance data
3. **Configuration Management**: Manage simulation scenarios and live mode settings
4. **Performance Comparison**: Compare simulation predictions vs actual live performance
5. **Scenario Management**: Create, run, and manage simulation scenarios from UI

---

## User Interface Design

### 1. Mode Toggle Component

**Location**: Global header/navigation bar

**Design**:
```
┌─────────────────────────────────────────────────────────┐
│ IndexPilot Dashboard                    [Simulation ▼] │
└─────────────────────────────────────────────────────────┘
```

**Toggle Options**:
- **Live Mode**: Shows real production performance data
- **Simulation Mode**: Shows simulation benchmark results
- **Comparison Mode**: Side-by-side comparison view

**Visual Indicators**:
- 🟢 Green badge for Live Mode (active production)
- 🔵 Blue badge for Simulation Mode (test/benchmark)
- ⚠️ Warning indicator if switching modes (data context changes)

---

### 2. Mode-Specific Views

#### Live Mode Dashboard

**Features**:
- Real-time performance metrics from `query_stats` table
- Current index recommendations and decisions
- Live query performance trends
- Index health monitoring
- Production alerts and notifications

**Data Sources**:
- `/api/performance` - Real-time performance data
- `/api/health` - Index health status
- `/api/decisions` - Recent index decisions
- `/api/explain-stats` - EXPLAIN analysis statistics

**Time Range**: Configurable (1 hour, 6 hours, 24 hours, 7 days, 30 days)

---

#### Simulation Mode Dashboard

**Features**:
- Simulation scenario selection and management
- Benchmark results visualization
- Scenario configuration (baseline, autoindex, comprehensive)
- Simulation run history
- Performance predictions and projections

**Data Sources**:
- `/api/simulation/scenarios` - List available scenarios
- `/api/simulation/run` - Execute simulation
- `/api/simulation/results` - Get simulation results
- `/api/simulation/history` - Historical simulation runs

**Simulation Types**:
- **Baseline**: No indexes (baseline performance)
- **Autoindex**: Auto-indexing enabled
- **Comprehensive**: Full optimization suite

**Scenario Sizes**:
- Small (1K-10K records)
- Medium (10K-100K records)
- Large (100K-1M records)
- Stress Test (1M+ records)

---

#### Comparison Mode Dashboard

**Features**:
- Side-by-side comparison of simulation vs live performance
- Performance gap analysis (predicted vs actual)
- Index effectiveness comparison
- Query pattern matching
- Trend alignment analysis

**Comparison Metrics**:
- Average latency (simulation vs live)
- P95/P99 latency comparison
- Index hit rates
- Query throughput
- Index creation decisions accuracy

---

### 3. Configuration Management

#### Simulation Configuration Panel

**Location**: Settings → Simulation Configuration

**Features**:
- **Scenario Templates**: Pre-defined scenarios (CRM, E-commerce, Analytics, etc.)
- **Custom Scenarios**: Create custom simulation scenarios
- **Data Generation**: Configure synthetic data generation parameters
- **Query Patterns**: Define query patterns for simulation
- **Run Scheduling**: Schedule periodic simulation runs
- **Result Retention**: Configure how long to keep simulation results

**Configuration Options**:
```typescript
interface SimulationConfig {
  scenarioName: string;
  scenarioType: 'baseline' | 'autoindex' | 'comprehensive';
  dataSize: 'small' | 'medium' | 'large' | 'stress-test';
  tableCount: number;
  recordCount: number;
  queryPatterns: QueryPattern[];
  duration: number; // seconds
  autoRun: boolean;
  retentionDays: number;
}
```

---

#### Live Mode Configuration Panel

**Location**: Settings → Live Mode Configuration

**Features**:
- **Auto-Indexing Settings**: Enable/disable auto-indexing
- **Performance Tracking**: Configure what metrics to track
- **Alert Thresholds**: Set performance alert thresholds
- **Data Retention**: Configure retention policy for `query_stats`
- **Index Creation Rules**: Configure index creation criteria
- **Tenant Filtering**: Filter by tenant (multi-tenant support)

**Configuration Options**:
```typescript
interface LiveModeConfig {
  autoIndexingEnabled: boolean;
  performanceTracking: {
    trackQueries: boolean;
    trackExplains: boolean;
    trackIndexUsage: boolean;
  };
  alertThresholds: {
    latencyMs: number;
    queryCount: number;
    errorRate: number;
  };
  retentionPolicy: {
    rawDataDays: number;
    aggregatedDataDays: number;
  };
  indexCreationRules: IndexCreationRules;
  tenantFilter?: number[];
}
```

---

### 4. Scenario Management

#### Scenario List View

**Features**:
- List all available simulation scenarios
- Create new scenario
- Edit existing scenario
- Delete scenario
- Run scenario
- View scenario results

**Scenario Card**:
```
┌─────────────────────────────────────┐
│ CRM Simulation (Small)              │
│ Type: Comprehensive                 │
│ Last Run: 2 hours ago               │
│ Status: ✅ Completed                │
│ [View Results] [Run Again] [Edit]   │
└─────────────────────────────────────┘
```

---

#### Scenario Editor

**Features**:
- Scenario name and description
- Scenario type selection (baseline/autoindex/comprehensive)
- Data size configuration
- Table and field definitions
- Query pattern configuration
- Advanced settings (ML models, algorithms, etc.)

---

## API Endpoints

### Simulation Endpoints

#### `GET /api/simulation/scenarios`
List all available simulation scenarios.

**Response**:
```json
{
  "scenarios": [
    {
      "id": 1,
      "name": "CRM Simulation (Small)",
      "type": "comprehensive",
      "dataSize": "small",
      "lastRun": "2025-12-10T10:30:00Z",
      "status": "completed",
      "resultId": 123
    }
  ]
}
```

---

#### `POST /api/simulation/scenarios`
Create a new simulation scenario.

**Request**:
```json
{
  "name": "E-commerce Simulation",
  "type": "autoindex",
  "dataSize": "medium",
  "config": { ... }
}
```

---

#### `POST /api/simulation/run`
Execute a simulation scenario.

**Request**:
```json
{
  "scenarioId": 1,
  "options": {
    "trackPerformance": true,
    "generateReport": true
  }
}
```

**Response**:
```json
{
  "runId": 456,
  "status": "running",
  "estimatedDuration": 300
}
```

---

#### `GET /api/simulation/results/:runId`
Get simulation results.

**Response**:
```json
{
  "runId": 456,
  "scenarioId": 1,
  "status": "completed",
  "results": {
    "performance": { ... },
    "indexesCreated": [ ... ],
    "algorithmsUsed": [ ... ],
    "benchmark": { ... }
  }
}
```

---

#### `GET /api/simulation/history`
Get historical simulation runs.

**Query Parameters**:
- `scenarioId` (optional): Filter by scenario
- `limit` (optional): Number of results (default: 50)
- `offset` (optional): Pagination offset

---

### Live Mode Endpoints

#### `GET /api/live/config`
Get live mode configuration.

**Response**:
```json
{
  "autoIndexingEnabled": true,
  "performanceTracking": { ... },
  "alertThresholds": { ... },
  "retentionPolicy": { ... }
}
```

---

#### `PUT /api/live/config`
Update live mode configuration.

**Request**:
```json
{
  "autoIndexingEnabled": false,
  "alertThresholds": {
    "latencyMs": 100
  }
}
```

---

### Comparison Endpoints

#### `GET /api/compare/simulation-vs-live`
Compare simulation predictions with live performance.

**Query Parameters**:
- `simulationRunId`: Simulation run ID
- `liveTimeRange`: Time range for live data (e.g., "7d")
- `metrics`: Comma-separated list of metrics to compare

**Response**:
```json
{
  "comparison": {
    "latency": {
      "simulation": 2.5,
      "live": 2.8,
      "difference": 0.3,
      "accuracy": 89.3
    },
    "indexHits": { ... },
    "queryThroughput": { ... }
  },
  "alignment": {
    "indexDecisions": 0.85,
    "performanceTrends": 0.92
  }
}
```

---

## Frontend Implementation

### Component Structure

```
ui/
├── app/
│   ├── dashboard/
│   │   ├── layout.tsx              # Mode toggle in header
│   │   ├── live/
│   │   │   └── page.tsx            # Live mode dashboard
│   │   ├── simulation/
│   │   │   ├── page.tsx            # Simulation mode dashboard
│   │   │   ├── scenarios/
│   │   │   │   ├── page.tsx        # Scenario list
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx    # Scenario details
│   │   │   │       └── edit/
│   │   │   │           └── page.tsx # Scenario editor
│   │   │   └── results/
│   │   │       └── [runId]/
│   │   │           └── page.tsx    # Simulation results
│   │   └── compare/
│   │       └── page.tsx            # Comparison dashboard
│   └── settings/
│       ├── simulation/
│       │   └── page.tsx            # Simulation config
│       └── live/
│           └── page.tsx            # Live mode config
├── components/
│   ├── mode-toggle.tsx             # Mode toggle component
│   ├── simulation/
│   │   ├── scenario-card.tsx
│   │   ├── scenario-editor.tsx
│   │   ├── simulation-runner.tsx
│   │   └── results-viewer.tsx
│   ├── live/
│   │   ├── performance-dashboard.tsx
│   │   └── live-config.tsx
│   └── compare/
│       └── comparison-view.tsx
└── lib/
    ├── api.ts                      # API client (extend with simulation endpoints)
    └── mode-context.tsx             # React context for mode state
```

---

### Mode Context Provider

**File**: `ui/lib/mode-context.tsx`

```typescript
import { createContext, useContext, useState, ReactNode } from 'react';

type Mode = 'live' | 'simulation' | 'compare';

interface ModeContextType {
  mode: Mode;
  setMode: (mode: Mode) => void;
  config: {
    simulation: SimulationConfig;
    live: LiveModeConfig;
  };
  updateConfig: (mode: 'simulation' | 'live', config: any) => void;
}

const ModeContext = createContext<ModeContextType | undefined>(undefined);

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>('live');
  const [config, setConfig] = useState({ ... });

  return (
    <ModeContext.Provider value={{ mode, setMode, config, updateConfig }}>
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  const context = useContext(ModeContext);
  if (!context) {
    throw new Error('useMode must be used within ModeProvider');
  }
  return context;
}
```

---

### Mode Toggle Component

**File**: `ui/components/mode-toggle.tsx`

```typescript
'use client';

import { useMode } from '@/lib/mode-context';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export function ModeToggle() {
  const { mode, setMode } = useMode();

  return (
    <Select value={mode} onValueChange={(value) => setMode(value as Mode)}>
      <SelectTrigger className="w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="live">
          🟢 Live Mode
        </SelectItem>
        <SelectItem value="simulation">
          🔵 Simulation Mode
        </SelectItem>
        <SelectItem value="compare">
          ⚖️ Comparison Mode
        </SelectItem>
      </SelectContent>
    </Select>
  );
}
```

---

## Backend Implementation

### New Modules

#### `src/simulation/api_endpoints.py`
Add simulation API endpoints to `src/api_server.py` or create separate router.

**Endpoints**:
- `GET /api/simulation/scenarios`
- `POST /api/simulation/scenarios`
- `PUT /api/simulation/scenarios/:id`
- `DELETE /api/simulation/scenarios/:id`
- `POST /api/simulation/run`
- `GET /api/simulation/results/:runId`
- `GET /api/simulation/history`

---

#### `src/simulation/scenario_manager.py`
Manage simulation scenarios (CRUD operations, storage).

**Features**:
- Store scenarios in database (`simulation_scenarios` table)
- Load scenario configurations
- Validate scenario definitions
- Track scenario run history

---

#### `src/historical_tracking.py` (from REMAINING_WORK_SUMMARY.md)
Historical performance tracking service.

**Features**:
- Aggregate `query_stats` into daily/weekly/monthly tables
- Retention policy management
- Historical trend analysis
- Integration with simulation results

---

## Database Schema Changes

### New Tables

#### `simulation_scenarios`
```sql
CREATE TABLE simulation_scenarios (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    scenario_type VARCHAR(50) NOT NULL, -- 'baseline', 'autoindex', 'comprehensive'
    data_size VARCHAR(50) NOT NULL, -- 'small', 'medium', 'large', 'stress-test'
    config_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255)
);
```

---

#### `simulation_runs`
```sql
CREATE TABLE simulation_runs (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES simulation_scenarios(id),
    status VARCHAR(50) NOT NULL, -- 'running', 'completed', 'failed'
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    results_json JSONB,
    benchmark_json JSONB,
    created_by VARCHAR(255)
);
```

---

#### `performance_aggregates_daily`
```sql
CREATE TABLE performance_aggregates_daily (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    tenant_id INTEGER,
    query_count BIGINT,
    avg_latency_ms NUMERIC,
    p95_latency_ms NUMERIC,
    p99_latency_ms NUMERIC,
    index_hits BIGINT,
    index_misses BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, tenant_id)
);
```

---

#### `performance_aggregates_weekly`
```sql
CREATE TABLE performance_aggregates_weekly (
    id SERIAL PRIMARY KEY,
    week_start DATE NOT NULL,
    tenant_id INTEGER,
    query_count BIGINT,
    avg_latency_ms NUMERIC,
    p95_latency_ms NUMERIC,
    p99_latency_ms NUMERIC,
    index_hits BIGINT,
    index_misses BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(week_start, tenant_id)
);
```

---

## Implementation Phases

### Phase 1: Core Mode Toggle (Week 1-2)
- ✅ Create mode context and provider
- ✅ Build mode toggle component
- ✅ Update dashboard layout to include toggle
- ✅ Create basic live/simulation/compare page structure

**Effort**: Low (1-2 weeks)

---

### Phase 2: Simulation Mode UI (Week 3-4)
- ✅ Scenario list view
- ✅ Scenario editor
- ✅ Simulation runner component
- ✅ Results viewer
- ✅ Simulation API endpoints

**Effort**: Medium (2 weeks)

---

### Phase 3: Configuration Management (Week 5-6)
- ✅ Simulation configuration panel
- ✅ Live mode configuration panel
- ✅ Configuration API endpoints
- ✅ Settings pages

**Effort**: Medium (2 weeks)

---

### Phase 4: Historical Tracking Integration (Week 7-8)
- ✅ Implement `src/historical_tracking.py`
- ✅ Create aggregate tables
- ✅ Add retention policy management
- ✅ Extend API endpoints with time range support
- ✅ Update UI to show historical data

**Effort**: Medium (2 weeks)

---

### Phase 5: Comparison Mode (Week 9-10)
- ✅ Comparison dashboard
- ✅ Comparison API endpoints
- ✅ Side-by-side visualization
- ✅ Gap analysis

**Effort**: Medium (2 weeks)

---

## Benefits

### For Users

1. **Unified Interface**: Single dashboard for both simulation and live modes
2. **Easy Testing**: Run simulations before applying to production
3. **Performance Validation**: Compare simulation predictions with actual results
4. **Configuration Management**: Centralized configuration for both modes
5. **Historical Analysis**: Long-term performance tracking and trends

---

### For Developers

1. **Better Testing**: Easy way to test index strategies before production
2. **Performance Monitoring**: Unified view of simulation and live performance
3. **Debugging**: Compare expected vs actual behavior
4. **Documentation**: Simulation scenarios serve as documentation

---

## Related Features

- **Historical Performance Tracking** (`REMAINING_WORK_SUMMARY.md` Part 2, Item 6)
- **Performance Dashboards** (`REMAINING_WORK_SUMMARY.md` Part 2, Item 1)
- **Index Health Monitoring Dashboard** (`REMAINING_WORK_SUMMARY.md` Part 2, Item 2)

---

## Future Enhancements

1. **Automated Simulation Scheduling**: Run simulations on schedule (daily/weekly)
2. **Simulation Templates**: Pre-built templates for common scenarios
3. **A/B Testing Integration**: Use simulation mode for A/B testing index strategies
4. **ML Model Training**: Use simulation data to train ML models
5. **Performance Forecasting**: Predict future performance based on simulation and historical data

---

**Document Created**: 10-12-2025  
**Status**: ⚠️ **PLANNED** - Future Phase Feature  
**Priority**: **MEDIUM** - Important for user experience and testing capabilities  
**Estimated Effort**: 8-10 weeks (phased implementation)

