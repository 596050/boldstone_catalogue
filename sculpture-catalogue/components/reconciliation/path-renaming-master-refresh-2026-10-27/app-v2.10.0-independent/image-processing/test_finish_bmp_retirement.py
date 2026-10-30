"""Exact approval and shared-link exception boundaries; no live API calls."""
from __future__ import annotations

import copy
import zipfile
from types import SimpleNamespace

import finish_bmp_retirement as f
import pytest
from test_retire_bmps import metadata


def approval():
    return {"user_instruction": f.INSTRUCTION, "source_ids": list(f.IDS),
            "h01_clearance_for_exact_actions": True, "moonphase_link_loss_accepted": True}


@pytest.mark.parametrize("change", [None, "instruction", "missing_file", "extra_file", "h01", "public_link"])
def test_exact_three_file_approval_is_required(monkeypatch, change):
    decision = approval()
    manifest = {"approval": {}, "rows": [{"source_id": i} for i in f.IDS]}
    if change == "instruction":
        decision["user_instruction"] = "Unrelated approval"
    elif change == "missing_file":
        manifest["rows"].pop()
    elif change == "extra_file":
        manifest["rows"].append({"source_id": "id:unreviewed"})
    elif change == "h01":
        decision["h01_clearance_for_exact_actions"] = False
    elif change == "public_link":
        decision["moonphase_link_loss_accepted"] = False
    monkeypatch.setattr(f, "read_reference", lambda _: decision)
    if change is None:
        f.approved_scope(manifest)
    else:
        with pytest.raises(f.w.Hold):
            f.approved_scope(manifest)


@pytest.mark.parametrize("change", [None, "different_link", "other_source", "additional_public_link", "new_membership"])
def test_public_link_exception_is_limited_to_the_reviewed_moonphase_link(change):
    source = metadata(identifier=f.MOON)
    identifier = f.MOON
    links = [{"resolved_visibility": "public", "effective_audience": "public", "url_sha256": f.PUBLIC_LINK_HASH}]
    if change == "different_link":
        links[0]["url_sha256"] = "a" * 64
    elif change == "other_source":
        identifier = f.KEEPER
    elif change == "additional_public_link":
        links.append({**copy.deepcopy(links[0]), "url_sha256": "b" * 64})
    elif change == "new_membership":
        source.has_explicit_shared_members = True
    if change is None:
        f.sharing_guard(identifier, source, links)
    else:
        with pytest.raises(f.w.Hold):
            f.sharing_guard(identifier, source, links)


def test_owner_navigation_link_remains_allowed():
    f.sharing_guard(f.KEEPER, metadata(identifier=f.KEEPER), [
        {"resolved_visibility": "no_one", "effective_audience": "no_one", "url_sha256": "c" * 64}])


@pytest.mark.parametrize("outcome", ["success", "unknown", "changed_jpeg"])
def test_deletion_is_conditional_journaled_and_never_retried(tmp_path, monkeypatch, outcome):
    original = tmp_path / "original.bmp"
    original.write_bytes(b"test-original-bytes")
    fingerprint = f.w.fingerprint(original)
    archive_path = tmp_path / "originals.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(original, "original.bmp")
    source = metadata(identifier=f.TARGET, content_hash=fingerprint["content_hash"], size=fingerprint["size"])
    jpeg = metadata(source.path_display[:-4] + ".jpg", "id:verified-jpeg", "987654321", "b" * 64)
    output = f.w.head(jpeg)
    row = {"source_id": source.id, "source_path": source.path_display, "source_head": f.w.head(source),
           "archive_member": "original.bmp", "backup": fingerprint}
    manifest = {"approval": {"type": "approval"}, "evidence": {"database_controls": {"type": "controls"}},
                "archive": {"path": str(archive_path)}, "rows": [{"source_id": i} for i in f.IDS]}
    events, calls = [], []
    monkeypatch.setattr(f, "read_reference", lambda ref: approval() if ref["type"] == "approval" else {})
    monkeypatch.setattr(f, "controls_unchanged", lambda _: None)
    monkeypatch.setattr(f, "current_source", lambda *_: {"source_head": row["source_head"]})
    monkeypatch.setattr(f, "record", lambda kind, identifier, status, *_args, **_kwargs: events.append(status))
    monkeypatch.setattr(f.w.BUDGET, "wait", lambda: None)

    def delete(identifier, parent_rev):
        assert events == ["DELETE_INTENT"]
        assert (identifier, parent_rev) == (source.id, source.rev)
        calls.append(identifier)
        if outcome == "unknown":
            raise TimeoutError("ambiguous response")
        return SimpleNamespace(metadata=source)

    if outcome == "changed_jpeg":
        jpeg.rev = "123456789"
    api = SimpleNamespace(metadata=lambda identifier: jpeg if identifier == jpeg.id else None,
                          client=SimpleNamespace(files_delete_v2=delete))
    if outcome == "success":
        f.delete_once(api, manifest, row, output, "manifest")
        assert events == ["DELETE_INTENT", "DELETE_RETURNED", "DELETED_VERIFIED"] and len(calls) == 1
    elif outcome == "unknown":
        with pytest.raises(f.w.SetupError):
            f.delete_once(api, manifest, row, output, "manifest")
        assert events == ["DELETE_INTENT", "DELETE_OUTCOME_UNKNOWN"] and len(calls) == 1
    else:
        with pytest.raises(f.w.Hold):
            f.delete_once(api, manifest, row, output, "manifest")
        assert not events and not calls
