from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from types import SimpleNamespace

import pytest
import requests
from conftest import add_batch
from dropbox.auth import AuthError as SDKAuthError
from dropbox.auth import TokenScopeError
from dropbox.exceptions import AuthError, RateLimitError

from boldstone.authentication import authorize, native_adapter
from boldstone.binary_cache import check_binary
from boldstone.census import census
from boldstone.cli import parser
from boldstone.config import READ_SCOPES
from boldstone.dropbox_adapter import NativeDropbox, translate_exception
from boldstone.errors import Blocked, RemoteError
from boldstone.reviews import run_batch
from boldstone.source_comparison import compare_verified_local_source
from boldstone.util import canonical, utc_now


def test_binary_post_read_catches_concurrent_source_change(scoped, monkeypatch):
    state, run, scope, fake = scoped
    original = scope.adapter.download

    def download(*args, **kwargs):
        result = original(*args, **kwargs)
        fake.backend["metadata"]["id:A"]["rev"] = "987654321"
        return result

    monkeypatch.setattr(scope.adapter, "download", download)
    result = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    assert result["checks"]["transfer"] == result["checks"]["hash"] == "pass"
    assert result["checks"]["post_read"] == "fail"
    assert result["cache_path"] is None
    assert result["exit_code"] == 7


def test_verified_source_dimensions_do_not_invent_visual_equivalence(scoped):
    state, run, scope, fake = scoped
    source = check_binary(state, run, scope, "id:BMP", expected_format="BMP")
    jpg = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    assert source["exit_code"] == jpg["exit_code"] == 0
    comparison = compare_verified_local_source(state, scope, "id:BMP", jpg)
    assert comparison["source_status"] == "VERIFIED_LOCAL_SOURCE_LOCATED"
    assert comparison["dimensions_match"] is True
    assert comparison["source_equivalence_accepted"] is False


def test_missing_cache_does_not_claim_no_historical_source(scoped):
    state, run, scope, fake = scoped
    jpg = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    comparison = compare_verified_local_source(state, scope, "id:MISSING", jpg)
    assert comparison["source_status"] == "NOT_LOCATED_IN_VERIFIED_LOCAL_DOWNLOAD_RECORDS"
    assert comparison["source_bytes_unavailable_everywhere"] is None


def test_inventory_rebuilds_current_immediate_parent_ids(scoped):
    state, run, scope, fake = scoped
    census(state, run, scope)
    assert (
        state.conn.execute(
            "SELECT parent_folder_id FROM current_assets WHERE asset_id='id:A'"
        ).fetchone()[0]
        == "id:FOLDER"
    )
    assert (
        state.conn.execute(
            "SELECT parent_folder_id FROM current_assets WHERE asset_id='id:FOLDER'"
        ).fetchone()[0]
        == "id:ROOT"
    )


def test_incomplete_scan_must_be_resumed(scoped):
    state, run, scope, fake = scoped
    result = census(state, run, scope, max_pages=1)
    with pytest.raises(Blocked, match="Resume"):
        census(state, run, scope)
    assert (
        census(state, run, scope, resume=result["scan_id"])["objective_outcome"]
        == "ENUMERATION_COMPLETE_VISIBLE_SCOPE"
    )


def test_later_census_missing_id_is_not_reported_present_or_deleted(scoped):
    state, run, scope, fake = scoped
    census(state, run, scope)
    del fake.backend["metadata"]["id:BMP"]
    census(state, run, scope)
    assert (
        state.conn.execute("SELECT status FROM current_assets WHERE asset_id='id:BMP'").fetchone()[
            0
        ]
        == "not_observed_in_latest_census"
    )
    assert state.conn.execute("SELECT count(*) FROM operations").fetchone()[0] == 0


def test_h01_remains_held_when_same_folder_hash_matches(scoped):
    state, run, scope, fake = scoped
    add_batch(
        state,
        "H01",
        [{"Target file ID": "id:A", "Designated keeper ID": "id:a"}],
        saved="Complete - holds retained",
    )
    source = "plan/batches/H01.csv"
    with state.conn:
        state.conn.execute(
            "INSERT INTO holds VALUES (?,?,?,?,?,?,NULL)",
            (
                "H01-01",
                "id:A",
                "historical_connector_safety_hold",
                "Preserve authority hold",
                1,
                source,
            ),
        )
    result = run_batch(state, run, "H01", scope=scope, new_attempt=True)
    pair = result["results"][0]
    assert pair["same_size"] and pair["same_server_hash"] and pair["same_immediate_parent"]
    assert pair["outcome"] == "REVIEW_FINISHED_HOLD_RETAINED"
    assert pair["deletion_eligible"] is False
    assert result["exit_code"] == 3
    assert state.conn.execute("SELECT active FROM holds").fetchone()[0] == 1


