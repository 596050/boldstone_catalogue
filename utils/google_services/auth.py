import json
import logging
import sys
import threading
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# Gmail + Calendar scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
]

_CRED_DIR = Path(__file__).resolve().parent.parent / "external_storage" / "credentials"
_DEFAULT_CLIENT_SECRET = _CRED_DIR / "client_secret.json"
_DEFAULT_TOKEN = _CRED_DIR / "google_gmail_calendar_token.json"

# Background refresh: check every 5 min, refresh if expiring within 10 min
_REFRESH_CHECK_INTERVAL = 300  # seconds
_REFRESH_THRESHOLD = 600  # seconds


class GoogleAuth:
    """OAuth2 authentication for Gmail and Google Calendar.

    Follows the same load-token / refresh / OAuth-flow / save-token pattern
    used by the existing Google Drive backend in object_storage.py, but with
    a separate token file to avoid scope conflicts.

    A daemon timer thread checks every 5 minutes and proactively refreshes
    the access token if it will expire within 10 minutes.
    """

    def __init__(
        self,
        client_secret_path: str | Path | None = None,
        token_path: str | Path | None = None,
        scopes: list[str] | None = None,
    ):
        self._client_secret_path = Path(client_secret_path or _DEFAULT_CLIENT_SECRET)
        self._token_path = Path(token_path or _DEFAULT_TOKEN)
        self._scopes = scopes or list(SCOPES)

        self._lock = threading.Lock()
        self._creds: Credentials | None = None

        self._authenticate()
        self._start_background_refresh()

    # -- public API ----------------------------------------------------------

    @property
    def credentials(self) -> Credentials:
        with self._lock:
            return self._creds

    def build_service(self, name: str, version: str):
        """Build a Google API service client (e.g. ``build('gmail', 'v1')``)."""
        return build(name, version, credentials=self.credentials)

    # -- auth flow -----------------------------------------------------------

    def _authenticate(self) -> None:
        creds = None

        if self._token_path.exists():
            creds = Credentials.from_authorized_user_file(
                str(self._token_path), self._scopes
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing Gmail/Calendar access token ...")
                try:
                    creds.refresh(Request())
                except Exception as exc:
                    logger.error("Token refresh failed (%s). Re-authenticating.", exc)
                    creds = None

            if not creds:
                if not self._client_secret_path.exists():
                    raise FileNotFoundError(
                        f"Client secret not found at {self._client_secret_path}"
                    )
                if not sys.stdin.isatty():
                    logger.warning(
                        "Non-interactive session but OAuth browser flow is required."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self._client_secret_path), self._scopes
                )
                creds = flow.run_local_server(port=0)

            self._token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._token_path, "w") as fh:
                fh.write(creds.to_json())

        with self._lock:
            self._creds = creds

    # -- background refresh --------------------------------------------------

    def _start_background_refresh(self) -> None:
        timer = threading.Timer(_REFRESH_CHECK_INTERVAL, self._background_refresh)
        timer.daemon = True
        timer.start()

    def _background_refresh(self) -> None:
        try:
            with self._lock:
                creds = self._creds

            if creds and creds.refresh_token:
                remaining = 0.0
                if creds.expiry:
                    from datetime import datetime, timezone

                    remaining = (
                        creds.expiry.replace(tzinfo=timezone.utc)
                        - datetime.now(timezone.utc)
                    ).total_seconds()

                if remaining < _REFRESH_THRESHOLD:
                    logger.info(
                        "Background refresh: token expires in %.0f s, refreshing.",
                        remaining,
                    )
                    creds.refresh(Request())
                    with self._lock:
                        self._creds = creds
                    self._token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self._token_path, "w") as fh:
                        fh.write(creds.to_json())
        except Exception:
            logger.exception("Background token refresh failed")
        finally:
            self._start_background_refresh()
