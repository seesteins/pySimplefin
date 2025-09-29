import base64
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from niquests import Session, exceptions

from simplefin._session import Auth, DefaultAuth, SimpleFinClient
from simplefin.models import Account


class TestDefaultAuth:
    def test_init(self):
        auth = DefaultAuth(
            username="testuser",
            password="testpass",
            hostname="example.com",
            path="/api",
        )
        assert auth.username == "testuser"
        assert auth.password == "testpass"
        assert auth.hostname == "example.com"
        assert auth.path == "/api"

    def test_url_property(self):
        auth = DefaultAuth(
            username="user", password="pass", hostname="example.com", path="/api"
        )
        expected_url = "https://user:pass@example.com/api"
        assert auth.url == expected_url

    def test_url_property_no_path(self):
        auth = DefaultAuth(
            username="user", password="pass", hostname="example.com", path=""
        )
        expected_url = "https://user:pass@example.com"
        assert auth.url == expected_url

    def test_session_property(self):
        auth = DefaultAuth(
            username="user", password="pass", hostname="example.com", path="/api"
        )
        session = auth.session
        assert isinstance(session, Session)
        assert session.base_url == "https://user:pass@example.com/api"

    def test_from_url_valid(self):
        url = "https://user:pass@example.com/api/path"
        auth = DefaultAuth.from_url(url)

        assert auth.username == "user"
        assert auth.password == "pass"
        assert auth.hostname == "example.com"
        assert auth.path == "/api/path"

    def test_from_url_no_path(self):
        url = "https://user:pass@example.com"
        auth = DefaultAuth.from_url(url)

        assert auth.username == "user"
        assert auth.password == "pass"
        assert auth.hostname == "example.com"
        assert auth.path == ""

    def test_from_url_missing_username(self):
        url = "https://:pass@example.com/api"
        with pytest.raises(ValueError, match="URL missing username"):
            DefaultAuth.from_url(url)

    def test_from_url_missing_password(self):
        url = "https://user@example.com/api"
        with pytest.raises(ValueError, match="URL missing password"):
            DefaultAuth.from_url(url)

    def test_from_url_missing_hostname(self):
        url = "https://user:pass@/api"
        with pytest.raises(ValueError, match="URL missing hostname"):
            DefaultAuth.from_url(url)

    @patch("simplefin._session.post")
    def test_claim_token_success(self, mock_post):
        # Setup
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()
        access_url = "https://user:pass@api.example.com/path"

        mock_response = Mock()
        mock_response.text = access_url
        mock_post.return_value = mock_response

        # Execute
        auth = DefaultAuth.claim_token(setup_token)

        # Verify
        mock_post.assert_called_once_with("https://claim.example.com/token")
        assert auth.username == "user"
        assert auth.password == "pass"
        assert auth.hostname == "api.example.com"
        assert auth.path == "/path"

    @patch("simplefin._session.post")
    def test_claim_token_empty_response(self, mock_post):
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()

        mock_response = Mock()
        mock_response.text = ""
        mock_post.return_value = mock_response

        with pytest.raises(Exception, match="Empty access URL returned"):
            DefaultAuth.claim_token(setup_token)

    @patch("simplefin._session.post")
    @patch("simplefin._session.warn")
    def test_claim_token_403_error(self, mock_warn, mock_post):
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()

        mock_response = Mock()
        mock_response.status_code = 403
        http_error = exceptions.HTTPError("403 Forbidden")
        http_error.response = mock_response
        mock_post.side_effect = http_error

        with pytest.raises(exceptions.HTTPError):
            DefaultAuth.claim_token(setup_token)

        mock_warn.assert_called_once_with(
            "403: Client Error. If this token has not been previously claimed it may be compromised."
        )

    @patch("simplefin._session.post")
    @patch("simplefin._session.warn")
    def test_claim_token_other_http_error(self, mock_warn, mock_post):
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()

        mock_response = Mock()
        mock_response.status_code = 500
        http_error = exceptions.HTTPError("500 Internal Server Error")
        http_error.response = mock_response
        mock_post.side_effect = http_error

        with pytest.raises(exceptions.HTTPError):
            DefaultAuth.claim_token(setup_token)

        mock_warn.assert_called_once_with(f"HTTP Error occurred: {http_error}")

    @patch("simplefin._session.post")
    @patch("simplefin._session.warn")
    def test_claim_token_http_error_no_response(self, mock_warn, mock_post):
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()

        http_error = exceptions.HTTPError("Network error")
        http_error.response = None
        mock_post.side_effect = http_error

        with pytest.raises(exceptions.HTTPError):
            DefaultAuth.claim_token(setup_token)

        mock_warn.assert_called_once_with(f"HTTP Error occurred: {http_error}")