def test_duplicate_in_different_immediate_folders_is_rejected(scoped):
    state, run, scope, fake = scoped
    moved = fake.backend["metadata"]["id:a"]
    moved.update(
        path_lower="/library/elsewhere.jpg",
        path_display="/Library/elsewhere.jpg",
        name="elsewhere.jpg",
    )
    add_batch(state, "D-DEMO", [{"Delete file ID": "id:A", "Keep file ID": "id:a"}])
    result = run_batch(state, run, "D-DEMO", scope=scope)
    assert result["results"][0]["outcome"] == "REJECTED_DIFFERENT_IMMEDIATE_PARENTS"
    assert result["results"][0]["direct_sharing"]["universal_no_sharing_proof"] is False


def test_missing_scope_is_specific_without_exposing_token():
    error = AuthError(
        "request-123", SDKAuthError.missing_scope(TokenScopeError("files.content.read"))
    )
    translated = translate_exception(error)
    assert translated.kind == "missing_scope"
    assert translated.details["required_scope"] == "files.content.read"


def test_rate_limit_honors_retry_after_without_permission_retry():
    delays, calls = [], []
    adapter = NativeDropbox(object(), sleep=delays.append)

    def call():
        calls.append(1)
        if len(calls) == 1:
            raise RateLimitError("request", backoff=3)
        return "success"

    assert adapter._read(call) == "success"
    assert delays == [3]
    delays.clear()
    with pytest.raises(RemoteError) as error:
        adapter._read(lambda: (_ for _ in ()).throw(RateLimitError("request", backoff=90)))
    assert error.value.retry_after == 90 and delays == []


def test_read_network_error_does_not_expose_raw_request_credentials():
    adapter = NativeDropbox(object(), policy={"max_attempts": 1})
    with pytest.raises(RemoteError) as result:
        adapter._read(
            lambda: (_ for _ in ()).throw(
                requests.ConnectionError("Authorization: Bearer private-token")
            )
        )
    assert "private-token" not in json.dumps(result.value.public())
    assert result.value.kind == "network_or_dns"


class MemoryStore:
    def __init__(self):
        self.value = None

    def get(self, reference):
        return deepcopy(self.value)

    def put(self, reference, value):
        self.value = deepcopy(value)


def test_oauth_requests_pkce_offline_and_stores_no_token_in_config(local_state, monkeypatch):
    settings, store = {}, MemoryStore()

    class Flow:
        def __init__(self, key, **kwargs):
            settings.update(kwargs)

        def start(self):
            return "https://www.dropbox.com/oauth2/authorize?test=synthetic"

        def finish(self, code):
            assert code == "local-hidden-code"
            return SimpleNamespace(
                scope=" ".join(READ_SCOPES),
                refresh_token="private-refresh",
                account_id="test-account",
            )

    monkeypatch.setattr("dropbox.oauth.DropboxOAuth2FlowNoRedirect", Flow)
    result = authorize(
        local_state.config,
        store=store,
        input_code=lambda _: "local-hidden-code",
        open_browser=False,
    )
    assert settings["use_pkce"] is True and settings["token_access_type"] == "offline"
    assert store.value["refresh_token"] == "private-refresh"
    assert "private-refresh" not in local_state.config.path.read_text()
    assert "private-refresh" not in canonical(result)


def test_sdk_automatic_retries_disabled(local_state, monkeypatch):
    kwargs, store = {}, MemoryStore()
    store.value = {
        "refresh_token": "private-refresh",
        "app_key": "public-test-key",
        "account_id": "test-account",
        "granted_scopes": list(READ_SCOPES),
    }

    def client(**values):
        kwargs.update(values)
        return object()

    monkeypatch.setattr("dropbox.Dropbox", client)
    native_adapter(local_state.config, store=store)
    assert kwargs["max_retries_on_error"] == kwargs["max_retries_on_rate_limit"] == 0
    assert kwargs["scope"] == list(READ_SCOPES)
    assert "app_secret" not in kwargs


def test_immutable_protection_and_exclusion_rows(local_state):
    source = "fixture.csv"
    with local_state.conn:
        local_state.conn.execute(
            "INSERT INTO sources VALUES (?,?,?,?,?,?)",
            (source, "hash", 0, utc_now(), ".csv", "synthetic"),
        )
        local_state.conn.execute(
            "INSERT INTO protections VALUES (?,?,?,?)", ("id:KEEP", "keeper", "test", source)
        )
        local_state.conn.execute(
            "INSERT INTO exclusions VALUES (?,?,?,?)", ("id:DONE", "completed", source, "{}")
        )
    for sql in (
        "UPDATE protections SET asset_id='id:OTHER'",
        "DELETE FROM protections",
        "UPDATE exclusions SET asset_id='id:OTHER'",
        "DELETE FROM exclusions",
    ):
        with local_state.conn, pytest.raises(sqlite3.IntegrityError):
            local_state.conn.execute(sql)


@pytest.mark.parametrize(
    "arguments",
    [
        ["apply", "R001"],
        ["batch", "run", "M004", "--read-only", "--force"],
        ["auth", "--profile", "admin", "--pkce", "--offline"],
    ],
)
def test_write_and_bypass_commands_are_unavailable(arguments):
    with pytest.raises(SystemExit) as result:
        parser().parse_args(arguments)
    assert result.value.code == 2
