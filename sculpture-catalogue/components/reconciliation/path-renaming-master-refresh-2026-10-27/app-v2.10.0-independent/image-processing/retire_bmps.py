"""Exact, revision-conditional BMP retirement with a separate durable journal.

Use `prepare` to freeze the checks and review list. Execution requires the exact
manifest SHA-256. There is no folder deletion, permanent deletion or write retry.
"""
from __future__ import annotations

import argparse
import collections
import fcntl
import hashlib
import json
import os
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

import audit_conversion as audit
import convert_bmps as w
from check_bmp_retirement import (
    CHECKS,
    database_controls,
    link_record,
    reference,
    sharing_flags,
)
from dropbox.files import FileMetadata, FolderMetadata

RETIREMENT = w.RUNTIME / "retirement"
SHARED = w.SHARED / "retirement"
MANIFEST = SHARED / "manifest.json"
FINISHED = {"DELETED_VERIFIED", "RECONCILED_DELETED_VERIFIED"}
LOCAL = threading.local()


class RetirementBudget(w.Budget):
    """Smoothly cap this single worker at four requests per second."""

    def wait(self):
        with self.lock:
            wait = max(0.0, self.next_call - time.monotonic())
            self.next_call = max(self.next_call, time.monotonic()) + 0.25
        if w.STOP.wait(wait):
            raise w.Hold("RUN_STOPPED")


def read_reference(item):
    path = Path(item["path"])
    if reference(path)["sha256"] != item["sha256"]:
        raise w.SetupError("A frozen retirement input changed")
    return json.loads(path.read_text())


def fingerprint_stream(stream):
    sha, blocks, size = hashlib.sha256(), hashlib.sha256(), 0
    while data := stream.read(w.BLOCK_SIZE):
        size += len(data)
        sha.update(data)
        blocks.update(hashlib.sha256(data).digest())
    return {"sha256": sha.hexdigest(), "content_hash": blocks.hexdigest(), "size": size}


def assert_file(metadata, expected, path):
    if not isinstance(metadata, FileMetadata):
        raise w.Hold("EXPECTED_FILE_MISSING_OR_WRONG_TYPE")
    current = w.head(metadata)
    if any(current[key] != expected[key] for key in ("id", "rev", "size", "content_hash")):
        raise w.Hold("FILE_ID_REVISION_HASH_OR_SIZE_CHANGED")
    if not w.path_equal(current["path"], path) or metadata.name != PurePosixPath(path).name:
        raise w.Hold("FILE_LOCATION_OR_NAME_CHANGED")
    return current


def assert_private_source(metadata, links):
    flags = sharing_flags(metadata)
    if flags["has_explicit_shared_members"] is not False or flags["sharing_info_present"]:
        raise w.Hold("EXTERNAL_OR_UNKNOWN_MEMBERSHIP")
    if flags["read_only"] or flags["file_lock_present"]:
        raise w.Hold("READ_ONLY_OR_LOCKED")
    if any(link["resolved_visibility"] not in ("no_one", "only_you")
           or link["effective_audience"] not in ("no_one", None) for link in links):
        raise w.Hold("ACTIVE_OR_UNKNOWN_DIRECT_LINK")


def source_key(row):
    return hashlib.sha256(row["source_id"].encode()).hexdigest()


def state_path(row):
    return RETIREMENT / "states" / (source_key(row) + ".json")


def saved(row):
    path = state_path(row)
    return json.loads(path.read_text()) if path.exists() else {}


