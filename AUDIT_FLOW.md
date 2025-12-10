# IndexPilot Audit Flow & Verification Steps

This document outlines a comprehensive step-by-step audit flow to verify the completeness, mathematical correctness, logic, and implementation quality of the IndexPilot codebase.

**Usage:** Execute the Cursor commands (or equivalent terminal commands) in order.

## Phase 1: Environment & Code Quality Setup

1.  **Verify Environment Setup**
    *   Command: `ls -R` (Check project structure)
    *   Action: Ensure virtual environment is active (`source venv/bin/activate` or `venv\Scripts\activate`).

2.  **Static Analysis (Linting & Types)**
    *   Command: `make check` (or `python -m ruff check src` and `python -m mypy src`)
    *   *Goal:* Ensure no syntax errors, undefined variables, or type mismatches before deep dive.

3.  **Test Suite Execution**
    *   Command: `make run-tests` (or `pytest tests/`)
    *   *Goal:* Verify all unit tests pass. Check test coverage with `pytest --cov=src tests/`
    *   *Audit Question:* Are critical paths covered by tests? Are edge cases tested?

## Phase 2: Core Algorithms Audit (Math & Logic)

Verify each algorithm against its reference paper or intended logic.

### 1. CERT (Cardinality Estimation Restriction Testing)
*   **Target:** `src/algorithms/cert.py`
*   **Reference:** arXiv:2306.00355
*   **Cursor Action:**
    *   `read_file src/algorithms/cert.py`
    *   *Audit Question:* Does the implementation correctly apply restriction testing for cardinality? Are the math formulas for estimation bounds correct?

### 2. Query Plan Guidance (QPG)
*   **Target:** `src/algorithms/qpg.py`
*   **Reference:** arXiv:2312.17510
*   **Cursor Action:**
    *   `read_file src/algorithms/qpg.py`
    *   *Audit Question:* Is the query plan extraction and guidance logic sound? Does it correctly parse EXPLAIN output?

### 3. Data Correlation Exploitation (Cortex)
*   **Target:** `src/algorithms/cortex.py`
*   **Reference:** arXiv:2012.06683
*   **Cursor Action:**
    *   `read_file src/algorithms/cortex.py`
    *   *Audit Question:* Are correlation coefficients calculated correctly? Is the exploitation of correlated columns implemented efficiently?

### 4. Predictive Indexing (ML)
*   **Target:** `src/algorithms/predictive_indexing.py`
*   **Reference:** arXiv:1901.07064
*   **Cursor Action:**
    *   `read_file src/algorithms/predictive_indexing.py`
    *   *Audit Question:* Check the model training and prediction flow. Is the feature engineering sound?

### 5. XGBoost Pattern Classification
*   **Target:** `src/algorithms/xgboost_classifier.py`
*   **Reference:** arXiv:1603.02754
*   **Cursor Action:**
    *   `read_file src/algorithms/xgboost_classifier.py`
    *   *Audit Question:* Verify XGBoost parameters and training logic. Is the classification output used correctly for indexing decisions?

### 6. PGM-Index
*   **Target:** `src/algorithms/pgm_index.py`
*   **Reference:** arXiv:1910.06169
*   **Cursor Action:**
    *   `read_file src/algorithms/pgm_index.py`
    *   *Audit Question:* Verify the piecewise geometric model construction. Are the error bounds respected?

### 7. Adaptive Learned Index (ALEX)
*   **Target:** `src/algorithms/alex.py`
*   **Reference:** arXiv:1905.08898
*   **Cursor Action:**
    *   `read_file src/algorithms/alex.py`
    *   *Audit Question:* Check the adaptive structure updates. Is the model retraining triggered correctly?

### 8. Other Algorithms
*   **Targets:**
    *   `src/algorithms/radix_string_spline.py` (Radix Spline)
    *   `src/algorithms/fractal_tree.py` (Fractal Tree)
    *   `src/algorithms/idistance.py` (iDistance)
    *   `src/algorithms/bx_tree.py` (Bx-tree)
    *   `src/algorithms/constraint_optimizer.py` (Constraint Optimization)
