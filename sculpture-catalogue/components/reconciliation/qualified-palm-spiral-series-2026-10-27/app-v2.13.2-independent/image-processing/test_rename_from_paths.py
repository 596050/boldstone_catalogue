"""Checks for bulk rename collision, conservation, and native batch failures."""
import copy
from datetime import datetime
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from dropbox.files import FileMetadata, FolderMetadata, RelocationBatchResultEntry, RelocationBatchV2Result, RelocationBatchErrorEntry

import rename_from_paths as r


def inventory():
    family = {"kind": "folder", "id": "family", "name": "Moon & Shellwave", "path": r.w.ROOT_PATH + "/Moon & Shellwave", "parent_id": r.w.ROOT_ID}
    leaf = {"kind": "folder", "id": "leaf", "name": "White In Situ", "path": family["path"] + "/White In Situ", "parent_id": "family"}
    files = [{"kind": "file", "id": f"id:file-{i}", "name": name, "path": leaf["path"] + "/" + name, "parent_id": "leaf", "rev": "abc123456", "content_hash": "h" * 64, "size": 42, "has_explicit_shared_members": False, "sharing_info_present": False, "read_only": False, "parent_shared_folder_id": None, "file_lock_present": False} for i, name in enumerate(["z.JPG", "A.png", "a.jpeg"])]
    return {"entries": [family, leaf, *files]}


def test_names_come_from_current_directories_and_keep_exact_extensions():
    rows, batches = r.build_rows(inventory(), {"holds": []})
    assert [x["destination_name"] for x in rows] == ["moon-and-shellwave__white-in-situ__001.jpeg", "moon-and-shellwave__white-in-situ__002.png", "moon-and-shellwave__white-in-situ__003.JPG"]
    assert all(x["source"]["parent_id"] == x["parent_id"] for x in rows)
    assert len(batches) == 1


def test_live_hold_stops_planning():
    with pytest.raises(r.w.Hold, match="AUTHORITY_HOLD"):
        r.build_rows(inventory(), {"holds": [{"asset_id": "id:file-1"}]})


def test_destination_occupied_by_a_different_id_is_not_overwritten():
    source = inventory()
    first = source["entries"][2]
    first["name"] = "moon-and-shellwave__white-in-situ__001.jpeg"
    first["path"] = source["entries"][1]["path"] + "/" + first["name"]
    with pytest.raises(r.w.Hold, match="DESTINATION_COLLISION"):
        r.build_rows(source, {"holds": []})


@pytest.mark.parametrize("field,value", [("content_hash", "changed"), ("size", 99), ("parent_id", "elsewhere"), ("file_lock_present", True), ("rev", "changed"), ("name", "elsewhere.JPG")])
def test_unexpected_content_access_revision_or_name_change_stops(field, value):
    old = {x["id"]: x for x in inventory()["entries"] if x["kind"] == "file"}
    new = copy.deepcopy(old)
    new["id:file-0"][field] = value
    with pytest.raises(r.w.Hold):
        r.compare_parent(old, new)


def test_renamed_revision_may_change_but_bytes_parent_and_extension_must_match():
    old = {x["id"]: x for x in inventory()["entries"] if x["kind"] == "file"}
    new = copy.deepcopy(old)
    new["id:file-0"].update(name="new.JPG", path=str(r.PurePosixPath(old["id:file-0"]["path"]).with_name("new.JPG")), rev="newrev")
    r.compare_parent(old, new, {"id:file-0": new["id:file-0"]["path"]})
    new["id:file-0"]["content_hash"] = "changed"
    with pytest.raises(r.w.Hold, match="CONTENT_HASH"):
        r.compare_parent(old, new, {"id:file-0": new["id:file-0"]["path"]})


def test_missing_sibling_stops_after_readback():
    old = {x["id"]: x for x in inventory()["entries"] if x["kind"] == "file"}
    new = dict(old)
    new.pop("id:file-1")
    with pytest.raises(r.w.Hold, match="MEMBERSHIP"):
        r.compare_parent(old, new)


def test_native_mixed_outcomes_remain_visible_and_fail_batch():
    rows, _ = r.build_rows(inventory(), {"holds": []})
    row = rows[0]
    native = FileMetadata(name=row["destination_name"], id=row["source"]["id"], rev="abc123456", size=42, content_hash="a" * 64, client_modified=datetime(2026, 1, 1), server_modified=datetime(2026, 1, 1), path_display=row["destination_path"])
    result = RelocationBatchV2Result(entries=[RelocationBatchResultEntry.success(native), RelocationBatchResultEntry.failure(RelocationBatchErrorEntry.other)])
    records, failed = r.terminal_rows(result, rows[:2])
    assert failed
    assert [x["tag"] for x in records] == ["success", "failure"]


