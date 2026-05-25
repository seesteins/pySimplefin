"""
Docker entrypoint script for exporting transactions to monthly CSV files.

Reads from the SQLite database and writes per-month CSV files to /data/exports.
Only files whose content has changed are rewritten.

Environment variables:
    DATABASE_URL    - Optional. SQLAlchemy database URL. Defaults to sqlite:////data/simplefin.db
    EXPORT_DIR      - Optional. Directory to write CSV files. Defaults to /data/exports
"""

import logging
import os

from pysimplefin import DatabaseManager, TransactionExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    database_url = os.environ.get("DATABASE_URL", "sqlite:////data/simplefin.db")
    export_dir = os.environ.get("EXPORT_DIR", "/data/exports")

    logger.info("Starting monthly CSV export...")
    logger.info("Database: %s", database_url)
    logger.info("Export dir: %s", export_dir)

    with DatabaseManager(database_url) as db:
        exporter = TransactionExporter(db)
        result = exporter.to_monthly_csvs(output_dir=export_dir)

    logger.info("Total transactions: %d", result["total"])
    logger.info("Files written (changed): %d", result["written"])
    logger.info("Files skipped (unchanged): %d", result["skipped"])
    logger.info("Export complete.")


if __name__ == "__main__":
    main()
