"""Rename the current Wall Sculptures files from their existing parent paths.

Native ID-preserving moves only. Frozen manifests, <=25-entry jobs, complete
parent readbacks, durable intent/job receipts, and no ambiguous write retries.
"""
from __future__ import annotations

import argparse
import collections
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import threading
import time
import unicodedata

import convert_bmps as w
from check_bmp_retirement import census, link_record, reference, sharing_flags
from dropbox.files import FileMetadata, FolderMetadata
from retire_bmps import RetirementBudget, read_reference

RUN = w.RUNTIME / "path-renaming-20261016"
DELIVERY = Path.home() / "BoldstoneMigration/path-renaming-20261016"
MANIFEST = RUN / "manifest.json"
WAIVER = Path.home() / "Library/Application Support/BoldstoneFlatMigration/flat-20261015/evidence/operator-policy-no-backup-downloads-v2.json"
FIELDS = ("id", "size", "content_hash", "has_explicit_shared_members", "sharing_info_present", "read_only", "parent_shared_folder_id", "file_lock_present")


def slug(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    result = re.sub(r"[^a-z0-9]+", "-", value.replace("&", " and ")).strip("-")
    if not result:
        raise w.Hold("EMPTY_FOLDER_SLUG")
    return result


def write_once(path, payload):
    if path.exists():
        if json.loads(path.read_text()) != payload:
            raise w.SetupError("IMMUTABLE_ARTIFACT_ALREADY_EXISTS")
    else:
        w.private_json(path, payload)
    return reference(path)


def event(kind, **data):
    record = {"recorded_utc": w.now(), "kind": kind, **data}
    fd = os.open(RUN / "events.jsonl", os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def build_rows(inventory, controls):
    entries = {e["id"]: e for e in inventory["entries"]}
    held = {e["asset_id"] for e in controls["holds"]}
    grouped = collections.defaultdict(list)
    for item in entries.values():
        if item["kind"] == "file":
            if item["id"] in held:
                raise w.Hold("LIVE_FILE_HAS_HISTORICAL_AUTHORITY_HOLD")
            if not item.get("content_hash") or not item.get("rev"):
                raise w.Hold("FILE_HASH_OR_REVISION_UNAVAILABLE")
            if any(item.get(k) for k in ("has_explicit_shared_members", "sharing_info_present", "read_only", "file_lock_present")):
                raise w.Hold("SHARED_OR_LOCKED_FILE_REQUIRES_REVIEW")
            grouped[item["parent_id"]].append(item)
    rows, batches = [], []
    for parent_id in sorted(grouped, key=lambda i: entries[i]["path"].casefold()):
        parent = entries[parent_id]
        family = entries[parent["parent_id"]]
        if family.get("parent_id") != w.ROOT_ID:
            raise w.Hold("UNEXPECTED_FOLDER_DEPTH")
        group_rows = []
        for number, source in enumerate(sorted(grouped[parent_id], key=lambda r: (r["name"].casefold(), r["name"], r["id"])), 1):
            extension = PurePosixPath(source["name"]).suffix
            name = f"{slug(family['name'])}__{slug(parent['name'])}__{number:03d}{extension}"
            path = parent["path"] + "/" + name
            if len(name.encode()) > 255 or len(path) > 255:
                raise w.Hold("PROPOSED_NAME_EXCEEDS_LOCAL_PORTABILITY_LIMIT")
            if path != source["path"] and path.casefold() == source["path"].casefold():
                raise w.Hold("CASE_ONLY_RENAME_NEEDS_EXPLICIT_TWO_STEP_MANIFEST")
            row = {"source": source, "parent_id": parent_id, "family_id": family["id"],
                   "destination_path": path, "destination_name": name, "extension": extension,
                   "naming_basis": "Current directory labels; no new visual identity assertion",
                   "operation": "NOOP" if path == source["path"] else "RENAME"}
            rows.append(row)
            if row["operation"] == "RENAME":
                group_rows.append(row)
        for offset in range(0, len(group_rows), 25):
            batches.append({"batch_id": f"PATH-NAME-{len(batches)+1:04d}", "parent_id": parent_id,
                            "family_id": family["id"], "file_ids": [r["source"]["id"] for r in group_rows[offset:offset+25]]})
    occupied = {e["path"].casefold(): e["id"] for e in entries.values()}
    targets = {}
    for row in rows:
        target, identifier = row["destination_path"].casefold(), row["source"]["id"]
        if target in targets or occupied.get(target, identifier) != identifier:
            raise w.Hold("DESTINATION_COLLISION")
        targets[target] = identifier
    return rows, batches


def prepare():
    if MANIFEST.exists():
        raise w.SetupError("MANIFEST_ALREADY_PREPARED")
    inventory = json.loads((RUN / "inventory.json").read_text())
    controls = json.loads((RUN / "controls.json").read_text())
    rows, batches = build_rows(inventory, controls)
    waiver = json.loads(WAIVER.read_text())
    if waiver["scope"] != "NATIVE_MOVE_ONLY_NO_CONTENT_CHANGE" or waiver["backup_downloads_required"]:
        raise w.SetupError("MOVE_ONLY_BACKUP_POLICY_NOT_APPLICABLE")
    manifest = {"schema": "boldstone-path-filenames-v1", "prepared_utc": w.now(),
                "root_id": w.ROOT_ID, "root_path": w.ROOT_PATH, "namespace_id": w.NAMESPACE_ID,
                "user_instruction": "Can you now rename every file according to the dir path?",
                "authority": "Direct user instruction authorizes this filename-only work; exact names are implementation-derived, not a separately user-reviewed checksum.",
                "naming_rule": "family-slug__immediate-folder-slug__NNN + original extension; number by original filename then stable ID within parent",
                "source_name_preservation": "Complete original names and stable IDs retained in this manifest and reversal mapping",
                "inventory": reference(RUN / "inventory.json"), "controls": reference(RUN / "controls.json"),
                "sharing_snapshot": reference(RUN / "links.json"), "backup_download_waiver": reference(WAIVER),
                "rows": rows, "batches": batches, "file_count": len(rows), "batch_count": len(batches)}
    write_once(MANIFEST, manifest)
    DELIVERY.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_once(DELIVERY / "RENAME-PLAN.json", manifest)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["file_id", "original_path", "new_path", "original_revision", "bytes", "dropbox_content_hash", "parent_id"])
    for row in rows:
        s = row["source"]
        writer.writerow([s["id"], s["path"], row["destination_path"], s["rev"], s["size"], s["content_hash"], row["parent_id"]])
    path = DELIVERY / "OLD-AND-NEW-NAMES.csv"
    path.write_text(output.getvalue())
    path.chmod(0o600)
    write_once(DELIVERY / "REVERSAL-MAP.json", {"note": "Reference only; rollback requires fresh guards and separate execution, never blind replay", "manifest": reference(MANIFEST), "rows": [{"file_id": r["source"]["id"], "from": r["destination_path"], "to": r["source"]["path"], "content_hash": r["source"]["content_hash"], "size": r["source"]["size"]} for r in rows]})
    print(json.dumps({"status": "PREPARED", "files": len(rows), "batches": len(batches), "manifest": reference(MANIFEST), "mapping": str(path)}), flush=True)


def native_row(metadata, parent):
    if not isinstance(metadata, FileMetadata):
        raise w.Hold("UNEXPECTED_NON_FILE_IN_LEAF")
    canonical = parent["path"] + "/" + metadata.name
    if not w.path_equal(metadata.path_display, canonical):
        raise w.Hold("FILE_OUTSIDE_BOUND_PARENT")
    return {"kind": "file", **w.head(metadata), **sharing_flags(metadata), "name": metadata.name,
            "path": canonical, "path_lower": metadata.path_lower, "parent_id": parent["id"]}


def folder_listing(api, parent):
    metadata = api.metadata(parent["id"])
    if not isinstance(metadata, FolderMetadata) or metadata.id != parent["id"] or metadata.name != parent["name"] or not w.path_equal(metadata.path_display, parent["path"]):
        raise w.Hold("PARENT_FOLDER_ID_NAME_OR_PATH_CHANGED")
    if (metadata.sharing_info is not None) != parent.get("sharing_info_present", False):
        raise w.Hold("PARENT_SHARING_CHANGED")
    page = api.read("files_list_folder", parent["id"], recursive=False, limit=2000, include_deleted=False, include_has_explicit_shared_members=True)
    result, cursors = {}, set()
    while True:
        for item in page.entries:
            row = native_row(item, parent)
            if row["id"] in result:
                raise w.Hold("DUPLICATE_ID_IN_PARENT_LISTING")
            result[row["id"]] = row
        if not page.has_more:
            return result
        if page.cursor in cursors:
            raise w.Hold("INCOMPLETE_PARENT_PAGINATION")
        cursors.add(page.cursor)
        page = api.read("files_list_folder_continue", page.cursor)


def compare_parent(expected, actual, destinations=None):
    destinations = destinations or {}
    if set(expected) != set(actual):
        raise w.Hold("PARENT_MEMBERSHIP_CHANGED")
    for identifier, old in expected.items():
        new = actual[identifier]
        for field in FIELDS:
            if old.get(field) != new.get(field):
                raise w.Hold("FILE_CONTENT_OR_ACCESS_CHANGED_" + field.upper())
        path = destinations.get(identifier, old["path"])
        if new["path"] != path or new["name"] != PurePosixPath(path).name:
            raise w.Hold("FILE_DESTINATION_OR_SIBLING_NAME_CHANGED")
        if new.get("parent_id") != old.get("parent_id"):
            raise w.Hold("FILE_PARENT_CHANGED")
        if identifier not in destinations and new["rev"] != old["rev"]:
            raise w.Hold("UNRENAMED_FILE_REVISION_CHANGED")
        if PurePosixPath(new["name"]).suffix != PurePosixPath(old["name"]).suffix:
            raise w.Hold("FILE_EXTENSION_CHANGED")


def terminal_rows(result, rows):
    if len(result.entries) != len(rows):
        raise w.Hold("NATIVE_BATCH_RESULT_COUNT_MISMATCH")
    records, failed = [], False
    for outcome, row in zip(result.entries, rows, strict=True):
        record = {"source_id": row["source"]["id"], "tag": outcome._tag}
        if outcome.is_success():
            metadata = outcome.get_success()
            record["metadata"] = w.head(metadata)
            if metadata.id != row["source"]["id"] or not w.path_equal(metadata.path_display, row["destination_path"]) or metadata.name != row["destination_name"]:
                failed = True
        else:
            failed = True
            if outcome.is_failure():
                record["failure_tag"] = outcome.get_failure()._tag
        records.append(record)
    return records, failed


def move_individuals(api, child_rows, directory, pool=None, api_factory=None):
    """Bounded independent native calls; stop scheduling on any uncertainty."""
    stop = threading.Event()

    def move_one(index, row):
        if stop.is_set():
            raise w.Hold("PEER_WRITE_FAILED")
        client = api_factory() if api_factory else api
        request = {"from_path": row["source"]["id"], "to_path": row["destination_path"],
                   "autorename": False, "allow_ownership_transfer": False}
        write_once(directory / f"file-{index:03d}-intent.json", {"recorded_utc": w.now(), "request": request})
        for attempt in range(4):
            w.BUDGET.wait()
            if stop.is_set():
                raise w.Hold("PEER_WRITE_FAILED_BEFORE_SUBMISSION")
            try:
                outcome = client.client.files_move_v2(**request)
                break
            except w.RateLimitError as error:
                reason = getattr(getattr(error.error, "reason", None), "_tag", None)
                prefix = f"file-{index:03d}" + (f"-retry-{attempt:03d}" if attempt else "")
                write_once(directory / (prefix + "-error.json"), {"recorded_utc": w.now(), "http_status": 429,
                           "reason": reason, "retry_after": error.backoff, "request_id": error.request_id})
                if pool is not None or attempt == 3 or reason not in {"too_many_write_operations", "too_many_requests"}:
                    raise
                delay = max(2 ** (attempt + 1), error.backoff or 0)
                while delay > 0:
                    interval = min(30, delay)
                    if stop.wait(interval):
                        raise w.Hold("RUN_STOPPED_DURING_BACKOFF")
                    delay -= interval
                proof = unchanged_after_rejection(client, row)
                write_once(directory / f"file-{index:03d}-retry-{attempt+1:03d}-intent.json", {"recorded_utc": w.now(),
                           "request": request, "reason": "Explicit 429 rejection; fresh source and empty destination verified", "preflight": proof})
        head = w.head(outcome.metadata)
        write_once(directory / f"file-{index:03d}-receipt.json", {"recorded_utc": w.now(), "metadata": head})
        if any(head[k] != row["source"][k] for k in ("id", "size", "content_hash")):
            raise w.Hold("NATIVE_MOVE_CONTENT_OR_ID_CHANGED")
        if not w.path_equal(head["path"], row["destination_path"]) or outcome.metadata.name != row["destination_name"]:
            raise w.Hold("NATIVE_MOVE_DESTINATION_MISMATCH")
        return {"source_id": row["source"]["id"], "tag": "success", "metadata": head}

    if pool is None:
        return [move_one(i, row) for i, row in enumerate(child_rows, 1)]
    pending, results, remaining = {}, {}, iter(enumerate(child_rows, 1))
    def schedule():
        item = next(remaining, None)
        if item is not None:
            i, row = item
            pending[pool.submit(move_one, i, row)] = i
    schedule()
    schedule()
    while pending:
        finished, _ = wait(pending, return_when=FIRST_COMPLETED)
        failure = None
        for future in finished:
            index = pending.pop(future)
            try:
                results[index] = future.result()
            except Exception as error:
                stop.set()
                failure = error
        if failure is not None:
            wait(pending)
            for future in pending:
                try:
                    future.result()
                except Exception:
                    pass
            raise failure
        for _ in finished:
            schedule()
    return [results[i] for i in range(1, len(child_rows) + 1)]


def unchanged_after_rejection(api, row):
    """Permit a new attempt only after a definite 429 and unchanged readback."""
    source = api.read("files_get_metadata", row["source"]["id"], include_has_explicit_shared_members=True)
    current = w.head(source)
    if any(current[k] != row["source"][k] for k in ("id", "rev", "size", "content_hash")):
        raise w.Hold("REJECTED_WRITE_SOURCE_CHANGED")
    if not w.path_equal(current["path"], row["source"]["path"]) or source.name != row["source"]["name"]:
        raise w.Hold("REJECTED_WRITE_SOURCE_MOVED")
    flags = sharing_flags(source)
    if any(flags.get(k) != row["source"].get(k) for k in flags):
        raise w.Hold("REJECTED_WRITE_SOURCE_ACCESS_CHANGED")
    parent = api.metadata(row["parent_id"])
    if not isinstance(parent, FolderMetadata) or parent.id != row["parent_id"] or not w.path_equal(parent.path_display, str(PurePosixPath(row["source"]["path"]).parent)):
        raise w.Hold("REJECTED_WRITE_PARENT_CHANGED")
    if api.metadata(row["destination_path"]) is not None:
        raise w.Hold("REJECTED_WRITE_DESTINATION_OCCUPIED")
    return {"source": current, "source_access": flags, "parent_id": parent.id, "destination_absent": True}


def get_owned_urls(api):
    result = api.read("sharing_list_shared_links")
    records, cursors = [], set()
    while True:
        records.extend({"url": l.url, "record": link_record(l)} for l in result.links)
        if not result.has_more:
            return records
        if not result.cursor or result.cursor in cursors:
            raise w.Hold("SHARED_LINK_PAGINATION_FAILED")
        cursors.add(result.cursor)
        result = api.read("sharing_list_shared_links", cursor=result.cursor)


def check_full(initial, final, destinations=None):
    destinations = destinations or {}
    before = {e["id"]: e for e in initial["entries"]}
    after = {e["id"]: e for e in final["entries"]}
    if set(before) != set(after):
        raise w.Hold("LIBRARY_MEMBERSHIP_CHANGED")
    compare_parent({i:r for i,r in before.items() if r["kind"]=="file"}, {i:r for i,r in after.items() if r["kind"]=="file"}, destinations)
    for identifier, old in before.items():
        if old["kind"] == "folder":
            for key in ("kind", "name", "path", "parent_id", "sharing_info_present"):
                if old.get(key) != after[identifier].get(key):
                    raise w.Hold("FOLDER_CHANGED")


def manifest_versions(path):
    current = json.loads(path.read_text())
    versions = {reference(path)["sha256"]: current}
    while current.get("previous_manifest"):
        ref = current["previous_manifest"]
        if ref["sha256"] in versions:
            raise w.SetupError("MANIFEST_HISTORY_CYCLE")
        current = read_reference(ref)
        versions[ref["sha256"]] = current
    return versions


def execute(api, manifest_hash, pool=None, api_factory=None):
    if reference(MANIFEST)["sha256"] != manifest_hash:
        raise w.SetupError("MANIFEST_HASH_MISMATCH")
    manifest = json.loads(MANIFEST.read_text())
    versions = manifest_versions(MANIFEST)
    baseline = read_reference(manifest["inventory"])
    read_reference(manifest["controls"])
    read_reference(manifest["backup_download_waiver"])
    entries = {e["id"]: e for e in baseline["entries"]}
    rows = {r["source"]["id"]: r for r in manifest["rows"]}
    batches = manifest["batches"]
    if (RUN / "COMPLETION.json").exists():
        raise w.SetupError("RUN_ALREADY_COMPLETE")
    expected = {i:e for i,e in entries.items() if e["kind"] == "file"}
    verified, completed_batches = 0, 0
    for batch in batches:
        directory = RUN / "batches" / batch["batch_id"]
        done = directory / "verified.json"
        if done.exists():
            receipt = json.loads(done.read_text())
            if receipt["manifest_sha256"] != manifest_hash:
                prior = versions.get(receipt["manifest_sha256"])
                if prior is None:
                    raise w.SetupError("SAVED_RECEIPT_MANIFEST_MISMATCH")
                prior_rows = {r["source"]["id"]: r for r in prior["rows"]}
                prior_batch = next((b for b in prior["batches"] if b["batch_id"] == batch["batch_id"]), None)
                if prior_batch != batch or any(prior_rows[i] != rows[i] for i in batch["file_ids"]):
                    raise w.SetupError("AMENDMENT_ALTERS_ALREADY_COMPLETED_OPERATION")
            post = read_reference(receipt["post_readback"])
            expected.update(post["entries"])
            verified += len(batch["file_ids"])
            completed_batches += 1
        elif (directory / "intent.json").exists():
            raise w.Hold("UNFINISHED_BATCH_REQUIRES_READ_ONLY_RECONCILIATION")
    initial = census(api)
    initial_expected = {**baseline, "entries": [expected.get(e["id"], e) for e in baseline["entries"]]}
    check_full(initial_expected, initial)
    initial_ref = write_once(RUN / f"pre-execution-{completed_batches:04d}.json", initial)
    urls_path = RUN / "private-original-link-urls.json"
    if not urls_path.exists():
        urls = get_owned_urls(api)
        write_once(urls_path, urls)
        frozen_links = read_reference(manifest["sharing_snapshot"])["links"]
        if sorted([u["record"] for u in urls], key=lambda r:r["url_sha256"]) != sorted(frozen_links, key=lambda r:r["url_sha256"]):
            raise w.Hold("SHARING_CHANGED_SINCE_PLANNING")
    event("EXECUTION_STARTED", manifest_sha256=manifest_hash, initial_census=initial_ref, already_verified=verified)
    for batch in batches:
        directory = RUN / "batches" / batch["batch_id"]
        if (directory / "verified.json").exists():
            continue
        if (RUN / "STOP_AFTER_CHECKPOINT").exists():
            raise w.Hold("CHECKPOINT_STOP_REQUESTED")
        parent = entries[batch["parent_id"]]
        family = entries[batch["family_id"]]
        fm = api.metadata(family["id"])
        if not isinstance(fm, FolderMetadata) or fm.id != family["id"] or fm.name != family["name"] or not w.path_equal(fm.path_display, family["path"]):
            raise w.Hold("FAMILY_FOLDER_CHANGED")
        sibling_expected = {i:e for i,e in expected.items() if e["parent_id"] == parent["id"]}
        before = folder_listing(api, parent)
        compare_parent(sibling_expected, before)
        child_rows = [rows[i] for i in batch["file_ids"]]
        occupied = {e["path"].casefold() for e in before.values()}
        if any(r["destination_path"].casefold() in occupied for r in child_rows):
            raise w.Hold("DESTINATION_BECAME_OCCUPIED")
        request = {"entries": [{"from_path": r["source"]["id"], "to_path": r["destination_path"]} for r in child_rows], "autorename": False, "allow_ownership_transfer": False}
        before_ref = write_once(directory / "before.json", {"recorded_utc": w.now(), "entries": before})
        write_once(directory / "intent.json", {"recorded_utc": w.now(), "manifest_sha256": manifest_hash, "before": before_ref, "request": request})
        event("SUBMITTING", batch_id=batch["batch_id"], count=len(child_rows), manifest_sha256=manifest_hash)
        native_records = move_individuals(api, child_rows, directory, pool, api_factory)
        write_once(directory / "launch.json", {"recorded_utc": w.now(), "status": "NATIVE_CALLS_COMPLETE", "concurrent_workers": 2 if pool else 1, "calls": len(child_rows)})
        write_once(directory / "terminal.json", {"recorded_utc": w.now(), "entries": native_records, "failed": False})
        after = folder_listing(api, parent)
        after_ref = write_once(directory / "after.json", {"recorded_utc": w.now(), "entries": after})
        compare_parent(before, after, {r["source"]["id"]: r["destination_path"] for r in child_rows})
        for item in native_records:
            actual = after[item["source_id"]]
            if any(item["metadata"].get(k) != actual.get(k) for k in ("id", "rev", "size", "content_hash")):
                raise w.Hold("RECEIPT_AND_INDEPENDENT_READBACK_DISAGREE")
        write_once(directory / "verified.json", {"status": "RENAMED_VERIFIED", "recorded_utc": w.now(), "manifest_sha256": manifest_hash, "file_ids": batch["file_ids"], "post_readback": after_ref})
        expected.update(after)
        verified += len(child_rows)
        completed_batches += 1
        state = {"status": "RUNNING", "recorded_utc": w.now(), "files_verified": verified, "files_total": len(rows), "batches_verified": completed_batches, "batches_total": len(batches), "last_parent": parent["path"]}
        w.private_json(RUN / "status.json", state)
        event("BATCH_VERIFIED", batch_id=batch["batch_id"], files_verified=verified)
        print(f"Verified {verified}/{len(rows)} files; batch {completed_batches}/{len(batches)}; {family['name']} / {parent['name']}", flush=True)
    final = census(api)
    destinations = {i:r["destination_path"] for i,r in rows.items()}
    check_full(baseline, final, destinations)
    compare_parent(expected, {e["id"]:e for e in final["entries"] if e["kind"]=="file"})
    final_ref = write_once(RUN / "final-census.json", final)
    current_links = get_owned_urls(api)
    old_urls = json.loads(urls_path.read_text())
    old_by_id = collections.Counter((u["record"]["id"], u["record"]["resolved_visibility"], u["record"]["effective_audience"], u["record"]["link_access_level"], u["record"]["expires"]) for u in old_urls)
    new_by_id = collections.Counter((u["record"]["id"], u["record"]["resolved_visibility"], u["record"]["effective_audience"], u["record"]["link_access_level"], u["record"]["expires"]) for u in current_links)
    if old_by_id != new_by_id:
        raise w.Hold("OWNED_LINK_MEMBERSHIP_OR_ACCESS_CHANGED")
    link_checks = []
    for item in old_urls:
        old = item["record"]
        if old["id"] not in rows:
            continue
        new = link_record(api.read("sharing_get_shared_link_metadata", item["url"]))
        if new["id"] != old["id"] or new["name"] != rows[old["id"]]["destination_name"]:
            raise w.Hold("EXISTING_LINK_NO_LONGER_RESOLVES_TO_RENAMED_FILE")
        if any(new[k] != old[k] for k in ("resolved_visibility", "effective_audience", "link_access_level", "expires")):
            raise w.Hold("EXISTING_LINK_ACCESS_CHANGED")
        link_checks.append({"old_url_sha256": old["url_sha256"], "current": new, "status": "ORIGINAL_URL_RESOLVES_SAME_FILE_ID"})
    link_ref = write_once(RUN / "shared-link-verification.json", {"status": "PASS", "owned_links_before": len(old_urls), "owned_links_after": len(current_links), "original_file_urls_checked": len(link_checks), "checks": link_checks})
    mapping_path = Path(manifest.get("mapping", {}).get("path", DELIVERY / "OLD-AND-NEW-NAMES.csv"))
    completion = {"schema": "boldstone-path-renaming-completion-v1", "status": "PASS", "recorded_utc": w.now(), "manifest": reference(MANIFEST), "files_renamed_verified": verified, "files_total": len(rows), "batches_verified": completed_batches, "folders_unchanged_by_this_run": sum(e["kind"]=="folder" for e in final["entries"]), "external_folder_change_adopted": manifest.get("external_change_amendment"), "same_file_ids_bytes_extensions_parents_and_access": True, "final_census": final_ref, "shared_link_verification": link_ref, "backup_policy": "Prior user waiver for native move-only operations; no new image downloads or byte edits", "original_name_mapping": reference(mapping_path), "historical_reports": "Retained unchanged; use this mapping as current path overlay"}
    write_once(RUN / "COMPLETION.json", completion)
    write_once(DELIVERY / "COMPLETION.json", completion)
    w.private_json(RUN / "status.json", completion)
    event("COMPLETE", completion=reference(RUN / "COMPLETION.json"))
    print(json.dumps({k:completion[k] for k in ("status", "files_renamed_verified", "folders_unchanged_by_this_run", "batches_verified")}), flush=True)


def main():
    global MANIFEST
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    parser.add_argument("--manifest-path", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.manifest_path:
        if args.manifest_path.resolve().parent != RUN.resolve():
            raise w.SetupError("MANIFEST_OUTSIDE_FIXED_RUN_DIRECTORY")
        MANIFEST = args.manifest_path
    if args.mode == "prepare":
        prepare()
        return
    if not args.apply or not args.manifest_sha256:
        raise w.SetupError("EXECUTION_REQUIRES_APPLY_AND_FROZEN_MANIFEST")
    w.BUDGET = RetirementBudget()
    with ExitStack() as stack:
        for path in (w.RUN_PATH / "worker.lock", Path.home() / "Library/Application Support/BoldstoneImageConsistency/wall-duplicate-writer.lock"):
            lock = stack.enter_context(path.open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
        w.verify_grant(grant)
        api = w.API(grant)
        local = threading.local()
        clients, clients_lock = [], threading.Lock()
        def worker_api():
            if not hasattr(local, "api"):
                local.api = w.API(grant)
                with clients_lock:
                    clients.append(local.api)
            return local.api
        try:
            if args.workers == 2:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    execute(api, args.manifest_sha256, pool, worker_api)
            else:
                execute(api, args.manifest_sha256)
        except Exception as error:
            reason = str(error) if isinstance(error, (w.Hold, w.SetupError)) else type(error).__name__
            event("STOPPED", reason=reason)
            w.private_json(RUN / "stopped.json", {"recorded_utc": w.now(), "status": "STOPPED", "reason": reason})
            print("Stopped: " + reason, flush=True)
            raise SystemExit(2) from None
        finally:
            api.close()
            for client in clients:
                client.close()


if __name__ == "__main__":
    main()
