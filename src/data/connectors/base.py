"""Base exchange connector protocol and utilities."""

from abc import ABC, abstractmethod
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
import pandas as pd
from dataclasses import dataclass
from enum import Enum


class TimeFrame(str, Enum):
    """Supported timeframes."""

    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    H6 = "6h"
    H12 = "12h"
    D1 = "1d"
    D3 = "3d"
    W1 = "1w"


@dataclass
class OHLCV:
    """OHLCV data structure."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: Optional[float] = None
    trades_count: Optional[int] = None
    taker_buy_volume: Optional[float] = None
    taker_buy_quote_volume: Optional[float] = None

    def validate(self) -> bool:
        """Validate OHLCV data integrity."""
        if self.high < self.low:
            return False
        if self.high < self.open or self.high < self.close:
            return False
        if self.low > self.open or self.low > self.close:
            return False
        if self.volume < 0:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trades_count": self.trades_count,
            "taker_buy_volume": self.taker_buy_volume,
            "taker_buy_quote_volume": self.taker_buy_quote_volume,
        }


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_second: int
    requests_per_minute: int
    weight_per_minute: Optional[int] = None


class ExchangeConnector(ABC):
    """Abstract base class for exchange connectors."""

    def __init__(
        self,
        exchange_id: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
    ):
        """Initialize exchange connector.

        Args:
            exchange_id: Exchange identifier (e.g., 'binance', 'coinbase')
            api_key: API key for authenticated requests
            api_secret: API secret for authenticated requests
            rate_limit_config: Rate limiting configuration
        """
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.rate_limit_config = rate_limit_config

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data.

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '1m', '1h', '1d')
            since: Timestamp in milliseconds to fetch from
            limit: Maximum number of candles to fetch

        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker information.

        Args:
            symbol: Trading pair symbol

        Returns:
            Dictionary with ticker data (last, bid, ask, volume, etc.)
        """
        pass

    @abstractmethod
    async def fetch_order_book(
        self, symbol: str, limit: int = 100
    ) -> Dict[str, Any]:
        """Fetch order book.

        Args:
            symbol: Trading pair symbol
            limit: Depth of order book to fetch

        Returns:
            Dictionary with bids and asks
        """
        pass

    @abstractmethod
    async def get_symbols(self) -> List[str]:
        """Get all available trading symbols.

        Returns:
            List of symbol strings
        """
        pass

    @abstractmethod
    async def get_timeframes(self) -> List[str]:
        """Get supported timeframes.

        Returns:
            List of timeframe strings
        """
        pass

    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is tradable.

        Args:
            symbol: Trading pair symbol

        Returns:
            True if symbol is valid and tradable
        """
        pass

    def parse_ohlcv(self, raw_data: List[Any]) -> pd.DataFrame:
        """Parse raw OHLCV data into DataFrame.

        Args:
            raw_data: Raw OHLCV data from exchange

        Returns:
            Formatted DataFrame
        """
        df = pd.DataFrame(
            raw_data,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "quote_volume",
                "trades_count",
                "taker_buy_volume",
                "taker_buy_quote_volume",
            ],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.astype(
            {
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "volume": float,
            }
        )
        return df

    @staticmethod
    def timeframe_to_seconds(timeframe: str) -> int:
        """Convert timeframe string to seconds.

        Args:
            timeframe: Timeframe string (e.g., '1m', '1h', '1d')

        Returns:
            Number of seconds in the timeframe
        """
        multipliers = {
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800,
        }
        value = int(timeframe[:-1])
        unit = timeframe[-1]
        return value * multipliers.get(unit, 60)

    @staticmethod
    def timeframe_to_milliseconds(timeframe: str) -> int:
        """Convert timeframe string to milliseconds.

        Args:
            timeframe: Timeframe string (e.g., '1m', '1h', '1d')

        Returns:
            Number of milliseconds in the timeframe
        """
        return ExchangeConnector.timeframe_to_seconds(timeframe) * 1000
