import pytest
import warnings
import base64
import niquests as requests
from unittest.mock import patch, Mock

# Import the function to test
from ..src.setup import get_access_url

def test_get_access_url_success():
    """Test successful exchange of setup token for access URL"""
    # Mock setup token
    setup_token = base64.b64encode(b"https://example.com/claim/TEST-TOKEN").decode("utf-8")
    
    # Mock response
    mock_response = Mock()
    mock_response.text = "https://example.com/access/ACCESS-TOKEN"
    mock_response.status_code = 200
    
    with patch("niquests.post", return_value=mock_response):
        access_url = get_access_url(setup_token)
        assert access_url == "https://example.com/access/ACCESS-TOKEN"

def test_get_access_url_403_error():
    """Test handling of 403 error"""
    setup_token = base64.b64encode(b"https://example.com/claim/TEST-TOKEN").decode("utf-8")
    
    # Create a mock 403 response
    mock_response = Mock()
    mock_response.status_code = 403
    
    # Create a mock HTTPError
    mock_http_error = requests.exceptions.HTTPError()
    mock_http_error.response = mock_response
    
    with patch("niquests.post", side_effect=mock_http_error):
        with pytest.warns(UserWarning, match="403: Client Error"):
            with pytest.raises(requests.exceptions.HTTPError):
                get_access_url(setup_token)

def test_get_access_url_other_http_error():
    """Test handling of other HTTP errors"""
    setup_token = base64.b64encode(b"https://example.com/claim/TEST-TOKEN").decode("utf-8")
    
    # Create a mock 500 response
    mock_response = Mock()
    mock_response.status_code = 500
    
    # Create a mock HTTPError
    mock_http_error = requests.exceptions.HTTPError()
    mock_http_error.response = mock_response
    
    with patch("niquests.post", side_effect=mock_http_error):
        with pytest.raises(requests.exceptions.HTTPError):
            get_access_url(setup_token)