import niquests as requests
import warnings

import base64
from urllib.parse import urlparse

def get_access_url(setup_token: str) -> str:
    try:
        claim_url = base64.b64decode(setup_token).decode("utf-8")
        response = requests.post(claim_url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            warnings.warn("403: Client Error. If this token has not been previously claimed it may be compromised.")
            raise e
        else:
            raise e
    return response.text


print(get_access_url("aHR0cHM6Ly9iZXRhLWJyaWRnZS5zaW1wbGVmaW4ub3JnL3NpbXBsZWZpbi9jbGFpbS9ERU1PLXYyLUZBOTBBNDVGNzZDRUFENjFFNjhB"))