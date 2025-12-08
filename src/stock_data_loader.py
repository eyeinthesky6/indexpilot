"""Stock market data loader for IndexPilot real-data simulation

Loads CSV stock market data into database, splitting into initial load (50%)
and live update queue (50%) for realistic simulation.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path

from psycopg2.extras import RealDictCursor

from src.db import get_connection
from src.type_definitions import JSONDict, JSONValue

logger = logging.getLogger(__name__)


def parse_csv_file(filepath: Path) -> list[JSONDict]:
    """
    Parse a stock market CSV file.

    Args:
        filepath: Path to CSV file

    Returns:
        List of parsed rows with normalized data
    """
    rows = []
    try:
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalize timestamp
                timestamp_str = row.get("timestamp", "").strip()
                if not timestamp_str:
                    continue

                # Handle different timestamp formats
                try:
                    # Try parsing with timezone
                    if "+" in timestamp_str or timestamp_str.endswith("+05:30"):
                        timestamp = datetime.strptime(
                            timestamp_str.replace("+05:30", ""), "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S%z")
                    except ValueError:
                        logger.warning(f"Could not parse timestamp: {timestamp_str}, skipping row")
                        continue

                # Parse numeric values
                try:
                    # Convert datetime to ISO format string for JSON compatibility
                    parsed_row: JSONDict = {
                        "timestamp": timestamp.isoformat(),
                        "open": float(row["open"]) if row.get("open") else None,
                        "high": float(row["high"]) if row.get("high") else None,
                        "low": float(row["low"]) if row.get("low") else None,
                        "close": float(row["close"]) if row.get("close") else None,
                        "volume": int(float(row["volume"])) if row.get("volume") else None,
                    }
                    rows.append(parsed_row)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing row in {filepath}: {e}, skipping")
                    continue

    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        raise

    return rows


def extract_symbol_from_filename(filename: str) -> str:
    """
    Extract stock symbol from filename.

    Examples:
        WIPRO_5min_historical_data.csv -> WIPRO
        TCS_1d_historical_data.csv -> TCS
    """
    # Remove extension and extract symbol (before first underscore)
    base = filename.replace("_historical_data.csv", "").replace(".csv", "")
    # Handle timeframes: _1min, _5min, _1d
    for timeframe in ["_1min", "_5min", "_1d"]:
        if base.endswith(timeframe):
            base = base[: -len(timeframe)]
            break
    return base


def get_or_create_stock(cursor: RealDictCursor, symbol: str, name: str | None = None) -> int:
    """
    Get or create a stock record.

    Args:
        cursor: Database cursor
        symbol: Stock symbol
        name: Stock name (optional)

    Returns:
        Stock ID
    """
    # Try to get existing stock
    cursor.execute("SELECT id FROM stocks WHERE symbol = %s", (symbol,))
    result = cursor.fetchone()
    if result:
        stock_id = result.get("id")
        if isinstance(stock_id, int):
            return stock_id
        # Type narrowing: convert to int if needed
        if isinstance(stock_id, str | float):
            return int(stock_id)
        raise ValueError(f"Invalid stock ID type: {type(stock_id)}")

    # Create new stock
    cursor.execute(
        "INSERT INTO stocks (symbol, name) VALUES (%s, %s) RETURNING id",
        (symbol, name or symbol),
    )
    result = cursor.fetchone()
    if not result:
        raise ValueError(f"Failed to create stock {symbol}")
    stock_id = result.get("id")
    if isinstance(stock_id, int):
        return stock_id
    # Type narrowing: convert to int if needed
    if isinstance(stock_id, str | float):
        return int(stock_id)
    raise ValueError(f"Invalid stock ID type: {type(stock_id)}")


def load_stock_data(
    data_dir: str | Path = "data/backtesting",
    timeframe: str = "5min",
    mode: str = "initial",
    stocks: list[str] | None = None,
    batch_size: int = 1000,
) -> JSONDict:
    """
    Load stock market data from CSV files.

    Args:
        data_dir: Directory containing CSV files
        timeframe: Timeframe to load (1min, 5min, 1d)
        mode: Load mode - "initial" (first 50%) or "live" (second 50%)
        stocks: List of stock symbols to load (None = all)
        batch_size: Batch size for inserts

    Returns:
        Dictionary with load statistics
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise ValueError(f"Data directory does not exist: {data_dir}")

    # Find matching CSV files
    pattern = f"*_{timeframe}_historical_data.csv"
    csv_files = list(data_path.glob(pattern))

    if not csv_files:
        raise ValueError(f"No CSV files found matching pattern: {pattern}")

    # Filter by stocks if specified
    if stocks:
        stock_set = {s.upper() for s in stocks}
        csv_files = [
            f for f in csv_files if extract_symbol_from_filename(f.name).upper() in stock_set
        ]

    logger.info(f"Found {len(csv_files)} CSV files for timeframe {timeframe}")

    total_rows_loaded = 0
    total_rows_queued = 0
    stocks_processed = []

    with get_connection() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            for csv_file in csv_files:
                symbol = extract_symbol_from_filename(csv_file.name)
                logger.info(f"Processing {symbol} from {csv_file.name}...")

                # Parse CSV
                rows = parse_csv_file(csv_file)
                if not rows:
                    logger.warning(f"No rows parsed from {csv_file.name}")
                    continue

                # Sort by timestamp (convert to string for comparison if needed)
                rows.sort(key=lambda x: str(x.get("timestamp", "")))

                # Split at midpoint (50/50)
                midpoint = len(rows) // 2

                if mode == "initial":
                    # Load first 50%
                    rows_to_load = rows[:midpoint]
                    rows_to_queue = rows[midpoint:]
                else:  # mode == "live"
                    # Load second 50% (for live updates simulation)
                    rows_to_load = rows[midpoint:]
                    rows_to_queue = []

                if not rows_to_load:
                    logger.warning(f"No rows to load for {symbol} in mode {mode}")
                    continue

                # Get or create stock
                stock_id = get_or_create_stock(cursor, symbol)

                # Batch insert
                insert_data = []
                for row in rows_to_load:
                    insert_data.append(
                        (
                            stock_id,
                            row["timestamp"],
                            row["open"],
                            row["high"],
                            row["low"],
                            row["close"],
                            row["volume"],
                        )
                    )

                # Bulk insert
                cursor.executemany(
                    """
                    INSERT INTO stock_prices
                    (stock_id, timestamp, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    insert_data,
                )

                rows_loaded = len(insert_data)
                total_rows_loaded += rows_loaded
                total_rows_queued += len(rows_to_queue)

                stocks_processed.append(
                    {
                        "symbol": symbol,
                        "rows_loaded": rows_loaded,
                        "rows_queued": len(rows_to_queue),
                        "total_rows": len(rows),
                    }
                )

                logger.info(
                    f"Loaded {rows_loaded} rows for {symbol} "
                    f"({len(rows_to_queue)} queued for live updates)"
                )

            conn.commit()
            logger.info(
                f"Data load complete: {total_rows_loaded} rows loaded, "
                f"{total_rows_queued} rows queued for live updates"
            )

        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    # Convert stocks_processed to JSON-compatible format
    from typing import cast

    from src.type_definitions import JSONDict as JSONDictType

    stocks_list: list[JSONDictType] = []
    for stock in stocks_processed:
        if isinstance(stock, dict):
            rows_loaded_val = stock.get("rows_loaded", 0)
            # Type narrowing: ensure rows_loaded is a number
            if isinstance(rows_loaded_val, int | float):
                rows_loaded = int(rows_loaded_val)
            elif isinstance(rows_loaded_val, str):
                try:
                    rows_loaded = int(rows_loaded_val)
                except ValueError:
                    rows_loaded = 0
            else:
                rows_loaded = 0
            stock_dict: JSONDictType = {
                "symbol": str(stock.get("symbol", "")),
                "rows_loaded": rows_loaded,
            }
            stocks_list.append(stock_dict)

    # Cast to JSONValue since list[JSONDict] is compatible with list[JSONValue]
    stocks_json: list[JSONValue] = cast(list[JSONValue], stocks_list)

    return {
        "mode": mode,
        "timeframe": timeframe,
        "stocks_processed": len(stocks_processed),
        "total_rows_loaded": total_rows_loaded,
        "total_rows_queued": total_rows_queued,
        "stocks": stocks_json,
    }


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Load stock market data into database")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/backtesting",
        help="Directory containing CSV files",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="5min",
        choices=["1min", "5min", "1d"],
        help="Timeframe to load",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="initial",
        choices=["initial", "live"],
        help="Load mode: initial (first 50%) or live (second 50%)",
    )
    parser.add_argument(
        "--stocks",
        type=str,
        help="Comma-separated list of stock symbols to load (default: all)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for inserts",
    )

    args = parser.parse_args()

    stocks_list = None
    if args.stocks:
        stocks_list = [s.strip().upper() for s in args.stocks.split(",")]

    result = load_stock_data(
        data_dir=args.data_dir,
        timeframe=args.timeframe,
        mode=args.mode,
        stocks=stocks_list,
        batch_size=args.batch_size,
    )

    print("\nLoad Summary:")
    print(f"  Mode: {result['mode']}")
    print(f"  Timeframe: {result['timeframe']}")
    print(f"  Stocks processed: {result['stocks_processed']}")
    print(f"  Total rows loaded: {result['total_rows_loaded']}")
    print(f"  Total rows queued: {result['total_rows_queued']}")