*   **Cursor Action:**
    *   `read_file src/algorithms/<filename>` for each.
    *   *Audit Question:* Verify data structures and algorithmic complexity.

## Phase 3: Core Logic & Architecture Review

### 1. Auto-Indexer Logic
*   **Target:** `src/auto_indexer.py`
*   **Cursor Action:**
    *   `read_file src/auto_indexer.py`
    *   *Audit Question:* Trace `analyze_queries` -> `_calculate_benefit` -> `create_index`. Is the Cost-Benefit Analysis (CBA) formula robust? Does it handle edge cases (zero frequency, high cost)? Are all algorithms properly integrated into the decision flow?

### 2. Genome & Expression (Multi-tenancy)
*   **Target:** `src/genome.py`, `src/expression.py`
*   **Cursor Action:**
    *   `read_file src/genome.py`
    *   `read_file src/expression.py`
    *   *Audit Question:* How is the canonical schema defined? Does `expression.py` correctly filter fields per tenant? Are multi-tenant isolation guarantees maintained?

### 3. Query Analysis & Patterns
*   **Target:** `src/query_analyzer.py`, `src/query_patterns.py`, `src/query_pattern_learning.py`
*   **Cursor Action:**
    *   `read_file src/query_analyzer.py`
    *   `read_file src/query_patterns.py`
    *   `read_file src/query_pattern_learning.py`
    *   *Audit Question:* Is the SQL parsing accurate? Are query patterns correctly fingerprinting similar queries? Does pattern learning improve over time?

### 4. Schema Auto-Discovery
*   **Target:** `src/schema/auto_discovery.py`, `src/schema/discovery.py`
*   **Cursor Action:**
    *   `read_file src/schema/auto_discovery.py`
    *   `read_file src/schema/discovery.py`
    *   *Audit Question:* Does auto-discovery correctly identify tables, columns, types, constraints? Are metadata tables properly excluded? Is the discovered schema compatible with genome catalog format?

## Phase 4: Database & Connection Management Audit

### 1. Connection Pooling
*   **Target:** `src/db.py`
*   **Cursor Action:**
    *   `read_file src/db.py`
    *   *Audit Question:* Is connection pooling thread-safe? Are connection limits enforced? Does it handle pool exhaustion gracefully? Are connections properly validated before use? Is SSL/TLS enforced in production?

### 2. Database Adapters
*   **Target:** `src/database/adapters/base.py`, `src/database/adapters/postgresql.py`
*   **Cursor Action:**
    *   `read_file src/database/adapters/base.py`
    *   `read_file src/database/adapters/postgresql.py`
    *   *Audit Question:* Is the adapter pattern correctly implemented? Does PostgreSQL adapter generate correct SQL? Are database-specific features handled properly?

### 3. Host Integration Adapters
*   **Target:** `src/adapters.py`
*   **Cursor Action:**
    *   `read_file src/adapters.py`
    *   *Audit Question:* Can IndexPilot integrate with host application's database pool? Are monitoring adapters properly wired? Does error tracking integration work?

## Phase 5: Index Lifecycle & Advanced Features Audit

### 1. Index Lifecycle Management
*   **Target:** `src/index_lifecycle_manager.py`, `src/index_lifecycle_advanced.py`, `src/index_cleanup.py`
*   **Cursor Action:**
    *   `read_file src/index_lifecycle_manager.py`
    *   `read_file src/index_lifecycle_advanced.py`
    *   `read_file src/index_cleanup.py`
    *   *Audit Question:* Are unused indexes detected correctly? Is index versioning tracked? Are lifecycle transitions handled properly?

### 2. Index Health Monitoring
*   **Target:** `src/index_health.py`, `src/concurrent_index_monitoring.py`
*   **Cursor Action:**
    *   `read_file src/index_health.py`
    *   `read_file src/concurrent_index_monitoring.py`
    *   *Audit Question:* Is index bloat detected? Are index statistics monitored? Is concurrent index creation monitored safely?

