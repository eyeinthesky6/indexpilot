# RLS and RBAC Analysis for IndexPilot

**Date**: 05-12-2025  
**Purpose**: Analyze Row Level Security (RLS) and Role-Based Access Control (RBAC) requirements and implications

---

## Executive Summary

**Short Answer**: IndexPilot does **NOT need its own RLS/RBAC implementation**. The system is a transparent layer that inherits security from the host database. However, proper configuration is required to ensure compatibility with host system RLS/RBAC policies.

**Key Findings**:
- ✅ **System inherits host RLS/RBAC automatically** when using host connection pool
- ⚠️ **Database user permissions** must be configured correctly for system operations
- ✅ **EXPLAIN queries respect RLS policies** (PostgreSQL behavior)
- ⚠️ **Index creation requires appropriate privileges** (CREATE INDEX permission)
- ✅ **No security bypass** - all queries go through database security layer

---

## System Architecture Context

IndexPilot operates as a **transparent optimization layer** on top of PostgreSQL:

```
Host Application
    ↓ (queries)
IndexPilot Layer (query interception, analysis, optimization)
    ↓ (SQL queries)
PostgreSQL Database (with RLS/RBAC policies)
```

### Connection Modes

The system supports two connection modes:

1. **Host Connection Pool** (via `HostDatabaseAdapter`)
   - Reuses host application's database connections
   - **Inherits all RLS/RBAC policies automatically**
   - Uses the same database user as host application
   - **Note**: `DatabaseAdapter` has been renamed to `HostDatabaseAdapter` for clarity. A backward compatibility alias exists.

2. **Dedicated Connection Pool** (via `src/db.py`)
   - Uses dedicated database user (`DB_USER` environment variable)
   - **Requires explicit permissions configuration**
   - Must respect host RLS policies if accessing same tables

---

## RLS (Row Level Security) Impact

### How RLS Works with IndexPilot

**PostgreSQL RLS** is enforced at the database level, which means:

1. **All queries through IndexPilot are subject to RLS policies**
   - When IndexPilot executes `SELECT * FROM contacts WHERE tenant_id = 123`
   - PostgreSQL applies RLS policies **before** returning results
   - IndexPilot only sees rows the database user has permission to see

2. **EXPLAIN queries respect RLS**
   - When IndexPilot runs `EXPLAIN (FORMAT JSON) SELECT * FROM contacts WHERE tenant_id = 123`
   - PostgreSQL applies RLS policies during plan generation
   - Plan costs reflect filtered row counts (post-RLS)
   - **This is correct behavior** - plan analysis matches actual query execution

3. **Query interception works correctly**
   - Query cost analysis reflects RLS-filtered data
   - Blocking decisions are based on actual accessible data
   - No security bypass occurs

### Potential Issues and Solutions

#### Issue 1: EXPLAIN on RLS-protected tables

**Scenario**: Host system has RLS policies that filter by `tenant_id`. IndexPilot runs EXPLAIN queries.

**Impact**: ✅ **No issue** - EXPLAIN respects RLS policies automatically.

**Example**:
```sql
-- Host RLS policy
CREATE POLICY tenant_isolation ON contacts
    FOR ALL USING (tenant_id = current_setting('app.tenant_id')::int);

-- IndexPilot EXPLAIN query
EXPLAIN (FORMAT JSON) SELECT * FROM contacts WHERE email = 'test@example.com';
-- ✅ PostgreSQL applies RLS policy automatically
-- ✅ Plan reflects filtered row count
```

#### Issue 2: Cross-tenant data leakage

**Scenario**: IndexPilot uses dedicated connection pool with superuser privileges.

**Risk**: ⚠️ **High** - If IndexPilot user has bypass privileges, it could see all tenant data.

**Solution**: ✅ **Use host connection pool** OR configure IndexPilot user with same RLS context:
```sql
-- Option 1: Use host connection pool (recommended)
-- IndexPilot inherits tenant context automatically

-- Option 2: Set tenant context for IndexPilot user
SET app.tenant_id = '123';
-- Then run queries (RLS will apply)
```

#### Issue 3: Index creation on RLS-protected tables

**Scenario**: IndexPilot creates indexes on tables with RLS policies.

**Impact**: ✅ **No issue** - Index creation doesn't bypass RLS for data access.

**Note**: Index creation requires `CREATE INDEX` privilege, but indexes themselves don't contain data - they're metadata structures. RLS policies still apply to queries using the index.

---

## RBAC (Role-Based Access Control) Impact

### Database User Permissions Required

IndexPilot requires specific database permissions for its operations:

#### Minimum Required Permissions

