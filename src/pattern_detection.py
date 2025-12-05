"""Sustained pattern detection to avoid false optimizations"""

import logging

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.monitoring import get_monitoring

logger = logging.getLogger(__name__)

# Configuration
MIN_DAYS_SUSTAINED = 3  # Minimum days of sustained pattern
MIN_QUERIES_PER_DAY = 50  # Minimum queries per day to be considered
SPIKE_DETECTION_WINDOW = 7  # Days to analyze for spikes
SPIKE_THRESHOLD = 3.0  # Spike if >3x average


def detect_sustained_pattern(table_name: str, field_name: str,
                            days: int = 7, time_window_hours: int | None = None) -> dict:
    """
    Detect if query pattern is sustained (not a one-time spike).

    Args:
        table_name: Table name
        field_name: Field name
        days: Number of days to analyze
        time_window_hours: If provided, use hourly analysis for short time windows (simulation mode)

    Returns:
        dict with pattern analysis
    """
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Validate inputs
            from src.validation import validate_field_name, validate_table_name
            table_name = validate_table_name(table_name)
            field_name = validate_field_name(field_name, table_name)

            # For short time windows (simulation mode), use hourly analysis instead of daily
            if time_window_hours and time_window_hours <= 24:
                # Use hourly grouping for simulations
                cursor.execute("""
                    SELECT
                        DATE_TRUNC('hour', created_at) as query_period,
                        COUNT(*) as query_count
                    FROM query_stats
                    WHERE table_name = %s
                      AND field_name = %s
                      AND created_at >= NOW() - INTERVAL '1 hour' * %s
                    GROUP BY DATE_TRUNC('hour', created_at)
                    ORDER BY query_period DESC
                """, (table_name, field_name, time_window_hours))

                period_counts = cursor.fetchall()
                
                # For simulations, require at least 2 hours of data and lower threshold
                min_periods_required = 2
                min_queries_per_period = 10  # Lower threshold for simulations
                
                if not period_counts or len(period_counts) < min_periods_required:
                    return {
                        'is_sustained': False,
                        'reason': f'Insufficient data: {len(period_counts) if period_counts else 0} hours',
                        'days_analyzed': len(period_counts) if period_counts else 0,
                        'avg_queries_per_day': 0,
                        'min_queries_per_day': 0,
                        'max_queries_per_day': 0
                    }
                
                # Calculate statistics for hourly data
                query_counts = [row['query_count'] for row in period_counts]
                avg_queries = sum(query_counts) / len(query_counts)
                min_queries = min(query_counts)
                max_queries = max(query_counts)
                
                # For simulations, be more lenient - just check if pattern exists
                periods_above_threshold = sum(1 for count in query_counts
                                             if count >= min_queries_per_period)
                is_sustained = (periods_above_threshold >= min_periods_required and
                              avg_queries >= min_queries_per_period)
                
                # Check for spike (one period much higher than average)
                is_spike = max_queries > avg_queries * SPIKE_THRESHOLD if avg_queries > 0 else False
                
                return {
                    'is_sustained': is_sustained and not is_spike,
                    'reason': 'sustained_pattern' if (is_sustained and not is_spike) else
                             ('spike_detected' if is_spike else
                              f'only_{periods_above_threshold}_periods_above_threshold'),
                    'days_analyzed': len(period_counts),
                    'days_above_threshold': periods_above_threshold,
                    'avg_queries_per_day': avg_queries,
                    'min_queries_per_day': min_queries,
                    'max_queries_per_day': max_queries,
                    'is_spike': is_spike,
                    'spike_ratio': max_queries / avg_queries if avg_queries > 0 else 0
                }
            
            # Original daily analysis for production
            # Get daily query counts
            cursor.execute("""
                SELECT
                    DATE(created_at) as query_date,
                    COUNT(*) as query_count
                FROM query_stats
                WHERE table_name = %s
                  AND field_name = %s
                  AND created_at >= NOW() - INTERVAL '1 day' * %s
                GROUP BY DATE(created_at)
                ORDER BY query_date DESC
            """, (table_name, field_name, days))

            daily_counts = cursor.fetchall()

            if not daily_counts or len(daily_counts) < MIN_DAYS_SUSTAINED:
                return {
                    'is_sustained': False,
                    'reason': f'Insufficient data: {len(daily_counts) if daily_counts else 0} days',
                    'days_analyzed': len(daily_counts) if daily_counts else 0,
                    'avg_queries_per_day': 0,
                    'min_queries_per_day': 0,
                    'max_queries_per_day': 0
                }

            # Calculate statistics
            query_counts = [row['query_count'] for row in daily_counts]
            avg_queries = sum(query_counts) / len(query_counts)
            min_queries = min(query_counts)
            max_queries = max(query_counts)

            # Check for spike (one day much higher than average)
            is_spike = max_queries > avg_queries * SPIKE_THRESHOLD

            # Check if pattern is sustained
            days_above_threshold = sum(1 for count in query_counts
                                     if count >= MIN_QUERIES_PER_DAY)
            is_sustained = (days_above_threshold >= MIN_DAYS_SUSTAINED and
                          not is_spike and
                          avg_queries >= MIN_QUERIES_PER_DAY)

            return {
                'is_sustained': is_sustained,
                'reason': 'sustained_pattern' if is_sustained else
                         ('spike_detected' if is_spike else
                          f'only_{days_above_threshold}_days_above_threshold'),
                'days_analyzed': len(daily_counts),
                'days_above_threshold': days_above_threshold,
                'avg_queries_per_day': avg_queries,
                'min_queries_per_day': min_queries,
                'max_queries_per_day': max_queries,
                'is_spike': is_spike,
                'spike_ratio': max_queries / avg_queries if avg_queries > 0 else 0
            }
        finally:
            cursor.close()


