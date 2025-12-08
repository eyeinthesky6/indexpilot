#!/usr/bin/env python3
"""Setup script for stock market data simulation

Initializes database schema, bootstraps genome catalog, and loads stock data.
"""

import sys
from pathlib import Path

from src.schema import init_schema_from_config, load_schema
from src.stock_data_loader import load_stock_data
from src.stock_genome import bootstrap_stock_genome_catalog


def safe_print(text: str) -> None:
    """Print text safely, handling Unicode encoding issues on Windows"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback to ASCII-safe version
        text = text.replace("✓", "[OK]").replace("❌", "[ERROR]")
        print(text)


def setup_stock_schema():
    """Initialize stock market schema from YAML config"""
    print("=" * 80)
    print("STEP 1: Initializing Stock Market Schema")
    print("=" * 80)

    schema_config_path = "schema_config_stock_market.yaml"
    if not Path(schema_config_path).exists():
        print(f"ERROR: Schema config file not found: {schema_config_path}")
        print("Please ensure schema_config_stock_market.yaml exists in project root")
        return False

    try:
        schema_config = load_schema(schema_config_path)
        init_schema_from_config(schema_config)
        safe_print("[OK] Stock market schema initialized successfully")
        return True
    except Exception as e:
        print(f"ERROR: Failed to initialize schema: {e}")
        return False


def setup_stock_genome():
    """Bootstrap stock market genome catalog"""
    print("\n" + "=" * 80)
    print("STEP 2: Bootstrapping Stock Genome Catalog")
    print("=" * 80)

    try:
        bootstrap_stock_genome_catalog()
        safe_print("[OK] Stock genome catalog bootstrapped successfully")
        return True
    except Exception as e:
        print(f"ERROR: Failed to bootstrap genome catalog: {e}")
        return False


def setup_stock_data(
    data_dir: str = "data/backtesting", timeframe: str = "5min", stocks: list[str] | None = None
):
    """Load initial stock data (first 50%)"""
    print("\n" + "=" * 80)
    print("STEP 3: Loading Stock Market Data")
    print("=" * 80)
    print(f"Data directory: {data_dir}")
    print(f"Timeframe: {timeframe}")
    if stocks:
        print(f"Stocks: {', '.join(stocks)}")
    else:
        print("Stocks: All available")

    try:
        result = load_stock_data(
            data_dir=data_dir,
            timeframe=timeframe,
            mode="initial",  # First 50% of data
            stocks=stocks,
        )
        safe_print(
            f"[OK] Loaded {result['total_rows_loaded']} rows from {result['stocks_processed']} stocks"
        )
        return True
    except Exception as e:
        print(f"ERROR: Failed to load stock data: {e}")
        return False


def main():
    """Main setup function"""
    print("\n" + "=" * 80)
    print("IndexPilot Stock Market Data Setup")
    print("=" * 80)
    print("\nThis script will:")
    print("  1. Initialize stock market schema (stocks, stock_prices tables)")
    print("  2. Bootstrap genome catalog for stock fields")
    print("  3. Load initial stock data (first 50% for baseline)")
    print("\nThe remaining 50% can be loaded later for live update simulation.")
    print("=" * 80 + "\n")

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Setup stock market data for IndexPilot")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/backtesting",
        help="Directory containing stock CSV files (default: data/backtesting)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="5min",
        choices=["1min", "5min", "1d"],
        help="Timeframe to load (default: 5min)",
    )
    parser.add_argument(
        "--stocks",
        type=str,
        help="Comma-separated list of stock symbols (e.g., WIPRO,TCS,ITC). If not provided, loads all available stocks.",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip schema initialization (use if schema already exists)",
    )
    parser.add_argument(
        "--skip-genome",
        action="store_true",
        help="Skip genome bootstrapping (use if genome already bootstrapped)",
    )
    parser.add_argument(
        "--skip-data",
        action="store_true",
        help="Skip data loading (use if data already loaded)",
    )

    args = parser.parse_args()

    # Parse stocks list
    stock_list = None
    if args.stocks:
        stock_list = [s.strip().upper() for s in args.stocks.split(",")]

    success = True

    # Step 1: Initialize schema
    if not args.skip_schema:
        success = setup_stock_schema()
        if not success:
            print("\n[ERROR] Setup failed at schema initialization")
            sys.exit(1)
    else:
        print("Skipping schema initialization (--skip-schema)")

    # Step 2: Bootstrap genome
    if not args.skip_genome:
        success = setup_stock_genome()
        if not success:
            print("\n[ERROR] Setup failed at genome bootstrapping")
            sys.exit(1)
    else:
        print("Skipping genome bootstrapping (--skip-genome)")

    # Step 3: Load data
    if not args.skip_data:
        success = setup_stock_data(
            data_dir=args.data_dir,
            timeframe=args.timeframe,
            stocks=stock_list,
        )
        if not success:
            print("\n[ERROR] Setup failed at data loading")
            sys.exit(1)
    else:
        print("Skipping data loading (--skip-data)")

    # Success!
    print("\n" + "=" * 80)
    safe_print("[OK] SETUP COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Run small simulation with stock data:")
    print("     python -m src.simulation.simulator real-data --scenario small --timeframe 5min")
    print("\n  2. Or run with specific stocks:")
    print("     python -m src.simulation.simulator real-data --stocks WIPRO,TCS,ITC --queries 200")
    print("\n  3. XGBoost ML training will automatically use query_stats from simulations")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
