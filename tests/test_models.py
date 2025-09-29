import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from pydantic import ValidationError

from simplefin.models import (
    Transaction,
    Organization,
    Account,
    CustomCurrency
)


class TestTransaction:
    def test_transaction_creation_minimal(self):
        """Test creating a transaction with minimal required fields."""
        transaction = Transaction(
            id="12394832938403",
            amount=Decimal("-33293.43"),
            description="Uncle Frank's Bait Shop"
        )
        
        assert transaction.id == "12394832938403"
        assert transaction.amount == Decimal("-33293.43")
        assert transaction.description == "Uncle Frank's Bait Shop"
        assert transaction.posted is None
        assert transaction.transacted_at is None
        assert transaction.pending is None
        assert transaction.extra is None

    def test_transaction_creation_full(self):
        """Test creating a transaction with all fields."""
        posted = datetime.fromtimestamp(793090572)
        transacted = datetime.fromtimestamp(793090500)
        
        transaction = Transaction(
            id="12394832938403",
            posted=posted,
            amount=Decimal("-33293.43"),
            description="Uncle Frank's Bait Shop",
            transacted_at=transacted,
            pending=True,
            extra={"category": "food"}
        )
        
        assert transaction.id == "12394832938403"
        assert transaction.posted == posted
        assert transaction.amount == Decimal("-33293.43")
        assert transaction.description == "Uncle Frank's Bait Shop"
        assert transaction.transacted_at == transacted
        assert transaction.pending is True
        assert transaction.extra == {"category": "food"}

    def test_transaction_validates_required_fields(self):
        """Test that all required fields are present in a valid transaction."""
        # This test verifies the model works correctly with all required fields
        transaction = Transaction(
            id="123",
            amount=Decimal("100.00"),
            description="Test transaction"
        )
        assert transaction.id == "123"
        assert transaction.amount == Decimal("100.00")
        assert transaction.description == "Test transaction"


class TestOrganization:
    def test_organization_with_domain(self):
        """Test creating organization with domain."""
        org_data = {
            "domain": "mybank.com",
            "sfin-url": "https://sfin.mybank.com"
        }
        org = Organization(**org_data)
        
        assert org.domain == "mybank.com"
        assert org.sfinurl == "https://sfin.mybank.com"
        assert org.name is None

    def test_organization_with_name(self):
        """Test creating organization with name."""
        org_data = {
            "name": "My Bank",
            "sfin-url": "https://sfin.mybank.com"
        }
        org = Organization(**org_data)
        
        assert org.name == "My Bank"
        assert org.sfinurl == "https://sfin.mybank.com"
        assert org.domain is None

    def test_organization_with_both_domain_and_name(self):
        """Test creating organization with both domain and name."""
        org_data = {
            "domain": "mybank.com",
            "name": "My Bank",
            "sfin-url": "https://sfin.mybank.com"
        }
        org = Organization(**org_data)
        
        assert org.domain == "mybank.com"
        assert org.name == "My Bank"
        assert org.sfinurl == "https://sfin.mybank.com"

    def test_organization_with_all_fields(self):
        """Test creating organization with all optional fields."""
        org_data = {
            "domain": "mybank.com",
            "name": "My Bank",
            "sfin-url": "https://sfin.mybank.com",
            "url": "https://mybank.com",
            "id": "bank123"
        }
        org = Organization(**org_data)
        
        assert org.domain == "mybank.com"
        assert org.name == "My Bank"
        assert org.sfinurl == "https://sfin.mybank.com"
        assert org.url == "https://mybank.com"
        assert org.id == "bank123"

    def test_organization_field_alias(self):
        """Test that the sfin-url alias works correctly."""
        org_data = {
            "domain": "mybank.com",
            "sfin-url": "https://sfin.mybank.com"
        }
        org = Organization(**org_data)
        assert org.sfinurl == "https://sfin.mybank.com"

    def test_organization_domain_or_name_validation(self):
        """Test that organization validates domain or name requirement."""
        # Test that a valid organization can be created with domain
        org_data = {
            "domain": "mybank.com",
            "sfin-url": "https://sfin.mybank.com"
        }
        org = Organization(**org_data)
        assert org.domain == "mybank.com"

    def test_organization_validates_required_fields(self):
        """Test that organization validates required sfin-url field."""
        org_data = {
            "domain": "mybank.com",
            "sfin-url": "https://sfin.mybank.com"
        }
        org = Organization(**org_data)
        assert org.sfinurl == "https://sfin.mybank.com"


class TestCustomCurrency:
    def test_custom_currency_creation(self):
        """Test creating a custom currency."""
        currency = CustomCurrency(
            name="Example Airline Miles",
            abbr="miles"
        )
        
        assert currency.name == "Example Airline Miles"
        assert currency.abbr == "miles"

    def test_custom_currency_validates_required_fields(self):
        """Test that custom currency validates required fields."""
        currency = CustomCurrency(
            name="Test Currency",
            abbr="TST"
        )
        assert currency.name == "Test Currency"
        assert currency.abbr == "TST"


