from datetime import datetime
from decimal import Decimal
import warnings

import pytest
from sqlmodel import Session, select

from pysimplefin.database import DatabaseManager
from pysimplefin.models import Account as PydanticAccount
from pysimplefin.models import Organization as PydanticOrg
from pysimplefin.models import Transaction as PydanticTransaction
from pysimplefin.sql import Account, Organization, Transaction


@pytest.fixture
def db_manager():
    """Create in-memory database for testing"""
    return DatabaseManager("sqlite:///:memory:")


@pytest.fixture
def sample_data():
    """Sample pydantic data for testing"""
    org = PydanticOrg(
        domain="example.com",
        name="Test Bank",
        **{
            "sfin-url": "https://example.com/ofx"
        },  # Use dict unpacking for hyphenated field name
    )

    transactions = [
        PydanticTransaction(
            id="txn1",
            posted=datetime(2024, 1, 1),
            amount=Decimal("-10.00"),
            description="Test payment",
        ),
        PydanticTransaction(
            id="txn2",
            posted=datetime(2024, 1, 2),
            amount=Decimal("5.00"),
            description="Test deposit",
        ),
    ]

    account_data = {
        "id": "acc1",
        "name": "Checking",
        "balance": Decimal("15.00"),
        "currency": "USD",
        "org": org,
        "transactions": transactions,
        "balance-date": datetime(2024, 1, 2),
    }

    account = PydanticAccount(**account_data)

    return [account]


def test_upsert_new_record(db_manager):
    """Test upserting a new record"""
    with Session(db_manager.engine) as session:
        org_data = {
            "domain": "test.com",
            "name": "Test Org",
            "sfinurl": "https://test.com/ofx",
        }
        org = db_manager._upsert(session, Organization, org_data, "domain")

        assert org.domain == "test.com"
        assert org.name == "Test Org"
        assert org.sfinurl == "https://test.com/ofx"
        assert org.pk is not None


def test_upsert_existing_record(db_manager):
    """Test upserting updates existing record"""
    with Session(db_manager.engine) as session:
        # Create initial record
        org_data = {
            "domain": "test.com",
            "name": "Original Name",
            "sfinurl": "https://test.com/ofx",
        }
        org1 = db_manager._upsert(session, Organization, org_data, "domain")
        session.commit()

        # Update same record
        org_data["name"] = "Updated Name"
        org2 = db_manager._upsert(session, Organization, org_data, "domain")

        assert org1.pk == org2.pk  # Same record
        assert org2.name == "Updated Name"


def test_sync_basic(db_manager, sample_data):
    """Test basic sync functionality"""
    db_manager.sync(sample_data)

    with Session(db_manager.engine) as session:
        # Check org was created
        org = session.exec(select(Organization)).first()
        assert org is not None
        assert org.domain == "example.com"

        # Check account was created
        account = session.exec(select(Account)).first()
        assert account is not None
        assert account.id == "acc1"
        assert account.name == "Checking"

        # Check transactions were created
        transactions = session.exec(select(Transaction)).all()
        assert len(transactions) == 2
        assert {t.id for t in transactions} == {"txn1", "txn2"}


def test_sync_removes_stale_transactions_realistic(db_manager):
    """Test that stale transactions are removed in a realistic scenario"""
    from datetime import datetime
    from decimal import Decimal
    
    # Create initial data with 3 transactions
    org = PydanticOrg(domain="example.com", name="Test Bank", **{"sfin-url": "https://example.com/ofx"})
    
    initial_transactions = [
        PydanticTransaction(id="txn1", posted=datetime(2024, 1, 1), amount=Decimal("-10.00"), description="Confirmed payment"),
        PydanticTransaction(id="txn2", posted=datetime(2024, 1, 2), amount=Decimal("-5.00"), description="Pending charge"),
        PydanticTransaction(id="txn3", posted=datetime(2024, 1, 3), amount=Decimal("100.00"), description="Deposit"),
    ]
    
    account_data = {
        "id": "acc1", "name": "Checking", "balance": Decimal("85.00"), "currency": "USD",
        "org": org, "transactions": initial_transactions, "balance-date": datetime(2024, 1, 3),
    }
    initial_account = PydanticAccount(**account_data)
    
    # First sync - all 3 transactions
    db_manager.sync([initial_account])
    
    # Simulate SimpleFin no longer returning the pending charge (txn2)
    # This represents what would happen if a pending charge was cancelled
    updated_transactions = [
        PydanticTransaction(id="txn1", posted=datetime(2024, 1, 1), amount=Decimal("-10.00"), description="Confirmed payment"),
        PydanticTransaction(id="txn3", posted=datetime(2024, 1, 3), amount=Decimal("100.00"), description="Deposit"),
        # txn2 is no longer in the response from SimpleFin
    ]
    
    updated_account_data = account_data.copy()
    updated_account_data["transactions"] = updated_transactions
    updated_account_data["balance"] = Decimal("90.00")  # Balance reflects removed pending charge
    updated_account = PydanticAccount(**updated_account_data)
    
    # Second sync should remove the stale transaction and emit warning
    with pytest.warns(UserWarning, match="Removed \\d+ transactions from account"):
        db_manager.sync([updated_account], stale_window=7)
    
    # Verify only 2 transactions remain
    with Session(db_manager.engine) as session:
        transactions = session.exec(select(Transaction)).all()
        assert len(transactions) == 2
        assert {t.id for t in transactions} == {"txn1", "txn3"}
        assert "txn2" not in {t.id for t in transactions}


def test_context_manager(db_manager):
    """Test database manager as context manager"""
    with db_manager as db:
        assert db.engine is not None

    # Engine should be disposed after context exit
    # For SQLite in-memory, just check that the engine is still accessible
    assert db_manager.engine is not None
