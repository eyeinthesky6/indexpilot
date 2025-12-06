"""
Query interception layer for proactive blocking of harmful queries.

This module provides runtime query analysis and blocking before execution,
preventing expensive operations like sequential scans and high-cost queries
from running and impacting database performance.

Optimizations:
- Plan analysis caching to reduce EXPLAIN overhead
- Query signature normalization for better cache hits
- Early exit for simple/known-safe queries
- Whitelist/blacklist support for query patterns
- Per-table threshold configuration
- Metrics collection for monitoring
"""

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict

from psycopg2.extras import RealDictCursor

from src.audit import log_audit_event
from src.config_loader import ConfigLoader
from src.db import get_connection
from src.error_handler import QueryBlockedError
from src.rate_limiter import check_query_rate_limit
from src.type_definitions import JSONDict, JSONValue, QueryParams

logger = logging.getLogger(__name__)

# Load configuration with error handling
try:
    _config_loader = ConfigLoader()
except Exception as e:
    logger.error(f"Failed to initialize ConfigLoader: {e}, using defaults")
    # Create a minimal config loader that will use defaults
    _config_loader = ConfigLoader()

# Global configuration (can be updated at runtime)
# Load from config file with environment variable overrides
def _load_config() -> JSONDict:
    """Load configuration from config file with environment variable overrides"""
    # Environment variables take precedence (for backward compatibility)
    max_query_cost = os.getenv('QUERY_INTERCEPTOR_MAX_COST')
    max_seq_scan_cost = os.getenv('QUERY_INTERCEPTOR_MAX_SEQ_SCAN_COST')
    max_planning_time_ms = os.getenv('QUERY_INTERCEPTOR_MAX_PLANNING_TIME_MS')
    enable_blocking = os.getenv('QUERY_INTERCEPTOR_ENABLE')
    enable_rate_limiting = os.getenv('QUERY_INTERCEPTOR_RATE_LIMITING')
    enable_plan_cache = os.getenv('QUERY_INTERCEPTOR_PLAN_CACHE')
    plan_cache_ttl = os.getenv('QUERY_INTERCEPTOR_PLAN_CACHE_TTL')
    plan_cache_max_size = os.getenv('QUERY_INTERCEPTOR_PLAN_CACHE_SIZE')

    # Helper function to safely parse float from env var
    def safe_float(env_value: str | None, config_path: str, default: float) -> float:
        if env_value:
            try:
                value = float(env_value)
                # Validate range (must be positive)
                if value <= 0:
                    logger.warning(f"Invalid {config_path} from env var: {value}, using default {default}")
                    return default
                return value
            except (ValueError, TypeError):
                logger.warning(f"Invalid {config_path} from env var: {env_value}, using default {default}")
                return default
        return _config_loader.get_float(config_path, default)

    # Helper function to safely parse int from env var
    def safe_int(env_value: str | None, config_path: str, default: int) -> int:
        if env_value:
            try:
                value = int(env_value)
                # Validate range (must be positive)
                if value <= 0:
                    logger.warning(f"Invalid {config_path} from env var: {value}, using default {default}")
                    return default
                return value
            except (ValueError, TypeError):
                logger.warning(f"Invalid {config_path} from env var: {env_value}, using default {default}")
                return default
        return _config_loader.get_int(config_path, default)

    # Load and validate configuration
    config = {
        'max_query_cost': safe_float(max_query_cost, 'features.query_interceptor.max_query_cost', 10000.0),
        'max_seq_scan_cost': safe_float(max_seq_scan_cost, 'features.query_interceptor.max_seq_scan_cost', 1000.0),
        'max_planning_time_ms': safe_float(max_planning_time_ms, 'features.query_interceptor.max_planning_time_ms', 100.0),
        'enable_blocking': enable_blocking.lower() in ('true', '1', 'yes') if enable_blocking else _config_loader.get_bool('features.query_interceptor.enable_blocking', True),
        'enable_rate_limiting': enable_rate_limiting.lower() in ('true', '1', 'yes') if enable_rate_limiting else _config_loader.get_bool('features.query_interceptor.enable_rate_limiting', True),
        'enable_plan_cache': enable_plan_cache.lower() in ('true', '1', 'yes') if enable_plan_cache else _config_loader.get_bool('features.query_interceptor.enable_plan_cache', True),
        'plan_cache_ttl': safe_int(plan_cache_ttl, 'features.query_interceptor.plan_cache_ttl', 300),
        'plan_cache_max_size': safe_int(plan_cache_max_size, 'features.query_interceptor.plan_cache_max_size', 1000),
        'query_preview_length': _config_loader.get_int('features.query_interceptor.query_preview_length', 200),
        'safety_score_unsafe_threshold': _config_loader.get_float('features.query_interceptor.safety_score_unsafe_threshold', 0.3),
        'safety_score_warning_threshold': _config_loader.get_float('features.query_interceptor.safety_score_warning_threshold', 0.7),
        'safety_score_high_cost_penalty': _config_loader.get_float('features.query_interceptor.safety_score_high_cost_penalty', 0.5),
        'safety_score_seq_scan_penalty': _config_loader.get_float('features.query_interceptor.safety_score_seq_scan_penalty', 0.7),
        'safety_score_nested_loop_penalty': _config_loader.get_float('features.query_interceptor.safety_score_nested_loop_penalty', 0.8),
    }

    # Validate logical constraints
    if config['safety_score_unsafe_threshold'] >= config['safety_score_warning_threshold']:
        logger.warning(
            f"Invalid safety score thresholds: unsafe ({config['safety_score_unsafe_threshold']}) >= warning "
            f"({config['safety_score_warning_threshold']}), adjusting"
        )
        config['safety_score_unsafe_threshold'] = min(0.3, config['safety_score_warning_threshold'] - 0.1)

    # Validate penalty factors are in reasonable range (0.0 to 1.0)
    for penalty_key in ['safety_score_high_cost_penalty', 'safety_score_seq_scan_penalty', 'safety_score_nested_loop_penalty']:
        if not (0.0 <= config[penalty_key] <= 1.0):
            logger.warning(f"Invalid {penalty_key}: {config[penalty_key]}, clamping to [0.0, 1.0]")
            config[penalty_key] = max(0.0, min(1.0, config[penalty_key]))

    # Convert to JSONDict (float, int, bool are all JSONValue)
    return config  # type: ignore[return-value]

