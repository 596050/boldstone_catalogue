"""Read-only retirement checks, kept separate from the additive conversion ledger."""
from __future__ import annotations

import collections
import fcntl
import hashlib
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import audit_conversion as audit
import convert_bmps as w
from dropbox.files import (
    DeletedMetadata,
    FileMetadata,
    FolderMetadata,
    ListRevisionsMode,
)

CHECKS = w.RUNTIME / "retirement-checks"
LOCAL = threading.local()


def tag(value):
    return value._tag if value is not None else None


def reference(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def link_record(link):
    permissions = link.link_permissions
    return {"type": type(link).__name__, "id": link.id, "path_lower": link.path_lower,
            "name": link.name, "url_sha256": hashlib.sha256(link.url.encode()).hexdigest(),
            "resolved_visibility": tag(permissions.resolved_visibility),
            "effective_audience": tag(permissions.effective_audience),
            "link_access_level": tag(permissions.link_access_level),
            "expires": link.expires.isoformat() if link.expires else None}


def all_links(api):
    result = api.read("sharing_list_shared_links")
    links, cursors, pages = [], set(), 0
    while True:
        pages += 1
        links.extend(link_record(link) for link in result.links)
        if not result.has_more:
            break
        if not result.cursor or result.cursor in cursors:
            raise w.SetupError("Incomplete sharing pagination")
        cursors.add(result.cursor)
        result = api.read("sharing_list_shared_links", cursor=result.cursor)
    return {"recorded_utc": w.now(), "pages": pages, "pagination_exhausted": True,
            "scope": "All links of the authorized account; not a universal proof for other accounts.",
            "links": links}


def sharing_flags(item):
    sharing = item.sharing_info
    return {"has_explicit_shared_members": item.has_explicit_shared_members,
            "sharing_info_present": sharing is not None,
            "read_only": sharing.read_only if sharing else False,
            "parent_shared_folder_id": sharing.parent_shared_folder_id if sharing else None,
            "file_lock_present": item.file_lock_info is not None}


def census(api):
    entries, pages = {}, 0
    cursors = set()
    result = api.read("files_list_folder", w.ROOT_ID, recursive=True, limit=2000,
                      include_has_explicit_shared_members=True, include_deleted=False)
    while True:
        pages += 1
        for item in result.entries:
            if isinstance(item, DeletedMetadata):
                raise w.SetupError("Library changed during retirement census")
            if isinstance(item, FileMetadata):
                row = {"kind": "file", **w.head(item), **sharing_flags(item)}
            elif isinstance(item, FolderMetadata):
                row = {"kind": "folder", "id": item.id, "path": item.path_display,
                       "sharing_info_present": item.sharing_info is not None}
            else:
                raise w.SetupError("Unexpected census metadata")
            row.update(name=item.name, path_lower=item.path_lower)
            entries[item.id] = row
        print(f"Retirement census: {len(entries)} entries / {pages} pages", flush=True)
        if not result.has_more:
            break
        if not isinstance(result.cursor, str) or not result.cursor or result.cursor in cursors:
            raise w.SetupError("Incomplete retirement census pagination")
        cursors.add(result.cursor)
        result = api.read("files_list_folder_continue", result.cursor)
    root = api.metadata(w.ROOT_ID)
    if not isinstance(root, FolderMetadata):
        raise w.SetupError("Root changed type")
    entries[root.id] = {"kind": "folder", "id": root.id, "path": root.path_display,
                        "name": root.name, "path_lower": root.path_lower}
    return {"recorded_utc": w.now(), "root_id": w.ROOT_ID, "namespace_id": w.NAMESPACE_ID,
            "pagination_exhausted": True, "pages": pages,
            "entries": audit.normalize_paths(entries)}


def database_controls():
    db = Path.home() / "Library/Application Support/BoldstoneLocal/state/boldstone-state.sqlite3"
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return {"path": str(db), "recorded_utc": w.now(),
                "protections": [dict(r) for r in connection.execute("SELECT * FROM protections")],
                "holds": [dict(r) for r in connection.execute("SELECT * FROM holds WHERE active=1")],
                "lineage": [dict(r) for r in connection.execute("SELECT * FROM lineage")]}


def check_one(row, live, links, controls, grant):
    if not hasattr(LOCAL, "api"):
        LOCAL.api = w.API(grant)
    api = LOCAL.api
    state = w.saved_state(row)
    record = {"source_id": row["source_id"], "source_path": row["source_path"],
              "destination_path": row["destination_path"], "checked_utc": w.now(), "holds": []}
    try:
        if state.get("state") not in audit.COMPLETE:
            raise w.Hold("CONVERSION_NOT_VERIFIED")
        record["local_verification"] = audit.inspect_local(row, state)
        record["holds"].extend(record["local_verification"]["failures"])
        source, output = live.get(row["source_id"], {}), live.get(state["output_head"]["id"], {})
        for item, expected, path, kind in ((source, state["source_head"], row["source_path"], "SOURCE"),
                                           (output, state["output_head"], row["destination_path"], "JPEG")):
            if item.get("kind") != "file" or any(item.get(k) != expected[k] for k in ("id", "rev", "size", "content_hash")):
                record["holds"].append(kind + "_CHANGED_SINCE_CONVERSION")
            if item.get("path") != path or item.get("parent_id") != row["parent_id"]:
                record["holds"].append(kind + "_LOCATION_CHANGED")
        record["source_head"] = source
        record["output_head"] = output
        record["direct_links"] = [link for link in links["links"] if link["id"] == row["source_id"]]
        record["ancestor_links"] = [link for link in links["links"] if link["type"] == "FolderLinkMetadata"
                                    and row["source_path"].casefold().startswith(link["path_lower"] + "/")]
        # A no_one/only_you link grants no access. With no direct or inherited members,
        # it is an owner navigation link, not a public distribution URL.
        if source.get("has_explicit_shared_members") is not False or source.get("sharing_info_present"):
            record["holds"].append("EXTERNAL_OR_UNKNOWN_MEMBERSHIP")
        if source.get("read_only") or source.get("file_lock_present"):
            record["holds"].append("READ_ONLY_OR_LOCKED")
        if any(link["resolved_visibility"] not in ("no_one", "only_you")
               or link["effective_audience"] not in ("no_one", None)
               for link in record["direct_links"]):
            record["holds"].append("ACTIVE_OR_UNKNOWN_DIRECT_LINK")
        for name, values in (("PROTECTED_ID", controls["protections"]), ("ACTIVE_HOLD", controls["holds"])):
            if any(r["asset_id"] == row["source_id"] for r in values):
                record["holds"].append(name)
        if any(row["source_id"] in (r["from_asset_id"], r["to_asset_id"]) for r in controls["lineage"]):
            record["holds"].append("EXISTING_LINEAGE_DEPENDENCY")
        history = api.read("files_list_revisions", row["source_id"], mode=ListRevisionsMode.id,
                           limit=100, include_restorable_info=True)
        record["available_history"] = {"mode": "id", "limit": 100,
                                       "retention_boundary": "Only revisions currently available from Dropbox.",
                                       "is_deleted": history.is_deleted,
                                       "entries": [w.head(m) for m in history.entries]}
        if history.is_deleted or not history.entries or len(history.entries) >= 100:
            record["holds"].append("HISTORY_INCOMPLETE_OR_DELETED")
        elif any(m.id != row["source_id"] for m in history.entries):
            record["holds"].append("HISTORY_ID_MISMATCH")
        elif history.entries[0].rev != state["source_head"]["rev"]:
            record["holds"].append("SOURCE_REVISION_CHANGED_DURING_CHECK")
        unique_history = {(m.content_hash, m.size) for m in history.entries}
        record["available_history_unique_contents"] = len(unique_history)
        if unique_history != {(state["backup"]["content_hash"], state["backup"]["size"])}:
            record["holds"].append("UNIQUE_OLDER_CONTENT_NEEDS_BACKUP")
    except w.Hold as error:
        record["holds"].append(str(error))
    except Exception as error:  # noqa: BLE001 -- Never record credentials or exception text.
        record["holds"].append("CHECK_ERROR_" + type(error).__name__)
    record["status"] = "CHECKS_PASSED_PENDING_PUBLICATION_AND_ARCHIVE" if not record["holds"] else "HELD"
    w.private_json(CHECKS / "rows" / (hashlib.sha256(row["source_id"].encode()).hexdigest() + ".json"), record)
    return record


def main():
    os.umask(0o077)
    CHECKS.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (w.RUN_PATH / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = json.loads(w.PLAN_PATH.read_text())
        w.validate_plan(plan)
        completion = json.loads((w.RUNTIME / "conversion-completion.json").read_text())
        if completion["status"] != "PASS":
            raise w.SetupError("Conversion final audit did not pass")
        grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
        identity = w.verify_grant(grant)
        api = w.API(grant)
        try:
            current = census(api)
            links = all_links(api)
        finally:
            api.close()
        w.private_json(CHECKS / "pre-deletion-census.json", current)
        w.private_json(CHECKS / "all-owned-links.json", links)
        controls = database_controls()
        w.private_json(CHECKS / "database-controls.json", controls)
        live = {r["id"]: r for r in current["entries"]}
        rows = [r for r in plan["rows"] if r["status"] == "ELIGIBLE"]
        records = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(check_one, r, live, links, controls, grant) for r in rows]
            for future in as_completed(futures):
                records.append(future.result())
                if len(records) % 20 == 0 or len(records) == len(rows):
                    print(f"Checked {len(records)}/{len(rows)}; holds: "
                          f"{dict(collections.Counter(h for r in records for h in r['holds']))}", flush=True)
        records.sort(key=lambda r: r["source_path"].casefold())
        original = json.loads(Path(plan["evidence"]["census"]["path"]).read_text())
        census_failures = audit.compare_census(original, current,
                                              [r["local_verification"] for r in records if "local_verification" in r])
        report = {"schema": "boldstone-bmp-retirement-read-only-checks-v1", "completed_utc": w.now(),
                  "identity": identity, "plan": reference(w.PLAN_PATH),
                  "census": reference(CHECKS / "pre-deletion-census.json"),
                  "links": reference(CHECKS / "all-owned-links.json"),
                  "database_controls": reference(CHECKS / "database-controls.json"),
                  "census_failures": census_failures, "records": records,
                  "counts": dict(collections.Counter(r["status"] for r in records)),
                  "hold_reasons": dict(collections.Counter(h for r in records for h in r["holds"])),
                  "remote_mutations": 0}
        w.private_json(CHECKS / "checks.json", report)
        print(json.dumps({k: report[k] for k in ("counts", "hold_reasons", "census_failures")}, indent=2))
        return 0 if not census_failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 -- Do not log secrets.
        print("Read-only checks stopped: " + type(error).__name__, flush=True)
        raise SystemExit(1) from None
