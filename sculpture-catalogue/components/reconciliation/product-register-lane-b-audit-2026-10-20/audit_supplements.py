"""Bind Wall Circle source scope and current MCP4 links without shared writes."""
from collections import Counter
from datetime import datetime, timezone
from itertools import islice, product
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import hashlib
import json

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parents[2]
REPO = CATALOGUE.parent
SNAP = HERE / "inputs"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    path = HERE / name
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(path), "sha256": sha(path)}


def snapshot(path):
    path = Path(path)
    raw = path.read_bytes()
    target = SNAP / path.name
    assert not target.exists(), target
    target.write_bytes(raw)
    assert path.read_bytes() == raw, path
    return {"path": str(path), "snapshot": str(target), "sha256": sha(target)}


wall = read(SNAP / "wall-circle-approved-working-catalogue.json")
rows = wall["native_option_register"]
visuals = wall["visual_working_records"]
attrs = list(rows[0]["attributes"])
values = {k: sorted({r["attributes"][k] for r in rows}) for k in attrs}
combinations = [tuple(r["attributes"][k] for k in attrs) for r in rows]
evidence = wall["authoritative_user_evidence"]
with Path(evidence["transcript_path"]).open("rb") as f:
    raw = next(islice(f, evidence["line"] - 1, evidence["line"]))
message = json.loads(raw)
text = "".join(c.get("text", "") for c in message["payload"]["content"])
checks = {
    "Family approval exact user message and digest verified": message["payload"]["role"] == "user" and text == evidence["user_statement"] and hashlib.sha256(text.encode()).hexdigest() == evidence["text_sha256"],
    "Seven unique kept visual working entries": len(visuals) == len({v["review_id"] for v in visuals}) == 7 and all(v["working_entry_kept"] for v in visuals),
    "All seven retain primary file and folder IDs and links": all(v["primary_file_id"] and v["primary_folder_id"] and v["image_url"] and v["folder_url"] for v in visuals),
    "All seven retain six original scoped field records": all(len(v["specification_review_items"]) == 6 for v in visuals),
    "144 unique native variant IDs and SKUs": len(rows) == len({r["variant_id"] for r in rows}) == len({r["sku"] for r in rows}) == 144,
    "Native option axes have18patterns4sizes2lightingchoices": {k: len(v) for k, v in values.items()} == {"Pattern": 18, "Diameter Size": 4, "Lighting": 2},
    "Native option combinations are complete and unique": len(combinations) == len(set(combinations)) == 144 and set(combinations) == set(product(*(values[k] for k in attrs))),
    "Native options retain unresolved visual name mapping": all(r["relationship_to_visual_review_names"] == "UNRESOLVED_NO_NEW_DISTINCT_DESIGN_COUNT" for r in rows),
    "Physical stock quantity unverified on all native options": all(r["physical_stock_verified"] is False for r in rows),
    "Source raw numeric units not silently converted": all(r["raw_units"] == "Not asserted; retain native numeric values without conversion" for r in rows),
}
wc01 = visuals[0]
fields = {r["group"]: r for r in wc01["specification_review_items"]}
checks["WC01 exact owner facts preserved at WC01 scope"] = (
    fields["dimensions_and_depth"]["confirmed_dimensions_cm"] == {"diameter": 50, "width": 50, "height": 50, "depth": 2.5}
    and fields["weight"]["value_kg"] == 12 and fields["weight"]["approximate"] is True
    and fields["material_and_finish"]["confirmed_material"] == "plaster/gypsum composite"
    and fields["fixings_and_lighting"]["confirmed_fixings"] == "French cleat"
    and fields["fixings_and_lighting"]["confirmed_lighting"] == "RGB lighting"
    and fields["individual_price"]["amount"] == 600
    and fields["availability"]["confirmed_value"] == "Made to order"
)
wall_result = {
    "schema": "boldstone.wall-circle-register-supplement-independent-proof.v1",
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if all(checks.values()) else "FAIL",
    "source": {"snapshot": str(SNAP / "wall-circle-approved-working-catalogue.json"), "sha256": sha(SNAP / "wall-circle-approved-working-catalogue.json")},
    "family_owner_evidence": {**evidence, "raw_line_sha256_including_newline": hashlib.sha256(raw).hexdigest()},
    "checks": {k: "PASS" if v else "FAIL" for k, v in checks.items()},
    "visual_working_records": visuals,
    "native_options": rows,
    "native_option_axes": values,
    "source_price_by_diameter_gbp": {s: sorted({r["price"]["value"] for r in rows if r["attributes"]["Diameter Size"] == s}) for s in values["Diameter Size"]},
    "native_product_id": wall["native_squarespace_product_id"],
    "native_product_url": wall["native_squarespace_url"],
    "family_approval_meaning": wall["family_approval"]["approval_meaning"],
    "family_working_50cm_template": wall["family_approval"]["working_50cm_template"],
    "preferred_register_disposition": {
        "visual_records": "Retain WC-01 through WC-07 as seven owner-kept working visual entries with exact six-field source labels and stable media IDs.",
        "native_options": "Retain144 source options as18patterns by4diameters by2lightingchoices. Link to one Wall Circle family; exact visual-review-name aliases remain unresolved.",
        "option_family_header": "Family/reference record rather than an extra individual sculpture.",
        "count_scope": "Seven working visual entries and144 native option rows are overlapping representations; never sum them as distinct products, designs, casts, moulds or stock.",
        "global_offered_fixings": ["Keyhole fixing", "French cleat"],
        "installed_fixing_scope": "WC01 French cleat is owner stated. Global offered choices do not replace that installation fact or confirm other installed hardware.",
        "other_six_template_scope": "Dimensions50dia×2.5,approx12kg,gypsum composite,RGB,£600,MTO are existing working proposals outsideWC01; retain labels and unknown lead time.",
    },
    "new_owner_reply_events": 0, "new_working_approval_events": 0,
    "new_native_pattern_aliases": 0, "new_physical_stock_claims": 0,
    "remote_reads": 0, "remote_writes": 0, "shared_master_writes": 0,
}
wall_receipt = save("WALL_CIRCLE_REGISTER_SUPPLEMENT_VERIFIED.json", wall_result)

