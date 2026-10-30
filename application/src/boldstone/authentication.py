from __future__ import annotations

import getpass
import json
import sqlite3
import sys
import webbrowser
from contextlib import closing

from .config import EXECUTOR_SCOPES, READ_SCOPES
from .dropbox_adapter import NativeDropbox
from .errors import Blocked, RemoteError
from .root import binding_hash

EXECUTOR_CREDENTIAL_REFERENCE = "boldstone/dropbox/executor"


def authorization_scopes(profile):
    if profile == "audit":
        return READ_SCOPES
    if profile == "executor":
        return EXECUTOR_SCOPES
    raise Blocked("Unknown authorization profile; choose audit or executor")


def executor_binding(config):
    dbx = config.dropbox
    if (
        not all(
            dbx.get(key)
            for key in ("expected_account_id", "verified_namespace_id", "verified_root_folder_id")
        )
        or len(set(dbx.get("known_file_ids", []))) < 2
    ):
        raise Blocked("Confirm the account and root with the audit profile before executor auth")
    binding = binding_hash(config)
    try:
        with closing(sqlite3.connect(config.database.as_uri() + "?mode=ro", uri=True)) as conn:
            receipt = conn.execute(
                "SELECT 1 FROM root_bindings WHERE binding_sha256=?", (binding,)
            ).fetchone()
    except sqlite3.Error:
        raise Blocked("Audit root confirmation is unavailable; confirm the root first") from None
    if not receipt:
        raise Blocked("Configured scope has no matching audit root confirmation")
    return binding


def authorization_reference(config, profile):
    authorization_scopes(profile)
    audit_reference = config.dropbox["credential_store_reference"]
    if profile == "audit":
        return audit_reference
    if audit_reference == EXECUTOR_CREDENTIAL_REFERENCE:
        raise Blocked("Audit and executor authorizations must use separate Keychain entries")
    return EXECUTOR_CREDENTIAL_REFERENCE


class OSCredentialStore:
    def __init__(self):
        # Fail closed rather than allowing keyring's optional plaintext/chained fallbacks.
        if sys.platform != "darwin":
            raise Blocked(
                "This release supports macOS Keychain; other secure backends need testing"
            )
        from keyring.backends.macOS import Keyring

        self.backend = Keyring()

    def get(self, reference):
        try:
            value = self.backend.get_password("BoldstoneLocal", reference)
        except Exception as exc:
            raise Blocked("macOS Keychain is unavailable or access was denied") from exc
        return json.loads(value) if value else None

    def put(self, reference, value):
        try:
            self.backend.set_password("BoldstoneLocal", reference, json.dumps(value))
        except Exception as exc:
            raise Blocked("Could not save authorization in macOS Keychain") from exc


def validate_grant(record, config, *, profile="audit"):
    required = authorization_scopes(profile)
    scopes = set(record.get("granted_scopes", []))
    if scopes != set(required):
        raise Blocked(
            "Audit authorization must have exactly the four read scopes; reauthorize"
            if profile == "audit"
            else "Executor authorization must have exactly the five execution scopes; reauthorize",
            details={"required_scopes": list(required), "granted_scopes": sorted(scopes)},
        )
    if record.get("profile", "audit") != profile:
        raise Blocked("Keychain authorization belongs to a different profile")
    if record.get("app_key") != config.dropbox.get("app_key"):
        raise Blocked("Keychain authorization belongs to a different app key")
    expected = config.dropbox.get("expected_account_id")
    if expected and expected != record.get("account_id"):
        raise Blocked("Keychain authorization belongs to a different account")
    if not record.get("refresh_token"):
        raise Blocked("Offline authorization is missing its refresh token")
    if profile == "executor" and record.get("root_binding_sha256") != executor_binding(config):
        raise Blocked("Executor authorization belongs to a different confirmed root")


def authorize(
    config, *, app_key=None, store=None, input_code=None, open_browser=True, profile="audit"
):
    from dropbox.oauth import DropboxOAuth2FlowNoRedirect

    scopes = authorization_scopes(profile)
    reference = authorization_reference(config, profile)
    app_key = app_key or config.dropbox.get("app_key")
    if not app_key or app_key.startswith("REPLACE_"):
        raise Blocked("Dropbox public app key is required; use auth --app-key YOUR_APP_KEY")
    binding = None
    if profile == "executor":
        if app_key != config.dropbox.get("app_key"):
            raise Blocked("Executor auth must use the app key from the confirmed audit setup")
        binding = executor_binding(config)
    store = store or OSCredentialStore()
    flow = DropboxOAuth2FlowNoRedirect(
        app_key, token_access_type="offline", scope=list(scopes), use_pkce=True, timeout=30
    )
    authorization_url = flow.start()
    print(
        "Authorize read-only access in your browser, then paste the code into this terminal."
        if profile == "audit"
        else "Authorize Dropbox file read/write access in your browser, then paste the code "
        "into this terminal. This command saves authorization only; it does not change files.",
        file=sys.stderr,
    )
    if profile == "executor":
        print(
            "Dropbox grants this permission across your account. "
            f"Your confirmed working root is {config.dropbox['verified_root_folder_id']}.",
            file=sys.stderr,
        )
    print(authorization_url, file=sys.stderr)
    if open_browser:
        webbrowser.open(authorization_url)
    code = (input_code or getpass.getpass)("Dropbox authorization code (hidden): ").strip()
    try:
        result = flow.finish(code)
    except Exception:
        raise RemoteError(
            "oauth_failed", "Dropbox authorization failed; no token was saved"
        ) from None
    scope = result.scope.split() if isinstance(result.scope, str) else list(result.scope or [])
    record = {
        "app_key": app_key,
        "refresh_token": result.refresh_token,
        "account_id": result.account_id,
        "granted_scopes": scope,
        "profile": profile,
    }
    if binding:
        record["root_binding_sha256"] = binding
    updated = config.with_dropbox(app_key=app_key)
    validate_grant(record, updated, profile=profile)
    store.put(reference, record)
    if profile == "audit":
        updated.save()
    return {
        "objective_outcome": "AUDIT_AUTHORIZED_ROOT_UNCONFIRMED"
        if profile == "audit"
        else "EXECUTOR_AUTHORIZED_EXECUTION_UNAVAILABLE",
        "profile": profile,
        "account_id": result.account_id,
        "granted_scopes": scope,
        "credential_storage": "macOS Keychain",
        "credential_reference": reference,
        **({"root_binding_sha256": binding} if binding else {}),
        "content_writes": False,
        "remote_mutations": 0,
    }


def native_adapter(config, *, store=None):
    import dropbox

    if not config.dropbox.get("app_key"):
        raise Blocked("Dropbox app key is not configured; finish local OAuth first")
    store = store or OSCredentialStore()
    record = store.get(config.dropbox["credential_store_reference"])
    if not record:
        raise Blocked("No audit authorization exists in macOS Keychain")
    validate_grant(record, config)
    client = dropbox.Dropbox(
        oauth2_refresh_token=record["refresh_token"],
        app_key=record["app_key"],
        timeout=30,
        max_retries_on_error=0,
        max_retries_on_rate_limit=0,
        scope=list(READ_SCOPES),
    )
    return NativeDropbox(client, policy=config.data["read_policy"])
