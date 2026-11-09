"""Read-only final audit of JPEG additions and preservation of the migration."""
from __future__ import annotations

import collections
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path, PurePosixPath

import convert_bmps as worker
from dropbox.files import DeletedMetadata, FileMetadata, FolderMetadata
from PIL import Image, JpegImagePlugin

COMPLETE = {"VERIFIED", "RECONCILED_JPEG_VERIFIED"}


def save_evidence(name, payload):
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    digest = hashlib.sha256(data).hexdigest()
    path = worker.SHARED / "audits" / f"{name}-{digest}.json"
    if path.exists():
        if path.read_bytes() != data:
            raise worker.SetupError("A content-addressed audit artifact has changed.")
    else:
        worker.private_json(path, payload)
    return path


def inspect_local(row, state):
    work = Path(state["work_directory"])
    source, output = work / "original.bmp", work / "converted.jpg"
    returned = Path(state.get("readback_proof", work / "downloaded-output.jpg"))
    local = state["local_jpeg"]
    expected = {k: local[k] for k in ("sha256", "content_hash", "size")}
    failures = []
    if worker.fingerprint(source) != state["backup"]:
        failures.append("ORIGINAL_BACKUP_CHANGED")
    if state["backup"]["content_hash"] != state["source_head"]["content_hash"]:
        failures.append("BACKUP_SOURCE_HASH_MISMATCH")
    for path in (output, returned):
        if worker.fingerprint(path) != expected:
            failures.append("LOCAL_JPEG_OR_DOWNLOADED_COPY_HASH_MISMATCH")
        worker.decode_jpeg(path, local["dimensions"])
    with Image.open(source) as original, Image.open(returned) as jpeg:
        original.load()
        jpeg.load()
        if original.size != jpeg.size or list(jpeg.size) != local["dimensions"]:
            failures.append("DIMENSIONS_CHANGED")
        if original.format == "BMP":
            if local["method"] != "BMP_TO_JPEG_QUALITY_100_SUBSAMPLING_0":
                failures.append("BMP_ENCODING_METHOD_MISMATCH")
            if not jpeg.quantization or any(v != 1 for table in jpeg.quantization.values() for v in table):
                failures.append("JPEG_QUANTIZATION_IS_NOT_MAXIMUM_QUALITY")
            if jpeg.mode != "L" and JpegImagePlugin.get_sampling(jpeg) != 0:
                failures.append("JPEG_CHROMA_SUBSAMPLING_FOUND")
            for key in ("icc_profile", "exif"):
                if original.info.get(key) and original.info[key] != jpeg.info.get(key):
                    failures.append("SOURCE_METADATA_NOT_PRESERVED_" + key.upper())
        elif original.format == "JPEG":
            if local["method"] != "EXISTING_JPEG_BYTES_COPIED_WITHOUT_RECOMPRESSION":
                failures.append("MISLABELLED_JPEG_METHOD_MISMATCH")
            if state["backup"] != expected:
                failures.append("MISLABELLED_JPEG_WAS_RECOMPRESSED")
        else:
            failures.append("UNEXPECTED_SOURCE_FORMAT")
    return {"source_id": row["source_id"], "source_path": row["source_path"],
            "destination_path": row["destination_path"], "output_head": state["output_head"],
            "parent_id": row["parent_id"],
            "source_head": state["source_head"], "method": local["method"],
            "dimensions": local["dimensions"], "local_sha256": local["sha256"],
            "source_backup_sha256": state["backup"]["sha256"], "failures": failures}


def normalize_paths(entries):
    """Rebuild ancestor casing from each current folder's own native name."""
    root = entries[worker.ROOT_ID]
    if root["kind"] != "folder" or root["path"] != worker.ROOT_PATH:
        raise worker.SetupError("Final census root identity or path does not match.")
    folders = {r["path_lower"]: r["id"] for r in entries.values() if r["kind"] == "folder"}
    if len(folders) != sum(r["kind"] == "folder" for r in entries.values()):
        raise worker.SetupError("Duplicate folder locations in final census.")
    paths = {worker.ROOT_ID: worker.ROOT_PATH}
    visiting = set()

    def resolve(identifier):
        if identifier in paths:
            return paths[identifier]
        if identifier in visiting:
            raise worker.SetupError("Cycle in final folder graph.")
        visiting.add(identifier)
        item = entries[identifier]
        parent_id = folders.get(str(PurePosixPath(item["path_lower"]).parent))
        if parent_id is None:
            raise worker.SetupError("Missing parent folder in final census.")
        if not item["name"] or "/" in item["name"] or item["name"] in (".", ".."):
            raise worker.SetupError("Invalid native item name in final census.")
        item["parent_id"] = parent_id
        paths[identifier] = resolve(parent_id) + "/" + item["name"]
        visiting.remove(identifier)
        return paths[identifier]

    normalized = []
    for identifier, item in entries.items():
        if identifier == worker.ROOT_ID:
            continue
        canonical = resolve(identifier)
        if not worker.path_equal(canonical, item["path"]):
            raise worker.SetupError("Native names and parent locations disagree.")
        normalized.append({**item, "raw_path_display": item["path"], "path": canonical,
                           "ancestor_display_alias": canonical != item["path"]})
    return normalized