_config = _load_config()

# Helper functions to safely extract typed values from config
def _get_config_int(key: str, default: int) -> int:
    """Safely extract int value from config"""
    value = _config.get(key, default)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default

def _get_config_float(key: str, default: float) -> float:
    """Safely extract float value from config"""
    value = _config.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    return default

def _get_config_bool(key: str, default: bool) -> bool:
    """Safely extract bool value from config"""
    value = _config.get(key, default)
    if isinstance(value, bool):
        return value
    return default

def _get_float_from_dict(d: dict[str, JSONValue] | dict[str, float], key: str, default: float) -> float:
    """Safely extract float value from dict"""
    value = d.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    return default

def _get_bool_from_dict(d: dict[str, JSONValue], key: str, default: bool) -> bool:
    """Safely extract bool value from dict"""
    value = d.get(key, default)
    if isinstance(value, bool):
        return value
    return default

def _get_str_from_dict(d: dict[str, JSONValue], key: str, default: str) -> str:
    """Safely extract str value from dict"""
    value = d.get(key, default)
    if isinstance(value, str):
        return value
    return default

# Plan analysis cache (LRU with TTL)
_plan_cache: OrderedDict[str, tuple[JSONDict, float]] = OrderedDict()
_plan_cache_lock = threading.Lock()
_plan_cache_stats: dict[str, int] = {
    'hits': 0,
    'misses': 0,
    'evictions': 0,
}

# Query whitelist/blacklist (query pattern -> action)
_query_whitelist: set[str] = set()  # Patterns that always pass
_query_blacklist: set[str] = set()  # Patterns that always block
_query_list_lock = threading.Lock()

# Per-table thresholds (table_name -> thresholds dict)
_per_table_thresholds: dict[str, dict[str, JSONValue]] = {}
_per_table_lock = threading.Lock()

# Interception metrics
_interception_metrics: JSONDict = {
    'total_interceptions': 0,
    'total_blocked': 0,
    'total_analyzed': 0,
    'total_cache_hits': 0,
    'total_cache_misses': 0,
    'total_analysis_time_ms': 0.0,
    'blocked_by_reason': {},
}
_metrics_lock = threading.Lock()




