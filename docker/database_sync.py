"""
Docker entrypoint script for pysimplefin.

Fetches transactions from SimpleFIN and syncs them to a local SQLite database.

Environment variables:
    SIMPLEFIN_URL   - Required. Your SimpleFIN access URL.
    DATABASE_URL    - Optional. SQLAlchemy database URL. Defaults to sqlite:///data/simplefin.db
    LOOKBACK_DAYS   - Optional. Number of days to look back for transactions. Defaults to 30.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

from pysimplefin import DatabaseManager, DefaultAuth, SimpleFinClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    # --- Configuration from environment ---
    simplefin_url = os.environ.get("SIMPLEFIN_URL")
    if not simplefin_url:
        logger.error("SIMPLEFIN_URL environment variable is required.")
        sys.exit(1)

    database_url = os.environ.get("DATABASE_URL", "sqlite:///data/simplefin.db")
    lookback_days = int(os.environ.get("LOOKBACK_DAYS", "30"))

    # --- Fetch and sync ---
    logger.info("Starting sync (lookback=%d days)...", lookback_days)

    auth = DefaultAuth.from_url(simplefin_url)
    client = SimpleFinClient(auth)

    start_date = datetime.now() - timedelta(days=lookback_days)
    data = client.get_data(start_date=start_date, end_date=datetime.now(), pending=True)

    logger.info("Fetched %d account(s) from SimpleFIN.", len(data))

    with DatabaseManager(database_url) as db:
        db.sync(data, start_date=start_date)

    logger.info("Sync complete.")


if __name__ == "__main__":
    main()
