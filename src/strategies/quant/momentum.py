"""Dual moving average momentum strategy with KAMA confirmation."""

from typing import List, Dict, Any
import pandas as pd
from loguru import logger

from src.strategies.base import BaseStrategy, Signal, SignalType
from src.analytics.indicators.technical import TechnicalIndicators
import pandas_ta as ta_lib


class MomentumStrategy(BaseStrategy):
    """Momentum strategy with dual MA crossover and KAMA filter."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Momentum strategy."""
        super().__init__(name="Momentum", config=config)
        self.fast_ma = config.get("fast_ma_period", 20)
        self.slow_ma = config.get("slow_ma_period", 50)
        self.kama_period = config.get("kama_period", 10)
        self.min_efficiency = config.get("min_kama_efficiency", 0.3)
        self.atr_multiple = config.get("atr_trailing_multiplier", 2.5)

    def validate_config(self) -> bool:
        """Validate configuration."""
        return self.fast_ma < self.slow_ma and self.min_efficiency > 0

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """Generate momentum signals."""
        if not self.validate_config():
            return []

        if len(df) < max(self.slow_ma, 50):
            logger.warning("Insufficient data")
            return []

        signals = []

        # Add indicators with configured periods
        if f"ema_{self.fast_ma}" not in df.columns:
            df["fast_ema"] = ta_lib.ema(df["close"], length=self.fast_ma)
        else:
            df["fast_ema"] = df[f"ema_{self.fast_ma}"]

        if f"ema_{self.slow_ma}" not in df.columns:
            df["slow_ema"] = ta_lib.ema(df["close"], length=self.slow_ma)
        else:
            df["slow_ema"] = df[f"ema_{self.slow_ma}"]

        df["kama"] = TechnicalIndicators.calculate_kama(df["close"], period=self.kama_period)

        if "atr_14" not in df.columns:
            atr = ta_lib.atr(df["high"], df["low"], df["close"], length=14)
            df["atr"] = atr if atr is not None else 0
        else:
            df["atr"] = df["atr_14"]

        # Calculate KAMA efficiency (aligned with KAMA calculation)
        change = abs(df["close"] - df["close"].shift(self.kama_period))
        volatility = abs(df["close"].diff()).rolling(window=self.kama_period).sum()
        df["efficiency"] = change / volatility

        for i in range(max(self.slow_ma, self.kama_period) + 1, len(df)):
            current = df.iloc[i]
            prev = df.iloc[i - 1]

            if pd.isna(current["efficiency"]) or pd.isna(current["atr"]):
                continue

            # Skip low efficiency markets
            if current["efficiency"] < self.min_efficiency:
                continue

            # Bullish crossover
            if (
                prev["fast_ema"] <= prev["slow_ema"]
                and current["fast_ema"] > current["slow_ema"]
                and current["close"] > current["kama"]
            ):
                entry_price = current["close"]
                stop_loss = entry_price - (current["atr"] * self.atr_multiple)
                take_profit = entry_price + (current["atr"] * self.atr_multiple * 2)

                signals.append(
                    Signal(
                        timestamp=current["timestamp"],
                        signal_type=SignalType.LONG,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=current["efficiency"],
                        timeframe=df.iloc[0].get("timeframe", "1h"),
                        reason=f"Bullish MA crossover, efficiency={current['efficiency']:.2f}",
                    )
                )

            # Bearish crossover
            if (
                prev["fast_ema"] >= prev["slow_ema"]
                and current["fast_ema"] < current["slow_ema"]
                and current["close"] < current["kama"]
            ):
                entry_price = current["close"]
                stop_loss = entry_price + (current["atr"] * self.atr_multiple)
                take_profit = entry_price - (current["atr"] * self.atr_multiple * 2)

                signals.append(
                    Signal(
                        timestamp=current["timestamp"],
                        signal_type=SignalType.SHORT,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=current["efficiency"],
                        timeframe=df.iloc[0].get("timeframe", "1h"),
                        reason=f"Bearish MA crossover, efficiency={current['efficiency']:.2f}",
                    )
                )

        self.signals = signals

        if len(signals) == 0:
            logger.warning(
                f"No momentum signals generated. "
                f"Data length: {len(df)}, "
                f"Min efficiency threshold: {self.min_efficiency}. "
                f"Possible reasons: No MA crossovers, efficiency too low, "
                f"or price not aligned with KAMA"
            )
        else:
            logger.info(f"Generated {len(signals)} momentum signals")

        return signals
