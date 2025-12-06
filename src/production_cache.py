"""
Production-grade application cache for query results.

This cache is designed as a fallback for databases that don't have
robust native query plan caching (e.g., SQLite, older MySQL versions).

For PostgreSQL, MySQL 8.0+, and SQL Server, use native database caching instead.

Features:
- LRU eviction policy
- Memory limits
- Thread-safe operations
- Automatic table-based invalidation
- Configurable TTL
- Cache statistics and monitoring
- Production-ready error handling
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Iterable
from src.types import JSONDict, JSONValue, QueryParams

from src.database.type_detector import (
    DATABASE_POSTGRESQL,
    get_database_type,
    get_recommended_cache_strategy,
)

logger = logging.getLogger(__name__)


class ProductionCache:
    """
    Production-grade in-memory cache for query results.

    Features:
    - LRU (Least Recently Used) eviction
    - Memory limit protection
    - Thread-safe operations
    - Table-based invalidation
    - Configurable TTL
    - Cache statistics
    """

    def __init__(
        self,
        default_ttl: int = 300,
        max_size: int = 10000,
        max_memory_mb: int | None = 100,
    ):
        """
        Initialize production cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 5 minutes)
            max_size: Maximum number of cache entries (default: 10,000)
            max_memory_mb: Maximum memory usage in MB (None = no limit)
        """
        # Use OrderedDict for LRU eviction
        self.cache: OrderedDict[str, tuple[JSONValue, float, set[str]]] = OrderedDict()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.max_memory_mb = max_memory_mb
        self.lock = threading.Lock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.invalidations = 0

    def _estimate_entry_size(self, value: JSONValue) -> int:
        """Estimate memory size of cache entry in bytes"""
        try:
            if isinstance(value, (list, tuple)):
                return sum(self._estimate_entry_size(item) for item in value)
            elif isinstance(value, dict):
                return sum(
                    len(str(k)) + self._estimate_entry_size(v)
                    for k, v in value.items()
                )
            elif isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (int, float)):
                return 8
            elif value is None:
                return 0
            else:
                # Handle bool and other JSONValue types not explicitly checked above
                return len(str(value).encode('utf-8'))  # type: ignore[unreachable]
        except Exception:
            # Fallback: estimate based on string representation
            return len(str(value).encode('utf-8'))

    def _get_total_memory_mb(self) -> float:
        """Get total memory usage in MB"""
        total_bytes = 0
        for key, (value, _expiry, _tables) in self.cache.items():
            total_bytes += len(key.encode('utf-8'))  # Key size
            total_bytes += self._estimate_entry_size(value)  # Value size
            total_bytes += 100  # Overhead (expiry, tables, etc.)
        return total_bytes / (1024 * 1024)

    def _evict_if_needed(self):
        """Evict entries if size or memory limits exceeded"""
        evicted = False

        # Check size limit
        while len(self.cache) >= self.max_size:
            # Remove least recently used (first item in OrderedDict)
            if self.cache:
                self.cache.popitem(last=False)
                self.evictions += 1
                evicted = True

        # Check memory limit
        if self.max_memory_mb:
            while self._get_total_memory_mb() > self.max_memory_mb:
                if self.cache:
                    self.cache.popitem(last=False)
                    self.evictions += 1
                    evicted = True
                else:
                    break

        if evicted:
            logger.debug(f"Cache evicted entries (size: {len(self.cache)}, memory: {self._get_total_memory_mb():.2f}MB)")

    def _extract_tables_from_query(self, query: str) -> set[str]:
        """
        Extract table names from SQL query.

        Enhanced parser that handles:
        - FROM/JOIN clauses
        - INSERT/UPDATE/DELETE operations
        - Subqueries (basic)
        - Table aliases

        Args:
            query: SQL query string

        Returns:
            set: Set of table names referenced in the query
        """
        tables: set[str] = set()

        # Normalize query (remove comments, extra whitespace)
        query_normalized = re.sub(r'--.*?\n', ' ', query, flags=re.MULTILINE)
        query_normalized = re.sub(r'/\*.*?\*/', ' ', query_normalized, flags=re.DOTALL)
        query_normalized = ' '.join(query_normalized.split())

        # Patterns to match table names
        patterns = [
            r'\bFROM\s+["\']?(\w+)["\']?',  # FROM table
            r'\bJOIN\s+["\']?(\w+)["\']?',  # JOIN table
            r'\bINTO\s+["\']?(\w+)["\']?',  # INSERT INTO
            r'\bUPDATE\s+["\']?(\w+)["\']?',  # UPDATE
            r'\bTABLE\s+["\']?(\w+)["\']?',  # CREATE TABLE, DROP TABLE
        ]

        for pattern in patterns:
            matches = re.findall(pattern, query_normalized, re.IGNORECASE)
            # Filter out SQL keywords that might be matched
            sql_keywords = {'select', 'where', 'group', 'order', 'having', 'limit', 'offset'}
            tables.update(m for m in matches if m.lower() not in sql_keywords)

        return tables

    def _make_key(self, query: str, params: QueryParams | None = None) -> str:
        """Create cache key from query and params"""
        if params is None:
            params = ()
        # Normalize query (remove extra whitespace)
        query_normalized = ' '.join(query.split())
        key_data = f"{query_normalized}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, query: str, params: QueryParams | None = None) -> JSONValue | None:
        """
        Get cached result if available and not expired.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cached result or None if not found/expired
        """
        if params is None:
            params = ()

        key = self._make_key(query, params)
        current_time = time.time()

        with self.lock:
            if key in self.cache:
                value, expiry, _tables = self.cache[key]
                if current_time < expiry:
                    # Move to end (most recently used)
                    self.cache.move_to_end(key)
                    self.hits += 1
                    return value
                else:
                    # Expired, remove it
                    del self.cache[key]
                    logger.debug(f"Cache entry expired for query: {query[:50]}...")

            self.misses += 1
            return None

    def set(
        self,
        query: str,
        params: QueryParams | None,
        value: JSONValue,
        ttl: int | None = None,
        tables: Iterable[str] | None = None,
    ):
        """
        Cache a query result.

        Args:
            query: SQL query
            params: Query parameters
            value: Result to cache
            ttl: Time-to-live in seconds (uses default if None)
            tables: Optional set of table names (auto-extracted if None)
        """
        if ttl is None:
            ttl = self.default_ttl

        # Extract table names from query if not provided
        if tables is None:
            tables_set = self._extract_tables_from_query(query)
        else:
            # Ensure tables is a set
            tables_set = set(tables) if not isinstance(tables, set) else tables

        key = self._make_key(query, params)
        expiry = time.time() + ttl

        with self.lock:
            # Remove existing entry if present (for LRU update)
            if key in self.cache:
                del self.cache[key]

            # Evict if needed before adding
            self._evict_if_needed()

            # Add new entry (at end = most recently used)
            self.cache[key] = (value, expiry, tables_set)

    def invalidate_table(self, table_name: str):
        """
        Invalidate all cache entries for a specific table.

        Args:
            table_name: Name of the table that was modified
        """
        if not table_name:
            return

        keys_to_remove = []

        with self.lock:
            for key, (_value, _expiry, tables) in self.cache.items():
                if table_name in tables:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                if key in self.cache:
                    del self.cache[key]
                    self.invalidations += 1

        if keys_to_remove:
            logger.debug(f"Invalidated {len(keys_to_remove)} cache entries for table: {table_name}")

    def invalidate_tables(self, table_names: Iterable[str]):
        """Invalidate cache entries for multiple tables"""
        for table_name in table_names:
            self.invalidate_table(table_name)

    def clear(self):
        """Clear all cached entries"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.invalidations = 0

    def get_stats(self) -> JSONDict:
        """Get cache statistics"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0.0
            memory_mb = self._get_total_memory_mb()

            return {
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate_pct': round(hit_rate, 2),
                'size': len(self.cache),
                'max_size': self.max_size,
                'evictions': self.evictions,
                'invalidations': self.invalidations,
                'memory_mb': round(memory_mb, 2),
                'max_memory_mb': self.max_memory_mb,
            }

    def cleanup_expired(self):
        """Remove expired entries (call periodically)"""
        current_time = time.time()
        expired_count = 0

        with self.lock:
            keys_to_remove = [
                key
                for key, (_value, expiry, _tables) in self.cache.items()
                if current_time >= expiry
            ]

            for key in keys_to_remove:
                del self.cache[key]
                expired_count += 1

        if expired_count > 0:
            logger.debug(f"Cleaned up {expired_count} expired cache entries")


# Global cache instance
_global_cache: ProductionCache | None = None
_cache_enabled: bool | None = None


def _should_use_application_cache() -> bool:
    """
    Determine if application cache should be used.

    Returns:
        bool: True if application cache is recommended
    """
    import os
    try:
        database_type = get_database_type()
        strategy = get_recommended_cache_strategy(database_type)

        # Use application cache if:
        # 1. Strategy is 'application' or 'hybrid'
        # 2. Database doesn't have good native caching
        # 3. Explicitly enabled via environment variable
        use_app_cache = os.getenv('USE_APPLICATION_CACHE', '').lower() in ('true', '1', 'yes')

        if strategy in ('application', 'hybrid') or use_app_cache:
            return True

        # PostgreSQL: Use native cache (don't use application cache unless explicitly enabled)
        if database_type == DATABASE_POSTGRESQL:
            return use_app_cache  # Only use if explicitly enabled

        return False
    except Exception as e:
        logger.warning(f"Could not determine cache strategy: {e}, defaulting to application cache")
        return True  # Default to application cache if detection fails


def get_production_cache() -> ProductionCache | None:
    """
    Get production cache instance if enabled.

    Returns:
        ProductionCache instance or None if disabled
    """
    global _global_cache, _cache_enabled
    import os

    if _cache_enabled is None:
        _cache_enabled = _should_use_application_cache()

    if not _cache_enabled:
        return None

    if _global_cache is None:
        default_ttl = int(os.getenv('CACHE_TTL', '300'))
        max_size = int(os.getenv('CACHE_MAX_SIZE', '10000'))
        max_memory_mb = int(os.getenv('CACHE_MAX_MEMORY_MB', '100')) if os.getenv('CACHE_MAX_MEMORY_MB') else None

        _global_cache = ProductionCache(
            default_ttl=default_ttl,
            max_size=max_size,
            max_memory_mb=max_memory_mb
        )
        logger.info(f"Production cache initialized (TTL: {default_ttl}s, Max size: {max_size}, Max memory: {max_memory_mb}MB)")

    return _global_cache


def invalidate_cache_for_table(table_name: str):
    """Invalidate cache for a table after data mutations"""
    cache = get_production_cache()
    if cache:
        cache.invalidate_table(table_name)


def invalidate_cache_for_tables(table_names: set[str]):
    """Invalidate cache for multiple tables"""
    cache = get_production_cache()
    if cache:
        cache.invalidate_tables(table_names)

