"""Dedicated local OAuth; never reads Chrome cookies or global gcloud credentials."""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import secrets
import stat
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .core import ToolkitError, private_json

PREFIX = "https://www.googleapis.com/auth/"
SCOPES = {
    "report": ["openid", "email", PREFIX + "analytics.readonly", PREFIX + "webmasters.readonly"],
    "setup": [
        "openid",
        "email",
        PREFIX + "analytics.readonly",
        PREFIX + "analytics.edit",
        PREFIX + "webmasters",
        PREFIX + "siteverification.verify_only",
    ],
}


class Vault:
    def __init__(self, profile, backend="keychain"):
        self.profile, self.backend = profile, backend

    def _keyring(self):
        try:
            import keyring

            if keyring.get_keyring().priority <= 0:
                raise RuntimeError("No secure OS credential backend.")
            return keyring
        except Exception:
            raise ToolkitError(
                "OS credential store unavailable. Install the keychain extra. "
                "Use --credential-store file explicitly for private 0600 files; no silent fallback."
            ) from None

    def _path(self, name):
        return self.profile.state_dir / self.profile.id / "credentials" / (name + ".json")

    def get(self, name, required=True):
        try:
            if self.backend == "file":
                p = self._path(name)
                if p.exists() and (
                    p.is_symlink() or p.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)
                ):
                    raise ToolkitError(
                        "Credential file must not be a symlink or accessible by other users."
                    )
                raw = p.read_text() if p.exists() else None
            else:
                raw = self._keyring().get_password(
                    "SearchAnalyticsToolkit", self.profile.id + ":" + name
                )
        except ToolkitError:
            raise
        except Exception:
            raise ToolkitError(
                "OS credential store read failed; credentials were not exposed."
            ) from None
        if raw is None:
            if required:
                raise ToolkitError(f"Missing {name} credential for profile {self.profile.id}.")
            return None
        return json.loads(raw)

    def set(self, name, value):
        if self.backend == "file":
            private_json(self._path(name), value)
            if self.get(name) != value:
                raise ToolkitError("Credential file readback mismatch.")
        else:
            try:
                kr = self._keyring()
                encoded = json.dumps(value)
                kr.set_password("SearchAnalyticsToolkit", self.profile.id + ":" + name, encoded)
                if (
                    kr.get_password("SearchAnalyticsToolkit", self.profile.id + ":" + name)
                    != encoded
                ):
                    raise RuntimeError("Readback mismatch.")
            except Exception:
                raise ToolkitError(
                    "OS credential store save/readback failed. No file fallback was used."
                ) from None

    def prompt_secret(self, name):
        value = getpass.getpass("Enter " + name + " (hidden): ").strip()
        if not value:
            raise ToolkitError("No secret supplied.")
        self.set(name, {"value": value})


def authorize_google(profile, vault, http, client_file, mode, *, open_browser=True, timeout=240):
    try:
        client = json.loads(Path(client_file).expanduser().read_text())["installed"]
        client_id = client["client_id"]
    except (OSError, ValueError, KeyError):
        raise ToolkitError(
            "Supply the downloaded Google Desktop OAuth client JSON (installed type)."
        ) from None
    if not client_id.endswith(".apps.googleusercontent.com"):
        raise ToolkitError("This is not a Google Desktop OAuth client ID.")
    scopes = SCOPES[mode]
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    state = secrets.token_urlsafe(32)
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Authorization codes must never enter access logs.

        def do_GET(self):
            p = urllib.parse.urlsplit(self.path)
            values = urllib.parse.parse_qs(p.query)
            if p.path != "/" or not secrets.compare_digest(values.get("state", [""])[0], state):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid OAuth callback.")
                return
            if "code" in values:
                result["code"] = values["code"][0]
            else:
                result["error"] = values.get("error", ["Authorization denied"])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization received. Return to the terminal.")

    # Avoid the HTTP client's variable shadowing the stdlib server namespace.
    server = http_server(Callback)
    redirect = f"http://127.0.0.1:{server.server_port}/"
    query = {
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    expected = profile.data.get("google", {}).get("expected_email")
    if expected:
        query["login_hint"] = expected
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(query)
    print("Requested Google scopes: " + ", ".join(scopes))
    print(
        "Complete Google's consent screen yourself. Callback expires in "
        + str(timeout)
        + " seconds."
    )
    print(url)
    if open_browser:
        webbrowser.open(url)
    deadline = time.monotonic() + timeout
    server.timeout = 1
    try:
        while not result and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not result.get("code"):
        raise ToolkitError("Google authorization was denied or timed out; no credential saved.")
    form = {
        "client_id": client_id,
        "code": result["code"],
        "code_verifier": verifier,
        "grant_type": "authorization_code",
        "redirect_uri": redirect,
    }
    if client.get("client_secret"):
        form["client_secret"] = client["client_secret"]
    token = http.call("POST", "https://oauth2.googleapis.com/token", form=form)["data"]
    http.secrets.extend(
        [token.get("access_token"), token.get("refresh_token"), client.get("client_secret")]
    )
    user = http.call(
        "GET",
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": "Bearer " + token["access_token"]},
    )["data"]
    if not user.get("email_verified") or (
        expected and user.get("email", "").lower() != expected.lower()
    ):
        raise ToolkitError(
            "Google identity does not match the profile's verified expected account; no credential saved."
        )
    granted = token.get("scope", " ".join(scopes)).split()
    # OAuth may return canonical userinfo.email instead of the alias 'email'.
    required = {s for s in scopes if s.startswith(PREFIX)}
    if not required.issubset(set(granted)):
        raise ToolkitError("Required API scopes were not granted; no setup credential saved.")
    token.update(
        client_id=client_id,
        client_secret=client.get("client_secret", ""),
        scopes=granted,
        email=user["email"],
        expires_at=time.time() + token.get("expires_in", 3600),
    )
    if not token.get("refresh_token"):
        raise ToolkitError(
            "No offline refresh token returned; repeat consent or review existing Google grants."
        )
    vault.set("google", token)
    return {"email": token["email"], "scopes": granted, "stored_in": vault.backend}


def http_server(handler):
    return HTTPServer(("127.0.0.1", 0), handler)


class GoogleToken:
    def __init__(self, vault, http):
        self.vault, self.http = vault, http

    def headers(self, scope):
        cred = self.vault.get("google")
        scopes = set(cred.get("scopes", []))
        if not any(s in scopes for s in scope.split("|")):
            raise ToolkitError(
                "Google credential lacks " + scope + "; run auth google --mode setup."
            )
        expected = self.vault.profile.data.get("google", {}).get("expected_email")
        if expected and cred.get("email", "").lower() != expected.lower():
            raise ToolkitError("Stored Google identity differs from this profile.")
        self.http.secrets.extend(
            [cred.get(k) for k in ["access_token", "refresh_token", "client_secret"]]
        )
        if cred.get("expires_at", 0) <= time.time() + 60:
            form = {
                "client_id": cred["client_id"],
                "client_secret": cred.get("client_secret", ""),
                "refresh_token": cred["refresh_token"],
                "grant_type": "refresh_token",
            }
            refreshed = self.http.call("POST", "https://oauth2.googleapis.com/token", form=form)[
                "data"
            ]
            cred.update(refreshed, expires_at=time.time() + refreshed.get("expires_in", 3600))
            self.vault.set("google", cred)
            self.http.secrets.append(cred["access_token"])
        return {"Authorization": "Bearer " + cred["access_token"]}
