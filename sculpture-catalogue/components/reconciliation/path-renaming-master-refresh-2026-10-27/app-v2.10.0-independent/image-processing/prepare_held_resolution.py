"""Archive all held sources and freeze evidence-based successor/protection decisions."""
from __future__ import annotations

import collections
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import convert_bmps as w
from check_bmp_retirement import reference
from inspect_held_bmps import RUN, SHARED, inspect_jpeg
from PIL import Image

ARCHIVE_DIR = Path.home() / "BoldstoneMigration/remaining-bmp-originals-20261015"
ARCHIVE = ARCHIVE_DIR / "Remaining_BMP_Originals_2026-10-15.zip"
MANIFEST = SHARED / "manifest.json"


def archive_originals(inspection):
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    records = []
    for row in inspection["records"]:
        path = Path(row["work_directory"]) / "original.bmp"
        if w.fingerprint(path) != row["backup"]:
            raise w.SetupError("Held original backup changed")
        records.append({"source_id": row["source_id"], "source_head": row["source_head"],
                        "backup": row["backup"], "dimensions": row["local_jpeg"]["dimensions"],
                        "path": str(path), "archive_member": "originals/" + str(PurePosixPath(row["source_path"]).relative_to(w.ROOT_PATH)),
                        "available_history": row["available_history"]})
    if not ARCHIVE.exists():
        partial = ARCHIVE.with_suffix(".zip.partial")
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for row in records:
                archive.write(row["path"], row["archive_member"])
            archive.writestr("MANIFEST.json", json.dumps({"records": records}, indent=2, sort_keys=True) + "\n")
            archive.writestr("README.txt", "Exact lossless originals for the 232 remaining BMPs. JPEG quality 100 is still lossy.\n"
                             "Preserve this archive. Every original is tied to its Dropbox ID, revision and hashes.\n"
                             "Available historical revisions are recorded in MANIFEST.json; all contain the archived bytes.\n")
        with partial.open("rb") as handle:
            os.fsync(handle.fileno())
        partial.rename(ARCHIVE)
    proofs = []
    with zipfile.ZipFile(ARCHIVE) as archive, tempfile.TemporaryDirectory(prefix="restore-", dir=ARCHIVE_DIR) as temporary:
        if json.loads(archive.read("MANIFEST.json"))["records"] != records:
            raise w.SetupError("Archive manifest differs")
        for index, row in enumerate(records, 1):
            path = Path(temporary) / "restored.bmp"
            path.write_bytes(archive.read(row["archive_member"]))
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
            actual = w.fingerprint(path)
            if actual != row["backup"]:
                raise w.SetupError("Archive restoration hash mismatch")
            with Image.open(path) as image:
                image.load()
                if image.format != "BMP" or list(image.size) != row["dimensions"]:
                    raise w.SetupError("Archive restoration decode mismatch")
            proofs.append({"source_id": row["source_id"], "archive_member": row["archive_member"],
                           **actual, "restore_and_decode_passed": True})
            if index % 50 == 0 or index == len(records):
                print(f"Remaining-original archive restore-tested: {index}/{len(records)}", flush=True)
    result = {"status": "PASS", "recorded_utc": w.now(), "archive": {**reference(ARCHIVE), "size": ARCHIVE.stat().st_size},
              "original_bytes": sum(r["size"] for r in proofs), "records": proofs}
    w.private_json(ARCHIVE_DIR / "RESTORE-VERIFICATION.json", result)
    w.private_json(RUN / "archive-proof.json", result)
    return result


