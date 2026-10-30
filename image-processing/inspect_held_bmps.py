"""Review held BMPs, their current bytes, JPEG collisions and keeper dependencies.

This command downloads and builds local candidates only. It never mutates Dropbox.
"""
from __future__ import annotations

import collections
import fcntl
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import convert_bmps as w
from check_bmp_retirement import all_links, census, database_controls, reference
from dropbox.files import ListRevisionsMode
from PIL import Image, JpegImagePlugin
from retire_bmps import RetirementBudget, compare_retirement

RUN = w.RUNTIME / "held-resolution"
SHARED = w.SHARED / "held-resolution"
LOCAL = threading.local()


def api_for(grant):
    if not hasattr(LOCAL, "api"):
        LOCAL.api = w.API(grant)
    return LOCAL.api


def key(identifier):
    return hashlib.sha256(identifier.encode()).hexdigest()


def inspect_jpeg(candidate, expected):
    """Accept an existing JPEG only if it exactly preserves the verified encoding."""
    record = {"fingerprint": w.fingerprint(candidate)}
    with Image.open(candidate) as actual, Image.open(expected) as wanted:
        actual.load()
        wanted.load()
        record.update(format=actual.format, dimensions=list(actual.size), mode=actual.mode,
                      jpeg_sampling=JpegImagePlugin.get_sampling(actual) if actual.format == "JPEG" else None,
                      jpeg_quantization_max=max((v for table in getattr(actual, "quantization", {}).values() for v in table), default=None))
        same_pixels = actual.size == wanted.size and actual.convert("RGB").tobytes() == wanted.convert("RGB").tobytes()
        same_metadata = all(actual.info.get(k) == wanted.info.get(k) for k in ("icc_profile", "exif", "dpi"))
        record["same_decoded_pixels_as_verified_conversion"] = same_pixels
        record["same_colour_and_display_metadata"] = same_metadata
        record["same_jpeg_sampling_and_quantization"] = (
            actual.format == "JPEG" and getattr(actual, "quantization", None) == getattr(wanted, "quantization", None)
            and JpegImagePlugin.get_sampling(actual) == JpegImagePlugin.get_sampling(wanted))
        record["verified_replacement"] = actual.format == "JPEG" and same_pixels and same_metadata and record["same_jpeg_sampling_and_quantization"]
    return record


