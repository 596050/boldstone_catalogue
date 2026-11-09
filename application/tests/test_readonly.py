from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import pytest
from conftest import add_batch, metadata
from dropbox.common import UserRootInfo
from dropbox.files import FileMetadata, FolderMetadata, ListFolderResult
from dropbox.users import FullAccount, Name
from dropbox.users_common import AccountType

from boldstone.authentication import validate_grant
from boldstone.binary_cache import check_binary, require_capability
from boldstone.census import census
from boldstone.config import READ_SCOPES
from boldstone.controls import validate_controls
from boldstone.dropbox_adapter import NativeDropbox, sdk_json
from boldstone.errors import Blocked, IntegrityError, RemoteError
from boldstone.hashing import BLOCK_SIZE, dropbox_content_hash
from boldstone.identity import SUPPLEMENTAL, consolidate_identity
from boldstone.importers import import_pack
from boldstone.naming import assess_name
from boldstone.reporting import checkpoint, save_review_report, spreadsheet_literal
from boldstone.reviews import run_batch
from boldstone.root import RootScope, confirm_root
from boldstone.state import State
from boldstone.util import atomic_write, canonical, digest, utc_now


def test_sdk_native_serialization_has_metadata_tag():
    value = FileMetadata(
        name="image.jpg",
        id="id:synthetic",
        client_modified=datetime(2026, 1, 1),
        server_modified=datetime(2026, 1, 1),
        rev="123456789",
        size=0,
        path_lower="/library/image.jpg",
        path_display="/Library/image.jpg",
    )
    assert sdk_json(value)[".tag"] == "file"
    folder = FolderMetadata(
        name="Library", id="id:ROOT", path_lower="/library", path_display="/Library"
    )
    result = sdk_json(ListFolderResult(entries=[value, folder], cursor="cursor", has_more=False))
    assert result["entries"][1][".tag"] == "folder"


def test_sdk_facade_has_no_mutation_interface():
    for name in ("delete", "move", "upload", "restore", "apply", "files_delete_v2"):
        assert not hasattr(NativeDropbox, name)


def test_root_confirmation_preserves_structured_sdk_account_name(local_state, fake, monkeypatch):
    fake.account_id = "dbid:" + "A" * 35
    config = local_state.config.with_dropbox(expected_account_id=fake.account_id)
    account = sdk_json(
        FullAccount(
            account_id=fake.account_id,
            name=Name(
                given_name="Test",
                surname="Account",
                familiar_name="Test",
                display_name="Test Account",
                abbreviated_name="TA",
            ),
            email="test@example.invalid",
            email_verified=True,
            disabled=False,
            locale="en",
            referral_link="https://example.invalid/referral",
            is_paired=False,
            account_type=AccountType.basic,
            root_info=UserRootInfo(
                root_namespace_id=fake.namespace, home_namespace_id=fake.namespace
            ),
        )
    )
    monkeypatch.setattr(fake, "account", lambda: deepcopy(account))
    with local_state.run() as run:
        result = confirm_root(local_state, run, fake, config, acknowledgement="id:ROOT")
        assert result["objective_outcome"] == "ROOT_CONFIRMED"
        assert RootScope(local_state, run, fake, config=config).root["id"] == "id:ROOT"

    observation = local_state.conn.execute(
        "SELECT * FROM observations WHERE endpoint='users/get_current_account' LIMIT 1"
    ).fetchone()
    assert observation["name"] == "Test Account"
    assert observation["asset_id"] is None
    assert json.loads(observation["response_json"]) == account
    assert json.loads(Path(observation["raw_evidence_path"]).read_text()) == account
    file_observation = local_state.conn.execute(
        "SELECT name FROM observations WHERE asset_id='id:A' LIMIT 1"
    ).fetchone()
    assert file_observation["name"] == "family__dsc-001.jpg"
    assert fake.backend["writes"] == []


def test_wrong_account_rejected(local_state, fake):
    fake.account_id = "wrong-account"
    with local_state.run() as run, pytest.raises(Blocked, match="account"):
        confirm_root(local_state, run, fake, local_state.config, acknowledgement="id:ROOT")


def test_wrong_namespace_rejected(local_state, fake):
    config = local_state.config.with_dropbox(verified_namespace_id="999")
    with local_state.run() as run, pytest.raises(RemoteError):
        confirm_root(local_state, run, fake, config, acknowledgement="id:ROOT")


