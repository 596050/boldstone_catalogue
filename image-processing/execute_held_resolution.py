"""Apply the reviewed held-BMP resolution with verified successors and guarded retirement.

Historical control records are preserved. New lineage and successor protection are
recorded separately before retiring sources. H01 and public-link exceptions are
excluded from this manifest. No write is retried automatically.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath

import audit_conversion as audit
import convert_bmps as w
from check_bmp_retirement import census, database_controls, link_record, reference
from dropbox.files import FolderMetadata
from inspect_held_bmps import RUN, SHARED, inspect_jpeg, key
from prepare_held_resolution import ARCHIVE_DIR, MANIFEST
from retire_bmps import (
    RetirementBudget,
    assert_file,
    assert_private_source,
    compare_retirement,
    fingerprint_stream,
    read_reference,
)

LOCAL = threading.local()
EVENT_LOCK = threading.Lock()
WRITES = threading.Lock()
STOP_WRITES = threading.Event()
COMPLETE = {"SUCCESSOR_VERIFIED", "DELETED_VERIFIED"}


def state_path(kind, identifier):
    return RUN / (kind + "-states") / (key(identifier) + ".json")


def saved(kind, identifier):
    path = state_path(kind, identifier)
    return json.loads(path.read_text()) if path.exists() else {}


def record(kind, identifier, status, manifest_hash, **details):
    with EVENT_LOCK:
        old = saved(kind, identifier)
        if old and old["manifest_sha256"] != manifest_hash:
            raise w.SetupError("State belongs to another manifest")
        event = {**old, "schema": "boldstone-held-resolution-operation-v1", "kind": kind,
                 "identifier": identifier, "status": status, "recorded_utc": w.now(),
                 "manifest_sha256": manifest_hash, **details}
        w.private_json(state_path(kind, identifier), event)
        fd = os.open(SHARED / "operations.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event


def api_for(grant):
    if not hasattr(LOCAL, "api"):
        LOCAL.api = w.API(grant)
    return LOCAL.api


def check_controls(manifest):
    inspection = read_reference(manifest["evidence"]["inspection"])
    expected = read_reference(inspection["database_controls"])
    current = database_controls()
    if any(current[k] != expected[k] for k in ("protections", "holds", "lineage")):
        raise w.SetupError("Historical restrictions changed; review required")
    held = {r["asset_id"] for r in current["holds"]}
    if held & {r["source_id"] for r in manifest["ready"]}:
        raise w.SetupError("An unresolved historical hold entered the ready set")


def validate(manifest, manifest_hash):
    if reference(MANIFEST)["sha256"] != manifest_hash:
        raise w.SetupError("Exact reviewed manifest hash required")
    if (manifest["root_id"], manifest["namespace_id"], manifest["root_path"]) != (w.ROOT_ID, w.NAMESPACE_ID, w.ROOT_PATH):
        raise w.SetupError("Manifest scope changed")
    for item in manifest["evidence"].values():
        read_reference(item)
    w.validate_plan(read_reference(manifest["evidence"]["original_plan"]))
    inspection = read_reference(manifest["evidence"]["inspection"])
    expected = {r["source_id"] for r in inspection["records"] if not r["unresolved"]}
    ready = {r["source_id"]: r for r in manifest["ready"]}
    groups = {g["group_id"]: g for g in manifest["groups"]}
    if set(ready) != expected or len(ready) != len(manifest["ready"]):
        raise w.SetupError("Ready set differs from inspected and cleared sources")
    if set(ready) & {r["source_id"] for r in manifest["held"]}:
        raise w.SetupError("Held source entered the ready set")
    coverage = [s for g in groups.values() for s in g["source_ids"]]
    if len(coverage) != len(ready) or set(coverage) != set(ready):
        raise w.SetupError("Successor groups do not cover each source exactly once")
    for row in ready.values():
        group = groups[row["replacement_group"]]
        owner = group["representative"]
        source, target = PurePosixPath(row["source_path"]), PurePosixPath(group["destination_path"])
        if row["unresolved"] or "H01_TARGET_OR_KEEPER" in row["original_hold_reasons"]:
            raise w.SetupError("Unresolved source in deletion plan")
        if (source.suffix.casefold() != ".bmp" or target.suffix.casefold() != ".jpg"
                or not str(source).startswith(w.ROOT_PATH + "/") or source.parent != target.parent):
            raise w.SetupError("Source or successor outside approved sibling scope")
        if row["backup"] != owner["backup"] or row["parent_id"] != owner["parent_id"]:
            raise w.SetupError("Duplicate source does not match representative")
        if row["protection_transition_required"] != ("PROTECTED_KEEPER_OR_REPLACEMENT" in row["original_hold_reasons"]):
            raise w.SetupError("Keeper protection transition missing")
    check_controls(manifest)
    if reference(Path(manifest["archive"]["path"]))["sha256"] != manifest["archive"]["sha256"]:
        raise w.SetupError("Lossless archive changed")
    for kind, identifiers in (("successor", groups), ("retirement", ready)):
        for identifier in identifiers:
            state = saved(kind, identifier)
            if state and (state["manifest_sha256"] != manifest_hash or state["status"] not in COMPLETE):
                raise w.SetupError("Unresolved prior operation requires read-only reconciliation")


def current_source(api, row, archive_path):
    with zipfile.ZipFile(archive_path) as archive, archive.open(row["archive_member"]) as source:
        if fingerprint_stream(source) != row["backup"]:
            raise w.Hold("ARCHIVE_MEMBER_CHANGED")
    metadata = api.read("files_get_metadata", row["source_id"], include_has_explicit_shared_members=True)
    head = assert_file(metadata, row["source_head"], row["source_path"])
    result = api.read("sharing_list_shared_links", path=row["source_id"], direct_only=True)
    if result.has_more:
        raise w.Hold("INCOMPLETE_SHARING_CHECK")
    links = [link_record(link) for link in result.links]
    assert_private_source(metadata, links)
    if sorted(links, key=lambda r: r["url_sha256"]) != sorted(row["direct_links"], key=lambda r: r["url_sha256"]):
        raise w.Hold("SOURCE_SHARING_CHANGED")
    return {"source_head": head, "direct_links": links, "archive_member_verified": True, "checked_utc": w.now()}


def verify_jpeg(api, group, expected):
    path = group["destination_path"]
    current = assert_file(api.metadata(expected["id"]), expected, path)
    work = RUN / "successors" / key(group["group_id"])
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    downloaded = work / "remote-readback.jpg"
    api.download(downloaded, current["id"], current["rev"])
    if w.fingerprint(downloaded) != group["jpeg_fingerprint"]:
        raise w.Hold("SUCCESSOR_DOWNLOAD_BYTES_DIFFER")
    check = inspect_jpeg(downloaded, Path(group["representative"]["work_directory"]) / "converted.jpg")
    if not check["verified_replacement"] or check["dimensions"] != group["dimensions"] or check["jpeg_quantization_max"] != 1:
        raise w.Hold("SUCCESSOR_MAXIMUM_QUALITY_OR_METADATA_FAILED")
    assert_file(api.metadata(current["id"]), current, path)
    return {"output_head": {**current, "kind": "file", "path": path, "name": PurePosixPath(path).name,
                            "parent_id": group["representative"]["parent_id"]},
            "readback": {"path": str(downloaded), **group["jpeg_fingerprint"]}, "quality_check": check}


def prepare_successor(group, manifest, manifest_hash, grant):
    if saved("successor", group["group_id"]):
        return
    api = api_for(grant)
    owner = next(r for r in manifest["ready"] if r["source_id"] == group["group_id"])
    w.validate_folders(api, owner)
    proof = current_source(api, owner, manifest["archive"]["path"])
    local = Path(group["local_verified_jpeg"])
    if w.fingerprint(local) != group["jpeg_fingerprint"]:
        raise w.Hold("LOCAL_JPEG_CHANGED")
    if group["method"] == "CREATE_MAXIMUM_QUALITY_JPEG":
        with WRITES:
            if STOP_WRITES.is_set():
                raise w.Hold("WRITES_STOPPED")
            if api.metadata(group["destination_path"]) is not None:
                raise w.Hold("DESTINATION_OCCUPIED")
            record("successor", group["group_id"], "UPLOAD_INTENT", manifest_hash,
                   destination_path=group["destination_path"], expected_fingerprint=group["jpeg_fingerprint"], preflight=proof)
            try:
                metadata = api.upload(local, group["destination_path"], owner["source_head"]["client_modified"])
            except Exception as error:  # noqa: BLE001 -- Never retry an unknown write or log secrets.
                STOP_WRITES.set()
                record("successor", group["group_id"], "UPLOAD_OUTCOME_UNKNOWN", manifest_hash, error_type=type(error).__name__)
                raise w.SetupError("Upload outcome unknown; writes stopped") from None
            expected = w.head(metadata)
            record("successor", group["group_id"], "UPLOAD_RETURNED", manifest_hash, output_head=expected)
    else:
        expected = group["output_head"]
    result = verify_jpeg(api, group, expected)
    assert_file(api.metadata(owner["source_id"]), owner["source_head"], owner["source_path"])
    record("successor", group["group_id"], "SUCCESSOR_VERIFIED", manifest_hash,
           method=group["method"], source_ids=group["source_ids"], **result)


def successors(manifest, manifest_hash, grant):
    pending = [g for g in manifest["groups"] if not saved("successor", g["group_id"])]
    # Exercise one real upload and complete its readback before the remaining queue.
    pilot = next((g for g in pending if g["method"] == "CREATE_MAXIMUM_QUALITY_JPEG"), None)
    if pilot:
        prepare_successor(pilot, manifest, manifest_hash, grant)
        pending.remove(pilot)
        print("Pilot JPEG uploaded and independently verified", flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(prepare_successor, g, manifest, manifest_hash, grant) for g in pending]
        count = len(manifest["groups"]) - len(pending)
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                STOP_WRITES.set()
                for queued in futures:
                    queued.cancel()
                raise
            count += 1
            if count % 10 == 0 or count == len(manifest["groups"]):
                print(f"JPEG successors independently verified: {count}/{len(manifest['groups'])}", flush=True)
    establish_lineage(manifest, manifest_hash)


def establish_lineage(manifest, manifest_hash):
    groups = {g["group_id"]: g for g in manifest["groups"]}
    relations = read_reference(manifest["evidence"]["relationships"])["records"]
    transitions, edges = [], []
    for row in manifest["ready"]:
        group = groups[row["replacement_group"]]
        state = saved("successor", group["group_id"])
        if state.get("status") != "SUCCESSOR_VERIFIED" or state["manifest_sha256"] != manifest_hash:
            raise w.SetupError("Cannot transition protection without verified JPEG")
        output = state["output_head"]
        evidence = {"source_id": row["source_id"], "source_head": row["source_head"], "output_head": output,
                    "archive_member": row["archive_member"], "backup": row["backup"],
                    "relation": "converted_to", "successor_proof": reference(state_path("successor", group["group_id"]))}
        edges.append(evidence)
        if row["protection_transition_required"]:
            dependents = [r for r in relations if r["keeper_id"] == row["source_id"]]
            if not dependents or any(r["failures"] for r in dependents):
                raise w.SetupError("Keeper dependencies remain unresolved")
            transitions.append({**evidence, "protection_role": "verified_keeper_successor",
                                "dependent_relationships": dependents,
                                "reason": "Authorized BMP retirement after exact originals were archived and full-quality successor verified."})
    registry = {"schema": "boldstone-successor-protection-registry-v1", "recorded_utc": w.now(),
                "manifest_sha256": manifest_hash, "manifest": reference(MANIFEST),
                "historical_controls_preserved": True, "historical_control_scope": "Historical imported database remains unchanged; apply this additive protection registry as well.",
                "protected_current_jpeg_ids": sorted({t["output_head"]["id"] for t in transitions}),
                "protection_transitions": transitions, "source_to_current_jpeg": edges}
    path = SHARED / "LINEAGE-AND-PROTECTIONS.json"
    if path.exists():
        old = json.loads(path.read_text())
        if any(old[k] != registry[k] for k in ("manifest_sha256", "protection_transitions", "source_to_current_jpeg")):
            raise w.SetupError("Published protection registry changed")
    else:
        w.private_json(path, registry)
    w.private_json(w.SHARED / "CURRENT-SUCCESSOR-PROTECTIONS.json", {"registry": reference(path),
                   "recorded_utc": w.now(), "status": "ACTIVE", "protected_jpeg_ids": registry["protected_current_jpeg_ids"]})
    print(f"Recorded {len(edges)} verified lineage edges and {len(transitions)} keeper-protection transitions", flush=True)


def preflight_delete(row, group, manifest, grant):
    api = api_for(grant)
    proof = current_source(api, row, manifest["archive"]["path"])
    state = saved("successor", group["group_id"])
    if state.get("status") != "SUCCESSOR_VERIFIED":
        raise w.Hold("SUCCESSOR_NOT_VERIFIED")
    proof["output_head"] = assert_file(api.metadata(state["output_head"]["id"]), state["output_head"], group["destination_path"])
    if w.fingerprint(Path(state["readback"]["path"])) != group["jpeg_fingerprint"]:
        raise w.Hold("SUCCESSOR_READBACK_PROOF_CHANGED")
    w.decode_jpeg(Path(state["readback"]["path"]), group["dimensions"])
    return proof


def delete_once(api, row, group, proof, manifest_hash):
    if (row["unresolved"] or "H01_TARGET_OR_KEEPER" in row["original_hold_reasons"]
            or PurePosixPath(row["source_path"]).suffix.casefold() != ".bmp"
            or not row["source_path"].startswith(w.ROOT_PATH + "/")
            or not row["source_id"].startswith("id:") or not row["source_head"].get("rev")):
        raise w.Hold("SOURCE_NOT_CLEARED_FOR_RETIREMENT")
    state = saved("successor", group["group_id"])
    if (state.get("status") != "SUCCESSOR_VERIFIED" or state["output_head"]["id"] == row["source_id"]
            or PurePosixPath(state["output_head"]["path"]).parent != PurePosixPath(row["source_path"]).parent):
        raise w.Hold("SUCCESSOR_NOT_VERIFIED_IN_SOURCE_PARENT")
    if any(proof[k].get(f) != expected.get(f) for k, expected in
           (("source_head", row["source_head"]), ("output_head", state["output_head"]))
           for f in ("id", "rev", "size", "content_hash")):
        raise w.Hold("PREFLIGHT_REVISION_OR_HASH_CHANGED")
    record("retirement", row["source_id"], "DELETE_INTENT", manifest_hash,
           source_path=row["source_path"], expected_source=row["source_head"], expected_output=state["output_head"], preflight=proof)
    w.BUDGET.wait()
    try:
        result = api.client.files_delete_v2(row["source_id"], parent_rev=row["source_head"]["rev"])
    except Exception as error:  # noqa: BLE001 -- Unknown outcomes require reconciliation, never retry.
        record("retirement", row["source_id"], "DELETE_OUTCOME_UNKNOWN", manifest_hash, error_type=type(error).__name__)
        raise w.SetupError("Delete outcome unknown; writes stopped") from None
    receipt = assert_file(result.metadata, row["source_head"], row["source_path"])
    record("retirement", row["source_id"], "DELETE_RETURNED", manifest_hash, receipt=receipt)


def verify_deletion(row, group, grant):
    api = api_for(grant)
    if api.metadata(row["source_id"]) is not None:
        raise w.Hold("DELETED_SOURCE_STILL_PRESENT")
    output = saved("successor", group["group_id"])["output_head"]
    return {"source_absent_by_id": True, "output_head": assert_file(api.metadata(output["id"]), output, group["destination_path"]), "checked_utc": w.now()}


def library_gate(manifest, grant):
    api = w.API(grant)
    try:
        current = census(api)
    finally:
        api.close()
    before = read_reference(manifest["evidence"]["baseline_census"])
    successor_states = [saved("successor", g["group_id"]) for g in manifest["groups"]]
    additions = [s["output_head"] for s in successor_states if s.get("status") == "SUCCESSOR_VERIFIED" and s["method"] == "CREATE_MAXIMUM_QUALITY_JPEG"]
    deleted = {r["source_id"] for r in manifest["ready"] if saved("retirement", r["source_id"]).get("status") == "DELETED_VERIFIED"}
    failures = compare_retirement({**before, "entries": before["entries"] + additions}, current, deleted)
    if failures:
        w.private_json(RUN / "pre-mutation-library-differences.json", failures)
        raise w.SetupError("Library differs from reviewed state and verified operation receipts")
    w.private_json(RUN / "pre-mutation-library-check.json", {"status": "PASS", "recorded_utc": w.now(),
                   "census": reference(audit.save_evidence("held-resolution-pre-mutation-census", current))})


def retire(manifest, manifest_hash, grant):
    establish_lineage(manifest, manifest_hash)
    groups = {g["group_id"]: g for g in manifest["groups"]}
    # Retire extra copies before protected keepers. Every replacement is already verified.
    rows = sorted([r for r in manifest["ready"] if not saved("retirement", r["source_id"])],
                  key=lambda r: (r["protection_transition_required"], r["source_path"]))
    batches = [rows[:1]] + [rows[i:i + 5] for i in range(1, len(rows), 5)] if rows else []
    api = w.API(grant)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for index, batch in enumerate(batches, 1):
                check_controls(manifest)
                root = api.metadata(w.ROOT_ID)
                if not isinstance(root, FolderMetadata) or root.path_display != w.ROOT_PATH:
                    raise w.Hold("ROOT_CHANGED")
                for row in batch:
                    w.validate_folders(api, row)
                futures = [(r, pool.submit(preflight_delete, r, groups[r["replacement_group"]], manifest, grant)) for r in batch]
                ready = [(r, future.result()) for r, future in futures]
                for row, proof in ready:
                    delete_once(api, row, groups[row["replacement_group"]], proof, manifest_hash)
                checks = [(r, pool.submit(verify_deletion, r, groups[r["replacement_group"]], grant)) for r in batch]
                for row, future in checks:
                    record("retirement", row["source_id"], "DELETED_VERIFIED", manifest_hash, verification=future.result())
                completed = sum(saved("retirement", r["source_id"]).get("status") == "DELETED_VERIFIED" for r in manifest["ready"])
                status = {"state": "RUNNING", "recorded_utc": w.now(), "deleted_verified": completed,
                          "total": len(manifest["ready"]), "batch": index, "batches": len(batches)}
                w.private_json(RUN / "status.json", status)
                print(f"Retirement batch {index}/{len(batches)}: {completed}/{len(manifest['ready'])} deleted and verified", flush=True)
    finally:
        api.close()


def final_audit(manifest, manifest_hash, grant):
    api = w.API(grant)
    try:
        current = census(api)
    finally:
        api.close()
    before = read_reference(manifest["evidence"]["baseline_census"])
    states = [saved("retirement", r["source_id"]) for r in manifest["ready"]]
    deleted = {s["identifier"] for s in states if s.get("status") == "DELETED_VERIFIED"}
    successors = [saved("successor", g["group_id"]) for g in manifest["groups"]]
    new = [s["output_head"] for s in successors if s.get("status") == "SUCCESSOR_VERIFIED" and s["method"] == "CREATE_MAXIMUM_QUALITY_JPEG"]
    expected = {**before, "entries": before["entries"] + new}
    failures = compare_retirement(expected, current, deleted)
    live = {r["id"]: r for r in current["entries"]}
    for state in successors:
        if state.get("status") != "SUCCESSOR_VERIFIED":
            failures.append({"reason": "SUCCESSOR_UNVERIFIED"})
            continue
        output = state["output_head"]
        if any(live.get(output["id"], {}).get(k) != output.get(k) for k in ("id", "rev", "size", "content_hash", "path")):
            failures.append({"reason": "SUCCESSOR_CHANGED", "id": output["id"]})
    if reference(Path(manifest["archive"]["path"]))["sha256"] != manifest["archive"]["sha256"]:
        failures.append({"reason": "ARCHIVE_CHANGED"})
    check_controls(manifest)
    unresolved = [s for s in states if s.get("status") != "DELETED_VERIFIED"]
    census_path = reference(audit.save_evidence("held-bmp-resolution-final-census", current))
    summary = {"schema": "boldstone-held-bmp-resolution-completion-v1", "completed_utc": w.now(),
               "status": "PASS" if not failures and not unresolved else "REVIEW_REQUIRED",
               "manifest": reference(MANIFEST), "manifest_sha256": manifest_hash,
               "deleted": len(deleted), "deleted_ids": sorted(deleted), "new_jpegs": len(new),
               "reused_jpegs": len(successors) - len(new), "protected_keeper_transitions": manifest["counts"]["keeper_protection_transitions"],
               "remaining_bmps": sum(r["kind"] == "file" and r["name"].casefold().endswith(".bmp") for r in live.values()),
               "held": manifest["held"], "files": sum(r["kind"] == "file" for r in live.values()),
               "folders": sum(r["kind"] == "folder" for r in live.values()), "archive": manifest["archive"],
               "lineage_and_protections": reference(SHARED / "LINEAGE-AND-PROTECTIONS.json"),
               "final_census": census_path, "failures": failures, "unresolved_operations": unresolved,
               "jpeg_quality": 100, "jpeg_subsampling": 0, "original_dimensions_preserved": True,
               "existing_jpegs_and_other_files_unchanged": not failures,
               "historical_control_records_unchanged": True, "no_permanent_deletion": True}
    w.private_json(SHARED / "COMPLETION.json", summary)
    w.private_json(RUN / "completion.json", summary)
    w.private_json(RUN / "status.json", {"state": "COMPLETED_WITH_DECISIONS_PENDING" if summary["status"] == "PASS" else "REVIEW_REQUIRED",
                   "recorded_utc": w.now(), "deleted_verified": len(deleted), "total": len(manifest["ready"]),
                   "remaining_bmps": summary["remaining_bmps"], "completion_report": reference(SHARED / "COMPLETION.json")})
    w.private_json(ARCHIVE_DIR / "RESOLUTION-REPORT.json", summary)
    w.private_json(ARCHIVE_DIR / "LINEAGE-AND-PROTECTIONS.json", json.loads((SHARED / "LINEAGE-AND-PROTECTIONS.json").read_text()))
    if summary["status"] == "PASS":
        w.private_json(w.RUNTIME / "latest-library-state.json", {"updated_utc": w.now(), "state": "HELD_BMP_RESOLUTION_VERIFIED", "report": reference(SHARED / "COMPLETION.json"), "remaining_bmps": summary["remaining_bmps"], "final_census": census_path})
        w.private_json(w.SHARED / "HELD-RESOLUTION-HANDOVER.json", {"status": "PASS", "recorded_utc": w.now(),
                       "report": reference(SHARED / "COMPLETION.json"), "active_successor_protections": reference(SHARED / "LINEAGE-AND-PROTECTIONS.json"),
                       "original_historical_plans_and_reports_unchanged": True})
    print(json.dumps({k: summary[k] for k in ("status", "deleted", "new_jpegs", "reused_jpegs", "remaining_bmps", "files", "folders", "failures")}, indent=2), flush=True)
    return 0 if summary["status"] == "PASS" else 2


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("successors", "retire", "audit"))
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    with (w.RUN_PATH / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = json.loads(MANIFEST.read_text())
        validate(manifest, args.manifest_sha256)
        grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
        w.verify_grant(grant)
        w.BUDGET = RetirementBudget()
        if args.phase != "audit":
            library_gate(manifest, grant)
        if args.phase == "successors":
            successors(manifest, args.manifest_sha256, grant)
            return 0
        if args.phase == "retire":
            retire(manifest, args.manifest_sha256, grant)
        return final_audit(manifest, args.manifest_sha256, grant)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (w.Hold, w.SetupError) as error:
        print("Held resolution stopped: " + str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as error:  # noqa: BLE001 -- Keep token-bearing diagnostics private.
        print("Held resolution stopped without retry: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
