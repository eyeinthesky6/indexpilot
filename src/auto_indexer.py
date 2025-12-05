"""Auto-indexer - automatic index creation based on query patterns"""

import logging
import threading
from typing import Any

from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from src.config_loader import ConfigLoader
from src.db import get_connection
from src.error_handler import IndexCreationError, handle_errors
from src.lock_manager import create_index_with_lock_management
from src.maintenance_window import is_in_maintenance_window, should_wait_for_maintenance_window
from src.monitoring import get_monitoring
from src.pattern_detection import should_create_index_based_on_pattern
from src.query_analyzer import analyze_query_plan, measure_query_performance
from src.query_patterns import detect_query_patterns, get_null_ratio
from src.rate_limiter import check_index_creation_rate_limit
from src.rollback import require_enabled
from src.stats import (
    get_field_usage_stats,
    get_table_row_count,
    get_table_size_info,
)
from src.write_performance import can_create_index_for_table, monitor_write_performance

logger = logging.getLogger(__name__)

# Load configuration with error handling
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    # Create a minimal config loader that will use defaults
    _config_loader = ConfigLoader()

# Cost tuning configuration constants
# Loaded from config file with defaults
def _get_cost_config() -> dict[str, Any]:
    """Get cost configuration from config file with validation"""
    config = {
        'BUILD_COST_PER_1000_ROWS': _config_loader.get_float('features.auto_indexer.build_cost_per_1000_rows', 1.0),
        'QUERY_COST_PER_10000_ROWS': _config_loader.get_float('features.auto_indexer.query_cost_per_10000_rows', 1.0),
        'MIN_QUERY_COST': _config_loader.get_float('features.auto_indexer.min_query_cost', 0.1),
        'INDEX_TYPE_COSTS': {
            'partial': _config_loader.get_float('features.auto_indexer.index_type_costs.partial', 0.5),
            'expression': _config_loader.get_float('features.auto_indexer.index_type_costs.expression', 0.7),
            'standard': _config_loader.get_float('features.auto_indexer.index_type_costs.standard', 1.0),
            'multi_column': _config_loader.get_float('features.auto_indexer.index_type_costs.multi_column', 1.2),
        },
        'MIN_SELECTIVITY_FOR_INDEX': _config_loader.get_float('features.auto_indexer.min_selectivity_for_index', 0.01),
        'HIGH_SELECTIVITY_THRESHOLD': _config_loader.get_float('features.auto_indexer.high_selectivity_threshold', 0.5),
        'MIN_IMPROVEMENT_PCT': _config_loader.get_float('features.auto_indexer.min_improvement_pct', 20.0),
        'SAMPLE_QUERY_RUNS': _config_loader.get_int('features.auto_indexer.sample_query_runs', 5),
        'USE_REAL_QUERY_PLANS': _config_loader.get_bool('features.auto_indexer.use_real_query_plans', True),
        'MIN_PLAN_COST_FOR_INDEX': _config_loader.get_float('features.auto_indexer.min_plan_cost_for_index', 100.0),
        # Table size thresholds
        'SMALL_TABLE_ROW_COUNT': _config_loader.get_int('features.auto_indexer.small_table_row_count', 1000),
        'MEDIUM_TABLE_ROW_COUNT': _config_loader.get_int('features.auto_indexer.medium_table_row_count', 10000),
        'SMALL_TABLE_MIN_QUERIES_PER_HOUR': _config_loader.get_int('features.auto_indexer.small_table_min_queries_per_hour', 1000),
        'SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT': _config_loader.get_float('features.auto_indexer.small_table_max_index_overhead_pct', 50.0),
        'MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT': _config_loader.get_float('features.auto_indexer.medium_table_max_index_overhead_pct', 60.0),
        'LARGE_TABLE_COST_REDUCTION_FACTOR': _config_loader.get_float('features.auto_indexer.large_table_cost_reduction_factor', 0.8),
        'MAX_WAIT_FOR_MAINTENANCE_WINDOW': _config_loader.get_int('features.auto_indexer.max_wait_for_maintenance_window', 3600),
    }

    # Validate logical constraints
    small_count: int = int(config['SMALL_TABLE_ROW_COUNT'])  # type: ignore[call-overload]
    medium_count: int = int(config['MEDIUM_TABLE_ROW_COUNT'])  # type: ignore[call-overload]
    if small_count >= medium_count:
        logger.warning(
            f"Invalid table size thresholds: small ({small_count}) >= medium "
            f"({medium_count}), adjusting"
        )
        config['SMALL_TABLE_ROW_COUNT'] = min(1000, medium_count - 1000)

    min_selectivity: float = float(config['MIN_SELECTIVITY_FOR_INDEX'])  # type: ignore[arg-type]
    high_selectivity: float = float(config['HIGH_SELECTIVITY_THRESHOLD'])  # type: ignore[arg-type]
    if min_selectivity >= high_selectivity:
        logger.warning(
            f"Invalid selectivity thresholds: min ({min_selectivity}) >= high "
            f"({high_selectivity}), adjusting"
        )
        config['MIN_SELECTIVITY_FOR_INDEX'] = min(0.01, high_selectivity - 0.1)

    # Validate cost factors are positive
    for key in ['BUILD_COST_PER_1000_ROWS', 'QUERY_COST_PER_10000_ROWS', 'MIN_QUERY_COST']:
        cost_value: float = float(config[key])  # type: ignore[arg-type]
        if cost_value <= 0:
            logger.warning(f"Invalid {key}: {cost_value}, must be positive, using default")
            config[key] = {'BUILD_COST_PER_1000_ROWS': 1.0, 'QUERY_COST_PER_10000_ROWS': 1.0, 'MIN_QUERY_COST': 0.1}[key]

    # Validate percentage values are in [0, 100]
    for key in ['SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT', 'MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT', 'MIN_IMPROVEMENT_PCT']:
        pct_value: float = float(config[key])  # type: ignore[arg-type]
        if not (0 <= pct_value <= 100):
            logger.warning(f"Invalid {key}: {pct_value}, must be in [0, 100], clamping")
            config[key] = max(0, min(100, pct_value))

    # Validate reduction factor is in [0, 1]
    reduction_factor: float = float(config['LARGE_TABLE_COST_REDUCTION_FACTOR'])  # type: ignore[arg-type]
    if not (0 < reduction_factor <= 1):
        logger.warning(f"Invalid LARGE_TABLE_COST_REDUCTION_FACTOR: {reduction_factor}, clamping to [0.1, 1.0]")
        config['LARGE_TABLE_COST_REDUCTION_FACTOR'] = max(0.1, min(1.0, reduction_factor))

    return config