def configure_interceptor(
    max_query_cost: float | None = None,
    max_seq_scan_cost: float | None = None,
    max_planning_time_ms: float | None = None,
    enable_blocking: bool | None = None,
    enable_rate_limiting: bool | None = None,
):
    """
    Configure query interceptor thresholds and behavior.

    Args:
        max_query_cost: Maximum allowed query cost (None = use default)
        max_seq_scan_cost: Maximum allowed cost for sequential scans (None = use default)
        max_planning_time_ms: Maximum allowed planning time in ms (None = use default)
        enable_blocking: Enable/disable query blocking (None = use default)
        enable_rate_limiting: Enable/disable rate limiting check (None = use default)
    """
    if max_query_cost is not None:
        _config['max_query_cost'] = max_query_cost
    if max_seq_scan_cost is not None:
        _config['max_seq_scan_cost'] = max_seq_scan_cost
    if max_planning_time_ms is not None:
        _config['max_planning_time_ms'] = max_planning_time_ms
    if enable_blocking is not None:
        _config['enable_blocking'] = enable_blocking
    if enable_rate_limiting is not None:
        _config['enable_rate_limiting'] = enable_rate_limiting

    logger.info(f"Query interceptor configured: {_config}")


def _normalize_query_signature(query: str, params: QueryParams | None = None) -> str:
    """
    Create a normalized query signature for caching.

    Normalizes:
    - Whitespace (multiple spaces -> single space)
    - Parameter placeholders (%s -> ?)
    - Case-insensitive keywords
    - Removes comments

    Args:
        query: SQL query string
        params: Query parameters

    Returns:
        Normalized query signature string
    """
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', query.strip())

    # Normalize parameter placeholders
    normalized = re.sub(r'%s|\$\d+', '?', normalized)

    # Remove comments
    normalized = re.sub(r'--.*?$', '', normalized, flags=re.MULTILINE)
    normalized = re.sub(r'/\*.*?\*/', '', normalized, flags=re.DOTALL)

    # Normalize case for SQL keywords (optional - can be disabled if case matters)
    # normalized = re.sub(r'\b(SELECT|FROM|WHERE|JOIN|INNER|OUTER|LEFT|RIGHT|ON|AND|OR|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET)\b', lambda m: m.group(1).upper(), normalized, flags=re.IGNORECASE)

    # Add params hash if provided (for queries with different params but same structure)
    if params:
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        normalized = f"{normalized}|params:{params_hash}"

    return normalized


def _get_plan_cache_key(query: str, params: QueryParams | None = None) -> str:
    """Get cache key for plan analysis."""
    signature = _normalize_query_signature(query, params)
    return hashlib.md5(signature.encode()).hexdigest()


def _cleanup_plan_cache():
    """Remove expired entries from plan cache."""
    current_time = time.time()
    with _plan_cache_lock:
        expired_keys = [
            key for key, (_, expiry) in _plan_cache.items()
            if current_time >= expiry
        ]
        for key in expired_keys:
            del _plan_cache[key]
            _plan_cache_stats['evictions'] += 1


def get_interceptor_config() -> dict[str, JSONValue]:
    """Get current interceptor configuration."""
    return _config.copy()


def get_interceptor_metrics() -> JSONDict:
    """Get interception metrics for monitoring."""
    with _metrics_lock:
        hits: int = _plan_cache_stats['hits']
        misses: int = _plan_cache_stats['misses']
        total_cache_ops: int = hits + misses

        with _plan_cache_lock:
            cache_hit_rate: float = (
                float(hits) / float(total_cache_ops)
                if total_cache_ops > 0
                else 0.0
            )

        total_analyzed_val = _interception_metrics.get('total_analyzed', 0)
        total_analyzed: int = total_analyzed_val if isinstance(total_analyzed_val, int) else 0
        total_analysis_time_val = _interception_metrics.get('total_analysis_time_ms', 0.0)
        total_analysis_time: float = total_analysis_time_val if isinstance(total_analysis_time_val, (int, float)) else 0.0
        avg_analysis_time: float = (
            total_analysis_time / float(total_analyzed)
            if total_analyzed > 0
            else 0.0
        )

        total_interceptions_val = _interception_metrics.get('total_interceptions', 0)
        total_interceptions: int = total_interceptions_val if isinstance(total_interceptions_val, int) else 0
        total_blocked_val = _interception_metrics.get('total_blocked', 0)
        total_blocked: int = total_blocked_val if isinstance(total_blocked_val, int) else 0
        block_rate: float = (
            float(total_blocked) / float(total_interceptions)
            if total_interceptions > 0
            else 0.0
        )

        blocked_by_reason_val = _interception_metrics.get('blocked_by_reason', {})
        blocked_by_reason: dict[str, int] = {}
        if isinstance(blocked_by_reason_val, dict):
            for k, v in blocked_by_reason_val.items():
                if isinstance(k, str) and isinstance(v, int):
                    blocked_by_reason[k] = v

        return {
            'total_interceptions': total_interceptions,
            'total_blocked': total_blocked,
            'total_analyzed': total_analyzed,
            'block_rate': block_rate,
            'cache_hits': _interception_metrics.get('total_cache_hits', 0) if isinstance(_interception_metrics.get('total_cache_hits', 0), int) else 0,
            'cache_misses': _interception_metrics.get('total_cache_misses', 0) if isinstance(_interception_metrics.get('total_cache_misses', 0), int) else 0,
            'cache_hit_rate': cache_hit_rate,
            'avg_analysis_time_ms': avg_analysis_time,
            'blocked_by_reason': dict(blocked_by_reason),
            'plan_cache_size': len(_plan_cache),
        }


