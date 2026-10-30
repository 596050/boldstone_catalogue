from copy import deepcopy

import audit_conversion as audit


def inventory():
    root = audit.worker.ROOT_PATH
    rows = [
        {"id": audit.worker.ROOT_ID, "kind": "folder", "path": root, "name": "01 Wall Sculptures"},
        {"id": "family", "kind": "folder", "path": root + "/Family", "name": "Family"},
        {"id": "leaf", "kind": "folder", "path": root + "/FAMILY/Leaf", "name": "Leaf"},
        {"id": "source", "kind": "file", "path": root + "/FAMILY/LEAF/Image.BMP", "name": "Image.BMP",
         "size": 123, "client_modified": "2026-10-01T00:00:00Z", "server_modified": "2026-10-01T00:00:00Z"},
    ]
    return {r["id"]: {**r, "path_lower": r["path"].lower()} for r in rows}


def test_ancestor_display_aliases_resolve_from_current_names_and_ids():
    entries = audit.normalize_paths(inventory())
    by_id = {r["id"]: r for r in entries}
    assert len(entries) == 3
    assert audit.worker.ROOT_ID not in by_id
    assert by_id["source"]["path"] == audit.worker.ROOT_PATH + "/Family/Leaf/Image.BMP"
    assert by_id["source"]["parent_id"] == "leaf"
    assert by_id["leaf"]["parent_id"] == "family"
    assert by_id["source"]["ancestor_display_alias"] is True


def test_actual_case_only_folder_rename_is_not_hidden():
    initial = {"entries": audit.normalize_paths(inventory())}
    changed = deepcopy(inventory())
    changed["family"]["name"] = "FAMILY"
    current = {"entries": audit.normalize_paths(changed)}
    failures = audit.compare_census(initial, current, [])
    assert {f["id"] for f in failures if f["reason"] == "ORIGINAL_ENTRY_KIND_OR_PATH_CHANGED"} == {
        "family", "leaf", "source"}
