"""Fidelity and destructive-operation safety tests using local files and fake APIs."""
from __future__ import annotations

import copy
from datetime import datetime
from types import SimpleNamespace

import execute_held_resolution as e
import pytest
from dropbox.files import FileMetadata
from inspect_held_bmps import inspect_jpeg
from PIL import Image


@pytest.mark.parametrize("quality,sampling,resize,accepted", [(100, 0, False, True), (95, 0, False, False), (100, 2, False, False), (100, 0, True, False)])
def test_replacement_must_preserve_full_quality_pixels_sampling_and_dimensions(tmp_path, quality, sampling, resize, accepted):
    image = Image.new("RGB", (64, 48))
    image.putdata([((x * 17 + y * 31) % 256, x * 23 % 256, y * 29 % 256) for y in range(48) for x in range(64)])
    expected, candidate = tmp_path / "q100.jpg", tmp_path / "candidate.jpg"
    image.save(expected, quality=100, subsampling=0, dpi=(96, 96))
    if resize:
        image = image.resize((32, 24))
    image.save(candidate, quality=quality, subsampling=sampling, dpi=(96, 96))
    assert inspect_jpeg(candidate, expected)["verified_replacement"] is accepted


def test_same_pixels_with_changed_display_metadata_are_not_reused(tmp_path):
    image = Image.new("RGB", (32, 24), "white")
    first, second = tmp_path / "first.jpg", tmp_path / "second.jpg"
    image.save(first, quality=100, subsampling=0, dpi=(96, 96))
    image.save(second, quality=100, subsampling=0, dpi=(72, 72))
    result = inspect_jpeg(second, first)
    assert result["same_decoded_pixels_as_verified_conversion"]
    assert not result["verified_replacement"]


def sample():
    path = e.w.ROOT_PATH + "/Family/Leaf/image.bmp"
    metadata = FileMetadata(name="image.bmp", id="id:source", rev="abcdef123",
                            content_hash="a" * 64, size=1234, path_display=path, path_lower=path.lower(),
                            client_modified=datetime(2026, 10, 15), server_modified=datetime(2026, 10, 15),
                            has_explicit_shared_members=False)
    source = e.w.head(metadata)
    output = {**source, "id": "id:jpeg", "rev": "123abcdef", "content_hash": "b" * 64, "path": path[:-4] + ".jpg"}
    row = {"source_id": source["id"], "source_path": path, "source_head": source, "unresolved": [], "original_hold_reasons": []}
    group = {"group_id": "id:source"}
    proof = {"source_head": source, "output_head": output}
    return metadata, row, group, proof, {"status": "SUCCESSOR_VERIFIED", "output_head": output}


@pytest.mark.parametrize("change", ["h01", "unresolved", "source_revision", "successor_hash", "wrong_extension", "unverified_successor"])
def test_unsafe_delete_never_reaches_api(monkeypatch, change):
    _, row, group, proof, state = sample()
    proof = copy.deepcopy(proof)
    if change == "h01":
        row["original_hold_reasons"] = ["H01_TARGET_OR_KEEPER"]
    elif change == "unresolved":
        row["unresolved"] = ["ACTIVE_OR_UNKNOWN_DIRECT_LINK"]
    elif change == "source_revision":
        proof["source_head"]["rev"] = "changed"
    elif change == "successor_hash":
        proof["output_head"]["content_hash"] = "c" * 64
    elif change == "wrong_extension":
        row["source_path"] = row["source_path"][:-4] + ".jpg"
    elif change == "unverified_successor":
        state["status"] = "UPLOAD_RETURNED"
    monkeypatch.setattr(e, "saved", lambda *_: state)
    api = SimpleNamespace(client=SimpleNamespace(files_delete_v2=lambda *_args, **_kwargs: pytest.fail("Unsafe delete submitted")))
    monkeypatch.setattr(e, "record", lambda *_args, **_kwargs: pytest.fail("Unsafe delete intent recorded"))
    with pytest.raises(e.w.Hold):
        e.delete_once(api, row, group, proof, "manifest")


def test_delete_is_exact_revision_conditional_and_journaled_before_call(monkeypatch):
    metadata, row, group, proof, state = sample()
    events = []
    monkeypatch.setattr(e, "saved", lambda *_: state)
    monkeypatch.setattr(e, "record", lambda kind, identifier, status, *_args, **_kwargs: events.append(status))
    monkeypatch.setattr(e.w.BUDGET, "wait", lambda: None)

    def delete(identifier, parent_rev):
        assert events == ["DELETE_INTENT"]
        assert identifier == metadata.id and parent_rev == metadata.rev
        return SimpleNamespace(metadata=metadata)

    e.delete_once(SimpleNamespace(client=SimpleNamespace(files_delete_v2=delete)), row, group, proof, "manifest")
    assert events == ["DELETE_INTENT", "DELETE_RETURNED"]


def test_unknown_delete_outcome_is_recorded_and_never_retried(monkeypatch):
    _, row, group, proof, state = sample()
    events, calls = [], []
    monkeypatch.setattr(e, "saved", lambda *_: state)
    monkeypatch.setattr(e, "record", lambda kind, identifier, status, *_args, **_kwargs: events.append(status))
    monkeypatch.setattr(e.w.BUDGET, "wait", lambda: None)

    def delete(identifier, parent_rev):
        calls.append((identifier, parent_rev))
        raise TimeoutError("ambiguous network outcome")

    with pytest.raises(e.w.SetupError):
        e.delete_once(SimpleNamespace(client=SimpleNamespace(files_delete_v2=delete)), row, group, proof, "manifest")
    assert len(calls) == 1
    assert events == ["DELETE_INTENT", "DELETE_OUTCOME_UNKNOWN"]


def test_keeper_protection_cannot_transfer_before_successor_verification(monkeypatch):
    manifest = {"evidence": {"relationships": {}}, "groups": [{"group_id": "id:keeper"}],
                "ready": [{"replacement_group": "id:keeper", "source_id": "id:keeper", "protection_transition_required": True}]}
    monkeypatch.setattr(e, "read_reference", lambda _: {"records": []})
    monkeypatch.setattr(e, "saved", lambda *_: {"status": "UPLOAD_RETURNED", "manifest_sha256": "manifest"})
    monkeypatch.setattr(e.w, "private_json", lambda *_args, **_kwargs: pytest.fail("Unverified protection transition written"))
    with pytest.raises(e.w.SetupError):
        e.establish_lineage(manifest, "manifest")
