"""Base strategy class and common structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import pandas as pd


class SignalType(str, Enum):
    """Trading signal types."""

    LONG = "long"
    SHORT = "short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"


@dataclass
class Signal:
    """Trading signal."""

    timestamp: datetime
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # 0-1
    timeframe: str
    reason: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TimeframeRecommendation:
    """Timeframe recommendation with scoring."""

    timeframe: str
    score: float
    trend_efficiency: float
    volume_score: float
    slippage_penalty: float
    liquidity_score: float
    reasoning: str


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize strategy.

        Args:
            name: Strategy name
            config: Strategy configuration
        """
        self.name = name
        self.config = config or {}
        self.signals: List[Signal] = []

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """Generate trading signals from data.

        Args:
            df: DataFrame with OHLCV and indicator data

        Returns:
            List of signals
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate strategy configuration.

        Returns:
            True if configuration is valid
        """
        pass

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_price: float,
        leverage: float = 1.0,
        atr: Optional[float] = None,
        max_atr_multiple: float = 5.0,
        min_atr_multiple: float = 0.5,
    ) -> Dict[str, float]:
        """Calculate position size using fixed risk.

        Args:
            account_balance: Account balance
            risk_percent: Risk percentage (0-1)
            entry_price: Entry price
            stop_price: Stop loss price
            leverage: Leverage multiplier
            atr: Optional ATR value for validation
            max_atr_multiple: Maximum stop distance as ATR multiple
            min_atr_multiple: Minimum stop distance as ATR multiple

        Returns:
            Dictionary with position sizing info
        """
        risk_amount = account_balance * risk_percent
        stop_distance = abs(entry_price - stop_price)

        # Division by zero guard
        if entry_price == 0:
            return {
                "position_size": 0,
                "quantity": 0,
                "risk_amount": risk_amount,
                "stop_distance": stop_distance,
                "stop_percent": 0,
                "warnings": ["Entry price is zero"],
            }

        stop_percent = stop_distance / entry_price

        # Validate stop loss against ATR if provided
        warnings = []
        if atr is not None and atr > 0:
            atr_multiple = stop_distance / atr
            if atr_multiple > max_atr_multiple:
                warnings.append(f"Stop loss too wide: {atr_multiple:.2f}x ATR (max {max_atr_multiple}x)")
            elif atr_multiple < min_atr_multiple:
                warnings.append(f"Stop loss too tight: {atr_multiple:.2f}x ATR (min {min_atr_multiple}x)")

        if stop_percent == 0:
            position_size = 0
            quantity = 0
            warnings.append("Stop distance is zero")
        else:
            position_size = risk_amount / stop_percent
            position_size = position_size * leverage  # Apply leverage first
            position_size = min(position_size, account_balance * 0.2)  # Then cap at 20%
            quantity = position_size / entry_price

        return {
            "position_size": position_size,
            "quantity": quantity,
            "risk_amount": risk_amount,
            "stop_distance": stop_distance,
            "stop_percent": stop_percent * 100,
            "warnings": warnings,
        }

    def get_signal_summary(self) -> Dict[str, Any]:
        """Get summary of generated signals.

        Returns:
            Dictionary with signal statistics
        """
        if not self.signals:
            return {"total": 0}

        long_signals = [s for s in self.signals if s.signal_type == SignalType.LONG]
        short_signals = [s for s in self.signals if s.signal_type == SignalType.SHORT]
        avg_confidence = sum(s.confidence for s in self.signals) / len(self.signals)

        return {
            "total": len(self.signals),
            "long": len(long_signals),
            "short": len(short_signals),
            "avg_confidence": avg_confidence,
            "timeframes": list(set(s.timeframe for s in self.signals)),
        }

    @staticmethod
    def select_optimal_timeframe(
        symbol_data: Dict[str, pd.DataFrame],
        risk_percent: float = 1.0,
        max_stop_atr_multiple: float = 3.0,
    ) -> TimeframeRecommendation:
        """Select optimal timeframe based on market conditions.

        Args:
            symbol_data: Dictionary mapping timeframe -> DataFrame
            risk_percent: Risk percentage
            max_stop_atr_multiple: Maximum stop distance as ATR multiple

        Returns:
            Timeframe recommendation
        """
        recommendations = []

        for timeframe, df in symbol_data.items():
            if len(df) < 50:
                continue

            # Calculate trend efficiency (Kaufman Efficiency Ratio)
            change = abs(df["close"].iloc[-1] - df["close"].iloc[-30])
            volatility = abs(df["close"].diff()).iloc[-30:].sum()
            trend_efficiency = change / volatility if volatility > 0 else 0

            # Volume score (z-score)
            vol_mean = df["volume"].iloc[-30:].mean()
            vol_std = df["volume"].iloc[-30:].std()
            recent_vol = df["volume"].iloc[-10:].mean()
            volume_score = (
                (recent_vol - vol_mean) / vol_std if vol_std > 0 else 0
            )
            volume_score = max(0, min(volume_score, 3)) / 3  # Normalize 0-1

            # Slippage penalty (estimate from spread)
            spread = (df["high"] - df["low"]).iloc[-20:].mean()
            avg_price = df["close"].iloc[-20:].mean()
            slippage_penalty = (spread / avg_price) if avg_price > 0 else 1

            # Liquidity score (inverse of slippage, normalized 0-1)
            liquidity_score = 1 - min(slippage_penalty * 10, 1)

            # Combined score (weights sum to 1.0, no double-counting)
            score = (
                0.4 * trend_efficiency
                + 0.3 * volume_score
                + 0.3 * liquidity_score
            )

            reasoning = (
                f"Trend efficiency: {trend_efficiency:.2f}, "
                f"Volume score: {volume_score:.2f}, "
                f"Slippage: {slippage_penalty:.4f}, "
                f"Liquidity: {liquidity_score:.2f}"
            )

            recommendations.append(
                TimeframeRecommendation(
                    timeframe=timeframe,
                    score=score,
                    trend_efficiency=trend_efficiency,
                    volume_score=volume_score,
                    slippage_penalty=slippage_penalty,
                    liquidity_score=liquidity_score,
                    reasoning=reasoning,
                )
            )

        if not recommendations:
            return TimeframeRecommendation(
                timeframe="1h",
                score=0,
                trend_efficiency=0,
                volume_score=0,
                slippage_penalty=1,
                liquidity_score=0,
                reasoning="Insufficient data",
            )

        # Return best timeframe
        return max(recommendations, key=lambda x: x.score)
