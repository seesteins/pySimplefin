#TODO clean this up

"""Export functionality for SimpleFin data."""

import csv
import hashlib
import io
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session, col, select

from pysimplefin.database import DatabaseManager
from pysimplefin.sql import Account, Organization, Transaction

logger = logging.getLogger(__name__)


class TransactionExporter:
    """
    Handle exporting transaction data to various formats.
    """

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize exporter with a DatabaseManager instance.

        Args:
            database_manager: DatabaseManager instance that provides the engine
        """
        self.db = database_manager

    def to_csv(
        self,
        output_path: str | Path = "transactions.csv",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        account_id: Optional[str] = None,
        include_pending: bool = True,
    ) -> int:
        """
        Export transactions from the database to a CSV file.

        Args:
            output_path: Path to the output CSV file
            start_date: Optional start date filter (uses posted date)
            end_date: Optional end date filter (uses posted date)
            account_id: Optional SimpleFIN account ID to filter by
            include_pending: Whether to include pending transactions

        Returns:
            Number of transactions exported
        """
        with Session(self.db.engine) as session:
            # Build query with joins
            query = self._export_query(
                start_date=start_date,
                end_date=end_date,
                account_id=account_id,
                include_pending=include_pending,
            )

            results = session.exec(query).all()

            rows = [self._row_to_dict(txn, acct, org) for txn, acct, org in results]

            # Write to CSV
            self._write_csv(Path(output_path), rows)

            return len(results)

    CSV_FIELDNAMES = [
        "transaction_id",
        "posted",
        "transacted_at",
        "amount",
        "description",
        "pending",
        "account_id",
        "account_name",
        "currency",
        "account_balance",
        "org_name",
        "org_domain",
    ]

    @staticmethod
    def _row_to_dict(
        transaction: Transaction, account: Account, org: Organization
    ) -> dict:
        """Convert a transaction/account/org tuple to a CSV row dict."""
        return {
            "transaction_id": transaction.id,
            "posted": (transaction.posted.isoformat() if transaction.posted else ""),
            "transacted_at": (
                transaction.transacted_at.isoformat()
                if transaction.transacted_at
                else ""
            ),
            "amount": str(transaction.amount),
            "description": transaction.description,
            "pending": transaction.pending if transaction.pending is not None else "",
            "account_id": account.id,
            "account_name": account.name,
            "currency": account.currency,
            "account_balance": str(account.balance),
            "org_name": org.name or "",
            "org_domain": org.domain or "",
        }

    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        """Write rows to a CSV file."""
        with path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.CSV_FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    @staticmethod
    def _csv_content(fieldnames: list[str], rows: list[dict]) -> str:
        """Render CSV rows to a string (for hashing / comparison)."""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return buf.getvalue()

    @staticmethod
    def _file_hash(path: Path) -> str:
        """Return the SHA-256 hex digest of an existing file."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def to_monthly_csvs(
        self,
        output_dir: str | Path = "/data/exports",
        account_id: Optional[str] = None,
        include_pending: bool = True,
    ) -> dict:
        """
        Export transactions to per-month CSV files, only writing files whose
        content has actually changed.

        Files are named ``YYYY-MM.csv`` and placed in *output_dir*.

        Args:
            output_dir: Directory to write monthly CSV files into.
            account_id: Optional SimpleFIN account ID to filter by.
            include_pending: Whether to include pending transactions.

        Returns:
            A dict with keys ``written``, ``skipped``, and ``total``
            indicating how many month-files were written (changed),
            skipped (unchanged), and total transactions exported.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        with Session(self.db.engine) as session:
            query = self._export_query(
                account_id=account_id,
                include_pending=include_pending,
            )
            results = session.exec(query).all()

        # Bucket rows by (year, month) using the posted date
        monthly_buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for transaction, account, org in results:
            if transaction.posted:
                key = (transaction.posted.year, transaction.posted.month)
            elif transaction.transacted_at:
                key = (transaction.transacted_at.year, transaction.transacted_at.month)
            else:
                # Fallback: bucket under a special "no-date" file
                key = (0, 0)
            monthly_buckets[key].append(self._row_to_dict(transaction, account, org))

        written = 0
        skipped = 0
        total_transactions = 0

        for (year, month), rows in sorted(monthly_buckets.items()):
            total_transactions += len(rows)
            filename = (
                f"transactions{year:04d}-{month:02d}.csv" if year else "no-date.csv"
            )
            filepath = output_path / filename

            # Render what the new file *would* contain
            new_content = self._csv_content(self.CSV_FIELDNAMES, rows)
            new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()

            # Compare with the existing file (if any)
            if filepath.exists():
                existing_hash = self._file_hash(filepath)
                if existing_hash == new_hash:
                    skipped += 1
                    continue

            # Content differs (or file is new) — write it
            self._write_csv(filepath, rows)
            written += 1

        return {"written": written, "skipped": skipped, "total": total_transactions}

    def _export_query(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        account_id: Optional[str] = None,
        include_pending: bool = True,
    ):
        """
        Build SQLModel query for transactions with optional filters.

        Returns a query that joins Transaction -> Account -> Organization.

        Args:
            start_date: Optional start date filter (uses posted date)
            end_date: Optional end date filter (uses posted date)
            account_id: Optional SimpleFIN account ID to filter by
            include_pending: Whether to include pending transactions

        Returns:
            SQLModel select statement ready to execute
        """
        # Start with base query, explicitly establishing the join chain
        # Transaction -> Account -> Organization
        query = (
            select(Transaction, Account, Organization)
            .select_from(Transaction)
            .join(Account, col(Transaction.account_pk) == col(Account.pk))
            .join(Organization, col(Account.org_pk) == col(Organization.pk))
        )

        # Apply filters
        if start_date:
            query = query.where(col(Transaction.posted) >= start_date)

        if end_date:
            query = query.where(col(Transaction.posted) <= end_date)

        if account_id:
            query = query.where(Account.id == account_id)

        if not include_pending:
            query = query.where(
                (col(Transaction.pending) == False) | col(Transaction.pending).is_(None)  # noqa: E712
            )

        query = query.order_by(col(Transaction.transacted_at).desc())

        return query
