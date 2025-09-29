import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Union
from urllib.parse import urlparse
from warnings import warn

from niquests import Session, exceptions, post

from simplefin.models import Account


@dataclass
class Auth(ABC):
    @property
    @abstractmethod
    def session(self) -> Session:
        pass


@dataclass
class DefaultAuth(Auth):
    username: str
    password: str
    hostname: str
    path: str

    @property
    def url(self) -> str:
        return f"https://{self.username}:{self.password}@{self.hostname}{self.path}"

    @property
    def session(self) -> Session:
        return Session(base_url=self.url)

    @classmethod
    def from_url(cls, url: str) -> "DefaultAuth":
        """
        Setup a DefaultAuth using an access url that is provided by the claim token.
        """
        parsed = urlparse(url)
        if not parsed.username:
            raise ValueError("URL missing username")
        if not parsed.password:
            raise ValueError("URL missing password")
        if not parsed.hostname:
            raise ValueError("URL missing hostname")

        return cls(
            username=parsed.username,
            password=parsed.password,
            hostname=parsed.hostname,
            path=parsed.path or "",
        )

    @classmethod
    def claim_token(cls, setup_token: str) -> "DefaultAuth":
        """Authenticate with SimpleFIN using the setup token.

        Args:
            setup_token (str): base 64 encoded setup_token from your simplefin provider

        Raises:
            e: Caught HTTPError
            Exception: Raises an exception if a 403 status is encountered and warns the user that their token may be compromised

        Returns:
            DefaultAuth: Returns an Auth class that can be used to generate a client
        """
        claim_url = base64.b64decode(setup_token).decode("utf-8")
        try:
            response = post(claim_url)
        except exceptions.HTTPError as e:
            if e.response and e.response.status_code == 403:
                warn(
                    "403: Client Error. If this token has not been previously claimed it may be compromised."
                )
            else:
                warn(f"HTTP Error occurred: {e}")
            raise e
        access_url = response.text
        if not access_url:
            raise Exception("Empty access URL returned")
        return cls.from_url(url=access_url)


class SimpleFinClient:
    auth: Auth
    _session: Session

    def __init__(self, auth: Auth):
        self.auth = auth
        self._session = self.auth.session

    def get_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,  # Noninclusive
        pending: bool = False,
        account: Optional[List[Union[str, Account]]] = None,
        balances_only: bool = False,
    ) -> List[Account]:
        """Retrieves data from a simplefin /accounts endpoint.

        Args:
            start_date (Optional[datetime], optional): Start date to retrieve transactions. Defaults to None.
            end_date (Optional[datetime], optional): End date to retrieve transactions. This is non-inclusive. Defaults to None.
            account (Optional[List[Union[str, Account]]], optional): Either an account id string or an Account class. Allows filtering by account. Defaults to None.
            balances_only (bool, optional): Setting this to True will not return any transactions. Defaults to False.

        Returns:
            List[Account]: Returns a list of accounts that contains all of the associate data. Transactions, Organizations, etc.
        """
        # Build query parameters
        params = {}

        if start_date is not None:
            params["start-date"] = int(start_date.timestamp())
        if end_date is not None:
            params["end-date"] = int(end_date.timestamp())
        if pending:
            params["pending"] = "1"
        if account is not None:
            # Handle both string IDs and Account objects
            account_ids = []
            for acc in account:
                if isinstance(acc, str):
                    account_ids.append(acc)
                else:
                    # Assume it's an Account object with an id attribute
                    account_ids.append(acc.id)
            params["account"] = account_ids
        if balances_only:
            params["balances-only"] = "1"

        response = self._session.get("/accounts", params=params)
        response.raise_for_status()
        json = response.json()
        errors = json["errors"]
        for error in errors:
            warn(str(error))  # TODO Sanitize this
        accounts = json["accounts"]
        validated_data = [Account.model_validate(account) for account in accounts]
        return validated_data

    @property
    def info(self):
        """Returns the info for the server"""
        response = self._session.get("/info")
        response.raise_for_status()
        return response.json()


def main():
    # demo_url = "https://demo:demo@beta-bridge.simplefin.org"
    user = "demo"
    password = "demo"
    hostname = "beta-bridge.simplefin.org"
    path = "/simplefin"
    auth = DefaultAuth(username=user, password=password, hostname=hostname, path=path)
    client = SimpleFinClient(auth=auth)
    print(client.info)

    client._session.close()


if __name__ == "__main__":
    main()
