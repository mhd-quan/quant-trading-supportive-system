"""Parquet file manager for data lake operations."""

from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger


class ParquetManager:
    """Manage Parquet data lake with partitioning."""

    def __init__(self, root_dir: str = "./data/lake"):
        """Initialize Parquet manager.

        Args:
            root_dir: Root directory for Parquet data lake
        """
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Parquet Manager initialized with root: {self.root_dir}")

    def get_partition_path(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        year: int,
        month: int,
    ) -> Path:
        """Get partition path for data.

        Args:
            exchange: Exchange identifier
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            year: Year for partition
            month: Month for partition

        Returns:
            Path to partition directory
        """
        # Clean symbol for filesystem
        symbol_clean = symbol.replace("/", "_")

        path = (
            self.root_dir
            / exchange
            / symbol_clean
            / timeframe
            / f"year={year}"
            / f"month={month:02d}"
        )
        return path

    def write_partition(
        self,
        df: pd.DataFrame,
        exchange: str,
        symbol: str,
        timeframe: str,
        compression: str = "snappy",
    ) -> None:
        """Write DataFrame to partitioned Parquet files.

        Args:
            df: DataFrame with OHLCV data
            exchange: Exchange identifier
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            compression: Compression algorithm
        """
        if df.empty:
            logger.warning("Empty DataFrame, skipping write")
            return

        # Ensure timestamp column is datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Add partition columns
        df["year"] = df["timestamp"].dt.year
        df["month"] = df["timestamp"].dt.month

        # Group by year and month
        for (year, month), group_df in df.groupby(["year", "month"]):
            partition_path = self.get_partition_path(
                exchange, symbol, timeframe, year, month
            )
            partition_path.mkdir(parents=True, exist_ok=True)

            # Remove partition columns from data
            data_df = group_df.drop(columns=["year", "month"])

            # Atomic write: write to .tmp file, then rename
            file_path = partition_path / "data.parquet"
            tmp_file_path = partition_path / ".data.parquet.tmp"

            try:
                table = pa.Table.from_pandas(data_df)
                pq.write_table(
                    table,
                    tmp_file_path,
                    compression=compression,
                    use_dictionary=True,
                    write_statistics=True,
                )

                # Atomic rename
                tmp_file_path.rename(file_path)

                logger.info(
                    f"Wrote {len(data_df)} rows to {file_path}"
                )
            except Exception as e:
                # Clean up temp file on error
                if tmp_file_path.exists():
                    tmp_file_path.unlink()
                logger.error(f"Error writing parquet file: {e}")
                raise

    def read_partition(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> pd.DataFrame:
        """Read data from partition.

        Args:
            exchange: Exchange identifier
            symbol: Trading pair symbol
            timeframe: Candle timeframe
            year: Year filter (optional)
            month: Month filter (optional)

        Returns:
            DataFrame with data
        """
        symbol_clean = symbol.replace("/", "_")
        base_path = self.root_dir / exchange / symbol_clean / timeframe

        if not base_path.exists():
            logger.warning(f"Path does not exist: {base_path}")
            return pd.DataFrame()

        # Build list of files to read
        files = []

        if year and month:
            # Specific partition
            partition_path = self.get_partition_path(
                exchange, symbol, timeframe, year, month
            )
            file_path = partition_path / "data.parquet"
            if file_path.exists():
                files.append(file_path)
        elif year:
            # All months in year
            for m in range(1, 13):
                partition_path = self.get_partition_path(
                    exchange, symbol, timeframe, year, m
                )
                file_path = partition_path / "data.parquet"
                if file_path.exists():
                    files.append(file_path)
        else:
            # All partitions
            for year_dir in base_path.glob("year=*"):
                for month_dir in year_dir.glob("month=*"):
                    file_path = month_dir / "data.parquet"
                    if file_path.exists():
                        files.append(file_path)

        if not files:
            logger.warning(f"No Parquet files found for {symbol} {timeframe}")
            return pd.DataFrame()

        # Read all files and concatenate
        dfs = []
        for file_path in files:
            try:
                df = pd.read_parquet(file_path)
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        if not dfs:
            return pd.DataFrame()

        result = pd.concat(dfs, ignore_index=True)
        result = result.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Read {len(result)} rows from {len(files)} files")
        return result

    def compact_partitions(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
    ) -> None:
        """Compact small Parquet files in partitions.

        Args:
            exchange: Exchange identifier
            symbol: Trading pair symbol
            timeframe: Candle timeframe
        """
        symbol_clean = symbol.replace("/", "_")
        base_path = self.root_dir / exchange / symbol_clean / timeframe

        if not base_path.exists():
            logger.warning(f"Path does not exist: {base_path}")
            return

        for year_dir in base_path.glob("year=*"):
            for month_dir in year_dir.glob("month=*"):
                files = list(month_dir.glob("*.parquet"))

                if len(files) > 1:
                    # Read all files
                    dfs = [pd.read_parquet(f) for f in files]
                    combined = pd.concat(dfs, ignore_index=True)
                    combined = combined.drop_duplicates().sort_values("timestamp")

                    # Remove old files
                    for f in files:
                        f.unlink()

                    # Write compacted file
                    table = pa.Table.from_pandas(combined)
                    pq.write_table(
                        table,
                        month_dir / "data.parquet",
                        compression="snappy",
                    )

                    logger.info(
                        f"Compacted {len(files)} files into 1 in {month_dir}"
                    )

    def get_storage_stats(self) -> pd.DataFrame:
        """Get storage statistics for all data.

        Returns:
            DataFrame with storage stats
        """
        stats = []

        for exchange_dir in self.root_dir.glob("*"):
            if not exchange_dir.is_dir():
                continue

            for symbol_dir in exchange_dir.glob("*"):
                if not symbol_dir.is_dir():
                    continue

                for timeframe_dir in symbol_dir.glob("*"):
                    if not timeframe_dir.is_dir():
                        continue

                    total_size = sum(
                        f.stat().st_size
                        for f in timeframe_dir.rglob("*.parquet")
                    )
                    file_count = len(list(timeframe_dir.rglob("*.parquet")))

                    stats.append(
                        {
                            "exchange": exchange_dir.name,
                            "symbol": symbol_dir.name.replace("_", "/"),
                            "timeframe": timeframe_dir.name,
                            "file_count": file_count,
                            "total_size_mb": total_size / (1024 * 1024),
                        }
                    )

        if not stats:
            return pd.DataFrame()

        return pd.DataFrame(stats).sort_values(
            ["exchange", "symbol", "timeframe"]
        )
