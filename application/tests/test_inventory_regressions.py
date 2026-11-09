from copy import deepcopy

import pytest

from boldstone.census import _ingest, census
from boldstone.dropbox_adapter import Page
from boldstone.errors import IntegrityError


@pytest.mark.parametrize("resume", [False, True])
def test_inventory_cursor_cycles_are_blocked_including_after_resume(scoped, monkeypatch, resume):
    state, run, scope, _ = scoped
    calls = []

    def listing(reference, **kwargs):
        cursor = kwargs.get("cursor")
        calls.append(cursor)
        assert len(calls) <= 3, "Inventory loop must stop when any cursor repeats"
        next_cursor = "cursor-b" if cursor == "cursor-a" else "cursor-a"
        return Page([], next_cursor, True, {"entries": [], "cursor": next_cursor, "has_more": True})

    monkeypatch.setattr(scope.adapter, "list_folder", listing)
    if resume:
        partial = census(state, run, scope, max_pages=2)
        kwargs = {"resume": partial["scan_id"]}
    else:
        kwargs = {}
    with pytest.raises(IntegrityError, match="pagination made no progress"):
        census(state, run, scope, **kwargs)
    assert len(calls) == 3
    assert state.conn.execute("SELECT state FROM scan_details").fetchone()[0] == "FAILED_READ"


def test_folder_move_does_not_modify_another_confirmed_scope(scoped):
    state, run, scope, fake = scoped
    result = census(state, run, scope)
    with state.conn:
        state.conn.execute(
            """INSERT INTO current_assets SELECT 'id:OTHER', namespace_id, 'other-account',
            root_folder_id, path_lower, path_display, parent_folder_id, revision, content_hash,
            byte_size, kind, status, latest_scan_id, metadata_json, updated_utc
            FROM current_assets WHERE asset_id='id:A'"""
        )
        moved = deepcopy(fake.backend["metadata"]["id:FOLDER"])
        moved.update(path_lower="/library/renamed", path_display="/Library/Renamed")
        _ingest(state, run, result["scan_id"], moved, incremental=True)
    rows = {
        row["asset_id"]: row
        for row in state.conn.execute("SELECT * FROM current_assets WHERE kind='file'")
    }
    assert rows["id:A"]["path_lower"].startswith("/library/renamed/")
    assert rows["id:OTHER"]["path_lower"].startswith("/library/family/")
    assert rows["id:OTHER"]["status"] == "present"