# Cache config to avoid repeated lookups
_COST_CONFIG = _get_cost_config()


def should_create_index(estimated_build_cost, queries_over_horizon, extra_cost_per_query_without_index,
                        table_size_info=None, field_selectivity=None):
    """
    Decide if an index should be created based on cost-benefit analysis with size-aware thresholds.

    Args:
        estimated_build_cost: Estimated cost to build the index (proportional to table size)
        queries_over_horizon: Number of queries expected over the time horizon
        extra_cost_per_query_without_index: Additional cost per query without index
        table_size_info: Optional dict with table size information (from get_table_size_info)
        field_selectivity: Optional field selectivity (0.0 to 1.0)

    Returns:
        Tuple of (should_create: bool, confidence: float, reason: str)
    """
    if queries_over_horizon == 0:
        return False, 0.0, "no_queries"

    total_query_cost_without_index = queries_over_horizon * extra_cost_per_query_without_index

    # Base decision: cost of queries without index exceeds build cost
    cost_benefit_ratio = total_query_cost_without_index / estimated_build_cost if estimated_build_cost > 0 else 0
    base_decision = cost_benefit_ratio > 1.0

    # Calculate confidence score (0.0 to 1.0)
    confidence = min(1.0, cost_benefit_ratio / 2.0)  # 2x benefit = full confidence

    reason = "cost_benefit_met" if base_decision else "cost_benefit_not_met"

    # Apply size-based adaptive thresholds
    if table_size_info:
        row_count = table_size_info.get('row_count', 0)
        index_overhead_percent = table_size_info.get('index_overhead_percent', 0.0)

        # Small tables: Require higher query volume threshold
        if row_count < _COST_CONFIG['SMALL_TABLE_ROW_COUNT']:
            # Require minimum queries/hour equivalent for small tables
            queries_per_hour_equivalent = queries_over_horizon / 24.0  # Assuming 24h horizon
            if queries_per_hour_equivalent < _COST_CONFIG['SMALL_TABLE_MIN_QUERIES_PER_HOUR']:
                return False, 0.0, "small_table_low_query_volume"
            # Also check if index overhead would be too high
            if index_overhead_percent > _COST_CONFIG['SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT']:
                return False, 0.0, "small_table_high_overhead"
            # Small tables need higher benefit ratio
            if cost_benefit_ratio < 2.0:
                return False, confidence, "small_table_insufficient_benefit"

        # Medium tables: Standard thresholds
        elif row_count < _COST_CONFIG['MEDIUM_TABLE_ROW_COUNT']:
            # Standard thresholds apply, but check overhead
            if index_overhead_percent > _COST_CONFIG['MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT']:
                return False, 0.0, "medium_table_high_overhead"
            # Require at least 1.5x benefit for medium tables
            if cost_benefit_ratio < 1.5:
                return False, confidence, "medium_table_insufficient_benefit"

        # Large tables: Lower thresholds, more aggressive indexing
        else:
            # For large tables, be more lenient - indexes are more beneficial
            # Apply cost reduction factor for large tables
            adjusted_build_cost = estimated_build_cost * _COST_CONFIG['LARGE_TABLE_COST_REDUCTION_FACTOR']
            adjusted_ratio = total_query_cost_without_index / adjusted_build_cost if adjusted_build_cost > 0 else 0
            if adjusted_ratio > 1.0:
                confidence = min(1.0, adjusted_ratio / 1.5)  # Boost confidence for large tables
                return True, confidence, "large_table_benefit"

    # Check field selectivity
    if field_selectivity is not None:
        if field_selectivity < _COST_CONFIG['MIN_SELECTIVITY_FOR_INDEX']:
            # Very low selectivity - probably not worth indexing
            return False, 0.0, f"low_selectivity_{field_selectivity:.3f}"
        elif field_selectivity > _COST_CONFIG['HIGH_SELECTIVITY_THRESHOLD']:
            # High selectivity - boost confidence
            confidence = min(1.0, confidence * 1.2)
            reason = "high_selectivity_benefit"

    return base_decision, confidence, reason


