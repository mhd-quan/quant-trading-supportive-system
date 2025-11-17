"""ICT (Inner Circle Trader) pattern detection."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class FairValueGap:
    """Fair Value Gap structure."""

    start_idx: int
    end_idx: int
    gap_high: float
    gap_low: float
    gap_size: float
    direction: str  # 'bullish' or 'bearish'
    timestamp: datetime
    filled: bool = False
    fill_percent: float = 0.0


@dataclass
class OrderBlock:
    """Order Block structure."""

    idx: int
    high: float
    low: float
    open: float
    close: float
    direction: str  # 'bullish' or 'bearish'
    timestamp: datetime
    strength: float  # Based on imbalance ratio
    valid: bool = True


@dataclass
class LiquidityPool:
    """Liquidity pool/sweep zone."""

    price_level: float
    touches: int
    first_touch: datetime
    last_touch: datetime
    pool_type: str  # 'buy_side' or 'sell_side'
    swept: bool = False


@dataclass
class StructurePoint:
    """Market structure point (swing high/low)."""

    idx: int
    price: float
    point_type: str  # 'high' or 'low'
    timestamp: datetime
    broken: bool = False


class ICTPatterns:
    """Detect ICT trading patterns and market structure."""

    @staticmethod
    def detect_fair_value_gaps(
        df: pd.DataFrame, min_gap_atr_multiple: float = 0.5
    ) -> List[FairValueGap]:
        """Detect Fair Value Gaps (FVG).

        A bullish FVG occurs when:
        - candle[i-2].high < candle[i].low (gap exists)

        Args:
            df: DataFrame with OHLCV data
            min_gap_atr_multiple: Minimum gap size as ATR multiple

        Returns:
            List of Fair Value Gaps
        """
        # Calculate ATR for threshold
        high_low = df["high"] - df["low"]
        high_close = abs(df["high"] - df["close"].shift(1))
        low_close = abs(df["low"] - df["close"].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()

        fvgs = []

        for i in range(2, len(df)):
            atr_val = atr.iloc[i]
            if pd.isna(atr_val) or atr_val == 0:
                continue

            # Bullish FVG: gap between candle i-2 high and candle i low
            gap_low_bull = df.iloc[i - 2]["high"]
            gap_high_bull = df.iloc[i]["low"]

            if gap_low_bull < gap_high_bull:  # Bullish gap exists
                gap_size = gap_high_bull - gap_low_bull
                if gap_size >= min_gap_atr_multiple * atr_val:
                    fvgs.append(
                        FairValueGap(
                            start_idx=i - 2,
                            end_idx=i,
                            gap_high=gap_high_bull,
                            gap_low=gap_low_bull,
                            gap_size=gap_size,
                            direction="bullish",
                            timestamp=df.iloc[i]["timestamp"],
                        )
                    )

            # Bearish FVG: gap between candle i-2 low and candle i high
            gap_high_bear = df.iloc[i - 2]["low"]
            gap_low_bear = df.iloc[i]["high"]

            if gap_low_bear < gap_high_bear:  # Bearish gap exists
                gap_size = gap_high_bear - gap_low_bear
                if gap_size >= min_gap_atr_multiple * atr_val:
                    fvgs.append(
                        FairValueGap(
                            start_idx=i - 2,
                            end_idx=i,
                            gap_high=gap_high_bear,
                            gap_low=gap_low_bear,
                            gap_size=gap_size,
                            direction="bearish",
                            timestamp=df.iloc[i]["timestamp"],
                        )
                    )

        logger.info(f"Detected {len(fvgs)} Fair Value Gaps")
        return fvgs

    @staticmethod
    def detect_order_blocks(
        df: pd.DataFrame, imbalance_ratio: float = 3.0
    ) -> List[OrderBlock]:
        """Detect Order Blocks.

        Order block is the last opposite candle before an impulsive move.

        Args:
            df: DataFrame with OHLCV data
            imbalance_ratio: Minimum ratio for impulsive move

        Returns:
            List of Order Blocks
        """
        order_blocks = []

        for i in range(1, len(df) - 1):
            current = df.iloc[i]
            next_candle = df.iloc[i + 1]

            # Bullish order block: bearish candle before bullish impulse
            if current["close"] < current["open"]:  # Bearish candle
                next_range = next_candle["high"] - next_candle["low"]
                current_range = current["high"] - current["low"]

                if (
                    next_candle["close"] > next_candle["open"]
                    and next_range > current_range * imbalance_ratio
                ):
                    strength = next_range / current_range
                    order_blocks.append(
                        OrderBlock(
                            idx=i,
                            high=current["high"],
                            low=current["low"],
                            open=current["open"],
                            close=current["close"],
                            direction="bullish",
                            timestamp=current["timestamp"],
                            strength=strength,
                        )
                    )

            # Bearish order block: bullish candle before bearish impulse
            if current["close"] > current["open"]:  # Bullish candle
                next_range = next_candle["high"] - next_candle["low"]
                current_range = current["high"] - current["low"]

                if (
                    next_candle["close"] < next_candle["open"]
                    and next_range > current_range * imbalance_ratio
                ):
                    strength = next_range / current_range
                    order_blocks.append(
                        OrderBlock(
                            idx=i,
                            high=current["high"],
                            low=current["low"],
                            open=current["open"],
                            close=current["close"],
                            direction="bearish",
                            timestamp=current["timestamp"],
                            strength=strength,
                        )
                    )

        logger.info(f"Detected {len(order_blocks)} Order Blocks")
        return order_blocks

    @staticmethod
    def detect_market_structure(
        df: pd.DataFrame, swing_lookback: int = 5
    ) -> List[StructurePoint]:
        """Detect market structure (swing highs and lows).

        Args:
            df: DataFrame with OHLCV data
            swing_lookback: Bars to look back/forward for swing

        Returns:
            List of structure points
        """
        structure_points = []

        for i in range(swing_lookback, len(df) - swing_lookback):
            # Check for swing high
            is_swing_high = all(
                df.iloc[i]["high"] > df.iloc[i + j]["high"]
                for j in range(-swing_lookback, swing_lookback + 1)
                if j != 0
            )

            if is_swing_high:
                structure_points.append(
                    StructurePoint(
                        idx=i,
                        price=df.iloc[i]["high"],
                        point_type="high",
                        timestamp=df.iloc[i]["timestamp"],
                    )
                )

            # Check for swing low
            is_swing_low = all(
                df.iloc[i]["low"] < df.iloc[i + j]["low"]
                for j in range(-swing_lookback, swing_lookback + 1)
                if j != 0
            )

            if is_swing_low:
                structure_points.append(
                    StructurePoint(
                        idx=i,
                        price=df.iloc[i]["low"],
                        point_type="low",
                        timestamp=df.iloc[i]["timestamp"],
                    )
                )

        logger.info(f"Detected {len(structure_points)} structure points")
        return structure_points

    @staticmethod
    def detect_liquidity_pools(
        df: pd.DataFrame, structure_points: List[StructurePoint], touch_threshold: int = 2
    ) -> List[LiquidityPool]:
        """Detect liquidity pools at swing highs/lows.

        Args:
            df: DataFrame with OHLCV data
            structure_points: List of structure points
            touch_threshold: Minimum touches to qualify as pool

        Returns:
            List of liquidity pools
        """
        # Group nearby structure points
        tolerance = df["close"].std() * 0.01  # 1% of price std dev

        pools: Dict[float, List[StructurePoint]] = {}

        for point in structure_points:
            matched = False
            for price_level in list(pools.keys()):
                if abs(point.price - price_level) < tolerance:
                    pools[price_level].append(point)
                    matched = True
                    break

            if not matched:
                pools[point.price] = [point]

        # Filter by touch threshold
        liquidity_pools = []
        for price_level, points in pools.items():
            if len(points) >= touch_threshold:
                pool_type = "buy_side" if points[0].point_type == "high" else "sell_side"
                liquidity_pools.append(
                    LiquidityPool(
                        price_level=price_level,
                        touches=len(points),
                        first_touch=points[0].timestamp,
                        last_touch=points[-1].timestamp,
                        pool_type=pool_type,
                    )
                )

        logger.info(f"Detected {len(liquidity_pools)} liquidity pools")
        return liquidity_pools

    @staticmethod
    def detect_bos_choch(
        df: pd.DataFrame, structure_points: List[StructurePoint]
    ) -> List[Dict[str, Any]]:
        """Detect Break of Structure (BOS) and Change of Character (CHoCH).

        Args:
            df: DataFrame with OHLCV data
            structure_points: List of structure points

        Returns:
            List of BOS/CHoCH events
        """
        if len(structure_points) < 2:
            return []

        events = []
        sorted_points = sorted(structure_points, key=lambda x: x.idx)

        for i in range(1, len(sorted_points)):
            prev_point = sorted_points[i - 1]
            curr_point = sorted_points[i]

            # BOS: continuation of trend (high > prev high or low < prev low)
            if prev_point.point_type == "high" and curr_point.point_type == "high":
                if curr_point.price > prev_point.price:
                    events.append(
                        {
                            "type": "BOS",
                            "direction": "bullish",
                            "price": curr_point.price,
                            "timestamp": curr_point.timestamp,
                            "idx": curr_point.idx,
                        }
                    )

            if prev_point.point_type == "low" and curr_point.point_type == "low":
                if curr_point.price < prev_point.price:
                    events.append(
                        {
                            "type": "BOS",
                            "direction": "bearish",
                            "price": curr_point.price,
                            "timestamp": curr_point.timestamp,
                            "idx": curr_point.idx,
                        }
                    )

            # CHoCH: change of trend direction
            if (
                prev_point.point_type == "high"
                and curr_point.point_type == "low"
                and i > 1
            ):
                # Check if this low is lower than previous low
                prev_lows = [p for p in sorted_points[:i] if p.point_type == "low"]
                if prev_lows and curr_point.price < min(p.price for p in prev_lows):
                    events.append(
                        {
                            "type": "CHoCH",
                            "direction": "bearish",
                            "price": curr_point.price,
                            "timestamp": curr_point.timestamp,
                            "idx": curr_point.idx,
                        }
                    )

        logger.info(f"Detected {len(events)} BOS/CHoCH events")
        return events
