from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from niquests import get
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
    model_validator,
)


class Transaction(BaseModel):
    id: str
    posted: Optional[datetime] = None
    amount: Decimal
    description: str
    transacted_at: Optional[datetime] = None
    pending: Optional[bool] = None
    extra: Optional[Any] = None


class Organization(BaseModel):
    # This will always be the same for simplefin.org
    domain: Optional[str] = None
    sfinurl: str = Field(alias="sfin-url")
    name: Optional[str] = None
    url: Optional[str] = None
    id: Optional[str] = None

    @model_validator(mode="after")
    def domain_or_name(self):
        if not (self.domain or self.name):
            raise ValueError("Either domain or name or both must be provided")
        return self


class Account(BaseModel):
    org: Organization
    id: str
    name: str
    currency: str
    balance: Decimal
    available_balance: Optional[Decimal] = Field(
        default=None, alias="available-balance"
    )
    balancedate: datetime = Field(alias="balance-date")
    transactions: List[Transaction]
    extra: Optional[Any] = None

    @field_validator("currency", mode="before")
    @classmethod
    def custom_currency(cls, v):
        if isinstance(v, str):
            # Check if it's a URL
            try:
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


class CustomCurrency(BaseModel):
    name: str
    abbr: str
