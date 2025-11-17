"""Shared pytest fixtures for the crypto research platform."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import numpy as np
import pandas as pd
import pytest
from pandas import DataFrame


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture
def sample_ohlcv_data() -> DataFrame:
    """Generate sample OHLCV data for testing.

    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    np.random.seed(42)
    periods = 1000
    start_time = datetime(2024, 1, 1)

    timestamps = [start_time + timedelta(minutes=i) for i in range(periods)]
    base_price = 50000.0

    # Generate realistic price movements
    returns = np.random.normal(0, 0.001, periods)
    prices = base_price * np.exp(np.cumsum(returns))

    data = {
        "timestamp": timestamps,
        "open": prices,
        "high": prices * (1 + np.abs(np.random.normal(0, 0.002, periods))),
        "low": prices * (1 - np.abs(np.random.normal(0, 0.002, periods))),
        "close": prices * (1 + np.random.normal(0, 0.001, periods)),
        "volume": np.random.uniform(100, 1000, periods),
    }

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@pytest.fixture
def sample_ohlcv_with_gaps() -> DataFrame:
    """Generate OHLCV data with intentional gaps for validation testing."""
    np.random.seed(42)
    periods = 100
    start_time = datetime(2024, 1, 1)

    timestamps = []
    for i in range(periods):
        # Skip timestamps at indices 30-35 to create a gap
        if 30 <= i < 35:
            continue
        timestamps.append(start_time + timedelta(minutes=i))

    base_price = 50000.0
    prices = base_price + np.random.normal(0, 100, len(timestamps))

    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps),
            "open": prices,
            "high": prices * 1.01,
            "low": prices * 0.99,
            "close": prices * (1 + np.random.normal(0, 0.001, len(timestamps))),
            "volume": np.random.uniform(100, 1000, len(timestamps)),
        }
    )


@pytest.fixture
def sample_trade_data() -> DataFrame:
    """Generate sample trade execution data."""
    np.random.seed(42)
    n_trades = 50

    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start="2024-01-01", periods=n_trades, freq="1H"),
            "symbol": ["BTC/USDT"] * n_trades,
            "side": np.random.choice(["buy", "sell"], n_trades),
            "price": np.random.uniform(49000, 51000, n_trades),
            "amount": np.random.uniform(0.01, 1.0, n_trades),
            "fee": np.random.uniform(0.5, 5.0, n_trades),
        }
    )


# ============================================================================
# Exchange Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_exchange_response() -> Dict[str, Any]:
    """Mock successful exchange API response."""
    return {
        "symbol": "BTC/USDT",
        "timestamp": 1704067200000,
        "datetime": "2024-01-01T00:00:00.000Z",
        "high": 50500.0,
        "low": 49500.0,
        "bid": 50000.0,
        "ask": 50001.0,
        "vwap": 50000.5,
        "open": 50100.0,
        "close": 50000.0,
        "last": 50000.0,
        "previousClose": 50100.0,
        "change": -100.0,
        "percentage": -0.2,
        "average": 50050.0,
        "baseVolume": 1234.56,
        "quoteVolume": 61728000.0,
    }


@pytest.fixture
def mock_ccxt_exchange():
    """Mock ccxt exchange instance."""
    exchange = Mock()
    exchange.fetch_ohlcv = Mock(
        return_value=[
            [1704067200000, 50000, 50500, 49500, 50200, 1000],
            [1704067260000, 50200, 50600, 50000, 50400, 1100],
            [1704067320000, 50400, 50800, 50200, 50600, 1200],
        ]
    )
    exchange.fetch_ticker = Mock(
        return_value={
            "symbol": "BTC/USDT",
            "last": 50000.0,
            "bid": 49999.0,
            "ask": 50001.0,
            "volume": 1000.0,
        }
    )
    exchange.fetch_balance = Mock(return_value={"USDT": {"free": 10000.0, "used": 0.0}})
    exchange.create_order = Mock(
        return_value={
            "id": "12345",
            "symbol": "BTC/USDT",
            "type": "limit",
            "side": "buy",
            "price": 50000.0,
            "amount": 0.1,
            "status": "open",
        }
    )
    return exchange


@pytest.fixture
def mock_async_exchange():
    """Mock async ccxt exchange instance."""
    exchange = AsyncMock()
    exchange.fetch_ohlcv = AsyncMock(
        return_value=[
            [1704067200000, 50000, 50500, 49500, 50200, 1000],
            [1704067260000, 50200, 50600, 50000, 50400, 1100],
        ]
    )
    exchange.close = AsyncMock()
    return exchange


