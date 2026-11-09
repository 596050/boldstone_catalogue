import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import requests

from utils.ig_index.models import IGQuote, PositionState


DEMO_BASE_URL = "https://demo-api.ig.com/gateway/deal"
LIVE_BASE_URL = "https://api.ig.com/gateway/deal"


@dataclass(frozen=True)
class IGCredentials:
    username: str
    password: str
    api_key: str
    account_id: Optional[str] = None
    environment: str = "demo"

    @classmethod
    def from_env(cls) -> "IGCredentials":
        # IG calls the login field "identifier"; accept that as well as the
        # IG_USERNAME alias so a .env written in IG's own terms just works.
        username = os.environ.get("IG_USERNAME") or os.environ.get("IG_IDENTIFIER")
        missing = [
            label
            for label, value in (
                ("IG_USERNAME (or IG_IDENTIFIER)", username),
                ("IG_PASSWORD", os.environ.get("IG_PASSWORD")),
                ("IG_API_KEY", os.environ.get("IG_API_KEY")),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing IG environment variables: {', '.join(missing)}")
        return cls(
            username=str(username),
            password=os.environ["IG_PASSWORD"],
            api_key=os.environ["IG_API_KEY"],
            account_id=os.environ.get("IG_ACCOUNT_ID") or None,
            environment=os.environ.get("IG_ENVIRONMENT", "demo"),
        )

    @property
    def base_url(self) -> str:
        if self.environment.lower() == "live":
            return LIVE_BASE_URL
        if self.environment.lower() == "demo":
            return DEMO_BASE_URL
        raise ValueError("IG_ENVIRONMENT must be 'demo' or 'live'")


class IGRestClient:
    """Small IG REST adapter for the retail API.

    It intentionally handles only the endpoints needed by the IG strategy
    runner. Keep broker details here rather than mixing them into the IBKR bot.
    """

    def __init__(
        self,
        credentials: IGCredentials,
        timeout_seconds: float = 10.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.cst: Optional[str] = None
        self.security_token: Optional[str] = None
        self.access_token: Optional[str] = None
        self.token_type: str = "Bearer"
        self.account_id: Optional[str] = None

    def login(self) -> Dict[str, Any]:
        """Authenticate, preferring IG's v3 OAuth flow.

        Some accounts are issued a valid-looking v2 CST / X-SECURITY-TOKEN pair
        that every authenticated endpoint then rejects with
        `error.security.account-token-invalid`, while v3 OAuth works on the same
        credentials. Try v3 first and keep v2 only as a fallback.
        """
        payload = {
            "identifier": self.credentials.username,
            "password": self.credentials.password,
        }
        try:
            data = self._request(
                "POST", "/session", payload=payload, version="3", authenticated=False
            )
            oauth = data.get("oauthToken") or {}
            self.access_token = oauth.get("access_token")
            self.token_type = oauth.get("token_type") or "Bearer"
            self.account_id = data.get("accountId") or self.credentials.account_id
            if self.access_token:
                return data
        except RuntimeError:
            self.access_token = None  # fall through to v2

        data, headers = self._request(
            "POST",
            "/session",
            payload=payload,
            version="2",
            authenticated=False,
            return_headers=True,
        )
        self.cst = headers.get("CST")
        self.security_token = headers.get("X-SECURITY-TOKEN")
        self.account_id = data.get("currentAccountId") or self.credentials.account_id
        if self.credentials.account_id:
            self.switch_account(self.credentials.account_id)
        return data

    @property
    def uses_oauth(self) -> bool:
        return bool(self.access_token)

    def logout(self) -> None:
        if self.access_token or (self.cst and self.security_token):
            try:
                self._request("DELETE", "/session", version="1")
            except RuntimeError:
                pass
        self.cst = None
        self.security_token = None
        self.access_token = None

    def switch_account(self, account_id: str, default_account: bool = False) -> Dict[str, Any]:
        return self._request(
            "PUT",
            "/session",
            payload={"accountId": account_id, "defaultAccount": default_account},
            version="1",
        )

    def get_market_quote(self, epic: str) -> IGQuote:
        data = self._request("GET", f"/markets/{epic}", version="3")
        snapshot = data.get("snapshot") or {}
        status = (
            snapshot.get("marketStatus")
            or (data.get("instrument") or {}).get("marketStatus")
            or "UNKNOWN"
        )
        bid = self._first_number(snapshot, "bid", "BID")
        offer = self._first_number(snapshot, "offer", "ask", "OFFER", "ASK")
        if bid is None or offer is None:
            raise RuntimeError(f"IG market snapshot for {epic} did not include bid/offer")
        return IGQuote(
            epic=epic,
            bid=bid,
            offer=offer,
            status=status,
            timestamp=self._parse_timestamp(snapshot),
        )

    def search_markets(self, search_term: str) -> Dict[str, Any]:
        return self._request(
            "GET",
            "/markets",
            params={"searchTerm": search_term},
            version="1",
        )

    def get_positions(self) -> Dict[str, Any]:
        return self._request("GET", "/positions", version="2")

    def find_position(self, epic: str) -> PositionState:
        data = self.get_positions()
        for item in data.get("positions", []):
            market = item.get("market") or {}
            if market.get("epic") != epic:
                continue
            position = item.get("position") or {}
            direction = position.get("direction")
            size = float(position.get("size") or 0)
            open_level = position.get("openLevel")
            if direction == "BUY":
                mapped_direction = "LONG"
            elif direction == "SELL":
                mapped_direction = "SHORT"
            else:
                mapped_direction = "FLAT"
                size = 0
            return PositionState(
                direction=mapped_direction,
                size=size,
                average_entry=float(open_level) if open_level is not None else None,
                deal_id=position.get("dealId"),
            )
        return PositionState()

    def create_otc_position(
        self,
        *,
        epic: str,
        direction: str,
        size: float,
        currency_code: str,
        expiry: str = "-",
        order_type: str = "MARKET",
        level: Optional[float] = None,
        stop_distance: Optional[float] = None,
        limit_distance: Optional[float] = None,
        force_open: bool = True,
    ) -> Dict[str, Any]:
        payload = self._drop_none(
            {
                "currencyCode": currency_code,
                "direction": direction,
                "epic": epic,
                "expiry": expiry,
                "forceOpen": force_open,
                "guaranteedStop": False,
                "level": level,
                "limitDistance": limit_distance,
                "orderType": order_type,
                "size": size,
                "stopDistance": stop_distance,
                "timeInForce": "FILL_OR_KILL" if order_type == "MARKET" else "GOOD_TILL_CANCELLED",
            }
        )
        return self._request("POST", "/positions/otc", payload=payload, version="2")

    def close_otc_position(
        self,
        *,
        deal_id: str,
        direction: str,
        size: float,
        order_type: str = "MARKET",
        level: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload = self._drop_none(
            {
                "dealId": deal_id,
                "direction": direction,
                "level": level,
                "orderType": order_type,
                "size": size,
                "timeInForce": "FILL_OR_KILL" if order_type == "MARKET" else "GOOD_TILL_CANCELLED",
            }
        )
        return self._request("DELETE", "/positions/otc", payload=payload, version="1")

    def confirm(self, deal_reference: str) -> Dict[str, Any]:
        return self._request("GET", f"/confirms/{deal_reference}", version="1")

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        version: str = "1",
        authenticated: bool = True,
        return_headers: bool = False,
    ):
        url = f"{self.credentials.base_url}{path}"
        headers = {
            "Accept": "application/json; charset=UTF-8",
            "Content-Type": "application/json; charset=UTF-8",
            "VERSION": version,
            "X-IG-API-KEY": self.credentials.api_key,
        }
        if authenticated:
            if self.access_token:
                headers["Authorization"] = f"{self.token_type} {self.access_token}"
                if self.account_id:
                    headers["IG-ACCOUNT-ID"] = str(self.account_id)
            elif self.cst and self.security_token:
                headers["CST"] = self.cst
                headers["X-SECURITY-TOKEN"] = self.security_token
            else:
                raise RuntimeError("IG client is not logged in")

        response = self.session.request(
            method,
            url,
            headers=headers,
            json=payload,
            params=params,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"IG API {method} {path} failed: {response.status_code} {response.text}")
        data = response.json() if response.text else {}
        if return_headers:
            return data, response.headers
        return data

    @staticmethod
    def _drop_none(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}

    @staticmethod
    def _first_number(payload: Dict[str, Any], *keys: str) -> Optional[float]:
        for key in keys:
            value = payload.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _parse_timestamp(snapshot: Dict[str, Any]) -> Optional[datetime]:
        for key in ("updateTimeUTC", "updateTime"):
            value = snapshot.get(key)
            if not value:
                continue
            if isinstance(value, datetime):
                return value
            text = str(value).replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                continue
        return None

