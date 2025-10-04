from datetime import datetime, timedelta
from typing import Any, List
from warnings import warn

from sqlmodel import Session, SQLModel, create_engine, delete, select, col

from .models import Account as PydanticAccount
from .sql import Account, Organization, Transaction


class DatabaseManager:
    def __init__(self, database_url: str = "sqlite:///simplefin.db"):
        self.engine = create_engine(database_url)
        SQLModel.metadata.create_all(self.engine)

    def _upsert(self, session: Session, model_class, data: dict, key: str):
        """Generic upsert using model dumps"""
        existing = session.get(model_class, data[key])

        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing

        new_obj = model_class(**data)
        session.add(new_obj)
        session.flush()
        return new_obj

    def sync(self, accounts: List[PydanticAccount], sync_window_days: int = 30):
        """Sync data and optionally detect removed transactions"""
        with Session(self.engine) as session:
            for pydantic_account in accounts:
                # Sync org and account - use by_alias=False to get Python field names
                org_data = pydantic_account.org.model_dump(by_alias=False)
                org = self._upsert(session, Organization, org_data, "sfinurl")
                
                account_data = pydantic_account.model_dump(by_alias=False, exclude={"org", "transactions"})
                account_data["org_pk"] = org.pk
                account = self._upsert(session, Account, account_data, "id")
                
                # Remove stale transactions if sync window specified
                if sync_window_days > 0:
                    remote_txn_ids = {txn.id for txn in pydantic_account.transactions}
                    cutoff_date = datetime.now() - timedelta(days=sync_window_days)
                    
                    existing_txn_ids = set(session.exec(
                        select(Transaction.id)
                        .where(Transaction.account_id == account.id)
                        .where(col(Transaction.posted) >= cutoff_date)
                    ).all())
                    
                    removed_ids = existing_txn_ids - remote_txn_ids
                    if removed_ids:
                        session.exec(
                            delete(Transaction)
                            .where(col(Transaction.id).in_(removed_ids))
                        )
                        warn(f"Removed {len(removed_ids)} transactions from account {account.id}")
                
                # Upsert all transactions
                for txn in pydantic_account.transactions:
                    txn_data = {**txn.model_dump(by_alias=False), "account_id": account.id}
                    self._upsert(session, Transaction, txn_data, "id")
            
            session.commit()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,  # Type of exception (if any)
        exc_val: BaseException | None,  # Exception instance (if any)
        exc_tb: Any | None,  # Exception traceback (if any)
    ) -> None:
        """Context manager exit - disposes of database engine"""
        self.engine.dispose()

