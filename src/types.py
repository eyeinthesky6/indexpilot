"""Type definitions and aliases for IndexPilot

This module provides type aliases and TypedDict definitions to replace
Any usage and improve type safety across the codebase.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

# ============================================================================
# Verification Result Types
# ============================================================================

class VerificationDetails(TypedDict, total=False):
    """Details dictionary for verification results"""
    total_index_mutations: int
    sample_mutations_checked: int
    mutations_with_details: int
    mutations_with_tenant: int
    tenants_checked: int
    tenants_with_profiles: int
    total_fields_enabled: int
    avg_fields_per_tenant: float
    maintenance_window: dict[str, bool | list[int]]
    rate_limiter: dict[str, bool | float]
    cpu_throttle: dict[str, bool | str]
    write_performance: dict[str, bool | str | None]
    system_enabled: bool
    any_bypass_active: bool
    features: dict[str, dict[str, bool]]
    database_health: dict[str, str | float | None]
    system_health: dict[str, str | dict[str, JSONValue] | list[JSONValue]]


class VerificationResult(TypedDict):
    """Result structure for verification functions"""
    passed: bool
    errors: list[str]
    warnings: list[str]
    details: VerificationDetails


class VerificationSummary(TypedDict):
    """Summary of all verification results"""
    all_passed: bool
    total_errors: int
    total_warnings: int


class ComprehensiveVerificationResults(TypedDict):
    """Complete verification results from all checks"""
    mutation_log: VerificationResult
    expression_profiles: VerificationResult
    production_safeguards: VerificationResult
    bypass_system: VerificationResult
    health_checks: VerificationResult
    summary: VerificationSummary


# ============================================================================
# Audit Trail Types
# ============================================================================

class AuditDetails(TypedDict, total=False):
    """Details dictionary for audit trail entries"""
    index_name: str
    size_mb: float
    queries: int
    build_cost: float
    query_cost: float
    reason: str
    fields_initialized: int
    action: str
    ip_address: str
    user_id: str


# ============================================================================
# Health Check Types
# ============================================================================

class DatabaseHealthStatus(TypedDict):
    """Database health check result"""
    status: str  # 'healthy' | 'unhealthy' | 'unknown'
    latency_ms: float | None
    error: str | None


class SystemHealthStatus(TypedDict, total=False):
    """System health check result"""
    timestamp: float
    overall_status: str  # 'healthy' | 'degraded' | 'unhealthy' | 'disabled'
    message: str
    components: dict[str, DatabaseHealthStatus | ConnectionPoolHealth | dict[str, JSONValue]]
    warnings: list[str]
    errors: list[str]


class SystemStatus(TypedDict):
    """System status check result"""
    enabled: bool
    shutting_down: bool
    status: str  # 'operational' | 'shutting_down' | 'disabled'


class HealthSummary(TypedDict):
    """Quick health summary for monitoring/alerting"""
    status: str
    database: str
    pool: str
    system: str
    has_errors: bool
    has_warnings: bool


# ============================================================================
# Configuration Types
# ============================================================================

class ConfigValue(TypedDict, total=False):
    """Configuration value - can be various types"""
    pass  # Used for type checking only


# ============================================================================
# Type Aliases for Common Patterns (defined early for forward references)
# ============================================================================

# JSON-serializable types - using TypeAlias for strict Any checking
type JSONValue = str | int | float | bool | None | list['JSONValue'] | dict[str, 'JSONValue']
type JSONDict = dict[str, 'JSONValue']

# Database row (from RealDictCursor)
type DatabaseRow = dict[str, str | int | float | bool | None]

# Tenant ID (always int in our system)
type TenantID = int

# Table and field names
type TableName = str
type FieldName = str

# Common list types
type StringList = list[str]
type IntList = list[int]
type TenantIDList = list[TenantID]

# Common dictionary types
type StringDict = dict[str, str]
type BoolDict = dict[str, bool]
type StringBoolDict = dict[str, dict[str, bool]]  # Nested: dict[str, dict[str, bool]]
type HealthDict = dict[str, str | float | None]  # For health status dictionaries

# Common tuple types for results
type BoolStrTuple = tuple[bool, str | None]  # (success, message)
type BoolFloatTuple = tuple[bool, float]  # (allowed, retry_after)

# ============================================================================
# Query Result Types
# ============================================================================

# Query results are dictionaries with string keys and various value types
type QueryResult = dict[str, JSONValue]
type QueryResults = list[QueryResult]


# ============================================================================
# Index Creation Types
# ============================================================================

class IndexCreationResult(TypedDict, total=False):
    """Result from index creation operation"""
    table: str
    field: str
    index_name: str
    queries: int
    build_cost: float
    query_cost: float
    success: bool
    error: str


# ============================================================================
# Expression Profile Types
# ============================================================================

class ExpressionProfile(TypedDict):
    """Expression profile entry"""
    tenant_id: int
    table_name: str
    field_name: str
    is_enabled: bool


# ============================================================================
# Mutation Log Types
# ============================================================================

class MutationLogEntry(TypedDict, total=False):
    """Mutation log entry structure"""
    id: int
    tenant_id: int | None
    mutation_type: str
    table_name: str | None
    field_name: str | None
    details_json: str | JSONDict
    created_at: str


class AuditSummaryByType(TypedDict, total=False):
    """Audit summary grouped by mutation type"""
    mutation_type: str
    count: int
    first_occurrence: str | datetime
    last_occurrence: str | datetime


class AuditSummaryStats(TypedDict, total=False):
    """Audit summary statistics"""
    total_events: int
    unique_tenants: int
    unique_tables: int


class AuditSummary(TypedDict):
    """Complete audit summary"""
    summary: AuditSummaryStats
    by_type: list[AuditSummaryByType]  # Keep as-is since it's a specific TypedDict list
    period_days: int



# ============================================================================
# Query Parameter Types
# ============================================================================

# Query parameters can be various types
type QueryParam = str | int | float | bool | None | list[str | int | float]
type QueryParams = tuple[QueryParam, ...]

# ============================================================================
# Configuration Types (Expanded)
# ============================================================================

# Configuration dictionary structure
type ConfigDict = dict[str, JSONValue]

# ============================================================================
# Connection Pool Types
# ============================================================================

class PoolStats(TypedDict, total=False):
    """Connection pool statistics"""
    min_connections: int
    max_connections: int
    current_connections: int
    available_connections: int
    waiting_requests: int


class ConnectionPoolHealth(TypedDict, total=False):
    """Connection pool health status"""
    status: str  # 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
    pool_stats: PoolStats | None
    error: str | None

# ============================================================================
# Schema Types
# ============================================================================

class SchemaDefinition(TypedDict, total=False):
    """Schema definition structure"""
    tables: list[JSONDict]
    version: str
    metadata: JSONDict | None

# ============================================================================
# Rate Limiter Types
# ============================================================================

class RateLimitResult(TypedDict):
    """Rate limit check result"""
    allowed: bool
    retry_after: float

# ============================================================================
# CPU Throttle Types
# ============================================================================

class CPUThrottleResult(TypedDict):
    """CPU throttle check result"""
    should_throttle: bool
    reason: str | None

# ============================================================================
# Write Performance Types
# ============================================================================

class WritePerformanceResult(TypedDict):
    """Write performance check result"""
    can_create: bool
    reason: str | None

