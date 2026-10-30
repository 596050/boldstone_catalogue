"""Verify and adapt the authorized three-family rename ledger for root."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import hashlib
import json

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parents[2]
source = CATALOGUE.parent / "reports/dropbox-wall-structure-2026-10-20/step-02-three-family-renames-current-overlay.json"
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(source) == "599b2a0fc6eb8f50515339082600d435d00242ddd1cbaa640b8458e314b37e5e"
overlay = read(source)
inputs = HERE / "family-rename-inputs"
inputs.mkdir(exist_ok=True)
manifest = {}
for key, path in {"current_overlay": str(source), **overlay["receipts"]}.items():
    path = Path(path)
    raw = path.read_bytes()
    target = inputs / path.name
    assert not target.exists(), target
    target.write_bytes(raw)
    assert path.read_bytes() == raw
    manifest[key] = {"source": str(path), "snapshot": str(target), "sha256": sha(target)}
plan = read(manifest["plan"]["snapshot"])
terminal = read(manifest["terminal"]["snapshot"])["terminal"]
baseline = {}
for chunks in plan["baseline_inventories"].values():
    for chunk in chunks:
        for item in chunk["entries"]:
            assert item["file_id"] not in baseline
            baseline[item["file_id"]] = item
objects = {x["file_id"]: x for x in overlay["objects"]}
files = [o for o in objects.values() if o["object_type"] == "file"]
folders = [o for o in objects.values() if o["object_type"] == "folder"]
folder_by_path = {o["current_display_path"]: o for o in folders}
roots = {o["file_id"]: o for o in plan["operations"]}
checks = {}
checks["Three native rename entries completed successfully"] = terminal["status"] == "completed" and len(terminal["move_result"]["entries"]) == 3 and all(e["entry_status"] == "success" for e in terminal["move_result"]["entries"])
checks["Independent writer verification passed"] = overlay["verification"]["status"] == "PASS"
checks["783 distinct IDs equal760files23folders"] = len(objects) == len(overlay["objects"]) == 783 and len(files) == 760 and len(folders) == 23
checks["Ledger retains every baseline descendant and the three roots"] = set(objects) == set(baseline) | set(roots)
for fid, obj in objects.items():
    prefix = next(p for p in overlay["prefix_maps"] if obj["old_display_path"] == p["old_prefix"] or obj["old_display_path"].startswith(p["old_prefix"] + "/"))
    expected = prefix["current_prefix"] + obj["old_display_path"][len(prefix["old_prefix"]):]
    checks["Current expected path " + fid] = obj["current_display_path"] == expected
    if fid in baseline:
        old = baseline[fid]
        old_size = old.get("file", {}).get("size")
        checks["Retained descendant name type size " + fid] = obj["name"] == old["name"] and obj["object_type"] == old["object_type"] and (obj["object_type"] != "file" or obj["size"] == old_size)
checks["Only requested family-root names changed"] = all(objects[fid]["name"] == op["new_name"] for fid, op in roots.items())
checks["Owned direct-link folder listing scope complete"] = overlay["link_dispositions"]["all_23_folder_link_listings_complete"] is True
checks["No invented whole-estate link audit"] = overlay["link_dispositions"]["per_file_owned_links_exhaustively_enumerated"] is False

file_map = []
for obj in files:
    parent = str(Path(obj["current_display_path"]).parent)
    folder = folder_by_path[parent]
    file_map.append({
        "file_id": obj["file_id"],
        "historical_file_path": obj["old_display_path"],
        "current_file_path": obj["current_display_path"],
        "current_folder_id": folder["file_id"],
        "current_folder_path": parent, "size": obj["size"],
        "current_image_url": obj["current_native_url"],
        "current_folder_url": "https://www.dropbox.com/home" + quote(parent, safe="/"),
        "old_basename_preserved": True, "before_after_content_hash_compared": False,
    })
folder_map = []
for obj in folders:
    folder_map.append({
        "deleted_folder_id": obj["file_id"],
        "prior_folder_id": obj["file_id"], "current_folder_id": obj["file_id"],
        "historical_folder_path": obj["old_display_path"],
        "current_folder_path": obj["current_display_path"],
        "current_folder_url": "https://www.dropbox.com/home" + quote(obj["current_display_path"], safe="/"),
        "folder_deleted": False,
        "legacy_schema_field_note": "deleted_folder_id is lookup-key compatibility only. Every one of these23folder IDs remains present.",
    })
result = {
    "schema": "boldstone.three-family-current-register-link-overlay-independent-readback.v1",
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if all(checks.values()) else "FAIL",
    "checks_passed": sum(checks.values()),
    "checks_failed": sum(not v for v in checks.values()),
    "failed_checks": [k for k, v in checks.items() if not v],
    "writer_receipts": manifest,
    "prefix_maps": overlay["prefix_maps"],
    "folder_replacements": folder_map, "moved_file_replacements": file_map,
    "current_product_link_updates": [],
    "confirmed_deleted_folder_ids": [],
    "current_folder_count": len(folders), "current_file_count": len(files),
    "catalogue_identity_guard": overlay["catalogue_identity_guard"],
    "link_dispositions": overlay["link_dispositions"],
    "verification_scope": overlay["verification"]["content_scope"],
    "current_native_url_scope": "Current path-derived native links. No HTTP opening or whole-estate share-link audit by B.",
    "shared_master_writes": 0, "remote_reads": 0, "remote_writes": 0,
}
out = HERE / "THREE_FAMILY_CURRENT_LINK_OVERLAY_VERIFIED.json"
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
prefix_file = HERE / "SUPERSEDED_FAMILY_PREFIXES.json"
assert not prefix_file.exists()
prefix_file.write_text(json.dumps([p["old_prefix"] + "/" for p in overlay["prefix_maps"]], ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"path": str(out), "sha256": sha(out), "status": result["status"], "checks_passed": result["checks_passed"], "failed": result["failed_checks"], "files": len(files), "folders": len(folders), "forbidden_prefixes": str(prefix_file)}))