def choose_prior_successor(row, relations, prior_rows):
    for relation in sorted(relations, key=lambda r: r["target_id"]):
        if relation["keeper_id"] != row["source_id"] or relation["target_disposition"] != "PREVIOUSLY_CONVERTED_AND_RETIRED":
            continue
        if relation["failures"] or relation["original_backup"] != row["backup"]:
            continue
        prior = w.saved_state(prior_rows[relation["target_id"]])
        candidate = Path(prior.get("readback_proof", Path(prior["work_directory"]) / "downloaded-output.jpg"))
        if w.fingerprint(candidate) != {k: prior["local_jpeg"][k] for k in ("sha256", "content_hash", "size")}:
            raise w.SetupError("Prior verified JPEG readback changed")
        check = inspect_jpeg(candidate, Path(row["work_directory"]) / "converted.jpg")
        if check["verified_replacement"] and relation["surviving_jpeg_head"]["parent_id"] == row["parent_id"]:
            return {"method": "REUSE_VERIFIED_PRIOR_CONVERSION", "output_head": relation["surviving_jpeg_head"],
                    "local_verified_jpeg": str(candidate), "jpeg_fingerprint": check["fingerprint"],
                    "equivalence_check": check, "duplicate_source_id": relation["target_id"],
                    "duplicate_group": relation["historical_group"]}
    return None


def build_plan(inspection, relations, archive):
    if inspection["relationship_failures"]:
        raise w.SetupError("Keeper dependencies did not pass")
    if any(r.get("historical_backups") for r in inspection["records"]):
        raise w.SetupError("Unique older versions need a larger archive manifest")
    by_id = {r["source_id"]: r for r in inspection["records"]}
    prior_rows = {r["source_id"]: r for r in json.loads(w.PLAN_PATH.read_text())["rows"]}
    current = json.loads(Path(inspection["pre_resolution_census"]["path"]).read_text())
    by_path = {r["path"].casefold(): r for r in current["entries"]}
    parent = {r["target_id"]: r["keeper_id"] for r in relations if r["target_id"] in by_id}

    def representative(identifier):
        seen = set()
        while identifier in parent:
            if identifier in seen:
                raise w.SetupError("Duplicate lineage cycle")
            seen.add(identifier)
            identifier = parent[identifier]
        return identifier

    ready, held = [], []
    additional_path = RUN / "additional-jpeg-reviews.json"
    additional = json.loads(additional_path.read_text())["records"] if additional_path.exists() else []
    for row in inspection["records"]:
        owner_id = representative(row["source_id"])
        owner = by_id[owner_id]
        reasons = sorted(set(row["unresolved"] + owner["unresolved"]))
        if reasons:
            held.append({"source_id": row["source_id"], "source_path": row["source_path"], "reasons": reasons})
            continue
        if row["backup"] != owner["backup"] or row["parent_id"] != owner["parent_id"]:
            raise w.SetupError("A duplicate does not match its representative")
        ready.append({**row, "replacement_group": owner_id,
                      "archive_member": next(a["archive_member"] for a in archive["records"] if a["source_id"] == row["source_id"]),
                      "protection_transition_required": "PROTECTED_KEEPER_OR_REPLACEMENT" in row["original_hold_reasons"],
                      "resolved_reasons": row["original_hold_reasons"],
                      "retirement_status": "READY_AFTER_SUCCESSOR_VERIFICATION"})
    groups, destinations = [], set()
    for owner_id in sorted({r["replacement_group"] for r in ready}):
        owner = by_id[owner_id]
        choice = choose_prior_successor(owner, relations, prior_rows)
        if choice is None:
            candidates = owner["existing_jpegs"] + [j for j in additional if j["source_id"] == owner_id]
            existing = next((j for j in candidates if j["verified_replacement"]), None)
            if existing:
                choice = {"method": "REUSE_VERIFIED_EXISTING_JPEG", "output_head": existing["head"],
                          "local_verified_jpeg": existing["local_path"], "jpeg_fingerprint": existing["fingerprint"]}
            else:
                destination = owner["destination_path"] if not owner["collision_ids"] else str(PurePosixPath(owner["source_path"]).with_suffix("")) + "__from-bmp.jpg"
                if destination.casefold() in by_path:
                    if not any(j["head"]["id"] == by_path[destination.casefold()]["id"] for j in candidates):
                        raise w.SetupError("An occupied alternate JPEG requires inspection")
                    destination = str(PurePosixPath(owner["source_path"]).with_suffix("")) + "__from-bmp-q100.jpg"
                if destination.casefold() in by_path or destination.casefold() in destinations:
                    raise w.SetupError("Planned JPEG path is already occupied")
                if len(PurePosixPath(destination).name.encode("utf-8")) > 255:
                    raise w.SetupError("Planned JPEG basename is too long")
                destinations.add(destination.casefold())
                choice = {"method": "CREATE_MAXIMUM_QUALITY_JPEG", "output_head": None,
                          "destination_path": destination,
                          "local_verified_jpeg": str(Path(owner["work_directory"]) / "converted.jpg"),
                          "jpeg_fingerprint": {k: owner["local_jpeg"][k] for k in ("sha256", "content_hash", "size")}}
        if choice["output_head"]:
            choice["destination_path"] = choice["output_head"]["path"]
        groups.append({"group_id": owner_id, "representative": owner,
                       "source_ids": [r["source_id"] for r in ready if r["replacement_group"] == owner_id],
                       "dimensions": owner["local_jpeg"]["dimensions"], **choice})
    counts = {"bmp_sources_to_retire": len(ready), "held_for_specific_decisions": len(held),
              "successor_groups": len(groups), "successor_methods": dict(collections.Counter(g["method"] for g in groups)),
              "keeper_protection_transitions": sum(r["protection_transition_required"] for r in ready),
              "duplicate_bmps_sharing_a_successor": len(ready) - len(groups),
              "old_jpeg_files_preserved": inspection["existing_jpegs"]}
    return {"schema": "boldstone-held-bmp-resolution-plan-v1", "created_utc": w.now(),
            "authorization": {"instruction": "Can you resolve these: 232 BMPs remain because of protection holds or unverified replacements.",
                              "prior_instruction": "Do the checks and then delete", "quality": "Full quality BMP to JPG conversion"},
            "root_id": w.ROOT_ID, "root_path": w.ROOT_PATH, "namespace_id": w.NAMESPACE_ID,
            "evidence": {"inspection": reference(RUN / "inspection.json"), "relationships": reference(RUN / "relationships.json"),
                         "additional_jpeg_review": reference(additional_path),
                         "archive_proof": reference(RUN / "archive-proof.json"),
                         "baseline_census": inspection["pre_resolution_census"], "original_plan": reference(w.PLAN_PATH)},
            "archive": archive["archive"], "counts": counts, "groups": groups, "ready": ready, "held": held,
            "policy": {"maximum_delete_batch": 5, "conditional_revision_delete": True,
                       "h01_automatically_released": False, "active_public_link_deleted": False,
                       "overwrite_existing_files": False, "upload_retry": False, "delete_retry": False,
                       "protection_resolution": "Original records retained. Each dependent source reaches a verified current JPEG; exact BMP bytes and history metadata remain archived. Protection transfers to the verified successor."}}


