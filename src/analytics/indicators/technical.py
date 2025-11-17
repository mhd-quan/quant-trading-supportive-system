"""Technical indicators using pandas-ta and ta libraries."""

from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
import pandas_ta as ta_lib
from loguru import logger
from functools import lru_cache


class TechnicalIndicators:
    """Calculate technical indicators on OHLCV data.

    All methods are static to maintain backward compatibility with existing callers.
    Refactored to split indicators into focused methods for better organization.
    """

    @staticmethod
    def add_moving_averages(
        df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Add moving average indicators.

        Args:
            df: DataFrame with OHLCV data
            config: Optional configuration for MA periods

        Returns:
            DataFrame with MA indicators
        """
        df = df.copy()

        # Default periods
        sma_periods = config.get("sma_periods", [20, 50, 200]) if config else [20, 50, 200]
        ema_periods = config.get("ema_periods", [9, 20, 50]) if config else [9, 20, 50]

        # Simple Moving Averages
        for period in sma_periods:
            df[f"sma_{period}"] = ta_lib.sma(df["close"], length=period)

        # Exponential Moving Averages
        for period in ema_periods:
            df[f"ema_{period}"] = ta_lib.ema(df["close"], length=period)

        logger.debug(f"Added {len(sma_periods)} SMA and {len(ema_periods)} EMA indicators")
        return df

    @staticmethod
    def add_momentum_indicators(
        df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Add momentum indicators (RSI, MACD).

        Args:
            df: DataFrame with OHLCV data
            config: Optional configuration for indicator parameters

        Returns:
            DataFrame with momentum indicators
        """
        df = df.copy()

        # RSI
        rsi_period = config.get("rsi_period", 14) if config else 14
        df[f"rsi_{rsi_period}"] = ta_lib.rsi(df["close"], length=rsi_period)

        # MACD
        macd = ta_lib.macd(df["close"])
        if macd is not None and not macd.empty:
            df["macd"] = macd.iloc[:, 0]
            df["macd_signal"] = macd.iloc[:, 1]
            df["macd_hist"] = macd.iloc[:, 2]

        logger.debug("Added momentum indicators (RSI, MACD)")
        return df

    @staticmethod
    def add_volatility_indicators(
        df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Add volatility indicators (ATR, Bollinger Bands).

        Args:
            df: DataFrame with OHLCV data
            config: Optional configuration for indicator parameters

        Returns:
            DataFrame with volatility indicators
        """
        df = df.copy()

        # ATR
        atr_period = config.get("atr_period", 14) if config else 14
        atr = ta_lib.atr(df["high"], df["low"], df["close"], length=atr_period)
        if atr is not None and not atr.empty:
            df[f"atr_{atr_period}"] = atr

        # Bollinger Bands
        bb_period = config.get("bb_period", 20) if config else 20
        bb_std = config.get("bb_std", 2) if config else 2
        bbands = ta_lib.bbands(df["close"], length=bb_period, std=bb_std)
        if bbands is not None and not bbands.empty:
            df["bb_upper"] = bbands.iloc[:, 0]
            df["bb_middle"] = bbands.iloc[:, 1]
            df["bb_lower"] = bbands.iloc[:, 2]

        logger.debug("Added volatility indicators (ATR, Bollinger Bands)")
        return df

    @staticmethod
    def add_volume_indicators(
        df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Add volume-based indicators.

        Args:
            df: DataFrame with OHLCV data
            config: Optional configuration for indicator parameters

        Returns:
            DataFrame with volume indicators
        """
        df = df.copy()

        if "volume" not in df.columns:
            logger.warning("Volume column not found, skipping volume indicators")
            return df

        # VWAP
        vwap = ta_lib.vwap(df["high"], df["low"], df["close"], df["volume"])
        if vwap is not None and not vwap.empty:
            df["vwap"] = vwap

        # Volume SMA and ratio
        volume_period = config.get("volume_period", 20) if config else 20
        df[f"volume_sma_{volume_period}"] = ta_lib.sma(df["volume"], length=volume_period)
        df["volume_ratio"] = df["volume"] / df[f"volume_sma_{volume_period}"]

        logger.debug("Added volume indicators (VWAP, Volume SMA)")
        return df

    @staticmethod
    def add_trend_indicators(
        df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Add trend indicators (ADX).

        Args:
            df: DataFrame with OHLCV data
            config: Optional configuration for indicator parameters

        Returns:
            DataFrame with trend indicators
        """
        df = df.copy()

        # ADX
        adx_period = config.get("adx_period", 14) if config else 14
        adx = ta_lib.adx(df["high"], df["low"], df["close"], length=adx_period)
        if adx is not None and not adx.empty:
            df[f"adx_{adx_period}"] = adx.iloc[:, 0]

        logger.debug("Added trend indicators (ADX)")
        return df

    @staticmethod
    def add_all_indicators(
        df: pd.DataFrame, config: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Add all common technical indicators to DataFrame.

        This method delegates to focused indicator methods for better
        organization and maintainability.

        Args:
            df: DataFrame with OHLCV data
            config: Optional configuration for indicators

        Returns:
            DataFrame with added indicator columns
        """
        df = df.copy()

        # Add indicators by category
        df = TechnicalIndicators.add_moving_averages(df, config)
        df = TechnicalIndicators.add_momentum_indicators(df, config)
        df = TechnicalIndicators.add_volatility_indicators(df, config)
        df = TechnicalIndicators.add_volume_indicators(df, config)
        df = TechnicalIndicators.add_trend_indicators(df, config)

        indicator_count = len([c for c in df.columns if c not in ['open', 'high', 'low', 'close', 'volume', 'timestamp']])
        logger.debug(f"Added {indicator_count} total indicators")
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
        # Division by zero guard
        er = change / volatility.replace(0, np.nan)  # Efficiency ratio
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
        # Division by zero guard
        return (atr / close.replace(0, np.nan)) * 100

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

        # Vectorized approach: digitize all lows and highs at once
        low_bins = np.digitize(df["low"].values, bins) - 1
        high_bins = np.digitize(df["high"].values, bins) - 1

        # Clip to valid range
        low_bins = np.clip(low_bins, 0, num_bins - 1)
        high_bins = np.clip(high_bins, 0, num_bins - 1)

        # Iterate only for distribution (still needed but more efficient)
        for i in range(len(df)):
            low_bin = low_bins[i]
            high_bin = high_bins[i]
            bins_touched = high_bin - low_bin + 1
            volume_per_bin = df.iloc[i]["volume"] / bins_touched

            # Use numpy add.at for efficient accumulation
            np.add.at(volume_by_price, range(low_bin, high_bin + 1), volume_per_bin)

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

        # Add bounds checking to prevent index overflow
        vah = bins[min(max(value_area_indices) + 1, len(bins) - 1)]  # Value Area High
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

    @staticmethod
    def calculate_stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> Dict[str, pd.Series]:
        """Calculate Stochastic Oscillator.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            k_period: %K period
            d_period: %D period (SMA of %K)

        Returns:
            Dictionary with %K and %D series
        """
        stoch = ta_lib.stoch(high, low, close, k=k_period, d=d_period)
        if stoch is not None and not stoch.empty:
            return {"stoch_k": stoch.iloc[:, 0], "stoch_d": stoch.iloc[:, 1]}
        return {"stoch_k": pd.Series(dtype=float), "stoch_d": pd.Series(dtype=float)}

    @staticmethod
    def calculate_cci(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
    ) -> pd.Series:
        """Calculate Commodity Channel Index (CCI).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: CCI period

        Returns:
            CCI series
        """
        cci = ta_lib.cci(high, low, close, length=period)
        return cci if cci is not None else pd.Series(dtype=float)

    @staticmethod
    def calculate_roc(close: pd.Series, period: int = 12) -> pd.Series:
        """Calculate Rate of Change (ROC).

        Args:
            close: Close prices
            period: ROC period

        Returns:
            ROC series
        """
        roc = ta_lib.roc(close, length=period)
        return roc if roc is not None else pd.Series(dtype=float)

    @staticmethod
    def calculate_williams_r(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate Williams %R.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Williams %R period

        Returns:
            Williams %R series
        """
        willr = ta_lib.willr(high, low, close, length=period)
        return willr if willr is not None else pd.Series(dtype=float)

    @staticmethod
    def calculate_supertrend(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 10,
        multiplier: float = 3.0,
    ) -> Dict[str, pd.Series]:
        """Calculate Supertrend indicator.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period
            multiplier: ATR multiplier

        Returns:
            Dictionary with supertrend and direction series
        """
        supertrend = ta_lib.supertrend(
            high, low, close, length=period, multiplier=multiplier
        )
        if supertrend is not None and not supertrend.empty:
            return {
                "supertrend": supertrend.iloc[:, 0],
                "supertrend_direction": supertrend.iloc[:, 1],
            }
        return {
            "supertrend": pd.Series(dtype=float),
            "supertrend_direction": pd.Series(dtype=float),
        }

    @staticmethod
    def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate On-Balance Volume (OBV).

        Args:
            close: Close prices
            volume: Volume data

        Returns:
            OBV series
        """
        obv = ta_lib.obv(close, volume)
        return obv if obv is not None else pd.Series(dtype=float)

    @staticmethod
    def calculate_mfi(
        high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate Money Flow Index (MFI).

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data
            period: MFI period

        Returns:
            MFI series
        """
        mfi = ta_lib.mfi(high, low, close, volume, length=period)
        return mfi if mfi is not None else pd.Series(dtype=float)
