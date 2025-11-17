"""Technical indicators using pandas-ta and ta libraries."""

from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
import pandas_ta as ta_lib
from loguru import logger


class TechnicalIndicators:
    """Calculate technical indicators on OHLCV data."""

    @staticmethod
    def add_all_indicators(
        df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Add all common technical indicators to DataFrame.

        Args:
            df: DataFrame with OHLCV data
            config: Optional configuration for indicators

        Returns:
            DataFrame with added indicator columns
        """
        df = df.copy()

        # Moving averages
        df["sma_20"] = ta_lib.sma(df["close"], length=20)
        df["sma_50"] = ta_lib.sma(df["close"], length=50)
        df["sma_200"] = ta_lib.sma(df["close"], length=200)
        df["ema_9"] = ta_lib.ema(df["close"], length=9)
        df["ema_20"] = ta_lib.ema(df["close"], length=20)
        df["ema_50"] = ta_lib.ema(df["close"], length=50)

        # VWAP
        if "volume" in df.columns:
            vwap = ta_lib.vwap(df["high"], df["low"], df["close"], df["volume"])
            if vwap is not None and not vwap.empty:
                df["vwap"] = vwap

        # Momentum indicators
        df["rsi_14"] = ta_lib.rsi(df["close"], length=14)

        macd = ta_lib.macd(df["close"])
        if macd is not None and not macd.empty:
            df["macd"] = macd.iloc[:, 0]
            df["macd_signal"] = macd.iloc[:, 1]
            df["macd_hist"] = macd.iloc[:, 2]

        # Volatility
        atr = ta_lib.atr(df["high"], df["low"], df["close"], length=14)
        if atr is not None and not atr.empty:
            df["atr_14"] = atr

        bbands = ta_lib.bbands(df["close"], length=20, std=2)
        if bbands is not None and not bbands.empty:
            df["bb_upper"] = bbands.iloc[:, 0]
            df["bb_middle"] = bbands.iloc[:, 1]
            df["bb_lower"] = bbands.iloc[:, 2]

        # Volume
        if "volume" in df.columns:
            df["volume_sma_20"] = ta_lib.sma(df["volume"], length=20)
            df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

        # Trend
        adx = ta_lib.adx(df["high"], df["low"], df["close"], length=14)
        if adx is not None and not adx.empty:
            df["adx_14"] = adx.iloc[:, 0]

        logger.debug(f"Added {len([c for c in df.columns if c not in ['open', 'high', 'low', 'close', 'volume', 'timestamp']])} indicators")
        return df

    @staticmethod
    def calculate_kama(
        close: pd.Series, period: int = 10, fast: int = 2, slow: int = 30
    ) -> pd.Series:
        """Calculate Kaufman Adaptive Moving Average.

        Args:
            close: Close prices
            period: Period for efficiency ratio
            fast: Fast EMA constant
            slow: Slow EMA constant

        Returns:
            KAMA series
        """
        change = abs(close - close.shift(period))
        volatility = (abs(close - close.shift(1))).rolling(window=period).sum()
        er = change / volatility  # Efficiency ratio
        er = er.fillna(0)

        fast_sc = 2 / (fast + 1)
        slow_sc = 2 / (slow + 1)
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2

        kama = pd.Series(index=close.index, dtype=float)
        kama.iloc[period - 1] = close.iloc[period - 1]

        for i in range(period, len(close)):
            kama.iloc[i] = kama.iloc[i - 1] + sc.iloc[i] * (
                close.iloc[i] - kama.iloc[i - 1]
            )

        return kama

    @staticmethod
    def calculate_atr_percent(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate ATR as percentage of price.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period

        Returns:
            ATR percentage series
        """
        atr = ta_lib.atr(high, low, close, length=period)
        if atr is None or atr.empty:
            return pd.Series(index=close.index, dtype=float)
        return (atr / close) * 100

    @staticmethod
    def calculate_volume_profile(
        df: pd.DataFrame, num_bins: int = 24
    ) -> Dict[str, Any]:
        """Calculate volume profile.

        Args:
            df: DataFrame with OHLCV data
            num_bins: Number of price bins

        Returns:
            Dictionary with volume profile data
        """
        price_min = df["low"].min()
        price_max = df["high"].max()
        bins = np.linspace(price_min, price_max, num_bins + 1)

        volume_by_price = np.zeros(num_bins)

        for _, row in df.iterrows():
            # Distribute volume across bins
            low_bin = np.digitize(row["low"], bins) - 1
            high_bin = np.digitize(row["high"], bins) - 1

            low_bin = max(0, min(low_bin, num_bins - 1))
            high_bin = max(0, min(high_bin, num_bins - 1))

            bins_touched = high_bin - low_bin + 1
            volume_per_bin = row["volume"] / bins_touched

            for b in range(low_bin, high_bin + 1):
                if 0 <= b < num_bins:
                    volume_by_price[b] += volume_per_bin

        # Find POC (Point of Control) - price level with highest volume
        poc_index = np.argmax(volume_by_price)
        poc_price = (bins[poc_index] + bins[poc_index + 1]) / 2

        # Value area (70% of volume)
        total_volume = volume_by_price.sum()
        target_volume = total_volume * 0.7
        sorted_indices = np.argsort(volume_by_price)[::-1]

        cumsum = 0
        value_area_indices = []
        for idx in sorted_indices:
            cumsum += volume_by_price[idx]
            value_area_indices.append(idx)
            if cumsum >= target_volume:
                break

        vah = bins[max(value_area_indices) + 1]  # Value Area High
        val = bins[min(value_area_indices)]  # Value Area Low

        return {
            "poc": poc_price,
            "vah": vah,
            "val": val,
            "bins": bins,
            "volume_by_price": volume_by_price,
        }

    @staticmethod
    def calculate_support_resistance(
        df: pd.DataFrame, window: int = 20, threshold_pct: float = 0.02
    ) -> Dict[str, list]:
        """Identify support and resistance levels.

        Args:
            df: DataFrame with OHLCV data
            window: Window for local extrema
            threshold_pct: Clustering threshold as percentage

        Returns:
            Dictionary with support and resistance levels
        """
        # Find local maxima (resistance)
        df["local_max"] = df["high"].rolling(window=window, center=True).max()
        resistance_levels = df[df["high"] == df["local_max"]]["high"].tolist()

        # Find local minima (support)
        df["local_min"] = df["low"].rolling(window=window, center=True).min()
        support_levels = df[df["low"] == df["local_min"]]["low"].tolist()

        # Cluster nearby levels
        def cluster_levels(levels, threshold_pct):
            if not levels:
                return []
            levels = sorted(levels)
            clustered = []
            current_cluster = [levels[0]]

            for level in levels[1:]:
                if (level - current_cluster[-1]) / current_cluster[-1] < threshold_pct:
                    current_cluster.append(level)
                else:
                    clustered.append(np.mean(current_cluster))
                    current_cluster = [level]

            clustered.append(np.mean(current_cluster))
            return clustered

        return {
            "support": cluster_levels(support_levels, threshold_pct),
            "resistance": cluster_levels(resistance_levels, threshold_pct),
        }