def main():
    os.umask(0o077)
    if MANIFEST.exists():
        raise w.SetupError("A held-resolution plan already exists")
    inspection = json.loads((RUN / "inspection.json").read_text())
    relations = json.loads((RUN / "relationships.json").read_text())["records"]
    archive = archive_originals(inspection)
    plan = build_plan(inspection, relations, archive)
    w.private_json(MANIFEST, plan)
    report = ["# Remaining BMP resolution review", "", json.dumps(plan["counts"], indent=2), "",
              f"Lossless originals: {ARCHIVE}", "", "Existing JPEG files will be preserved. A new filename ending __from-bmp.jpg is used where required.", "",
              "Protected keeper records remain in historical evidence; the new verified survivor is explicitly protected before source retirement.", "",
              "| BMP source | Verified or proposed JPEG successor | Resolution |", "|---|---|---|"]
    groups = {g["group_id"]: g for g in plan["groups"]}
    for row in plan["ready"]:
        group = groups[row["replacement_group"]]
        report.append(f"| {row['source_path']} | {group['destination_path']} | {group['method']} |")
    report += ["", "## Awaiting specific decisions", ""]
    report += [f"- {row['source_path']}: {', '.join(row['reasons'])}" for row in plan["held"]]
    (SHARED / "RESOLUTION-REVIEW.md").write_text("\n".join(report) + "\n")
    print(json.dumps({"manifest": reference(MANIFEST), **plan["counts"]}, indent=2))


if __name__ == "__main__":
    main()
