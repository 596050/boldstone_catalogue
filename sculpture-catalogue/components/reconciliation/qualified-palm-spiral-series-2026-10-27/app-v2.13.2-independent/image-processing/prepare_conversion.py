"""Freeze the completed migration's BMP inventory and a separate conversion handover."""
from __future__ import annotations

import collections
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from authorize import NAMESPACE_ID, ROOT_ID, ROOT_PATH, RUNTIME, private_json

MIGRATION = Path.home() / "Library/Application Support/BoldstoneFlatMigration/flat-20261015"
CONTROLS = Path("/Users/tprice/BoldstoneMigration/flat-20261015/inputs/package/inputs/historical_controls")
SHARED = MIGRATION / "execution/image-conversion"
PLAN_PATH = RUNTIME / "conversion-plan-full-quality.json"
HANDOVER_PATH = SHARED / "HANDOVER-full-quality.json"


def reference(path):
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_plan():
    audit = MIGRATION / "reports/independent-live-audits"
    index_path = max(audit.glob("final-independent-evidence-index-*.json"), key=lambda p: p.stat().st_mtime)
    index = json.loads(index_path.read_text())
    if not index.get("move_only_flat_migration_mechanically_complete"):
        raise ValueError("Final migration verification is not complete.")
    census_path = Path(index["components"]["normalized_census"]["path"])
    reconciliation_path = Path(index["components"]["final_census"]["path"])
    for name, path in (("normalized_census", census_path), ("final_census", reconciliation_path)):
        if reference(path)["sha256"] != index["components"][name]["sha256"]:
            raise ValueError("Final migration evidence hash mismatch.")
    census = json.loads(census_path.read_text())
    reconciliation = json.loads(reconciliation_path.read_text())
    if not (census["writers_drained"] and census["raw_pagination_exhausted"] and reconciliation["writers_drained"]):
        raise ValueError("Migration writers have not drained or the census is incomplete.")
    for flag in ("conservation_pass", "file_location_and_recorded_metadata_pass", "strict_directory_depth_complete"):
        if not reconciliation["result"][flag]:
            raise ValueError("The final census did not pass.")
    keeper_path = CONTROLS / "Protected_Keepers_And_Replacements.csv"
    hold_path = CONTROLS / "Preserved_H01_Holds.csv"
    protected = {r["Dropbox ID"] for r in read_csv(keeper_path)}
    held = {r[k] for r in read_csv(hold_path) for k in ("Target file ID", "Designated keeper ID")}
    entries = census["entries"]
    by_id = {r["id"]: r for r in entries}
    by_path = {r["path"].casefold(): r for r in entries}
    rows = []
    for source in entries:
        if source["kind"] != "file" or not source["name"].casefold().endswith(".bmp"):
            continue
        path = PurePosixPath(source["path"])
        family = by_id[source["family_id"]]
        parent = by_id[source["parent_id"]]
        if source["depth"] != 3 or parent["parent_id"] != family["id"]:
            raise ValueError("BMP has an unexpected parent graph.")
        reasons = []
        if source["id"] in protected:
            reasons.append("PROTECTED_KEEPER_OR_REPLACEMENT")
        if source["id"] in held:
            reasons.append("H01_TARGET_OR_KEEPER")
        collisions = [by_path[str(path.with_suffix(ext)).casefold()]["id"]
                      for ext in (".jpg", ".jpeg") if str(path.with_suffix(ext)).casefold() in by_path]
        if collisions:
            reasons.append("EXISTING_JPEG_NAME")
        rows.append({
            "source_id": source["id"], "source_path": source["path"], "size": source["size"],
            "client_modified": source["client_modified"], "server_modified": source["server_modified"],
            "parent_id": parent["id"], "parent_path": parent["path"],
            "family_id": family["id"], "family_path": family["path"], "family": family["name"],
            "destination_path": str(path.with_suffix(".jpg")),
            "status": "HELD" if reasons else "ELIGIBLE", "hold_reasons": reasons,
            "collision_ids": collisions,
        })
    rows.sort(key=lambda r: (r["family"].casefold(), r["source_path"].casefold()))
    eligible = [r for r in rows if r["status"] == "ELIGIBLE"]
    return {
        "schema": "boldstone-completed-family-bmp-conversion-v2-full-quality",
        "created_utc": datetime.now(UTC).isoformat(),
        "namespace_id": NAMESPACE_ID, "root_id": ROOT_ID, "root_path": ROOT_PATH,
        "authorization": {
            "source_session": "01a13b4a-da24-7921-9c08-7b17d95e8413",
            "instruction": "New app: convert BMPs in families whose moves are fully verified and handed over; shared operation ledger.",
            "current_instruction": "Proceed with a parallel conversion of BMPs in folders already completed for migration.",
            "quality_instruction": "Make sure the BMP conversion to JPG is full quality.",
            "handover_basis": "Final independent move-only audit and drained-writer census; derived handover, not a new owner signature.",
        },
        "policy": {"workers": 2, "one_worker_per_family": True, "jpeg_quality": 100,
                   "jpeg_subsampling": 0, "keep_original_dimensions": True,
                   "source_retirement_enabled": False, "overwrite_enabled": False,
                   "originals_note": "BMPs retained. Retirement requires separate link/history/publication dependency checks.",
                   "mislabelled_jpeg": "Copy existing JPEG bytes without recompression."},
        "evidence": {"final_audit": reference(index_path), "census": reference(census_path),
                     "reconciliation": reference(reconciliation_path),
                     "protected": reference(keeper_path), "holds": reference(hold_path)},
        "counts": {"bmp_files": len(rows), "eligible": len(eligible), "held": len(rows) - len(eligible),
                   "eligible_families": len({r["family_id"] for r in eligible}),
                   "eligible_bytes": sum(r["size"] for r in eligible),
                   "hold_reasons_overlapping": dict(collections.Counter(x for r in rows for x in r["hold_reasons"]))},
        "rows": rows,
    }


def main():
    plan_path = PLAN_PATH
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        plan = build_plan()
        private_json(plan_path, plan)
    handover = {
        "schema": "boldstone-image-conversion-handover-v1", "status": "PREPARED_NOT_STARTED",
        "plan": reference(plan_path), "counts": plan["counts"], "basis": plan["authorization"],
        "operation_ledger": str(SHARED / "operations.jsonl"),
        "status_path": str(RUNTIME / "conversion-status.json"),
        "original_retirements_enabled": False,
        "audit_rule": "Add only verified JPEG IDs from the conversion ledger to the post-migration inventory. Source IDs remain present; no replacement/removal is implied.",
    }
    if not HANDOVER_PATH.exists():
        private_json(HANDOVER_PATH, handover)
    private_json(SHARED / "ACTIVE-PLAN.json", {"plan": reference(PLAN_PATH), "handover": reference(HANDOVER_PATH),
                 "jpeg_quality": 100, "previous_quality_95_plan_superseded_before_any_upload": True})
    print(json.dumps({"plan": str(plan_path), **plan["counts"]}, indent=2))


if __name__ == "__main__":
    main()