def test_root_requires_operator_confirmation(local_state, fake):
    with local_state.run() as run, pytest.raises(Blocked, match="confirmation"):
        RootScope(local_state, run, fake)


def test_wrong_root_acknowledgement_rejected(local_state, fake):
    with local_state.run() as run, pytest.raises(Blocked, match="confirmation"):
        confirm_root(local_state, run, fake, local_state.config, acknowledgement="yes")


def test_two_distinct_known_ids_required(local_state, fake):
    config = local_state.config.with_dropbox(known_file_ids=["id:A", "id:A"])
    with local_state.run() as run, pytest.raises(Blocked, match="two known"):
        confirm_root(local_state, run, fake, config, acknowledgement="id:ROOT")


def test_scope_prefix_lookalike_rejected(scoped):
    state, run, scope, fake = scoped
    fake.backend["metadata"]["id:OUT"] = metadata("id:OUT", "/Library-old/photo.jpg", b"x")
    with pytest.raises(Blocked, match="outside"):
        scope.resolve("id:OUT")


def test_opaque_id_case_is_preserved(scoped):
    state, run, scope, fake = scoped
    assert scope.resolve("id:A")["id"] == "id:A"
    assert scope.resolve("id:a")["id"] == "id:a"


def test_no_write_scopes_allowed(local_state):
    grant = {
        "app_key": "public-test-key",
        "account_id": "test-account",
        "refresh_token": "never-logged",
        "granted_scopes": [*READ_SCOPES, "files.content.write"],
    }
    with pytest.raises(Blocked, match="four read scopes"):
        validate_grant(grant, local_state.config)
    grant["granted_scopes"] = list(READ_SCOPES)
    validate_grant(grant, local_state.config)


def test_census_consumes_all_pages(scoped):
    state, run, scope, fake = scoped
    result = census(state, run, scope)
    assert result["pages"] == 2
    assert state.conn.execute("SELECT count(*) FROM current_assets").fetchone()[0] == 4
    assert state.conn.execute("SELECT enumeration_exhausted FROM scans").fetchone()[0] == 1


def test_partial_census_resumes_without_duplicate_entries(scoped):
    state, run, scope, fake = scoped
    first = census(state, run, scope, max_pages=1)
    assert first["resume_required"]
    second = census(state, run, scope, resume=first["scan_id"])
    assert second["pages"] == 2
    assert state.conn.execute("SELECT count(*) FROM inventory_entries").fetchone()[0] == 4
    assert state.conn.execute("SELECT count(*) FROM cursor_pages").fetchone()[0] == 2


def test_failed_page_preserves_cursor_and_can_resume(scoped):
    state, run, scope, fake = scoped
    first = census(state, run, scope, max_pages=1)
    cursor = state.conn.execute("SELECT current_cursor FROM scans").fetchone()[0]
    fake.backend["failures"][cursor] = [RemoteError("network_or_dns")]
    with pytest.raises(RemoteError):
        census(state, run, scope, resume=first["scan_id"])
    assert state.conn.execute("SELECT count(*) FROM cursor_pages").fetchone()[0] == 1
    result = census(state, run, scope, resume=first["scan_id"])
    assert result["pages"] == 2


def test_incremental_path_deletion_does_not_invent_id_or_operation(scoped):
    state, run, scope, fake = scoped
    census(state, run, scope)
    fake.backend["changes"] = [
        {
            ".tag": "deleted",
            "name": "family__dsc-001.jpg",
            "path_lower": "/library/family/family__dsc-001.jpg",
        }
    ]
    census(state, run, scope, incremental=True)
    tombstone = state.conn.execute(
        "SELECT asset_id FROM observations WHERE observation_outcome='path_tombstone'"
    ).fetchone()
    assert tombstone[0] is None
    assert state.conn.execute("SELECT count(*) FROM operations").fetchone()[0] == 0
    assert (
        state.conn.execute("SELECT status FROM current_assets WHERE asset_id='id:A'").fetchone()[0]
        == "not_observed_after_path_tombstone"
    )


