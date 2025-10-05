from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from niquests import get
from pydantic import ValidationError, field_validator, model_validator
from sqlmodel import (
    DECIMAL,
    JSON,
    Boolean,
    Column,
    DateTime,
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)


class Base(SQLModel):
    pk: Optional[int] = Field(default=None, primary_key=True)



class Transaction(Base, table=True):
    # SimpleFin spec fields
    id: str
    posted: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    amount: Decimal = Field(sa_column=Column(DECIMAL(precision=10, scale=2)))
    description: str
    transacted_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime))
    pending: Optional[bool] = Field(default=None, sa_column=Column(Boolean))
    extra: Optional[Any] = Field(default=None, sa_column=Column(JSON))

    # Foreign key to account using internal pk (safest approach)
    account_pk: int = Field(foreign_key="account.pk")
    account: "Account" = Relationship(back_populates="transactions")

    # Ensure combination of SimpleFIN id + account pk is unique
    __table_args__ = (
        UniqueConstraint('id', 'account_pk', name='uix_transaction_id_account'),
    )

class Organization(Base, table=True):
    # SimpleFIN spec fields
    domain: Optional[str] = None
    sfinurl: str = Field(alias="sfin-url")  # Required but not necessarily unique
    name: Optional[str] = None
    url: Optional[str] = None
    id: Optional[str] = None

    # Relationship to accounts
    accounts: List["Account"] = Relationship(back_populates="org")

    # Create a unique constraint on the combination that makes sense
    __table_args__ = (
        UniqueConstraint('domain', 'name', name='uix_org_identity'),
    )

    @model_validator(mode="after")
    def domain_or_name(self):
        if not (self.domain or self.name):
            raise ValueError("Either domain or name or both must be provided")
        return self


class Account(Base, table=True):
    # SimpleFin spec fields
    id: str  # SimpleFIN account ID
    name: str
    currency: str
    balance: Decimal = Field(sa_column=Column(DECIMAL(precision=10, scale=2)))
    available_balance: Optional[Decimal] = Field(
        default=None,
        alias="available-balance",
        sa_column=Column(DECIMAL(precision=10, scale=2)),
    )
    balancedate: datetime = Field(alias="balance-date", sa_column=Column(DateTime))
    extra: Optional[Any] = Field(default=None, sa_column=Column(JSON))

    # Foreign key to organization using internal pk
    org_pk: int = Field(foreign_key="organization.pk")
    org: Organization = Relationship(back_populates="accounts")

    # Relationship to transactions
    transactions: List[Transaction] = Relationship(back_populates="account")

    # Ensure combination of SimpleFIN id + organization pk is unique
    __table_args__ = (
        UniqueConstraint('id', 'org_pk', name='uix_account_id_org'),
    )

    @field_validator("currency", mode="before")
    @classmethod
    def custom_currency(cls, v):
        if isinstance(v, str):
            # Check if it's a URL
            try:
                from pydantic import HttpUrl

                HttpUrl(v)
                try:
                    response = get(v)
                    response.raise_for_status()
                    currency_data = response.json()
                    custom_currency = CustomCurrency(**currency_data)
                    return custom_currency.name
                except Exception as e:
                    raise ValueError(f"Failed to fetch currency from URL {v}: {e}")
            except ValidationError:
                return v
        return v





class CustomCurrency(SQLModel):
    name: str
    abbr: str

