"""Tests for exchange connectors."""

import pytest
from src.data.connectors.base import ExchangeConnector


def test_timeframe_to_seconds():
    """Test timeframe conversion."""
    assert ExchangeConnector.timeframe_to_seconds("1m") == 60
    assert ExchangeConnector.timeframe_to_seconds("1h") == 3600
    assert ExchangeConnector.timeframe_to_seconds("1d") == 86400
    assert ExchangeConnector.timeframe_to_seconds("1w") == 604800


def test_timeframe_to_milliseconds():
    """Test timeframe conversion to milliseconds."""
    assert ExchangeConnector.timeframe_to_milliseconds("1m") == 60000
    assert ExchangeConnector.timeframe_to_milliseconds("1h") == 3600000
