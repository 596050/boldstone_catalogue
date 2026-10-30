from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from boldstone.authentication import (
    EXECUTOR_CREDENTIAL_REFERENCE,
    authorize,
    native_adapter,
    validate_grant,
)
from boldstone.cli import main
from boldstone.config import EXECUTOR_SCOPES, READ_SCOPES
from boldstone.errors import Blocked
from boldstone.root import binding_hash
from boldstone.util import canonical


class Keychain:
    def __init__(self):
        self.records = {}
        self.writes = []

    def get(self, reference):
        return deepcopy(self.records.get(reference))

    def put(self, reference, value):
        self.records[reference] = deepcopy(value)
        self.writes.append(reference)


def oauth_stub(monkeypatch, **overrides):
    settings = {}
    result = SimpleNamespace(
        scope=" ".join(EXECUTOR_SCOPES),
        refresh_token="private-executor-refresh",
        account_id="test-account",
    )
    for key, value in overrides.items():
        setattr(result, key, value)

    class Flow:
        def __init__(self, key, **kwargs):
            settings.update(app_key=key, **kwargs)

        def start(self):
            return "https://www.dropbox.com/oauth2/authorize?test=synthetic"

        def finish(self, code):
            assert code == "private-local-code"
            return result

    monkeypatch.setattr("dropbox.oauth.DropboxOAuth2FlowNoRedirect", Flow)
    return settings


def authorize_executor(config, store):
    return authorize(
        config,
        profile="executor",
        store=store,
        input_code=lambda _: "private-local-code",
        open_browser=False,
    )


def test_executor_grant_is_separate_and_audit_adapter_stays_read_only(scoped, monkeypatch, capsys):
    state, _, _, fake = scoped
    settings = oauth_stub(monkeypatch)
    store = Keychain()
    audit_reference = state.config.dropbox["credential_store_reference"]
    audit_grant = {
        "app_key": "public-test-key",
        "account_id": "test-account",
        "refresh_token": "private-audit-refresh",
        "granted_scopes": list(READ_SCOPES),
    }
    store.records[audit_reference] = deepcopy(audit_grant)
    original_config = state.config.path.read_bytes()

    result = authorize_executor(state.config, store)

    assert settings["scope"] == list(EXECUTOR_SCOPES)
    assert settings["use_pkce"] is True and settings["token_access_type"] == "offline"
    assert settings["timeout"] == 30
    assert "include_granted_scopes" not in settings
    assert "consumer_secret" not in settings
    assert store.writes == [EXECUTOR_CREDENTIAL_REFERENCE]
    assert store.records[audit_reference] == audit_grant
    record = store.records[EXECUTOR_CREDENTIAL_REFERENCE]
    assert record["profile"] == "executor"
    assert record["refresh_token"] == "private-executor-refresh"
    assert record["root_binding_sha256"] == binding_hash(state.config)
    validate_grant(record, state.config, profile="executor")
    assert result["objective_outcome"] == "EXECUTOR_AUTHORIZED_EXECUTION_UNAVAILABLE"
    assert result["granted_scopes"] == list(EXECUTOR_SCOPES)
    assert result["content_writes"] is False and result["remote_mutations"] == 0
    assert state.config.path.read_bytes() == original_config
    output = capsys.readouterr()
    for secret in ("private-executor-refresh", "private-audit-refresh", "private-local-code"):
        assert secret not in output.out + output.err + canonical(result)

    client_kwargs = {}

    def client(**kwargs):
        client_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr("dropbox.Dropbox", client)
    native_adapter(state.config, store=store)
    assert client_kwargs["oauth2_refresh_token"] == "private-audit-refresh"
    assert client_kwargs["scope"] == list(READ_SCOPES)
    assert fake.backend["writes"] == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"account_id": "wrong-account"}, "different account"),
        ({"scope": " ".join(READ_SCOPES)}, "five execution scopes"),
        ({"scope": " ".join((*EXECUTOR_SCOPES, "sharing.write"))}, "five execution scopes"),
        ({"refresh_token": None}, "refresh token"),
    ],
)
def test_executor_rejects_wrong_account_or_scope_without_saving(
    scoped, monkeypatch, overrides, message
):
    state, _, _, _ = scoped
    oauth_stub(monkeypatch, **overrides)
    store = Keychain()
    original_config = state.config.path.read_bytes()
    with pytest.raises(Blocked, match=message):
        authorize_executor(state.config, store)
    assert store.writes == []
    assert state.config.path.read_bytes() == original_config