def add_query_to_whitelist(pattern: str):
    """Add a query pattern to whitelist (always allow)."""
    with _query_list_lock:
        _query_whitelist.add(pattern.lower())


def add_query_to_blacklist(pattern: str):
    """Add a query pattern to blacklist (always block)."""
    with _query_list_lock:
        _query_blacklist.add(pattern.lower())


def remove_query_from_whitelist(pattern: str):
    """Remove a query pattern from whitelist."""
    with _query_list_lock:
        _query_whitelist.discard(pattern.lower())


def remove_query_from_blacklist(pattern: str):
    """Remove a query pattern from blacklist."""
    with _query_list_lock:
        _query_blacklist.discard(pattern.lower())


def set_per_table_thresholds(table_name: str, thresholds: dict[str, JSONValue]):
    """
    Set per-table blocking thresholds.

    Args:
        table_name: Table name
        thresholds: Dict with keys: max_query_cost, max_seq_scan_cost
    """
    with _per_table_lock:
        _per_table_thresholds[table_name] = thresholds.copy()


def get_per_table_thresholds(table_name: str) -> dict[str, float] | None:
    """Get per-table thresholds if configured."""
    with _per_table_lock:
        thresholds = _per_table_thresholds.get(table_name)
        if thresholds:
            # Convert dict[str, JSONValue] to dict[str, float]
            result: dict[str, float] = {}
            for k, v in thresholds.items():
                if isinstance(v, (int, float)):
                    result[k] = float(v)
            return result
        return None


