# IndexPilot - Architecture Diagrams

**Date**: 08-12-2025  
**Purpose**: Visual architecture diagrams for IndexPilot system  
**Status**: ✅ Complete

---

## System Architecture Overview

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Next.js Dashboard<br/>Performance, Health, Decisions]
        Browser[Web Browser]
    end
    
    subgraph "API Layer"
        API[FastAPI Server<br/>REST API Endpoints<br/>Port 8000]
        OpenAPI[OpenAPI/Swagger Docs<br/>/docs, /redoc]
    end
    
    subgraph "IndexPilot Control Layer"
        subgraph "Core Components"
            Genome[Genome Catalog<br/>Canonical Schema]
            Expression[Expression Profiles<br/>Per-Tenant Activation]
            Stats[Query Statistics<br/>Performance Metrics]
            AutoIndexer[Auto-Indexer<br/>Cost-Benefit Analysis]
        end
        
        subgraph "Production Safeguards"
            LockMgr[Lock Manager]
            RateLimit[Rate Limiter]
            CPUThrottle[CPU Throttle]
            MaintWindow[Maintenance Window]
            WritePerf[Write Performance]
        end
        
        subgraph "Query Optimization"
            QueryAnalyzer[Query Analyzer<br/>EXPLAIN Analysis]
            QueryInterceptor[Query Interceptor<br/>Proactive Blocking]
            PatternDetect[Pattern Detection]
        end
        
        subgraph "Academic Algorithms"
            CERT[CERT]
            QPG[QPG]
            Cortex[Cortex]
            Predictive[Predictive Indexing]
            XGBoost[XGBoost]
            PGM[PGM-Index]
            ALEX[ALEX]
            RSS[RadixStringSpline]
            Fractal[Fractal Tree]
            iDist[iDistance]
            BxTree[Bx-tree]
            Constraint[Constraint Optimizer]
        end
        
        subgraph "Operational"
            Maintenance[Maintenance Tasks<br/>13+ Steps]
            Health[Health Checks]
            Monitoring[Monitoring]
            Audit[Audit Trail]
        end
    end
    
    subgraph "Database Layer"
        DB[(PostgreSQL Database)]
        subgraph "Metadata Tables"
            GenomeCatalog[genome_catalog]
            ExpressionProfile[expression_profile]
            MutationLog[mutation_log]
            QueryStats[query_stats]
        end
        subgraph "Business Tables"
            Tenants[tenants]
            Contacts[contacts]
            Organizations[organizations]
            Interactions[interactions]
        end
        Indexes[(Auto-Created Indexes)]
    end
    
    Browser -->|HTTP| UI
    UI -->|HTTP/REST| API
    API -->|Calls| AutoIndexer
    API -->|Calls| Health
    API -->|Calls| Stats
    API -->|Calls| QueryAnalyzer
    OpenAPI -->|Documentation| API
    
    AutoIndexer -->|Uses| Stats
    AutoIndexer -->|Uses| QueryAnalyzer
    AutoIndexer -->|Uses| PatternDetect
    AutoIndexer -->|Uses| CERT
    AutoIndexer -->|Uses| Predictive
    AutoIndexer -->|Uses| Constraint
    
    QueryAnalyzer -->|Uses| QPG
    PatternDetect -->|Uses| Cortex
    PatternDetect -->|Uses| iDist
    PatternDetect -->|Uses| BxTree
    
    AutoIndexer -->|Checks| LockMgr
    AutoIndexer -->|Checks| RateLimit
    AutoIndexer -->|Checks| CPUThrottle
    AutoIndexer -->|Checks| MaintWindow
    AutoIndexer -->|Checks| WritePerf
    
    Maintenance -->|Uses| Stats
    Maintenance -->|Uses| QueryAnalyzer
    Maintenance -->|Uses| Multiple Algorithms
    
    AutoIndexer -->|Creates| Indexes
    QueryInterceptor -->|Blocks| DB
    QueryAnalyzer -->|Analyzes| DB
    
    Stats -->|Stores| QueryStats
    Genome -->|Stores| GenomeCatalog
    Expression -->|Stores| ExpressionProfile
    Audit -->|Stores| MutationLog
    
    DB -->|Contains| GenomeCatalog
    DB -->|Contains| ExpressionProfile
    DB -->|Contains| MutationLog
    DB -->|Contains| QueryStats
    DB -->|Contains| Tenants
    DB -->|Contains| Contacts
    DB -->|Contains| Organizations
    DB -->|Contains| Interactions
    DB -->|Contains| Indexes
