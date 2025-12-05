"""Comprehensive audit trail logging for all critical system actions"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.validation import validate_field_name, validate_table_name, validate_tenant_id

logger = logging.getLogger(__name__)

# Mutation types for audit trail
MUTATION_TYPES = {
    # Schema operations
    'CREATE_TABLE': 'Schema change - table created',
    'DROP_TABLE': 'Schema change - table dropped',
    'ALTER_TABLE': 'Schema change - table altered',
    'ADD_COLUMN': 'Schema change - column added',
    'DROP_COLUMN': 'Schema change - column dropped',
    'ALTER_COLUMN': 'Schema change - column type altered',
    'RENAME_COLUMN': 'Schema change - column renamed',

    # Index operations
    'CREATE_INDEX': 'Index created',
    'DROP_INDEX': 'Index dropped',
    'REINDEX': 'Index rebuilt',

    # Expression operations
    'ENABLE_FIELD': 'Field enabled for tenant',
    'DISABLE_FIELD': 'Field disabled for tenant',
    'INITIALIZE_TENANT': 'Tenant expression profile initialized',

    # System operations
    'SYSTEM_ENABLE': 'System enabled',
    'SYSTEM_DISABLE': 'System disabled',
    'SYSTEM_CONFIG_CHANGE': 'System configuration changed',

    # Security operations
    'RATE_LIMIT_EXCEEDED': 'Rate limit exceeded',
    'QUERY_BLOCKED': 'Query blocked by interceptor',
    'SECURITY_VIOLATION': 'Security violation detected',
    'AUTHENTICATION_FAILURE': 'Authentication failed',
    'AUTHORIZATION_DENIED': 'Authorization denied',

    # Error operations
    'CRITICAL_ERROR': 'Critical error occurred',
    'INDEX_CREATION_FAILED': 'Index creation failed',
    'CONNECTION_ERROR': 'Database connection error',

    # Data operations (if needed)
    'BULK_UPDATE': 'Bulk data update',
    'DATA_MIGRATION': 'Data migration performed',
}


def log_audit_event(
    mutation_type: str,
    tenant_id: int | None = None,
    table_name: str | None = None,
    field_name: str | None = None,
    details: dict[str, Any] | None = None,
    severity: str = 'info',
    user_id: str | None = None,
    ip_address: str | None = None
) -> bool:
    """
    Log a critical system action to the audit trail.

    This function provides comprehensive audit logging for all operations that
    cause changes to the database or system state. All critical operations
    should use this function to maintain a complete audit trail.

    Args:
        mutation_type: Type of mutation (from MUTATION_TYPES)
        tenant_id: Tenant ID (if applicable)
        table_name: Table name (if applicable)
        field_name: Field name (if applicable)
        details: Additional details as dict (will be JSON-encoded)
        severity: Severity level ('info', 'warning', 'error', 'critical')
        user_id: User ID who performed the action (if applicable)
        ip_address: IP address of the request (if applicable)

    Returns:
        True if logged successfully, False otherwise

    Example:
        log_audit_event(
            'CREATE_INDEX',
            table_name='contacts',
            field_name='email',
            details={'index_name': 'idx_contacts_email', 'size_mb': 18.5},
            severity='info'
        )
    """
    # Check if mutation logging is enabled (bypass check)
    try:
        from src.rollback import is_mutation_logging_enabled
        if not is_mutation_logging_enabled():
            # Bypass mode: skip mutation logging but still log to application logger
            logger.debug(f"Mutation logging bypassed for: {mutation_type}")
            # Still log to application logger for visibility
            log_message = (
                f"Audit (bypassed): {mutation_type} | "
                f"tenant={tenant_id} | "
                f"table={table_name} | "
                f"field={field_name}"
            )
            if severity == 'critical':
                logger.critical(log_message)
            elif severity == 'error':
                logger.error(log_message)
            elif severity == 'warning':
                logger.warning(log_message)
            else:
                logger.info(log_message)
            return False  # Indicate logging was bypassed
    except ImportError:
        # Rollback module not available, continue normally
        pass

    try:
        # Validate inputs
        if mutation_type not in MUTATION_TYPES:
            logger.warning(f"Unknown mutation type: {mutation_type}")

        validated_tenant_id = None
        if tenant_id is not None:
            try:
                validated_tenant_id = validate_tenant_id(tenant_id)
            except ValueError:
                logger.warning(f"Invalid tenant_id in audit log: {tenant_id}")

        validated_table_name = None
        if table_name:
            try:
                validated_table_name = validate_table_name(table_name)
            except ValueError:
                logger.warning(f"Invalid table_name in audit log: {table_name}")

        validated_field_name = None
        if field_name and validated_table_name:
            try:
                validated_field_name = validate_field_name(field_name, validated_table_name)
            except ValueError:
                logger.warning(f"Invalid field_name in audit log: {field_name}")

        # Prepare details JSON
        details_json = {}
        if details:
            details_json.update(details)

        # Add metadata
        details_json.update({
            'severity': severity,
            'logged_at': datetime.now(UTC).isoformat(),
        })

        if user_id:
            details_json['user_id'] = user_id
        if ip_address:
            details_json['ip_address'] = ip_address

        # Log to database
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute("""
                    INSERT INTO mutation_log
                    (tenant_id, mutation_type, table_name, field_name, details_json)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    validated_tenant_id,
                    mutation_type,
                    validated_table_name,
                    validated_field_name,
                    json.dumps(details_json)
                ))
                conn.commit()

                # Also log to application logger with appropriate level
                log_message = (
                    f"Audit: {mutation_type} | "
                    f"tenant={validated_tenant_id} | "
                    f"table={validated_table_name} | "
                    f"field={validated_field_name}"
                )

                if severity == 'critical':
                    logger.critical(log_message)
                elif severity == 'error':
                    logger.error(log_message)
                elif severity == 'warning':
                    logger.warning(log_message)
                else:
                    logger.info(log_message)

                # Also log to host audit system via adapter (if configured)
                try:
                    from src.adapters import get_audit_adapter
                    adapter = get_audit_adapter()
                    adapter.log_event(
                        mutation_type,
                        tenant_id=validated_tenant_id,
                        table_name=validated_table_name,
                        field_name=validated_field_name,
                        details=details_json,
                        severity=severity,
                        user_id=user_id,
                        ip_address=ip_address
                    )
                except Exception as e:
                    # Don't fail if adapter not available or fails
                    logger.debug(f"Could not log to host audit system via adapter: {e}")

                return True
            except Exception as e:
                conn.rollback()
                # Don't fail the operation if audit logging fails, but log the error
                logger.error(f"Failed to log audit event {mutation_type}: {e}")
                return False
            finally:
                cursor.close()

    except Exception as e:
        # Don't fail the operation if audit logging fails
        logger.error(f"Error in audit logging: {e}")
        return False