def inspect_one(row, live, links, grant):
    api = api_for(grant)
    folder = RUN / "files" / key(row["source_id"])
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    source_path, generated = folder / "original.bmp", folder / "converted.jpg"
    record = {**row, "original_hold_reasons": row["hold_reasons"], "recorded_utc": w.now(),
              "work_directory": str(folder), "unresolved": []}
    try:
        source = live.get(row["source_id"])
        if not source or source["kind"] != "file" or source["path"] != row["source_path"] or source["parent_id"] != row["parent_id"]:
            raise w.Hold("SOURCE_ID_OR_LOCATION_CHANGED")
        record["source_head"] = source
        if source_path.exists():
            downloaded = api.metadata(row["source_id"])
        else:
            downloaded = api.download(source_path, row["source_id"], source["rev"])
        w.check_source(row, downloaded, source)
        backup = w.fingerprint(source_path)
        if backup["content_hash"] != source["content_hash"] or backup["size"] != source["size"]:
            raise w.Hold("SOURCE_BACKUP_MISMATCH")
        record["backup"] = backup
        record["local_jpeg"] = w.encode_jpeg(source_path, generated)
        record["direct_links"] = [link for link in links["links"] if link["id"] == row["source_id"]]
        if source.get("has_explicit_shared_members") is not False or source.get("sharing_info_present"):
            record["unresolved"].append("EXTERNAL_OR_UNKNOWN_MEMBERSHIP")
        if source.get("read_only") or source.get("file_lock_present"):
            record["unresolved"].append("READ_ONLY_OR_LOCKED")
        if any(link["resolved_visibility"] not in ("no_one", "only_you") or link["effective_audience"] not in ("no_one", None)
               for link in record["direct_links"]):
            record["unresolved"].append("ACTIVE_OR_UNKNOWN_DIRECT_LINK")
        history = api.read("files_list_revisions", row["source_id"], mode=ListRevisionsMode.id,
                           limit=100, include_restorable_info=True)
        record["available_history"] = [w.head(m) for m in history.entries]
        if history.is_deleted or not history.entries or len(history.entries) >= 100:
            record["unresolved"].append("HISTORY_INCOMPLETE")
        elif history.entries[0].rev != source["rev"] or any(m.id != row["source_id"] for m in history.entries):
            record["unresolved"].append("HISTORY_ID_OR_CURRENT_REVISION_CHANGED")
        record["historical_backups"] = []
        seen = {backup["content_hash"]}
        for old in history.entries:
            if old.content_hash in seen:
                continue
            old_path = folder / "history" / (old.rev + ".bin")
            old_path.parent.mkdir(mode=0o700, exist_ok=True)
            if not old_path.exists():
                api.download(old_path, row["source_id"], old.rev)
            proof = w.fingerprint(old_path)
            if proof["content_hash"] != old.content_hash or proof["size"] != old.size:
                raise w.Hold("HISTORY_BACKUP_MISMATCH")
            record["historical_backups"].append({"head": w.head(old), "path": str(old_path), "fingerprint": proof})
            seen.add(old.content_hash)
        record["existing_jpegs"] = []
        for identifier in row["collision_ids"]:
            current = live.get(identifier)
            if not current or current["kind"] != "file" or current["parent_id"] != row["parent_id"]:
                raise w.Hold("EXISTING_JPEG_ID_OR_LOCATION_CHANGED")
            path = folder / ("existing-" + key(identifier) + ".jpg")
            if not path.exists():
                api.download(path, identifier, current["rev"])
            proof = w.fingerprint(path)
            if proof["content_hash"] != current["content_hash"] or proof["size"] != current["size"]:
                raise w.Hold("EXISTING_JPEG_BACKUP_MISMATCH")
            inspection = inspect_jpeg(path, generated)
            record["existing_jpegs"].append({"head": current, "local_path": str(path), **inspection})
        if "H01_TARGET_OR_KEEPER" in row["hold_reasons"]:
            record["unresolved"].append("H01_AUTHORITY_CLEARANCE_REQUIRED")
    except w.Hold as error:
        record["unresolved"].append(str(error))
    except Exception as error:  # noqa: BLE001 -- Never log token-bearing exception text.
        record["unresolved"].append("INSPECTION_ERROR_" + type(error).__name__)
    record["status"] = "REVIEWED" if not record["unresolved"] else "HELD"
    w.private_json(RUN / "inspections" / (key(row["source_id"]) + ".json"), record)
    return record


def relationships(live, previous, rows, api):
    raw = json.loads((RUN / "historical-relationships-raw.json").read_text())
    master = [r for r in raw if r["source_path"] == "plan/source_registers/Boldstone_2069_Duplicate_Target_Presence_2026-10-14.csv"]
    previous_plan = json.loads(w.PLAN_PATH.read_text())
    prior_rows = {r["source_id"]: r for r in previous_plan["rows"]}
    previous_deleted = set(previous["deleted_ids"])
    records = []
    for original in master:
        item = original["data"]
        target_id, keeper_id = item["Delete file ID"], item["Keep file ID"]
        keeper = live.get(keeper_id)
        result = {"target_id": target_id, "keeper_id": keeper_id, "historical_group": item["Group"],
                  "source_row_sha256": original["row_sha256"], "source_path": original["source_path"],
                  "source_row_number": original["row_number"], "failures": []}
        expected_hash, expected_size = item["Source Dropbox content hash"], int(item["Bytes per copy"])
        if not keeper or keeper["content_hash"] != expected_hash or keeper["size"] != expected_size:
            result["failures"].append("KEEPER_CHANGED_FROM_DUPLICATE_RELATIONSHIP")
        result["keeper_head"] = keeper
        target = live.get(target_id)
        if target:
            result.update(target_disposition="PRESENT_BYTE_IDENTICAL", target_head=target)
            if target["content_hash"] != expected_hash or target["size"] != expected_size or target["parent_id"] != keeper["parent_id"]:
                result["failures"].append("LIVE_DUPLICATE_RELATIONSHIP_CHANGED")
        elif target_id in previous_deleted:
            state = w.saved_state(prior_rows[target_id])
            jpeg = live.get(state["output_head"]["id"])
            result.update(target_disposition="PREVIOUSLY_CONVERTED_AND_RETIRED", original_backup=state["backup"],
                          surviving_jpeg_head=jpeg)
            if state["backup"]["content_hash"] != expected_hash or state["backup"]["size"] != expected_size:
                result["failures"].append("RETIRED_DUPLICATE_BACKUP_MISMATCH")
            if not jpeg or any(jpeg[k] != state["output_head"][k] for k in ("id", "rev", "size", "content_hash")):
                result["failures"].append("RETIRED_DUPLICATE_JPEG_CHANGED")
        else:
            result["target_disposition"] = "HISTORICALLY_DELETED_TARGET_ABSENCE_RECONFIRMED"
            if item["Target ID present now"] != "False" or api.metadata(target_id) is not None:
                result["failures"].append("HISTORICAL_ABSENCE_NOT_CONFIRMED")
        records.append(result)
    protected = {r["source_id"] for r in rows if "PROTECTED_KEEPER_OR_REPLACEMENT" in r["hold_reasons"]}
    if protected - {r["keeper_id"] for r in records}:
        raise w.SetupError("A protected BMP has no complete dependency record")
    targets = {r["target_id"]: r["keeper_id"] for r in records if r["target_id"] in {x["source_id"] for x in rows}}
    for target in targets:
        visited, node = set(), target
        while node in targets:
            if node in visited:
                raise w.SetupError("Cycle in duplicate relationships")
            visited.add(node)
            node = targets[node]
    return records


