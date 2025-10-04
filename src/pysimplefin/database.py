from typing import List

from sqlmodel import Session, SQLModel, create_engine

from .models import Account as PydanticAccount
from .sql import Account, Organization, Transaction


class DatabaseManager:
    def __init__(self, database_url: str = "sqlite:///simplefin.db"):
        self.engine = create_engine(database_url)
        SQLModel.metadata.create_all(self.engine)

    def update_from_pydantic_models(self, accounts: List[PydanticAccount]):
        """Update database with data from Pydantic models"""
        with Session(self.engine) as session:
            for pydantic_account in accounts:
                org_data = pydantic_account.org.model_dump(by_alias=True)
                org = self._upsert(session, Organization, org_data, "sfinurl")

                account_data = pydantic_account.model_dump(
                    by_alias=True, exclude={"org", "transactions"}
                )
                account_data["org_id"] = org.id
                account = self._upsert(session, Account, account_data, "id")

                # Bulk handle transactions
                txn_data = [
                    {**txn.model_dump(by_alias=True), "account_id": account.id}
                    for txn in pydantic_account.transactions
                ]
                for data in txn_data:
                    self._upsert(session, Transaction, data, "id")

            session.commit()

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
