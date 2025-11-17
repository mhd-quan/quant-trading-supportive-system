"""Coinbase Pro exchange connector implementation."""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import ccxt.async_support as ccxt
from loguru import logger

from src.data.connectors.base import ExchangeConnector, RateLimitConfig


class CoinbaseConnector(ExchangeConnector):
    """Coinbase Pro exchange connector using CCXT."""

    TIMEFRAME_MAP = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "6h": 21600,
        "1d": 86400,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize Coinbase Pro connector.

        Args:
            api_key: Coinbase API key
            api_secret: Coinbase API secret
            password: Coinbase API password
        """
        rate_limit_config = RateLimitConfig(
            requests_per_second=3, requests_per_minute=15
        )
        super().__init__(
            exchange_id="coinbase",
            api_key=api_key,
            api_secret=api_secret,
            rate_limit_config=rate_limit_config,
        )

        self.client = ccxt.coinbasepro(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "password": password,
                "enableRateLimit": True,
                "verify": True,  # SSL/TLS verification
                "timeout": 30000,  # 30 second timeout
            }
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 300,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data from Coinbase Pro.

        Args:
            symbol: Trading pair (e.g., 'BTC/USD')
            timeframe: Timeframe (e.g., '1m', '1h', '1d')
            since: Start timestamp in milliseconds
            limit: Maximum number of candles (max 300 for Coinbase)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            if timeframe not in self.TIMEFRAME_MAP:
                raise ValueError(f"Unsupported timeframe: {timeframe}")

            # Coinbase limit is 300 candles per request
            limit = min(limit, 300)

            logger.debug(
                f"Fetching OHLCV for {symbol} {timeframe} since {since} limit {limit}"
            )

            # Convert timeframe to granularity
            granularity = self.TIMEFRAME_MAP[timeframe]

            ohlcv = await self.client.fetch_ohlcv(
                symbol=symbol, timeframe=str(granularity), since=since, limit=limit
            )

            if not ohlcv:
                logger.warning(f"No data returned for {symbol} {timeframe}")
                return pd.DataFrame()

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df["exchange"] = self.exchange_id
            df["symbol"] = symbol
            df["timeframe"] = timeframe

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
        batch_size: int = 300,
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
        from datetime import timezone as tz

        if end_date is None:
            end_date = datetime.now(tz.utc)

        all_data = []
        failed_batches = []
        current_timestamp = int(start_date.timestamp() * 1000)
        end_timestamp = int(end_date.timestamp() * 1000)
        timeframe_ms = self.timeframe_to_milliseconds(timeframe)

        logger.info(
            f"Fetching {symbol} {timeframe} from {start_date} to {end_date}"
        )

        retry_count = 0
        max_retries = 3

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

                # Filter results to not exceed end_timestamp
                df = df[df["timestamp"] <= pd.Timestamp(end_date)]

                if not df.empty:
                    all_data.append(df)

                # Move to next batch
                last_timestamp = int(df.iloc[-1]["timestamp"].timestamp() * 1000)
                current_timestamp = last_timestamp + timeframe_ms

                # Reset retry count on success
                retry_count = 0

                # Rate limiting (Coinbase is more strict)
                await asyncio.sleep(0.5)

                logger.debug(
                    f"Progress: {sum(len(d) for d in all_data)} candles fetched"
                )

            except Exception as e:
                retry_count += 1
                logger.error(
                    f"Error during batch fetch at {current_timestamp}: {e} (retry {retry_count}/{max_retries})"
                )

                # Track failed batch
                failed_batches.append({
                    "timestamp": current_timestamp,
                    "error": str(e),
                    "retry_count": retry_count
                })

                if retry_count >= max_retries:
                    logger.error(f"Max retries reached for batch at {current_timestamp}, skipping")
                    # Skip this batch and move to next
                    current_timestamp += timeframe_ms * batch_size
                    retry_count = 0
                    continue

                # Exponential backoff
                await asyncio.sleep(2 ** retry_count)

        if not all_data:
            logger.warning("No data fetched successfully")
            return pd.DataFrame()

        # Report failed batches
        if failed_batches:
            logger.warning(f"Failed to fetch {len(failed_batches)} batches: {failed_batches}")

        # Concatenate all batches
        result = pd.concat(all_data, ignore_index=True)
        result = result.drop_duplicates(subset=["timestamp"], keep="first")
        result = result.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Fetched total {len(result)} candles for {symbol} {timeframe}")
        return result

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """Fetch current ticker."""
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
        """Fetch order book."""
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
        """Get all available trading symbols."""
        try:
            markets = await self.client.load_markets()
            symbols = [
                market["symbol"]
                for market in markets.values()
                if market.get("active", False)
            ]
            return sorted(symbols)
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            raise

    async def get_timeframes(self) -> List[str]:
        """Get supported timeframes."""
        return list(self.TIMEFRAME_MAP.keys())

    async def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol exists and is tradable."""
        try:
            markets = await self.client.load_markets()
            return symbol in markets and markets[symbol].get("active", False)
        except Exception as e:
            logger.error(f"Error validating symbol {symbol}: {e}")
            return False

    async def close(self) -> None:
        """Close the exchange connection."""
        await self.client.close()

    async def __aenter__(self) -> "CoinbaseConnector":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