# ============================================================================
# WebSocket Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock(
        return_value='{"e":"trade","s":"BTCUSDT","p":"50000.00","q":"0.01"}'
    )
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def mock_websocket_messages() -> List[str]:
    """Sample WebSocket messages."""
    return [
        '{"e":"kline","s":"BTCUSDT","k":{"t":1704067200000,"o":"50000","h":"50500","l":"49500","c":"50200","v":"1000"}}',
        '{"e":"kline","s":"BTCUSDT","k":{"t":1704067260000,"o":"50200","h":"50600","l":"50000","c":"50400","v":"1100"}}',
        '{"e":"trade","s":"BTCUSDT","p":"50300","q":"0.5","T":1704067320000}',
    ]


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Temporary DuckDB database path."""
    return tmp_path / "test_crypto.duckdb"


@pytest.fixture
def temp_parquet_dir(tmp_path: Path) -> Path:
    """Temporary directory for Parquet files."""
    parquet_dir = tmp_path / "lake"
    parquet_dir.mkdir()
    return parquet_dir


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Temporary directory for all data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "lake").mkdir()
    return data_dir


@pytest.fixture
def sample_parquet_file(temp_parquet_dir: Path, sample_ohlcv_data: DataFrame) -> Path:
    """Create a sample Parquet file."""
    file_path = temp_parquet_dir / "binance_btcusdt_1m_2024_01.parquet"
    sample_ohlcv_data.to_parquet(file_path, index=False)
    return file_path


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration dictionary."""
    return {
        "exchange": {
            "name": "binance",
            "api_key": "test_key",
            "secret": "test_secret",
            "rate_limit": {"requests_per_minute": 1000},
        },
        "data": {"chunk_size": 1000, "cache_enabled": False},
        "strategy": {
            "risk_percent": 1.0,
            "max_positions": 3,
            "stop_loss_atr": 2.0,
        },
        "backtest": {"initial_capital": 10000, "commission": 0.001},
    }


@pytest.fixture
def test_env_vars(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("BINANCE_API_KEY", "test_api_key")
    monkeypatch.setenv("BINANCE_SECRET", "test_secret")
    monkeypatch.setenv("DATA_PATH", "/tmp/test_data")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


# ============================================================================
# Strategy Fixtures
# ============================================================================


@pytest.fixture
def strategy_config() -> Dict[str, Any]:
    """Sample strategy configuration."""
    return {
        "name": "test_strategy",
        "timeframe": "1h",
        "symbols": ["BTC/USDT"],
        "parameters": {
            "fast_ma": 10,
            "slow_ma": 20,
            "atr_period": 14,
        },
        "risk_management": {
            "max_risk_percent": 1.0,
            "stop_loss_atr_multiple": 2.0,
            "take_profit_ratio": 2.5,
        },
    }


@pytest.fixture
def backtest_results() -> Dict[str, Any]:
    """Sample backtest results."""
    return {
        "total_return": 0.25,
        "sharpe_ratio": 1.8,
        "max_drawdown": -0.15,
        "win_rate": 0.55,
        "profit_factor": 1.6,
        "total_trades": 50,
        "winning_trades": 27,
        "losing_trades": 23,
        "avg_win": 150.0,
        "avg_loss": -80.0,
        "largest_win": 500.0,
        "largest_loss": -200.0,
    }


# ============================================================================
# Pattern Recognition Fixtures
# ============================================================================


@pytest.fixture
def sample_patterns() -> List[Dict[str, Any]]:
    """Sample pattern recognition results."""
    return [
        {
            "type": "fair_value_gap",
            "timestamp": datetime(2024, 1, 1, 12, 0),
            "high": 50500.0,
            "low": 50200.0,
            "size": 300.0,
            "filled": False,
        },
        {
            "type": "order_block",
            "timestamp": datetime(2024, 1, 1, 14, 0),
            "high": 51000.0,
            "low": 50800.0,
            "zone": "bullish",
            "tested": True,
        },
        {
            "type": "liquidity_pool",
            "timestamp": datetime(2024, 1, 1, 16, 0),
            "level": 51500.0,
            "touches": 3,
            "swept": False,
        },
    ]


# ============================================================================
# Performance Fixtures
# ============================================================================


@pytest.fixture
def mock_metrics() -> Dict[str, float]:
    """Mock performance metrics."""
    return {
        "query_time_ms": 150.0,
        "backtest_time_s": 3.2,
        "pattern_search_time_s": 1.8,
        "websocket_latency_ms": 73.0,
        "memory_usage_mb": 256.0,
        "cpu_usage_percent": 45.0,
    }


# ============================================================================
# Test Data Files
# ============================================================================


@pytest.fixture
def sample_csv_data(tmp_path: Path) -> Path:
    """Create sample CSV file for import testing."""
    csv_path = tmp_path / "sample_data.csv"
    data = {
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="1min"),
        "open": np.random.uniform(49000, 51000, 100),
        "high": np.random.uniform(50000, 52000, 100),
        "low": np.random.uniform(48000, 50000, 100),
        "close": np.random.uniform(49000, 51000, 100),
        "volume": np.random.uniform(100, 1000, 100),
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_path, index=False)
    return csv_path


# ============================================================================
# Cleanup
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup resources after each test."""
    yield
    # Cleanup code runs after each test
    import gc

    gc.collect()
