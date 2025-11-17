"""Tests for pattern recognition in strategies."""

import pytest
import pandas as pd
import numpy as np

from src.analytics.patterns.matrix_profile import MatrixProfileAnalyzer
from src.analytics.patterns.ict_structures import ICTStructureAnalyzer


class TestMatrixProfile:
    """Test matrix profile pattern recognition."""

    def test_matrix_profile_calculation(self, sample_ohlcv_data):
        """Test matrix profile calculation."""
        analyzer = MatrixProfileAnalyzer(window_size=50)

        mp = analyzer.calculate(sample_ohlcv_data["close"])

        assert len(mp) == len(sample_ohlcv_data) - 50 + 1
        assert not np.isnan(mp).all()

    def test_motif_discovery(self, sample_ohlcv_data):
        """Test discovering recurring patterns."""
        analyzer = MatrixProfileAnalyzer(window_size=20)

        motifs = analyzer.find_motifs(
            data=sample_ohlcv_data["close"],
            num_motifs=3,
        )

        assert len(motifs) > 0
        assert "index" in motifs[0]
        assert "distance" in motifs[0]

    def test_discord_detection(self, sample_ohlcv_data):
        """Test anomaly (discord) detection."""
        analyzer = MatrixProfileAnalyzer(window_size=20)

        # Add an obvious anomaly
        data = sample_ohlcv_data.copy()
        data.loc[500, "close"] = data["close"].mean() * 2

        discords = analyzer.find_discords(
            data=data["close"],
            num_discords=1,
        )

        assert len(discords) > 0
        # Should detect the anomaly near index 500
        assert any(abs(d["index"] - 500) < 20 for d in discords)


class TestICTStructures:
    """Test ICT structure analysis."""

    def test_fair_value_gap_detection(self, sample_ohlcv_data):
        """Test fair value gap detection."""
        analyzer = ICTStructureAnalyzer()

        fvgs = analyzer.find_fair_value_gaps(sample_ohlcv_data)

        assert isinstance(fvgs, list)
        if len(fvgs) > 0:
            assert "type" in fvgs[0]
            assert "high" in fvgs[0]
            assert "low" in fvgs[0]

    def test_order_block_identification(self, sample_ohlcv_data):
        """Test order block identification."""
        analyzer = ICTStructureAnalyzer()

        order_blocks = analyzer.find_order_blocks(sample_ohlcv_data)

        assert isinstance(order_blocks, list)
        if len(order_blocks) > 0:
            assert "zone" in order_blocks[0]  # bullish or bearish
            assert "high" in order_blocks[0]
            assert "low" in order_blocks[0]

    def test_liquidity_pool_detection(self, sample_ohlcv_data):
        """Test liquidity pool detection."""
        analyzer = ICTStructureAnalyzer()

        liquidity_pools = analyzer.find_liquidity_pools(
            data=sample_ohlcv_data,
            lookback=50,
        )

        assert isinstance(liquidity_pools, list)
        if len(liquidity_pools) > 0:
            assert "level" in liquidity_pools[0]
            assert "touches" in liquidity_pools[0]

    def test_market_structure_shift(self, sample_ohlcv_data):
        """Test market structure shift detection."""
        analyzer = ICTStructureAnalyzer()

        shifts = analyzer.detect_structure_shifts(sample_ohlcv_data)

        assert isinstance(shifts, list)
        if len(shifts) > 0:
            assert "type" in shifts[0]  # BOS or MSS
            assert "index" in shifts[0]

    def test_optimal_trade_entry_zones(self, sample_ohlcv_data):
        """Test OTE (Optimal Trade Entry) zone calculation."""
        analyzer = ICTStructureAnalyzer()

        # Create a clear impulse move
        data = sample_ohlcv_data.copy()
        data.loc[100:110, "close"] = np.linspace(
            data.loc[100, "close"],
            data.loc[100, "close"] * 1.05,
            11
        )

        ote_zones = analyzer.calculate_ote_zones(
            data=data,
            start_idx=100,
            end_idx=110,
        )

        assert "fib_0.62" in ote_zones
        assert "fib_0.79" in ote_zones
        assert ote_zones["fib_0.62"] < ote_zones["fib_0.79"]


class TestDTWPatternMatching:
    """Test Dynamic Time Warping pattern matching."""

    def test_dtw_distance_calculation(self):
        """Test DTW distance between two series."""
        from src.analytics.patterns.dtw import calculate_dtw_distance

        series1 = np.array([1, 2, 3, 4, 5])
        series2 = np.array([1.1, 2.1, 3.1, 4.1, 5.1])

        distance = calculate_dtw_distance(series1, series2)

        assert distance >= 0
        assert distance < 1.0  # Should be small for similar series

    def test_find_similar_patterns(self, sample_ohlcv_data):
        """Test finding similar historical patterns."""
        from src.analytics.patterns.dtw import PatternMatcher

        matcher = PatternMatcher(window_size=20)

        # Use recent 20 bars as query pattern
        query_pattern = sample_ohlcv_data["close"].iloc[-20:].values

        # Find similar patterns in history
        similar_patterns = matcher.find_similar(
            query=query_pattern,
            data=sample_ohlcv_data["close"].values,
            top_k=5,
        )

        assert len(similar_patterns) > 0
        assert "index" in similar_patterns[0]
        assert "distance" in similar_patterns[0]

    def test_pattern_classification(self):
        """Test pattern classification (e.g., V-bottom, head-shoulders)."""
        from src.analytics.patterns.classifier import PatternClassifier

        classifier = PatternClassifier()

        # Create a V-shaped pattern
        v_pattern = np.concatenate([
            np.linspace(100, 50, 10),
            np.linspace(50, 100, 10),
        ])

        pattern_type = classifier.classify(v_pattern)

        assert pattern_type in ["v_bottom", "v_top", "consolidation", "trend"]