def test_folder_move_rebases_derived_paths_and_invalidates_pending_work(scoped):
    state, run, scope, fake = scoped
    census(state, run, scope)
    folder = fake.backend["metadata"]["id:FOLDER"]
    folder.update(path_lower="/library/renamed", path_display="/Library/Renamed", name="Renamed")
    fake.backend["changes"] = [deepcopy(folder)]
    census(state, run, scope, incremental=True)
    child = state.conn.execute(
        "SELECT path_lower,status FROM current_assets WHERE asset_id='id:A'"
    ).fetchone()
    assert tuple(child) == ("/library/renamed/family__dsc-001.jpg", "derived_path_needs_refresh")
    assert (
        state.conn.execute(
            "SELECT count(*) FROM change_invalidations WHERE reason='folder_moved'"
        ).fetchone()[0]
        == 1
    )


def test_cursor_reset_retains_old_scan(scoped):
    state, run, scope, fake = scoped
    first = census(state, run, scope)
    cursor = state.conn.execute("SELECT cursor FROM cursor_tracks").fetchone()[0]
    fake.backend["failures"][cursor] = RemoteError("cursor_reset")
    with pytest.raises(RemoteError):
        census(state, run, scope, incremental=True)
    assert (
        state.conn.execute(
            "SELECT count(*) FROM scan_details WHERE state='CURSOR_RESET'"
        ).fetchone()[0]
        == 1
    )
    replacement = census(state, run, scope)
    assert replacement["scan_id"] != first["scan_id"]


def test_explicit_access_limit_is_not_complete_scope(scoped):
    state, run, scope, fake = scoped
    fake.backend["metadata"]["id:FOLDER"]["sharing_info"] = {"traverse_only": True}
    result = census(state, run, scope)
    assert result["objective_outcome"] == "ACCESS_LIMITED"
    assert state.conn.execute("SELECT scope_complete FROM scans").fetchone()[0] == 0


def test_fresh_download_hash_decode_and_format(scoped):
    state, run, scope, fake = scoped
    result = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    assert result["exit_code"] == 0
    assert result["image"]["full_pixel_decode"]
    assert result["image"]["width"] == 20
    assert Path(result["cache_path"]).exists()
    assert result["sha256"] != result["dropbox_content_hash"]


@pytest.mark.parametrize("changed", ["size", "hash", "revision", "id"])
def test_mismatched_download_is_not_promoted(scoped, changed):
    state, run, scope, fake = scoped
    returned = deepcopy(fake.backend["metadata"]["id:A"])
    field = {"size": "size", "hash": "content_hash", "revision": "rev", "id": "id"}[changed]
    returned[field] = 999 if field == "size" else "different"
    fake.backend["downloads"]["id:A"] = returned
    result = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    assert result["exit_code"] == 7
    assert result["cache_path"] is None
    assert not list(state.config.directory("cache").rglob("*.verified-original"))
    assert not list(state.config.directory("cache").rglob(".download-*"))


def test_same_size_different_download_bytes_fails_hash(scoped):
    state, run, scope, fake = scoped
    data = fake.backend["contents"][("id:A", "123456789")]
    fake.backend["contents"][("id:A", "123456789")] = data[:-1] + bytes([data[-1] ^ 1])
    result = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    assert result["checks"]["size"] == "pass"
    assert result["checks"]["hash"] == "fail"


def test_corrupt_stream_with_matching_hash_still_fails_decode(scoped):
    state, run, scope, fake = scoped
    data = b"This is not an image"
    fake.backend["metadata"]["id:A"] = metadata("id:A", "/Library/Family/corrupt.jpg", data)
    fake.backend["contents"][("id:A", "123456789")] = data
    result = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    assert result["checks"]["hash"] == "pass"
    assert result["checks"]["decode"] == "fail"
    assert result["exit_code"] == 7


def test_actual_format_is_checked_independently_of_extension(scoped):
    state, run, scope, fake = scoped
    result = check_binary(state, run, scope, "id:A", expected_format="BMP")
    assert result["checks"]["decode"] == "pass"
    assert result["checks"]["format"] == "fail"
    assert result["cache_path"] is None


def test_download_permission_failure_keeps_unknown_integrity(scoped):
    state, run, scope, fake = scoped
    fake.backend["failures"]["download:id:A"] = RemoteError("permission")
    result = check_binary(state, run, scope, "id:A", expected_format="JPEG")
    assert result["exit_code"] == 5
    assert result["checks"]["metadata"] == "pass"
    assert result["checks"]["hash"] == "unknown"


