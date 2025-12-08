"""Stock market simulation functions for real-data mode

Generates realistic stock market queries based on real data patterns.
"""

import logging
import random
import time
from datetime import datetime, timedelta

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.stats import log_query_stat

logger = logging.getLogger(__name__)


def run_stock_time_range_query(stock_id: int, days_back: int = 7) -> float:
    """
    Simulate time-range query: Get prices for last N days.

    Args:
        stock_id: Stock ID
        days_back: Number of days to look back

    Returns:
        Query duration in milliseconds
    """
    start_time = time.time()
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days_back)

                cursor.execute(
                    """
                    SELECT timestamp, open, high, low, close, volume
                    FROM stock_prices
                    WHERE stock_id = %s AND timestamp BETWEEN %s AND %s
                    ORDER BY timestamp ASC
                """,
                    (stock_id, start_date, end_date),
                )
                results = cursor.fetchall()
                duration_ms = (time.time() - start_time) * 1000

                # Log query stat
                log_query_stat(
                    tenant_id=None,  # Stock data is not tenant-based
                    table_name="stock_prices",
                    field_name="timestamp",
                    query_type="READ",
                    duration_ms=duration_ms,
                )

                return duration_ms
            finally:
                cursor.close()
    except Exception as e:
        logger.warning(f"Stock time-range query failed: {e}")
        return (time.time() - start_time) * 1000


def run_stock_aggregation_query(stock_ids: list[int] | None = None) -> float:
    """
    Simulate aggregation query: Average volume, max high, min low by stock.

    Args:
        stock_ids: List of stock IDs (None = all stocks)

    Returns:
        Query duration in milliseconds
    """
    start_time = time.time()
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if stock_ids:
                    placeholders = ",".join(["%s"] * len(stock_ids))
                    query = f"""
                        SELECT 
                            stock_id,
                            AVG(volume) as avg_volume,
                            MAX(high) as max_high,
                            MIN(low) as min_low,
                            COUNT(*) as price_count
                        FROM stock_prices
                        WHERE timestamp >= NOW() - INTERVAL '7 days'
                            AND stock_id IN ({placeholders})
                        GROUP BY stock_id
                    """
                    cursor.execute(query, stock_ids)
                else:
                    cursor.execute(
                        """
                        SELECT 
                            stock_id,
                            AVG(volume) as avg_volume,
                            MAX(high) as max_high,
                            MIN(low) as min_low,
                            COUNT(*) as price_count
                        FROM stock_prices
                        WHERE timestamp >= NOW() - INTERVAL '7 days'
                        GROUP BY stock_id
                    """
                    )
                results = cursor.fetchall()
                duration_ms = (time.time() - start_time) * 1000

                # Log query stat
                log_query_stat(
                    tenant_id=None,
                    table_name="stock_prices",
                    field_name="volume",
                    query_type="READ",
                    duration_ms=duration_ms,
                )

                return duration_ms
            finally:
                cursor.close()
    except Exception as e:
        logger.warning(f"Stock aggregation query failed: {e}")
        return (time.time() - start_time) * 1000


def run_stock_price_filter_query(min_price: float, min_volume: int) -> float:
    """
    Simulate price filtering query: Stocks with close > X and volume > Y.

    Args:
        min_price: Minimum close price
        min_volume: Minimum volume

    Returns:
        Query duration in milliseconds
    """
    start_time = time.time()
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cursor.execute(
                    """
                    SELECT sp.*, s.symbol, s.name
                    FROM stock_prices sp
                    JOIN stocks s ON s.id = sp.stock_id
                    WHERE sp.close > %s AND sp.volume > %s
                    ORDER BY sp.timestamp DESC
                    LIMIT 100
                """,
                    (min_price, min_volume),
                )
                results = cursor.fetchall()
                duration_ms = (time.time() - start_time) * 1000

                # Log query stat
                log_query_stat(
                    tenant_id=None,
                    table_name="stock_prices",
                    field_name="close",
                    query_type="READ",
                    duration_ms=duration_ms,
                )

                return duration_ms
            finally:
                cursor.close()
    except Exception as e:
        logger.warning(f"Stock price filter query failed: {e}")
        return (time.time() - start_time) * 1000


