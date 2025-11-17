"""Simple backtest engine for strategy evaluation."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from loguru import logger

from src.strategies.base import Signal, SignalType


@dataclass
class Trade:
    """Trade record."""

    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    commission: float
    reason: str


@dataclass
class BacktestResults:
    """Backtest results container."""

    trades: List[Trade]
    equity_curve: pd.Series
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float


class SimpleBacktestEngine:
    """Simple backtesting engine."""

    def __init__(
        self,
        initial_capital: float = 10000,
        commission: float = 0.001,
        slippage: float = 0.0005,
    ):
        """Initialize backtest engine.

        Args:
            initial_capital: Starting capital
            commission: Commission rate (0.001 = 0.1%)
            slippage: Slippage rate (0.0005 = 0.05%)
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(
        self,
        df: pd.DataFrame,
        signals: List[Signal],
        risk_per_trade: float = 0.02,
    ) -> BacktestResults:
        """Run backtest on signals.

        Args:
            df: DataFrame with OHLCV data
            signals: List of trading signals
            risk_per_trade: Risk per trade as fraction of capital

        Returns:
            Backtest results
        """
        if not signals:
            logger.warning("No signals provided")
            return self._empty_results()

        trades = []
        capital = self.initial_capital
        equity_curve = [capital]
        timestamps = [df.iloc[0]["timestamp"]]

        # Sort signals by timestamp
        signals = sorted(signals, key=lambda x: x.timestamp)

        for signal in signals:
            # Find signal in dataframe
            signal_idx = df[df["timestamp"] == signal.timestamp].index
            if len(signal_idx) == 0:
                continue

            signal_idx = signal_idx[0]

            # Calculate position size
            entry_price = signal.entry_price
            stop_price = signal.stop_loss
            risk_amount = capital * risk_per_trade
            stop_distance = abs(entry_price - stop_price)

            if stop_distance == 0:
                continue

            position_size = risk_amount / stop_distance
            quantity = position_size / entry_price

            # Apply slippage to entry
            if signal.signal_type == SignalType.LONG:
                actual_entry = entry_price * (1 + self.slippage)
            else:
                actual_entry = entry_price * (1 - self.slippage)

            # Simulate trade execution
            exit_price = None
            exit_time = None
            exit_reason = ""

            # Look forward to find exit
            future_data = df.iloc[signal_idx + 1 :]

            for idx, row in future_data.iterrows():
                # Check stop loss
                if signal.signal_type == SignalType.LONG:
                    if row["low"] <= signal.stop_loss:
                        exit_price = signal.stop_loss
                        exit_time = row["timestamp"]
                        exit_reason = "stop_loss"
                        break
                    elif row["high"] >= signal.take_profit:
                        exit_price = signal.take_profit
                        exit_time = row["timestamp"]
                        exit_reason = "take_profit"
                        break
                else:  # SHORT
                    if row["high"] >= signal.stop_loss:
                        exit_price = signal.stop_loss
                        exit_time = row["timestamp"]
                        exit_reason = "stop_loss"
                        break
                    elif row["low"] <= signal.take_profit:
                        exit_price = signal.take_profit
                        exit_time = row["timestamp"]
                        exit_reason = "take_profit"
                        break

            if exit_price is None:
                # Use last price if no exit found
                exit_price = future_data.iloc[-1]["close"] if len(future_data) > 0 else entry_price
                exit_time = future_data.iloc[-1]["timestamp"] if len(future_data) > 0 else signal.timestamp
                exit_reason = "end_of_data"

            # Apply slippage to exit
            if signal.signal_type == SignalType.LONG:
                actual_exit = exit_price * (1 - self.slippage)
            else:
                actual_exit = exit_price * (1 + self.slippage)

            # Calculate P&L
            if signal.signal_type == SignalType.LONG:
                pnl_raw = (actual_exit - actual_entry) * quantity
            else:
                pnl_raw = (actual_entry - actual_exit) * quantity

            # Subtract commission
            commission_cost = (
                actual_entry * quantity * self.commission
                + actual_exit * quantity * self.commission
            )
            pnl_net = pnl_raw - commission_cost
            pnl_percent = (pnl_net / (actual_entry * quantity)) * 100

            # Update capital
            capital += pnl_net

            # Record trade
            trades.append(
                Trade(
                    entry_time=signal.timestamp,
                    exit_time=exit_time,
                    direction="long" if signal.signal_type == SignalType.LONG else "short",
                    entry_price=actual_entry,
                    exit_price=actual_exit,
                    quantity=quantity,
                    pnl=pnl_net,
                    pnl_percent=pnl_percent,
                    commission=commission_cost,
                    reason=exit_reason,
                )
            )

            equity_curve.append(capital)
            timestamps.append(exit_time)

        # Calculate metrics
        return self._calculate_results(trades, equity_curve, timestamps)

    def _calculate_results(
        self, trades: List[Trade], equity_curve: List[float], timestamps: List
    ) -> BacktestResults:
        """Calculate backtest statistics."""
        if not trades:
            return self._empty_results()

        equity_series = pd.Series(equity_curve, index=timestamps)

        # Returns
        returns = equity_series.pct_change().dropna()
        total_return = ((equity_curve[-1] - self.initial_capital) / self.initial_capital) * 100

        # Sharpe ratio (annualized)
        sharpe = (
            (returns.mean() / returns.std()) * np.sqrt(252)
            if returns.std() > 0
            else 0
        )

        # Max drawdown
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()

        # Trade statistics
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]

        win_rate = len(winning) / len(trades) * 100 if trades else 0
        avg_win = sum(t.pnl for t in winning) / len(winning) if winning else 0
        avg_loss = sum(t.pnl for t in losing) / len(losing) if losing else 0

        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        return BacktestResults(
            trades=trades,
            equity_curve=equity_series,
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=max((t.pnl for t in winning), default=0),
            largest_loss=min((t.pnl for t in losing), default=0),
        )

    def _empty_results(self) -> BacktestResults:
        """Return empty results."""
        return BacktestResults(
            trades=[],
            equity_curve=pd.Series([self.initial_capital]),
            total_return=0,
            sharpe_ratio=0,
            max_drawdown=0,
            win_rate=0,
            profit_factor=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_win=0,
            avg_loss=0,
            largest_win=0,
            largest_loss=0,
        )