```

---

## Component Dependency Diagram

```mermaid
graph TD
    subgraph "Base Layer"
        DB[db.py<br/>Connection Pool]
        Config[config_loader.py<br/>Configuration]
        Types[type_definitions.py<br/>Type Definitions]
    end
    
    subgraph "Core Layer"
        Stats[stats.py]
        Genome[genome.py]
        Expression[expression.py]
        Validation[validation.py]
        Rollback[rollback.py]
    end
    
    subgraph "Query Layer"
        QueryAnalyzer[query_analyzer.py]
        QueryInterceptor[query_interceptor.py]
        QueryPatterns[query_patterns.py]
        PatternDetect[pattern_detection.py]
    end
    
    subgraph "Index Layer"
        AutoIndexer[auto_indexer.py]
        IndexType[index_type_selection.py]
        IndexHealth[index_health.py]
        IndexCleanup[index_cleanup.py]
    end
    
    subgraph "Algorithm Layer"
        CERT[algorithms/cert.py]
        QPG[algorithms/qpg.py]
        Cortex[algorithms/cortex.py]
        Predictive[algorithms/predictive_indexing.py]
        Constraint[algorithms/constraint_optimizer.py]
    end
    
    subgraph "Production Layer"
        LockMgr[lock_manager.py]
        RateLimit[rate_limiter.py]
        CPUThrottle[cpu_throttle.py]
        MaintWindow[maintenance_window.py]
        WritePerf[write_performance.py]
    end
    
    subgraph "Operational Layer"
        Maintenance[maintenance.py]
        Health[health_check.py]
        Monitoring[monitoring.py]
        Audit[audit.py]
    end
    
    subgraph "Integration Layer"
        API[api_server.py]
        Simulator[simulator.py]
    end
    
    DB --> Stats
    DB --> Genome
    DB --> Expression
    DB --> QueryAnalyzer
    DB --> AutoIndexer
    
    Config --> Stats
    Config --> AutoIndexer
    Config --> QueryAnalyzer
    Config --> Maintenance
    
    Stats --> AutoIndexer
    Genome --> Expression
    Validation --> Stats
    Validation --> AutoIndexer
    Rollback --> Stats
    Rollback --> AutoIndexer
    
    QueryAnalyzer --> QueryInterceptor
    QueryAnalyzer --> AutoIndexer
    QueryPatterns --> AutoIndexer
    PatternDetect --> AutoIndexer
    
    QPG --> QueryAnalyzer
    CERT --> AutoIndexer
    Cortex --> PatternDetect
    Predictive --> AutoIndexer
    Constraint --> AutoIndexer
    
    LockMgr --> AutoIndexer
    RateLimit --> AutoIndexer
    CPUThrottle --> AutoIndexer
    MaintWindow --> AutoIndexer
    WritePerf --> AutoIndexer
    
    Maintenance --> Stats
    Maintenance --> QueryAnalyzer
    Maintenance --> AutoIndexer
    Maintenance --> IndexHealth
    Maintenance --> IndexCleanup
    Maintenance --> Multiple Algorithms
    
    AutoIndexer --> API
    Stats --> API
    Health --> API
    
    Simulator --> AutoIndexer
    Simulator --> Stats
    Simulator --> Expression
