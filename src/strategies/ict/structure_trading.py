"""ICT market structure trading strategy."""

from typing import List, Dict, Any
import pandas as pd
from loguru import logger

from src.strategies.base import BaseStrategy, Signal, SignalType
from src.analytics.patterns.ict import ICTPatterns


class ICTStructureStrategy(BaseStrategy):
    """Multi-timeframe ICT structure analysis strategy."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize ICT Structure strategy."""
        super().__init__(name="ICT Structure", config=config)
        self.min_fvg_atr = config.get("min_gap_atr_multiple", 0.5)
        self.ob_imbalance_ratio = config.get("imbalance_ratio", 3.0)

    def validate_config(self) -> bool:
        """Validate configuration."""
        return self.min_fvg_atr > 0 and self.ob_imbalance_ratio > 0

    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """Generate ICT structure signals."""
        if not self.validate_config() or len(df) < 100:
            return []

        signals = []

        # Detect patterns
        fvgs = ICTPatterns.detect_fair_value_gaps(df, self.min_fvg_atr)
        order_blocks = ICTPatterns.detect_order_blocks(df, self.ob_imbalance_ratio)
        structure_points = ICTPatterns.detect_market_structure(df)

        # Generate signals from order blocks
        for ob in order_blocks[-10:]:  # Last 10 order blocks
            if not ob.valid or ob.idx >= len(df) - 5:
                continue

            # Find if price returned to order block
            future_data = df.iloc[ob.idx + 1 :]
            if len(future_data) == 0:
                continue

            if ob.direction == "bullish":
                # Look for price testing the order block (check if candle overlaps OB range)
                test = future_data[
                    (future_data["low"] <= ob.high) & (future_data["high"] >= ob.low)
                ]
                if len(test) > 0:
                    entry_row = test.iloc[0]
                    entry_price = ob.low  # Enter at support (low of order block)
                    stop_loss = ob.low * 0.995  # Stop just below the order block
                    take_profit = entry_price + (entry_price - stop_loss) * 2

                    signals.append(
                        Signal(
                            timestamp=entry_row["timestamp"],
                            signal_type=SignalType.LONG,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            confidence=min(1.0, ob.strength / 5),
                            timeframe=df.iloc[0].get("timeframe", "15m"),
                            reason=f"Bullish order block test, strength={ob.strength:.2f}",
                        )
                    )

            elif ob.direction == "bearish":
                # Look for price testing the order block (check if candle overlaps OB range)
                test = future_data[
                    (future_data["high"] >= ob.low) & (future_data["low"] <= ob.high)
                ]
                if len(test) > 0:
                    entry_row = test.iloc[0]
                    entry_price = ob.high  # Enter at resistance (high of order block)
                    stop_loss = ob.high * 1.005  # Stop just above the order block
                    take_profit = entry_price - (stop_loss - entry_price) * 2

                    signals.append(
                        Signal(
                            timestamp=entry_row["timestamp"],
                            signal_type=SignalType.SHORT,
                            entry_price=entry_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            confidence=min(1.0, ob.strength / 5),
                            timeframe=df.iloc[0].get("timeframe", "15m"),
                            reason=f"Bearish order block test, strength={ob.strength:.2f}",
                        )
                    )

        self.signals = signals

        if len(signals) == 0:
            logger.warning(
                f"No ICT structure signals generated. "
                f"Order blocks detected: {len(order_blocks)}, "
                f"FVGs detected: {len(fvgs)}, "
                f"Structure points: {len(structure_points)}. "
                f"Possible reasons: No price retests of order blocks, "
                f"or all OBs too old/invalid"
            )
        else:
            logger.info(f"Generated {len(signals)} ICT structure signals")

        return signals
