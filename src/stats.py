"""Query stats collection and analysis"""

import logging
import threading
import time

from psycopg2.extras import RealDictCursor

from src.db import get_connection

logger = logging.getLogger(__name__)

# Thread-safe batch stats for performance

_stats_buffer: list[tuple[str, str, str | None, str, float]] = []
_stats_lock = threading.Lock()
_last_flush_time = time.time()
_flush_interval = 5.0  # Flush every 5 seconds even if buffer not full
_max_buffer_size = 10000  # Maximum buffer size to prevent memory issues

def log_query_stat(tenant_id, table_name, field_name, query_type, duration_ms, batch_size=100, skip_validation=False):
    """Log a query statistic (batched for performance, thread-safe)"""
    # Check if stats collection is enabled (bypass check)
    try:
        from src.rollback import is_stats_collection_enabled
        if not is_stats_collection_enabled():
            return  # Silent bypass - stats collection disabled
    except ImportError:
        # Rollback module not available, continue normally
        pass

    global _stats_buffer, _last_flush_time

    # Validate inputs (best-effort, don't crash on invalid data)
    # Skip validation for simulator/internal use (performance optimization)
    if not skip_validation:
        try:
            from src.validation import validate_field_name, validate_table_name, validate_tenant_id
            validated_tenant_id = validate_tenant_id(tenant_id)
            # Convert to string for buffer storage
            tenant_id = str(validated_tenant_id) if validated_tenant_id is not None else ""
            table_name = validate_table_name(table_name)
            if field_name:
                field_name = validate_field_name(field_name, table_name)
        except (ValueError, ImportError) as e:
            logger.warning(f"Invalid stat data, skipping: {e}")
            return
    else:
        # Convert tenant_id to string even when skipping validation
        tenant_id = str(tenant_id) if tenant_id is not None else ""

    buffer_copy = None
    with _stats_lock:
        # Prevent buffer overflow (memory protection)
        if len(_stats_buffer) >= _max_buffer_size:
            logger.warning(f"Stats buffer at maximum size ({_max_buffer_size}), forcing flush")
            current_time = time.time()
            _last_flush_time = current_time
            buffer_copy = _stats_buffer[:]
            _stats_buffer = []
        else:
            _stats_buffer.append((tenant_id, table_name, field_name, query_type, duration_ms))

            # Flush when buffer is full or time interval passed
            current_time = time.time()
            should_flush = (
                len(_stats_buffer) >= batch_size or
                (current_time - _last_flush_time) >= _flush_interval
            )

            if should_flush:
                _last_flush_time = current_time
                # Make a copy to flush outside lock
                buffer_copy = _stats_buffer[:]
                _stats_buffer = []

    if buffer_copy:
        flush_query_stats_buffer(buffer_copy)

def flush_query_stats():
    """Flush buffered query stats to database (thread-safe)"""
    global _stats_buffer

    with _stats_lock:
        if not _stats_buffer:
            return
        # Make a copy to flush outside lock
        buffer_copy = _stats_buffer[:]
        _stats_buffer = []

    flush_query_stats_buffer(buffer_copy)


def flush_query_stats_buffer(buffer):
    """Flush a specific buffer to database"""
    if not buffer:
        return

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.executemany("""
                INSERT INTO query_stats
                (tenant_id, table_name, field_name, query_type, duration_ms)
                VALUES (%s, %s, %s, %s, %s)
            """, buffer)
            conn.commit()
        except Exception as e:
            conn.rollback()
            # Log error but don't crash - stats are best-effort
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to flush query stats: {e}")
            raise
        finally:
            cursor.close()


