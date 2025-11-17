"""Tests for base strategy functionality."""

import pytest
from src.strategies.base import BaseStrategy, Signal, SignalType
from datetime import datetime, timezone


def test_position_size_calculation():
    """Test position sizing calculation."""

    class DummyStrategy(BaseStrategy):
        def generate_signals(self, df):
            return []

        def validate_config(self):
            return True

    strategy = DummyStrategy("test", {})

    result = strategy.calculate_position_size(
        account_balance=10000,
        risk_percent=0.02,  # 2%
        entry_price=100,
        stop_price=98,  # 2% stop
        leverage=1.0,
    )

    assert result["position_size"] > 0
    assert result["quantity"] > 0
    assert result["risk_amount"] == 200  # 2% of 10000


def test_signal_summary():
    """Test signal summary generation."""

    class DummyStrategy(BaseStrategy):
        def generate_signals(self, df):
            return []

        def validate_config(self):
            return True

    strategy = DummyStrategy("test", {})

    # Add some signals
    strategy.signals = [
        Signal(
            timestamp=datetime.now(),
            signal_type=SignalType.LONG,
            entry_price=100,
            stop_loss=98,
            take_profit=104,
            confidence=0.8,
            timeframe="1h",
            reason="test",
        ),
        Signal(
            timestamp=datetime.now(),
            signal_type=SignalType.SHORT,
            entry_price=100,
            stop_loss=102,
            take_profit=96,
            confidence=0.7,
            timeframe="1h",
            reason="test",
        ),
    ]

    summary = strategy.get_signal_summary()

    assert summary["total"] == 2
    assert summary["long"] == 1
    assert summary["short"] == 1
    assert 0.7 <= summary["avg_confidence"] <= 0.8