def test_short_native_receipt_is_not_success():
    rows, _ = r.build_rows(inventory(), {"holds": []})
    with pytest.raises(r.w.Hold, match="COUNT_MISMATCH"):
        r.terminal_rows(RelocationBatchV2Result(entries=[]), rows)


def test_uncertain_individual_write_is_never_retried(tmp_path, monkeypatch):
    rows, _ = r.build_rows(inventory(), {"holds": []})
    calls = []
    def uncertain(**request):
        calls.append(request)
        raise TimeoutError("uncertain write")
    monkeypatch.setattr(r.w.BUDGET, "wait", lambda: None)
    api = SimpleNamespace(client=SimpleNamespace(files_move_v2=uncertain))
    with pytest.raises(TimeoutError):
        r.move_individuals(api, rows, tmp_path)
    assert len(calls) == 1
    assert (tmp_path / "file-001-intent.json").exists()
    assert not (tmp_path / "file-001-receipt.json").exists()


def test_changed_native_content_stops_remaining_writes(tmp_path, monkeypatch):
    rows, _ = r.build_rows(inventory(), {"holds": []})
    calls = []
    def changed(**request):
        calls.append(request)
        row = rows[0]
        return SimpleNamespace(metadata=FileMetadata(name=row["destination_name"], id=row["source"]["id"], rev="abc123456", size=99, content_hash="b" * 64, client_modified=datetime(2026, 1, 1), server_modified=datetime(2026, 1, 1), path_display=row["destination_path"]))
    monkeypatch.setattr(r.w.BUDGET, "wait", lambda: None)
    with pytest.raises(r.w.Hold, match="CONTENT_OR_ID_CHANGED"):
        r.move_individuals(SimpleNamespace(client=SimpleNamespace(files_move_v2=changed)), rows, tmp_path)
    assert len(calls) == 1
    assert (tmp_path / "file-001-receipt.json").exists()


def test_two_workers_use_disjoint_requests_and_preserve_receipt_order(tmp_path, monkeypatch):
    rows, _ = r.build_rows(inventory(), {"holds": []})
    barrier = threading.Barrier(2)
    calls = []
    def moved(**request):
        calls.append(request["from_path"])
        if request["from_path"] in {x["source"]["id"] for x in rows[:2]}:
            barrier.wait(timeout=3)
        row = next(x for x in rows if x["source"]["id"] == request["from_path"])
        return SimpleNamespace(metadata=FileMetadata(name=row["destination_name"], id=row["source"]["id"], rev="abc123456", size=42, content_hash="h" * 64, client_modified=datetime(2026, 1, 1), server_modified=datetime(2026, 1, 1), path_display=row["destination_path"]))
    monkeypatch.setattr(r.w.BUDGET, "wait", lambda: None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = r.move_individuals(SimpleNamespace(client=SimpleNamespace(files_move_v2=moved)), rows, tmp_path, pool)
    assert [x["source_id"] for x in records] == [x["source"]["id"] for x in rows]
    assert len(calls) == len(set(calls)) == 3


def test_parallel_failure_does_not_schedule_remaining_file(tmp_path, monkeypatch):
    rows, _ = r.build_rows(inventory(), {"holds": []})
    barrier = threading.Barrier(2)
    calls = []
    def uncertain(**request):
        calls.append(request["from_path"])
        barrier.wait(timeout=3)
        raise TimeoutError("uncertain write")
    monkeypatch.setattr(r.w.BUDGET, "wait", lambda: None)
    with ThreadPoolExecutor(max_workers=2) as pool, pytest.raises(TimeoutError):
        r.move_individuals(SimpleNamespace(client=SimpleNamespace(files_move_v2=uncertain)), rows, tmp_path, pool)
    assert len(calls) == 2
    assert not (tmp_path / "file-003-intent.json").exists()


@pytest.mark.parametrize("changed", ["revision", "path", "destination", "none"])
def test_known_rejection_requires_unchanged_source_and_vacant_destination(changed):
    row = r.build_rows(inventory(), {"holds": []})[0][0]
    old = row["source"]
    metadata = FileMetadata(name=old["name"], id=old["id"], rev="def123456" if changed=="revision" else old["rev"], size=old["size"], content_hash=old["content_hash"], client_modified=datetime(2026, 1, 1), server_modified=datetime(2026, 1, 1), path_display=row["destination_path"] if changed=="path" else old["path"], has_explicit_shared_members=False)
    parent = FolderMetadata(name="White In Situ", id="leaf", path_display=str(r.PurePosixPath(old["path"]).parent))
    api = SimpleNamespace(read=lambda *a,**k: metadata, metadata=lambda p: parent if p=="leaf" else (metadata if changed=="destination" else None))
    if changed == "none":
        assert r.unchanged_after_rejection(api, row)["destination_absent"]
    else:
        with pytest.raises(r.w.Hold):
            r.unchanged_after_rejection(api, row)