### 3. Redundant Index Detection
*   **Target:** `src/redundant_index_detection.py`
*   **Cursor Action:**
    *   `read_file src/redundant_index_detection.py`
    *   *Audit Question:* Are redundant indexes correctly identified? Is index consolidation logic sound?

### 4. Composite Index Detection
*   **Target:** `src/composite_index_detection.py`
*   **Cursor Action:**
    *   `read_file src/composite_index_detection.py`
    *   *Audit Question:* Are multi-column index opportunities detected? Is column ordering optimized?

### 5. Foreign Key Suggestions
*   **Target:** `src/foreign_key_suggestions.py`
*   **Cursor Action:**
    *   `read_file src/foreign_key_suggestions.py`
    *   *Audit Question:* Are foreign keys without indexes detected? Is join pattern analysis accurate?

### 6. Materialized View Support
*   **Target:** `src/materialized_view_support.py`
*   **Cursor Action:**
    *   `read_file src/materialized_view_support.py`
    *   *Audit Question:* Are materialized view refresh strategies correct? Is view dependency tracking accurate?

### 7. Index Type Selection
*   **Target:** `src/index_type_selection.py`
*   **Cursor Action:**
    *   `read_file src/index_type_selection.py`
    *   *Audit Question:* Is the correct index type (B-tree, partial, expression, GIN, GiST) selected for each use case?

### 8. Index Retry Logic
*   **Target:** `src/index_retry.py`
*   **Cursor Action:**
    *   `read_file src/index_retry.py`
    *   *Audit Question:* Are retryable errors correctly identified? Is exponential backoff implemented? Are retry limits enforced?

## Phase 6: Safety & Production Hardening Audit

### 1. Rollback & Bypass
*   **Target:** `src/rollback.py`, `src/bypass_config.py`, `src/bypass_status.py`
*   **Cursor Action:**
    *   `read_file src/rollback.py`
    *   `read_file src/bypass_config.py`
    *   *Audit Question:* Can the system effectively disable features on failure? Verify the 4-level bypass logic (feature/module/system/startup). Is emergency bypass functional?

### 2. Rate Limiting & Throttling
*   **Target:** `src/rate_limiter.py`, `src/cpu_throttle.py`
*   **Cursor Action:**
    *   `read_file src/rate_limiter.py`
    *   `read_file src/cpu_throttle.py`
    *   *Audit Question:* Is the token bucket or window logic correct? Does it prevent index storms? Is CPU throttling effective during index creation?

### 3. Lock Management
*   **Target:** `src/lock_manager.py`
*   **Cursor Action:**
    *   `read_file src/lock_manager.py`
    *   *Audit Question:* Are database locks acquired correctly? Is deadlock prevention implemented? Are locks released properly on errors?

### 4. Monitoring & Health
*   **Target:** `src/monitoring.py`, `src/health_check.py`, `src/safeguard_monitoring.py`
*   **Cursor Action:**
    *   `read_file src/monitoring.py`
    *   `read_file src/health_check.py`
    *   *Audit Question:* Are metrics being collected (Prometheus/Logs)? Is the health check endpoint reliable? Are safeguard violations monitored?

### 5. Error Handling & Resilience
*   **Target:** `src/error_handler.py`, `src/resilience.py`, `src/graceful_shutdown.py`
*   **Cursor Action:**
    *   `read_file src/error_handler.py`
    *   `read_file src/resilience.py`
    *   `read_file src/graceful_shutdown.py`
    *   *Audit Question:* Are errors handled gracefully? Is circuit breaker logic correct? Does graceful shutdown clean up resources properly?

### 6. Input Validation & Security
*   **Target:** `src/validation.py`
*   **Cursor Action:**
    *   `read_file src/validation.py`
    *   *Audit Question:* Is SQL injection prevented? Are identifiers validated? Are dangerous SQL keywords filtered?