def test_historical_standardized_name_is_noop_with_suffix():
    name = "family__dsc-001__asset-abc123.jpg"
    row = {"Earlier detailed path": "/BOLDSTONE MASTER/Products/01 Wall Sculptures/Family/" + name}
    meta = {"name": name, "path_lower": "/library/family/" + name}
    assert (
        assess_name(meta, row, "/library")["outcome"] == "REVIEWED_NO_CHANGE_HISTORICAL_NAME_MATCH"
    )


def test_stale_parent_prefix_is_held():
    row = {"Earlier detailed path": "/BOLDSTONE MASTER/Products/01 Wall Sculptures/Old/name.jpg"}
    meta = {"name": "name.jpg", "path_lower": "/library/new/name.jpg"}
    assert assess_name(meta, row, "/library")["outcome"] == "HELD_STALE_HISTORICAL_PARENT"


def test_metadata_review_collision_and_immutable_history(scoped):
    state, run, scope, fake = scoped
    row = {
        "Dropbox file ID": "id:A",
        "Original byte size": str(fake.backend["metadata"]["id:A"]["size"]),
        "Earlier detailed path": "/BOLDSTONE MASTER/Products/01 Wall Sculptures/Family/family__dsc-002.jpg",
    }
    add_batch(state, "M-DEMO", [row])
    result = run_batch(state, run, "M-DEMO", scope=scope)
    assert result["results"][0]["outcome"] == "HELD_COLLISION"
    assert result["proposed_changes_applied"] == 0
    assert state.conn.execute("SELECT saved_status FROM batches").fetchone()[0] == "Planned"
    with state.conn, pytest.raises(sqlite3.IntegrityError):
        state.conn.execute("UPDATE batches SET saved_status='Complete'")


def test_s02_failed_test_is_not_success(scoped):
    state, run, scope, fake = scoped
    add_batch(
        state,
        "S02",
        [{"Dropbox ID": "id:BMP", "Role": "BMP"}, {"Dropbox ID": "id:A", "Role": "JPG"}],
        saved="Complete - test failed",
    )
    fake.backend["failures"]["download:id:A"] = RemoteError("network_or_dns")
    result = run_batch(state, run, "S02", scope=scope, new_attempt=True)
    assert result["objective_outcome"] == "CAPABILITY_FAILED"
    assert result["exit_code"] != 0
    assert state.conn.execute("SELECT objective_completed_utc FROM attempts").fetchone()[0] is None
    with pytest.raises(Blocked):
        require_capability(state)


def test_jpg_integrity_does_not_invent_source_equivalence(scoped):
    state, run, scope, fake = scoped
    add_batch(
        state,
        "S02",
        [{"Dropbox ID": "id:BMP", "Role": "BMP"}, {"Dropbox ID": "id:A", "Role": "JPG"}],
    )
    run_batch(state, run, "S02", scope=scope)
    add_batch(
        state,
        "J001",
        [
            {
                "Dropbox file ID": "id:a",
                "Related original BMP ID": "id:MISSING",
                "Observed bytes": "100",
            }
        ],
        saved="Partial",
    )
    result = run_batch(state, run, "J001", scope=scope, new_attempt=True)
    assert result["exit_code"] == 4
    assert result["results"][0]["binary"]["exit_code"] == 0
    assert result["results"][0]["fresh_source_equivalence_verified"] is False
    assert (
        state.conn.execute("SELECT saved_status FROM batches WHERE batch_id='J001'").fetchone()[0]
        == "Partial"
    )


def test_checkpoint_contains_consistent_database_derived_ledger_and_verified_bytes(scoped):
    state, run, scope, fake = scoped
    census(state, run, scope)
    result = checkpoint(state)
    with zipfile.ZipFile(result["path"]) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        events = [json.loads(line) for line in bundle.read("events.jsonl").splitlines()]
        assert events[-1]["event_type"] == "inventory_finished"
        assert manifest["original_image_backups_included"] is False
        assert any(name.startswith("evidence/") for name in bundle.namelist())
    assert state.validate_events()["result"] == "pass"


def test_append_only_event_and_membership_protection(local_state):
    with local_state.conn:
        local_state.event("test", "synthetic", "test_event", {"private": "ordinary metadata"})
    for sql in ("DELETE FROM events", "UPDATE events SET payload_json='{}'"):
        with local_state.conn, pytest.raises(sqlite3.IntegrityError):
            local_state.conn.execute(sql)
    assert local_state.validate_events()["result"] == "pass"