overlay_source = REPO / "reports/dropbox-wall-structure-2026-10-20/phase4-register-overlay-2026-10-20.json"
overlay_manifest = snapshot(overlay_source)
overlay = read(overlay_manifest["snapshot"])
receipts = {key: snapshot(path) for key, path in overlay["receipts"].items()}
plan_manifest = snapshot(overlay_source.parent / "step-01a-phase4-consolidation-plan.json")
plan = read(plan_manifest["snapshot"])
deletion = read(receipts["delete_verification"]["snapshot"])
moves = read(receipts["move_verification"]["snapshot"])
folder_ids = {r["file_id"]: r for r in overlay["current_finish_folders"]}
deleted_ids = {r["file_id"] for r in overlay["deleted_alias_folders"]}
folder_replacements = []
for pair in plan["folder_pairs"]:
    old, new = pair["source"], pair["destination"]
    assert old["file_id"] in deleted_ids and new["file_id"] in folder_ids
    current = folder_ids[new["file_id"]]
    old_path = old["path"].split("ns:202238505/", 1)[-1]
    new_path = current["current_display_path"]
    folder_replacements.append({
        "deleted_folder_id": old["file_id"], "current_folder_id": new["file_id"],
        "historical_folder_path": old_path, "current_folder_path": new_path,
        "current_folder_url": "https://www.dropbox.com/home" + quote(new_path, safe="/"),
        "native_account_path_replacement": True,
        "public_link_redirect_created": False,
    })
file_replacements = []
moved = {r["file_id"]: r for r in overlay["moved_files"]}
for row in plan["file_moves"]:
    now = moved[row["file_id"]]
    assert now["path_display"] == row["destination_path"]
    assert now["file"]["size"] == row["size"]
    file_replacements.append({
        "file_id": row["file_id"], "historical_file_path": row["source_path"],
        "current_file_path": now["path_display"],
        "historical_folder_id": row["old_parent_id"],
        "current_folder_id": row["new_parent_id"], "size": row["size"],
        "current_image_url": "https://www.dropbox.com/home" + quote(str(Path(now["path_display"]).parent), safe="/") + "?preview=" + quote(now["name"], safe=""),
        "bytes_hash_compared": False,
    })

