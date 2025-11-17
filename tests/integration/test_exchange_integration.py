"""Integration tests for exchange connectors."""

import pytest
from unittest.mock import AsyncMock, patch

from src.data.connectors.binance import BinanceConnector
from src.data.connectors.coinbase import CoinbaseConnector


@pytest.mark.integration
@pytest.mark.asyncio
class TestExchangeIntegration:
    """Test exchange connector integration."""

    async def test_binance_connector_lifecycle(self, test_config, mock_ccxt_exchange):
        """Test Binance connector full lifecycle."""
        with patch("src.data.connectors.binance.ccxt.binance", return_value=mock_ccxt_exchange):
            connector = BinanceConnector(
                api_key=test_config["exchange"]["api_key"],
                secret=test_config["exchange"]["secret"],
            )

            # Test connection
            await connector.connect()
            assert connector.is_connected

            # Test data fetch
            data = await connector.fetch_ohlcv(
                symbol="BTC/USDT",
                timeframe="1h",
                limit=100,
            )
            assert len(data) > 0

            # Test cleanup
            await connector.disconnect()
            assert not connector.is_connected

    async def test_coinbase_connector_lifecycle(self, test_config, mock_ccxt_exchange):
        """Test Coinbase connector full lifecycle."""
        with patch("src.data.connectors.coinbase.ccxt.coinbase", return_value=mock_ccxt_exchange):
            connector = CoinbaseConnector(
                api_key=test_config["exchange"]["api_key"],
                secret=test_config["exchange"]["secret"],
            )

            await connector.connect()
            assert connector.is_connected

            data = await connector.fetch_ohlcv(
                symbol="BTC/USD",
                timeframe="1h",
                limit=100,
            )
            assert len(data) > 0

            await connector.disconnect()

    async def test_rate_limiting(self, test_config, mock_ccxt_exchange):
        """Test rate limiting across multiple requests."""
        with patch("src.data.connectors.binance.ccxt.binance", return_value=mock_ccxt_exchange):
            connector = BinanceConnector(
                api_key=test_config["exchange"]["api_key"],
                secret=test_config["exchange"]["secret"],
            )

            await connector.connect()

            # Make multiple rapid requests
            symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]
            results = []

            for symbol in symbols:
                data = await connector.fetch_ohlcv(symbol, "1h", limit=10)
                results.append(data)

            # Should complete without rate limit errors
            assert len(results) == 3
            assert all(len(r) > 0 for r in results)

            await connector.disconnect()

    async def test_error_recovery(self, test_config):
        """Test connector error handling and recovery."""
        mock_exchange = AsyncMock()
        mock_exchange.fetch_ohlcv = AsyncMock(side_effect=Exception("Network error"))

        with patch("src.data.connectors.binance.ccxt.binance", return_value=mock_exchange):
            connector = BinanceConnector(
                api_key=test_config["exchange"]["api_key"],
                secret=test_config["exchange"]["secret"],
            )

            await connector.connect()

            with pytest.raises(Exception):
                await connector.fetch_ohlcv("BTC/USDT", "1h", limit=10)

            await connector.disconnect()


@pytest.mark.integration
class TestMultiExchangeAggregation:
    """Test aggregating data from multiple exchanges."""

    def test_price_comparison_across_exchanges(self, mock_ccxt_exchange):
        """Test comparing prices across exchanges."""
        from src.analytics.cross_exchange import PriceComparator

        comparator = PriceComparator()

        # Mock data from different exchanges
        binance_price = 50000.0
        coinbase_price = 50050.0

        spread = comparator.calculate_spread(binance_price, coinbase_price)

        assert spread > 0
        assert spread == 50.0

    def test_arbitrage_opportunity_detection(self):
        """Test detecting arbitrage opportunities."""
        from src.analytics.cross_exchange import ArbitrageDetector

        detector = ArbitrageDetector()

        prices = {
            "binance": {"bid": 50000.0, "ask": 50001.0},
            "coinbase": {"bid": 50060.0, "ask": 50061.0},
        }

        opportunities = detector.find_opportunities(prices)

        assert len(opportunities) > 0
        assert opportunities[0]["profit"] > 0