def _extract_table_name(query: str) -> str | None:
    """Extract primary table name from query (simple heuristic)."""
    # Simple extraction - looks for FROM table_name
    match = re.search(r'\bFROM\s+["\']?(\w+)["\']?', query, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _check_query_lists(query: str) -> tuple[bool, str] | None:
    """
    Check if query matches whitelist or blacklist.

    Returns:
        (True, 'WHITELISTED') if whitelisted
        (True, 'BLACKLISTED') if blacklisted
        None if not in any list
    """
    query_lower = query.lower()
    with _query_list_lock:
        # Check blacklist first (more restrictive)
        for pattern in _query_blacklist:
            if pattern in query_lower or re.search(pattern, query_lower, re.IGNORECASE):
                return True, 'BLACKLISTED'

        # Check whitelist
        for pattern in _query_whitelist:
            if pattern in query_lower or re.search(pattern, query_lower, re.IGNORECASE):
                return False, 'WHITELISTED'

    return None


def analyze_query_plan_fast(query: str, params: QueryParams | None = None) -> JSONDict | None:
    """
    Fast query plan analysis using EXPLAIN (without ANALYZE).

    This is faster than EXPLAIN ANALYZE because it doesn't execute the query,
    making it suitable for proactive blocking before execution.

    Uses caching to avoid re-analyzing the same queries.

    Args:
        query: SQL query string
        params: Query parameters

    Returns:
        dict with plan analysis or None if analysis fails
    """
    if params is None:
        params = ()

    # Check cache if enabled
    if _config['enable_plan_cache']:
        cache_key = _get_plan_cache_key(query, params)
        current_time = time.time()

        with _plan_cache_lock:
            if cache_key in _plan_cache:
                cached_analysis, expiry = _plan_cache[cache_key]
                if current_time < expiry:
                    # Cache hit - move to end (LRU)
                    _plan_cache.move_to_end(cache_key)
                    _plan_cache_stats['hits'] += 1
                    with _metrics_lock:
                        current_hits = _interception_metrics.get('total_cache_hits', 0)
                        if isinstance(current_hits, int):
                            _interception_metrics['total_cache_hits'] = current_hits + 1
                        else:
                            _interception_metrics['total_cache_hits'] = 1
                    return cached_analysis.copy()  # Return copy to prevent mutation
                else:
                    # Expired - remove it
                    del _plan_cache[cache_key]
                    _plan_cache_stats['evictions'] += 1

        # Cleanup expired entries periodically (every 100 cache operations)
        cache_max_size = _get_config_int('plan_cache_max_size', 1000)
        if len(_plan_cache) > cache_max_size * 0.9:
            _cleanup_plan_cache()

    # Cache miss or cache disabled - analyze query
    start_time = time.time()
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                # Use EXPLAIN without ANALYZE for speed (doesn't execute query)
                explain_query = f"EXPLAIN (FORMAT JSON) {query}"
                cursor.execute(explain_query, params)
                result = cursor.fetchone()

                if not result or not result[0]:
                    return None

                plan_data = result[0]
                plan = json.loads(plan_data) if isinstance(plan_data, str) else plan_data

                # Extract plan information
                if not plan or len(plan) == 0 or 'Plan' not in plan[0]:
                    return None
                plan_node = plan[0]['Plan']

                # Extract values with type safety
                total_cost_val = plan_node.get('Total Cost')
                total_cost_float = float(total_cost_val) if isinstance(total_cost_val, (int, float)) else 0.0
                node_type_val = plan_node.get('Node Type')
                node_type_str = str(node_type_val) if node_type_val is not None else 'Unknown'
                estimated_rows_val = plan_node.get('Plan Rows')
                estimated_rows_int = int(estimated_rows_val) if isinstance(estimated_rows_val, (int, float)) else 0

                # Ensure plan_node is dict[str, JSONValue] for function calls
                plan_node_dict: dict[str, JSONValue] = plan_node if isinstance(plan_node, dict) else {}

                analysis: JSONDict = {
                    'total_cost': total_cost_float,
                    'planning_time_ms': 0,  # Not available without ANALYZE
                    'node_type': node_type_str,
                    'has_seq_scan': _has_sequential_scan(plan_node_dict),
                    'has_index_scan': _has_index_scan(plan_node_dict),
                    'has_nested_loop': _has_nested_loop(plan_node_dict),
                    'estimated_rows': estimated_rows_int,
                    'recommendations': []
                }

                # Add recommendations
                has_seq_scan_val = _get_bool_from_dict(analysis, 'has_seq_scan', False)
                has_nested_loop_val = _get_bool_from_dict(analysis, 'has_nested_loop', False)
                total_cost_for_msg = _get_float_from_dict(analysis, 'total_cost', 0.0)
                
                if has_seq_scan_val:
                    recommendations_val = analysis.get('recommendations', [])
                    if isinstance(recommendations_val, list):
                        recommendations_val.append(
                            f"Sequential scan detected (cost: {total_cost_for_msg:.2f}). "
                        "Consider creating an index on filtered columns."
                    )
                        analysis['recommendations'] = recommendations_val

                if has_nested_loop_val:
                    recommendations_val2 = analysis.get('recommendations', [])
                    if isinstance(recommendations_val2, list):
                        recommendations_val2.append(
                        "Nested loop join detected. Consider indexes on join columns."
                    )
                        analysis['recommendations'] = recommendations_val2

                # Cache result if enabled
                if _get_config_bool('enable_plan_cache', True):
                    cache_ttl = _get_config_int('plan_cache_ttl', 300)
                    cache_max_size = _get_config_int('plan_cache_max_size', 1000)
                    expiry = current_time + cache_ttl
                    with _plan_cache_lock:
                        # Evict oldest if at max size
                        if len(_plan_cache) >= cache_max_size:
                            _plan_cache.popitem(last=False)  # Remove oldest (LRU)
                            _plan_cache_stats['evictions'] += 1
                        _plan_cache[cache_key] = (analysis.copy(), expiry)

                    _plan_cache_stats['misses'] += 1
                    with _metrics_lock:
                        current_misses = _interception_metrics.get('total_cache_misses', 0)
                        if isinstance(current_misses, int):
                            _interception_metrics['total_cache_misses'] = current_misses + 1
                        else:
                            _interception_metrics['total_cache_misses'] = 1

                # Update metrics
                analysis_time = (time.time() - start_time) * 1000
                with _metrics_lock:
                    current_analyzed = _interception_metrics.get('total_analyzed', 0)
                    if isinstance(current_analyzed, int):
                        _interception_metrics['total_analyzed'] = current_analyzed + 1
                    else:
                        _interception_metrics['total_analyzed'] = 1
                    current_time_ms = _interception_metrics.get('total_analysis_time_ms', 0.0)
                    if isinstance(current_time_ms, (int, float)):
                        _interception_metrics['total_analysis_time_ms'] = current_time_ms + analysis_time
                    else:
                        _interception_metrics['total_analysis_time_ms'] = analysis_time

                return analysis
            except Exception as e:
                # If EXPLAIN fails, query might be invalid or unsupported
                logger.debug(f"Query plan analysis failed: {e}")
                return None
            finally:
                cursor.close()
    except Exception as e:
        logger.debug(f"Connection error during plan analysis: {e}")
        return None


def _has_sequential_scan(plan_node: dict[str, JSONValue]) -> bool:
    """Recursively check if plan contains sequential scan."""
    if plan_node.get('Node Type') == 'Seq Scan':
        return True

    # Check child plans
    plans_val = plan_node.get('Plans')
    if plans_val and isinstance(plans_val, list):
        for child in plans_val:
            if isinstance(child, dict):
                child_dict: dict[str, JSONValue] = child
                if _has_sequential_scan(child_dict):
                    return True

    return False


def _has_index_scan(plan_node: dict[str, JSONValue]) -> bool:
    """Recursively check if plan uses index scan."""
    node_type_val = plan_node.get('Node Type', '')
    node_type = str(node_type_val) if isinstance(node_type_val, str) else (str(node_type_val) if node_type_val is not None else '')
    if isinstance(node_type, str) and ('Index' in node_type or node_type == 'Bitmap Heap Scan'):
        return True

    # Check child plans
    plans_val = plan_node.get('Plans')
    if plans_val and isinstance(plans_val, list):
        for child in plans_val:
            if isinstance(child, dict):
                child_dict: dict[str, JSONValue] = child
                if _has_index_scan(child_dict):
                    return True

    return False


def _has_nested_loop(plan_node: dict[str, JSONValue]) -> bool:
    """Recursively check if plan contains nested loop joins."""
    if plan_node.get('Node Type') == 'Nested Loop':
        return True

    # Check child plans
    plans_val = plan_node.get('Plans')
    if plans_val and isinstance(plans_val, list):
        for child in plans_val:
            if isinstance(child, dict):
                child_dict: dict[str, JSONValue] = child
                if _has_nested_loop(child_dict):
                    return True

    return False


def should_block_query(
    query: str,
    params: QueryParams | None = None,
    tenant_id: str | None = None,
    plan_analysis: JSONDict | None = None,
) -> tuple[bool, str | None, JSONDict]:
    """
    Determine if a query should be blocked before execution.

    Args:
        query: SQL query string
        params: Query parameters
        tenant_id: Tenant ID for rate limiting
        plan_analysis: Pre-computed plan analysis (if available)

    Returns:
        Tuple of (should_block, reason, details)
        - should_block: True if query should be blocked
        - reason: Human-readable reason for blocking (None if not blocked)
        - details: Dictionary with blocking details
    """
    # Check whitelist/blacklist first (fastest check)
    list_check = _check_query_lists(query)
    if list_check is not None:
        should_block, reason = list_check
        return (
            should_block,
            reason,
            {
                'message': f'Query {reason.lower()}',
                'query_preview': query[:200]
            }
        )

    # Check rate limiting (if enabled)
    if _config['enable_rate_limiting']:
        allowed, retry_after = check_query_rate_limit(tenant_id)
        if not allowed:
            return (
                True,
                'RATE_LIMIT_EXCEEDED',
                {
                    'retry_after_seconds': retry_after,
                    'tenant_id': tenant_id,
                    'message': f'Query rate limit exceeded. Retry after {retry_after:.1f} seconds.'
                }
            )

    # If blocking is disabled, only check rate limiting
    if not _get_config_bool('enable_blocking', True):
        return False, None, {}

    # Early exit for simple queries (SELECT with LIMIT, simple WHERE)
    # These are typically safe and don't need analysis
    query_upper = query.strip().upper()
    # Simple SELECT with LIMIT - likely safe
    if (query_upper.startswith('SELECT') and
            re.search(r'\bLIMIT\s+\d+\b', query_upper) and not re.search(r'\bJOIN\b', query_upper)):
        # Very simple query - skip analysis
        return False, None, {'skipped_analysis': True, 'reason': 'simple_query'}

    # Analyze query plan if not provided
    if plan_analysis is None:
        plan_analysis = analyze_query_plan_fast(query, params)

    # If plan analysis fails, allow query (fail open for safety)
    if plan_analysis is None:
        logger.debug("Query plan analysis failed, allowing query")
        return False, None, {}

    # Get per-table thresholds if configured
    table_name = _extract_table_name(query)
    thresholds = get_per_table_thresholds(table_name) if table_name else None

    max_query_cost: float = (
        _get_float_from_dict(thresholds, 'max_query_cost', _get_config_float('max_query_cost', 10000.0))
        if thresholds is not None else _get_config_float('max_query_cost', 10000.0)
    )
    max_seq_scan_cost: float = (
        _get_float_from_dict(thresholds, 'max_seq_scan_cost', _get_config_float('max_seq_scan_cost', 1000.0))
        if thresholds is not None else _get_config_float('max_seq_scan_cost', 1000.0)
    )

    total_cost = _get_float_from_dict(plan_analysis, 'total_cost', 0.0)
    has_seq_scan = _get_bool_from_dict(plan_analysis, 'has_seq_scan', False)
    has_nested_loop = _get_bool_from_dict(plan_analysis, 'has_nested_loop', False)
    node_type = _get_str_from_dict(plan_analysis, 'node_type', 'Unknown')

    details: JSONDict = {
        'total_cost': total_cost,
        'has_seq_scan': has_seq_scan,
        'has_nested_loop': has_nested_loop,
        'node_type': node_type,
        'table_name': table_name,
    }

    # Block if total cost exceeds threshold
    if total_cost > max_query_cost:
        block_details: dict[str, JSONValue] = {
            'total_cost': total_cost,
            'has_seq_scan': has_seq_scan,
            'has_nested_loop': has_nested_loop,
            'node_type': node_type,
            'table_name': table_name,
                'threshold': max_query_cost,
                'message': f'Query cost ({total_cost:.2f}) exceeds maximum allowed ({max_query_cost:.2f})'
            }
        return (
            True,
            'QUERY_COST_TOO_HIGH',
            block_details
        )

    # Block sequential scans with high cost
    if has_seq_scan and total_cost > max_seq_scan_cost:
        seq_scan_details: dict[str, JSONValue] = {
            'total_cost': total_cost,
            'has_seq_scan': has_seq_scan,
            'has_nested_loop': has_nested_loop,
            'node_type': node_type,
            'table_name': table_name,
                'threshold': max_seq_scan_cost,
                'message': f'Sequential scan detected with cost ({total_cost:.2f}) exceeding threshold ({max_seq_scan_cost:.2f})'
            }
        return (
            True,
            'SEQUENTIAL_SCAN_TOO_EXPENSIVE',
            seq_scan_details
        )

    # Note: Planning time check is not available in fast analysis (requires ANALYZE)
    # This would be checked in post-execution analysis if needed

    # Query is safe to execute
    return False, None, details


def intercept_query(
    query: str,
    params: QueryParams | None = None,
    tenant_id: str | None = None,
    skip_interception: bool = False,
) -> None:
    """
    Intercept and potentially block a query before execution.

    This function should be called before executing any query to check
    if it should be blocked. If the query is harmful, it raises QueryBlockedError.

    Args:
        query: SQL query string
        params: Query parameters
        tenant_id: Tenant ID for rate limiting and audit logging
        skip_interception: If True, skip interception (for internal queries)

    Raises:
        QueryBlockedError: If query should be blocked
    """
    if skip_interception:
        return

    # Update metrics
    with _metrics_lock:
        current_interceptions = _interception_metrics.get('total_interceptions', 0)
        if isinstance(current_interceptions, int):
            _interception_metrics['total_interceptions'] = current_interceptions + 1
        else:
            _interception_metrics['total_interceptions'] = 1

    # Check if query should be blocked
    should_block, reason, details = should_block_query(query, params, tenant_id)

    if should_block:
        # Update metrics
        with _metrics_lock:
            current_blocked = _interception_metrics.get('total_blocked', 0)
            if isinstance(current_blocked, int):
                _interception_metrics['total_blocked'] = current_blocked + 1
            else:
                _interception_metrics['total_blocked'] = 1
            blocked_by_reason_dict = _interception_metrics.get('blocked_by_reason', {})
            if isinstance(blocked_by_reason_dict, dict) and reason is not None:
                current_count = blocked_by_reason_dict.get(reason, 0)
                if isinstance(current_count, int):
                    blocked_by_reason_dict[reason] = current_count + 1
                else:
                    blocked_by_reason_dict[reason] = 1
                _interception_metrics['blocked_by_reason'] = blocked_by_reason_dict

        # Log to audit trail
        preview_length = _get_config_int('query_preview_length', 200)
        audit_details: dict[str, JSONValue] = {
            'reason': reason if reason is not None else 'unknown',
            'query_preview': query[:preview_length],  # Configurable preview length
        }
        # Merge details into audit_details
        for k, v in details.items():
            audit_details[k] = v
        log_audit_event(
            'QUERY_BLOCKED',
            tenant_id=int(tenant_id) if tenant_id and tenant_id.isdigit() else None,
            details=audit_details,
            severity='warning'
        )

        # Raise exception to block query
        message_str = _get_str_from_dict(details, 'message', f'Query blocked: {reason}')
        raise QueryBlockedError(
            message=message_str,
            reason=reason,
            details=details
        )


def get_query_safety_score(
    query: str,
    params: QueryParams | None = None,
) -> JSONDict:
    """
    Get a safety score for a query without blocking it.

    This can be used for monitoring or logging purposes.

    Args:
        query: SQL query string
        params: Query parameters

    Returns:
        dict with safety score and analysis
    """
    plan_analysis = analyze_query_plan_fast(query, params)

    if plan_analysis is None:
        return {
            'score': 0.5,  # Unknown - neutral score
            'status': 'UNKNOWN',
            'message': 'Query plan analysis failed',
            'analysis': None
        }

    total_cost = _get_float_from_dict(plan_analysis, 'total_cost', 0.0)
    has_seq_scan = _get_bool_from_dict(plan_analysis, 'has_seq_scan', False)
    has_nested_loop = _get_bool_from_dict(plan_analysis, 'has_nested_loop', False)

    # Calculate safety score (0.0 = very unsafe, 1.0 = very safe)
    score = 1.0

    max_query_cost_val = _get_config_float('max_query_cost', 10000.0)
    max_seq_scan_cost_val = _get_config_float('max_seq_scan_cost', 1000.0)
    high_cost_penalty = _get_config_float('safety_score_high_cost_penalty', 0.5)
    seq_scan_penalty = _get_config_float('safety_score_seq_scan_penalty', 0.7)
    nested_loop_penalty = _get_config_float('safety_score_nested_loop_penalty', 0.8)
    unsafe_threshold = _get_config_float('safety_score_unsafe_threshold', 0.3)
    warning_threshold = _get_config_float('safety_score_warning_threshold', 0.7)

    # Penalize high cost
    if total_cost > max_query_cost_val:
        score = 0.0
    elif total_cost > max_query_cost_val * 0.5:
        score *= high_cost_penalty

    # Penalize sequential scans
    if has_seq_scan:
        if total_cost > max_seq_scan_cost_val:
            score = 0.0
        else:
            score *= seq_scan_penalty

    # Penalize nested loops
    if has_nested_loop:
        score *= nested_loop_penalty

    # Determine status
    if score < unsafe_threshold:
        status = 'UNSAFE'
    elif score < warning_threshold:
        status = 'WARNING'
    else:
        status = 'SAFE'

    return {
        'score': score,
        'status': status,
        'total_cost': total_cost,
        'has_seq_scan': has_seq_scan,
        'has_nested_loop': has_nested_loop,
        'analysis': plan_analysis
    }