def rewrite_native_url(url):
    parsed = urlsplit(url)
    if parsed.hostname not in {"www.dropbox.com", "dropbox.com"}:
        return url
    decoded = unquote(parsed.path)
    for replacement in folder_replacements:
        old, new = replacement["historical_folder_path"], replacement["current_folder_path"]
        for prefix in ("/home", "/preview"):
            base = prefix + old
            if decoded == base or decoded.startswith(base + "/"):
                return parsed._replace(path=quote(prefix + new + decoded[len(base):], safe="/")).geturl()
    return url

graph = read(SNAP / "canonical-products.json")
product_updates = []
for p in graph["products"]:
    updates = {key: rewrite_native_url(p[key]) for key in ["image_url", "folder_url", "context_image_url", "context_folder_url"] if p.get(key) and rewrite_native_url(p[key]) != p[key]}
    replacement = next((r for r in folder_replacements if r["deleted_folder_id"] == p["folder_id"]), None)
    if replacement:
        updates["folder_id"] = replacement["current_folder_id"]
    if updates:
        product_updates.append({
            "product_id": p["product_id"], "canonical_key": p["canonical_key"],
            "product_name": p["name"], "primary_file_id_preserved": p["file_id"],
            "historical_values": {k: p[k] for k in updates},
            "current_values": updates,
            "applies_to": "Current register link display only; original source assertion links remain immutable history",
        })
check = {
    "Writer live readback bound to terminal verification": overlay["live_readback_match_to_terminal_verification"] is True,
    "Flattening remains unapplied": "FLATTENING_NOT_APPLIED" in overlay["status"],
    "All47Phase4 files remain in7nestedfinishfolders": sum(r["files"] for r in overlay["current_finish_folders"]) == 47 and len(folder_ids) == 7 and all("/Moon Crater Phase/Moon Crater Phase 4/" in r["current_display_path"] for r in folder_ids.values()),
    "11moved file IDs and sizes agree with plan and terminal overlay": len(file_replacements) == 11,
    "Four deleted aliases map to retained destination IDs": len(folder_replacements) == len(deleted_ids) == 4 and not deleted_ids.intersection(folder_ids),
    "Native deletion verification retained178familyfiles47phase4files": deletion["status"] == "PASS" and deletion["family_file_count"] == 178 and deletion["phase4_file_count"] == 47,
    "Native move verification preserved IDspathssizes": moves["status"] == "PASS_IDS_PATHS_AND_SIZES",
    "No deleted alias link described as public": all(r["public_link_observed"] is False for r in overlay["affected_alias_link_dispositions"]),
}
current_result = {
    "schema": "boldstone.mcp4-current-register-link-overlay-independent-readback.v1",
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if all(check.values()) else "FAIL",
    "checks": {k: "PASS" if v else "FAIL" for k, v in check.items()},
    "writer_live_overlay": overlay_manifest, "writer_terminal_receipts": receipts,
    "move_plan": plan_manifest, "current_wrapper": overlay["current_wrapper"],
    "current_finish_folders": overlay["current_finish_folders"],
    "folder_replacements": folder_replacements, "moved_file_replacements": file_replacements,
    "current_product_link_updates": product_updates,
    "deleted_alias_direct_link_dispositions": overlay["affected_alias_link_dispositions"],
    "link_scope_note": overlay["link_scope_note"],
    "verification_scope": "Independent local readback of the authorized writer's native terminal receipts and just-refreshed inventory. No additional API calls by B; before/after content hashes and public URL HTTP behavior not tested.",
    "proposal_destinations_promoted_to_live": False,
    "shared_master_writes": 0, "remote_reads": 0, "remote_writes": 0,
}
current_receipt = save("MCP4_CURRENT_LINK_OVERLAY_VERIFIED.json", current_result)
print(json.dumps({
    "wall_circle": {**wall_receipt, "status": wall_result["status"], "checks": len(checks), "visual_records": len(visuals), "native_options": len(rows)},
    "mcp4": {**current_receipt, "status": current_result["status"], "checks": len(check), "products_requiring_current_link_update": len(product_updates)},
}))