```sql
-- For query interception and analysis
GRANT CONNECT ON DATABASE your_database TO indexpilot_user;
GRANT USAGE ON SCHEMA public TO indexpilot_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO indexpilot_user;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO indexpilot_user;

-- For index creation (auto-indexer)
GRANT CREATE ON SCHEMA public TO indexpilot_user;
-- OR grant on specific tables:
GRANT CREATE INDEX ON TABLE contacts TO indexpilot_user;
GRANT CREATE INDEX ON TABLE organizations TO indexpilot_user;

-- For metadata tables (IndexPilot's own tables)
GRANT ALL ON TABLE genome_catalog TO indexpilot_user;
GRANT ALL ON TABLE expression_profile TO indexpilot_user;
GRANT ALL ON TABLE mutation_log TO indexpilot_user;
GRANT ALL ON TABLE query_stats TO indexpilot_user;
```

#### Recommended: Use Host Connection Pool

**Best Practice**: Use host application's connection pool instead of dedicated user:

```python
# In your host application
from src.adapters import configure_adapters, get_host_database_adapter

# Configure IndexPilot to use host connection pool
configure_adapters(
    database=your_connection_pool,  # Your existing pool
    validate=True                    # Validate interface (recommended)
)

# Verify it's working
adapter = get_host_database_adapter()
if adapter.is_healthy():
    print("✅ Database adapter configured and inheriting RLS/RBAC")
```

**Benefits**:
- ✅ Inherits all RBAC permissions automatically
- ✅ No additional user configuration needed
- ✅ Same security context as host application
- ✅ No permission conflicts

### Permission Conflicts

#### Conflict 1: Index creation on read-only user

**Scenario**: Host application uses read-only database user for queries.

**Problem**: IndexPilot cannot create indexes with read-only user.

**Solutions**:
1. **Use separate user for index creation** (recommended):
   ```python
   # Use host pool for queries (read-only user)
   # Use dedicated pool for index creation (write user)
   ```
2. **Disable auto-indexing** if permissions insufficient:
   ```yaml
   bypass:
     features:
       auto_indexing:
         enabled: false
   ```

#### Conflict 2: Schema modification permissions

**Scenario**: IndexPilot tries to `ALTER TABLE` but user lacks permissions.

**Impact**: ⚠️ **Operations fail gracefully** - system logs error and continues.

**Solution**: Grant appropriate permissions or disable schema evolution features.

---

## Security Model: Transparent Layer

### Why IndexPilot Doesn't Need Its Own RLS/RBAC

IndexPilot is designed as a **transparent optimization layer**:

1. **No Security Bypass**
   - All queries go through PostgreSQL's security layer
   - No direct data access outside database
   - EXPLAIN queries respect RLS policies

2. **Query Pass-Through**
   - IndexPilot intercepts queries **before** execution
   - Analyzes query plans (which respect RLS)
   - Blocks harmful queries (cost-based, not security-based)
   - Actual execution uses host application's security context

3. **Metadata Operations**
   - IndexPilot's metadata tables (`genome_catalog`, `query_stats`, etc.) are separate
   - These don't contain business data
   - Access controlled by database user permissions

### Security Responsibilities

| Layer | Responsibility |
|-------|---------------|
| **Host Application** | Authentication, authorization, business logic security |
| **PostgreSQL Database** | RLS policies, RBAC roles, data access control |
| **IndexPilot** | Query optimization, performance monitoring, index management |

**IndexPilot does NOT**:
- ❌ Authenticate users
- ❌ Authorize data access
- ❌ Bypass RLS policies
- ❌ Implement its own security model

**IndexPilot DOES**:
- ✅ Optimize query performance
- ✅ Create indexes automatically
- ✅ Monitor query patterns
- ✅ Block expensive queries (cost-based, not security-based)

---

## Configuration Recommendations

### Recommended Setup: Host Connection Pool

```python
# In your host application initialization
from src.adapters import get_host_database_adapter

# Configure IndexPilot to use your connection pool
adapter = get_host_database_adapter()
adapter.use_host = True
adapter.host_impl = your_existing_connection_pool
```

**Benefits**:
- ✅ Automatic RLS/RBAC inheritance
- ✅ No additional user configuration
- ✅ Same security context as host application
- ✅ No permission conflicts

### Alternative: Dedicated User with Proper Permissions

If you must use a dedicated user:

```sql
-- Create IndexPilot user
CREATE USER indexpilot_user WITH PASSWORD 'secure_password';

-- Grant minimum required permissions
GRANT CONNECT ON DATABASE your_database TO indexpilot_user;
GRANT USAGE ON SCHEMA public TO indexpilot_user;

-- Grant SELECT on business tables (for query analysis)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO indexpilot_user;

-- Grant CREATE INDEX (for auto-indexing)
-- Option 1: Grant on schema (if you trust IndexPilot)
GRANT CREATE ON SCHEMA public TO indexpilot_user;

-- Option 2: Grant on specific tables (more secure)
GRANT CREATE INDEX ON TABLE contacts TO indexpilot_user;
GRANT CREATE INDEX ON TABLE organizations TO indexpilot_user;

-- Grant full access to IndexPilot metadata tables
GRANT ALL ON TABLE genome_catalog TO indexpilot_user;
GRANT ALL ON TABLE expression_profile TO indexpilot_user;
GRANT ALL ON TABLE mutation_log TO indexpilot_user;
GRANT ALL ON TABLE query_stats TO indexpilot_user;
```

