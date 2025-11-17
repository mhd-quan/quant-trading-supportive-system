"""Binance WebSocket implementation."""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from loguru import logger

from src.data.stream.websocket_manager import WebSocketManager


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
        """Handle kline message.

        Args:
            data: Kline data
        """
        k = data.get("k", {})

        if not k.get("x"):  # Only process closed candles
            return

        candle = {
            "timestamp": pd.to_datetime(k["t"], unit="ms"),
            "symbol": data.get("s"),
            "timeframe": k.get("i"),
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "quote_volume": float(k.get("q", 0)),
            "trades_count": int(k.get("n", 0)),
            "taker_buy_volume": float(k.get("V", 0)),
            "taker_buy_quote_volume": float(k.get("Q", 0)),
        }

        # Call registered callback
        callback = self.callbacks.get("kline")
        if callback:
            await callback(candle)
        else:
            logger.debug(f"Kline received: {candle}")

    async def _handle_ticker(self, data: Dict[str, Any]) -> None:
        """Handle ticker message.

        Args:
            data: Ticker data
        """
        ticker = {
            "symbol": data.get("s"),
            "price_change": float(data.get("p", 0)),
            "price_change_percent": float(data.get("P", 0)),
            "weighted_avg_price": float(data.get("w", 0)),
            "last_price": float(data.get("c", 0)),
            "last_qty": float(data.get("Q", 0)),
            "bid": float(data.get("b", 0)),
            "ask": float(data.get("a", 0)),
            "open": float(data.get("o", 0)),
            "high": float(data.get("h", 0)),
            "low": float(data.get("l", 0)),
            "volume": float(data.get("v", 0)),
            "quote_volume": float(data.get("q", 0)),
            "timestamp": pd.to_datetime(data.get("E"), unit="ms"),
        }

        callback = self.callbacks.get("ticker")
        if callback:
            await callback(ticker)

    async def _handle_depth(self, data: Dict[str, Any]) -> None:
        """Handle depth update message.

        Args:
            data: Depth data
        """
        depth = {
            "symbol": data.get("s"),
            "bids": [[float(p), float(v)] for p, v in data.get("b", [])],
            "asks": [[float(p), float(v)] for p, v in data.get("a", [])],
            "timestamp": pd.to_datetime(data.get("E"), unit="ms"),
        }

        callback = self.callbacks.get("depth")
        if callback:
            await callback(depth)
