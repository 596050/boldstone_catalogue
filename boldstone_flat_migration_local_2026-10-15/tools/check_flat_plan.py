#!/usr/bin/env python3
"""Offline inspection of the supplied Boldstone flat-directory proposal.

No network, Dropbox SDK, authentication, mutation or approval commands exist here.
A route preview is not an executable manifest or an independently verified result.
Python 3.11+; standard library only.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from typing import Any
import unicodedata
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ROUTE_ACTIONS = {"FLAT GROUP PROPOSAL", "ROOT-FILE HOLDING PROPOSAL"}
DECISIONS = {"PENDING", "HOLD", "APPROVE_SOURCE_LABEL_ROUTING",
             "APPROVE_PROVISIONAL_STORAGE", "RESOLVED_APPROVED"}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f"Missing or duplicated CSV headers: {path}")
        rows = list(reader)
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError(f"Malformed CSV row: {path}")
    return rows


def component(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Empty or whitespace-padded path component")
    if value in {".", ".."} or any(ord(c) < 32 for c in value):
        raise ValueError("Unsafe path component")
    if any(c in value for c in '/\\:\x00†'):
        raise ValueError("Separator, colon or annotation inside path component")
    return value


def path_key(value: str) -> str:
    # Conservative planning key, not a substitute for server collision checks.
    return unicodedata.normalize("NFC", value).casefold()


def validate_relative(value: str, depth: int | None = None) -> str:
    pieces = value.split("/")
    for piece in pieces:
        component(piece)
    if depth is not None and len(pieces) != depth:
        raise ValueError(f"Expected {depth} path components: {value}")
    return value


def load_plan(base: Path = ROOT) -> dict[str, Any]:
    source = base / "inputs" / "flat_plan"
    targets = load_csv(source / "Boldstone_347_Proposed_Subdirectories.csv")
    rows = load_csv(source / "Boldstone_Source_to_Flat_Target.csv")
    folders = load_csv(source / "Boldstone_Current_422_Folders.csv")
    target_map: dict[str, dict[str, str]] = {}
    for t in targets:
        validate_relative(t["target_relative"], 2)
        if t["target_relative"] != t["family"] + "/" + t["target_name"]:
            raise ValueError("Target fields disagree")
        key = path_key(t["target_relative"])
        if key in target_map:
            raise ValueError("Case-insensitive target collision")
        if t["review"] not in {"True", "False"}:
            raise ValueError("Invalid review flag")
        target_map[key] = t
    # IMPORTANT: control and direct-file rules deliberately use separate maps.
    family_controls: dict[str, dict[str, str]] = {}
    direct_routes: dict[str, dict[str, str]] = {}
    controls: dict[str, dict[str, str]] = {}
    typed_keys: set[tuple[str, str]] = set()
    for row in rows:
        fid, action = row["id"], row["action"]
        if not fid.startswith("id:"):
            raise ValueError("Expected exact Dropbox folder ID")
        key = (fid, action)
        if key in typed_keys:
            raise ValueError("Duplicate source ID/action pair")
        typed_keys.add(key)
        if action in ROUTE_ACTIONS:
            if fid in direct_routes:
                raise ValueError("Ambiguous immediate-file route")
            if path_key(row["target_relative"]) not in target_map:
                raise ValueError("Route points outside the proposed target set")
            direct_routes[fid] = row
        elif action == "RETAIN FAMILY":
            family_controls[fid] = row
        elif action in {"COLLAPSE EMPTY WRAPPER", "VIDEO EXCEPTION"}:
            controls[fid] = row
        else:
            raise ValueError(f"Unsupported source action: {action}")
    if len({x["id"] for x in folders}) != len(folders):
        raise ValueError("Repeated folder ID in source folder census")
    if {r["id"] for r in rows} != {f["id"] for f in folders}:
        raise ValueError("Source mapping does not cover exact folder census")
    groups: dict[str, set[str]] = collections.defaultdict(set)
    for fid, row in direct_routes.items():
        groups[path_key(row["target_relative"])].add(fid)
    for key, t in target_map.items():
        declared = {s.strip() for s in t["source_ids"].split(";") if s.strip()}
        if groups[key] != declared or len(declared) != int(t["source_count"]):
            raise ValueError(f"Source contribution mismatch: {t['target_relative']}")
    return dict(targets=targets, rows=rows, folders=folders,
                target_map=target_map, family_controls=family_controls,
                direct_routes=direct_routes, controls=controls)


def package_validation(base: Path = ROOT) -> dict[str, Any]:
    plan = load_plan(base)
    archive = base / "inputs" / "Boldstone_Flat_Family_Directory_Plan_2026-10-15.zip"
    checked = 0
    with ZipFile(archive) as z:
        for row in load_csv(base / "inputs" / "flat_plan" / "Package_Checksums.csv"):
            payload = z.read(row["filename"])
            if len(payload) != int(row["bytes"]) or hashlib.sha256(payload).hexdigest() != row["sha256"]:
                raise ValueError(f"Original archive checksum failure: {row['filename']}")
            local = base / "inputs" / "flat_plan" / row["filename"]
            if local.exists() and local.read_bytes() != payload:
                raise ValueError(f"Extracted source changed: {row['filename']}")
            checked += 1
    expected = (347, 425, 422, 63, 359, 74)
    actual = (len(plan["targets"]), len(plan["rows"]), len(plan["folders"]),
              len(plan["family_controls"]), len(plan["direct_routes"]),
              sum(t["review"] == "True" for t in plan["targets"]))
    if actual != expected:
        raise ValueError(f"Original proposal structure differs: {actual} != {expected}")
    for job in sorted((base / "rules" / "families").glob("*.json")):
        data = json.loads(job.read_text(encoding="utf-8"))
        fam_targets = [x for x in plan["targets"] if x["family"] == data["family"]]
        if data["targets"] != fam_targets:
            raise ValueError(f"Family target specification differs: {job.name}")
    return {"status": "OFFLINE_INPUT_VALIDATION_PASSED", "target_leaves": actual[0],
            "source_rows": actual[1], "unique_source_folder_ids": actual[2],
            "families": actual[3], "immediate_file_routes": actual[4],
            "review_leaves": actual[5], "original_checksum_entries_verified": checked,
            "dropbox_contacted": False, "mutations": 0,
            "file_moves_determined": False}


def check_snapshot(snapshot: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if snapshot.get("schema") != "boldstone-flat-snapshot-v1":
        raise ValueError("Wrong snapshot schema")
    if snapshot.get("complete") is not True or snapshot.get("has_more") is not False:
        raise ValueError("Snapshot is not marked fully paginated")
    if not snapshot.get("account_id") or not snapshot.get("root_id") or not snapshot.get("observed_at_utc"):
        raise ValueError("Missing account/root/observation binding")
    folders = {f["id"]: f for f in snapshot["folders"]}
    if len(folders) != len(snapshot["folders"]):
        raise ValueError("Duplicate snapshot folder ID")
    all_ids: set[str] = {snapshot["root_id"]}
    paths: dict[str, str] = {}
    for item in [*snapshot["folders"], *snapshot["files"]]:
        if item["id"] in all_ids:
            raise ValueError("Duplicate snapshot object ID")
        all_ids.add(item["id"])
        validate_relative(item["relative_path"])
        if item["name"] != item["relative_path"].split("/")[-1]:
            raise ValueError("Snapshot name and final path component differ")
        key = path_key(item["relative_path"])
        if key in paths:
            raise ValueError("Snapshot path collision")
        paths[key] = item["id"]
    for item in [*snapshot["folders"], *snapshot["files"]]:
        parent = item["parent_id"]
        if parent == snapshot["root_id"]:
            expected = item["name"]
        elif parent in folders:
            expected = folders[parent]["relative_path"] + "/" + item["name"]
        else:
            raise ValueError("Unknown snapshot parent ID")
        if path_key(expected) != path_key(item["relative_path"]):
            raise ValueError("Snapshot parent ancestry mismatch")
    return folders, paths


def route_preview(plan: dict[str, Any], snapshot: dict[str, Any],
                  decisions: dict[str, str] | None = None,
                  held_ids: set[str] | None = None) -> list[dict[str, Any]]:
    folders, occupied = check_snapshot(snapshot)
    decisions = decisions or {}
    held_ids = held_ids or set()
    result: list[dict[str, Any]] = []
    reservations: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for f in snapshot["files"]:
        row = {"file_id": f["id"], "source_relative": f["relative_path"],
               "parent_folder_id": f["parent_id"], "proposed_relative": "",
               "preview_status": "", "holds": [], "executable": False}
        parent = f["parent_id"]
        control = plan["controls"].get(parent)
        route = plan["direct_routes"].get(parent)
        if control:
            row["preview_status"] = control["action"]
            row["holds"].append("EXTERNAL_ROUTE_REQUIRES_APPROVAL" if control["action"] == "VIDEO EXCEPTION" else "UNEXPECTED_DIRECT_FILE_IN_WRAPPER")
        elif not route:
            row["preview_status"] = "UNALLOCATED_IMMEDIATE_PARENT"
            row["holds"].append("NO_ANCESTOR_FALLBACK_ALLOWED")
        else:
            target = plan["target_map"][path_key(route["target_relative"])]
            target_path = target["target_relative"] + "/" + f["name"]
            row["proposed_relative"] = target_path
            row["preview_status"] = "ALREADY_AT_PROPOSED_TARGET" if f["relative_path"] == target_path else "MOVE_CANDIDATE_ONLY"
            family_id = next((fid for fid, r in plan["family_controls"].items() if r["family"] == route["family"]), None)
            if family_id not in folders or folders[family_id]["parent_id"] != snapshot["root_id"] or folders[family_id]["name"] != route["family"]:
                row["holds"].append("FAMILY_BINDING_DRIFT")
            expected_source = route["family"] if route["action"] == "ROOT-FILE HOLDING PROPOSAL" else route["source_relative"]
            current_parent_path = folders[parent]["relative_path"]
            if path_key(current_parent_path) not in {path_key(expected_source), path_key(target["target_relative"])}:
                row["holds"].append("SOURCE_FOLDER_LOCATION_DRIFT")
            decision = decisions.get(target["target_relative"], "PENDING")
            if decision not in DECISIONS:
                raise ValueError(f"Invalid decision: {decision}")
            row["storage_decision"] = decision
            if decision in {"PENDING", "HOLD"}:
                row["holds"].append("TARGET_DECISION_PENDING_OR_HELD")
            if target["review"] == "True" and decision not in {"APPROVE_PROVISIONAL_STORAGE", "RESOLVED_APPROVED"}:
                row["holds"].append("PROVISIONAL_STORAGE_DECISION_REQUIRED")
            if f.get("media_kind") != "image":
                row["holds"].append("NON_IMAGE_OR_UNVERIFIED_TYPE")
            if not f.get("rev") or not f.get("content_hash") or not isinstance(f.get("size"), int) or isinstance(f.get("size"), bool) or f["size"] < 0:
                row["holds"].append("CONTENT_METADATA_INCOMPLETE")
            if f["id"] in held_ids and row["preview_status"] != "ALREADY_AT_PROPOSED_TARGET":
                row["holds"].append("HISTORICAL_HOLD_SCOPE_REQUIRES_REVIEW")
            key = path_key(target_path)
            if key in occupied and occupied[key] != f["id"]:
                row["holds"].append("OCCUPIED_DESTINATION_REQUIRES_COLLISION_PLAN")
            reservations[key].append(row)
        result.append(row)
    for group in reservations.values():
        if len(group) > 1:
            for row in group:
                row["holds"].append("MULTIPLE_FILES_REQUEST_SAME_DESTINATION")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    family = sub.add_parser("family"); family.add_argument("name")
    route = sub.add_parser("route-preview")
    route.add_argument("snapshot", type=Path)
    route.add_argument("--decisions", type=Path)
    route.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            print(json.dumps(package_validation(), indent=2)); return
        plan = load_plan()
        if args.command == "family":
            targets = [t for t in plan["targets"] if t["family"].casefold() == args.name.casefold()]
            if not targets: raise ValueError("Unknown family name")
            print(json.dumps({"targets": targets, "executable": False}, indent=2, ensure_ascii=False)); return
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        decisions: dict[str, str] = {}
        if args.decisions:
            for row in load_csv(args.decisions):
                if row["target_relative"] in decisions: raise ValueError("Repeated target decision")
                decisions[row["target_relative"]] = row["decision"]
        holds = {r["Target file ID"] for r in load_csv(ROOT / "inputs" / "historical_controls" / "Preserved_H01_Holds.csv")}
        preview = route_preview(plan, snapshot, decisions, holds)
        output = {"kind": "OFFLINE_ROUTE_PREVIEW_NOT_AN_EXECUTABLE_MANIFEST", "snapshot_observed_at": snapshot["observed_at_utc"],
                  "source_snapshot_sha256": hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
                  "rows": preview, "dropbox_contacted": False}
        # Refuse overwrite to avoid destroying an earlier evidence file.
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False); f.write("\n")
        print(f"Wrote {len(preview)} offline preview rows to {args.out}")
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
