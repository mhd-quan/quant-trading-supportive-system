"""Compact Parquet files to optimize storage."""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger

from src.data.warehouse.parquet_manager import ParquetManager


def compact_all_partitions():
    """Compact all Parquet partitions in the data lake."""
    load_dotenv()

    logger.info("Starting Parquet compaction")

    parquet_manager = ParquetManager()

    try:
        # Get storage stats before compaction
        stats_before = parquet_manager.get_storage_stats()

        if stats_before.empty:
            logger.warning("No Parquet files found")
            return

        logger.info(f"Found {len(stats_before)} datasets")
        logger.info(f"Total storage before: {stats_before['total_size_mb'].sum():.2f} MB")
        logger.info(f"Total files before: {stats_before['file_count'].sum()}")

        # Compact each dataset
        compacted_count = 0
        for _, row in stats_before.iterrows():
            exchange = row['exchange']
            symbol = row['symbol']
            timeframe = row['timeframe']

            # Only compact if there are multiple files
            if row['file_count'] > 1:
                logger.info(f"Compacting {exchange} {symbol} {timeframe}")
                parquet_manager.compact_partitions(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe
                )
                compacted_count += 1
            else:
                logger.debug(f"Skipping {exchange} {symbol} {timeframe} (only 1 file)")

        # Get storage stats after compaction
        stats_after = parquet_manager.get_storage_stats()

        logger.info("=" * 60)
        logger.info("COMPACTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Datasets compacted: {compacted_count}")
        logger.info(f"Total storage after: {stats_after['total_size_mb'].sum():.2f} MB")
        logger.info(f"Total files after: {stats_after['file_count'].sum()}")

        files_removed = stats_before['file_count'].sum() - stats_after['file_count'].sum()
        space_saved = stats_before['total_size_mb'].sum() - stats_after['total_size_mb'].sum()

        logger.info(f"Files removed: {files_removed}")
        logger.info(f"Space saved: {space_saved:.2f} MB")

        logger.success("Compaction completed successfully")

    except Exception as e:
        logger.error(f"Compaction failed: {e}", exc_info=True)
    finally:
        logger.info("Compaction process finished")


def compact_specific(exchange: str, symbol: str, timeframe: str):
    """Compact a specific dataset.

    Args:
        exchange: Exchange identifier
        symbol: Trading pair symbol
        timeframe: Candle timeframe
    """
    load_dotenv()

    logger.info(f"Compacting {exchange} {symbol} {timeframe}")

    parquet_manager = ParquetManager()

    try:
        parquet_manager.compact_partitions(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe
        )
        logger.success(f"Compacted {exchange} {symbol} {timeframe}")
    except Exception as e:
        logger.error(f"Compaction failed: {e}", exc_info=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compact Parquet files")
    parser.add_argument(
        "--exchange",
        type=str,
        help="Specific exchange to compact"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        help="Specific symbol to compact (e.g., BTC/USDT)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        help="Specific timeframe to compact"
    )

    args = parser.parse_args()

    # If specific dataset provided, compact only that
    if args.exchange and args.symbol and args.timeframe:
        compact_specific(args.exchange, args.symbol, args.timeframe)
    elif args.exchange or args.symbol or args.timeframe:
        logger.error("Must provide all of --exchange, --symbol, and --timeframe, or none")
        sys.exit(1)
    else:
        # Compact all datasets
        compact_all_partitions()


if __name__ == "__main__":
    main()
