"""Prepare the verdigris Spiral variant, preserving the kept white parent."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REVIEWS = ROOT / "components/reviews"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def rel(path):
    return str(path.relative_to(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths = {"walkthrough": REVIEWS / "walkthrough_checkpoint.json", "progress": REVIEWS / "specification_review_progress.json", "component": ROOT / "components/checkpoint.json", "root": ROOT / "checkpoint.json"}
docs = {key: read(path) for key, path in paths.items()}
cp, progress, component = [docs[key] for key in ["walkthrough", "progress", "component"]]
source_white = HERE.parent / "component-review.json"
parent_approval = HERE.parent / "identity-approval.json"
out = HERE / "component-review.json"
if cp.get("current_review_record") == rel(out):
    print(json.dumps({"status": "ALREADY_PREPARED", "review": rel(out)}))
    raise SystemExit(0)
assert cp["current_component_id"] == "BC-DDR-SPIRAL" and cp["current_size_finish_variant_id"] == "DDR-SPIRAL-WHITE" and cp["current_answer_recorded"]
assert read(parent_approval)["user_statement"] == "Keep “Deco Dune Ripple — Spiral”"
assert read(parent_approval)["identity_confirmed"] and not read(parent_approval)["specifications_approved"]
now = datetime.now(timezone.utc).isoformat()
protected = [ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"], REVIEWS / "user_classifications.json", source_white, parent_approval]
hashes = {path: sha(path) for path in protected}
write(HERE / "before-verdigris-review.json", {"recorded_utc": now, "files": {rel(paths[key]): value for key, value in docs.items()}})
parent = progress["reviews"]["BC-DDR-SPIRAL"]
parent_before = copy.deepcopy(parent)
white = read(source_white)
meta = read(HERE / "metadata-links.json")
download = read(HERE / "download-receipt.json")
file, folder = meta["primary_metadata"]["file"], meta["folder_metadata"]["folder"]
assert file["id"] == "id:cnqzTNngPVsAAAAAAAyj3w" and folder["id"] == "id:cnqzTNngPVsAAAAAAAyj3g"
assert Path(file["path_display"]).parent.as_posix() == folder["path_display"]
assert file["size"] == download["actual_size"] == 6874274
assert download["content_hash"] == download["calculated_dropbox_content_hash"]
listings = [meta["solo_listing"]] + meta["context_listings"]
assert all(not listing["has_more"] and not listing["cursor"] for listing in listings)
assert sum(len(listing["entries"]) for listing in listings) == 4
previews = {item["file_name"]: item for item in meta["previews"]}
primary, containing = previews[file["id"]], previews[folder["id"]]
review = read(REVIEWS / "deco-dune-ripple-wave-review-2026-10-17/verdigris/component-review.json")
review = copy.deepcopy(review)
for item in review["specification_review_items"]:
    item["proposal_id"] = item["proposal_id"].replace("DDR-WAVE-VERDIGRIS", "DDR-SPIRAL-VERDIGRIS")
    item["basis"] = item["basis"].replace("rows61/63", "row62")
review["specification_review_items"][4]["value"]["sale_unit"] = "One verdigris Spiral panel"
review["specification_review_items"][0]["basis"] = "The native white pair listing and historical maker row62 give100×22cm per DDR2 component,6cm native depth and5–7cm historical side. The green picture shows comparable two-spiral geometry but supplies no scale or cast-specific size. Approximately100×22×6cm is a white-version comparison guess only."
review.update({
    "prepared_utc": now,
    "component_id": "BC-DDR-SPIRAL",
    "canonical_design_name": "Deco Dune Ripple — Spiral",
    "proposed_name": "Deco Dune Ripple — Spiral, Verdigris",
    "display_name": "Deco Dune Ripple — Spiral, Verdigris",
    "review_number": 27,
    "family_review_number": 4,
    "family_review_total": 4,
    "size_finish_variant_id": "DDR-SPIRAL-VERDIGRIS",
    "variant_only_review": True,
    "review_decision_mode": "SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS",
    "scope": "One depicted individual verdigris Spiral finish variant, with two spiral centres and flowing channels. White parent name/identity is already kept; no white specification approval or physical manufacture confirmation is inferred. Every green-specific specification below is an owner-check proposal, not a measured or chemically identified fact.",
    "primary_image_id": file["id"],
    "primary_folder_id": folder["id"],
    "primary_image_link": primary["copy_link_url"],
    "primary_folder_link": containing["copy_link_url"],
    "metadata_checked_utc": meta["observed_utc"],
    "reference_refresh": rel(HERE / "metadata-links.json"),
    "primary_original_receipt": rel(HERE / "download-receipt.json"),
    "image_review_index": rel(HERE / "image-review-index.json"),
    "context_image_id": "id:cnqzTNngPVsAAAAAAAyj4g",
    "context_image_link": previews["id:cnqzTNngPVsAAAAAAAyj4g"]["copy_link_url"],
    "series_image_id": "id:cnqzTNngPVsAAAAAAAyiPQ",
    "series_image_link": previews["id:cnqzTNngPVsAAAAAAAyiPQ"]["copy_link_url"],
    "parent_identity_approval": rel(parent_approval),
    "parent_identity_approval_scope": "White Spiral name and depicted identity only; all six white specification groups remain pending.",
    "white_source_review": rel(source_white),
    "source_offer_refs": [],
    "related_white_offer_refs": ["O013"],
    "platform_mapping": {"squarespace_id": None, "shopify_handle": None, "shared_sku": None, "status": "NO CONFIRMED VERDIGRIS-SPECIFIC PLATFORM MATCH", "related_white_arrangement": copy.deepcopy(white["platform_mapping"]), "related_reference_scope": "The confirmed shared SKU DDR-2-100.44 covers the white Spiral and Wave arrangement. It remains related design/source context, not an exact finish or standalone verdigris offer match.", "live_account_records_refreshed": False},
    "photo_coverage": {"complete_individual_front": True, "dedicated_detail": False, "rear": False, "room_context": True, "series_arrangement": True, "arrangement_description": "Horizontal Wave/Spiral pair in room context; two floor-propped Wave/Spiral/Wave views. Repeated Wave positions are not additional design identities or stock counts.", "scope": "One solo plus3context files freshly listed in3folders. Primary current original downloaded and Dropbox-hash verified; all4 cached thumbnails inspected. Context originals not re-downloaded.", "installation_provenance": "UNCONFIRMED", "manufacture_confirmed": False, "physical_stock_inferred": False},
    "identity_confirmed": False,
    "specifications_approved": False,
    "physical_specs_verified": False,
    "open_gaps": ["Actual manufacture/finish availability and measured dimensions/depth", "Actual dry mass and material/binder/reinforcement/sealing/coating chemistry", "Dedicated detail and rear fixing photographs; actual hardware/attachment/layout and rated load", "Approve individual price and sale policy; establish actual stock, capacity and lead time", "Exact Squarespace/Shopify/shared-SKU offer for this individual verdigris Spiral", "Actual installation provenance, care and packing dimensions/weight"],
    "next_review_after_keep": {"component_id": "BC-DECO-1", "review_number": 32, "family_review_number": 1},
    "next_global_component_id": "BC-DECO-1",
    "remote_files_changed": False,
    "live_platform_records_changed": False,
})
write(out, review)
white_variant = {
    "size_finish_variant_id": "DDR-SPIRAL-WHITE", "canonical_name": white["proposed_name"],
    "review_record": rel(source_white), "identity_confirmed": True, "identity_approval": rel(parent_approval),
    "primary_image_id": white["primary_image_id"], "primary_folder_id": white["primary_folder_id"],
    "specification_proposals": copy.deepcopy(white["specification_review_items"]), "specifications_approved": False,
    "proposals_approved": False, "physical_specs_verified": False, "specification_review_status": "NAME KEPT; SIX SPECIFICATION GROUPS REMAIN PENDING",
}
green_variant = {
    "size_finish_variant_id": "DDR-SPIRAL-VERDIGRIS", "canonical_name": review["proposed_name"],
    "review_record": rel(out), "identity_confirmed": False, "primary_image_id": file["id"], "primary_folder_id": folder["id"],
    "specification_proposals": copy.deepcopy(review["specification_review_items"]), "specifications_approved": False,
    "proposals_approved": False, "physical_specs_verified": False, "photo_coverage": review["photo_coverage"], "platform_mapping": review["platform_mapping"],
}
parent["size_finish_variants"] = {"DDR-SPIRAL-WHITE": white_variant, "DDR-SPIRAL-VERDIGRIS": green_variant}
for pending in parent["pending_size_finish_variants"]:
    if pending["variant_id"] == "DDR-SPIRAL-VERDIGRIS":
        pending.update({"review_status": "PRESENTED; AWAITING OWNER NAME/IDENTITY AND SPECIFICATION REVIEW", "review_record": rel(out)})
assert {key:value for key,value in parent.items() if key not in ["size_finish_variants", "pending_size_finish_variants"]} == {key:value for key,value in parent_before.items() if key not in ["size_finish_variants", "pending_size_finish_variants"]}
progress["updated_utc"] = now
cp.update({
    "proposed_name": review["proposed_name"], "state": "Awaiting individual verdigris Spiral name/identity and six working specification guesses",
    "current_size_finish_variant_id": "DDR-SPIRAL-VERDIGRIS", "current_review_record": rel(out),
    "current_family_review_number": 4, "current_family_review_total": 4,
    "primary_image": {"file_id": file["id"], "name": file["name"], "path_display": file["path_display"], "copy_link_url": primary["copy_link_url"], "open_in_dropbox_url": primary["open_in_dropbox_url"]},
    "containing_folder": {"folder_id": folder["id"], "name": folder["name"], "path_display": folder["path_display"], "copy_link_url": containing["copy_link_url"], "open_in_dropbox_url": containing["open_in_dropbox_url"]},
    "answer_state": "No answer yet for verdigris finish; kept white name/identity remains unchanged. A name-only reply confirms only name and depicted variant identity.",
    "question_scope": "Keep Deco Dune Ripple — Spiral, Verdigris for the depicted individual green panel. Display six guesses:approximately100 H×22 W×6 D cm;10kg(range8–12);AC730 with applied verdigris-effect patina;one small rear stainless fixing in upper third(actual hardware/load unknown);£550 individual price;made to order individually(stock/lead time/manufacture unknown). A name-only reply approves only name/identity.",
    "metadata_checked_utc": meta["observed_utc"], "current_answer_recorded": False, "current_specification_answer_recorded": False,
    "current_dimension_answer_recorded": False, "working_version_user_approved": False,
    "displayed_identity_evidence_file_ids": [file["id"]], "displayed_identity_evidence_folder_ids": [folder["id"]],
    "current_component_source_notes": [item["display"] for item in review["specification_review_items"]],
    "family_review_evidence": rel(HERE / "metadata-links.json"), "next_review_after_keep": review["next_review_after_keep"],
    "review_decision_mode": review["review_decision_mode"], "updated_utc": now,
})
receipt = "components/parallel-reviews/riyadh-2026-10-17/spiral-panel-2/review-approval.json"
if (ROOT / receipt).exists() and not any(item.get("receipt") == receipt for item in cp.setdefault("parallel_import_queue", [])):
    cp["parallel_import_queue"].append({"component_id": "BC-RIYADH-2", "receipt": receipt, "receipt_sha256": sha(ROOT / receipt), "status": "RECEIVED; PENDING NEXT SERIALIZED IMPORT", "scope": "Name/depicted identity receipt reported; independently verify exact owner statement and proposal context before importing any scope.", "approval_imported": False, "recorded_utc": now})
component["interactive_review_state"].update({"current_name": review["proposed_name"], "state": cp["state"], "current_size_finish_variant_id": "DDR-SPIRAL-VERDIGRIS", "family_review_number": 4, "specification_proposals_approved": False, "working_version_user_approved": False, "review_decision_mode": review["review_decision_mode"]})
component["current_component_review_record"] = rel(out)
component["last_family_media_review"] = {"family": "Deco Dune Ripple", "finish": "Spiral Verdigris", "observed_utc": meta["observed_utc"], "scope": review["photo_coverage"]["scope"], "files": 4, "evidence": rel(HERE / "metadata-links.json"), "workbook_contains_this_live_media_audit": False}
component["updated_utc"] = now
docs["root"]["current_component_review"] = copy.deepcopy(component)
for key, path in paths.items():
    write(path, docs[key])
assert all(sha(path) == expected for path, expected in hashes.items())
assert read(paths["root"])["current_component_review"] == read(paths["component"])
validation = {"status": "PASS", "component_id": "BC-DDR-SPIRAL", "variant_id": "DDR-SPIRAL-VERDIGRIS", "review_number": 27, "family_review_number": 4, "source_file_id": file["id"], "source_folder_id": folder["id"], "complete_individual_image_observed": True, "primary_original_hash_verified": True, "files_listed": 4, "folders": 3, "cached_thumbnails_inspected": 4, "six_groups_are_unapproved_proposals": True, "white_parent_name_and_specs_preserved": True, "user_decisions_source_model_workbook_unchanged": True, "remote_files_changed": False}
write(HERE / "review-validation.json", validation)
print(json.dumps(validation))
