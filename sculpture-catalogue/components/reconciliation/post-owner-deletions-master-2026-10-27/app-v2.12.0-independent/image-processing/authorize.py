#!/usr/bin/env python3
"""Authorize the image-processing app without changing Dropbox files."""

from __future__ import annotations

import argparse
import fcntl
import getpass
import json
import os
from pathlib import Path
import secrets
import sys
from datetime import datetime, timezone

APP_KEY = "ztwztr7wnylkx3q"
EXPECTED_EMAIL = "sally.v.price@gmail.com"
NAMESPACE_ID = "202238505"
ROOT_ID = "id:cnqzTNngPVsAAAAAAArpsA"
ROOT_PATH = "/BOLDSTONE MASTER/Products/01 Wall Sculptures"
SCOPES = (
    "account_info.read",
    "files.metadata.read",
    "files.content.read",
    "files.content.write",
    "sharing.read",
)
SERVICE = "BoldstoneImageProcessing"
CREDENTIAL_ACCOUNT = f"dropbox:{APP_KEY}"
RUNTIME = Path.home() / "Library/Application Support/BoldstoneImageProcessing"


class SetupError(RuntimeError):
    """Only fixed, non-secret messages should be supplied to this exception."""


def private_json(path, payload):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise SetupError("Refusing a symbolic link in the setup destination.")
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def status(state, *, message=None, authorization_url=None, verified=None):
    public = {
        "status": state,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "app_key": APP_KEY,
        "dropbox_file_mutations": 0,
        "conversion_enabled": False,
    }
    if message:
        public["message"] = message
    if authorization_url:
        public["authorization_url"] = authorization_url
    if verified:
        public["verified"] = verified
    private_json(RUNTIME / "authorization-status.json", public)


def keychain_backend():
    if sys.platform != "darwin":
        raise SetupError("Run this setup on your Mac.")
    from keyring.backends.macOS import Keyring

    return Keyring()  # Deliberately excludes plaintext and chained fallbacks.


def check_storage(backend):
    account = "setup-probe-" + secrets.token_hex(12)
    value = secrets.token_urlsafe(32)
    created = False
    try:
        backend.set_password(SERVICE, account, value)
        created = True
        if backend.get_password(SERVICE, account) != value:
            raise SetupError("Keychain verification did not return the stored value.")
    except SetupError:
        raise
    except Exception:
        raise SetupError(
            "macOS Keychain denied access. Unlock your login keychain and approve "
            "any macOS prompt for this setup, then run the command again. "
            "Dropbox authorization has not started."
        ) from None
    finally:
        if created:
            try:
                backend.delete_password(SERVICE, account)
            except Exception:
                raise SetupError("The temporary Keychain test entry could not be removed.") from None


def verify_scopes(granted):
    actual = set(granted.split() if isinstance(granted, str) else granted or ())
    if actual != set(SCOPES):
        raise SetupError(
            "The grant does not contain exactly the five requested permissions. "
            "Check the app Permissions tab and authorize again."
        )


def verify_identity(account, root, granted_account_id):
    from dropbox.files import FolderMetadata

    if account.account_id != granted_account_id:
        raise SetupError("Dropbox grant and account verification disagree.")
    if account.email.casefold() != EXPECTED_EMAIL.casefold() or not account.email_verified:
        raise SetupError("Authorize using Sally Price's verified Dropbox account.")
    if account.root_info.root_namespace_id != NAMESPACE_ID:
        raise SetupError("The authorized Dropbox namespace is not the expected namespace.")
    if not isinstance(root, FolderMetadata) or root.id != ROOT_ID:
        raise SetupError("The working root is not the expected Wall Sculptures folder.")
    if (root.path_display or "").casefold() != ROOT_PATH.casefold():
        raise SetupError("The Wall Sculptures root has moved; review its location first.")
    return {
        "account_id": account.account_id,
        "email": account.email,
        "namespace_id": NAMESPACE_ID,
        "root_id": root.id,
        "root_path": root.path_display,
        "scopes": list(SCOPES),
        "credential_storage": "macOS Keychain",
        "credential_service": SERVICE,
        "credential_account": CREDENTIAL_ACCOUNT,
    }


