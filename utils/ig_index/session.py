"""IG REST session for this package, using the v3 OAuth flow.

`ig.client.IGRestClient` authenticates with the v2 CST / X-SECURITY-TOKEN pair.
That pair is issued for this account but every authenticated endpoint rejects it
with `error.security.account-token-invalid`, while the v3 OAuth flow works on the
same credentials. This module therefore does its own auth rather than depending
on a path that is broken for the account we actually have.

Scope is deliberately small: authenticate, read markets and dealing rules, read
positions, deal, confirm. Nothing else belongs here.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests


DEMO_BASE_URL = "https://demo-api.ig.com/gateway/deal"
LIVE_BASE_URL = "https://api.ig.com/gateway/deal"

# Measured against this demo key: the allowance refills in bursts of roughly
# 4-5 requests per minute, well under IG's documented 60/min. Anything faster
# earns error.public-api.exceeded-api-key-allowance.
MIN_SECONDS_BETWEEN_REQUESTS = float(os.environ.get("IG_MIN_REQUEST_INTERVAL", "14.0"))


@dataclass(frozen=True)
class Credentials:
    identifier: str
    password: str
    api_key: str
    account_id: str | None = None
    environment: str = "demo"

    @classmethod
    def from_env(cls) -> "Credentials":
        """Accept IG's own IG_IDENTIFIER as well as the IG_USERNAME alias."""
        identifier = os.environ.get("IG_IDENTIFIER") or os.environ.get("IG_USERNAME")
        password = os.environ.get("IG_PASSWORD")
        api_key = os.environ.get("IG_API_KEY")
        missing = [
            name
            for name, value in (
                ("IG_IDENTIFIER (or IG_USERNAME)", identifier),
                ("IG_PASSWORD", password),
                ("IG_API_KEY", api_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"missing IG environment variables: {', '.join(missing)}")
        return cls(
            identifier=str(identifier),
            password=str(password),
            api_key=str(api_key),
            account_id=os.environ.get("IG_ACCOUNT_ID") or None,
            environment=os.environ.get("IG_ENVIRONMENT", "demo"),
        )

    @property
    def base_url(self) -> str:
        env = self.environment.lower()
        if env == "live":
            return LIVE_BASE_URL
        if env == "demo":
            return DEMO_BASE_URL
        raise ValueError("IG_ENVIRONMENT must be 'demo' or 'live'")


class IGSession:
    """Authenticated IG REST session with client-side rate limiting."""

    def __init__(self, credentials: Credentials, *, timeout: float = 20.0) -> None:
        self.credentials = credentials
        self.timeout = timeout
        self.session = requests.Session()
        self.access_token: str | None = None
        self.token_type: str = "Bearer"
        self.account_id: str | None = None
        self.account_type: str | None = None
        self.currency: str | None = None
        self._last_request_at = 0.0

    # ------------------------------------------------------------------ auth
    def login(self) -> dict[str, Any]:
        headers = {
            "Accept": "application/json; charset=UTF-8",
            "Content-Type": "application/json; charset=UTF-8",
            "X-IG-API-KEY": self.credentials.api_key,
            "VERSION": "3",
        }
        response = self.session.post(
            f"{self.credentials.base_url}/session",
            headers=headers,
            json={
                "identifier": self.credentials.identifier,
                "password": self.credentials.password,
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"IG login failed: {response.status_code} {response.text[:200]}")
        body = response.json()
        oauth = body.get("oauthToken") or {}
        self.access_token = oauth.get("access_token")
        self.token_type = oauth.get("token_type") or "Bearer"
        # OAuth authenticates the identity, while IG-ACCOUNT-ID selects the
        # dealing account for subsequent requests. Honour the explicit
        # operator-configured account even if the login response names a
        # different preferred/default account.
        self.account_id = self.credentials.account_id or body.get("accountId")
        if not self.access_token:
            raise RuntimeError("IG login returned no OAuth access token")
        return body

    def _headers(self, version: str) -> dict[str, str]:
        if not self.access_token:
            raise RuntimeError("IG session is not logged in")
        return {
            "Accept": "application/json; charset=UTF-8",
            "Content-Type": "application/json; charset=UTF-8",
            "X-IG-API-KEY": self.credentials.api_key,
            "Authorization": f"{self.token_type} {self.access_token}",
            "IG-ACCOUNT-ID": str(self.account_id),
            "VERSION": version,
        }

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)
        self._last_request_at = time.monotonic()

    def request(
        self,
        method: str,
        path: str,
        *,
        version: str = "1",
        params: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        before_send: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        self._throttle()
        # A timed model decision may expire while waiting for the API allowance.
        # Validate after throttling and before any network mutation.
        if before_send is not None:
            before_send()
        headers = self._headers(version)
        if extra_headers:
            headers.update(extra_headers)
        response = self.session.request(
            method,
            f"{self.credentials.base_url}{path}",
            headers=headers,
            params=dict(params) if params else None,
            json=dict(payload) if payload else None,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"IG {method} {path} failed: {response.status_code} {response.text[:200]}"
            )
        return response.json() if response.text else {}

    # --------------------------------------------------------------- reading
    def search_markets(self, term: str) -> list[dict[str, Any]]:
        return list(self.request("GET", "/markets", params={"searchTerm": term}).get("markets", []))

    def market_details(self, epic: str) -> dict[str, Any]:
        return self.request("GET", f"/markets/{epic}", version="3")

    def positions(self) -> list[dict[str, Any]]:
        return list(self.request("GET", "/positions", version="2").get("positions", []))

    # --------------------------------------------------------------- dealing
    def create_position(
        self,
        *,
        epic: str,
        direction: str,
        size: float,
        currency_code: str,
        expiry: str = "DFB",
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/positions/otc",
            version="2",
            payload={
                "epic": epic,
                "expiry": expiry,
                "direction": direction,
                "size": size,
                "orderType": "MARKET",
                "currencyCode": currency_code,
                # forceOpen=False lets IG NET against an existing position on
                # the same epic. With forceOpen=True every deal opens a separate
                # position, so a daily rebalancing book silently stacks exposure.
                "forceOpen": False,
                "guaranteedStop": False,
                "timeInForce": "FILL_OR_KILL",
            },
        )

    def close_position(self, *, deal_id: str, direction: str, size: float) -> dict[str, Any]:
        # IG's gateway discards the body of a real HTTP DELETE, so the request
        # arrives with a null payload ("validation.null-not-allowed.request").
        # Its documented convention is POST carrying `_method: DELETE`. Measured
        # against the demo endpoint with a non-existent dealId, 2026-09-03:
        #   DELETE            -> 400 validation.null-not-allowed.request
        #   POST + _method    -> 404 error.service.marketdata.position...  (body parsed)
        return self.request(
            "POST",
            "/positions/otc",
            version="1",
            extra_headers={"_method": "DELETE"},
            payload={
                "dealId": deal_id,
                "direction": direction,
                "size": size,
                "orderType": "MARKET",
                "timeInForce": "FILL_OR_KILL",
            },
        )

    def confirm(self, deal_reference: str) -> dict[str, Any]:
        return self.request("GET", f"/confirms/{deal_reference}", version="1")


def connect(*, demo: bool = True) -> IGSession:
    credentials = Credentials.from_env()
    if demo and credentials.environment.lower() != "demo":
        credentials = Credentials(
            identifier=credentials.identifier,
            password=credentials.password,
            api_key=credentials.api_key,
            account_id=credentials.account_id,
            environment="demo",
        )
    session = IGSession(credentials)
    body = session.login()
    session.account_type = body.get("accountType")
    session.currency = body.get("currencyIsoCode") or body.get("currency")
    return session


__all__ = ["Credentials", "IGSession", "connect"]