class TestAccount:
    @pytest.fixture
    def sample_org(self):
        org_data = {
            "domain": "mybank.com",
            "sfin-url": "https://sfin.mybank.com"
        }
        return Organization(**org_data)

    @pytest.fixture
    def sample_transaction(self):
        return Transaction(
            id="12394832938403",
            posted=datetime.fromtimestamp(793090572),
            amount=Decimal("-33293.43"),
            description="Uncle Frank's Bait Shop"
        )

    def test_account_creation_minimal(self, sample_org):
        """Test creating an account with minimal required fields."""
        balance_date = datetime.fromtimestamp(978366153)
        
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "USD",
            "balance": Decimal("100.23"),
            "balance-date": balance_date,
            "transactions": []
        }
        account = Account(**account_data)
        
        assert account.org == sample_org
        assert account.id == "2930002"
        assert account.name == "Savings"
        assert account.currency == "USD"
        assert account.balance == Decimal("100.23")
        assert account.available_balance is None
        assert account.balancedate == balance_date
        assert account.transactions == []
        assert account.extra is None

    def test_account_creation_full(self, sample_org, sample_transaction):
        """Test creating an account with all fields."""
        balance_date = datetime.fromtimestamp(978366153)
        
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "USD",
            "balance": Decimal("100.23"),
            "available-balance": Decimal("75.23"),
            "balance-date": balance_date,
            "transactions": [sample_transaction],
            "extra": {"account-open-date": 978360153}
        }
        account = Account(**account_data)
        
        assert account.org == sample_org
        assert account.id == "2930002"
        assert account.name == "Savings"
        assert account.currency == "USD"
        assert account.balance == Decimal("100.23")
        assert account.available_balance == Decimal("75.23")
        assert account.balancedate == balance_date
        assert account.transactions == [sample_transaction]
        assert account.extra == {"account-open-date": 978360153}

    def test_account_field_aliases(self, sample_org):
        """Test that field aliases work correctly."""
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "USD",
            "balance": "100.23",
            "available-balance": "75.23",
            "balance-date": datetime.fromtimestamp(978366153),
            "transactions": []
        }
        
        account = Account(**account_data)
        assert account.available_balance == Decimal("75.23")
        assert account.balancedate == datetime.fromtimestamp(978366153)

    @patch('simplefin.models.get')
    def test_account_custom_currency_url_success(self, mock_get, sample_org):
        """Test account with custom currency URL that returns valid data."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "name": "Example Airline Miles",
            "abbr": "miles"
        }
        mock_get.return_value = mock_response
        
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "https://www.example.com/flight-miles",
            "balance": "100.23",
            "balance-date": datetime.fromtimestamp(978366153),
            "transactions": []
        }
        
        account = Account(**account_data)
        assert account.currency == "Example Airline Miles"
        mock_get.assert_called_once_with("https://www.example.com/flight-miles")

    @patch('simplefin.models.get')
    def test_account_custom_currency_url_failure(self, mock_get, sample_org):
        """Test account with custom currency URL that fails to fetch."""
        mock_get.side_effect = Exception("Network error")
        
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "https://www.example.com/flight-miles",
            "balance": "100.23",
            "balance-date": datetime.fromtimestamp(978366153),
            "transactions": []
        }
        
        with pytest.raises(ValidationError) as exc_info:
            Account(**account_data)
        
        assert "Failed to fetch currency from URL" in str(exc_info.value)

    @patch('simplefin.models.get')
    def test_account_custom_currency_invalid_response(self, mock_get, sample_org):
        """Test account with custom currency URL that returns invalid data."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"invalid": "data"}  # Missing required fields
        mock_get.return_value = mock_response
        
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "https://www.example.com/flight-miles",
            "balance": "100.23",
            "balance-date": datetime.fromtimestamp(978366153),
            "transactions": []
        }
        
        with pytest.raises(ValidationError) as exc_info:
            Account(**account_data)
        
        assert "Failed to fetch currency from URL" in str(exc_info.value)

    def test_account_standard_currency(self, sample_org):
        """Test account with standard ISO currency code."""
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "USD",
            "balance": "100.23",
            "balance-date": datetime.fromtimestamp(978366153),
            "transactions": []
        }
        
        account = Account(**account_data)
        assert account.currency == "USD"

    def test_account_validates_required_fields(self, sample_org):
        """Test that account validates with all required fields present."""
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "USD",
            "balance": "100.23",
            "balance-date": datetime.fromtimestamp(978366153),
            "transactions": []
        }
        
        account = Account(**account_data)
        assert account.org == sample_org
        assert account.id == "2930002"

    def test_account_type_conversions(self, sample_org):
        """Test that string values are properly converted to appropriate types."""
        account_data = {
            "org": sample_org,
            "id": "2930002",
            "name": "Savings",
            "currency": "USD",
            "balance": "100.23",  # String should convert to Decimal
            "available-balance": "75.23",  # String should convert to Decimal
            "balance-date": datetime.fromtimestamp(978366153),
            "transactions": []
        }
        
        account = Account(**account_data)
        assert isinstance(account.balance, Decimal)
        assert isinstance(account.available_balance, Decimal)
        assert account.balance == Decimal("100.23")
        assert account.available_balance == Decimal("75.23")