```

---

## Index Creation Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    participant App as Application
    participant Stats as Query Stats
    participant DB as PostgreSQL
    participant AutoIndexer as Auto-Indexer
    participant QueryAnalyzer as Query Analyzer
    participant Algorithms as Algorithms
    participant Safeguards as Production Safeguards
    participant LockMgr as Lock Manager
    participant Audit as Audit Trail
    
    App->>Stats: log_query_stat(tenant_id, table, field, query_type, duration)
    Stats->>DB: INSERT INTO query_stats (batched)
    
    Note over AutoIndexer: Periodic Analysis (every 5 minutes)
    AutoIndexer->>Stats: get_field_usage_stats(table, field)
    Stats->>DB: SELECT aggregated statistics
    Stats-->>AutoIndexer: Usage statistics
    
    AutoIndexer->>QueryAnalyzer: analyze_query_plan(sample_query)
    QueryAnalyzer->>DB: EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
    DB-->>QueryAnalyzer: Query plan with costs
    QueryAnalyzer-->>AutoIndexer: Plan analysis
    
    AutoIndexer->>Algorithms: validate_cardinality_with_cert()
    Algorithms->>DB: Check actual vs estimated cardinality
    Algorithms-->>AutoIndexer: Selectivity validation
    
    AutoIndexer->>Algorithms: predict_index_utility()
    Algorithms-->>AutoIndexer: ML utility prediction
    
    AutoIndexer->>Algorithms: optimize_index_with_constraints()
    Algorithms-->>AutoIndexer: Constraint-optimized decision
    
    AutoIndexer->>AutoIndexer: should_create_index()<br/>Cost-benefit analysis
    
    alt Index Creation Recommended
        AutoIndexer->>Safeguards: Check maintenance window
        Safeguards-->>AutoIndexer: Window status
        
        AutoIndexer->>Safeguards: Check rate limits
        Safeguards-->>AutoIndexer: Rate limit status
        
        AutoIndexer->>Safeguards: Check CPU usage
        Safeguards-->>AutoIndexer: CPU status
        
        AutoIndexer->>Safeguards: Check write performance
        Safeguards-->>AutoIndexer: Write performance status
        
        AutoIndexer->>LockMgr: Acquire advisory lock
        LockMgr->>DB: pg_advisory_lock()
        LockMgr-->>AutoIndexer: Lock acquired
        
        AutoIndexer->>DB: CREATE INDEX CONCURRENTLY
        DB-->>AutoIndexer: Index created
        
        AutoIndexer->>QueryAnalyzer: measure_query_performance(before/after)
        QueryAnalyzer->>DB: Execute sample queries
        QueryAnalyzer-->>AutoIndexer: Performance metrics
        
        AutoIndexer->>Audit: log_audit_event(CREATE_INDEX)
        Audit->>DB: INSERT INTO mutation_log
        
        AutoIndexer->>LockMgr: Release advisory lock
        LockMgr->>DB: pg_advisory_unlock()
    else Index Not Recommended
        AutoIndexer->>Audit: log_audit_event(SKIP_INDEX)
        Audit->>DB: INSERT INTO mutation_log
    end
```

---

## Query Interception Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    participant App as Application
    participant Interceptor as Query Interceptor
    participant Cache as Plan Cache
    participant QueryAnalyzer as Query Analyzer
    participant DB as PostgreSQL
    participant ML as ML Classifier
    
    App->>Interceptor: intercept_query(query, params)
    
    Interceptor->>Interceptor: Normalize query signature
    
    Interceptor->>Cache: Check plan cache
    alt Cache Hit
        Cache-->>Interceptor: Cached plan analysis
    else Cache Miss
        Interceptor->>QueryAnalyzer: analyze_query_plan_fast(query)
        QueryAnalyzer->>DB: EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
        DB-->>QueryAnalyzer: Query plan
        QueryAnalyzer->>QueryAnalyzer: Analyze plan (QPG enhancement)
        QueryAnalyzer-->>Interceptor: Plan analysis
        Interceptor->>Cache: Store in cache (LRU, TTL)
    end
    
    Interceptor->>Interceptor: Calculate safety score
    
    alt Safety Score < Threshold
        Interceptor->>ML: predict_query_risk_ml(query)
        ML-->>Interceptor: ML risk prediction
    end
    
    alt Query Blocked
        Interceptor-->>App: QueryBlockedError(reason, plan)
        Note over App: Query not executed
    else Query Allowed
        Interceptor-->>App: Query approved
        App->>DB: Execute query
        DB-->>App: Query results
    end
```

---

## Maintenance Workflow (Flowchart)

```mermaid
flowchart TD
    Start([Maintenance Task<br/>Triggered]) --> CheckBypass{Maintenance<br/>Enabled?}
    CheckBypass -->|No| End([Skip Maintenance])
    CheckBypass -->|Yes| Step1[Step 1: System Health Check]
    
    Step1 --> Step2[Step 2: Database Integrity Check]
    Step2 --> Step3[Step 3: Connection Pool Health]
    Step3 --> Step4[Step 4: Index Creation Analysis]
    
    Step4 --> Step5[Step 5: Index Health Monitoring]
    Step5 --> Step6[Step 6: Unused Index Detection]
    Step6 --> Step7[Step 7: Automatic REINDEX Scheduling]
    
    Step7 --> Step8[Step 8: Query Pattern Learning]
    Step8 --> Step9[Step 9: Statistics Refresh]
    Step9 --> Step10[Step 10: Redundant Index Detection]
    
    Step10 --> Step11[Step 11: Workload Analysis]
    Step11 --> Step12[Step 12: Foreign Key Suggestions]
    Step12 --> Step13[Step 13: Concurrent Index Monitoring]
    
    Step13 --> Step14[Step 14: Materialized View Support]
    Step14 --> Step15[Step 15: Safeguard Monitoring]
    Step15 --> Step16[Step 16: Predictive Maintenance]
    
    Step16 --> Step17[Step 17: ML Query Interception Training]
    Step17 --> LogResults[Log Results to Audit Trail]
    LogResults --> End([Maintenance Complete])
    
    style Start fill:#90EE90
    style End fill:#90EE90
    style CheckBypass fill:#FFE4B5