def get_field_selectivity(table_name, field_name) -> float:
    """
    Calculate field selectivity (distinct values / total rows).

    High selectivity (many distinct values) = better index candidate
    Low selectivity (few distinct values) = less beneficial index

    Returns:
        Selectivity ratio (0.0 to 1.0), or 0.0 if unable to calculate
    """
    try:
        from src.validation import validate_field_name, validate_table_name
        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Get distinct count and total rows
                query = sql.SQL("""
                    SELECT
                        COUNT(DISTINCT {}) as distinct_count,
                        COUNT(*) as total_rows
                    FROM {}
                """).format(
                    sql.Identifier(validated_field),
                    sql.Identifier(validated_table)
                )
                cursor.execute(query)
                result = cursor.fetchone()

                if result and result['total_rows'] and result['total_rows'] > 0:
                    distinct_count = result['distinct_count'] or 0
                    total_rows = result['total_rows']
                    selectivity = distinct_count / total_rows
                    return float(selectivity)
                return 0.0
            finally:
                cursor.close()
    except Exception as e:
        logger.debug(f"Could not calculate selectivity for {table_name}.{field_name}: {e}")
        return 0.0


def get_sample_query_for_field(table_name, field_name, tenant_id=None) -> tuple | None:
    """
    Construct a sample query for a field to use with EXPLAIN.

    Returns:
        Tuple of (query_string, params) or None if unable to construct
    """
    try:
        from src.validation import validate_field_name, validate_table_name
        validated_table = validate_table_name(table_name)
        validated_field = validate_field_name(field_name, table_name)

        # Check if table has tenant_id field
        has_tenant = _has_tenant_field(table_name, use_cache=True)

        # Construct a simple WHERE query on the field
        with get_connection() as conn:
            if has_tenant and tenant_id:
                # Multi-tenant query
                query = sql.SQL("SELECT * FROM {} WHERE tenant_id = %s AND {} = %s LIMIT 1").format(
                    sql.Identifier(validated_table),
                    sql.Identifier(validated_field)
                )
                # Use a placeholder value - actual value doesn't matter for EXPLAIN
                params = [tenant_id, None]
            elif has_tenant:
                # Multi-tenant without specific tenant
                query = sql.SQL("SELECT * FROM {} WHERE tenant_id = %s AND {} IS NOT NULL LIMIT 1").format(
                    sql.Identifier(validated_table),
                    sql.Identifier(validated_field)
                )
                params = [None]
            else:
                # Single-tenant query
                query = sql.SQL("SELECT * FROM {} WHERE {} = %s LIMIT 1").format(
                    sql.Identifier(validated_table),
                    sql.Identifier(validated_field)
                )
                params = [None]

            return (query.as_string(conn), params)
    except Exception as e:
        logger.debug(f"Could not construct sample query for {table_name}.{field_name}: {e}")
        return None


