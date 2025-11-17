"""Backfill historical OHLCV data from exchanges."""

import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger

from src.data.connectors.binance import BinanceConnector
from src.data.connectors.coinbase import CoinbaseConnector
from src.data.warehouse.duckdb_manager import DuckDBManager
from src.data.warehouse.parquet_manager import ParquetManager


async def backfill_data(
    exchange: str,
    symbol: str,
    timeframe: str,
    days: int,
    export_parquet: bool = True,
):
    """Backfill historical data.

    Args:
        exchange: Exchange identifier
        symbol: Trading pair symbol
        timeframe: Candle timeframe
        days: Number of days to backfill
        export_parquet: Whether to export to Parquet
    """
    logger.info(
        f"Starting backfill: {exchange} {symbol} {timeframe} for {days} days"
    )

    # Initialize connector
    if exchange == "binance":
        connector = BinanceConnector()
    elif exchange == "coinbase":
        connector = CoinbaseConnector()
    else:
        logger.error(f"Unknown exchange: {exchange}")
        return

    # Initialize storage
    db_manager = DuckDBManager()
    db_manager.init_schema()

    parquet_manager = ParquetManager() if export_parquet else None

    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Fetching data from {start_date} to {end_date}")

        # Fetch data
        df = await connector.fetch_ohlcv_range(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            logger.warning("No data fetched")
            return

        # Add metadata
        df["exchange"] = exchange
        df["symbol"] = symbol
        df["timeframe"] = timeframe

        logger.info(f"Fetched {len(df)} candles")

        # Insert into DuckDB
        rows_inserted = db_manager.insert_ohlcv(df, replace_duplicates=True)
        logger.info(f"Inserted {rows_inserted} rows into DuckDB")

        # Export to Parquet
        if parquet_manager:
            parquet_manager.write_partition(df, exchange, symbol, timeframe)
            logger.info("Exported to Parquet")

        # Validate data
        validation = db_manager.validate_data_integrity(symbol, timeframe, exchange)
        logger.info(f"Data validation: {validation}")

        # Get coverage stats
        coverage = db_manager.get_data_coverage()
        logger.info(f"Data coverage:\n{coverage}")

        logger.success(f"Backfill completed successfully")

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
    finally:
        await connector.close()
        db_manager.close()


def main():
    """Main entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="Backfill historical crypto data")
    parser.add_argument(
        "--exchange",
        type=str,
        required=True,
        choices=["binance", "coinbase"],
        help="Exchange name",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Trading pair (e.g., BTC/USDT)",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        required=True,
        choices=["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w"],
        help="Candle timeframe",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to backfill (default: 30)",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Skip Parquet export",
    )

    args = parser.parse_args()

    asyncio.run(
        backfill_data(
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            export_parquet=not args.no_parquet,
        )
    )


if __name__ == "__main__":
    main()
