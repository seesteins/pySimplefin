from niquests import Session, post
from urllib.parse import urlparse
import base64

class SimpleFINClient:
    def __init__(self, username: str, password: str, scheme: str, hostname: str) -> None:
        self.username = username
        self.password = password
        self.hostname = hostname
        self.scheme = scheme
        self.url = f"{self.scheme}://{self.username}:{self.password}@{self.hostname}"
        print(self.url)
        self._session = Session(base_url=self.url)
        
    @classmethod
    def setup(cls, setup_token: str) -> "SimpleFINClient":
        """
        Authenticate with SimpleFIN using the setup token.
        """
        claim_url = base64.b64decode(setup_token).decode('utf-8')
        response = post(claim_url)
        if response.status_code != 200:
            raise Exception(f"Failed to claim token: {response.status_code}")
        access_url = response.text
        parsed = urlparse(access_url)
        return cls(
            username = parsed.username,
            password = parsed.password,
            scheme = parsed.scheme,
            hostname = parsed.hostname
        )

user = "demo"
password = "demo"
scheme = "https"
hostname = "beta-bridge.simplefin.org"
client = SimpleFINClient(username=user, password=password, scheme=scheme, hostname=hostname)
client._session.close()