"""Finish the three explicitly reviewed and subsequently approved BMP retirements.

This is an exact three-file approval, not a general hold override. Earlier plans,
controls and reports remain immutable. No remote write is retried automatically.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import zipfile
from pathlib import Path, PurePosixPath

import audit_conversion as audit
import convert_bmps as w
from check_bmp_retirement import (
    census,
    database_controls,
    link_record,
    reference,
    sharing_flags,
)
from dropbox.files import ListRevisionsMode
from dropbox.sharing import FileAction
from inspect_held_bmps import RUN as PREVIOUS_RUN
from inspect_held_bmps import SHARED as PREVIOUS_SHARED
from inspect_held_bmps import inspect_jpeg, key
from prepare_held_resolution import ARCHIVE_DIR, choose_prior_successor
from retire_bmps import (
    RetirementBudget,
    assert_file,
    compare_retirement,
    fingerprint_stream,
    read_reference,
)

TARGET = "id:cnqzTNngPVsAAAAAAAuWiw"
KEEPER = "id:cnqzTNngPVsAAAAAAAuWdA"
MOON = "id:cnqzTNngPVsAAAAAAArs3g"
IDS = {TARGET, KEEPER, MOON}
PUBLIC_LINK_HASH = "07450a628f1da50948b12b7eaf8f069e454bae36876d6f2158facc82deb5f76e"
INSTRUCTION = "As long as there are jpeg versions, delete them, otherwise make te jpegs and then delete"
RUN = w.RUNTIME / "final-three-bmps"
SHARED = w.SHARED / "final-three-bmps"
MANIFEST = SHARED / "manifest.json"
OTHER_CLEANUP = Path.home() / "Library/Application Support/BoldstoneImageConsistency/review-20261015T223009Z"


def state(kind, identifier):
    path = RUN / "states" / (kind + "-" + key(identifier) + ".json")
    return json.loads(path.read_text()) if path.exists() else {}


def record(kind, identifier, status, digest, **details):
    event = {**state(kind, identifier), "kind": kind, "id": identifier, "status": status,
             "manifest_sha256": digest, "recorded_utc": w.now(), **details}
    w.private_json(RUN / "states" / (kind + "-" + key(identifier) + ".json"), event)
    fd = os.open(SHARED / "operations.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return event


def approved_scope(manifest):
    approval = read_reference(manifest["approval"])
    if (approval["user_instruction"] != INSTRUCTION or set(approval["source_ids"]) != IDS
            or not approval["h01_clearance_for_exact_actions"] or not approval["moonphase_link_loss_accepted"]
            or {r["source_id"] for r in manifest["rows"]} != IDS or len(manifest["rows"]) != 3):
        raise w.Hold("EXACT_THREE_FILE_APPROVAL_REQUIRED")


def sharing_guard(identifier, metadata, links):
    flags = sharing_flags(metadata)
    if (flags["has_explicit_shared_members"] is not False or flags["sharing_info_present"]
            or flags["read_only"] or flags["file_lock_present"]):
        raise w.Hold("MEMBERSHIP_LOCK_OR_READ_ONLY_CHANGED")
    if identifier not in IDS:
        raise w.Hold("SOURCE_OUTSIDE_EXACT_APPROVAL")
    for link in links:
        if link["resolved_visibility"] in ("no_one", "only_you") and link["effective_audience"] in ("no_one", None):
            continue
        if identifier != MOON or link["url_sha256"] != PUBLIC_LINK_HASH:
            raise w.Hold("UNAPPROVED_PUBLIC_LINK")


def current_source(api, row):
    w.validate_folders(api, row)
    metadata = api.read("files_get_metadata", row["source_id"], include_has_explicit_shared_members=True)
    result = assert_file(metadata, row["source_head"], row["source_path"])
    response = api.read("sharing_list_shared_links", path=row["source_id"], direct_only=True)
    if response.has_more:
        raise w.Hold("INCOMPLETE_LINK_LIST")
    links = [link_record(link) for link in response.links]
    sharing_guard(row["source_id"], metadata, links)
    if sorted(links, key=lambda r: r["url_sha256"]) != sorted(row["direct_links"], key=lambda r: r["url_sha256"]):
        raise w.Hold("DIRECT_LINK_STATE_CHANGED")
    return {"source_head": result, "direct_links": links, "checked_utc": w.now()}


def controls_unchanged(expected):
    current = database_controls()
    if any(current[k] != expected[k] for k in ("protections", "holds", "lineage")):
        raise w.Hold("HISTORICAL_CONTROLS_CHANGED")


def completed_other_cleanup():
    """Verify receipts; prepare then independently checks the complete live census."""
    notices = sorted(OTHER_CLEANUP.glob("DELETION-COMPLETED-*.json"))
    if notices:
        notice = json.loads(notices[-1].read_text())
        completion = read_reference(notice["completion"])
        if completion["status"] != "PASS_COMPLETE_INDEPENDENTLY_VERIFIED":
            raise w.Hold("OTHER_CLEANUP_NOT_VERIFIED")
        execution_reference = completion["execution_completion"]
        evidence = {"completion": notice["completion"]}
    else:
        execution_reference = reference(OTHER_CLEANUP / "cleanup-execution/Execution_Completion.json")
        link_reference = reference(RUN / "separate-cleanup-link-review.json")
        links = read_reference(link_reference)
        if links["status"] != "PASS_EXPECTED_OWNER_LINK_REMOVALS" or links["added"]:
            raise w.Hold("OTHER_CLEANUP_LINK_CHANGES_UNRESOLVED")
        evidence = {"sharing_review": link_reference,
                    "original_audit_issue": "Post-deletion link comparison included four owner-only links to approved deleted files. Their removal was independently reviewed; no public or inherited link changed."}
    execution = read_reference(execution_reference)
    deleted = set(execution["deleted_verified_ids"])
    approval_reference = reference(OTHER_CLEANUP / "cleanup-plan/Exact_Chat_Approval.json")
    subset_reference = reference(OTHER_CLEANUP / "report-v3/Exact_Current_Execution_Subset.json")
    approval = read_reference(approval_reference)
    subset = read_reference(subset_reference)
    operations = [op for child in subset["children"] for op in child["operations"]]
    if (approval["approved_subset_sha256"] != subset_reference["sha256"]
            or execution["manifest_sha256"] != approval["manifest_sha256"]
            or deleted != {op["target"]["id"] for op in operations}
            or execution["failed"] or execution["held"] or len(deleted) != 1854
            or deleted & (IDS | {"id:cnqzTNngPVsAAAAAAA51-g"})):
        raise w.Hold("OTHER_CLEANUP_CONFLICT_OR_UNRESOLVED_OUTCOME")
    for child in subset["children"]:
        receipt = json.loads((OTHER_CLEANUP / "cleanup-execution" / (child["child_id"] + "-terminal-receipt.json")).read_text())
        parent_check = json.loads((OTHER_CLEANUP / "cleanup-execution" / (child["child_id"] + "-independent-parent-verification.json")).read_text())
        targets = {op["target"]["id"]: op["target"] for op in child["operations"]}
        if receipt["status"] != "complete" or len(receipt["entries"]) != len(targets) or set(parent_check["deleted_ids"]) != set(targets):
            raise w.Hold("OTHER_CLEANUP_BATCH_EVIDENCE_MISMATCH")
        for item in receipt["entries"]:
            actual = item.get("metadata", {})
            if item["status"] != "success" or actual.get("id") not in targets or any(actual[k] != targets[actual["id"]][k] for k in ("id", "rev", "size", "content_hash")):
                raise w.Hold("OTHER_CLEANUP_RECEIPT_MISMATCH")
    proof = {"status": "RECEIPTS_VERIFIED_AWAITING_CURRENT_CENSUS", "recorded_utc": w.now(), **evidence,
             "execution_completion": execution_reference, "approval": approval_reference, "subset": subset_reference,
             "deleted_ids": sorted(deleted), "batches_receipt_and_parent_verified": len(subset["children"]),
             "relation": "Separate authorized duplicate cleanup completed before this three-BMP operation."}
    w.private_json(RUN / "separate-cleanup-reconciliation.json", proof)
    return deleted


def prepare(api):
    if MANIFEST.exists():
        raise w.SetupError("Exact final-three manifest already exists")
    previous = json.loads((PREVIOUS_SHARED / "COMPLETION.json").read_text())
    if previous["status"] != "PASS" or previous["remaining_bmps"] != 3:
        raise w.SetupError("Previous resolution did not finish cleanly")
    other_deleted = completed_other_cleanup()
    current = census(api)
    failures = compare_retirement(read_reference(previous["final_census"]), current, other_deleted)
    if failures:
        w.private_json(RUN / "changed-library.json", failures)
        raise w.SetupError("Library changed since the last verified census")
    w.private_json(RUN / "baseline-census.json", current)
    live = {r["id"]: r for r in current["entries"]}
    prior_registry = read_reference(previous["lineage_and_protections"])
    prior_successors = [r["output_head"] for r in prior_registry["source_to_current_jpeg"]]
    prior_successors.extend(w.saved_state(r)["output_head"] for r in json.loads(w.PLAN_PATH.read_text())["rows"] if r["status"] == "ELIGIBLE")
    for output in prior_successors:
        if any(live.get(output["id"], {}).get(k) != output[k] for k in ("id", "rev", "size", "content_hash")):
            raise w.Hold("PRIOR_BMP_SUCCESSOR_CHANGED_DURING_OTHER_CLEANUP")
    proof_path = RUN / "separate-cleanup-reconciliation.json"
    other_proof = json.loads(proof_path.read_text())
    other_proof.update(status="PASS_INDEPENDENTLY_RECONCILED", current_census=reference(RUN / "baseline-census.json"),
                       all_other_ids_paths_revisions_and_contents_unchanged=True, all_prior_bmp_jpegs_preserved=True)
    w.private_json(proof_path, other_proof)
    inspection = json.loads((PREVIOUS_RUN / "inspection.json").read_text())
    controls_unchanged(read_reference(inspection["database_controls"]))
    approval = {"schema": "boldstone-final-bmp-owner-approval-v1", "recorded_utc": w.now(),
                "user_instruction": INSTRUCTION, "source_ids": sorted(IDS),
                "context": "User instructed deletion of these exact three files after the H01 hold and public-link consequences were explained. Create a full-quality JPEG first when missing.",
                "h01_clearance_for_exact_actions": True, "moonphase_link_loss_accepted": True,
                "other_historical_holds_released": False,
                "prior_reviews": [reference(ARCHIVE_DIR / "H01-review/REVIEW.json"), reference(ARCHIVE_DIR / "Moonphase-link-review/REVIEW.json")]}
    w.private_json(SHARED / "OWNER-APPROVAL.json", approval)
    archive = previous["archive"]
    if reference(Path(archive["path"]))["sha256"] != archive["sha256"]:
        raise w.SetupError("Original archive changed")
    rows = []
    with zipfile.ZipFile(archive["path"]) as zipped:
        archived = {r["source_id"]: r for r in json.loads(zipped.read("MANIFEST.json"))["records"]}
        for identifier in (TARGET, KEEPER, MOON):
            row = next(r.copy() for r in inspection["records"] if r["source_id"] == identifier)
            if live[identifier]["rev"] != row["source_head"]["rev"]:
                raise w.Hold("SOURCE_REVISION_CHANGED")
            row["current_check"] = current_source(api, row)
            authority = api.read("sharing_get_file_metadata", identifier, actions=[FileAction.edit_contents])
            allowed = any(p.action == FileAction.edit_contents and p.allow for p in authority.permissions)
            if authority.access_type._tag != "owner" or not allowed:
                raise w.Hold("OWNER_EDIT_AUTHORITY_NOT_CONFIRMED")
            row["current_owner_authority"] = {"access_type": "owner", "edit_contents_allowed": True, "checked_utc": w.now()}
            work = RUN / "files" / key(identifier)
            work.mkdir(parents=True, mode=0o700, exist_ok=True)
            row["archive_member"] = archived[identifier]["archive_member"]
            with zipped.open(row["archive_member"]) as original:
                if fingerprint_stream(original) != row["backup"]:
                    raise w.Hold("ARCHIVED_SOURCE_BYTES_CHANGED")
            source = work / "fresh-original.bmp"
            api.download(source, identifier, row["source_head"]["rev"])
            if w.fingerprint(source) != row["backup"]:
                raise w.Hold("FRESH_ORIGINAL_DIFFERS_FROM_ARCHIVE")
            row["work_directory"] = str(work)
            row["local_jpeg"] = w.encode_jpeg(source, work / "converted.jpg")
            history = api.read("files_list_revisions", identifier, mode=ListRevisionsMode.id, limit=100, include_restorable_info=True)
            if history.is_deleted or not history.entries or len(history.entries) >= 100 or history.entries[0].rev != row["source_head"]["rev"]:
                raise w.Hold("INCOMPLETE_OR_CHANGED_HISTORY")
            if any(h.id != identifier or h.content_hash != row["backup"]["content_hash"] or h.size != row["backup"]["size"] for h in history.entries):
                raise w.Hold("UNARCHIVED_HISTORICAL_BYTES")
            row["fresh_history"] = [w.head(h) for h in history.entries]
            row["approval_resolves"] = row["unresolved"]
            row["replacement_group"] = MOON if identifier == MOON else KEEPER
            rows.append(row)
    by_id = {r["source_id"]: r for r in rows}
    if by_id[TARGET]["backup"] != by_id[KEEPER]["backup"] or by_id[TARGET]["local_jpeg"] != by_id[KEEPER]["local_jpeg"]:
        raise w.Hold("AMMONITE_DUPLICATES_DIFFER")
    ammonite = by_id[KEEPER]
    review = read_reference(approval["prior_reviews"][0])
    destination = review["proposed_jpeg_path"]
    if api.metadata(destination) is not None:
        raise w.Hold("AMMONITE_JPEG_DESTINATION_OCCUPIED")
    groups = [{"group_id": KEEPER, "source_ids": [TARGET, KEEPER], "representative": ammonite,
               "method": "CREATE_MAXIMUM_QUALITY_JPEG", "destination_path": destination,
               "local_verified_jpeg": str(Path(ammonite["work_directory"]) / "converted.jpg"),
               "jpeg_fingerprint": {k: ammonite["local_jpeg"][k] for k in ("sha256", "content_hash", "size")},
               "dimensions": ammonite["local_jpeg"]["dimensions"], "output_head": None}]
    relations = json.loads((PREVIOUS_RUN / "relationships.json").read_text())["records"]
    prior_rows = {r["source_id"]: r for r in json.loads(w.PLAN_PATH.read_text())["rows"]}
    choice = choose_prior_successor(by_id[MOON], relations, prior_rows)
    if not choice:
        raise w.Hold("REVIEWED_MOONPHASE_SUCCESSOR_NOT_EQUIVALENT")
    groups.append({"group_id": MOON, "source_ids": [MOON], "representative": by_id[MOON],
                   "dimensions": by_id[MOON]["local_jpeg"]["dimensions"],
                   "destination_path": choice["output_head"]["path"], **choice})
    manifest = {"schema": "boldstone-final-three-bmp-manifest-v1", "created_utc": w.now(),
                "approval": reference(SHARED / "OWNER-APPROVAL.json"), "root_id": w.ROOT_ID,
                "root_path": w.ROOT_PATH, "namespace_id": w.NAMESPACE_ID, "archive": archive,
                "rows": rows, "groups": groups,
                "evidence": {"baseline": reference(RUN / "baseline-census.json"),
                             "separate_cleanup": reference(RUN / "separate-cleanup-reconciliation.json"),
                             "previous_completion": reference(PREVIOUS_SHARED / "COMPLETION.json"),
                             "previous_protections": previous["lineage_and_protections"],
                             "database_controls": inspection["database_controls"],
                             "relationships": reference(PREVIOUS_RUN / "relationships.json")},
                "policy": {"jpeg_quality": 100, "jpeg_subsampling": 0, "permanent_delete": False,
                           "conditional_revision_delete": True, "overwrite": False, "write_retry": False}}
    approved_scope(manifest)
    w.private_json(MANIFEST, manifest)
    print(json.dumps({"manifest": reference(MANIFEST), "sources": 3, "new_jpegs": 1, "reused_jpegs": 1}, indent=2), flush=True)


def verify_jpeg(api, group, expected):
    current = assert_file(api.metadata(expected["id"]), expected, group["destination_path"])
    downloaded = Path(group["representative"]["work_directory"]) / "remote-jpeg-readback.jpg"
    api.download(downloaded, current["id"], current["rev"])
    if w.fingerprint(downloaded) != group["jpeg_fingerprint"]:
        raise w.Hold("JPEG_READBACK_BYTES_DIFFER")
    check = inspect_jpeg(downloaded, Path(group["representative"]["work_directory"]) / "converted.jpg")
    if not check["verified_replacement"] or check["jpeg_quantization_max"] != 1 or check["dimensions"] != group["dimensions"]:
        raise w.Hold("JPEG_FIDELITY_CHECK_FAILED")
    assert_file(api.metadata(current["id"]), current, group["destination_path"])
    return {"output_head": {**current, "kind": "file", "name": PurePosixPath(group["destination_path"]).name,
                            "path": group["destination_path"], "parent_id": group["representative"]["parent_id"]},
            "readback": {"path": str(downloaded), **group["jpeg_fingerprint"]}, "quality_check": check}


def successor_registry(manifest, digest):
    previous = read_reference(manifest["evidence"]["previous_protections"])
    transitions = list(previous["protection_transitions"])
    edges = list(previous["source_to_current_jpeg"])
    relations = read_reference(manifest["evidence"]["relationships"])["records"]
    for row in manifest["rows"]:
        verified = state("jpeg", row["replacement_group"])
        if verified.get("status") != "JPEG_VERIFIED":
            raise w.Hold("UNVERIFIED_SUCCESSOR_FOR_PROTECTION_TRANSITION")
        edge = {"source_id": row["source_id"], "source_head": row["source_head"],
                "output_head": verified["output_head"], "relation": "converted_to", "backup": row["backup"],
                "archive_member": row["archive_member"], "approval": manifest["approval"]}
        edges.append(edge)
        if "PROTECTED_KEEPER_OR_REPLACEMENT" in row["original_hold_reasons"]:
            dependencies = [r for r in relations if r["keeper_id"] == row["source_id"]]
            if not dependencies or any(r["failures"] for r in dependencies):
                raise w.Hold("UNRESOLVED_KEEPER_DEPENDENCY")
            transitions.append({**edge, "protection_role": "verified_keeper_successor", "dependent_relationships": dependencies})
    registry = {"schema": "boldstone-successor-protection-registry-v2", "recorded_utc": w.now(),
                "manifest_sha256": digest, "previous_registry": manifest["evidence"]["previous_protections"],
                "historical_controls_preserved": True, "approval": manifest["approval"],
                "h01_clearance_limited_to_ids": [TARGET, KEEPER],
                "protected_current_jpeg_ids": sorted({r["output_head"]["id"] for r in transitions}),
                "protection_transitions": transitions, "source_to_current_jpeg": edges}
    w.private_json(SHARED / "LINEAGE-AND-PROTECTIONS.json", registry)
    w.private_json(w.SHARED / "CURRENT-SUCCESSOR-PROTECTIONS.json", {"registry": reference(SHARED / "LINEAGE-AND-PROTECTIONS.json"),
                   "recorded_utc": w.now(), "status": "ACTIVE", "protected_jpeg_ids": registry["protected_current_jpeg_ids"]})


def delete_once(api, manifest, row, output, digest):
    approved_scope(manifest)
    if row["source_id"] not in IDS or PurePosixPath(row["source_path"]).suffix.casefold() != ".bmp":
        raise w.Hold("SOURCE_NOT_IN_EXACT_RETIREMENT_APPROVAL")
    if (not row["source_path"].startswith(w.ROOT_PATH + "/") or output["id"] == row["source_id"]
            or PurePosixPath(output["path"]).parent != PurePosixPath(row["source_path"]).parent):
        raise w.Hold("SOURCE_OR_SUCCESSOR_SCOPE_CHANGED")
    controls_unchanged(read_reference(manifest["evidence"]["database_controls"]))
    proof = current_source(api, row)
    assert_file(api.metadata(output["id"]), output, output["path"])
    with zipfile.ZipFile(manifest["archive"]["path"]) as archive, archive.open(row["archive_member"]) as source:
        if fingerprint_stream(source) != row["backup"]:
            raise w.Hold("ARCHIVE_MEMBER_CHANGED")
    record("delete", row["source_id"], "DELETE_INTENT", digest, source_head=row["source_head"], output_head=output, preflight=proof)
    w.BUDGET.wait()
    try:
        receipt = api.client.files_delete_v2(row["source_id"], parent_rev=row["source_head"]["rev"])
    except Exception as error:  # noqa: BLE001 -- No retry and no credential-bearing diagnostics.
        record("delete", row["source_id"], "DELETE_OUTCOME_UNKNOWN", digest, error_type=type(error).__name__)
        raise w.SetupError("Delete outcome unknown; stopped for read-only reconciliation") from None
    record("delete", row["source_id"], "DELETE_RETURNED", digest, receipt=assert_file(receipt.metadata, row["source_head"], row["source_path"]))
    if api.metadata(row["source_id"]) is not None:
        raise w.Hold("DELETED_SOURCE_STILL_PRESENT")
    assert_file(api.metadata(output["id"]), output, output["path"])
    record("delete", row["source_id"], "DELETED_VERIFIED", digest, source_absent_by_id=True)
    print("Deleted and verified: " + PurePosixPath(row["source_path"]).name, flush=True)


def execute(api, digest):
    if reference(MANIFEST)["sha256"] != digest:
        raise w.SetupError("Exact manifest hash required")
    manifest = json.loads(MANIFEST.read_text())
    approved_scope(manifest)
    for evidence in manifest["evidence"].values():
        read_reference(evidence)
    if any((RUN / "states").glob("*.json")):
        raise w.SetupError("An operation already started; reconcile rather than replay")
    current = census(api)
    if compare_retirement(read_reference(manifest["evidence"]["baseline"]), current, set()):
        raise w.Hold("LIBRARY_CHANGED_AFTER_PREPARATION")
    if reference(Path(manifest["archive"]["path"]))["sha256"] != manifest["archive"]["sha256"]:
        raise w.Hold("ARCHIVE_CHANGED")
    for group in manifest["groups"]:
        current_source(api, group["representative"])
        local = Path(group["local_verified_jpeg"])
        if w.fingerprint(local) != group["jpeg_fingerprint"]:
            raise w.Hold("LOCAL_JPEG_CHANGED")
        expected = group["output_head"]
        if group["method"] == "CREATE_MAXIMUM_QUALITY_JPEG":
            if api.metadata(group["destination_path"]) is not None:
                raise w.Hold("JPEG_DESTINATION_OCCUPIED")
            record("jpeg", group["group_id"], "UPLOAD_INTENT", digest, destination=group["destination_path"], fingerprint=group["jpeg_fingerprint"])
            try:
                expected = w.head(api.upload(local, group["destination_path"], group["representative"]["source_head"]["client_modified"]))
            except Exception as error:  # noqa: BLE001 -- No blind write retry.
                record("jpeg", group["group_id"], "UPLOAD_OUTCOME_UNKNOWN", digest, error_type=type(error).__name__)
                raise w.SetupError("Upload outcome unknown; stopped for reconciliation") from None
            record("jpeg", group["group_id"], "UPLOAD_RETURNED", digest, output_head=expected)
        proof = verify_jpeg(api, group, expected)
        current_source(api, group["representative"])
        record("jpeg", group["group_id"], "JPEG_VERIFIED", digest, method=group["method"], **proof)
        print("Maximum-quality JPEG independently verified: " + PurePosixPath(group["destination_path"]).name, flush=True)
    successor_registry(manifest, digest)
    for row in manifest["rows"]:
        output = state("jpeg", row["replacement_group"])["output_head"]
        delete_once(api, manifest, row, output, digest)
    final = census(api)
    additions = [state("jpeg", g["group_id"])["output_head"] for g in manifest["groups"] if g["method"] == "CREATE_MAXIMUM_QUALITY_JPEG"]
    before = read_reference(manifest["evidence"]["baseline"])
    failures = compare_retirement({**before, "entries": before["entries"] + additions}, final, IDS)
    remaining = [r for r in final["entries"] if r["kind"] == "file" and r["name"].casefold().endswith(".bmp")]
    if remaining:
        failures.append({"reason": "BMP_FILES_REMAIN", "ids": [r["id"] for r in remaining]})
    if reference(Path(manifest["archive"]["path"]))["sha256"] != manifest["archive"]["sha256"]:
        failures.append({"reason": "ARCHIVE_CHANGED"})
    controls_unchanged(read_reference(manifest["evidence"]["database_controls"]))
    result = {"schema": "boldstone-final-bmp-retirement-completion-v1", "completed_utc": w.now(),
              "status": "PASS" if not failures else "REVIEW_REQUIRED", "manifest": reference(MANIFEST),
              "approval": manifest["approval"], "deleted_this_run": 3, "total_original_bmps_retired": 642,
              "remaining_bmps": len(remaining), "new_jpegs_this_run": 1, "reused_jpegs_this_run": 1,
              "jpeg_quality": 100, "jpeg_subsampling": 0, "original_dimensions_preserved": True,
              "source_ids": sorted(IDS), "successors": [state("jpeg", g["group_id"])["output_head"] for g in manifest["groups"]],
              "files": sum(r["kind"] == "file" for r in final["entries"]), "folders": sum(r["kind"] == "folder" for r in final["entries"]),
              "final_census": reference(audit.save_evidence("final-bmp-retirement-census", final)),
              "archive": manifest["archive"], "lineage_and_protections": reference(SHARED / "LINEAGE-AND-PROTECTIONS.json"),
              "old_moonphase_bmp_public_link_retired_with_source": True, "public_link_loss_explicitly_accepted": True,
              "historical_control_records_preserved": True, "other_historical_holds_released": False,
              "all_previous_jpegs_and_other_entries_unchanged": not failures, "failures": failures}
    w.private_json(SHARED / "COMPLETION.json", result)
    w.private_json(RUN / "completion.json", result)
    w.private_json(ARCHIVE_DIR / "FINAL-ALL-BMPS-REPORT.json", result)
    w.private_json(ARCHIVE_DIR / "FINAL-LINEAGE-AND-PROTECTIONS.json", json.loads((SHARED / "LINEAGE-AND-PROTECTIONS.json").read_text()))
    if not failures:
        handover = {"status": "PASS", "state": "ALL_642_BMPS_RETIRED", "recorded_utc": w.now(),
                    "remaining_bmps": 0, "completion": reference(SHARED / "COMPLETION.json"),
                    "final_census": result["final_census"], "approval": manifest["approval"],
                    "active_successor_protections": result["lineage_and_protections"]}
        w.private_json(w.RUNTIME / "latest-library-state.json", handover)
        w.private_json(w.SHARED / "FINAL-BMP-RETIREMENT-HANDOVER.json", handover)
        w.private_json(RUN / "status.json", handover)
    print(json.dumps({k: result[k] for k in ("status", "deleted_this_run", "remaining_bmps", "files", "folders", "failures")}, indent=2), flush=True)
    return 0 if not failures else 2


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "execute"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    RUN.mkdir(parents=True, mode=0o700, exist_ok=True)
    SHARED.mkdir(parents=True, mode=0o700, exist_ok=True)
    with (w.RUN_PATH / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        w.validate_plan(json.loads(w.PLAN_PATH.read_text()))
        grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
        w.verify_grant(grant)
        w.BUDGET = RetirementBudget()
        api = w.API(grant)
        try:
            if args.phase == "prepare":
                prepare(api)
                return 0
            return execute(api, args.manifest_sha256)
        finally:
            api.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (w.Hold, w.SetupError) as error:
        print("Final BMP retirement stopped: " + str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception as error:  # noqa: BLE001 -- Do not print token-bearing exception details.
        print("Final BMP retirement stopped without retry: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