def record(row, status, manifest_hash, **details):
    event = {"schema": "boldstone-bmp-retirement-operation-v1", "recorded_utc": w.now(),
             "source_id": row["source_id"], "source_path": row["source_path"],
             "jpeg_id": row["output_head"]["id"], "jpeg_path": row["destination_path"],
             "manifest_sha256": manifest_hash, "status": status, **details}
    w.private_json(state_path(row), event)
    SHARED.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(SHARED / "operations.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return event


def prepare():
    plan = json.loads(w.PLAN_PATH.read_text())
    w.validate_plan(plan)
    checks = json.loads((CHECKS / "checks.json").read_text())
    publication = json.loads((CHECKS / "publication.json").read_text())
    import_links = json.loads((CHECKS / "import-link-review.json").read_text())
    archive = json.loads((CHECKS / "archive-proof.json").read_text())
    if checks["census_failures"] or publication["failed_pages"] or publication["public_reference_pages"]:
        raise w.SetupError("A library or publication check is unresolved")
    if publication["sitemap_image_references"] or archive["status"] != "PASS":
        raise w.SetupError("Image references or archive proof is unresolved")
    known_local = {"Boldstone_Dropbox_Folder_Index.md", "squarespace_import_dropbox_archive.csv"}
    if {Path(r["path"]).name for r in publication["local_reference_files"]} != known_local:
        raise w.SetupError("Local publication references changed")
    if len(import_links["records"]) != 18 or any(r.get("status") != 404 for r in import_links["records"]):
        raise w.SetupError("Legacy import link review changed")
    if reference(Path(archive["archive"]["path"]))["sha256"] != archive["archive"]["sha256"]:
        raise w.SetupError("Original archive hash changed")
    archive_manifest = read_reference(archive["manifest"])
    backed_up = {r["source_id"]: r for r in archive_manifest["records"]}
    restored = {r["source_id"]: r for r in archive["records"]}
    planned = {r["source_id"]: r for r in plan["rows"]}
    ready, skipped = [], []
    for check in checks["records"]:
        row = planned[check["source_id"]]
        if check["holds"]:
            skipped.append({**row, "retirement_holds": check["holds"]})
            continue
        backup = backed_up[row["source_id"]]
        proof = restored[row["source_id"]]
        if not proof["restore_and_decode_passed"] or any(proof[k] != backup["backup"][k]
                                                        for k in ("sha256", "content_hash", "size")):
            raise w.SetupError("Missing archive restoration proof")
        ready.append({**row, "source_head": check["source_head"], "output_head": check["output_head"],
                      "direct_links": check["direct_links"], "ancestor_links": check["ancestor_links"],
                      "backup": backup["backup"], "archive_member": backup["archive_member"],
                      "dimensions": check["local_verification"]["dimensions"],
                      "available_history_count": len(check["available_history"]["entries"]),
                      "reason": "Verified JPEG successor, identical archived original/history bytes, no protection or known publication dependency."})
    skipped.extend({**row, "retirement_holds": row["hold_reasons"]} for row in plan["rows"] if row["status"] != "ELIGIBLE")
    if len(ready) + len(skipped) != len(plan["rows"]):
        raise w.SetupError("Retirement manifest does not account for every BMP")
    manifest = {"schema": "boldstone-bmp-retirement-manifest-v1", "created_utc": w.now(),
                "authorization": {"instruction": "Do the checks and then delete",
                                  "scope": "Only checked, verified converted BMP sources in the established conversion plan."},
                "root_id": w.ROOT_ID, "root_path": w.ROOT_PATH, "namespace_id": w.NAMESPACE_ID,
                "policy": {"maximum_batch": 5, "permanent_delete": False, "delete_folders": False,
                           "expected_revision_required": True, "write_retry": False},
                "evidence": {"plan": reference(w.PLAN_PATH), "checks": reference(CHECKS / "checks.json"),
                             "publication": reference(CHECKS / "publication.json"),
                             "legacy_import_links": reference(CHECKS / "import-link-review.json"),
                             "archive_proof": reference(CHECKS / "archive-proof.json")},
                "publication_assessment": "435 public pages contain no BMP or Dropbox references; all 1269 sitemap images use Squarespace CDN. The only local file URLs are 18 already-404 legacy import URLs. The other reference is an unrelated Dropbox home folder index. Private/offline systems are outside this check.",
                "sharing_assessment": "No explicit/inherited members or active direct distribution links. Thirteen owner navigation links grant no additional rights. Existing parent-folder links remain unchanged; each JPEG remains in the same parent.",
                "archive": archive["archive"], "ready": ready, "skipped": skipped,
                "counts": {"delete_candidates": len(ready), "held": len(skipped),
                           "original_bytes_to_remove": sum(r["size"] for r in ready)}}
    if MANIFEST.exists():
        raise w.SetupError("A retirement manifest already exists; do not silently replace it")
    w.private_json(MANIFEST, manifest)
    lines = ["# BMP deletion review", "", f"Prepared {manifest['created_utc']}", "",
             f"Exact candidates: {len(ready)} files. Held: {len(skipped)} files.", "",
             f"Lossless archive: `{archive['archive']['path']}`", "",
             "All 410 archive members were extracted, hashed and decoded successfully.", "",
             manifest["publication_assessment"], "", manifest["sharing_assessment"], "",
             "Each listed item is a BMP file with a separately verified quality-100, 4:4:4 JPEG successor.", "",
             "| Candidate file | Stable ID | Modified UTC | Direct sharing |", "|---|---|---|---|"]
    for row in ready:
        links = "Owner navigation only" if row["direct_links"] else "None returned"
        lines.append(f"| {row['source_path']} | {row['source_id']} | {row['source_head']['server_modified']} | {links} |")
    lines += ["", "## Held BMP files", "", "| File | Reason |", "|---|---|"]
    for row in skipped:
        lines.append(f"| {row['source_path']} | {', '.join(row['retirement_holds'])} |")
    (SHARED / "DELETION-REVIEW.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({**manifest["counts"], "manifest": reference(MANIFEST),
                      "review": str(SHARED / "DELETION-REVIEW.md")}, indent=2))


