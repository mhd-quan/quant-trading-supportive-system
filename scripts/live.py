"""Live streaming script for real-time data collection."""

import asyncio
import argparse
from pathlib import Path
import sys
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger

from src.data.stream.binance_ws import BinanceWebSocket
from src.data.warehouse.duckdb_manager import DuckDBManager
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

    async def flush_buffer(self):
        """Flush buffer to database."""
        if not self.buffer:
            return

        logger.info(f"Flushing {len(self.buffer)} candles to database")

        try:
            df = pd.DataFrame(self.buffer)
            df["exchange"] = "binance"

            self.db_manager.insert_ohlcv(df, replace_duplicates=True)

            self.buffer = []
            logger.info("Buffer flushed successfully")

        except Exception as e:
            logger.error(f"Error flushing buffer: {e}")

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