```

---

## Data Flow Diagram (Level 0 - Context)

```mermaid
graph LR
    App[Host Application] -->|Queries| IndexPilot[IndexPilot System]
    IndexPilot -->|SQL Queries| DB[(PostgreSQL)]
    DB -->|Query Results| App
    IndexPilot -->|Index Creation| DB
    IndexPilot -->|Statistics| DB
    DB -->|Query Plans| IndexPilot
```

---

## Data Flow Diagram (Level 1 - Main Processes)

```mermaid
graph TD
    subgraph "IndexPilot System"
        P1[1.0 Query Statistics<br/>Collection]
        P2[2.0 Index Analysis<br/>& Decision]
        P3[3.0 Index Creation<br/>& Management]
        P4[4.0 Query Interception<br/>& Optimization]
        P5[5.0 Maintenance<br/>& Monitoring]
    end
    
    subgraph "Data Stores"
        D1[(D1: query_stats)]
        D2[(D2: genome_catalog)]
        D3[(D3: expression_profile)]
        D4[(D4: mutation_log)]
        D5[(D5: Database Indexes)]
    end
    
    App[Host Application] -->|Queries| P1
    App -->|Queries| P4
    P1 -->|Store Statistics| D1
    P1 -->|Read Schema| D2
    P1 -->|Read Expression| D3
    
    P2 -->|Read Statistics| D1
    P2 -->|Read Schema| D2
    P2 -->|Read Expression| D3
    P2 -->|Read Indexes| D5
    
    P3 -->|Create/Update| D5
    P3 -->|Log Changes| D4
    P3 -->|Read Schema| D2
    
    P4 -->|Read Statistics| D1
    P4 -->|Read Indexes| D5
    P4 -->|Block/Allow| App
    
    P5 -->|Read All| D1
    P5 -->|Read All| D2
    P5 -->|Read All| D3
    P5 -->|Read All| D4
    P5 -->|Manage| D5
    
    P3 -->|SQL| DB[(PostgreSQL)]
    P4 -->|SQL| DB
    P1 -->|SQL| DB
    P2 -->|SQL| DB
    P5 -->|SQL| DB
```

---

## Algorithm Integration Flow

```mermaid
graph LR
    subgraph "Input"
        Stats[Query Statistics]
        QueryPlan[Query Plans]
        TableInfo[Table Information]
    end
    
    subgraph "Algorithm Layer"
        CERT[CERT<br/>Cardinality Validation]
        QPG[QPG<br/>Plan Analysis]
        Cortex[Cortex<br/>Correlation]
        Predictive[Predictive<br/>ML Utility]
        Constraint[Constraint<br/>Optimization]
    end
    
    subgraph "Decision Engine"
        AutoIndexer[Auto-Indexer<br/>Cost-Benefit]
    end
    
    subgraph "Output"
        Decision[Index Decision<br/>Create/Skip]
    end
    
    Stats --> CERT
    Stats --> Predictive
    Stats --> Constraint
    QueryPlan --> QPG
    TableInfo --> Cortex
    TableInfo --> Predictive
    
    CERT --> AutoIndexer
    QPG --> AutoIndexer
    Cortex --> AutoIndexer
    Predictive --> AutoIndexer
    Constraint --> AutoIndexer
    
    AutoIndexer --> Decision
```

---

## Notes

1. **Diagram Format**: All diagrams use Mermaid syntax for easy rendering in Markdown viewers
2. **Rendering**: Diagrams can be viewed in:
   - GitHub/GitLab (native support)
   - VS Code with Mermaid extension
   - Online Mermaid editor: https://mermaid.live
3. **Maintenance**: Update diagrams when architecture changes
4. **Version**: Diagrams reflect architecture as of 08-12-2025

---

**Last Updated**: 08-12-2025  
**Status**: ✅ Complete