def get_audit_trail(
    tenant_id: int | None = None,
    mutation_type: str | None = None,
    table_name: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 100
) -> list:
    """
    Query the audit trail.

    Args:
        tenant_id: Filter by tenant ID
        mutation_type: Filter by mutation type
        table_name: Filter by table name
        start_date: Start date for filtering
        end_date: End date for filtering
        limit: Maximum number of records to return

    Returns:
        List of audit trail records
    """
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            query = """
                SELECT
                    id,
                    tenant_id,
                    mutation_type,
                    table_name,
                    field_name,
                    details_json,
                    created_at
                FROM mutation_log
                WHERE 1=1
            """
            params: list[Any] = []

            if tenant_id:
                query += " AND tenant_id = %s"
                params.append(tenant_id)

            if mutation_type:
                query += " AND mutation_type = %s"
                params.append(mutation_type)

            if table_name:
                query += " AND table_name = %s"
                params.append(table_name)

            if start_date:
                query += " AND created_at >= %s"
                params.append(start_date)

            if end_date:
                query += " AND created_at <= %s"
                params.append(end_date)

            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            result = cursor.fetchall()
            return list(result) if result else []
        finally:
            cursor.close()


def get_audit_summary(days: int = 30) -> dict[str, Any]:
    """
    Get summary statistics of audit trail.

    Args:
        days: Number of days to analyze

    Returns:
        Dictionary with summary statistics
    """
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT
                    mutation_type,
                    COUNT(*) as count,
                    MIN(created_at) as first_occurrence,
                    MAX(created_at) as last_occurrence
                FROM mutation_log
                WHERE created_at >= NOW() - INTERVAL '1 day' * %s
                GROUP BY mutation_type
                ORDER BY count DESC
            """, (days,))

            by_type = cursor.fetchall()

            cursor.execute("""
                SELECT
                    COUNT(*) as total_events,
                    COUNT(DISTINCT tenant_id) as unique_tenants,
                    COUNT(DISTINCT table_name) as unique_tables
                FROM mutation_log
                WHERE created_at >= NOW() - INTERVAL '1 day' * %s
            """, (days,))

            summary = cursor.fetchone()

            return {
                'summary': summary,
                'by_type': by_type,
                'period_days': days
            }
        finally:
            cursor.close()

