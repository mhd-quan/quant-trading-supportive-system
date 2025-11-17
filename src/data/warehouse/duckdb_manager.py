"""DuckDB database manager for OHLCV data storage and queries."""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import duckdb
from loguru import logger


class DuckDBManager:
    """Manage DuckDB database for cryptocurrency data."""

    def __init__(self, db_path: str = "./data/crypto.duckdb"):
        """Initialize DuckDB manager.

        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[duckdb.DuckDBPyConnection] = None
        logger.info(f"DuckDB Manager initialized with database: {self.db_path}")

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Establish connection to DuckDB database.

        Returns:
            DuckDB connection object
        """
        if self.conn is None:
            self.conn = duckdb.connect(str(self.db_path))
            logger.info(f"Connected to DuckDB at {self.db_path}")
        return self.conn

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("DuckDB connection closed")

    def init_schema(self) -> None:
        """Initialize database schema with tables and views."""
        conn = self.connect()

        # Create OHLCV raw data table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ohlcv_raw (
                exchange VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                timeframe VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                open DECIMAL(18,8) NOT NULL,
                high DECIMAL(18,8) NOT NULL,
                low DECIMAL(18,8) NOT NULL,
                close DECIMAL(18,8) NOT NULL,
                volume DECIMAL(18,8) NOT NULL,
                quote_volume DECIMAL(18,8),
                trades_count INTEGER,
                taker_buy_volume DECIMAL(18,8),
                taker_buy_quote_volume DECIMAL(18,8),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (exchange, symbol, timeframe, timestamp)
            )
        """
        )

        # Create index for faster queries
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time
            ON ohlcv_raw (symbol, timeframe, timestamp)
        """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ohlcv_exchange_symbol
            ON ohlcv_raw (exchange, symbol)
        """
        )

        # Create metadata table for tracking data quality
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS data_quality_metadata (
                exchange VARCHAR,
                symbol VARCHAR,
                timeframe VARCHAR,
                first_timestamp TIMESTAMP,
                last_timestamp TIMESTAMP,
                total_records BIGINT,
                gaps_detected INTEGER,
                duplicates_detected INTEGER,
                anomalies_detected INTEGER,
                last_validation TIMESTAMP,
                PRIMARY KEY (exchange, symbol, timeframe)
            )
        """
        )

        # Create view for latest candles
        conn.execute(
            """
            CREATE OR REPLACE VIEW latest_candles AS
            SELECT
                exchange,
                symbol,
                timeframe,
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                quote_volume
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY exchange, symbol, timeframe
                        ORDER BY timestamp DESC
                    ) as rn
                FROM ohlcv_raw
            ) ranked
            WHERE rn = 1
        """
        )

        logger.info("DuckDB schema initialized successfully")

    def insert_ohlcv(
        self, df: pd.DataFrame, replace_duplicates: bool = True
    ) -> int:
        """Insert OHLCV data into database.

        Args:
            df: DataFrame with OHLCV data
            replace_duplicates: Whether to replace existing records

        Returns:
            Number of rows inserted
        """
        if df.empty:
            logger.warning("Empty DataFrame provided, skipping insert")
            return 0

        conn = self.connect()

        # Validate required columns
        required_cols = [
            "exchange",
            "symbol",
            "timeframe",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            raise ValueError(f"Missing required columns: {missing}")

        # Prepare DataFrame
        df_insert = df.copy()
        df_insert["timestamp"] = pd.to_datetime(df_insert["timestamp"])

        try:
            if replace_duplicates:
                # Use INSERT OR REPLACE
                conn.execute(
                    """
                    INSERT OR REPLACE INTO ohlcv_raw
                    SELECT * FROM df_insert
                """
                )
            else:
                # Use INSERT OR IGNORE to skip duplicates
                conn.execute(
                    """
                    INSERT OR IGNORE INTO ohlcv_raw
                    SELECT * FROM df_insert
                """
                )

            rows_affected = len(df_insert)
            logger.info(f"Inserted {rows_affected} rows into ohlcv_raw")
            return rows_affected

        except Exception as e:
            logger.error(f"Error inserting data: {e}")
            raise

    def query_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        exchange: str = "binance",
    ) -> pd.DataFrame:
        """Query OHLCV data from database.

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            start_date: Start date for query
            end_date: End date for query
            exchange: Exchange identifier

        Returns:
            DataFrame with OHLCV data
        """
        conn = self.connect()

        query = """
            SELECT
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                quote_volume,
                trades_count
            FROM ohlcv_raw
            WHERE exchange = ?
                AND symbol = ?
                AND timeframe = ?
        """
        params = [exchange, symbol, timeframe]

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp ASC"

        try:
            df = conn.execute(query, params).df()
            logger.debug(f"Queried {len(df)} rows for {symbol} {timeframe}")
            return df
        except Exception as e:
            logger.error(f"Error querying OHLCV data: {e}")
            raise

    def get_data_coverage(self) -> pd.DataFrame:
        """Get data coverage statistics for all symbols.

        Returns:
            DataFrame with coverage statistics
        """
        conn = self.connect()

        query = """
            SELECT
                exchange,
                symbol,
                timeframe,
                MIN(timestamp) as first_candle,
                MAX(timestamp) as last_candle,
                COUNT(*) as total_candles,
                DATEDIFF('day', MIN(timestamp), MAX(timestamp)) as days_covered
            FROM ohlcv_raw
            GROUP BY exchange, symbol, timeframe
            ORDER BY exchange, symbol, timeframe
        """

        try:
            df = conn.execute(query).df()
            return df
        except Exception as e:
            logger.error(f"Error getting data coverage: {e}")
            raise

    def detect_gaps(
        self, symbol: str, timeframe: str, exchange: str = "binance"
    ) -> pd.DataFrame:
        """Detect gaps in time series data.

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            exchange: Exchange identifier

        Returns:
            DataFrame with detected gaps
        """
        conn = self.connect()

        # Calculate expected timeframe interval
        timeframe_seconds = self._timeframe_to_seconds(timeframe)

        query = """
            WITH gaps AS (
                SELECT
                    timestamp as gap_start,
                    LEAD(timestamp) OVER (ORDER BY timestamp) as gap_end,
                    DATEDIFF('second', timestamp, LEAD(timestamp) OVER (ORDER BY timestamp)) as gap_seconds
                FROM ohlcv_raw
                WHERE exchange = ? AND symbol = ? AND timeframe = ?
            )
            SELECT
                gap_start,
                gap_end,
                gap_seconds,
                gap_seconds / ? as missing_candles
            FROM gaps
            WHERE gap_seconds > ? * 1.5
            ORDER BY gap_start
        """

        try:
            df = conn.execute(
                query, [exchange, symbol, timeframe, timeframe_seconds, timeframe_seconds]
            ).df()
            logger.info(f"Detected {len(df)} gaps for {symbol} {timeframe}")
            return df
        except Exception as e:
            logger.error(f"Error detecting gaps: {e}")
            raise

    def validate_data_integrity(
        self, symbol: str, timeframe: str, exchange: str = "binance"
    ) -> Dict[str, Any]:
        """Validate data integrity (OHLC relationships, duplicates, etc.).

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            exchange: Exchange identifier

        Returns:
            Dictionary with validation results
        """
        conn = self.connect()

        # Check OHLC relationships
        invalid_ohlc = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM ohlcv_raw
            WHERE exchange = ? AND symbol = ? AND timeframe = ?
                AND (high < low
                    OR high < open
                    OR high < close
                    OR low > open
                    OR low > close
                    OR volume < 0)
        """,
            [exchange, symbol, timeframe],
        ).fetchone()[0]

        # Check duplicates
        duplicates = conn.execute(
            """
            SELECT COUNT(*) - COUNT(DISTINCT (exchange, symbol, timeframe, timestamp)) as count
            FROM ohlcv_raw
            WHERE exchange = ? AND symbol = ? AND timeframe = ?
        """,
            [exchange, symbol, timeframe],
        ).fetchone()[0]

        # Detect gaps
        gaps_df = self.detect_gaps(symbol, timeframe, exchange)

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": exchange,
            "invalid_ohlc_count": invalid_ohlc,
            "duplicate_count": duplicates,
            "gap_count": len(gaps_df),
            "validation_timestamp": datetime.utcnow(),
        }

    @staticmethod
    def _timeframe_to_seconds(timeframe: str) -> int:
        """Convert timeframe to seconds."""
        multipliers = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
        value = int(timeframe[:-1])
        unit = timeframe[-1]
        return value * multipliers.get(unit, 60)

    def export_to_parquet(
        self,
        symbol: str,
        timeframe: str,
        output_dir: str,
        exchange: str = "binance",
        partition_by: List[str] = ["year", "month"],
    ) -> None:
        """Export data to Parquet files with partitioning.

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            output_dir: Output directory for Parquet files
            exchange: Exchange identifier
            partition_by: Columns to partition by
        """
        df = self.query_ohlcv(symbol, timeframe, exchange=exchange)

        if df.empty:
            logger.warning(f"No data to export for {symbol} {timeframe}")
            return

        # Add partition columns
        df["year"] = pd.to_datetime(df["timestamp"]).dt.year
        df["month"] = pd.to_datetime(df["timestamp"]).dt.month

        # Create output directory structure
        output_path = Path(output_dir) / exchange / symbol.replace("/", "_") / timeframe
        output_path.mkdir(parents=True, exist_ok=True)

        # Export with partitioning
        df.to_parquet(
            output_path / "data.parquet",
            engine="pyarrow",
            compression="snappy",
            index=False,
        )

        logger.info(f"Exported {len(df)} rows to {output_path}")

    def __enter__(self) -> "DuckDBManager":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