def run_stock_comparison_query(symbols: list[str]) -> float:
    """
    Simulate multi-stock comparison query.

    Args:
        symbols: List of stock symbols to compare

    Returns:
        Query duration in milliseconds
    """
    start_time = time.time()
    try:
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                placeholders = ",".join(["%s"] * len(symbols))
                query = f"""
                    SELECT s.symbol, sp.timestamp, sp.close, sp.volume
                    FROM stock_prices sp
                    JOIN stocks s ON s.id = sp.stock_id
                    WHERE s.symbol IN ({placeholders})
                        AND sp.timestamp >= NOW() - INTERVAL '1 day'
                    ORDER BY s.symbol, sp.timestamp DESC
                """
                cursor.execute(query, symbols)
                results = cursor.fetchall()
                duration_ms = (time.time() - start_time) * 1000

                # Log query stat
                log_query_stat(
                    tenant_id=None,
                    table_name="stock_prices",
                    field_name="timestamp",
                    query_type="READ",
                    duration_ms=duration_ms,
                )

                return duration_ms
            finally:
                cursor.close()
    except Exception as e:
        logger.warning(f"Stock comparison query failed: {e}")
        return (time.time() - start_time) * 1000


def get_available_stocks() -> list[dict[str, int]]:
    """
    Get list of available stocks with their IDs.

    Returns:
        List of dicts with 'id' and 'symbol'
    """
    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute("SELECT id, symbol FROM stocks ORDER BY symbol")
            return cursor.fetchall()
        finally:
            cursor.close()


def simulate_stock_workload(
    num_queries: int = 500,
    stock_ids: list[int] | None = None,
    query_pattern: str = "mixed",
) -> list[float]:
    """
    Simulate stock market workload with various query patterns.

    Args:
        num_queries: Number of queries to run
        stock_ids: List of stock IDs to query (None = all)
        query_pattern: Query pattern ('time-range', 'aggregation', 'filter', 'comparison', 'mixed')

    Returns:
        List of query durations in milliseconds
    """
    durations = []

    # Get available stocks if not provided
    if stock_ids is None:
        stocks = get_available_stocks()
        stock_ids = [s["id"] for s in stocks]
        symbols = [s["symbol"] for s in stocks]
    else:
        # Get symbols for comparison queries
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                placeholders = ",".join(["%s"] * len(stock_ids))
                cursor.execute(
                    f"SELECT symbol FROM stocks WHERE id IN ({placeholders})", stock_ids
                )
                symbols = [row["symbol"] for row in cursor.fetchall()]
            finally:
                cursor.close()

    if not stock_ids:
        logger.warning("No stocks available for simulation")
        return []

    query_patterns = {
        "time-range": lambda: run_stock_time_range_query(
            random.choice(stock_ids), days_back=random.randint(1, 30)
        ),
        "aggregation": lambda: run_stock_aggregation_query(
            random.sample(stock_ids, min(5, len(stock_ids))) if len(stock_ids) > 1 else stock_ids
        ),
        "filter": lambda: run_stock_price_filter_query(
            min_price=random.uniform(100, 1000),
            min_volume=random.randint(100000, 1000000),
        ),
        "comparison": lambda: run_stock_comparison_query(
            random.sample(symbols, min(3, len(symbols))) if len(symbols) > 1 else symbols
        ),
    }

    if query_pattern == "mixed":
        patterns = list(query_patterns.keys())
    else:
        patterns = [query_pattern] if query_pattern in query_patterns else ["time-range"]

    print_flush(f"Running {num_queries} stock market queries (pattern: {query_pattern})...")

    for i in range(num_queries):
        if (i + 1) % 50 == 0:
            print_flush(f"  Progress: {i + 1}/{num_queries} queries")

        # Select pattern
        pattern = random.choice(patterns)
        duration = query_patterns[pattern]()
        durations.append(duration)

        # Small delay to simulate realistic query spacing
        time.sleep(0.01)

    avg_duration = sum(durations) / len(durations) if durations else 0
    print_flush(
        f"Stock workload complete: {len(durations)} queries, "
        f"avg duration: {avg_duration:.2f}ms"
    )

    return durations