def api_for(grant):
    if not hasattr(LOCAL, "api"):
        LOCAL.api = w.API(grant)
    return LOCAL.api


def preflight(row, grant, archive_path):
    api = api_for(grant)
    with zipfile.ZipFile(archive_path) as archive, archive.open(row["archive_member"]) as source:
        if fingerprint_stream(source) != row["backup"]:
            raise w.Hold("ARCHIVE_MEMBER_CHANGED")
    source = api.read("files_get_metadata", row["source_id"], include_has_explicit_shared_members=True)
    current = assert_file(source, row["source_head"], row["source_path"])
    output = assert_file(api.metadata(row["output_head"]["id"]), row["output_head"], row["destination_path"])
    response = api.read("sharing_list_shared_links", path=row["source_id"], direct_only=True)
    if response.has_more:
        raise w.Hold("INCOMPLETE_DIRECT_SHARING_CHECK")
    links = [link_record(link) for link in response.links]
    assert_private_source(source, links)
    if sorted(links, key=lambda r: r["url_sha256"]) != sorted(row["direct_links"], key=lambda r: r["url_sha256"]):
        raise w.Hold("DIRECT_LINK_STATE_CHANGED")
    state = w.saved_state(row)
    returned = Path(state.get("readback_proof", Path(state["work_directory"]) / "downloaded-output.jpg"))
    if w.fingerprint(returned) != {k: state["local_jpeg"][k] for k in ("sha256", "content_hash", "size")}:
        raise w.Hold("JPEG_READBACK_PROOF_CHANGED")
    w.decode_jpeg(returned, row["dimensions"])
    return {"checked_utc": w.now(), "source_head": current, "output_head": output,
            "archive_member_verified": True, "direct_links": links}


def delete_once(api, row, preflight_result, manifest_hash):
    # Validate again at the mutation boundary; no broad path, folder or force option exists.
    if row["status"] != "ELIGIBLE" or row["hold_reasons"] or not row["source_id"].startswith("id:"):
        raise w.Hold("SOURCE_NOT_ELIGIBLE")
    if PurePosixPath(row["source_path"]).suffix.casefold() != ".bmp":
        raise w.Hold("SOURCE_IS_NOT_A_BMP_PATH")
    if not row["source_path"].startswith(w.ROOT_PATH + "/"):
        raise w.Hold("SOURCE_OUTSIDE_ROOT")
    if row["source_head"].get("kind") != "file" or row["output_head"].get("kind") != "file":
        raise w.Hold("MANIFEST_TARGET_IS_NOT_A_FILE")
    if not row["source_head"]["rev"] or any(
        preflight_result[key].get(field) != row[key].get(field)
        for key in ("source_head", "output_head") for field in ("id", "rev", "size", "content_hash")
    ):
        raise w.Hold("INVALID_REVISION_CONDITION")
    record(row, "DELETE_INTENT", manifest_hash, expected_source=row["source_head"],
           expected_output=row["output_head"], preflight=preflight_result)
    w.BUDGET.wait()
    try:
        result = api.client.files_delete_v2(row["source_id"], parent_rev=row["source_head"]["rev"])
    except Exception as error:  # noqa: BLE001 -- An unknown write must never be automatically retried.
        record(row, "DELETE_OUTCOME_UNKNOWN", manifest_hash, error_type=type(error).__name__)
        raise w.SetupError("Delete outcome unknown; stopped writes for reconciliation") from None
    receipt = assert_file(result.metadata, row["source_head"], row["source_path"])
    record(row, "DELETE_RETURNED", manifest_hash, receipt=receipt)


