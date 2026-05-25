import base64
import logging
import string
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Union
from urllib.parse import urlparse
from warnings import warn

from niquests import Session, exceptions, post

from pysimplefin.models import Account

logger = logging.getLogger(__name__)


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

    def __str__(self):
        return self.url

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
            if e.response and e.response.status_code == 402:
                warn("402: Client Error. Payment is required.")
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
    SIMPLEFIN_MAX_DAYS = 45

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

        Requests spanning more than 90 days are automatically split into
        two recursive halves and the results are merged transparently. Account
        metadata (balance, balance-date, etc.) is taken from the most recent
        half; transactions are de-duplicated by id across all chunks.

        Args:
            start_date (Optional[datetime], optional): Start date to retrieve transactions. Defaults to None.
            end_date (Optional[datetime], optional): End date to retrieve transactions. This is non-inclusive. Defaults to None.
            account (Optional[List[Union[str, Account]]], optional): Either an account id string or an Account class. Allows filtering by account. Defaults to None.
            balances_only (bool, optional): Setting this to True will not return any transactions. Defaults to False.

        Returns:
            List[Account]: Returns a list of accounts that contains all of the associate data. Transactions, Organizations, etc.
        """

        def merge(left: List[Account], right: List[Account]) -> List[Account]:
            """Merge two account lists, taking metadata from the right (more recent) side
            and de-duplicating transactions by id across both."""
            merged: dict[str, Account] = {acc.id: acc for acc in right}
            all_transactions: dict[str, dict[str, object]] = {
                acc_id: {} for acc_id in merged
            }
            for chunk in (left, right):
                for acc in chunk:
                    if acc.id not in all_transactions:
                        merged[acc.id] = acc
                        all_transactions[acc.id] = {}
                    for txn in acc.transactions:
                        all_transactions[acc.id][txn.id] = txn
            return [
                acc.model_copy(
                    update={"transactions": list(all_transactions[acc_id].values())}
                )
                for acc_id, acc in merged.items()
            ]

        effective_end = end_date or datetime.now()
        effective_start = start_date or effective_end - timedelta(
            days=self.SIMPLEFIN_MAX_DAYS
        )

        total_days = (effective_end - effective_start).days
        if total_days <= self.SIMPLEFIN_MAX_DAYS:
            # Base case: window fits in a single request
            logger.info(
                "Fetching %s -> %s (%d days)",
                effective_start.date(),
                effective_end.date(),
                total_days,
            )
            params = {}
            params["start-date"] = int(effective_start.timestamp())
            params["end-date"] = int(effective_end.timestamp())
            if pending:
                params["pending"] = "1"
            if account is not None:
                params["account"] = [
                    acc if isinstance(acc, str) else acc.id for acc in account
                ]
            if balances_only:
                params["balances-only"] = "1"
            response = self._session.get("/accounts", params=params)
            response.raise_for_status()
            data = response.json()
            for error in data["errors"]:
                warn(self.sanitize_error(error))
            return [Account.model_validate(a) for a in data["accounts"]]

        # Recursive case: split the window in half and merge both sides
        midpoint = effective_start + (effective_end - effective_start) / 2
        logger.info(
            "Request spans %d days; splitting at midpoint %s.",
            total_days,
            midpoint.date(),
        )
        return merge(
            self.get_data(
                start_date=effective_start,
                end_date=midpoint,
                pending=pending,
                account=account,
                balances_only=balances_only,
            ),
            self.get_data(
                start_date=midpoint,
                end_date=effective_end,
                pending=pending,
                account=account,
                balances_only=balances_only,
            ),
        )

    @staticmethod
    def sanitize_error(error: str):
        sanitized = str(error).strip()
        sanitized = "".join(char for char in sanitized if char in string.printable)
        return " ".join(sanitized.split())

    @property
    def info(self):
        """Returns the info for the server"""
        response = self._session.get("/info")
        response.raise_for_status()
        return response.json()
