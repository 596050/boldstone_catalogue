import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import realign_filenames as a


def inventory():
    root = a.w.ROOT_ID
    family = {"id": "family", "kind": "folder", "name": "Example", "path": a.w.ROOT_PATH + "/Example", "parent_id": root}
    parent = {"id": "parent", "kind": "folder", "name": "New label", "path": family["path"] + "/New label", "parent_id": "family"}
    def file(identifier, name):
        return {"id": identifier, "kind": "file", "name": name, "path": parent["path"] + "/" + name,
                "parent_id": "parent", "rev": "revision", "size": 7, "content_hash": "bytes"}
    return {"entries": [family, parent, file("existing", "example__new-label__001.JPG"), file("moved", "example__old-label__001.JPG"), file("other", "example__old-label__007.jpg")]}


def test_preserves_existing_names_and_resolves_moved_numeric_collision():
    rows, batches = a.build_rows(inventory(), {"holds": []})
    by_id = {r["source"]["id"]: r for r in rows}
    assert by_id["existing"]["operation"] == "NOOP"
    assert by_id["moved"]["destination_name"] == "example__new-label__002.JPG"
    assert by_id["other"]["destination_name"] == "example__new-label__007.jpg"
    assert len(batches) == 1 and set(batches[0]["file_ids"]) == {"moved", "other"}


def test_historical_hold_on_live_id_prevents_any_plan():
    with pytest.raises(a.w.Hold, match="LIVE_HOLD"):
        a.build_rows(inventory(), {"holds": [{"asset_id": "moved"}]})


def test_unknown_filename_cannot_be_guessed():
    value = inventory()
    value["entries"][-1]["name"] = "no sequence.jpg"
    with pytest.raises(a.w.Hold, match="ORIGINAL_NUMBER_MISSING"):
        a.build_rows(value, {"holds": []})


def test_ambiguous_submission_keeps_intent_and_does_not_retry(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    monkeypatch.setattr(a, "MANIFEST", manifest)
    monkeypatch.setattr(a.w, "BUDGET", SimpleNamespace(wait=lambda: None))
    calls = []
    def submit(*args, **kwargs):
        calls.append(1)
        raise TimeoutError()
    api = SimpleNamespace(client=SimpleNamespace(files_move_batch_v2=submit))
    rows, _ = a.build_rows(inventory(), {"holds": []})
    for row in rows:
        row["source"]["id"] = "id:" + row["source"]["id"]
    directory = tmp_path / "batch"
    with pytest.raises(a.w.Hold, match="RECONCILIATION"):
        a.batch_move(api, "test-app", [r for r in rows if r["operation"] == "RENAME"], directory)
    assert len(calls) == 1
    assert (directory / "intent.json").exists()
    assert json.loads((directory / "submission-error.json").read_text())["automatic_retry"] is False
    assert not (directory / "verified.json").exists()


def test_async_job_is_polled_without_repeating_the_move(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    monkeypatch.setattr(a, "MANIFEST", manifest)
    monkeypatch.setattr(a.w, "BUDGET", SimpleNamespace(wait=lambda: None))
    monkeypatch.setattr(a.time, "sleep", lambda _: None)
    calls = []
    launch = SimpleNamespace(is_async_job_id=lambda: True, get_async_job_id=lambda: "job-1")
    complete = SimpleNamespace(is_complete=lambda: True, get_complete=lambda: "terminal-result")
    api = SimpleNamespace(client=SimpleNamespace(files_move_batch_v2=lambda *args, **kwargs: calls.append("move") or launch),
                          read=lambda method, job: calls.append((method, job)) or complete)
    monkeypatch.setattr(a.r, "terminal_rows", lambda result, rows: ([{"source_id": "moved", "tag": "success"}], False))
    rows, _ = a.build_rows(inventory(), {"holds": []})
    for row in rows:
        row["source"]["id"] = "id:" + row["source"]["id"]
    directory = tmp_path / "batch"
    a.batch_move(api, "test-app", [r for r in rows if r["operation"] == "RENAME"], directory)
    assert calls == ["move", ("files_move_batch_check_v2", "job-1")]
    assert json.loads((directory / "launch.json").read_text())["async_job_id"] == "job-1"
