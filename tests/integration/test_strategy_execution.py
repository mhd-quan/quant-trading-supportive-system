"""Integration tests for strategy execution."""

import pytest
import pandas as pd

from src.strategies.base import BaseStrategy
from src.backtesting.engine import BacktestEngine


@pytest.mark.integration
class TestStrategyExecution:
    """Test end-to-end strategy execution."""

    def test_strategy_backtest_pipeline(self, sample_ohlcv_data, strategy_config):
        """Test complete strategy backtest pipeline."""
        from src.strategies.quant.momentum import MomentumStrategy

        # Initialize strategy
        strategy = MomentumStrategy(config=strategy_config)

        # Run backtest
        engine = BacktestEngine(
            strategy=strategy,
            data=sample_ohlcv_data,
            initial_capital=10000.0,
            commission=0.001,
        )

        results = engine.run()

        # Verify results
        assert "total_return" in results
        assert "sharpe_ratio" in results
        assert "max_drawdown" in results
        assert results["total_trades"] >= 0

    def test_strategy_signal_generation(self, sample_ohlcv_data, strategy_config):
        """Test strategy generates valid trading signals."""
        from src.strategies.scalping.vwap_pullback import VWAPPullbackStrategy

        strategy = VWAPPullbackStrategy(config=strategy_config)
        signals = strategy.generate_signals(sample_ohlcv_data)

        assert isinstance(signals, pd.DataFrame)
        assert "signal" in signals.columns
        assert signals["signal"].isin([-1, 0, 1]).all()

    def test_multi_timeframe_strategy(self, sample_ohlcv_data):
        """Test strategy using multiple timeframes."""
        from src.strategies.ict.structure_trading import StructureTradingStrategy
        from src.data.processors import TimeframeAggregator

        aggregator = TimeframeAggregator()

        # Create multi-timeframe data
        data_1h = aggregator.aggregate(sample_ohlcv_data, "1m", "1h")
        data_4h = aggregator.aggregate(sample_ohlcv_data, "1m", "4h")

        strategy = StructureTradingStrategy(
            config={
                "timeframes": {"htf": "4h", "ltf": "1h"},
                "parameters": {},
            }
        )

        signals = strategy.analyze_multi_timeframe(
            htf_data=data_4h,
            ltf_data=data_1h,
        )

        assert isinstance(signals, pd.DataFrame)

    def test_strategy_risk_management(self, sample_ohlcv_data, strategy_config):
        """Test strategy risk management rules."""
        from src.strategies.quant.momentum import MomentumStrategy
        from src.risk.position_sizer import PositionSizer

        strategy = MomentumStrategy(config=strategy_config)
        sizer = PositionSizer(
            account_balance=10000.0,
            risk_per_trade=0.01,
        )

        # Generate signal
        signals = strategy.generate_signals(sample_ohlcv_data)
        signal_row = signals[signals["signal"] != 0].iloc[0]

        # Calculate position size
        position_size = sizer.calculate_size(
            entry_price=signal_row["close"],
            stop_loss=signal_row["stop_loss"],
        )

        assert position_size > 0
        assert position_size <= 10000.0  # Can't exceed account balance

    def test_strategy_portfolio_integration(self, sample_ohlcv_data):
        """Test multiple strategies in a portfolio."""
        from src.strategies.quant.momentum import MomentumStrategy
        from src.strategies.quant.mean_reversion import MeanReversionStrategy
        from src.portfolio.manager import PortfolioManager

        strategies = [
            MomentumStrategy(config={"name": "momentum"}),
            MeanReversionStrategy(config={"name": "mean_reversion"}),
        ]

        portfolio = PortfolioManager(
            strategies=strategies,
            capital=10000.0,
            max_positions=5,
        )

        # Run portfolio
        results = portfolio.run_backtest(sample_ohlcv_data)

        assert "total_return" in results
        assert "strategy_allocations" in results


@pytest.mark.integration
class TestStrategyOptimization:
    """Test strategy parameter optimization."""

    def test_parameter_grid_search(self, sample_ohlcv_data):
        """Test grid search parameter optimization."""
        from src.backtesting.optimizer import GridSearchOptimizer
        from src.strategies.quant.momentum import MomentumStrategy

        optimizer = GridSearchOptimizer(
            strategy_class=MomentumStrategy,
            parameter_grid={
                "fast_ma": [10, 20, 30],
                "slow_ma": [50, 100, 200],
            },
        )

        best_params = optimizer.optimize(
            data=sample_ohlcv_data,
            objective="sharpe_ratio",
        )

        assert "fast_ma" in best_params
        assert "slow_ma" in best_params
        assert best_params["fast_ma"] < best_params["slow_ma"]

    def test_walk_forward_analysis(self, sample_ohlcv_data):
        """Test walk-forward optimization."""
        from src.backtesting.walk_forward import WalkForwardAnalyzer
        from src.strategies.quant.momentum import MomentumStrategy

        analyzer = WalkForwardAnalyzer(
            strategy_class=MomentumStrategy,
            in_sample_ratio=0.7,
            num_periods=3,
        )

        results = analyzer.analyze(sample_ohlcv_data)

        assert "in_sample_results" in results
        assert "out_of_sample_results" in results
        assert len(results["periods"]) == 3