def estimate_build_cost(table_name, field_name, row_count=None, index_type='standard'):
    """
    Estimate the cost of building an index.

    Uses real query plan costs when available, falls back to row-count-based estimation.

    Args:
        table_name: Table name
        field_name: Field name
        row_count: Optional row count (will fetch if not provided)
        index_type: Type of index ('standard', 'partial', 'expression', 'multi_column')

    Returns:
        Estimated build cost
    """
    if row_count is None:
        row_count = get_table_row_count(table_name)

    # Base cost: proportional to table row count
    base_cost = row_count / (1000.0 / _COST_CONFIG['BUILD_COST_PER_1000_ROWS'])

    # Apply index type multiplier
    type_multiplier = _COST_CONFIG['INDEX_TYPE_COSTS'].get(index_type, 1.0)
    estimated_cost = base_cost * type_multiplier

    # Try to get more accurate cost from actual index creation estimate
    # PostgreSQL can estimate index build cost using EXPLAIN
    if _COST_CONFIG['USE_REAL_QUERY_PLANS']:
        try:
            # Get a sample query to estimate index benefit
            sample_query = get_sample_query_for_field(table_name, field_name)
            if sample_query:
                query_str, params = sample_query
                # Use EXPLAIN to estimate index build cost
                # Note: This is an approximation - actual CREATE INDEX cost may differ
                plan = analyze_query_plan(query_str, params)
                if plan and plan.get('total_cost', 0) > 0:
                    # Use plan cost as a reference, but scale by row count
                    # Index build is typically O(n log n), so we use a scaling factor
                    plan_cost = plan.get('total_cost', 0)
                    # Scale plan cost to build cost (build is typically 2-5x query cost)
                    build_cost_from_plan = plan_cost * 3.0 * type_multiplier
                    # Use weighted average: 70% from plan, 30% from row count
                    estimated_cost = (build_cost_from_plan * 0.7) + (estimated_cost * 0.3)
        except Exception as e:
            logger.debug(f"Could not use query plan for build cost estimation: {e}")
            # Fall back to row-count-based estimate

    return estimated_cost


def estimate_query_cost_without_index(table_name, field_name, row_count=None,
                                       use_real_plans=True):
    """
    Estimate the cost per query without an index.

    Uses real EXPLAIN plan costs when available, falls back to row-count-based estimation.

    Args:
        table_name: Table name
        field_name: Field name
        row_count: Optional row count (will fetch if not provided)
        use_real_plans: Whether to use real query plans (default: True)

    Returns:
        Estimated cost per query without index
    """
    if row_count is None:
        row_count = get_table_row_count(table_name)

    # Base cost: full table scan cost proportional to row count
    base_cost = max(_COST_CONFIG['MIN_QUERY_COST'],
                   row_count / (10000.0 / _COST_CONFIG['QUERY_COST_PER_10000_ROWS']))

    # Try to get real cost from EXPLAIN plan
    if use_real_plans and _COST_CONFIG['USE_REAL_QUERY_PLANS']:
        try:
            # Get sample queries from stats to analyze
            from src.stats import get_query_stats
            query_stats = get_query_stats(time_window_hours=24,
                                         table_name=table_name,
                                         field_name=field_name)

            if query_stats and len(query_stats) > 0:
                # Get a representative tenant_id for sample query
                tenant_id = query_stats[0].get('tenant_id')
                sample_query = get_sample_query_for_field(table_name, field_name, tenant_id)

                if sample_query:
                    query_str, params = sample_query
                    plan = analyze_query_plan(query_str, params)

                    if plan:
                        plan_cost = plan.get('total_cost', 0)
                        has_seq_scan = plan.get('has_seq_scan', False)
                        actual_time = plan.get('actual_time_ms', 0)

                        # If we have a sequential scan with high cost, use that
                        if has_seq_scan and plan_cost > _COST_CONFIG['MIN_PLAN_COST_FOR_INDEX']:
                            # Use actual plan cost, but convert to our cost units
                            # Plan costs are in PostgreSQL cost units, we normalize them
                            # Typical seq scan cost: ~0.01 per row, so divide by 100
                            normalized_cost = plan_cost / 100.0
                            # Use weighted average: 80% from plan, 20% from row count
                            base_cost = (normalized_cost * 0.8) + (base_cost * 0.2)

                            # Also factor in actual execution time if available
                            if actual_time > 0:
                                # Convert ms to cost units (rough approximation)
                                time_based_cost = actual_time / 10.0  # 10ms = 1 cost unit
                                # Blend time and cost estimates
                                base_cost = (base_cost * 0.6) + (time_based_cost * 0.4)
        except Exception as e:
            logger.debug(f"Could not use query plan for query cost estimation: {e}")
            # Fall back to row-count-based estimate

    # Factor in field selectivity
    selectivity = get_field_selectivity(table_name, field_name)
    if selectivity > 0:
        # Low selectivity fields (e.g., boolean flags) have lower query cost
        # High selectivity fields have higher query cost (more rows to scan)
        # Adjust cost based on selectivity
        if selectivity < _COST_CONFIG['MIN_SELECTIVITY_FOR_INDEX']:
            # Very low selectivity - queries are cheap (few distinct values)
            base_cost *= 0.5
        elif selectivity > _COST_CONFIG['HIGH_SELECTIVITY_THRESHOLD']:
            # High selectivity - queries are expensive (many distinct values)
            base_cost *= 1.2

    return base_cost


