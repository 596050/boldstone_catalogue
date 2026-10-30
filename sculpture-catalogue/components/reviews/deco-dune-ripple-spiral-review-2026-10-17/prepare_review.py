"""Prepare the next individual white Spiral review; no owner approval implied."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / "components/reviews"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def rel(path):
    return str(path.relative_to(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths = {"walkthrough": REVIEWS / "walkthrough_checkpoint.json", "progress": REVIEWS / "specification_review_progress.json", "component": ROOT / "components/checkpoint.json", "root": ROOT / "checkpoint.json"}
docs = {key: read(path) for key, path in paths.items()}
cp, progress, component = [docs[key] for key in ["walkthrough", "progress", "component"]]
out = HERE / "component-review.json"
if cp.get("current_component_id") == "BC-DDR-SPIRAL" and cp.get("current_review_record") == rel(out):
    print(json.dumps({"status": "ALREADY_PREPARED", "review": rel(out)}))
    raise SystemExit(0)
assert cp["current_component_id"] == "BC-DDR-WAVE"
assert cp["current_size_finish_variant_id"] == "DDR-WAVE-VERDIGRIS" and cp["current_answer_recorded"]
assert read(HERE.parent / "deco-dune-ripple-wave-review-2026-10-17/verdigris/identity-approval.json")["identity_confirmed"]
assert "BC-DDR-SPIRAL" not in progress["reviews"]
now = datetime.now(timezone.utc).isoformat()
protected = [ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"], REVIEWS / "user_classifications.json"]
protected_hashes = {path: sha(path) for path in protected}
write(HERE / "before-spiral-review.json", {"recorded_utc": now, "files": {rel(paths[key]): value for key, value in docs.items()}})
meta = read(HERE / "metadata-links.json")
download = read(HERE / "download-receipt.json")
file = meta["primary_metadata"]["file"]
folder = meta["folder_metadata"]["folder"]
listing = meta["individual_white_folder_listing"]
assert not listing["has_more"] and not listing["cursor"]
assert len(listing["entries"]) == 45
assert file["id"] == "id:cnqzTNngPVsAAAAAAAyj_Q"
assert folder["id"] == "id:cnqzTNngPVsAAAAAAAyiPg"
assert Path(file["path_display"]).parent.as_posix() == folder["path_display"]
assert download["content_hash"] == download["calculated_dropbox_content_hash"]
assert file["size"] == download["actual_size"] == 6054980
previews = {entry["file_name"]: entry for entry in meta["previews"]}
primary, containing = [previews[x["id"]] for x in [file, folder]]
model = read(ROOT / "components/evidence/component_register.json")
wave = read(REVIEWS / "deco-dune-ripple-wave-review-2026-10-17/component-review.json")
items = copy.deepcopy(wave["specification_review_items"])
for item in items:
    item["proposal_id"] = item["proposal_id"].replace("DDR-WAVE-WHITE", "DDR-SPIRAL-WHITE")
    item["display"] = item["display"].replace("Wave", "Spiral")
    item["basis"] = item["basis"].replace("rows61/63", "row62").replace("Rows61/63", "Row62")
items[0]["basis"] = "Native O013 and the public two-panel listing give 100×22×6 cm per panel, 100×44×6 cm overall excluding the gap. Maker row62 gives one DDR2 cast approximately100×22 cm with a5–7 cm side measurement. These are source claims for the standard white component; the pictured cast has not been measured."
items[1]["basis"] = "Maker row62 independently estimates8–10 kg for each DDR2 cast; dated2025 individual price lists give10 kg. O013's20 kg remains a two-panel offer-level claim and has not been divided to infer this individual weight."
items[2]["basis"] = "Maker row62 explicitly specifies White Marble Stone Finish Jesmonite AC730 for one DDR2 panel. The native/public pair listing also states the white finish. Actual chemistry, reinforcement and sealing of the depicted cast remain unverified."
items[3]["basis"] = "Maker row62 instructs one small stainless-steel fixing at the centre back in the top third, aligned with other pieces in the series. No rear photograph, hardware specification or rated load found. Intended orientation requires checking because a horizontal arrangement may need different mounting positions."
items[4]["value"]["sale_unit"] = "One white Spiral panel"
items[4]["display"] = "£450 per individual Spiral panel — new proposal"
items[5]["basis"] = "Propose sale as an individual made-to-order panel. The existing native offer covers the Spiral and Wave pair. Its active/Unlimited flags and image presence do not establish current individual stock, production readiness or lead time."
source_offer = next(x for x in model["platform_records"] if x["offer_ref"] == "O013")
platform = copy.deepcopy(wave["platform_mapping"])
platform["component_role"] = "One Spiral DDR2 panel in the matched two-panel arrangement"
platform["bom_position"] = next(x for x in model["bom"] if x["component_id"] == "BC-DDR-SPIRAL" and x["offer_ref"] == "O013")
coverage = {
    "complete_individual_front": True,
    "detail": True,
    "rear": False,
    "room_display": True,
    "series_arrangement": True,
    "scope": "Fresh complete45-file white-folder listing, current primary original downloaded and Dropbox-hash verified; all45 cached individual-folder thumbnails and2 retained arrangement thumbnails inspected. Remaining originals not downloaded; paired/triptych folder census not repeated this turn.",
    "room_observation": "Primary shows one complete two-spiral white relief against a wall. Alternate room photographs show it floor-propped. Triptych example shows Spiral between two repeated Waves, also floor-propped.",
    "installation_provenance": "UNCONFIRMED; verified client installation not established",
    "physical_stock_inferred": False,
}
next_review = {"component_id": "BC-DDR-SPIRAL", "review_number": 27, "family_review_number": 4, "size_finish_variant_id": "DDR-SPIRAL-VERDIGRIS"}
review = {
    "schema_version": 1,
    "prepared_utc": now,
    "component_id": "BC-DDR-SPIRAL",
    "proposed_name": "Deco Dune Ripple — Spiral",
    "display_name": "Deco Dune Ripple — Spiral, White",
    "canonical_design_name": "Deco Dune Ripple — Spiral",
    "maker_code": "DDR2",
    "family": "Deco Dune Ripple",
    "review_number": 27,
    "family_review_number": 3,
    "family_review_total": 4,
    "size_finish_variant_id": "DDR-SPIRAL-WHITE",
    "variant_only_review": False,
    "review_decision_mode": "COMPONENT_NAME_AND_SPECIFICATIONS",
    "scope": "One individual white Spiral design/component with two spiral centres and long flowing ripple channels. The white and verdigris finishes are reviewed separately. Shared-SKU offerO013 is the two-panel Spiral and Wave arrangement, not an established individual offer or cast identity.",
    "primary_image_id": file["id"],
    "primary_folder_id": folder["id"],
    "primary_image_link": primary["copy_link_url"],
    "primary_folder_link": containing["copy_link_url"],
    "metadata_checked_utc": meta["observed_utc"],
    "reference_refresh": rel(HERE / "metadata-links.json"),
    "primary_original_receipt": rel(HERE / "download-receipt.json"),
    "image_review_index": rel(HERE / "image-review-index.json"),
    "specification_review_items": items,
    "source_offer_refs": ["O013"],
    "source_offer_snapshot": source_offer,
    "maker_claims": [x for x in model["claims"] if x["component_id"] == "BC-DDR-SPIRAL" and "row62" in x.get("source_ref", "")],
    "historical_individual_price_evidence": read(HERE / "advisory-packet-used.json")["dated_supplements"],
    "advisory_preparation": rel(HERE / "advisory-packet-used.json"),
    "platform_mapping": platform,
    "public_page_check": {"checked_utc": now, "source_url": source_offer["source_url"], "web_crawl_state": "today as reported by web tool", "public_pair_price_gbp": 880, "native_per_panel_dimensions_cm": [100,22,6], "native_pair_dimensions_cm": [100,44,6], "individual_offer_confirmed": False, "live_account_records_refreshed": False},
    "photo_coverage": coverage,
    "arrangement_examples": [{"file_id": fid, "folder_id": folder_id, "image_link": previews[fid]["copy_link_url"], "scope": scope} for fid, folder_id, scope in [("id:cnqzTNngPVsAAAAAAArqeg", "id:cnqzTNngPVsAAAAAAAyiPw", "White Spiral + Wave diptych; native listing arrangement, context only"), ("id:cnqzTNngPVsAAAAAAArtPQ", "id:cnqzTNngPVsAAAAAAAyiQA", "White Wave/Spiral/Wave triptych, floor-propped display; repeated Wave design positions")]],
    "other_family_reviews": ["DDR-SPIRAL-VERDIGRIS"],
    "identity_confirmed": False,
    "specifications_approved": False,
    "physical_specs_verified": False,
    "open_gaps": ["Confirm source size and calculated weight apply to the depicted white cast", "Confirm actual material, reinforcement and sealing", "Rear photograph and actual hardware/layout/rated load, including intended orientation", "Approve individual retail price and sale policy; establish stock, production readiness and lead time", "Existing individual Squarespace/Shopify offer remains unconfirmed; matched O013 is a two-panel arrangement", "Verify installation provenance; current room/series images do not prove manufacture or current stock", "Care and packing dimensions/weight"],
    "next_review_after_keep": next_review,
    "next_global_component_id": "BC-DECO-1",
    "after_family_next_unclaimed": {"component_id": "BC-DECO-1", "review_number": 32},
    "remote_files_changed": False,
    "live_platform_records_changed": False,
}
write(out, review)
progress["reviews"]["BC-DDR-SPIRAL"] = {
    "reviewed_utc": now, "identity_confirmed": False, "specifications_approved": False, "physical_specs_verified": False,
    "proposed_name": review["proposed_name"], "size_finish_variant_id": review["size_finish_variant_id"],
    "specification_proposals": copy.deepcopy(items), "source_specifications_recorded": True,
    "maker_claims": review["maker_claims"], "source_offer_refs": ["O013"], "platform_mapping": platform,
    "primary_image_id": file["id"], "primary_folder_id": folder["id"], "review_record": rel(out),
    "gaps": review["open_gaps"], "photo_coverage": coverage,
    "pending_size_finish_variants": [{"variant_id": "DDR-SPIRAL-VERDIGRIS", "proposed_name": "Deco Dune Ripple — Spiral, Verdigris", "review_status": "NOT YET PRESENTED", "primary_file_id": "id:cnqzTNngPVsAAAAAAAyj3w", "primary_folder_id": "id:cnqzTNngPVsAAAAAAAyj3g"}],
}
progress["updated_utc"] = now
cp.update({
    "current_component_id": "BC-DDR-SPIRAL", "current_review_number": 27,
    "current_size_finish_variant_id": "DDR-SPIRAL-WHITE", "proposed_name": review["proposed_name"],
    "state": "Awaiting individual white Spiral name/identity and source/working specification review",
    "primary_image": {"file_id": file["id"], "name": file["name"], "path_display": file["path_display"], "copy_link_url": primary["copy_link_url"], "open_in_dropbox_url": primary["open_in_dropbox_url"]},
    "containing_folder": {"folder_id": folder["id"], "name": folder["name"], "path_display": folder["path_display"], "copy_link_url": containing["copy_link_url"], "open_in_dropbox_url": containing["open_in_dropbox_url"]},
    "answer_state": "No user answer yet; all source/working proposals await checking. A name-only Keep confirms only name and depicted component identity.",
    "question_scope": "Keep Deco Dune Ripple — Spiral for the pictured individual white panel. Six displayed source/working groups are100 H×22 W×6 D cm(native; maker side5–7),8–10kg historical maker estimate,AC730 white marble stone historical standard,one small rear stainless fixing centre upper third(historical instruction; actual hardware/load unknown),£450 individual NEW price proposal,and individual made-to-order proposal. A name-only reply confirms identity only; all estimates retain their source state.",
    "metadata_checked_utc": meta["observed_utc"], "current_answer_recorded": False, "current_specification_answer_recorded": False,
    "current_dimension_answer_recorded": False, "working_version_user_approved": False,
    "current_review_record": rel(out), "review_decision_mode": "COMPONENT_NAME_AND_SPECIFICATIONS",
    "current_family_review_number": 3, "current_family_review_total": 4, "active_family": "Deco Dune Ripple",
    "family_review_evidence": rel(HERE / "metadata-links.json"), "next_review_after_keep": next_review,
    "displayed_identity_evidence_file_ids": [file["id"]], "displayed_identity_evidence_folder_ids": [folder["id"]],
    "current_component_source_notes": [item["display"] for item in items], "updated_utc": now,
})
component["interactive_review_state"].update({
    "current_component_id": "BC-DDR-SPIRAL", "review_number": 27, "current_size_finish_variant_id": "DDR-SPIRAL-WHITE",
    "current_name": review["proposed_name"], "state": cp["state"], "family_review_number": 3,
    "specification_proposals_approved": False, "working_version_user_approved": False, "review_decision_mode": cp["review_decision_mode"],
})
component["current_component_review_record"] = rel(out)
component["last_family_media_review"] = {"family": "Deco Dune Ripple", "finish": "Spiral White", "observed_utc": meta["observed_utc"], "scope": coverage["scope"], "files": 45, "evidence": rel(HERE / "metadata-links.json"), "workbook_contains_this_live_media_audit": False}
component["updated_utc"] = now
docs["root"]["current_component_review"] = copy.deepcopy(component)
for key, path in paths.items():
    write(path, docs[key])
assert all(sha(path) == expected for path, expected in protected_hashes.items())
assert read(paths["walkthrough"])["current_component_id"] == "BC-DDR-SPIRAL"
assert read(paths["root"])["current_component_review"] == read(paths["component"])
validation = {"status": "PASS", "component_id": "BC-DDR-SPIRAL", "review_number": 27, "family_review_number": 3, "primary_complete_individual_observed": True, "current_original_dropbox_hash_verified": True, "white_folder_files": 45, "cached_thumbnails_inspected": 47, "specification_groups": len(items), "native_pair_values_kept_separate": True, "identity_or_specifications_approved": False, "protected_source_model_workbook_and_user_decisions_unchanged": True, "remote_files_changed": False}
write(HERE / "review-validation.json", validation)
print(json.dumps(validation))
