import base64
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from niquests import Session, exceptions

from pysimplefin._session import Auth, DefaultAuth, SimpleFinClient
from pysimplefin.models import Account


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
        assert auth.url == "https://user:pass@example.com/api"

        # Test no path case
        auth_no_path = DefaultAuth(
            username="user", password="pass", hostname="example.com", path=""
        )
        assert auth_no_path.url == "https://user:pass@example.com"

    def test_session_property(self):
        auth = DefaultAuth(
            username="user", password="pass", hostname="example.com", path="/api"
        )
        session = auth.session
        assert isinstance(session, Session)
        assert session.base_url == "https://user:pass@example.com/api"

    def test_from_url_valid(self):
        # Test with path
        url = "https://user:pass@example.com/api/path"
        auth = DefaultAuth.from_url(url)
        assert auth.username == "user"
        assert auth.password == "pass"
        assert auth.hostname == "example.com"
        assert auth.path == "/api/path"

        # Test without path
        url_no_path = "https://user:pass@example.com"
        auth_no_path = DefaultAuth.from_url(url_no_path)
        assert auth_no_path.path == ""

    def test_from_url_validation_errors(self):
        with pytest.raises(ValueError, match="URL missing username"):
            DefaultAuth.from_url("https://:pass@example.com/api")

        with pytest.raises(ValueError, match="URL missing password"):
            DefaultAuth.from_url("https://user@example.com/api")

        with pytest.raises(ValueError, match="URL missing hostname"):
            DefaultAuth.from_url("https://user:pass@/api")

    @patch("pysimplefin._session.post")
    def test_claim_token_success(self, mock_post):
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()
        access_url = "https://user:pass@api.example.com/path"

        mock_response = Mock()
        mock_response.text = access_url
        mock_post.return_value = mock_response

        auth = DefaultAuth.claim_token(setup_token)

        mock_post.assert_called_once_with("https://claim.example.com/token")
        assert auth.username == "user"
        assert auth.password == "pass"
        assert auth.hostname == "api.example.com"
        assert auth.path == "/path"

    @patch("pysimplefin._session.post")
    def test_claim_token_empty_response(self, mock_post):
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()
        mock_response = Mock()
        mock_response.text = ""
        mock_post.return_value = mock_response

        with pytest.raises(Exception, match="Empty access URL returned"):
            DefaultAuth.claim_token(setup_token)

    @patch("pysimplefin._session.post")
    @patch("pysimplefin._session.warn")
    def test_claim_token_http_errors(self, mock_warn, mock_post):
        setup_token = base64.b64encode(b"https://claim.example.com/token").decode()

        # Test 403 error
        mock_response = Mock()
        mock_response.status_code = 403
        http_error = exceptions.HTTPError("403 Forbidden")
        http_error.response = mock_response
        mock_post.side_effect = http_error

        with pytest.raises(exceptions.HTTPError):
            DefaultAuth.claim_token(setup_token)

        mock_warn.assert_called_with(
            "403: Client Error. If this token has not been previously claimed it may be compromised."
        )

        # Test other HTTP error
        mock_warn.reset_mock()
        mock_response.status_code = 500
        http_error = exceptions.HTTPError("500 Internal Server Error")
        http_error.response = mock_response
        mock_post.side_effect = http_error

        with pytest.raises(exceptions.HTTPError):
            DefaultAuth.claim_token(setup_token)

        mock_warn.assert_called_with(f"HTTP Error occurred: {http_error}")


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

    def test_get_data_basic(self, client):
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

        accounts = client.get_data()

        client._session.get.assert_called_once_with("/accounts", params={})
        mock_response.raise_for_status.assert_called_once()
        assert len(accounts) == 1
        assert isinstance(accounts[0], Account)

    def test_get_data_with_params(self, client):
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        account_list = ["acc1", "acc2"]

        mock_response = Mock()
        mock_response.json.return_value = {"errors": [], "accounts": []}
        client._session.get.return_value = mock_response

        client.get_data(
            start_date=start_date,
            end_date=end_date,
            pending=True,
            account=account_list,
            balances_only=True,
        )

        expected_params = {
            "start-date": int(start_date.timestamp()),
            "end-date": int(end_date.timestamp()),
            "pending": "1",
            "account": ["acc1", "acc2"],
            "balances-only": "1",
        }
        client._session.get.assert_called_once_with("/accounts", params=expected_params)

    def test_get_data_account_objects(self, client):
        mock_account = Mock()
        mock_account.id = "acc1"

        mock_response = Mock()
        mock_response.json.return_value = {"errors": [], "accounts": []}
        client._session.get.return_value = mock_response

        client.get_data(account=[mock_account, "acc2"])

        expected_params = {"account": ["acc1", "acc2"]}
        client._session.get.assert_called_once_with("/accounts", params=expected_params)

    @patch("pysimplefin._session.warn")
    def test_get_data_with_errors(self, mock_warn, client):
        mock_response = Mock()
        mock_response.json.return_value = {
            "errors": ["Error 1", "Error 2"],
            "accounts": [],
        }
        client._session.get.return_value = mock_response

        client.get_data()

        assert mock_warn.call_count == 2
        mock_warn.assert_any_call("Error 1")
        mock_warn.assert_any_call("Error 2")

    def test_info_property(self, client):
        expected_info = {"version": "1.0", "name": "Test Bank"}
        mock_response = Mock()
        mock_response.json.return_value = expected_info
        client._session.get.return_value = mock_response

        info = client.info

        client._session.get.assert_called_once_with("/info")
        mock_response.raise_for_status.assert_called_once()
        assert info == expected_info

    def test_http_errors(self, client):
        client._session.get.return_value.raise_for_status.side_effect = (
            exceptions.HTTPError("500 Error")
        )

        with pytest.raises(exceptions.HTTPError):
            client.get_data()

        with pytest.raises(exceptions.HTTPError):
            client.info


class TestAuth:
    def test_auth_abstract_implementation(self):
        assert hasattr(Auth, "__abstractmethods__")
        assert "session" in Auth.__abstractmethods__

        class ConcreteAuth(Auth):
            @property
            def session(self) -> Session:
                return Session()

        auth = ConcreteAuth()
        assert isinstance(auth.session, Session)