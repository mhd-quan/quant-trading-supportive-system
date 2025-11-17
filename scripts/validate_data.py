"""Validate data integrity in DuckDB."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from loguru import logger
import pandas as pd

from src.data.warehouse.duckdb_manager import DuckDBManager


def validate_all_data():
    """Validate data integrity for all symbols in database."""
    load_dotenv()

    logger.info("Starting data validation")

    db_manager = DuckDBManager()

    try:
        # Get all available data
        coverage = db_manager.get_data_coverage()

        if coverage.empty:
            logger.warning("No data found in database")
            return 0

        logger.info(f"Found {len(coverage)} datasets to validate")

        total_issues = 0
        validation_results = []

        # Validate each dataset
        for _, row in coverage.iterrows():
            exchange = row['exchange']
            symbol = row['symbol']
            timeframe = row['timeframe']

            logger.info(f"Validating {exchange} {symbol} {timeframe}")

            validation = db_manager.validate_data_integrity(
                symbol=symbol,
                timeframe=timeframe,
                exchange=exchange
            )

            validation_results.append(validation)

            # Report issues
            issues = (
                validation['invalid_ohlc_count'] +
                validation['duplicate_count'] +
                validation['gap_count']
            )
            total_issues += issues

            if issues > 0:
                logger.warning(
                    f"{exchange} {symbol} {timeframe}: "
                    f"Invalid OHLC: {validation['invalid_ohlc_count']}, "
                    f"Duplicates: {validation['duplicate_count']}, "
                    f"Gaps: {validation['gap_count']}"
                )
            else:
                logger.success(f"{exchange} {symbol} {timeframe}: OK")

        # Summary
        logger.info("=" * 60)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total datasets validated: {len(coverage)}")
        logger.info(f"Total issues found: {total_issues}")

        if total_issues == 0:
            logger.success("All data validation checks passed!")
        else:
            logger.warning(f"Found {total_issues} issues that need attention")

        # Save validation report
        report_path = Path("data/validation_report.csv")
        report_path.parent.mkdir(parents=True, exist_ok=True)

        report_df = pd.DataFrame(validation_results)
        report_df.to_csv(report_path, index=False)
        logger.info(f"Validation report saved to {report_path}")

        return total_issues

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        return -1
    finally:
        db_manager.close()


def main():
    """Main entry point."""
    exit_code = validate_all_data()

    # Exit with error code if issues found
    if exit_code > 0:
        logger.warning(f"Exiting with code 1 (found {exit_code} issues)")
        sys.exit(1)
    elif exit_code < 0:
        logger.error("Exiting with code 2 (validation error)")
        sys.exit(2)
    else:
        logger.success("Exiting with code 0 (success)")
        sys.exit(0)


if __name__ == "__main__":
    main()