**Important**: If using dedicated user with RLS-protected tables, ensure tenant context is set:
```python
# Before running queries, set tenant context
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SET app.tenant_id = %s", (tenant_id,))
    # Now run queries - RLS will apply
```

---

## Testing RLS/RBAC Compatibility

### Test Checklist

1. **RLS Policy Compatibility**
   ```sql
   -- Test: Can IndexPilot analyze queries on RLS-protected tables?
   EXPLAIN (FORMAT JSON) SELECT * FROM contacts WHERE tenant_id = 123;
   -- ✅ Should return plan (RLS applied automatically)
   ```

2. **Index Creation Permissions**
   ```sql
   -- Test: Can IndexPilot create indexes?
   CREATE INDEX test_idx ON contacts(email);
   -- ✅ Should succeed if permissions granted
   ```

3. **Cross-Tenant Isolation**
   ```python
   # Test: Does IndexPilot respect tenant boundaries?
   # Set tenant context
   set_tenant_context(123)
   # Run query - should only see tenant 123 data
   results = execute_query("SELECT * FROM contacts")
   # ✅ Should only return tenant 123 rows
   ```

4. **Query Interception with RLS**
   ```python
   # Test: Does query interception work with RLS?
   # RLS-filtered queries should have lower costs
   plan = analyze_query_plan("SELECT * FROM contacts WHERE tenant_id = 123")
   # ✅ Plan should reflect RLS-filtered row count
   ```

---

## Potential Issues and Solutions

### Issue 1: EXPLAIN Fails on RLS-Protected Tables

**Symptom**: `EXPLAIN` queries fail with permission errors.

**Cause**: Database user lacks `SELECT` permission or RLS policy blocks access.

**Solution**:
```sql
-- Grant SELECT permission
GRANT SELECT ON TABLE contacts TO indexpilot_user;

-- OR ensure RLS policy allows access
CREATE POLICY allow_indexpilot ON contacts
    FOR SELECT USING (true);  -- Adjust based on your security model
```

### Issue 2: Index Creation Fails

**Symptom**: Auto-indexer fails with "permission denied" errors.

**Cause**: Database user lacks `CREATE INDEX` permission.

**Solution**:
```sql
-- Grant CREATE INDEX permission
GRANT CREATE INDEX ON TABLE contacts TO indexpilot_user;

-- OR disable auto-indexing if permissions insufficient
```

### Issue 3: Cross-Tenant Data Leakage

**Symptom**: IndexPilot sees data from all tenants.

**Cause**: Using dedicated user with superuser privileges or RLS bypass.

**Solution**:
- ✅ **Use host connection pool** (recommended)
- OR set tenant context before queries
- OR configure RLS policies for IndexPilot user

### Issue 4: Query Interception Blocks Valid Queries

**Symptom**: Valid queries are blocked due to high cost estimates.

**Cause**: EXPLAIN plan shows high cost because RLS filters are applied (reducing selectivity).

**Solution**: This is **correct behavior** - if RLS filters reduce data significantly, query costs should reflect that. Adjust cost thresholds if needed:
```yaml
features:
  query_interceptor:
    max_query_cost: 5000.0  # Lower threshold for RLS-filtered queries
```

---

## Summary

### Does IndexPilot Need RLS/RBAC?

**Answer**: **NO** - IndexPilot does not need its own RLS/RBAC implementation because:

1. ✅ It's a transparent layer that inherits database security
2. ✅ All queries go through PostgreSQL's security layer
3. ✅ EXPLAIN queries respect RLS policies automatically
4. ✅ No security bypass occurs

### Will Host System RLS/RBAC Break IndexPilot?

**Answer**: **NO** - Host system RLS/RBAC will **NOT break** IndexPilot, but:

1. ⚠️ **Proper configuration required** - Database user needs appropriate permissions
2. ⚠️ **Recommended**: Use host connection pool to inherit security automatically
3. ✅ **EXPLAIN queries work correctly** - They respect RLS policies
4. ✅ **Index creation works** - Requires CREATE INDEX permission

### Best Practices

1. **Use Host Connection Pool** (recommended)
   - Automatic RLS/RBAC inheritance
   - No additional configuration
   - Same security context

2. **If Using Dedicated User**
   - Grant minimum required permissions
   - Set tenant context for RLS-protected tables
   - Test thoroughly with your RLS policies

3. **Monitor and Test**
   - Verify EXPLAIN queries work with RLS
   - Test index creation permissions
   - Validate cross-tenant isolation

---

## Conclusion

IndexPilot is designed to work seamlessly with existing RLS/RBAC policies. The system does not implement its own security model - it relies on PostgreSQL's built-in security features. As long as the database user has appropriate permissions for IndexPilot's operations (query analysis, index creation), the system will work correctly with host RLS/RBAC policies.

**No breaking changes** - IndexPilot respects and works with your existing security model.