def get_optimization_strategy(table_name, row_count, table_size_info=None):
    """
    Get optimization strategy based on table size with size-aware thresholds.

    Args:
        table_name: Name of the table
        row_count: Number of rows in the table
        table_size_info: Optional dict with table size information

    Returns:
        dict: Strategy with primary/secondary approaches and thresholds
    """
    # Get table size info if not provided
    if table_size_info is None:
        table_size_info = get_table_size_info(table_name)

    if row_count < _COST_CONFIG['SMALL_TABLE_ROW_COUNT']:
        # Small tables: Very selective indexing
        return {
            'primary': 'caching',
            'secondary': 'micro_indexes',
            'skip_traditional_indexes': True,
            'min_query_threshold': _COST_CONFIG['SMALL_TABLE_MIN_QUERIES_PER_HOUR'],
            'max_index_overhead': _COST_CONFIG['SMALL_TABLE_MAX_INDEX_OVERHEAD_PCT'],
            'size_category': 'small'
        }
    elif row_count < _COST_CONFIG['MEDIUM_TABLE_ROW_COUNT']:
        # Medium tables: Standard approach
        return {
            'primary': 'micro_indexes',
            'secondary': 'caching',
            'skip_traditional_indexes': False,
            'min_query_threshold': 100,  # Standard threshold
            'max_index_overhead': _COST_CONFIG['MEDIUM_TABLE_MAX_INDEX_OVERHEAD_PCT'],
            'size_category': 'medium'
        }
    else:
        # Large tables: More aggressive indexing
        return {
            'primary': 'indexing',
            'secondary': 'caching',
            'skip_traditional_indexes': False,
            'min_query_threshold': 50,  # Lower threshold for large tables
            'max_index_overhead': 80.0,  # Can tolerate higher overhead
            'size_category': 'large'
        }


# Cache for tenant field detection (performance optimization)
_tenant_field_cache: dict[str, bool] = {}
_tenant_field_cache_lock = threading.Lock()