### 7. Adaptive Safeguards
*   **Target:** `src/adaptive_safeguards.py`
*   **Cursor Action:**
    *   `read_file src/adaptive_safeguards.py`
    *   *Audit Question:* Do safeguards adapt based on system performance? Are thresholds adjusted dynamically?

### 8. Before/After Validation
*   **Target:** `src/before_after_validation.py`
*   **Cursor Action:**
    *   `read_file src/before_after_validation.py`
    *   *Audit Question:* Is query performance measured before and after index creation? Are regressions detected?

## Phase 7: Configuration & Resource Management Audit

### 1. Configuration Management
*   **Target:** `src/config_loader.py`, `src/production_config.py`, `src/per_tenant_config.py`
*   **Cursor Action:**
    *   `read_file src/config_loader.py`
    *   `read_file src/production_config.py`
    *   *Audit Question:* Are configuration files loaded correctly? Are environment variable overrides applied? Is configuration validation robust? Are per-tenant configs isolated?

### 2. Storage Budget
*   **Target:** `src/storage_budget.py`
*   **Cursor Action:**
    *   `read_file src/storage_budget.py`
    *   *Audit Question:* Is storage usage tracked accurately? Are budget limits enforced? Is cleanup triggered when budget exceeded?

### 3. Memory Configuration
*   **Target:** `src/memory_config.py`
*   **Cursor Action:**
    *   `read_file src/memory_config.py`
    *   *Audit Question:* Is PostgreSQL shared memory configured correctly? Are memory limits respected?

### 4. Query Timeout Management
*   **Target:** `src/query_timeout.py`
*   **Cursor Action:**
    *   `read_file src/query_timeout.py`
    *   *Audit Question:* Are query timeouts set correctly? Are long-running queries terminated? Is timeout configuration respected?

### 5. Maintenance Windows
*   **Target:** `src/maintenance_window.py`, `src/maintenance.py`
*   **Cursor Action:**
    *   `read_file src/maintenance_window.py`
    *   `read_file src/maintenance.py`
    *   *Audit Question:* Are maintenance windows respected? Is maintenance scheduling correct? Are all maintenance tasks executed?

## Phase 8: Workload Analysis & Optimization Audit

### 1. Workload Analysis
*   **Target:** `src/workload_analysis.py`
*   **Cursor Action:**
    *   `read_file src/workload_analysis.py`
    *   *Audit Question:* Is workload correctly analyzed? Are read/write patterns identified? Is workload analysis integrated into index decisions?

### 2. Pattern Detection
*   **Target:** `src/pattern_detection.py`
*   **Cursor Action:**
    *   `read_file src/pattern_detection.py`
    *   *Audit Question:* Are sustained patterns vs spikes correctly identified? Is pattern detection used to prevent over-indexing?

### 3. Write Performance Monitoring
*   **Target:** `src/write_performance.py`
*   **Cursor Action:**
    *   `read_file src/write_performance.py`
    *   *Audit Question:* Is write performance degradation detected? Are write-heavy workloads handled appropriately?

### 4. Statistics Refresh
*   **Target:** `src/statistics_refresh.py`
*   **Cursor Action:**
    *   `read_file src/statistics_refresh.py`
    *   *Audit Question:* Are stale statistics detected? Is ANALYZE executed correctly? Are statistics refresh limits respected?

## Phase 9: Schema Evolution & Change Management Audit

### 1. Schema Evolution
*   **Target:** `src/schema_evolution.py`, `src/schema/change_detection.py`
*   **Cursor Action:**
    *   `read_file src/schema_evolution.py`
    *   `read_file src/schema/change_detection.py`
    *   *Audit Question:* Are schema changes detected? Is impact analysis performed? Are schema mutations logged correctly?

### 2. Schema Validation
*   **Target:** `src/schema/validator.py`, `src/schema/loader.py`
*   **Cursor Action:**
    *   `read_file src/schema/validator.py`
    *   `read_file src/schema/loader.py`
    *   *Audit Question:* Is schema validation comprehensive? Are invalid schemas rejected? Is schema loading robust?

