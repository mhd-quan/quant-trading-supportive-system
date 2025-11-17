"""Pattern matching using Matrix Profile and DTW."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
import stumpy
from loguru import logger


@dataclass
class PatternMatch:
    """Pattern match result."""

    match_idx: int
    distance: float
    pattern_start: int
    pattern_end: int
    forward_returns_1h: Optional[float] = None
    forward_returns_4h: Optional[float] = None
    forward_returns_1d: Optional[float] = None
    max_drawdown: Optional[float] = None


class PatternMatcher:
    """Find similar historical patterns using Matrix Profile."""

    def __init__(self, window_size: int = 100):
        """Initialize pattern matcher.

        Args:
            window_size: Size of pattern window
        """
        self.window_size = window_size

    def find_similar_patterns(
        self,
        current_data: pd.DataFrame,
        historical_data: pd.DataFrame,
        top_k: int = 20,
        features: Optional[List[str]] = None,
        timeframe_minutes: int = 60,
    ) -> List[PatternMatch]:
        """Find similar patterns in historical data.

        Args:
            current_data: Current pattern data
            historical_data: Historical data to search
            top_k: Number of top matches to return
            features: Features to use for matching
            timeframe_minutes: Timeframe in minutes (e.g., 60 for 1h, 15 for 15m)

        Returns:
            List of pattern matches
        """
        if features is None:
            features = ["close"]

        # Extract features
        try:
            current_features = self._extract_features(current_data, features)
            historical_features = self._extract_features(historical_data, features)

            # Validate data size for matrix profile computation
            min_length = max(4, self.window_size)  # Matrix profile needs at least 4 points
            if len(current_features) < min_length:
                logger.warning(
                    f"Current data too short: {len(current_features)} < {min_length}"
                )
                return []

            if len(historical_features) < self.window_size * 2:
                logger.warning(
                    f"Historical data too short: {len(historical_features)} < {self.window_size * 2}"
                )
                return []

            # Additional validation for stumpy requirements
            if self.window_size >= len(historical_features):
                logger.warning(
                    f"Window size ({self.window_size}) must be less than data length ({len(historical_features)})"
                )
                return []

            # Normalize features
            current_norm = self._normalize(current_features)
            historical_norm = self._normalize(historical_features)

            # Use most recent window from current data
            query = current_norm[-self.window_size :]

            # Compute distance profile
            distance_profile = stumpy.mass(query, historical_norm)

            # Get top k matches
            top_indices = np.argsort(distance_profile)[:top_k]

            matches = []
            for idx in top_indices:
                if idx + self.window_size >= len(historical_data):
                    continue

                # Calculate forward returns with dynamic timeframe
                forward_returns = self._calculate_forward_returns(
                    historical_data, idx + self.window_size, timeframe_minutes
                )

                matches.append(
                    PatternMatch(
                        match_idx=idx,
                        distance=float(distance_profile[idx]),
                        pattern_start=idx,
                        pattern_end=idx + self.window_size,
                        **forward_returns,
                    )
                )

            logger.info(f"Found {len(matches)} similar patterns")
            return matches

        except Exception as e:
            logger.error(f"Error finding patterns: {e}")
            return []

    def find_motifs(
        self, data: pd.DataFrame, k: int = 3, features: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Find recurring patterns (motifs) in data.

        Args:
            data: DataFrame with OHLCV data
            k: Number of motifs to find
            features: Features to use

        Returns:
            List of motif dictionaries
        """
        if features is None:
            features = ["close"]

        try:
            features_data = self._extract_features(data, features)
            features_norm = self._normalize(features_data)

            # Validate data size before computing matrix profile
            min_length = max(4, self.window_size * 2)
            if len(features_norm) < min_length:
                logger.warning(
                    f"Data too short for motif discovery: {len(features_norm)} < {min_length}"
                )
                return []

            if self.window_size >= len(features_norm):
                logger.warning(
                    f"Window size ({self.window_size}) must be less than data length ({len(features_norm)})"
                )
                return []

            # Compute matrix profile
            mp = stumpy.stump(features_norm, m=self.window_size)

            # Find motifs
            motif_indices = stumpy.motifs(
                features_norm, mp[:, 0], k=k, cutoff=np.inf
            )

            motifs = []
            for i, indices in enumerate(motif_indices):
                if indices is not None and len(indices) > 0:
                    motifs.append(
                        {
                            "motif_id": i,
                            "occurrences": indices.tolist(),
                            "count": len(indices),
                            "window_size": self.window_size,
                        }
                    )

            logger.info(f"Found {len(motifs)} motifs")
            return motifs

        except Exception as e:
            logger.error(f"Error finding motifs: {e}")
            return []

    def _extract_features(
        self, df: pd.DataFrame, features: List[str]
    ) -> np.ndarray:
        """Extract and stack features from DataFrame.

        Args:
            df: DataFrame with data
            features: List of feature column names

        Returns:
            Stacked feature array
        """
        feature_arrays = []

        for feature in features:
            if feature == "returns":
                returns = df["close"].pct_change().fillna(0)
                feature_arrays.append(returns.values)
            elif feature == "log_returns":
                log_returns = np.log(df["close"] / df["close"].shift(1)).fillna(0)
                feature_arrays.append(log_returns.values)
            elif feature == "volume_ratio":
                vol_ma = df["volume"].rolling(window=20).mean()
                vol_ratio = (df["volume"] / vol_ma).fillna(1)
                feature_arrays.append(vol_ratio.values)
            elif feature in df.columns:
                feature_arrays.append(df[feature].values)
            else:
                logger.warning(f"Feature {feature} not found, skipping")

        if not feature_arrays:
            return df["close"].values.reshape(-1, 1)

        if len(feature_arrays) == 1:
            return feature_arrays[0]

        return np.column_stack(feature_arrays)

    def _normalize(self, data: np.ndarray) -> np.ndarray:
        """Z-score normalize data.

        Args:
            data: Input array

        Returns:
            Normalized array
        """
        if data.ndim == 1:
            mean = np.mean(data)
            std = np.std(data)
            if std == 0:
                return data - mean
            return (data - mean) / std
        else:
            # Normalize each column
            normalized = np.zeros_like(data, dtype=float)
            for i in range(data.shape[1]):
                col = data[:, i]
                mean = np.mean(col)
                std = np.std(col)
                if std == 0:
                    normalized[:, i] = col - mean
                else:
                    normalized[:, i] = (col - mean) / std
            return normalized

    def _calculate_forward_returns(
        self, df: pd.DataFrame, start_idx: int, timeframe_minutes: int = 60
    ) -> Dict[str, Optional[float]]:
        """Calculate forward returns from a given index.

        Args:
            df: DataFrame with data
            start_idx: Starting index
            timeframe_minutes: Timeframe in minutes (e.g., 60 for 1h, 15 for 15m)

        Returns:
            Dictionary with forward returns
        """
        result = {
            "forward_returns_1h": None,
            "forward_returns_4h": None,
            "forward_returns_1d": None,
            "max_drawdown": None,
        }

        # Validate inputs
        if start_idx >= len(df):
            logger.warning(f"Invalid start_idx {start_idx} >= len(df) {len(df)}")
            return result

        if 'close' not in df.columns:
            logger.error("Missing 'close' column in DataFrame")
            return result

        if 'high' not in df.columns or 'low' not in df.columns:
            logger.warning("Missing 'high' or 'low' columns, max drawdown will not be calculated")

        start_price = df.iloc[start_idx]["close"]

        # Calculate periods for each time horizon
        periods_1h = max(1, int(60 / timeframe_minutes))
        periods_4h = max(1, int(240 / timeframe_minutes))
        periods_1d = max(1, int(1440 / timeframe_minutes))

        # 1 hour forward
        if start_idx + periods_1h < len(df):
            result["forward_returns_1h"] = (
                (df.iloc[start_idx + periods_1h]["close"] - start_price) / start_price * 100
            )

        # 4 hours forward
        if start_idx + periods_4h < len(df):
            result["forward_returns_4h"] = (
                (df.iloc[start_idx + periods_4h]["close"] - start_price) / start_price * 100
            )

        # 1 day forward (24 hours)
        if start_idx + periods_1d < len(df):
            result["forward_returns_1d"] = (
                (df.iloc[start_idx + periods_1d]["close"] - start_price) / start_price * 100
            )

            # Calculate max drawdown in next 24 hours
            future_prices = df.iloc[start_idx : start_idx + periods_1d]["close"]
            running_max = future_prices.expanding().max()
            drawdown = ((future_prices - running_max) / running_max * 100).min()
            result["max_drawdown"] = float(drawdown)

        return result
