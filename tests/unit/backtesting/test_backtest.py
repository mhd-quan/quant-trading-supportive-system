"""Tests for backtesting engine."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from src.backtesting.engines.simple_backtest import SimpleBacktestEngine
from src.strategies.base import Signal, SignalType


def test_simple_backtest():
    """Test basic backtest execution."""
    # Create sample OHLCV data
    dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
    np.random.seed(42)

    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": 100 + np.cumsum(np.random.randn(100)),
            "high": 102 + np.cumsum(np.random.randn(100)),
            "low": 98 + np.cumsum(np.random.randn(100)),
            "close": 100 + np.cumsum(np.random.randn(100)),
            "volume": np.random.uniform(1000, 10000, 100),
        }
    )

    # Create test signal
    signals = [
        Signal(
            timestamp=dates[10],
            signal_type=SignalType.LONG,
            entry_price=df.iloc[10]["close"],
            stop_loss=df.iloc[10]["close"] * 0.98,
            take_profit=df.iloc[10]["close"] * 1.04,
            confidence=0.8,
            timeframe="1h",
            reason="test signal",
        )
    ]

    # Run backtest
    engine = SimpleBacktestEngine(initial_capital=10000)
    results = engine.run(df, signals)

    assert results.total_trades >= 0
    assert len(results.equity_curve) > 0
