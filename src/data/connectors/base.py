"""Base exchange connector protocol and utilities."""

from abc import ABC, abstractmethod
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime, timezone
import pandas as pd
from dataclasses import dataclass
from enum import Enum
from loguru import logger


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
        # Don't store keys as plain instance variables - use private attributes
        self._api_key = api_key
        self._api_secret = api_secret
        self.rate_limit_config = rate_limit_config

        # Log API key usage safely
        if api_key:
            masked_key = self._mask_key(api_key)
            logger.debug(f"{exchange_id} initialized with API key: {masked_key}")

    @property
    def api_key(self) -> Optional[str]:
        """Get API key."""
        return self._api_key

    @property
    def api_secret(self) -> Optional[str]:
        """Get API secret."""
        return self._api_secret

    @staticmethod
    def _mask_key(key: Optional[str]) -> str:
        """Mask API key for logging.

        Args:
            key: API key to mask

        Returns:
            Masked key string
        """
        if not key:
            return "None"
        if len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

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
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
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
    def validate_dataframe(df: pd.DataFrame) -> tuple[bool, List[str]]:
        """Validate OHLCV DataFrame before insert.

        Args:
            df: DataFrame to validate

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []

        if df.empty:
            errors.append("DataFrame is empty")
            return False, errors

        # Check required columns
        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")

        # Validate OHLC relationships
        invalid_high = df[df["high"] < df["low"]]
        if not invalid_high.empty:
            errors.append(f"Found {len(invalid_high)} rows where high < low")

        invalid_high_open = df[df["high"] < df["open"]]
        if not invalid_high_open.empty:
            errors.append(f"Found {len(invalid_high_open)} rows where high < open")

        invalid_high_close = df[df["high"] < df["close"]]
        if not invalid_high_close.empty:
            errors.append(f"Found {len(invalid_high_close)} rows where high < close")

        invalid_low_open = df[df["low"] > df["open"]]
        if not invalid_low_open.empty:
            errors.append(f"Found {len(invalid_low_open)} rows where low > open")

        invalid_low_close = df[df["low"] > df["close"]]
        if not invalid_low_close.empty:
            errors.append(f"Found {len(invalid_low_close)} rows where low > close")

        # Validate volume
        invalid_volume = df[df["volume"] < 0]
        if not invalid_volume.empty:
            errors.append(f"Found {len(invalid_volume)} rows with negative volume")

        # Check for null values
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            null_cols = null_counts[null_counts > 0].to_dict()
            errors.append(f"Found null values: {null_cols}")

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"DataFrame validation failed: {'; '.join(errors)}")

        return is_valid, errors

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
