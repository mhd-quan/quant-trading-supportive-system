"""VWAP Pullback scalping strategy."""

from typing import List, Dict, Any
import pandas as pd
import numpy as np
from loguru import logger

from src.strategies.base import BaseStrategy, Signal, SignalType
from src.analytics.indicators.technical import TechnicalIndicators


class VWAPPullbackStrategy(BaseStrategy):
    """Entry on VWAP touch with momentum confirmation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize VWAP Pullback strategy.

        Args:
            config: Strategy configuration
        """
        super().__init__(name="VWAP Pullback", config=config)
        self.ema_period = config.get("confirmation_ema_period", 9)
        self.volume_threshold = config.get("volume_threshold_zscore", 2.0)
        self.min_distance_pct = config.get("min_vwap_distance_percent", 0.1)
        self.max_distance_pct = config.get("max_vwap_distance_percent", 0.5)
        self.stop_atr_multiple = config.get("stop_loss_atr_multiple", 1.5)
        self.tp_atr_multiple = config.get("take_profit_atr_multiple", 3.0)

    def validate_config(self) -> bool:
        """Validate configuration."""
        return all(
            [
                self.ema_period > 0,
                self.volume_threshold > 0,
                self.min_distance_pct >= 0,
                self.max_distance_pct > self.min_distance_pct,
            ]
        )

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """Generate VWAP pullback signals.

        Args:
            df: DataFrame with OHLCV data and indicators

        Returns:
            List of trading signals
        """
        if not self.validate_config():
            logger.error("Invalid configuration")
            return []

        if len(df) < 50:
            logger.warning("Insufficient data for strategy")
            return []

        signals = []

        # Add required indicators (call once, extract multiple)
        missing_indicators = []
        if "vwap" not in df.columns:
            missing_indicators.append("vwap")
        if "ema_9" not in df.columns:
            missing_indicators.append("ema_9")
        if "atr_14" not in df.columns:
            missing_indicators.append("atr_14")

        if missing_indicators:
            df_with_indicators = TechnicalIndicators.add_all_indicators(df)
            for indicator in missing_indicators:
                if indicator in df_with_indicators.columns:
                    df[indicator] = df_with_indicators[indicator]

        # Volume z-score
        vol_mean = df["volume"].rolling(window=20).mean()
        vol_std = df["volume"].rolling(window=20).std()
        df["volume_zscore"] = (df["volume"] - vol_mean) / vol_std

        # EMA slope (momentum)
        df["ema_slope"] = df["ema_9"].diff()

        for i in range(50, len(df)):
            current = df.iloc[i]
            prev = df.iloc[i - 1]

            if pd.isna(current["vwap"]) or pd.isna(current["atr_14"]):
                continue

            # Distance from VWAP
            distance_pct = abs(current["close"] - current["vwap"]) / current["vwap"] * 100

            # Skip if not within target range
            if not (self.min_distance_pct <= distance_pct <= self.max_distance_pct):
                continue

            # Bullish signal: Price touches VWAP from below with momentum
            if (
                current["low"] <= current["vwap"]
                and current["close"] > current["vwap"]
                and current["ema_slope"] > 0
                and current["volume_zscore"] > self.volume_threshold
            ):
                entry_price = current["close"]
                stop_loss = entry_price - (current["atr_14"] * self.stop_atr_multiple)
                take_profit = entry_price + (current["atr_14"] * self.tp_atr_multiple)

                # Calculate confidence based on volume and momentum (normalized properly)
                volume_factor = min(1.0, current["volume_zscore"] / 3) if current["volume_zscore"] > 0 else 0
                # Normalize momentum by EMA value instead of close price
                momentum_factor = min(1.0, abs(current["ema_slope"]) / (current["ema_9"] * 0.01)) if current["ema_9"] > 0 else 0
                confidence = 0.6 * volume_factor + 0.4 * momentum_factor

                signals.append(
                    Signal(
                        timestamp=current["timestamp"],
                        signal_type=SignalType.LONG,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=confidence,
                        timeframe=df.iloc[0].get("timeframe", "1m"),
                        reason=f"VWAP pullback long: distance={distance_pct:.2f}%, vol_z={current['volume_zscore']:.2f}",
                        metadata={
                            "vwap": current["vwap"],
                            "ema_9": current["ema_9"],
                            "volume_zscore": current["volume_zscore"],
                        },
                    )
                )

            # Bearish signal: Price touches VWAP from above with momentum
            if (
                current["high"] >= current["vwap"]
                and current["close"] < current["vwap"]
                and current["ema_slope"] < 0
                and current["volume_zscore"] > self.volume_threshold
            ):
                entry_price = current["close"]
                stop_loss = entry_price + (current["atr_14"] * self.stop_atr_multiple)
                take_profit = entry_price - (current["atr_14"] * self.tp_atr_multiple)

                # Calculate confidence based on volume and momentum (normalized properly)
                volume_factor = min(1.0, current["volume_zscore"] / 3) if current["volume_zscore"] > 0 else 0
                # Normalize momentum by EMA value instead of close price
                momentum_factor = min(1.0, abs(current["ema_slope"]) / (current["ema_9"] * 0.01)) if current["ema_9"] > 0 else 0
                confidence = 0.6 * volume_factor + 0.4 * momentum_factor

                signals.append(
                    Signal(
                        timestamp=current["timestamp"],
                        signal_type=SignalType.SHORT,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=confidence,
                        timeframe=df.iloc[0].get("timeframe", "1m"),
                        reason=f"VWAP pullback short: distance={distance_pct:.2f}%, vol_z={current['volume_zscore']:.2f}",
                        metadata={
                            "vwap": current["vwap"],
                            "ema_9": current["ema_9"],
                            "volume_zscore": current["volume_zscore"],
                        },
                    )
                )

        self.signals = signals

        if len(signals) == 0:
            logger.warning(
                f"No VWAP pullback signals generated. "
                f"Data length: {len(df)}, "
                f"Volume threshold: {self.volume_threshold}. "
                f"Possible reasons: No VWAP touches, volume too low, "
                f"or distance from VWAP out of range "
                f"({self.min_distance_pct}%-{self.max_distance_pct}%)"
            )
        else:
            logger.info(f"Generated {len(signals)} VWAP pullback signals")

        return signals
