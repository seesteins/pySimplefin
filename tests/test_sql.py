from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from pysimplefin.sql import Account, CustomCurrency, Organization, Transaction


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_org(session):
    org_data = {
        "domain": "example.com",
        "sfinurl": "https://example.com/simplefin",
        "name": "Example Bank",
    }
    org = Organization.model_validate(org_data)
    session.add(org)
    session.commit()
    session.refresh(org)
    assert org.pk is not None
    return org


@pytest.fixture
def sample_account(session, sample_org):
    account_data = {
        "id": "acc123",
        "name": "Checking Account",
        "currency": "USD",
        "balance": Decimal("1000.50"),
        "balancedate": datetime(2024, 1, 1),
        "org_pk": sample_org.pk,
    }
    account = Account.model_validate(account_data)
    session.add(account)
    session.commit()
    session.refresh(account)
    assert account.pk is not None
    return account


class TestOrganization:
    def test_validation_requires_domain_or_name(self):
        with pytest.raises(
            ValueError, match="Either domain or name or both must be provided"
        ):
            Organization.model_validate({"sfinurl": "https://test.com/simplefin"})

    def test_unique_constraint_domain_name(self, session):
        org1_data = {
            "domain": "test.com",
            "name": "Test Bank",
            "sfinurl": "https://test.com/1",
        }
        org1 = Organization.model_validate(org1_data)
        session.add(org1)
        session.commit()

        org2_data = {
            "domain": "test.com",
            "name": "Test Bank",
            "sfinurl": "https://test.com/2",
        }
        org2 = Organization.model_validate(org2_data)
        session.add(org2)

        with pytest.raises(Exception):
            session.commit()


class TestAccount:
    def test_unique_constraint_id_org(self, session, sample_org):
        account1_data = {
            "id": "same_id",
            "name": "Account 1",
            "currency": "USD",
            "balance": Decimal("100.00"),
            "balancedate": datetime(2024, 1, 1),
            "org_pk": sample_org.pk,
        }
        account1 = Account.model_validate(account1_data)
        session.add(account1)
        session.commit()

        account2_data = {
            "id": "same_id",
            "name": "Account 2",
            "currency": "USD",
            "balance": Decimal("200.00"),
            "balancedate": datetime(2024, 1, 1),
            "org_pk": sample_org.pk,
        }
        account2 = Account.model_validate(account2_data)
        session.add(account2)

        with pytest.raises(Exception):
            session.commit()

    @patch("pysimplefin.sql.get")
    def test_currency_url_fetch_success(self, mock_get, session, sample_org):
        mock_response = Mock()
        mock_response.json.return_value = {"name": "US Dollar", "abbr": "USD"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        account_data = {
            "id": "test789",
            "name": "Test Account",
            "currency": "https://api.example.com/currency/usd",
            "balance": Decimal("100.00"),
            "balancedate": datetime(2024, 1, 1),
            "org_pk": sample_org.pk,
        }
        account = Account.model_validate(account_data)
        session.add(account)
        session.commit()

        assert account.currency == "US Dollar"

    @patch("pysimplefin.sql.get")
    def test_currency_url_fetch_failure(self, mock_get, sample_org):
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(ValueError, match="Failed to fetch currency from URL"):
            account_data = {
                "id": "test789",
                "name": "Test Account",
                "currency": "https://api.example.com/currency/invalid",
                "balance": Decimal("100.00"),
                "balancedate": datetime(2024, 1, 1),
                "org_pk": sample_org.pk,
            }
            Account.model_validate(account_data)


class TestTransaction:
    def test_unique_constraint_id_account(self, session, sample_account):
        txn1 = Transaction(
            id="same_txn_id",
            amount=Decimal("50.00"),
            description="Transaction 1",
            account_pk=sample_account.pk,
        )
        session.add(txn1)
        session.commit()

        txn2 = Transaction(
            id="same_txn_id",
            amount=Decimal("75.00"),
            description="Transaction 2",
            account_pk=sample_account.pk,
        )
        session.add(txn2)

        with pytest.raises(Exception):
            session.commit()


class TestRelationships:
    def test_org_account_transaction_hierarchy(self, session):
        org_data = {
            "domain": "test.com",
            "name": "Test Bank",
            "sfinurl": "https://test.com/sf",
        }
        org = Organization.model_validate(org_data)
        session.add(org)
        session.commit()
        session.refresh(org)
        assert org.pk is not None

        account_data = {
            "id": "acc1",
            "name": "Test Account",
            "currency": "USD",
            "balance": Decimal("1000.00"),
            "balancedate": datetime(2024, 1, 1),
            "org_pk": org.pk,
        }
        account = Account.model_validate(account_data)
        session.add(account)
        session.commit()
        session.refresh(account)
        assert account.pk is not None

        txn = Transaction(
            id="txn1",
            amount=Decimal("-50.00"),
            description="Purchase",
            account_pk=account.pk,
        )
        session.add(txn)
        session.commit()

        session.refresh(org)
        assert len(org.accounts) == 1
        assert len(account.transactions) == 1
        assert txn.account == account
        assert account.org == org


class TestCustomCurrency:
    def test_requires_both_fields(self):
        # This should work
        currency = CustomCurrency(name="US Dollar", abbr="USD")
        assert currency.name == "US Dollar"
        assert currency.abbr == "USD"
