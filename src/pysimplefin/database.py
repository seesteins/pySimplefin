from datetime import datetime, timedelta
from typing import Any, List, Type, TypeVar, Union
from warnings import warn

from sqlmodel import Session, SQLModel, col, create_engine, delete, select

from pysimplefin.models import Account as PydanticAccount
from pysimplefin.sql import Account, Base, Organization, Transaction

# Create a TypeVar bound to Base for better type hints
BASEMODEL = TypeVar("BASEMODEL", bound=Base)


class DatabaseManager:
    def __init__(self, database_url: str = "sqlite:///simplefin.db"):
        self.engine = create_engine(database_url)
        SQLModel.metadata.create_all(self.engine)

    def _upsert(
        self,
        session: Session,
        model_class: Type[BASEMODEL],
        data: dict,
        key_fields: Union[str, List[str]],
    ) -> BASEMODEL:
        """Generic upsert - key_fields can be string or list"""
        if isinstance(key_fields, str):
            key_fields = [key_fields]

        # Build the where conditions
        query = select(model_class)
        for field in key_fields:
            query = query.where(getattr(model_class, field) == data[field])

        existing = session.exec(query).first()

        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing

        new_obj = model_class(**data)
        session.add(new_obj)
        session.flush()
        return new_obj

    def sync(self, accounts: List[PydanticAccount], sync_window_days: int = 7):
        """
        Sync data from a simplefinClient request to a local database.

        Args:
            accounts (List[PydanticAccount]): List of pydantic Account models. Can be passed directly from the return of a SimpleFinClient.get_data()
            sync_window_days (int, optional): Number of days to check for transactions that are no longer in the simplefin dataset. Useful for removing holds, pending charges etc. Defaults to 7.
        """
        with Session(self.engine) as session:
            for pydantic_account in accounts:
                # Sync org - use a combination of fields for uniqueness
                org_data = pydantic_account.org.model_dump(by_alias=False)
                # Use sfinurl as primary identifier, but could fall back to domain/name combo
                org = self._upsert(session, Organization, org_data, ["domain", "name"])

                # Sync account - use the internal pk for foreign key
                account_data = pydantic_account.model_dump(
                    by_alias=False, exclude={"org", "transactions"}
                )
                account_data["org_pk"] = org.pk  # Use internal pk
                account = self._upsert(session, Account, account_data, ["id", "org_pk"])

                # Remove stale transactions if sync window specified
                if sync_window_days > 0:
                    remote_txn_ids = {txn.id for txn in pydantic_account.transactions}
                    cutoff_date = datetime.now() - timedelta(days=sync_window_days)

                    existing_txn_ids = set(
                        session.exec(
                            select(Transaction.id)
                            .where(Transaction.account_pk == account.pk)
                            .where(col(Transaction.posted) >= cutoff_date)
                        ).all()
                    )

                    removed_ids = existing_txn_ids - remote_txn_ids
                    if removed_ids:
                        session.exec(
                            delete(Transaction)
                            .where(Transaction.account_pk == account.pk)  # type: ignore[attr-defined]
                            .where(
                                col(Transaction.id).in_(list(removed_ids))
                            )  # Convert set to list and use col()
                        )
                        warn(
                            f"Removed {len(removed_ids)} transactions from account {account.id}"
                        )

                # Upsert all transactions
                for txn in pydantic_account.transactions:
                    txn_data = txn.model_dump(by_alias=False)
                    txn_data["account_pk"] = account.pk  # Use internal pk
                    self._upsert(session, Transaction, txn_data, ["id", "account_pk"])

            session.commit()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: Any | None = None,
    ) -> None:
        """Context manager exit - disposes of database engine"""
        self.engine.dispose()