def _has_tenant_field(table_name: str, use_cache: bool = True) -> bool:
    """
    Check if table has a tenant_id field (or similar tenant field).

    Uses caching to avoid repeated database queries.

    Args:
        table_name: Table name to check
        use_cache: Whether to use cache (default: True)

    Returns:
        True if table has tenant field, False otherwise
    """
    # Check cache first
    if use_cache:
        with _tenant_field_cache_lock:
            if table_name in _tenant_field_cache:
                return _tenant_field_cache[table_name]

    result = False
    try:
        from psycopg2.extras import RealDictCursor

        from src.db import get_connection

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Check genome_catalog for tenant_id or similar fields
                cursor.execute("""
                    SELECT field_name
                    FROM genome_catalog
                    WHERE table_name = %s
                      AND (field_name = 'tenant_id' OR field_name LIKE 'tenant_%')
                """, (table_name,))
                result = cursor.fetchone() is not None
            finally:
                cursor.close()
    except Exception:
        # If genome_catalog not available, try to check actual table
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = %s
                          AND (column_name = 'tenant_id' OR column_name LIKE 'tenant_%')
                    """, (table_name,))
                    result = cursor.fetchone() is not None
                finally:
                    cursor.close()
        except Exception:
            # Default: assume no tenant field (single-tenant or non-multi-tenant)
            result = False

    # Cache result
    if use_cache:
        with _tenant_field_cache_lock:
            _tenant_field_cache[table_name] = result

    return result


def clear_tenant_field_cache():
    """Clear the tenant field cache (useful after schema changes)"""
    global _tenant_field_cache
    with _tenant_field_cache_lock:
        _tenant_field_cache.clear()


def create_smart_index(table_name, field_name, row_count, query_patterns, _strategy=None):
    """
    Create optimized index based on query patterns and table size.
    Returns SQL for creating the index and index type.

    Automatically detects if table has tenant_id field and creates appropriate index.

    Args:
        table_name: Table name
        field_name: Field name
        row_count: Number of rows in table
        query_patterns: Dict with query pattern information
        _strategy: Optimization strategy (reserved for future use)

    Returns:
        Tuple of (index_sql, index_name, index_type)
    """
    quoted_table = f'"{table_name}"'
    quoted_field = f'"{field_name}"'

    # Check if table has tenant field
    has_tenant = _has_tenant_field(table_name)

    # Check for LIKE queries (pattern matching)
    has_like = query_patterns.get('has_like', False)

    # Check NULL ratio
    null_ratio = get_null_ratio(table_name, field_name)

    # Determine index type
    if has_like and row_count < _COST_CONFIG['MEDIUM_TABLE_ROW_COUNT']:
        # Expression index for text search on small-medium tables
        index_type = 'expression'
        if has_tenant:
            index_name = f'idx_{table_name}_{field_name}_lower_tenant'
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}(tenant_id, LOWER({quoted_field}))
            """
        else:
            index_name = f'idx_{table_name}_{field_name}_lower'
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}(LOWER({quoted_field}))
            """
        return index_sql, index_name, index_type
    elif null_ratio > 0.5 and row_count < _COST_CONFIG['MEDIUM_TABLE_ROW_COUNT']:
        # Partial index: only index non-null values
        index_type = 'partial'
        if has_tenant:
            index_name = f'idx_{table_name}_{field_name}_partial_tenant'
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}(tenant_id, {quoted_field})
                WHERE {quoted_field} IS NOT NULL
            """
        else:
            index_name = f'idx_{table_name}_{field_name}_partial'
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}({quoted_field})
                WHERE {quoted_field} IS NOT NULL
            """
        return index_sql, index_name, index_type
    else:
        # Standard index (with tenant_id if available)
        index_type = 'multi_column' if has_tenant else 'standard'
        if has_tenant:
            index_name = f'idx_{table_name}_{field_name}_tenant'
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}(tenant_id, {quoted_field})
            """
        else:
            index_name = f'idx_{table_name}_{field_name}'
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS "{index_name}"
                ON {quoted_table}({quoted_field})
            """
        return index_sql, index_name, index_type


@require_enabled
@handle_errors("analyze_and_create_indexes", default_return={'created': [], 'skipped': []})
def analyze_and_create_indexes(time_window_hours=24, min_query_threshold=100):
    """
    Analyze query stats and create indexes for fields that meet the threshold.

    Args:
        time_window_hours: Time window to analyze queries
        min_query_threshold: Minimum number of queries required to consider indexing
    """
    created_indexes = []
    skipped_indexes = []

    # Get field usage statistics
    print(f"  Analyzing query stats from last {time_window_hours} hours...")
    field_stats = get_field_usage_stats(time_window_hours)
    print(f"  Found {len(field_stats)} field patterns to analyze")

    if not field_stats:
        print("  No query statistics found. Skipping index creation.")
        return {'created': [], 'skipped': []}

    # Validate all table/field names before processing
    from src.validation import validate_field_name, validate_table_name

    validated_stats = []
    for stat in field_stats:
        try:
            table_name = validate_table_name(stat['table_name'])
            field_name = validate_field_name(stat['field_name'], table_name)
            stat['table_name'] = table_name
            stat['field_name'] = field_name
            validated_stats.append(stat)
        except ValueError as e:
            logger.warning(f"Skipping invalid stat: {e}")
            continue

    if not validated_stats:
        print("  No valid query statistics found after validation.")
        return {'created': [], 'skipped': []}

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            for stat in validated_stats:
                table_name = stat['table_name']
                field_name = stat['field_name']
                total_queries = stat['total_queries']

                # Check if any index already exists for this field
                # (could be standard, partial, or expression index)
                # Check if table has tenant field to determine index name patterns
                has_tenant = _has_tenant_field(table_name)

                if has_tenant:
                    # Multi-tenant index patterns
                    standard_index = f"idx_{table_name}_{field_name}_tenant"
                    partial_index = f"idx_{table_name}_{field_name}_partial_tenant"
                    expr_index = f"idx_{table_name}_{field_name}_lower_tenant"
                else:
                    # Single-tenant index patterns
                    standard_index = f"idx_{table_name}_{field_name}"
                    partial_index = f"idx_{table_name}_{field_name}_partial"
                    expr_index = f"idx_{table_name}_{field_name}_lower"

                # Validate table name to prevent SQL injection
                from src.validation import validate_table_name
                validated_table_name = validate_table_name(table_name)

                # Use PostgreSQL-specific query (could be abstracted via adapter in future)
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM pg_indexes
                    WHERE tablename = %s
                      AND (indexname = %s OR indexname = %s OR indexname = %s
                           OR indexdef LIKE %s)
                """, (validated_table_name, standard_index, partial_index, expr_index, f'%{field_name}%'))
                result = cursor.fetchone()
                exists = result['count'] > 0 if result else False

                if exists:
                    skipped_indexes.append({
                        'table': table_name,
                        'field': field_name,
                        'queries': total_queries,
                        'reason': 'already_exists'
                    })
                    continue

                # Check if we can create index (write performance limits)
                can_create, limit_reason = can_create_index_for_table(table_name)
                if not can_create:
                    skipped_indexes.append({
                        'table': table_name,
                        'field': field_name,
                        'queries': total_queries,
                        'reason': limit_reason
                    })
                    continue

                # Check for sustained pattern (not a spike)
                pattern_ok, pattern_reason = should_create_index_based_on_pattern(
                    table_name, field_name, total_queries, time_window_hours=time_window_hours
                )
                if not pattern_ok:
                    skipped_indexes.append({
                        'table': table_name,
                        'field': field_name,
                        'queries': total_queries,
                        'reason': pattern_reason
                    })
                    continue

                # Check rate limiting (security: prevent abuse)
                rate_allowed, retry_after = check_index_creation_rate_limit(table_name)
                if not rate_allowed:
                    skipped_indexes.append({
                        'table': table_name,
                        'field': field_name,
                        'queries': total_queries,
                        'reason': f'rate_limit_exceeded (retry after {retry_after:.1f}s)'
                    })
                    continue

                # Check maintenance window (unless urgent)
                if not is_in_maintenance_window():
                    should_wait, wait_seconds = should_wait_for_maintenance_window(
                        "index_creation", max_wait_hours=6.0
                    )
                    if should_wait and wait_seconds > _COST_CONFIG['MAX_WAIT_FOR_MAINTENANCE_WINDOW']:
                        skipped_indexes.append({
                            'table': table_name,
                            'field': field_name,
                            'queries': total_queries,
                            'reason': f'outside_maintenance_window (wait {wait_seconds/3600:.1f}h)'
                        })
                        continue

                # Get table size information and strategy
                row_count = get_table_row_count(table_name)
                table_size_info = get_table_size_info(table_name)
                strategy = get_optimization_strategy(table_name, row_count, table_size_info)

                # Apply size-based query threshold
                min_query_threshold = strategy.get('min_query_threshold', min_query_threshold)
                if total_queries < min_query_threshold:
                    skipped_indexes.append({
                        'table': table_name,
                        'field': field_name,
                        'queries': total_queries,
                        'reason': f'below_size_based_threshold (required: {min_query_threshold}, size_category: {strategy.get("size_category", "unknown")})'
                    })
                    continue

                # Check index overhead limit
                max_index_overhead = strategy.get('max_index_overhead', 100.0)
                current_overhead = table_size_info.get('index_overhead_percent', 0.0)
                if current_overhead >= max_index_overhead:
                    skipped_indexes.append({
                        'table': table_name,
                        'field': field_name,
                        'queries': total_queries,
                        'reason': f'index_overhead_limit_exceeded (current: {current_overhead:.1f}%, max: {max_index_overhead:.1f}%)'
                    })
                    continue

                # Detect query patterns
                query_patterns = detect_query_patterns(table_name, field_name, time_window_hours)

                # Get field selectivity for better cost estimation
                field_selectivity = get_field_selectivity(table_name, field_name)

                # Determine index type based on patterns (preview)
                strategy = get_optimization_strategy(table_name, row_count, table_size_info)
                _preview_index_sql, _preview_index_name, preview_index_type = create_smart_index(
                    table_name, field_name, row_count, query_patterns, strategy
                )

                # Estimate costs with index type consideration
                build_cost = estimate_build_cost(table_name, field_name, row_count, preview_index_type)
                query_cost_without_index = estimate_query_cost_without_index(
                    table_name, field_name, row_count, use_real_plans=True
                )

                # Decide if we should create the index (with size-aware analysis)
                should_create, confidence, reason = should_create_index(
                    build_cost,
                    total_queries,
                    query_cost_without_index,
                    table_size_info,
                    field_selectivity
                )

                # For small tables, prefer micro-indexes even if traditional index would be skipped
                if strategy['skip_traditional_indexes'] and should_create:
                    # Still create, but use micro-index
                    should_create = True

                if should_create:
                    # Monitor write performance before creating
                    write_stats = monitor_write_performance(table_name)

                    # Measure performance before index creation (if we have sample queries)
                    before_perf = None
                    sample_query = None
                    try:
                        from src.stats import get_query_stats
                        query_stats = get_query_stats(time_window_hours=24,
                                                     table_name=table_name,
                                                     field_name=field_name)
                        if query_stats and len(query_stats) > 0:
                            # Get a representative tenant_id
                            tenant_id = query_stats[0].get('tenant_id')
                            sample_query = get_sample_query_for_field(table_name, field_name, tenant_id)

                            if sample_query:
                                query_str, params = sample_query
                                before_perf = measure_query_performance(
                                    query_str, params,
                                    num_runs=_COST_CONFIG['SAMPLE_QUERY_RUNS']
                                )
                                # Note: before_plan analysis removed as it was unused
                    except Exception as e:
                        logger.debug(f"Could not measure before performance: {e}")

                    # Create smart index based on patterns and size
                    index_sql, index_name, index_type = create_smart_index(
                        table_name, field_name, row_count, query_patterns, strategy
                    )

                    try:
                        print(f"  Creating index {index_name} on {table_name}.{field_name} "
                              f"(type: {index_type}, confidence: {confidence:.2f})...")

                        # Use lock management with CPU throttling for index creation
                        success = create_index_with_lock_management(
                            table_name, field_name, index_sql, timeout=300,
                            respect_cpu_throttle=True
                        )

                        if not success:
                            # Index creation was throttled, skip this index
                            logger.warning(f"Index creation throttled for {index_name}")
                            skipped_indexes.append({
                                'table': table_name,
                                'field': field_name,
                                'queries': total_queries,
                                'reason': 'cpu_throttled'
                            })
                            continue

                        # Measure performance after index creation
                        after_perf = None
                        improvement_pct = 0.0
                        try:
                            if sample_query and before_perf:
                                query_str, params = sample_query
                                # Wait a moment for index to be ready
                                import time
                                time.sleep(0.5)

                                after_perf = measure_query_performance(
                                    query_str, params,
                                    num_runs=_COST_CONFIG['SAMPLE_QUERY_RUNS']
                                )
                                # Note: after_plan analysis removed as it was unused

                                # Calculate improvement
                                if before_perf['median_ms'] > 0:
                                    improvement_pct = ((before_perf['median_ms'] - after_perf['median_ms'])
                                                     / before_perf['median_ms']) * 100.0

                                # If improvement is below threshold, consider removing index
                                if improvement_pct < _COST_CONFIG['MIN_IMPROVEMENT_PCT']:
                                    logger.warning(
                                        f"Index {index_name} shows only {improvement_pct:.1f}% improvement "
                                        f"(below {_COST_CONFIG['MIN_IMPROVEMENT_PCT']}% threshold)"
                                    )
                                    # Note: We keep the index but log the warning
                                    # Future enhancement: auto-rollback if improvement is negative
                        except Exception as e:
                            logger.debug(f"Could not measure after performance: {e}")

                        # Log the mutation to audit trail
                        from src.audit import log_audit_event
                        log_audit_event(
                            'CREATE_INDEX',
                            table_name=table_name,
                            field_name=field_name,
                            details={
                                'index_name': index_name,
                                'index_type': index_type,
                                'build_cost_estimate': build_cost,
                                'queries_analyzed': total_queries,
                                'query_cost_without_index': query_cost_without_index,
                                'row_count': row_count,
                                'field_selectivity': field_selectivity,
                                'confidence': confidence,
                                'reason': reason,
                                'strategy': strategy['primary'],
                                'before_perf_ms': before_perf['median_ms'] if before_perf else None,
                                'after_perf_ms': after_perf['median_ms'] if after_perf else None,
                                'improvement_pct': improvement_pct if after_perf else None
                            },
                            severity='info'
                        )

                        # Monitor write performance after creating
                        monitor_write_performance(table_name)

                        created_indexes.append({
                            'table': table_name,
                            'field': field_name,
                            'index_name': index_name,
                            'index_type': index_type,
                            'queries': total_queries,
                            'build_cost': build_cost,
                            'confidence': confidence,
                            'field_selectivity': field_selectivity,
                            'improvement_pct': improvement_pct if after_perf else None,
                            'write_overhead_estimate': write_stats.get('estimated_write_overhead', 0)
                        })
                        print(f"Created index {index_name} on {table_name}.{field_name} "
                              f"(type: {index_type}, queries: {total_queries}, "
                              f"build_cost: {build_cost:.2f}, confidence: {confidence:.2f}, "
                              f"{f'improvement: {improvement_pct:.1f}%, ' if after_perf else ''}"
                              f"write overhead: {write_stats.get('estimated_write_overhead', 0)*100:.1f}%)")
                    except (IndexCreationError, Exception) as e:
                        logger.error(f"Failed to create index {index_name}: {e}")
                        monitoring = get_monitoring()
                        monitoring.alert('warning', f'Failed to create index {index_name}: {e}')
                        skipped_indexes.append({
                            'table': table_name,
                            'field': field_name,
                            'queries': total_queries,
                            'reason': f'creation_failed: {str(e)}'
                        })
                else:
                    skipped_indexes.append({
                        'table': table_name,
                        'field': field_name,
                        'queries': total_queries,
                        'reason': reason,
                        'build_cost': build_cost,
                        'query_cost': query_cost_without_index,
                        'confidence': confidence,
                        'field_selectivity': field_selectivity
                    })

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    return {
        'created': created_indexes,
        'skipped': skipped_indexes
    }


if __name__ == '__main__':
    results = analyze_and_create_indexes()
    print("\nIndex creation summary:")
    print(f"  Created: {len(results['created'])}")
    print(f"  Skipped: {len(results['skipped'])}")

