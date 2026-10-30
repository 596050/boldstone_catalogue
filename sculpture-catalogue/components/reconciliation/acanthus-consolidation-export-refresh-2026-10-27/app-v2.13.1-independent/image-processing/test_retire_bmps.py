"""Mutation-boundary and conservation tests; all API clients are fake."""
from __future__ import annotations

import copy
import io
from datetime import datetime
from types import SimpleNamespace

import pytest
import retire_bmps as r
from dropbox.files import FileMetadata, FolderMetadata


def metadata(path=None, identifier="id:source", rev="123456789", content_hash="a" * 64, size=12):
    path = path or r.w.ROOT_PATH + "/Family/Leaf/image.bmp"
    return FileMetadata(name=path.rsplit("/", 1)[1], id=identifier,
                        client_modified=datetime(2026, 10, 15), server_modified=datetime(2026, 10, 15),
                        rev=rev, size=size, path_display=path, path_lower=path.lower(),
                        content_hash=content_hash, has_explicit_shared_members=False)


def sample():
    source = metadata()
    jpeg = metadata(source.path_display[:-4] + ".jpg", "id:jpeg", "987654321", "b" * 64)
    row = {"source_id": source.id, "source_path": source.path_display, "destination_path": jpeg.path_display,
           "status": "ELIGIBLE", "hold_reasons": [], "source_head": {"kind": "file", **r.w.head(source)},
           "output_head": {"kind": "file", **r.w.head(jpeg)}}
    proof = {"source_head": r.w.head(source), "output_head": r.w.head(jpeg)}
    return source, row, proof


@pytest.mark.parametrize("change", ["revision", "hash", "size", "id", "path", "basename_case", "folder", "missing"])
def test_file_guard_rejects_changed_or_non_file(change):
    original = metadata()
    expected = r.w.head(original)
    candidate = metadata()
    if change == "revision":
        candidate.rev = "abcdefabc"
    elif change == "hash":
        candidate.content_hash = "c" * 64
    elif change == "size":
        candidate.size = 13
    elif change == "id":
        candidate.id = "id:other"
    elif change == "path":
        candidate.path_display = "/Elsewhere/image.bmp"
    elif change == "basename_case":
        candidate.name = "IMAGE.bmp"
    elif change == "folder":
        candidate = FolderMetadata(name="image.bmp", id=original.id, path_display=original.path_display)
    else:
        candidate = None
    with pytest.raises(r.w.Hold):
        r.assert_file(candidate, expected, original.path_display)


def test_folder_ancestor_display_alias_does_not_hide_basename_change():
    original = metadata()
    candidate = metadata()
    candidate.path_display = candidate.path_display.replace("/Family/", "/FAMILY/")
    r.assert_file(candidate, r.w.head(original), original.path_display)


@pytest.mark.parametrize("visibility,audience", [("public", "public"), (None, None), ("no_one", "team")])
def test_public_or_unknown_link_blocks(visibility, audience):
    with pytest.raises(r.w.Hold):
        r.assert_private_source(metadata(), [{"resolved_visibility": visibility, "effective_audience": audience}])


def test_owner_navigation_link_is_permitted_only_without_members():
    candidate = metadata()
    links = [{"resolved_visibility": "no_one", "effective_audience": "no_one"}]
    r.assert_private_source(candidate, links)
    candidate.has_explicit_shared_members = True
    with pytest.raises(r.w.Hold):
        r.assert_private_source(candidate, links)


def test_conditional_delete_journals_before_one_exact_call(monkeypatch):
    source, row, proof = sample()
    events = []
    monkeypatch.setattr(r, "record", lambda row, status, digest, **details: events.append(status))
    monkeypatch.setattr(r.w.BUDGET, "wait", lambda: None)

    def delete(path, parent_rev):
        assert events == ["DELETE_INTENT"]
        assert path == source.id
        assert parent_rev == source.rev
        events.append("API_DELETE")
        return SimpleNamespace(metadata=source)

    r.delete_once(SimpleNamespace(client=SimpleNamespace(files_delete_v2=delete)), row, proof, "approved-hash")
    assert events == ["DELETE_INTENT", "API_DELETE", "DELETE_RETURNED"]


def test_unknown_write_is_recorded_once_without_retry(monkeypatch):
    _, row, proof = sample()
    events = []
    calls = []
    monkeypatch.setattr(r, "record", lambda row, status, digest, **details: events.append(status))
    monkeypatch.setattr(r.w.BUDGET, "wait", lambda: None)

    def delete(*args, **kwargs):
        calls.append((args, kwargs))
        raise TimeoutError("not logged")

    with pytest.raises(r.w.SetupError):
        r.delete_once(SimpleNamespace(client=SimpleNamespace(files_delete_v2=delete)), row, proof, "approved-hash")
    assert len(calls) == 1
    assert events == ["DELETE_INTENT", "DELETE_OUTCOME_UNKNOWN"]


@pytest.mark.parametrize("change", ["hold", "folder", "empty_revision", "stale_preflight", "not_bmp", "outside_root"])
def test_mutation_guard_makes_no_call_for_invalid_candidate(monkeypatch, change):
    _, row, proof = sample()
    if change == "hold":
        row["hold_reasons"] = ["PROTECTED"]
    elif change == "folder":
        row["source_head"]["kind"] = "folder"
    elif change == "empty_revision":
        row["source_head"]["rev"] = ""
    elif change == "stale_preflight":
        proof["source_head"]["rev"] = "aaaaaaaaa"
    elif change == "not_bmp":
        row["source_path"] = row["source_path"][:-4] + ".jpg"
    else:
        row["source_path"] = "/Elsewhere/image.bmp"
    monkeypatch.setattr(r, "record", lambda *args, **kwargs: pytest.fail("Intent should not be recorded"))
    with pytest.raises(r.w.Hold):
        r.delete_once(SimpleNamespace(client=None), row, proof, "approved-hash")


def test_conservation_only_allows_receipted_removals():
    _, row, _ = sample()
    before = {"entries": [row["source_head"], row["output_head"]]}
    after = {"entries": [copy.deepcopy(row["output_head"])]}
    assert r.compare_retirement(before, after, {row["source_id"]}) == []
    assert r.compare_retirement(before, after, [])
    after["entries"][0]["content_hash"] = "changed"
    assert r.compare_retirement(before, after, {row["source_id"]})


def test_archive_stream_hash_matches_original_fingerprint(tmp_path):
    path = tmp_path / "original.bmp"
    data = b"x" * (r.w.BLOCK_SIZE + 123)
    path.write_bytes(data)
    assert r.fingerprint_stream(io.BytesIO(data)) == r.w.fingerprint(path)