### 3. Schema Initialization
*   **Target:** `src/schema/initialization.py`
*   **Cursor Action:**
    *   `read_file src/schema/initialization.py`
    *   *Audit Question:* Is schema initialization idempotent? Are metadata tables created correctly?

## Phase 10: API Server & Integration Audit

### 1. API Server
*   **Target:** `src/api_server.py`
*   **Cursor Action:**
    *   `read_file src/api_server.py`
    *   *Audit Question:* Are API endpoints correctly implemented? Is CORS configured properly? Are error responses handled? Is authentication/authorization considered?

### 2. Query Interception
*   **Target:** `src/query_interceptor.py`, `src/ml_query_interception.py`
*   **Cursor Action:**
    *   `read_file src/query_interceptor.py`
    *   `read_file src/ml_query_interception.py`
    *   *Audit Question:* Is query interception working? Are queries logged correctly? Is ML-based interception functional?

### 3. Query Execution
*   **Target:** `src/query_executor.py`
*   **Cursor Action:**
    *   `read_file src/query_executor.py`
    *   *Audit Question:* Is query execution tracked? Are performance metrics collected? Are errors handled?

## Phase 11: Simulation & Backtesting Audit

1.  **Simulator Harness**
    *   **Target:** `src/simulation/simulator.py`
    *   **Cursor Action:** `read_file src/simulation/simulator.py`
    *   *Audit Question:* Does the simulator accurately generate load? Are the `baseline` vs `autoindex` comparisons fair (same seed/load)? Are all simulation modes (baseline, autoindex, scaled, comprehensive, real-data) functional?

2.  **Stock Market Simulator (Real Data)**
    *   **Target:** `src/simulation/stock_simulator.py`, `src/stock_data_loader.py`
    *   **Cursor Action:** `read_file src/simulation/stock_simulator.py`
    *   *Audit Question:* Is data loading correct? Are time-series constraints respected? Is backtesting logic sound?

3.  **Simulation Verification**
    *   **Target:** `src/simulation/simulation_verification.py`
    *   **Cursor Action:** `read_file src/simulation/simulation_verification.py`
    *   *Audit Question:* Are simulation results verified? Are features validated during simulation?

4.  **Run Verification (Actionable)**
    *   **Command:** `run.bat sim-baseline` (Run small baseline)
    *   **Command:** `run.bat sim-autoindex` (Run small autoindex)
    *   **Action:** Compare `docs/audit/toolreports/results_baseline.json` and `docs/audit/toolreports/results_with_auto_index.json`. Look for improvement in execution time.

## Phase 12: Reporting & Observability Audit

### 1. Performance Reporting
*   **Target:** `src/scaled_reporting.py`
*   **Cursor Action:**
    *   `read_file src/scaled_reporting.py`
    *   *Audit Question:* Are reports generated correctly? Is scaled reporting efficient for large datasets? Are metrics aggregated properly?

### 2. Structured Logging
*   **Target:** `src/structured_logging.py`
*   **Cursor Action:**
    *   `read_file src/structured_logging.py`
    *   *Audit Question:* Is structured logging configured? Are log formats consistent? Are sensitive data redacted?

### 3. Audit Trail
*   **Target:** `src/audit.py`
*   **Cursor Action:**
    *   `read_file src/audit.py`
    *   *Audit Question:* Are all actions logged? Is audit trail complete? Are mutations tracked?

### 4. Algorithm Tracking
*   **Target:** `src/algorithm_tracking.py`
*   **Cursor Action:**
    *   `read_file src/algorithm_tracking.py`
    *   *Audit Question:* Are algorithm invocations tracked? Is algorithm performance monitored?

## Phase 13: Advanced Features Audit

### 1. Approval Workflow
*   **Target:** `src/approval_workflow.py`
*   **Cursor Action:**
    *   `read_file src/approval_workflow.py`
    *   *Audit Question:* Is approval workflow functional? Are approvals tracked? Is workflow state managed correctly?

