"""
Docker entrypoint script for exporting transactions to monthly CSV files.

Reads from the SQLite database and writes per-month CSV files to /data/exports,
then uploads them to a WebDAV remote using rclone. Only files whose content has
changed are rewritten locally; rclone handles syncing to the remote.

Rclone is configured via the standard RCLONE_CONFIG_WEBDAV_* environment variables
(set in .env), which define a remote named "webdav" automatically.

Environment variables:
    DATABASE_URL                - Optional. SQLAlchemy database URL. Defaults to sqlite:////data/simplefin.db
    EXPORT_DIR                  - Optional. Local directory to write CSV files. Defaults to /data/exports
    RCLONE_CONFIG_WEBDAV_TYPE   - Required. Must be "webdav".
    RCLONE_CONFIG_WEBDAV_URL    - Required. WebDAV server URL.
    RCLONE_CONFIG_WEBDAV_USER   - Required. WebDAV username.
    RCLONE_CONFIG_WEBDAV_PASS   - Required. WebDAV password (rclone-obscured).
    RCLONE_CONFIG_WEBDAV_VENDOR - Optional. WebDAV vendor (e.g. "nextcloud", "other").
    RCLONE_REMOTE_PATH          - Optional. Subdirectory on the remote to copy exports into. Defaults to empty (remote root).
"""

import logging
import os
import subprocess
import sys

from pysimplefin import DatabaseManager, TransactionExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def rclone_copy(source_dir: str, remote_path: str) -> None:
    """Copy source_dir to the rclone 'webdav' remote (configured via RCLONE_CONFIG_WEBDAV_* env vars)."""
    destination = f"webdav:{remote_path}"
    logger.info("Uploading exports via rclone: %s -> %s", source_dir, destination)
    result = subprocess.run(
        ["rclone", "copy", source_dir, destination, "--transfers=4", "-v"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        logger.info("rclone:\n%s", result.stdout.strip())
    if result.returncode != 0:
        logger.error("rclone copy failed:\n%s", result.stderr.strip())
        sys.exit(1)
    logger.info("Upload complete.")


def main():
    database_url = os.environ.get("DATABASE_URL", "sqlite:////data/simplefin.db")
    export_dir = os.environ.get("EXPORT_DIR", "/data/exports")
    remote_path = os.environ.get("RCLONE_REMOTE_PATH", "")

    for var in (
        "RCLONE_CONFIG_WEBDAV_TYPE",
        "RCLONE_CONFIG_WEBDAV_URL",
        "RCLONE_CONFIG_WEBDAV_USER",
        "RCLONE_CONFIG_WEBDAV_PASS",
    ):
        if not os.environ.get(var):
            logger.error("Required environment variable %s is not set.", var)
            sys.exit(1)

    logger.info("Starting monthly CSV export...")
    logger.info("Database: %s", database_url)
    logger.info("Export dir: %s", export_dir)

    with DatabaseManager(database_url) as db:
        exporter = TransactionExporter(db)
        result = exporter.to_monthly_csvs(output_dir=export_dir)

    logger.info("Total transactions: %d", result["total"])
    logger.info("Files written (changed): %d", result["written"])
    logger.info("Files skipped (unchanged): %d", result["skipped"])

    rclone_copy(export_dir, remote_path)
    logger.info("Export complete.")


if __name__ == "__main__":
    main()
