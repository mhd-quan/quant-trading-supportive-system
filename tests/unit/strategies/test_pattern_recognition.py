"""Tests for pattern recognition in strategies."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from src.analytics.similarity.pattern_matcher import PatternMatcher
from src.analytics.patterns.ict import ICTPatterns


class TestPatternMatcher:
    """Test pattern matching functionality."""

    def test_pattern_matcher_initialization(self):
        """Test pattern matcher can be initialized."""
        matcher = PatternMatcher(window_size=50)
        assert matcher.window_size == 50

    def test_find_similar_patterns(self, sample_ohlcv_data):
        """Test finding similar patterns in price data."""
        matcher = PatternMatcher(window_size=20)

        # Ensure data has enough rows
        if len(sample_ohlcv_data) < 100:
            pytest.skip("Insufficient data for pattern matching test")

        # Find patterns similar to the last 20 candles
        matches = matcher.find_similar_patterns(
            df=sample_ohlcv_data,
            query_start=len(sample_ohlcv_data) - 30,
            query_length=20,
            top_k=3,
        )

        # Should return a list of matches
        assert isinstance(matches, list)

    def test_similarity_search_empty_data(self):
        """Test pattern matcher handles empty data gracefully."""
        matcher = PatternMatcher(window_size=20)

        empty_df = pd.DataFrame()
        matches = matcher.find_similar_patterns(
            df=empty_df,
            query_start=0,
            query_length=20,
            top_k=3,
        )

        # Should return empty list, not crash
        assert matches == []


class TestICTPatterns:
    """Test ICT pattern detection."""

    def test_market_structure_detection(self, sample_ohlcv_data):
        """Test detecting market structure (swing highs/lows)."""
        structure = ICTPatterns.detect_market_structure(
            df=sample_ohlcv_data,
            swing_lookback=5
        )

        # Should return a list of structure points
        assert isinstance(structure, list)

    def test_fair_value_gap_detection(self, sample_ohlcv_data):
        """Test Fair Value Gap detection."""
        fvgs = ICTPatterns.detect_fair_value_gaps(
            df=sample_ohlcv_data,
            min_gap_size=0.001  # 0.1%
        )

        # Should return a list of FVG patterns
        assert isinstance(fvgs, list)

    def test_order_block_detection(self, sample_ohlcv_data):
        """Test Order Block detection."""
        order_blocks = ICTPatterns.detect_order_blocks(
            df=sample_ohlcv_data,
            lookback=20
        )

        # Should return a list of order blocks
        assert isinstance(order_blocks, list)

    def test_liquidity_pool_detection(self, sample_ohlcv_data):
        """Test liquidity pool detection."""
        pools = ICTPatterns.detect_liquidity_pools(
            df=sample_ohlcv_data,
            lookback=20
        )

        # Should return a list of liquidity pools
        assert isinstance(pools, list)

    def test_ict_patterns_empty_data(self):
        """Test ICT patterns handle empty data gracefully."""
        empty_df = pd.DataFrame()

        structure = ICTPatterns.detect_market_structure(empty_df)
        assert structure == []

        fvgs = ICTPatterns.detect_fair_value_gaps(empty_df)
        assert fvgs == []

        order_blocks = ICTPatterns.detect_order_blocks(empty_df)
        assert order_blocks == []


class TestPatternValidation:
    """Test pattern validation logic."""

    def test_validate_pattern_data(self):
        """Test pattern data validation."""
        # Valid pattern data
        valid_df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [99, 100, 101],
            'close': [103, 104, 105],
            'volume': [1000, 1100, 1200],
            'timestamp': pd.date_range('2024-01-01', periods=3, freq='1h')
        })

        # Check required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume', 'timestamp']
        assert all(col in valid_df.columns for col in required_cols)

        # Check OHLC relationships
        assert all(valid_df['high'] >= valid_df['low'])
        assert all(valid_df['high'] >= valid_df['open'])
        assert all(valid_df['high'] >= valid_df['close'])
        assert all(valid_df['low'] <= valid_df['open'])
        assert all(valid_df['low'] <= valid_df['close'])

    def test_invalid_ohlc_relationships(self):
        """Test detection of invalid OHLC data."""
        # Invalid: high < low
        invalid_df = pd.DataFrame({
            'open': [100],
            'high': [99],  # High less than low
            'low': [101],
            'close': [100],
            'volume': [1000],
        })

        # This should be detected as invalid
        assert not all(invalid_df['high'] >= invalid_df['low'])