def verify_deleted(row, grant):
    api = api_for(grant)
    if api.metadata(row["source_id"]) is not None:
        raise w.Hold("DELETED_SOURCE_STILL_PRESENT")
    jpeg = assert_file(api.metadata(row["output_head"]["id"]), row["output_head"], row["destination_path"])
    return {"checked_utc": w.now(), "source_absent_by_id": True, "output_head": jpeg}


def compare_retirement(before, after, deleted):
    deleted = set(deleted)
    old = {r["id"]: r for r in before["entries"]}
    new = {r["id"]: r for r in after["entries"]}
    failures = []
    if set(new) != set(old) - deleted:
        failures.append({"reason": "ENTRY_SET_DIFFERENCE", "unexpected": sorted(set(new) - set(old)),
                         "missing_without_receipt": sorted(set(old) - set(new) - deleted),
                         "deleted_still_present": sorted(deleted & set(new))})
    for identifier in set(new) & set(old):
        fields = ("kind", "path", "parent_id", "name")
        if old[identifier]["kind"] == "file":
            fields += ("rev", "size", "content_hash", "client_modified", "server_modified")
        if any(old[identifier].get(k) != new[identifier].get(k) for k in fields):
            failures.append({"id": identifier, "reason": "SURVIVING_ENTRY_CHANGED"})
    return failures


def final_audit(manifest, grant):
    api = w.API(grant)
    try:
        current = audit.live_census(api)
    finally:
        api.close()
    checked = read_reference(manifest["evidence"]["checks"])
    before = read_reference(checked["census"])
    states = [saved(row) for row in manifest["ready"]]
    deleted = {s["source_id"] for s in states if s.get("status") in FINISHED}
    failures = compare_retirement(before, current, deleted)
    current_path = audit.save_evidence("post-bmp-retirement-census", current)
    original = json.loads(w.PLAN_PATH.read_text())
    current_ids = {r["id"] for r in current["entries"]}
    all_jpeg_ids = {w.saved_state(r)["output_head"]["id"] for r in original["rows"] if r["status"] == "ELIGIBLE"}
    held_ids = {r["source_id"] for r in manifest["skipped"]}
    if not all_jpeg_ids <= current_ids or not held_ids <= current_ids:
        failures.append({"reason": "JPEG_OR_HELD_BMP_MISSING"})
    if reference(Path(manifest["archive"]["path"]))["sha256"] != manifest["archive"]["sha256"]:
        failures.append({"reason": "ARCHIVE_CHANGED"})
    unresolved = [s for s in states if s.get("status") not in FINISHED | {"HELD"}]
    summary = {"schema": "boldstone-bmp-retirement-completion-v1", "completed_utc": w.now(),
               "status": "PASS" if not failures and not unresolved else "REVIEW_REQUIRED",
               "deleted": len(deleted), "remaining_bmps": sum(r["kind"] == "file" and r["name"].casefold().endswith(".bmp") for r in current["entries"]),
               "verified_jpegs_preserved": len(all_jpeg_ids & current_ids),
               "original_exclusions_preserved": len(held_ids & current_ids),
               "final_library_files": sum(r["kind"] == "file" for r in current["entries"]),
               "final_folders": sum(r["kind"] == "folder" for r in current["entries"]),
               "states": dict(collections.Counter(s.get("status", "NOT_STARTED") for s in states)),
               "archive": manifest["archive"], "manifest": reference(MANIFEST),
               "final_census": reference(current_path), "failures": failures, "unresolved": unresolved,
               "deleted_ids": sorted(deleted), "deleted_bytes": sum(r["size"] for r in manifest["ready"] if r["source_id"] in deleted),
               "permanent_deletion": False, "source_originals_retained_in_local_archive": True}
    w.private_json(SHARED / "completion.json", summary)
    w.private_json(w.RUNTIME / "retirement-completion.json", summary)
    lineage = [{"source_id": r["source_id"], "source_revision": r["source_head"]["rev"],
                "successor_id": r["output_head"]["id"], "successor_revision": r["output_head"]["rev"],
                "source_state": "RETIRED_FROM_DROPBOX_ARCHIVED_LOCALLY" if r["source_id"] in deleted else "RETAINED",
                "archive_member": r["archive_member"], "backup": r["backup"]} for r in manifest["ready"]]
    w.private_json(SHARED / "lineage.json", {"recorded_utc": w.now(), "manifest": reference(MANIFEST), "records": lineage})
    print(json.dumps({k: v for k, v in summary.items() if k not in ("deleted_ids", "unresolved")}, indent=2))
    return 0 if summary["status"] == "PASS" else 1