def verify_grant(grant):
    from dropbox import Dropbox
    from dropbox.common import PathRoot

    if grant.get("app_key") != APP_KEY or not grant.get("refresh_token"):
        raise SetupError("Stored authorization does not belong to this app.")
    verify_scopes(grant.get("scopes"))
    with Dropbox(
        app_key=APP_KEY,
        oauth2_refresh_token=grant["refresh_token"],
        timeout=30,
        max_retries_on_error=0,
        max_retries_on_rate_limit=0,
    ) as client:
        account = client.users_get_current_account()
        rooted = client.with_path_root(PathRoot.namespace_id(NAMESPACE_ID))
        root = rooted.files_get_metadata(ROOT_ID)
        return verify_identity(account, root, grant.get("account_id"))


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-storage", action="store_true")
    args = parser.parse_args()
    if not sys.stdin.isatty() and not args.check_storage:
        raise SetupError("Run this command in your Mac's Terminal to enter the code privately.")
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    if RUNTIME.is_symlink():
        raise SetupError("Refusing a symbolic link for the setup runtime.")
    os.chmod(RUNTIME, 0o700)
    lock_fd = os.open(RUNTIME / "authorization.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        print("Authorization is already running in another Terminal window.")
        return 1
    try:
        return authorize(args)
    finally:
        os.close(lock_fd)


def authorize(args):
    backend = keychain_backend()
    print("Checking secure storage in macOS Keychain...", flush=True)
    check_storage(backend)
    if args.check_storage:
        print("Keychain write, independent readback and probe cleanup passed.")
        return 0
    private_json(RUNTIME / "app-config.json", {
        "app_key": APP_KEY,
        "expected_email": EXPECTED_EMAIL,
        "namespace_id": NAMESPACE_ID,
        "allowed_root_id": ROOT_ID,
        "allowed_root_path": ROOT_PATH,
        "scopes": list(SCOPES),
        "oauth": "authorization_code_pkce_s256_offline_no_redirect",
        "credential_service": SERVICE,
        "credential_account": CREDENTIAL_ACCOUNT,
        "conversion_enabled": False,
        "note": "Root binding for a future worker; this setup performs no file writes.",
    })
    existing = backend.get_password(SERVICE, CREDENTIAL_ACCOUNT)
    if existing:
        verified = verify_grant(json.loads(existing))
        status("LOCAL_OAUTH_VERIFIED", verified=verified)
        print("Existing app authorization and Wall Sculptures access verified.")
        return 0

    from dropbox.oauth import DropboxOAuth2FlowNoRedirect

    flow = DropboxOAuth2FlowNoRedirect(
        APP_KEY, use_pkce=True, token_access_type="offline", scope=list(SCOPES), timeout=30
    )
    authorization_url = flow.start()
    status("AWAITING_DROPBOX_APPROVAL", authorization_url=authorization_url)
    print("\nOpen this link in Chrome, confirm Sally's account, and select Allow:\n")
    print(authorization_url, flush=True)
    print("\nPaste the resulting code into this Terminal window. Input stays hidden.")
    code = getpass.getpass("Dropbox authorization code: ").strip()
    if not code:
        raise SetupError("No authorization code was entered; nothing was saved.")
    try:
        result = flow.finish(code)
    except Exception:
        raise SetupError(
            "Dropbox could not exchange the authorization code. Confirm the app's "
            "five permissions and Allow public clients setting, then run setup again."
        ) from None
    finally:
        code = None
    if not result.refresh_token:
        raise SetupError("Dropbox did not return an offline refresh token.")
    verify_scopes(result.scope)
    grant = {
        "app_key": APP_KEY,
        "refresh_token": result.refresh_token,
        "account_id": result.account_id,
        "scopes": list(SCOPES),
    }
    verify_grant(grant)
    payload = json.dumps(grant, sort_keys=True)
    backend.set_password(SERVICE, CREDENTIAL_ACCOUNT, payload)
    stored = backend.get_password(SERVICE, CREDENTIAL_ACCOUNT)
    if stored != payload:
        raise SetupError("The saved authorization could not be read back from Keychain.")
    verified = verify_grant(json.loads(stored))
    status("LOCAL_OAUTH_VERIFIED", verified=verified)
    print("\nAuthorization saved to macOS Keychain and independently verified.")
    print("Verified folder: " + ROOT_PATH)
    print("No Dropbox files were changed. Conversion is not enabled.")
    return 0


if __name__ == "__main__":
    os.umask(0o077)
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        status("AUTHORIZATION_INTERRUPTED", message="Setup interrupted; check Keychain before retrying.")
        print("\nSetup interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except SetupError as exc:
        status("SETUP_BLOCKED", message=str(exc))
        print("\n" + str(exc), file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:
        message = "Setup failed (" + type(exc).__name__ + "). No credential values were logged."
        status("SETUP_FAILED", message=message)
        print("\n" + message, file=sys.stderr)
        raise SystemExit(3)
