"""Tests for technical indicators."""

import pytest
import pandas as pd
import numpy as np
from src.analytics.indicators.technical import TechnicalIndicators


def test_kama_calculation():
    """Test KAMA calculation."""
    # Create sample data
    np.random.seed(42)
    close = pd.Series(np.cumsum(np.random.randn(100)) + 100)

    kama = TechnicalIndicators.calculate_kama(close, period=10)

    assert len(kama) == len(close)
    assert not kama.isna().all()  # Should have some non-NaN values


def test_atr_percent():
    """Test ATR percentage calculation."""
    data = {
        "high": [102, 103, 104, 103, 105],
        "low": [98, 99, 100, 99, 101],
        "close": [100, 101, 102, 101, 103],
    }
    df = pd.DataFrame(data)

    atr_pct = TechnicalIndicators.calculate_atr_percent(
        df["high"], df["low"], df["close"], period=3
    )

    assert len(atr_pct) == len(df)