### 2. Per-Tenant Configuration
*   **Target:** `src/per_tenant_config.py`
*   **Cursor Action:**
    *   `read_file src/per_tenant_config.py`
    *   *Audit Question:* Are per-tenant configs isolated? Are tenant-specific settings applied correctly?

### 3. Production Cache
*   **Target:** `src/production_cache.py`
*   **Cursor Action:**
    *   `read_file src/production_cache.py`
    *   *Audit Question:* Is caching implemented correctly? Are cache invalidation strategies sound? Is cache thread-safe?

## Phase 14: Documentation & Reporting

1.  **Audit Reports**
    *   **Target:** `docs/audit/`
    *   **Action:** Ensure all findings are logged in a new report in `docs/audit/`.

2.  **Agent & Plan Alignment**
    *   **Target:** `agents.yaml`
    *   **Action:** Verify the codebase reflects the architecture described in `agents.yaml`.

3.  **Documentation Completeness**
    *   **Target:** `docs/`
    *   **Action:** Verify all features are documented. Check for missing documentation in `docs/features/`, `docs/tech/`, `docs/installation/`.

## Phase 15: Integration Testing & End-to-End Verification

### 1. End-to-End Flow Test
*   **Action:** Run a complete workflow:
    1. Initialize database (`make init-db`)
    2. Load schema (auto-discover or from config)
    3. Run queries (simulate workload)
    4. Verify auto-indexing triggers
    5. Verify indexes created
    6. Verify performance improvement
    7. Verify mutation log entries
    8. Verify cleanup of unused indexes

### 2. Multi-Tenant Isolation Test
*   **Action:** Verify:
    1. Tenant A queries don't affect Tenant B indexes
    2. Expression profiles are isolated
    3. Query stats are tenant-specific
    4. Index creation respects tenant boundaries

### 3. Failure Scenario Testing
*   **Action:** Test:
    1. Database connection failures
    2. Index creation failures
    3. Configuration errors
    4. Bypass activation
    5. Graceful shutdown during operations

### 4. Performance Benchmarking
*   **Action:** Run comprehensive simulation:
    1. Small scenario (baseline + autoindex)
    2. Medium scenario (baseline + autoindex)
    3. Compare results
    4. Verify improvements are consistent

---

**Audit Completion Checklist:**
- [ ] All algorithms verified for math/logic.
- [ ] Core auto-indexing logic reviewed.
- [ ] Database connection pooling verified.
- [ ] Configuration management validated.
- [ ] Index lifecycle management checked.
- [ ] Safety features (rollback, limits, locks) verified.
- [ ] Multi-tenant isolation confirmed.
- [ ] Schema auto-discovery validated.
- [ ] Advanced features (composite indexes, foreign keys, materialized views) verified.
- [ ] API server endpoints tested.
- [ ] Simulation run and improvement verified.
- [ ] Error handling and resilience tested.
- [ ] Security features (validation, SQL injection prevention) verified.
- [ ] Resource management (memory, storage, timeouts) checked.
- [ ] Workload analysis integration verified.
- [ ] Schema evolution tested.
- [ ] Reporting and observability validated.
- [ ] Linting and types passed.
- [ ] Test suite passes.
- [ ] Documentation complete.

---

**Additional Audit Considerations:**

1. **Performance Under Load**: Test with high query volumes, multiple tenants, concurrent index creation.

2. **Data Consistency**: Verify no data corruption, proper transaction handling, rollback correctness.

3. **Security Posture**: Review SQL injection prevention, credential handling, error message sanitization, RLS/RBAC compatibility.

4. **Scalability**: Test with large schemas (100+ tables), high tenant counts (1000+), large datasets.

5. **Operational Readiness**: Verify logging, monitoring, alerting, health checks, graceful degradation.

6. **Compatibility**: Test with different PostgreSQL versions, different connection modes (host adapter vs dedicated pool).

7. **Edge Cases**: Empty schemas, single-table databases, read-only databases, permission-restricted scenarios.