def test_executor_requires_saved_root_confirmation_before_oauth(local_state, monkeypatch):
    settings = oauth_stub(monkeypatch)
    store = Keychain()
    with pytest.raises(Blocked, match="matching audit root confirmation"):
        authorize_executor(local_state.config, store)
    assert settings == {} and store.writes == []


def test_executor_rejects_changed_root_before_oauth(scoped, monkeypatch):
    state, _, _, _ = scoped
    settings = oauth_stub(monkeypatch)
    store = Keychain()
    config = state.config.with_dropbox(verified_root_folder_id="id:OTHER")
    with pytest.raises(Blocked, match="matching audit root confirmation"):
        authorize_executor(config, store)
    assert settings == {} and store.writes == []


def test_executor_rejects_changed_app_key_before_oauth(scoped, monkeypatch):
    state, _, _, _ = scoped
    settings = oauth_stub(monkeypatch)
    store = Keychain()
    with pytest.raises(Blocked, match="app key from the confirmed audit setup"):
        authorize(
            state.config,
            profile="executor",
            app_key="different-public-key",
            store=store,
            open_browser=False,
        )
    assert settings == {} and store.writes == []


def test_executor_cannot_overwrite_audit_keychain_entry(scoped, monkeypatch):
    state, _, _, _ = scoped
    settings = oauth_stub(monkeypatch)
    store = Keychain()
    config = state.config.with_dropbox(credential_store_reference=EXECUTOR_CREDENTIAL_REFERENCE)
    with pytest.raises(Blocked, match="separate Keychain entries"):
        authorize_executor(config, store)
    assert settings == {} and store.writes == []


def test_executor_grant_is_bound_to_the_confirmed_root(scoped):
    state, _, _, _ = scoped
    record = {
        "app_key": "public-test-key",
        "account_id": "test-account",
        "refresh_token": "private-executor-refresh",
        "granted_scopes": list(EXECUTOR_SCOPES),
        "profile": "executor",
        "root_binding_sha256": "different-root-binding",
    }
    with pytest.raises(Blocked, match="different confirmed root"):
        validate_grant(record, state.config, profile="executor")


def test_real_executor_oauth_url_requests_exact_scopes_and_pkce(scoped, capsys):
    state, _, _, _ = scoped
    store = Keychain()

    def cancel(_):
        raise EOFError

    with pytest.raises(EOFError):
        authorize(
            state.config,
            profile="executor",
            store=store,
            input_code=cancel,
            open_browser=False,
        )
    output = capsys.readouterr().err
    url = next(line for line in output.splitlines() if line.startswith("https://www.dropbox.com/"))
    query = parse_qs(urlparse(url).query)
    assert query["scope"] == [" ".join(EXECUTOR_SCOPES)]
    assert query["token_access_type"] == ["offline"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] and "code_verifier" not in query
    assert store.writes == []


def test_cli_routes_executor_profile_to_authorization(local_state, monkeypatch, capsys):
    arguments = {}

    def authorization(config, **kwargs):
        arguments.update(kwargs)
        return {"profile": kwargs["profile"]}

    monkeypatch.setattr("boldstone.cli.authorize", authorization)
    assert (
        main(
            [
                "--config",
                str(local_state.config.path),
                "auth",
                "--profile",
                "executor",
                "--pkce",
                "--offline",
                "--no-browser",
            ]
        )
        == 0
    )
    assert arguments["profile"] == "executor" and arguments["open_browser"] is False
    assert '"profile": "executor"' in capsys.readouterr().out