def get_query_stats(time_window_hours=24, table_name=None, field_name=None):
    """Get aggregated query stats over a time window"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Build query with proper parameterized interval
            query = """
                SELECT
                    tenant_id,
                    table_name,
                    field_name,
                    query_type,
                    COUNT(*) as query_count,
                    AVG(duration_ms) as avg_duration_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) as p99_duration_ms
                FROM query_stats
                WHERE created_at >= NOW() - INTERVAL '1 hour' * %s
            """

            conditions = []
            params = []
            if table_name:
                conditions.append("table_name = %s")
                params.append(table_name)
            if field_name:
                conditions.append("field_name = %s")
                params.append(field_name)

            if conditions:
                query += " AND " + " AND ".join(conditions)

            query += """
                GROUP BY tenant_id, table_name, field_name, query_type
                ORDER BY query_count DESC
            """

            # Execute with time_window_hours as parameter
            all_params = [time_window_hours] + params
            cursor.execute(query, all_params)
            return cursor.fetchall()
        finally:
            cursor.close()


def get_field_usage_stats(time_window_hours=24):
    """Get field usage statistics aggregated across all tenants"""
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("""
                SELECT
                    table_name,
                    field_name,
                    COUNT(*) as total_queries,
                    COUNT(DISTINCT tenant_id) as tenant_count,
                    AVG(duration_ms) as avg_duration_ms,
                    SUM(duration_ms) as total_duration_ms
                FROM query_stats
                WHERE created_at >= NOW() - INTERVAL '1 hour' * %s
                  AND field_name IS NOT NULL
                GROUP BY table_name, field_name
                ORDER BY total_queries DESC
            """, (time_window_hours,))
            return cursor.fetchall()
        finally:
            cursor.close()


def get_table_row_count(table_name):
    """Get the current row count for a table (used for cost estimation)"""
    # Validate table name to prevent SQL injection
    from src.validation import validate_table_name
    table_name = validate_table_name(table_name)

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Use parameterized query with identifier quoting
            from psycopg2 import sql
            query = sql.SQL("SELECT COUNT(*) as count FROM {}").format(
                sql.Identifier(table_name)
            )
            cursor.execute(query)
            result = cursor.fetchone()
            return result['count'] if result else 0
        finally:
            cursor.close()


def get_table_size_bytes(table_name):
    """
    Get the table size on disk in bytes (table data only, excluding indexes).

    Args:
        table_name: Name of the table

    Returns:
        int: Table size in bytes, or 0 if table doesn't exist
    """
    from src.validation import validate_table_name
    table_name = validate_table_name(table_name)

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            from psycopg2 import sql
            query = sql.SQL("""
                SELECT pg_relation_size(%s::regclass) as size_bytes
            """)
            cursor.execute(query, (table_name,))
            result = cursor.fetchone()
            return result['size_bytes'] if result else 0
        except Exception as e:
            logger.warning(f"Error getting table size for {table_name}: {e}")
            return 0
        finally:
            cursor.close()


def get_table_total_size_bytes(table_name):
    """
    Get the total size on disk in bytes (table data + indexes).

    Args:
        table_name: Name of the table

    Returns:
        int: Total size in bytes, or 0 if table doesn't exist
    """
    from src.validation import validate_table_name
    table_name = validate_table_name(table_name)

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            from psycopg2 import sql
            query = sql.SQL("""
                SELECT pg_total_relation_size(%s::regclass) as size_bytes
            """)
            cursor.execute(query, (table_name,))
            result = cursor.fetchone()
            return result['size_bytes'] if result else 0
        except Exception as e:
            logger.warning(f"Error getting total table size for {table_name}: {e}")
            return 0
        finally:
            cursor.close()


def get_table_index_size_bytes(table_name):
    """
    Get the total size of all indexes for a table in bytes.

    Args:
        table_name: Name of the table

    Returns:
        int: Total index size in bytes, or 0 if table doesn't exist
    """
    from src.validation import validate_table_name
    table_name = validate_table_name(table_name)

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            from psycopg2 import sql
            query = sql.SQL("""
                SELECT
                    COALESCE(SUM(pg_relation_size(indexname::regclass)), 0) as total_index_size_bytes
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = %s
            """)
            cursor.execute(query, (table_name,))
            result = cursor.fetchone()
            return result['total_index_size_bytes'] if result else 0
        except Exception as e:
            logger.warning(f"Error getting index size for {table_name}: {e}")
            return 0
        finally:
            cursor.close()


def get_table_size_info(table_name):
    """
    Get comprehensive size information for a table.

    Args:
        table_name: Name of the table

    Returns:
        dict: Dictionary with row_count, table_size_bytes, index_size_bytes,
              total_size_bytes, and index_overhead_percent
    """
    row_count = get_table_row_count(table_name)
    table_size_bytes = get_table_size_bytes(table_name)
    index_size_bytes = get_table_index_size_bytes(table_name)
    total_size_bytes = table_size_bytes + index_size_bytes

    index_overhead_percent = 0.0
    if table_size_bytes > 0:
        index_overhead_percent = (index_size_bytes / table_size_bytes) * 100.0

    return {
        'row_count': row_count,
        'table_size_bytes': table_size_bytes,
        'index_size_bytes': index_size_bytes,
        'total_size_bytes': total_size_bytes,
        'index_overhead_percent': index_overhead_percent
    }