def test_symlink_destination_rejected_without_touching_target(tmp_path):
    target = tmp_path / "original"
    target.write_text("unchanged")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(IntegrityError):
        atomic_write(link, "corrupt", exclusive=False)
    assert target.read_text() == "unchanged"


@pytest.mark.parametrize("value", ["=HYPERLINK('x')", " +CMD", "@x", "\t=1", "-2+4"])
def test_formula_like_report_values_are_safe(value):
    assert spreadsheet_literal(value).startswith("'")


def test_html_report_escapes_filename_scripts(local_state):
    result = {
        "batch_id": "M-DEMO",
        "attempt_id": "test",
        "objective_outcome": "REVIEW",
        "results": [
            {"asset_id": "id:TEST", "outcome": "REVIEW", "name": "<script>alert(1)</script>"}
        ],
    }
    paths = save_review_report(local_state, result)
    assert "<script>" not in Path(paths["html"]).read_text()
    assert json.loads(Path(paths["json"]).read_text())["results"][0]["name"].startswith("<script>")


def test_same_folder_questions_are_linked_without_claiming_aliases(local_state):
    source = SUPPLEMENTAL[1]
    rows = [
        {
            "Dropbox folder ID": "id:FOLDER",
            "Source identity constraint": q,
            "Source date": "2026-10-13",
        }
        for q in ("Which design repeats?", "Is this a real installation?")
    ]
    with local_state.conn:
        local_state.conn.execute(
            "INSERT INTO sources VALUES (?,?,?,?,?,?)",
            (source, "synthetic", 0, utc_now(), ".csv", "historical"),
        )
        for n, row in enumerate(rows, 1):
            local_state.conn.execute(
                "INSERT INTO source_rows VALUES (?,?,?,?)", (source, n, digest(row), canonical(row))
            )
    with local_state.run() as run:
        result = consolidate_identity(local_state, run)
    assert result["distinct_unresolved_identity_count"] is None
    assert result["new_visual_decisions"] == 0
    assert local_state.conn.execute("SELECT count(*) FROM identity_cases").fetchone()[0] == 2
    assert local_state.conn.execute("SELECT count(*) FROM issue_relations").fetchone()[0] == 1


def test_lineage_cycle_is_blocked(local_state):
    with local_state.conn:
        for n, (first, second) in enumerate((("id:ONE", "id:TWO"), ("id:TWO", "id:ONE"))):
            local_state.conn.execute(
                "INSERT INTO lineage(edge_id,from_asset_id,to_asset_id,relation,evidence_level,evidence_json) VALUES (?,?,?,?,?,?)",
                (str(n), first, second, "duplicate_of", "synthetic", "{}"),
            )
    with pytest.raises(IntegrityError, match="cycle"):
        validate_controls(local_state, full=False)


def test_official_hash_block_boundaries_and_short_reads():
    class Short(io.BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 131071))

    for size in (0, 1, BLOCK_SIZE, BLOCK_SIZE + 1):
        data = b"x" * size
        assert dropbox_content_hash(io.BytesIO(data)) == dropbox_content_hash(Short(data))


def test_shipped_pack_import_is_idempotent_and_preserves_controls(tmp_path):
    from boldstone.config import initialize_config

    pack = Path(__file__).resolve().parents[2] / "dropbox resolution"
    if not (pack / "PACKAGE_SHA256.json").is_file():
        pytest.skip("Requires the separately retained private handover package")
    config = initialize_config(pack, tmp_path.resolve() / "runtime")
    first = import_pack(config)
    second = import_pack(config)
    assert first["created_database"] is True
    assert second["created_database"] is False
    assert second["new_provenance_rows"] == 0
    with State(config) as state:
        controls = validate_controls(state)
        assert controls["counts"]["protected_distinct_ids"] == 1813
        assert controls["counts"]["active_H01_holds"] == 7
        assert state.conn.execute("SELECT count(*) FROM source_provenance").fetchone()[0] == 48213
        assert (
            state.conn.execute(
                "SELECT count(*) FROM observations WHERE is_historical=0"
            ).fetchone()[0]
            == 0
        )
        assert state.conn.execute("SELECT count(*) FROM operations").fetchone()[0] == 0