def main():
    os.umask(0o077)
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (w.RUN_PATH / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = json.loads(w.PLAN_PATH.read_text())
        w.validate_plan(plan)
        rows = [r for r in plan["rows"] if r["status"] == "HELD"]
        previous = json.loads((w.RUNTIME / "retirement-completion.json").read_text())
        before = json.loads(Path(previous["final_census"]["path"]).read_text())
        grant = json.loads(w.keychain_backend().get_password(w.SERVICE, w.CREDENTIAL_ACCOUNT))
        identity = w.verify_grant(grant)
        w.BUDGET = RetirementBudget()
        api = w.API(grant)
        try:
            current = census(api)
            failures = compare_retirement(before, current, set())
            if failures:
                w.private_json(RUN / "initial-census-differences.json", failures)
                raise w.SetupError("Library changed since the verified retirement; inspect differences")
            links = all_links(api)
            live = {r["id"]: r for r in current["entries"]}
            relations = relationships(live, previous, rows, api)
        finally:
            api.close()
        w.private_json(RUN / "pre-resolution-census.json", current)
        w.private_json(RUN / "links.json", links)
        w.private_json(RUN / "relationships.json", {"recorded_utc": w.now(), "records": relations})
        w.private_json(RUN / "database-controls.json", database_controls())
        records = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(inspect_one, row, live, links, grant) for row in rows]
            for future in as_completed(futures):
                records.append(future.result())
                if len(records) % 10 == 0 or len(records) == len(rows):
                    print(f"Inspected {len(records)}/{len(rows)}; outstanding: "
                          f"{dict(collections.Counter(h for r in records for h in r['unresolved']))}", flush=True)
        report = {"schema": "boldstone-held-bmp-inspection-v1", "completed_utc": w.now(), "identity": identity,
                  "original_plan": reference(w.PLAN_PATH), "pre_resolution_census": reference(RUN / "pre-resolution-census.json"),
                  "relationships": reference(RUN / "relationships.json"), "links": reference(RUN / "links.json"),
                  "database_controls": reference(RUN / "database-controls.json"),
                  "records": sorted(records, key=lambda r: r["source_path"].casefold()),
                  "unresolved": dict(collections.Counter(h for r in records for h in r["unresolved"])),
                  "existing_jpegs": sum(len(r.get("existing_jpegs", [])) for r in records),
                  "existing_jpegs_equivalent_to_maximum_quality_conversion": sum(j["verified_replacement"] for r in records for j in r.get("existing_jpegs", [])),
                  "relationship_failures": [r for r in relations if r["failures"]], "remote_mutations": 0}
        w.private_json(RUN / "inspection.json", report)
        print(json.dumps({k: report[k] for k in ("unresolved", "existing_jpegs", "existing_jpegs_equivalent_to_maximum_quality_conversion", "relationship_failures")}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except w.SetupError as error:
        print(str(error), flush=True)
        raise SystemExit(2) from None
    except Exception as error:  # noqa: BLE001 -- Avoid credential-bearing diagnostics.
        print("Inspection stopped: " + type(error).__name__, flush=True)
        raise SystemExit(1) from None