def live_census(api):
    entries, pages = {}, 0
    cursors = set()
    page = api.read("files_list_folder", worker.ROOT_ID, recursive=True, limit=2000,
                    include_deleted=False)
    while True:
        pages += 1
        for item in page.entries:
            if isinstance(item, DeletedMetadata):
                raise worker.SetupError("Dropbox changed during the final census; repeat the read-only audit.")
            if isinstance(item, FileMetadata):
                record = {"kind": "file", **worker.head(item)}
            elif isinstance(item, FolderMetadata):
                record = {"kind": "folder", "id": item.id, "path": item.path_display}
            else:
                raise worker.SetupError("Unexpected metadata in final census.")
            record.update(name=item.name, path_lower=item.path_lower)
            entries[record["id"]] = record
        print(f"Final census: {len(entries)} entries across {pages} pages", flush=True)
        if not page.has_more:
            break
        if not isinstance(page.cursor, str) or not page.cursor or page.cursor in cursors:
            raise worker.SetupError("Incomplete final census pagination")
        cursors.add(page.cursor)
        page = api.read("files_list_folder_continue", page.cursor)
    if worker.ROOT_ID not in entries:
        root = api.metadata(worker.ROOT_ID)
        if not isinstance(root, FolderMetadata):
            raise worker.SetupError("Final root is not a folder.")
        entries[root.id] = {"kind": "folder", "id": root.id, "path": root.path_display,
                            "name": root.name, "path_lower": root.path_lower}
    normalized = normalize_paths(entries)
    return {"recorded_utc": worker.now(), "root_id": worker.ROOT_ID,
            "root_path": worker.ROOT_PATH, "namespace_id": worker.NAMESPACE_ID,
            "pagination_exhausted": True, "pages": pages,
            "root_metadata_excluded_from_descendant_count": entries[worker.ROOT_ID],
            "ancestor_display_aliases_resolved": sum(r["ancestor_display_alias"] for r in normalized),
            "normalization": "Current native Metadata.name and parent folder IDs; raw display paths retained.",
            "entries": normalized}


def compare_census(before, after, records):
    initial = {r["id"]: r for r in before["entries"]}
    current = {r["id"]: r for r in after["entries"]}
    outputs = {r["output_head"]["id"]: r for r in records}
    failures = []
    if len(outputs) != len(records):
        failures.append({"reason": "DUPLICATE_OUTPUT_IDS"})
    if set(initial) & set(outputs):
        failures.append({"reason": "OUTPUT_REUSED_AN_ORIGINAL_FILE_ID"})
    for identifier, old in initial.items():
        new = current.get(identifier)
        if new is None:
            failures.append({"id": identifier, "reason": "ORIGINAL_ENTRY_MISSING"})
            continue
        if new["kind"] != old["kind"] or new["path"] != old["path"]:
            failures.append({"id": identifier, "reason": "ORIGINAL_ENTRY_KIND_OR_PATH_CHANGED"})
        if old.get("parent_id") and new.get("parent_id") != old["parent_id"]:
            failures.append({"id": identifier, "reason": "ORIGINAL_PARENT_ID_CHANGED"})
        if old["kind"] == "file" and new["kind"] == "file" and (
            old["size"] != new["size"] or any(
                worker.timestamp(old[k]) != worker.timestamp(new[k])
                for k in ("client_modified", "server_modified")
            )
        ):
            failures.append({"id": identifier, "reason": "ORIGINAL_FILE_SIZE_OR_TIMESTAMPS_CHANGED"})
    for record in records:
        source = current.get(record["source_id"], {})
        if source.get("path") != record["source_path"] or any(
            source.get(k) != record["source_head"][k] for k in ("id", "rev", "size", "content_hash")
        ):
            failures.append({"id": record["source_id"], "reason": "SOURCE_CHANGED_SINCE_CONVERSION"})
        output = current.get(record["output_head"]["id"], {})
        if output.get("path") != record["destination_path"] or any(
            output.get(k) != record["output_head"][k] for k in ("id", "rev", "size", "content_hash")
        ):
            failures.append({"id": record["output_head"]["id"], "reason": "OUTPUT_CHANGED_SINCE_VERIFICATION"})
        if output.get("parent_id") != record["parent_id"]:
            failures.append({"id": record["output_head"]["id"], "reason": "OUTPUT_PARENT_ID_CHANGED"})
    unexpected = sorted(set(current) - set(initial) - set(outputs))
    if unexpected:
        failures.append({"reason": "UNEXPECTED_ADDITIONS", "ids": unexpected})
    return failures


