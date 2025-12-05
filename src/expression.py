"""Expression profile operations - per-tenant field activation"""


from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.resilience import safe_database_operation


def initialize_tenant_expression(tenant_id):
    """Initialize expression profile for a tenant based on genome default_expression"""
    from src.audit import log_audit_event

    with safe_database_operation('initialize_tenant_expression', f'tenant_{tenant_id}', rollback_on_failure=True) as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Get all fields with default_expression = True
            cursor.execute("""
                SELECT table_name, field_name, default_expression
                FROM genome_catalog
                WHERE default_expression = TRUE
            """)
            fields = cursor.fetchall()

            # Create expression profile entries
            for field in fields:
                cursor.execute("""
                    INSERT INTO expression_profile
                    (tenant_id, table_name, field_name, is_enabled)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id, table_name, field_name)
                    DO NOTHING
                """, (tenant_id, field['table_name'], field['field_name'], True))

            # Commit is handled by safe_database_operation

            # Log to audit trail
            log_audit_event(
                'INITIALIZE_TENANT',
                tenant_id=tenant_id,
                details={'fields_initialized': len(fields), 'action': 'expression_profile_initialized'},
                severity='info'
            )

            print(f"Initialized expression profile for tenant {tenant_id} with {len(fields)} fields")
        finally:
            cursor.close()


def enable_field(tenant_id, table_name, field_name):
    """Enable a field for a specific tenant"""
    with safe_database_operation('enable_field', table_name, rollback_on_failure=True) as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO expression_profile
                (tenant_id, table_name, field_name, is_enabled)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, table_name, field_name)
                DO UPDATE SET is_enabled = TRUE
            """, (tenant_id, table_name, field_name, True))

            # Log mutation to audit trail
            from src.audit import log_audit_event
            log_audit_event(
                'ENABLE_FIELD',
                tenant_id=tenant_id,
                table_name=table_name,
                field_name=field_name,
                details={'action': 'field_enabled'},
                severity='info'
            )

            # Commit is handled by safe_database_operation
        finally:
            cursor.close()


def disable_field(tenant_id, table_name, field_name):
    """Disable a field for a specific tenant"""
    with safe_database_operation('disable_field', table_name, rollback_on_failure=True) as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                INSERT INTO expression_profile
                (tenant_id, table_name, field_name, is_enabled)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, table_name, field_name)
                DO UPDATE SET is_enabled = FALSE
            """, (tenant_id, table_name, field_name, False))

            # Log mutation to audit trail
            from src.audit import log_audit_event
            log_audit_event(
                'DISABLE_FIELD',
                tenant_id=tenant_id,
                table_name=table_name,
                field_name=field_name,
                details={'action': 'field_disabled'},
                severity='info'
            )

            # Commit is handled by safe_database_operation
        finally:
            cursor.close()


def get_enabled_fields(tenant_id, table_name=None):
    """Get all enabled fields for a tenant, optionally filtered by table"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if table_name:
                cursor.execute("""
                    SELECT table_name, field_name
                    FROM expression_profile
                    WHERE tenant_id = %s AND table_name = %s AND is_enabled = TRUE
                    ORDER BY table_name, field_name
                """, (tenant_id, table_name))
            else:
                cursor.execute("""
                    SELECT table_name, field_name
                    FROM expression_profile
                    WHERE tenant_id = %s AND is_enabled = TRUE
                    ORDER BY table_name, field_name
                """, (tenant_id,))
            return cursor.fetchall()
        finally:
            cursor.close()


def is_field_enabled(tenant_id, table_name, field_name):
    """Check if a specific field is enabled for a tenant"""
    # Check if expression checks are enabled (bypass check)
    try:
        from src.rollback import is_expression_checks_enabled
        if not is_expression_checks_enabled():
            # Bypass mode: return True (all fields enabled when bypassed)
            return True
    except ImportError:
        # Rollback module not available, continue normally
        pass

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT is_enabled
                FROM expression_profile
                WHERE tenant_id = %s AND table_name = %s AND field_name = %s
            """, (tenant_id, table_name, field_name))
            result = cursor.fetchone()
            if result:
                return result['is_enabled']
            # If no expression profile exists, check default_expression from genome
            cursor.execute("""
                SELECT default_expression
                FROM genome_catalog
                WHERE table_name = %s AND field_name = %s
            """, (table_name, field_name))
            genome_result = cursor.fetchone()
            return genome_result['default_expression'] if genome_result else False
        finally:
            cursor.close()

