"""Binance exchange connector implementation."""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
import ccxt.async_support as ccxt
from loguru import logger

from src.data.connectors.base import ExchangeConnector, RateLimitConfig


class BinanceConnector(ExchangeConnector):
    """Binance exchange connector using CCXT."""

    TIMEFRAME_MAP = {
        "1m": "1m",
        "3m": "3m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "12h": "12h",
        "1d": "1d",
        "3d": "3d",
        "1w": "1w",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = False,
    ):
        """Initialize Binance connector.

        Args:
            api_key: Binance API key (optional, for public data only)
            api_secret: Binance API secret
            testnet: Use testnet endpoint
        """
        rate_limit_config = RateLimitConfig(
            requests_per_second=10, requests_per_minute=1200, weight_per_minute=6000
        )
        super().__init__(
            exchange_id="binance",
            api_key=api_key,
            api_secret=api_secret,
            rate_limit_config=rate_limit_config,
        )

        options = {"defaultType": "spot"}
        if testnet:
            options["urls"] = {"api": "https://testnet.binance.vision/api"}

        self.client = ccxt.binance(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": options,
            }
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data from Binance.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1m', '1h', '1d')
            since: Start timestamp in milliseconds
            limit: Maximum number of candles (max 1000 for Binance)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            if timeframe not in self.TIMEFRAME_MAP:
                raise ValueError(f"Unsupported timeframe: {timeframe}")

            # Binance limit is 1000 candles per request
            limit = min(limit, 1000)

            logger.debug(
                f"Fetching OHLCV for {symbol} {timeframe} since {since} limit {limit}"
            )

            ohlcv = await self.client.fetch_ohlcv(
                symbol=symbol,
                timeframe=self.TIMEFRAME_MAP[timeframe],
                since=since,
                limit=limit,
            )

            if not ohlcv:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return pd.DataFrame()

            # Parse into DataFrame
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df["exchange"] = self.exchange_id
            df["symbol"] = symbol
            df["timeframe"] = timeframe

            # Convert to float
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            logger.debug(f"Fetched {len(df)} candles for {symbol} {timeframe}")
            return df

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching {symbol} {timeframe}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching {symbol} {timeframe}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol} {timeframe}: {e}")
            raise

    async def fetch_ohlcv_range(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        batch_size: int = 1000,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a date range.

        Args:
            symbol: Trading pair
            timeframe: Timeframe
            start_date: Start date
            end_date: End date (default: now)
            batch_size: Number of candles per request

        Returns:
            Complete DataFrame for the date range
        """
        if end_date is None:
            end_date = datetime.utcnow()

        all_data = []
        current_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        timeframe_ms = self.timeframe_to_milliseconds(timeframe)

        logger.info(
            f"Fetching {symbol} {timeframe} from {start_date} to {end_date}"
        )

        while current_timestamp < end_timestamp:
            try:
                df = await self.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_timestamp,
                    limit=batch_size,
                )

                if df.empty:
                    logger.warning(f"No more data available at {current_timestamp}")
                    break

                all_data.append(df)

                # Move to next batch
                last_timestamp = int(df.iloc[-1]["timestamp"].timestamp() * 1000)
                current_timestamp = last_timestamp + timeframe_ms

                # Rate limiting
                await asyncio.sleep(0.1)

                logger.debug(
                    f"Progress: {len(all_data) * batch_size} candles fetched"
                )

            except Exception as e:
                logger.error(f"Error during batch fetch: {e}")
                # Exponential backoff
                await asyncio.sleep(2)
                continue

        if not all_data:
            return pd.DataFrame()

        # Concatenate all batches
        result = pd.concat(all_data, ignore_index=True)
        result = result.drop_duplicates(subset=["timestamp"], keep="first")
        result = result.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Fetched total {len(result)} candles for {symbol} {timeframe}")
        return result

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker.

        Args:
            symbol: Trading pair

        Returns:
            Ticker data
        """
        try:
            ticker = await self.client.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "last": float(ticker.get("last", 0)),
                "bid": float(ticker.get("bid", 0)),
                "ask": float(ticker.get("ask", 0)),
                "volume": float(ticker.get("baseVolume", 0)),
                "quote_volume": float(ticker.get("quoteVolume", 0)),
                "high": float(ticker.get("high", 0)),
                "low": float(ticker.get("low", 0)),
                "change_percent": float(ticker.get("percentage", 0)),
                "timestamp": pd.to_datetime(ticker.get("timestamp"), unit="ms"),
            }
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            raise

    async def fetch_order_book(
        self, symbol: str, limit: int = 100
    ) -> Dict[str, Any]:
        """Fetch order book.

        Args:
            symbol: Trading pair
            limit: Depth of order book

        Returns:
            Order book data
        """
        try:
            orderbook = await self.client.fetch_order_book(symbol, limit=limit)
            return {
                "symbol": symbol,
                "bids": [[float(p), float(v)] for p, v in orderbook.get("bids", [])],
                "asks": [[float(p), float(v)] for p, v in orderbook.get("asks", [])],
                "timestamp": pd.to_datetime(orderbook.get("timestamp"), unit="ms"),
            }
        except Exception as e:
            logger.error(f"Error fetching order book for {symbol}: {e}")
            raise

    async def get_symbols(self) -> List[str]:
        """Get all available trading symbols.

        Returns:
            List of symbols
        """
        try:
            markets = await self.client.load_markets()
            # Filter for spot markets only
            symbols = [
                market["symbol"]
                for market in markets.values()
                if market.get("type") == "spot" and market.get("active", False)
            ]
            return sorted(symbols)
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            raise

    async def get_timeframes(self) -> List[str]:
        """Get supported timeframes.

        Returns:
            List of timeframe strings
        """
        return list(self.TIMEFRAME_MAP.keys())

    async def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol exists and is tradable.

        Args:
            symbol: Trading pair symbol

        Returns:
            True if valid
        """
        try:
            markets = await self.client.load_markets()
            return symbol in markets and markets[symbol].get("active", False)
        except Exception as e:
            logger.error(f"Error validating symbol {symbol}: {e}")
            return False

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange information.

        Returns:
            Exchange metadata
        """
        try:
            info = await self.client.fetch_status()
            return {
                "exchange": self.exchange_id,
                "status": info.get("status"),
                "updated": info.get("updated"),
            }
        except Exception as e:
            logger.error(f"Error fetching exchange info: {e}")
            raise

    async def close(self) -> None:
        """Close the exchange connection."""
        await self.client.close()

    async def __aenter__(self) -> "BinanceConnector":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