class TestSimpleFinClient:
    @pytest.fixture
    def mock_auth(self):
        auth = Mock(spec=Auth)
        auth.session = Mock(spec=Session)
        return auth

    @pytest.fixture
    def client(self, mock_auth):
        return SimpleFinClient(mock_auth)

    def test_init(self, mock_auth):
        client = SimpleFinClient(mock_auth)
        assert client.auth == mock_auth
        assert client._session == mock_auth.session

    def test_get_data_no_params(self, client):
        # Setup mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "errors": [],
            "accounts": [
                {
                    "id": "acc1",
                    "name": "Test Account",
                    "currency": "USD",
                    "balance": 1000,
                    "available-balance": 950,
                    "balance-date": 1234567890,
                    "transactions": [],
                    "org": {
                        "domain": "example.com",
                        "id": "org1",
                        "name": "Test Bank",
                        "url": "https://example.com",
                        "sfin-url": "https://example.com/simplefin",
                    },
                }
            ],
        }
        client._session.get.return_value = mock_response

        # Execute
        accounts = client.get_data()

        # Verify
        client._session.get.assert_called_once_with("/accounts", params={})
        mock_response.raise_for_status.assert_called_once()
        assert len(accounts) == 1
        assert isinstance(accounts[0], Account)

    def test_get_data_with_all_params(self, client):
        # Setup
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        account_list = ["acc1", "acc2"]

        mock_response = Mock()
        mock_response.json.return_value = {"errors": [], "accounts": []}
        client._session.get.return_value = mock_response

        # Execute
        client.get_data(
            start_date=start_date,
            end_date=end_date,
            pending=True,
            account=account_list,
            balances_only=True,
        )

        # Verify
        expected_params = {
            "start-date": int(start_date.timestamp()),
            "end-date": int(end_date.timestamp()),
            "pending": "1",
            "account": ["acc1", "acc2"],
            "balances-only": "1",
        }
        client._session.get.assert_called_once_with("/accounts", params=expected_params)

    def test_get_data_with_account_objects(self, client):
        # Setup mock Account objects
        mock_account1 = Mock()
        mock_account1.id = "acc1"
        mock_account2 = Mock()
        mock_account2.id = "acc2"

        mock_response = Mock()
        mock_response.json.return_value = {"errors": [], "accounts": []}
        client._session.get.return_value = mock_response

        # Execute
        client.get_data(account=[mock_account1, mock_account2])

        # Verify
        expected_params = {"account": ["acc1", "acc2"]}
        client._session.get.assert_called_once_with("/accounts", params=expected_params)

    def test_get_data_mixed_account_types(self, client):
        # Setup
        mock_account = Mock()
        mock_account.id = "acc1"

        mock_response = Mock()
        mock_response.json.return_value = {"errors": [], "accounts": []}
        client._session.get.return_value = mock_response

        # Execute
        client.get_data(account=[mock_account, "acc2"])

        # Verify
        expected_params = {"account": ["acc1", "acc2"]}
        client._session.get.assert_called_once_with("/accounts", params=expected_params)

    @patch("simplefin._session.warn")
    def test_get_data_with_errors(self, mock_warn, client):
        # Setup
        mock_response = Mock()
        mock_response.json.return_value = {
            "errors": ["Error 1", "Error 2"],
            "accounts": [],
        }
        client._session.get.return_value = mock_response

        # Execute
        client.get_data()

        # Verify warnings were called
        assert mock_warn.call_count == 2
        mock_warn.assert_any_call("Error 1")
        mock_warn.assert_any_call("Error 2")

    def test_info_property(self, client):
        # Setup
        expected_info = {"version": "1.0", "name": "Test Bank"}
        mock_response = Mock()
        mock_response.json.return_value = expected_info
        client._session.get.return_value = mock_response

        # Execute
        info = client.info

        # Verify
        client._session.get.assert_called_once_with("/info")
        mock_response.raise_for_status.assert_called_once()
        assert info == expected_info

    def test_get_data_http_error(self, client):
        # Setup
        client._session.get.return_value.raise_for_status.side_effect = (
            exceptions.HTTPError("500 Error")
        )

        # Execute & Verify
        with pytest.raises(exceptions.HTTPError):
            client.get_data()

    def test_info_http_error(self, client):
        # Setup
        client._session.get.return_value.raise_for_status.side_effect = (
            exceptions.HTTPError("500 Error")
        )

        # Execute & Verify
        with pytest.raises(exceptions.HTTPError):
            client.info


class TestAuth:
    def test_auth_is_abstract_base_class(self):
        # Verify that Auth is properly defined as ABC
        assert hasattr(Auth, "__abstractmethods__")
        assert "session" in Auth.__abstractmethods__

    def test_concrete_implementation_works(self):
        # Test that a proper concrete implementation works
        class ConcreteAuth(Auth):
            @property
            def session(self) -> Session:
                return Session()

        # Should be able to instantiate concrete implementation
        auth = ConcreteAuth()
        assert isinstance(auth.session, Session)


# Integration test
class TestIntegration:
    def test_full_workflow_with_real_auth(self):
        # Create a real DefaultAuth instance
        auth = DefaultAuth(
            username="demo",
            password="demo",
            hostname="beta-bridge.simplefin.org",
            path="/simplefin",
        )

        # Verify the auth object works
        assert auth.url == "https://demo:demo@beta-bridge.simplefin.org/simplefin"
        assert isinstance(auth.session, Session)

        # Create client
        client = SimpleFinClient(auth)
        assert client.auth == auth
        assert isinstance(client._session, Session)
