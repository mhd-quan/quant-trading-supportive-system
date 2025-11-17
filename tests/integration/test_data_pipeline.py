"""Integration tests for data pipeline components."""

import pytest
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

from src.data.warehouse.duckdb_manager import DuckDBManager
from src.data.warehouse.parquet_manager import ParquetManager


@pytest.fixture
def test_db_path(tmp_path):
    """Create temporary database path."""
    return str(tmp_path / "test.duckdb")


@pytest.fixture
def test_lake_path(tmp_path):
    """Create temporary data lake path."""
    return str(tmp_path / "lake")


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    timestamps = pd.date_range(
        start=datetime.utcnow() - timedelta(days=7),
        end=datetime.utcnow(),
        freq="1H"
    )

    data = {
        "exchange": ["binance"] * len(timestamps),
        "symbol": ["BTC/USDT"] * len(timestamps),
        "timeframe": ["1h"] * len(timestamps),
        "timestamp": timestamps,
        "open": [50000 + i * 10 for i in range(len(timestamps))],
        "high": [50100 + i * 10 for i in range(len(timestamps))],
        "low": [49900 + i * 10 for i in range(len(timestamps))],
        "close": [50050 + i * 10 for i in range(len(timestamps))],
        "volume": [100 + i for i in range(len(timestamps))],
    }

    return pd.DataFrame(data)


class TestDuckDBIntegration:
    """Integration tests for DuckDB operations."""

    def test_full_pipeline(self, test_db_path, sample_ohlcv_data):
        """Test complete data pipeline: insert, query, validate."""
        db_manager = DuckDBManager(db_path=test_db_path)

        try:
            # Initialize schema
            db_manager.init_schema()

            # Insert data
            rows = db_manager.insert_ohlcv(sample_ohlcv_data)
            assert rows == len(sample_ohlcv_data)

            # Query data back
            result = db_manager.query_ohlcv(
                symbol="BTC/USDT",
                timeframe="1h",
                exchange="binance"
            )
            assert len(result) == len(sample_ohlcv_data)

            # Validate data integrity
            validation = db_manager.validate_data_integrity(
                symbol="BTC/USDT",
                timeframe="1h",
                exchange="binance"
            )
            assert validation["invalid_ohlc_count"] == 0
            assert validation["duplicate_count"] == 0

        finally:
            db_manager.close()

    def test_gap_detection(self, test_db_path):
        """Test gap detection in time series data."""
        db_manager = DuckDBManager(db_path=test_db_path)

        try:
            db_manager.init_schema()

            # Create data with intentional gap
            timestamps = [
                datetime(2024, 1, 1, 0, 0),
                datetime(2024, 1, 1, 1, 0),
                datetime(2024, 1, 1, 2, 0),
                # Gap here - missing 3:00
                datetime(2024, 1, 1, 4, 0),
                datetime(2024, 1, 1, 5, 0),
            ]

            data = pd.DataFrame({
                "exchange": ["binance"] * len(timestamps),
                "symbol": ["BTC/USDT"] * len(timestamps),
                "timeframe": ["1h"] * len(timestamps),
                "timestamp": timestamps,
                "open": [50000] * len(timestamps),
                "high": [51000] * len(timestamps),
                "low": [49000] * len(timestamps),
                "close": [50500] * len(timestamps),
                "volume": [100] * len(timestamps),
            })

            db_manager.insert_ohlcv(data)

            # Detect gaps
            gaps = db_manager.detect_gaps("BTC/USDT", "1h", "binance")
            assert len(gaps) > 0  # Should detect the gap

        finally:
            db_manager.close()


class TestParquetIntegration:
    """Integration tests for Parquet operations."""

    def test_write_and_read_partition(self, test_lake_path, sample_ohlcv_data):
        """Test writing and reading Parquet partitions."""
        parquet_manager = ParquetManager(root_dir=test_lake_path)

        # Write partition
        parquet_manager.write_partition(
            df=sample_ohlcv_data,
            exchange="binance",
            symbol="BTC/USDT",
            timeframe="1h"
        )

        # Read partition back
        result = parquet_manager.read_partition(
            exchange="binance",
            symbol="BTC/USDT",
            timeframe="1h"
        )

        assert len(result) == len(sample_ohlcv_data)
        assert list(result.columns) == [
            "exchange", "symbol", "timeframe", "timestamp",
            "open", "high", "low", "close", "volume"
        ]

    def test_storage_stats(self, test_lake_path, sample_ohlcv_data):
        """Test storage statistics calculation."""
        parquet_manager = ParquetManager(root_dir=test_lake_path)

        # Write some data
        parquet_manager.write_partition(
            df=sample_ohlcv_data,
            exchange="binance",
            symbol="BTC/USDT",
            timeframe="1h"
        )

        # Get stats
        stats = parquet_manager.get_storage_stats()

        assert not stats.empty
        assert "exchange" in stats.columns
        assert "symbol" in stats.columns
        assert "total_size_mb" in stats.columns
        assert stats.iloc[0]["exchange"] == "binance"


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_duckdb_to_parquet_export(
        self, test_db_path, test_lake_path, sample_ohlcv_data
    ):
        """Test exporting from DuckDB to Parquet."""
        db_manager = DuckDBManager(db_path=test_db_path)
        parquet_manager = ParquetManager(root_dir=test_lake_path)

        try:
            # Initialize and insert into DuckDB
            db_manager.init_schema()
            db_manager.insert_ohlcv(sample_ohlcv_data)

            # Export to Parquet
            db_manager.export_to_parquet(
                symbol="BTC/USDT",
                timeframe="1h",
                output_dir=test_lake_path,
                exchange="binance"
            )

            # Verify files were created
            lake_path = Path(test_lake_path)
            parquet_files = list(lake_path.rglob("*.parquet"))
            assert len(parquet_files) > 0

        finally:
            db_manager.close()
