"""Binance WebSocket implementation."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import pandas as pd
from loguru import logger

from src.data.stream.websocket_manager import WebSocketManager
from src.data.stream.validation import (
    validate_kline_message,
    validate_ticker_message,
    validate_depth_message,
)


class BinanceWebSocket(WebSocketManager):
    """Binance WebSocket client for real-time data."""

    BASE_URL = "wss://stream.binance.com:9443/ws"

    def __init__(self):
        """Initialize Binance WebSocket client."""
        super().__init__(
            url=self.BASE_URL,
            ping_interval=30,
            ping_timeout=10,
            max_reconnect_delay=300,
        )
        self.subscriptions: List[str] = []

    async def on_connect(self) -> None:
        """Called after successful connection."""
        logger.info("Binance WebSocket connected")
        # Resubscribe to previous channels
        if self.subscriptions:
            await self.subscribe(self.subscriptions)

    async def on_message(self, data: Dict[str, Any]) -> None:
        """Process incoming message.

        Args:
            data: Message data
        """
        event_type = data.get("e")

        if event_type == "kline":
            await self._handle_kline(data)
        elif event_type == "24hrTicker":
            await self._handle_ticker(data)
        elif event_type == "depthUpdate":
            await self._handle_depth(data)
        else:
            logger.debug(f"Unknown event type: {event_type}")

    async def subscribe(self, channels: List[str]) -> None:
        """Subscribe to channels.

        Args:
            channels: List of channel names
        """
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": channels,
            "id": 1,
        }
        await self.send(subscribe_msg)
        self.subscriptions.extend(channels)
        logger.info(f"Subscribed to channels: {channels}")

    async def subscribe_klines(
        self, symbol: str, timeframes: List[str]
    ) -> None:
        """Subscribe to kline/candlestick streams.

        Args:
            symbol: Trading pair (e.g., 'btcusdt')
            timeframes: List of timeframes (e.g., ['1m', '5m'])
        """
        channels = [
            f"{symbol.lower()}@kline_{tf}" for tf in timeframes
        ]
        await self.subscribe(channels)

    async def subscribe_ticker(self, symbol: str) -> None:
        """Subscribe to 24hr ticker.

        Args:
            symbol: Trading pair
        """
        channel = f"{symbol.lower()}@ticker"
        await self.subscribe([channel])

    async def subscribe_depth(
        self, symbol: str, speed: str = "100ms"
    ) -> None:
        """Subscribe to order book depth.

        Args:
            symbol: Trading pair
            speed: Update speed ('100ms' or '1000ms')
        """
        channel = f"{symbol.lower()}@depth@{speed}"
        await self.subscribe([channel])

    async def _handle_kline(self, data: Dict[str, Any]) -> None:
        """Handle kline message with validation.

        Args:
            data: Kline data
        """
        try:
            # Validate message structure
            validated = validate_kline_message(data)

            k = validated.k

            if not k.x:  # Only process closed candles
                return

            candle = {
                "timestamp": pd.to_datetime(k.t, unit="ms", utc=True),
                "symbol": validated.s,
                "timeframe": k.i,
                "open": float(k.o),
                "high": float(k.h),
                "low": float(k.l),
                "close": float(k.c),
                "volume": float(k.v),
                "quote_volume": float(k.q),
                "trades_count": k.n,
                "taker_buy_volume": float(k.V),
                "taker_buy_quote_volume": float(k.Q),
            }

            # Call registered callback
            callback = self.callbacks.get("kline")
            if callback:
                await callback(candle)
            else:
                logger.debug(f"Kline received: {candle}")

        except ValueError as e:
            logger.error(f"Invalid kline message: {e}")
            logger.debug(f"Raw data: {data}")

    async def _handle_ticker(self, data: Dict[str, Any]) -> None:
        """Handle ticker message with validation.

        Args:
            data: Ticker data
        """
        try:
            # Validate message structure
            validated = validate_ticker_message(data)

            ticker = {
                "symbol": validated.s,
                "price_change": float(validated.p),
                "price_change_percent": float(validated.P),
                "weighted_avg_price": float(validated.w),
                "last_price": float(validated.c),
                "last_qty": float(validated.Q),
                "bid": float(validated.b),
                "ask": float(validated.a),
                "open": float(validated.o),
                "high": float(validated.h),
                "low": float(validated.l),
                "volume": float(validated.v),
                "quote_volume": float(validated.q),
                "timestamp": pd.to_datetime(validated.E, unit="ms", utc=True),
            }

            callback = self.callbacks.get("ticker")
            if callback:
                await callback(ticker)

        except ValueError as e:
            logger.error(f"Invalid ticker message: {e}")
            logger.debug(f"Raw data: {data}")

    async def _handle_depth(self, data: Dict[str, Any]) -> None:
        """Handle depth update message with validation.

        Args:
            data: Depth data
        """
        try:
            # Validate message structure
            validated = validate_depth_message(data)

            depth = {
                "symbol": validated.s,
                "bids": [[float(p), float(v)] for p, v in validated.b],
                "asks": [[float(p), float(v)] for p, v in validated.a],
                "timestamp": pd.to_datetime(validated.E, unit="ms", utc=True),
            }

            callback = self.callbacks.get("depth")
            if callback:
                await callback(depth)

        except ValueError as e:
            logger.error(f"Invalid depth update message: {e}")
            logger.debug(f"Raw data: {data}")
