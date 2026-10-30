"""Apply the newly verified manual folder moves as an additive reference proof."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import hashlib
import json

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parents[2]
B = HERE.parent / "product-register-lane-b-audit-2026-10-20"
source = CATALOGUE.parent / "reports/dropbox-wall-structure-2026-10-20/phase4-manual-move-overlay-2026-10-20.json"
raw = source.read_bytes()
snapshot = HERE / source.name
assert not snapshot.exists()
snapshot.write_bytes(raw)
manual = json.loads(raw)
read = lambda p: json.loads(Path(p).read_text())
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path = B / "MCP4_CURRENT_LINK_OVERLAY_VERIFIED.json"
prior = read(prior_path)
graph = read(B / "inputs/canonical-products.json")


def plain(path):
    return path.split("ns:202238505/", 1)[-1]


folders = {f["file_id"]: f for f in manual["current_finish_folders"]}
folders_by_path = {f["current_display_path"]: f for f in folders.values()}
current_files = {}
for f in manual["current_phase4_file_paths"]:
    path = plain(f["current_path"])
    folder_path = str(Path(path).parent)
    folder = folders_by_path[folder_path]
    current_files[f["file_id"]] = {
        "file_id": f["file_id"], "historical_file_path": plain(f["old_path"]),
        "current_file_path": path, "current_folder_id": folder["file_id"],
        "current_folder_path": folder_path, "size": f["size"],
        "current_folder_url": "https://www.dropbox.com/home" + quote(folder_path, safe="/"),
        "current_image_url": "https://www.dropbox.com/home" + quote(folder_path, safe="/") + "?preview=" + quote(Path(path).name, safe=""),
        "verification_basis": "Current manual-move path readback by stable file ID and unchanged size",
        "bytes_hash_compared": False,
    }
silver_old = "id:cnqzTNngPVsAAAAAAAyirQ"
silver_current = "id:cnqzTNngPVsAAAAAAAyglA"
folder_maps = []
for old in prior["current_finish_folders"]:
    fid = old["file_id"]
    current = folders[silver_current if fid == silver_old else fid]
    folder_maps.append({
        "deleted_folder_id": fid,
        "prior_folder_id": fid,
        "current_folder_id": current["file_id"],
        "historical_folder_path": old["current_display_path"],
        "current_folder_path": current["current_display_path"],
        "current_folder_url": "https://www.dropbox.com/home" + quote(current["current_display_path"], safe="/"),
        "folder_deleted": False,
        "old_id_scope": "Absent from current family; global deletion not proven" if fid == silver_old else "Same folder ID moved to parent",
        "legacy_schema_field_note": "deleted_folder_id is retained solely as lookup-key compatibility; deletion is asserted only by folder_deleted.",
    })
for old in prior["folder_replacements"]:
    current = folders[old["current_folder_id"]]
    folder_maps.append({
        **old, "prior_folder_id": old["deleted_folder_id"],
        "current_folder_path": current["current_display_path"],
        "current_folder_url": "https://www.dropbox.com/home" + quote(current["current_display_path"], safe="/"),
        "folder_deleted": True,
        "old_id_scope": "Prior authorized deletion receipt exists",
    })


def rewrite(url):
    parsed = urlsplit(url)
    if parsed.hostname not in {"www.dropbox.com", "dropbox.com"}:
        return url
    decoded = unquote(parsed.path)
    for entry in sorted(folder_maps, key=lambda x: -len(x["historical_folder_path"])):
        old, new = entry["historical_folder_path"], entry["current_folder_path"]
        for prefix in ["/home", "/preview"]:
            start = prefix + old
            if decoded == start or decoded.startswith(start + "/"):
                return parsed._replace(path=quote(prefix + new + decoded[len(start):], safe="/")).geturl()
    return url


updates = []
for p in graph["products"]:
    changed = {}
    if p["file_id"] in current_files:
        f = current_files[p["file_id"]]
        changed = {"image_url": f["current_image_url"], "folder_url": f["current_folder_url"], "folder_id": f["current_folder_id"]}
    for key in ["context_image_url", "context_folder_url"]:
        if p.get(key) and rewrite(p[key]) != p[key]:
            changed[key] = rewrite(p[key])
    changed = {k: v for k, v in changed.items() if p.get(k) != v}
    if changed:
        updates.append({
            "product_id": p["product_id"], "canonical_key": p["canonical_key"],
            "product_name": p["name"], "primary_file_id_preserved": p["file_id"],
            "historical_values": {k: p[k] for k in changed}, "current_values": changed,
            "applies_to": "Current register image/folder/context display only; original source assertions remain immutable",
        })
old_file_sizes = {r["file_id"]: r["size"] for r in prior["moved_file_replacements"]}
checks = {
    "Writer independently verified all178familyIDs and sizes": manual["verification"]["all_178_file_ids_present"] and manual["verification"]["all_178_file_sizes_unchanged"] and manual["family_file_count"] == 178,
    "All47Phase4stableIDs present once": manual["verification"]["all_47_phase4_files_present"] and len(current_files) == len(manual["current_phase4_file_paths"]) == manual["phase4_file_count"] == 47,
    "Six current folders account for all47files": len(folders) == 6 and sum(f["files"] for f in folders.values()) == 47,
    "No nested wrapper remains in current filepaths": manual["verification"]["no_nested_phase4_wrapper"] and all("/Moon Crater Phase/Moon Crater Phase 4/" not in f["current_file_path"] for f in current_files.values()),
    "All prior11agent-moved file IDs and sizes preserved": all(fid in current_files and current_files[fid]["size"] == size for fid, size in old_file_sizes.items()),
    "SeparateSilver8files combined withSilverBronze10": folders[silver_current]["files"] == 18 and silver_old not in folders,
    "Four MCP4named product records require fresh display links": len(updates) == 4 and all(u["canonical_key"].startswith("BC-MCP-4|") for u in updates),
    "Verdigris current context links corrected": any(u["canonical_key"] == "BC-MCP-4|MCP4-VERDIGRIS-25" and {"context_image_url", "context_folder_url"} <= set(u["current_values"]) for u in updates),
    "No original file names altered by this proof": all(Path(f["current_file_path"]).name == Path(f["historical_file_path"]).name for f in current_files.values()),
    "No source drift during readback": source.read_bytes() == raw,
}
result = {
    "schema": "boldstone.mcp4-manual-current-register-link-overlay-independent-readback.v2",
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if all(checks.values()) else "FAIL",
    "checks": {k: "PASS" if v else "FAIL" for k, v in checks.items()},
    "supersedes_current_paths": {"path": str(prior_path), "sha256": digest(prior_path)},
    "manual_writer_overlay": {"path": str(source), "snapshot": str(snapshot), "sha256": digest(snapshot)},
    "current_wrapper": None,
    "prior_wrapper_scope": "Former wrapper absent from current family; get_file_metadata INVALID_ARGUMENT is not a global deletion receipt",
    "current_finish_folders": manual["current_finish_folders"],
    "folder_replacements": folder_maps,
    "moved_file_replacements": list(current_files.values()),
    "current_product_link_updates": updates,
    "confirmed_deleted_alias_folder_ids": [x["deleted_folder_id"] for x in prior["folder_replacements"]],
    "old_folder_ids_absent_from_current_family": manual["old_folder_ids_absent_from_current_family"],
    "deleted_alias_direct_link_dispositions": prior["deleted_alias_direct_link_dispositions"],
    "link_scope_note": manual["link_disposition_limit"],
    "verification_scope": "Independent local readback of the Dropbox writer's fresh exhaustive family inventory following user-performed manual changes. Stable IDs and sizes retained. No new HTTP link test or full-content hash comparison.",
    "proposal_destinations_promoted_to_live": False,
    "current_manual_change_verified": True,
    "shared_master_writes": 0, "remote_reads": 0, "remote_writes": 0,
}
out = HERE / "MCP4_MANUAL_CURRENT_LINK_OVERLAY_VERIFIED.json"
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"path": str(out), "sha256": digest(out), "status": result["status"], "checks_passed": sum(checks.values()), "failed": [k for k, v in checks.items() if not v], "current_product_updates": len(updates)}))