def main():
    os.umask(0o077)
    with (worker.RUN_PATH / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = json.loads(worker.PLAN_PATH.read_text())
        worker.validate_plan(plan)
        previous_path = worker.RUNTIME / "conversion-completion.json"
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
        rows = [r for r in plan["rows"] if r["status"] == "ELIGIBLE"]
        states = [worker.saved_state(r) for r in rows]
        if any(s.get("state") not in COMPLETE for s in states):
            raise worker.SetupError("All eligible conversions must be verified before the final audit.")
        print(f"Inspecting all {len(rows)} local originals and downloaded JPEGs", flush=True)
        records = [inspect_local(r, s) for r, s in zip(rows, states, strict=True)]
        grant = json.loads(worker.keychain_backend().get_password(worker.SERVICE, worker.CREDENTIAL_ACCOUNT))
        identity = worker.verify_grant(grant)
        api = worker.API(grant)
        try:
            census = live_census(api)
        finally:
            api.close()
        census_path = save_evidence("post-conversion-live-census", census)
        before = json.loads(Path(plan["evidence"]["census"]["path"]).read_text())
        failures = compare_census(before, census, records)
        failures += [{"id": r["source_id"], "reason": reason}
                     for r in records for reason in r["failures"]]
        report_path = save_evidence("verification-full-quality", {
            "schema": "boldstone-full-quality-verification-v1", "recorded_utc": worker.now(),
            "records": records, "failures": failures})
        counts = collections.Counter(r["kind"] for r in census["entries"])
        original_counts = collections.Counter(r["kind"] for r in before["entries"])
        summary = {"schema": "boldstone-bmp-jpeg-completion-v1", "completed_utc": worker.now(),
                   "status": "PASS" if not failures else "REVIEW_REQUIRED",
                   "eligible": len(rows), "verified_jpegs": len(records),
                   "held_without_conversion": plan["counts"]["held"],
                   "methods": dict(collections.Counter(r["method"] for r in records)),
                   "jpeg_quality_for_true_bmps": 100, "jpeg_subsampling_for_true_bmps": 0,
                   "original_dimensions_preserved": not any("DIMENSIONS" in f["reason"] for f in failures),
                   "jpeg_is_lossy": True, "originals_retained": not any(
                       f["reason"].startswith(("ORIGINAL_", "SOURCE_")) for f in failures),
                   "source_files_deleted_by_conversion": 0, "remote_mutations_by_audit": 0,
                   "original_library_files": original_counts["file"],
                   "final_library_files": counts["file"], "final_folders": counts["folder"],
                   "ancestor_display_aliases_resolved": census["ancestor_display_aliases_resolved"],
                   "previous_audit_summary": previous.get("immutable_summary_path"),
                   "jpeg_bytes": sum(r["output_head"]["size"] for r in records),
                   "verified_identity": identity, "failures": failures,
                   "plan_path": str(worker.PLAN_PATH),
                   "plan_sha256": hashlib.sha256(worker.PLAN_PATH.read_bytes()).hexdigest(),
                   "shared_ledger": str(worker.SHARED / "operations.jsonl"),
                   "shared_ledger_sha256": hashlib.sha256((worker.SHARED / "operations.jsonl").read_bytes()).hexdigest(),
                   "migration_audit": plan["evidence"]["final_audit"],
                   "verification_path": str(report_path), "live_census_path": str(census_path),
                   "verification_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                   "live_census_sha256": hashlib.sha256(census_path.read_bytes()).hexdigest()}
        immutable_summary = save_evidence("completion-full-quality", summary)
        summary["immutable_summary_path"] = str(immutable_summary)
        summary["immutable_summary_sha256"] = hashlib.sha256(immutable_summary.read_bytes()).hexdigest()
        worker.private_json(worker.SHARED / "completion-full-quality.json", summary)
        worker.private_json(worker.RUNTIME / "conversion-completion.json", summary)
        worker.update_status(plan, "COMPLETE_VERIFIED" if not failures else "AUDIT_REVIEW_REQUIRED")
        print(json.dumps({k: v for k, v in summary.items() if k != "verified_identity"}, indent=2))
        return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except worker.SetupError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as error:  # noqa: BLE001 -- Keep credential and URL values out of logs.
        print("Final audit stopped safely; error type: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
