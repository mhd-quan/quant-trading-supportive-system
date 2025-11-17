"""Live streaming script for real-time data collection."""

import asyncio
import argparse
from pathlib import Path
import sys
import yaml
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger

from src.data.stream.binance_ws import BinanceWebSocket
from src.data.warehouse.duckdb_manager import DuckDBManager
from src.data.connectors.base import ExchangeConnector
import pandas as pd


class LiveStreamManager:
    """Manage live streaming and storage."""

    def __init__(self, config_path: str = "configs/streaming.yaml"):
        """Initialize live stream manager."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.db_manager = DuckDBManager()
        self.db_manager.init_schema()

        self.buffer = []
        self.buffer_size = self.config["buffer"]["max_size_records"]
        self.flush_interval = self.config["buffer"]["flush_interval_seconds"]

        # Dead letter queue for failed messages
        self.dead_letter_queue = []
        self.max_retry_count = 3
        self.retry_counts = {}  # Track retry counts per buffer batch

        # Dead letter queue file
        self.dlq_path = Path("./data/dead_letter_queue")
        self.dlq_path.mkdir(parents=True, exist_ok=True)

    async def handle_kline(self, candle: dict):
        """Handle incoming kline data.

        Args:
            candle: Candle data from WebSocket
        """
        logger.debug(f"Received candle: {candle['symbol']} {candle['timeframe']}")

        # Add to buffer
        self.buffer.append(candle)

        # Flush if buffer is full
        if len(self.buffer) >= self.buffer_size:
            await self.flush_buffer()

    async def flush_buffer(self, retry_count: int = 0):
        """Flush buffer to database with retry logic and dead letter queue.

        Args:
            retry_count: Current retry attempt number
        """
        if not self.buffer:
            return

        buffer_id = id(self.buffer)  # Unique ID for this buffer batch
        logger.info(f"Flushing {len(self.buffer)} candles to database (attempt {retry_count + 1}/{self.max_retry_count})")

        # Create a copy of the buffer for processing
        buffer_copy = self.buffer.copy()

        try:
            df = pd.DataFrame(buffer_copy)
            df["exchange"] = "binance"

            # Validate data before insert
            is_valid, errors = ExchangeConnector.validate_dataframe(df)
            if not is_valid:
                logger.warning(f"Data validation issues: {errors}")
                # Filter out invalid rows
                df_clean = df[
                    (df["high"] >= df["low"]) &
                    (df["high"] >= df["open"]) &
                    (df["high"] >= df["close"]) &
                    (df["low"] <= df["open"]) &
                    (df["low"] <= df["close"]) &
                    (df["volume"] >= 0)
                ]
                invalid_count = len(df) - len(df_clean)
                if invalid_count > 0:
                    logger.warning(f"Filtered out {invalid_count} invalid rows")
                    # Save invalid rows to dead letter queue
                    self._save_to_dlq(df[~df.index.isin(df_clean.index)], "validation_failed")
                df = df_clean

            if df.empty:
                logger.warning("No valid data to flush after filtering")
                # Clear buffer only on success (including empty after filtering)
                self.buffer = []
                return

            # Insert into database
            self.db_manager.insert_ohlcv(df, replace_duplicates=True)

            # Clear buffer only on success
            self.buffer = []
            logger.info("Buffer flushed successfully")

            # Reset retry count on success
            if buffer_id in self.retry_counts:
                del self.retry_counts[buffer_id]

        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")

            # Track retry count
            if buffer_id not in self.retry_counts:
                self.retry_counts[buffer_id] = 0
            self.retry_counts[buffer_id] += 1

            # Check if we should retry
            if self.retry_counts[buffer_id] < self.max_retry_count:
                logger.info(f"Will retry flush (attempt {self.retry_counts[buffer_id] + 1}/{self.max_retry_count})")
                # Don't clear buffer - will retry
                await asyncio.sleep(2 ** self.retry_counts[buffer_id])  # Exponential backoff
            else:
                # Max retries reached - save to dead letter queue
                logger.error(f"Max retries reached for buffer batch, saving to dead letter queue")
                self._save_to_dlq(buffer_copy, f"max_retries_exceeded: {str(e)}")
                # Clear buffer after saving to DLQ
                self.buffer = []
                del self.retry_counts[buffer_id]

    def _save_to_dlq(self, data, reason: str):
        """Save failed data to dead letter queue.

        Args:
            data: Data that failed to process (DataFrame or list)
            reason: Reason for failure
        """
        try:
            timestamp = datetime.utcnow().isoformat().replace(":", "-")
            filename = f"dlq_{timestamp}.json"
            filepath = self.dlq_path / filename

            if isinstance(data, pd.DataFrame):
                data_dict = data.to_dict(orient="records")
            else:
                data_dict = data

            dlq_entry = {
                "timestamp": timestamp,
                "reason": reason,
                "record_count": len(data_dict),
                "data": data_dict
            }

            with open(filepath, "w") as f:
                json.dump(dlq_entry, f, indent=2, default=str)

            logger.warning(f"Saved {len(data_dict)} records to dead letter queue: {filepath}")
        except Exception as e:
            logger.error(f"Error saving to dead letter queue: {e}")

    async def start_streaming(self):
        """Start live streaming."""
        ws = BinanceWebSocket()
        ws.register_callback("kline", self.handle_kline)

        # Subscribe to configured streams
        for stream in self.config["streams"]:
            if not stream["enabled"]:
                continue

            symbol = stream["symbol"].replace("/", "").lower()
            timeframes = stream["timeframes"]

            logger.info(f"Subscribing to {symbol} {timeframes}")
            await ws.subscribe_klines(symbol, timeframes)

        # Start periodic flush task
        async def periodic_flush():
            while True:
                await asyncio.sleep(self.flush_interval)
                await self.flush_buffer()

        # Run tasks
        await asyncio.gather(
            ws.receive_loop(),
            periodic_flush(),
        )


def main():
    """Main entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="Live crypto data streaming")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/streaming.yaml",
        help="Configuration file path",
    )

    args = parser.parse_args()

    manager = LiveStreamManager(config_path=args.config)

    logger.info("Starting live streaming...")
    asyncio.run(manager.start_streaming())


if __name__ == "__main__":
    main()