def execute(expected_hash):
    if reference(MANIFEST)["sha256"] != expected_hash:
        raise w.SetupError("Exact retirement manifest hash required")
    manifest = json.loads(MANIFEST.read_text())
    if (manifest["root_id"], manifest["root_path"], manifest["namespace_id"]) != (w.ROOT_ID, w.ROOT_PATH, w.NAMESPACE_ID):
        raise w.SetupError("Retirement root binding changed")
    for item in manifest["evidence"].values():
        read_reference(item)
    plan = read_reference(manifest["evidence"]["plan"])
    w.validate_plan(plan)
    if reference(Path(manifest["archive"]["path"]))["sha256"] != manifest["archive"]["sha256"]:
        raise w.SetupError("Archive hash failed before deletion")
    controls = database_controls()
    blocked = {r["asset_id"] for r in controls["protections"] + controls["holds"]}
    blocked |= {r[k] for r in controls["lineage"] for k in ("from_asset_id", "to_asset_id")}
    if any(r["source_id"] in blocked for r in manifest["ready"]):
        raise w.SetupError("A candidate now has a protection or hold")
    grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
    w.verify_grant(grant)
    w.BUDGET = RetirementBudget()
    api = w.API(grant)
    rows = []
    for row in manifest["ready"]:
        prior = saved(row)
        if prior and prior.get("manifest_sha256") != expected_hash:
            raise w.SetupError("Retirement state belongs to another manifest")
        if prior.get("status") in FINISHED | {"HELD"}:
            continue
        if prior:
            raise w.SetupError("Prior unresolved intent requires read-only reconciliation")
        rows.append(row)
    try:
        # One exact pilot, then batches containing no more than five BMPs.
        batches = ([rows[:1]] + [rows[i:i + 5] for i in range(1, len(rows), 5)]) if rows else []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for index, batch in enumerate(batches, 1):
                root = api.metadata(w.ROOT_ID)
                if not isinstance(root, FolderMetadata) or root.path_display != w.ROOT_PATH:
                    raise w.SetupError("Root changed during retirement")
                checked_folders = set()
                for row in batch:
                    for identifier, path in ((row["family_id"], row["family_path"]), (row["parent_id"], row["parent_path"])):
                        if identifier in checked_folders:
                            continue
                        folder = api.metadata(identifier)
                        if not isinstance(folder, FolderMetadata) or folder.id != identifier or not w.path_equal(folder.path_display, path):
                            raise w.SetupError("Candidate folder moved during retirement")
                        checked_folders.add(identifier)
                futures = [(row, pool.submit(preflight, row, grant, manifest["archive"]["path"])) for row in batch]
                ready = []
                for row, future in futures:
                    try:
                        ready.append((row, future.result()))
                    except w.Hold as error:
                        record(row, "HELD", expected_hash, reason=str(error))
                for row, proof in ready:
                    delete_once(api, row, proof, expected_hash)
                verifications = [(row, pool.submit(verify_deleted, row, grant)) for row, _ in ready]
                for row, future in verifications:
                    record(row, "DELETED_VERIFIED", expected_hash, verification=future.result())
                counts = collections.Counter(saved(r).get("status", "NOT_STARTED") for r in manifest["ready"])
                w.private_json(RETIREMENT / "status.json", {"updated_utc": w.now(), "batch": index,
                               "batches": len(batches), "states": dict(counts)})
                print(f"Batch {index}/{len(batches)}: {dict(counts)}", flush=True)
        return final_audit(manifest, grant)
    finally:
        api.close()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute", "audit"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    RETIREMENT.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (w.RUN_PATH / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == "prepare":
            prepare()
            return 0
        if args.mode == "execute":
            return execute(args.manifest_sha256)
        grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
        w.verify_grant(grant)
        return final_audit(json.loads(MANIFEST.read_text()), grant)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except w.Hold as error:
        print("Retirement held: " + str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except w.SetupError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as error:  # noqa: BLE001 -- Never expose token-bearing exception text.
        print("Retirement stopped without retry; error type: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
