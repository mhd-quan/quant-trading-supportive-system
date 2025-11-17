"""Backfill historical OHLCV data from exchanges."""

import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger

from src.data.connectors.binance import BinanceConnector
from src.data.connectors.coinbase import CoinbaseConnector
from src.data.connectors.base import ExchangeConnector
from src.data.warehouse.duckdb_manager import DuckDBManager
from src.data.warehouse.parquet_manager import ParquetManager


class BackfillCheckpoint:
    """Manage backfill checkpoints for resume capability."""

    def __init__(self, checkpoint_dir: str = "./data/checkpoints"):
        """Initialize checkpoint manager."""
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpoint_path(self, exchange: str, symbol: str, timeframe: str) -> Path:
        """Get checkpoint file path."""
        filename = f"{exchange}_{symbol.replace('/', '_')}_{timeframe}.json"
        return self.checkpoint_dir / filename

    def save(self, exchange: str, symbol: str, timeframe: str, last_timestamp: datetime, total_records: int):
        """Save checkpoint."""
        checkpoint_data = {
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "last_timestamp": last_timestamp.isoformat(),
            "total_records": total_records,
            "saved_at": datetime.utcnow().isoformat(),
        }
        path = self.get_checkpoint_path(exchange, symbol, timeframe)
        with open(path, "w") as f:
            json.dump(checkpoint_data, f, indent=2)
        logger.info(f"Checkpoint saved: {total_records} records up to {last_timestamp}")

    def load(self, exchange: str, symbol: str, timeframe: str) -> dict:
        """Load checkpoint if exists."""
        path = self.get_checkpoint_path(exchange, symbol, timeframe)
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
            logger.info(f"Checkpoint loaded: {data['total_records']} records up to {data['last_timestamp']}")
            return data
        return None

    def delete(self, exchange: str, symbol: str, timeframe: str):
        """Delete checkpoint."""
        path = self.get_checkpoint_path(exchange, symbol, timeframe)
        if path.exists():
            path.unlink()
            logger.info("Checkpoint deleted")


async def backfill_data(
    exchange: str,
    symbol: str,
    timeframe: str,
    days: int,
    export_parquet: bool = True,
    resume: bool = False,
):
    """Backfill historical data.

    Args:
        exchange: Exchange identifier
        symbol: Trading pair symbol
        timeframe: Candle timeframe
        days: Number of days to backfill
        export_parquet: Whether to export to Parquet
        resume: Whether to resume from checkpoint
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
    checkpoint_manager = BackfillCheckpoint()

    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Check for checkpoint
        if resume:
            checkpoint = checkpoint_manager.load(exchange, symbol, timeframe)
            if checkpoint:
                start_date = datetime.fromisoformat(checkpoint["last_timestamp"])
                logger.info(f"Resuming from checkpoint: {start_date}")

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

        # Add metadata if not present
        if "exchange" not in df.columns:
            df["exchange"] = exchange
        if "symbol" not in df.columns:
            df["symbol"] = symbol
        if "timeframe" not in df.columns:
            df["timeframe"] = timeframe

        logger.info(f"Fetched {len(df)} candles")

        # Validate data before insert
        is_valid, errors = ExchangeConnector.validate_dataframe(df)
        if not is_valid:
            logger.error(f"Data validation failed: {errors}")
            # Filter out invalid rows
            df_clean = df[
                (df["high"] >= df["low"]) &
                (df["high"] >= df["open"]) &
                (df["high"] >= df["close"]) &
                (df["low"] <= df["open"]) &
                (df["low"] <= df["close"]) &
                (df["volume"] >= 0)
            ]
            logger.info(f"Filtered to {len(df_clean)} valid candles (removed {len(df) - len(df_clean)} invalid)")
            df = df_clean

        if df.empty:
            logger.warning("No valid data after filtering")
            return

        # Insert into DuckDB
        rows_inserted = db_manager.insert_ohlcv(df, replace_duplicates=True)
        logger.info(f"Inserted {rows_inserted} rows into DuckDB")

        # Save checkpoint
        last_timestamp = df["timestamp"].max()
        checkpoint_manager.save(exchange, symbol, timeframe, last_timestamp, len(df))

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

        # Delete checkpoint on success
        checkpoint_manager.delete(exchange, symbol, timeframe)

        logger.success(f"Backfill completed successfully")

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        # Save checkpoint on failure for resume
        if 'df' in locals() and not df.empty:
            last_timestamp = df["timestamp"].max()
            checkpoint_manager.save(exchange, symbol, timeframe, last_timestamp, len(df))
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
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )

    args = parser.parse_args()

    asyncio.run(
        backfill_data(
            exchange=args.exchange,
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            export_parquet=not args.no_parquet,
            resume=args.resume,
        )
    )


if __name__ == "__main__":
    main()
