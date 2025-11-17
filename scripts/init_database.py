"""Initialize DuckDB database with schema."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger

from src.data.warehouse.duckdb_manager import DuckDBManager


def main():
    """Initialize database."""
    load_dotenv()

    logger.info("Initializing DuckDB database...")

    db_manager = DuckDBManager()
    db_manager.init_schema()

    logger.success("Database initialized successfully")

    # Show schema
    conn = db_manager.connect()
    tables = conn.execute("SHOW TABLES").fetchall()

    logger.info("Created tables:")
    for table in tables:
        logger.info(f"  - {table[0]}")

    db_manager.close()


if __name__ == "__main__":
    main()