def should_create_index_based_on_pattern(table_name: str, field_name: str,
                                         total_queries: int, time_window_hours: int | None = None) -> tuple[bool, str]:
    """
    Determine if index should be created based on sustained pattern.

    Args:
        table_name: Table name
        field_name: Field name
        total_queries: Total queries in time window
        time_window_hours: Time window in hours (for simulation mode)

    Returns:
        (should_create, reason)
    """
    # Check for sustained pattern
    if time_window_hours and time_window_hours <= 24:
        # Simulation mode: use hourly analysis
        pattern = detect_sustained_pattern(table_name, field_name,
                                          days=1, time_window_hours=time_window_hours)
        # Lower threshold for simulations
        min_queries_for_simulation = 20
        if total_queries < min_queries_for_simulation:
            reason = f"Insufficient query volume: {total_queries} queries (simulation mode requires {min_queries_for_simulation})"
            return False, reason
    else:
        # Production mode: use daily analysis
        pattern = detect_sustained_pattern(table_name, field_name,
                                          days=SPIKE_DETECTION_WINDOW)
        # Pattern is sustained, check query volume
        if total_queries < MIN_QUERIES_PER_DAY * MIN_DAYS_SUSTAINED:
            reason = f"Insufficient query volume: {total_queries} queries"
            return False, reason

    if not pattern['is_sustained']:
        reason = f"Pattern not sustained: {pattern['reason']}"
        logger.info(f"Skipping index for {table_name}.{field_name}: {reason}")

        # Alert if it's a spike
        if pattern.get('is_spike'):
            monitoring = get_monitoring()
            monitoring.alert('info',
                           f'Spike detected for {table_name}.{field_name} '
                           f'(ratio: {pattern["spike_ratio"]:.1f}x), skipping index')

        return False, reason

    return True, "sustained_pattern_detected"


def get_pattern_summary(table_name: str, field_name: str) -> dict:
    """Get summary of query pattern for a field"""
    pattern = detect_sustained_pattern(table_name, field_name)

    return {
        'table': table_name,
        'field': field_name,
        'pattern_analysis': pattern,
        'recommendation': 'create_index' if pattern['is_sustained'] else 'skip_index'
    }

