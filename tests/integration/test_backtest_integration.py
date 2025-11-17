"""Integration tests for backtesting engine."""

import pytest
import pandas as pd
import numpy as np

from src.backtesting.engine import BacktestEngine


@pytest.mark.integration
class TestBacktestIntegration:
    """Test complete backtesting workflows."""

    def test_full_backtest_with_slippage(self, sample_ohlcv_data, strategy_config):
        """Test backtest with realistic slippage modeling."""
        from src.strategies.quant.momentum import MomentumStrategy

        strategy = MomentumStrategy(config=strategy_config)

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
            commission=0.001,
            slippage=0.0005,
        )

        results = engine.run()

        # Verify slippage was applied
        if results["total_trades"] > 0:
            assert results["total_slippage"] > 0
            assert results["net_return"] < results["gross_return"]

    def test_backtest_with_position_sizing(self, sample_ohlcv_data):
        """Test backtest with dynamic position sizing."""
        from src.strategies.quant.momentum import MomentumStrategy
        from src.risk.position_sizer import ATRPositionSizer

        strategy = MomentumStrategy(
            config={"position_sizing": "atr", "risk_percent": 0.02}
        )

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
        )

        results = engine.run()

        # Verify position sizing was applied
        assert "avg_position_size" in results
        assert results["avg_position_size"] > 0

    def test_backtest_performance_metrics(self, sample_ohlcv_data, strategy_config):
        """Test calculation of comprehensive performance metrics."""
        from src.strategies.quant.momentum import MomentumStrategy

        strategy = MomentumStrategy(config=strategy_config)

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
        )

        results = engine.run()
        metrics = engine.calculate_metrics()

        # Verify all key metrics are present
        required_metrics = [
            "total_return",
            "sharpe_ratio",
            "sortino_ratio",
            "max_drawdown",
            "calmar_ratio",
            "win_rate",
            "profit_factor",
            "expectancy",
        ]

        for metric in required_metrics:
            assert metric in metrics

    def test_backtest_trade_logging(self, sample_ohlcv_data, strategy_config):
        """Test detailed trade logging."""
        from src.strategies.quant.momentum import MomentumStrategy

        strategy = MomentumStrategy(config=strategy_config)

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
        )

        results = engine.run()
        trades = engine.get_trades()

        if len(trades) > 0:
            # Verify trade structure
            assert "entry_time" in trades.columns
            assert "exit_time" in trades.columns
            assert "entry_price" in trades.columns
            assert "exit_price" in trades.columns
            assert "pnl" in trades.columns
            assert "return_pct" in trades.columns

    def test_backtest_equity_curve(self, sample_ohlcv_data, strategy_config):
        """Test equity curve generation."""
        from src.strategies.quant.momentum import MomentumStrategy

        strategy = MomentumStrategy(config=strategy_config)

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
        )

        results = engine.run()
        equity_curve = engine.get_equity_curve()

        assert isinstance(equity_curve, pd.DataFrame)
        assert "equity" in equity_curve.columns
        assert len(equity_curve) > 0
        assert equity_curve["equity"].iloc[0] == 10000.0

    def test_monte_carlo_simulation(self, sample_ohlcv_data, strategy_config):
        """Test Monte Carlo simulation for backtest results."""
        from src.strategies.quant.momentum import MomentumStrategy
        from src.backtesting.monte_carlo import MonteCarloSimulator

        strategy = MomentumStrategy(config=strategy_config)

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
        )

        results = engine.run()
        trades = engine.get_trades()

        if len(trades) > 10:  # Need enough trades for MC
            simulator = MonteCarloSimulator(trades=trades)
            mc_results = simulator.run(num_simulations=1000)

            assert "mean_return" in mc_results
            assert "percentile_95" in mc_results
            assert "percentile_5" in mc_results
            assert "probability_profit" in mc_results


@pytest.mark.integration
class TestBacktestRealism:
    """Test realistic backtesting scenarios."""

    def test_market_hours_filter(self, sample_ohlcv_data):
        """Test trading only during specific market hours."""
        from src.strategies.scalping.session_range import SessionRangeStrategy

        strategy = SessionRangeStrategy(
            config={
                "sessions": {
                    "london": {"open_utc": "08:00", "close_utc": "16:00"},
                    "newyork": {"open_utc": "13:00", "close_utc": "20:00"},
                }
            }
        )

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
        )

        results = engine.run()
        trades = engine.get_trades()

        # Verify trades only during specified hours
        if len(trades) > 0:
            for _, trade in trades.iterrows():
                hour = trade["entry_time"].hour
                # Should be within London or NY hours
                assert (8 <= hour < 16) or (13 <= hour < 20)

    def test_realistic_execution_delays(self, sample_ohlcv_data):
        """Test backtest with execution delays."""
        from src.strategies.quant.momentum import MomentumStrategy

        strategy = MomentumStrategy(config={})

        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
            execution_delay_bars=1,  # 1 bar delay
        )

        results = engine.run()

        # Results should account for execution delay
        assert "execution_delay_bars" in results
        assert results["execution_delay_bars"] == 1
