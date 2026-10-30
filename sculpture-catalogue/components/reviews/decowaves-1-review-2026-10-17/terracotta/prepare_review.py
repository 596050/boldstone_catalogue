"""Prepare the individual terracotta Decowaves 1 card from current evidence."""
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


def write(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def rel(path):
    return str(path.relative_to(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths = {"walkthrough": REVIEWS / "walkthrough_checkpoint.json", "progress": REVIEWS / "specification_review_progress.json", "component": ROOT / "components/checkpoint.json", "root": ROOT / "checkpoint.json"}
docs = {key: read(path) for key, path in paths.items()}
cp, progress, component = [docs[key] for key in ["walkthrough", "progress", "component"]]
out = HERE / "component-review.json"
if cp.get("current_review_record") == rel(out):
    print(json.dumps({"status": "ALREADY_PREPARED", "review": rel(out)}))
    raise SystemExit(0)
assert cp["current_component_id"] == "BC-DDR-SPIRAL" and cp["current_size_finish_variant_id"] == "DDR-SPIRAL-VERDIGRIS" and cp["current_answer_recorded"]
assert cp["review_order"].index("BC-DECO-1") + 1 == 32
assert "BC-DECO-1" not in progress["reviews"]
now = datetime.now(timezone.utc).isoformat()
protected = [ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"], REVIEWS / "user_classifications.json", ROOT / cp["current_review_record"], REVIEWS / "deco-dune-ripple-spiral-review-2026-10-17/verdigris/identity-approval.json"]
hashes = {path: sha(path) for path in protected}
write(HERE / "before-decowaves-review.json", {"recorded_utc": now, "files": {rel(paths[key]): value for key, value in docs.items()}})
meta, receipt, rear_receipt = [read(HERE / name) for name in ["metadata-links.json", "download-receipt.json", "rear-download-receipt.json"]]
file, folder = meta["primary_metadata"]["file"], meta["folder_metadata"]["folder"]
assert file["id"] == "id:cnqzTNngPVsAAAAAAAyfBA" and folder["id"] == "id:cnqzTNngPVsAAAAAAAyiXA"
assert Path(file["path_display"]).parent.as_posix() == folder["path_display"]
for download in [receipt, rear_receipt]:
    assert download["content_hash"] == download["calculated_dropbox_content_hash"]
    assert sha(Path(download["local_path"])) == download["sha256"]
assert not meta["family_census"]["has_more"] and not meta["family_census"]["cursor"]
entries = meta["family_census"]["entries"]
assert len([e for e in entries if e["object_type"] == "file"]) == 157
assert len([e for e in entries if e["object_type"] == "folder"]) == 12
index = read(HERE / "image-review-index.json")
assert len(index) == 15
previews = {e["file_name"]:e for e in meta["previews"]}
rear_previews = {e["file_name"]:e for e in meta["rear_reference"]["previews"]}
primary, containing = previews[file["id"]], previews[folder["id"]]
model = read(ROOT / "components/evidence/component_register.json")
offers = {e["offer_ref"]:e for e in model["platform_records"] if e["offer_ref"] in ["O050", "O060"]}
single = offers["O050"]
items = [
    {"proposal_id":"DECO-1-TERRACOTTA-DIMENSIONS", "field":"Individual dimensions", "value":{"source_height_cm":90,"source_width_cm":15,"source_overall_depth_cm":9,"current_cast_measured":False}, "display":"90 H × 15 W × 9 D cm — individual terracotta listing claim", "status":"NATIVE AND CURRENT PUBLIC INDIVIDUAL CLAIM; NOT OWNER-MEASURED", "basis":"O050 and the public terracotta single-panel page state90×15×9cm. Keep this9cm terracotta depth separate from O060's8cm-per-panel verdigris claim; no measurement is inferred from the picture.", "source_refs":["SS Wall Products!row55/Description",single["source_url"]]},
    {"proposal_id":"DECO-1-TERRACOTTA-WEIGHT", "field":"Individual dry weight", "value":{"source_approximate_kg":6,"current_cast_weighed":False}, "display":"Approximately 6 kg — individual terracotta listing claim", "status":"SOURCE APPROXIMATION; NOT WEIGHED", "basis":"O050 directly states approximately6kg for one terracotta panel. O060's approximately14kg is a separate verdigris pair claim and is not divided or transferred to this component.", "source_refs":["SS Wall Products!row55/Description",single["source_url"]]},
    {"proposal_id":"DECO-1-TERRACOTTA-MATERIAL", "field":"Material and finish", "value":{"source_substrate":"Gypsum composite","source_finish":"Terracotta surface effect","actual_binder":None,"actual_reinforcement":None,"actual_sealing":None}, "display":"Gypsum composite with terracotta-effect surface — individual listing claim", "status":"SOURCE-SPECIFIED MATERIAL; ACTUAL COMPOSITION UNVERIFIED", "basis":"The linked native/public individual offer explicitly describes gypsum composite and a terracotta surface effect. Do not substitute AC730 or assume fired ceramic terracotta, solid bronze, white Frozen Decowaves mould equivalence or exterior performance from colour.", "source_refs":["SS Wall Products!row55/Description",single["source_url"]]},
    {"proposal_id":"DECO-1-TERRACOTTA-FIXING", "field":"Fixing", "value":{"source_type":"Keyhole fixing","source_orientation":"Vertical","observed_rear_plate_count_per_depicted_panel":1,"observed_plate_material":"Metal; alloy unconfirmed","actual_wall_hardware":None,"rated_load":None}, "display":"Rear keyhole fixing; one metal plate visible per panel in paired rear photograph", "status":"NATIVE/PUBLIC CLAIM WITH REAR IMAGE OBSERVATION; NO LOAD RATING", "basis":"O050 explicitly specifies a vertical keyhole fixing. Its current public rear photo shows one metal keyhole plate. Current Dropbox paired-rear original id:cnqzTNngPVsAAAAAAAye7g independently shows one plate on each pictured terracotta panel. Attachment strength, alloy, wall fastener specification and rated load remain unknown; no installation design is inferred.", "source_refs":["SS Wall Products!row55/Description",single["source_url"],"id:cnqzTNngPVsAAAAAAAye7g"]},
    {"proposal_id":"DECO-1-TERRACOTTA-PRICE", "field":"Individual retail price", "value":{"observed_public_amount":48.44,"native_amount":48.44,"proposed_repriced_amount":300,"currency":"GBP","sale_unit":"One terracotta Decowaves 1 panel","proposal_discussion_range_gbp":[280,350],"proposed_price_approved":False}, "display":"£48.44 currently listed; £300 proposed if repricing — requires owner check", "status":"CURRENT SOURCE PRICE RETAINED; OPTIONAL NEW PRICE PROPOSAL UNAPPROVED", "basis":"Native O050 and the refreshed public page both display48.44. Preserve it exactly and flag the large difference from other individual references; do not label it an established error or change it automatically. An optional300 proposal lies within the advisory280–350 range informed by the dated281.97 white90×15 reference and an unpriced coloured-finish difference. It is not derived by dividing O060's600 pair price and does not establish mould or material equivalence.", "source_refs":["SS Wall Products!row55/Price",single["source_url"],"retail-2025:90×15 individual dated reference; pricing analogy only"]},
    {"proposal_id":"DECO-1-TERRACOTTA-AVAILABILITY", "field":"Availability", "value":{"proposed_sale_status":"Enquire / made to order individually","physical_stock_quantity":None,"lead_time":None,"production_capacity":None}, "display":"Enquire / made to order individually — proposed; stock and lead time unknown", "status":"CURRENT OFFER PRESENT; PHYSICAL AVAILABILITY AND SALE POLICY UNCONFIRMED", "basis":"The public individual page was readable and showed Add to Cart; native Unlimited/visible flags remain source settings. These do not confirm finished stock, current production capacity or dispatch time. Propose individual made-to-order/enquiry status for owner review only.", "source_refs":["SS Wall Products!row55/Stock",single["source_url"]]},
]
mapping = {"squarespace_id":single["sq_id"],"shopify_handle":None,"sku":single["sku"],"shared_sku":None,"offer_ref":"O050","platform_status":"SQUARESPACE INDIVIDUAL OFFER IDENTIFIED; NO CONFIRMED SHOPIFY COUNTERPART","dropbox_status":"CONFIRMED IMAGE LINK; CURRENT PUBLIC FRONT VISUALLY COMPARED","individual_offer_confirmed":True,"sale_unit":"ONE TERRACOTTA PANEL","public_image_comparison":"Same individual terracotta folded-wave relief, wall-block pattern and camera view as selected Dropbox primary; image encoding/resolution differ, no byte-equality claim.","live_account_records_refreshed":False,"related_offer_ref":"O060","related_offer_scope":"Coloured verdigris two-panel arrangement; values remain arrangement/finish-specific","source_title_alias":single["title"],"white_frozen_designs_merged":False}
coverage = {"complete_individual_front":True,"oblique_views":True,"wall_display":True,"series_arrangement":True,"rear":True,"dedicated_detail":False,"wider_room":False,"installation_provenance":"UNCONFIRMED","physical_stock_inferred":False,"scope":"Fresh Decowaves family census157files/12folders complete. Selected7individual terracotta and8terracotta pair thumbnails inspected; current individual and paired-rear originals downloaded/hash-verified. Other142family images not visually recertified this turn.","rear_scope":"Paired rear view has one visible keyhole plate on each panel; public single listing has a separate rear photo. Rear photographs do not establish load capacity."}
next_review = {"component_id":"BC-DECO-1","review_number":32,"family_review_number":2,"size_finish_variant_id":"DECO-1-VERDIGRIS"}
family_order = ["DECO-1-TERRACOTTA","DECO-1-VERDIGRIS","DECO-2-TERRACOTTA","DECO-2-VERDIGRIS","FDW-1-WHITE","FDW-2-WHITE"]
review = {"schema_version":1,"prepared_utc":now,"component_id":"BC-DECO-1","canonical_design_name":"Decowaves 1","proposed_name":"Decowaves 1 — Terracotta","display_name":"Decowaves 1 — Terracotta","family":"Decowaves","review_number":32,"family_review_number":1,"family_review_total":6,"size_finish_variant_id":"DECO-1-TERRACOTTA","variant_only_review":False,"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS","scope":"One individual terracotta coloured Decowaves 1 design/component, with large alternating folded planes. Keep separate from coloured Decowaves 2, its verdigris finish and the white Frozen Decowaves records until design/mould equivalence is explicitly resolved.","primary_image_id":file["id"],"primary_folder_id":folder["id"],"primary_image_link":primary["copy_link_url"],"primary_folder_link":containing["copy_link_url"],"metadata_checked_utc":meta["observed_utc"],"reference_refresh":rel(HERE/"metadata-links.json"),"primary_original_receipt":rel(HERE/"download-receipt.json"),"rear_image_id":"id:cnqzTNngPVsAAAAAAAye7g","rear_folder_id":"id:cnqzTNngPVsAAAAAAAye5A","rear_image_link":rear_previews["id:cnqzTNngPVsAAAAAAAye7g"]["copy_link_url"],"rear_original_receipt":rel(HERE/"rear-download-receipt.json"),"series_image_id":"id:cnqzTNngPVsAAAAAAAye5g","series_folder_id":"id:cnqzTNngPVsAAAAAAAye5A","series_image_link":previews["id:cnqzTNngPVsAAAAAAAye5g"]["copy_link_url"],"image_review_index":rel(HERE/"image-review-index.json"),"advisory_preparation":rel(HERE/"advisory-packet-used.json"),"specification_review_items":items,"source_offer_refs":["O050"],"related_offer_refs":["O060"],"source_offer_snapshots":list(offers.values()),"platform_mapping":mapping,"public_page_check":{"checked_utc":now,"source_url":single["source_url"],"web_crawl_state":"today as reported by tool","individual_price_gbp":48.44,"dimensions_cm":[90,15,9],"approximate_weight_kg":6,"material":"Gypsum composite, terracotta effect","fixing":"Keyhole, vertical","tool_result":rel(HERE/"public-page-tool-result.txt"),"public_image_receipts":rel(HERE/"public-image-receipts.json"),"pair_page_status":"Tool could not access O060; native/cached pair evidence retained without inferring deletion or current price"},"photo_coverage":coverage,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"open_gaps":["Confirm current individual dimensions and dry weight against source claims","Confirm actual gypsum binder, reinforcement, finish process and sealing","Rear keyhole plate attachment, intended wall hardware and rated load","Check currently displayed£48.44 price; optional£300 repricing proposal requires explicit approval","Approve sale policy and confirm physical stock/production capacity/lead time","Shopify counterpart not confirmed","Wider room/client-installation photograph for this terracotta finish not identified; dedicated close-up absent","Care and packing dimensions/weight; no automatic alias with white Frozen Decowaves"],"next_review_after_keep":next_review,"next_global_component_id":"BC-DECO-2","other_family_reviews":family_order[1:],"remote_files_changed":False,"live_platform_records_changed":False}
write(out, review)
progress["reviews"]["BC-DECO-1"] = {"reviewed_utc":now,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"proposed_name":review["proposed_name"],"size_finish_variant_id":review["size_finish_variant_id"],"specification_proposals":copy.deepcopy(items),"source_specifications_recorded":True,"source_offer_refs":["O050"],"platform_mapping":mapping,"primary_image_id":file["id"],"primary_folder_id":folder["id"],"review_record":rel(out),"gaps":review["open_gaps"],"photo_coverage":coverage,"pending_size_finish_variants":[{"variant_id":"DECO-1-VERDIGRIS","proposed_name":"Decowaves 1 — Verdigris","review_status":"NOT YET PRESENTED","primary_file_id":"id:cnqzTNngPVsAAAAAAAykAQ","primary_folder_id":"id:cnqzTNngPVsAAAAAAAyiXg"}]}
progress["updated_utc"] = now
cp.update({"current_component_id":"BC-DECO-1","current_review_number":32,"current_size_finish_variant_id":"DECO-1-TERRACOTTA","proposed_name":review["proposed_name"],"state":"Awaiting individual terracotta Decowaves 1 name/identity and source/proposed specification review","primary_image":{"file_id":file["id"],"name":file["name"],"path_display":file["path_display"],"copy_link_url":primary["copy_link_url"],"open_in_dropbox_url":primary["open_in_dropbox_url"]},"containing_folder":{"folder_id":folder["id"],"name":folder["name"],"path_display":folder["path_display"],"copy_link_url":containing["copy_link_url"],"open_in_dropbox_url":containing["open_in_dropbox_url"]},"answer_state":"No answer yet. A name-only Keep approves only depicted component name/identity; source specifications, price change and sale policy require separate checking.","question_scope":"Keep Decowaves 1 — Terracotta as the name/identity of this individual folded-wave panel. Six displayed groups:source90×15×9cm,sourceapprox6kg,sourcegypsumcomposite/terracottaeffect,sourcekeyhole/observedrearplate,listed£48.44withoptional£300repricingproposal,andindividualenquire/madetoorderpolicyproposal. A name-only reply confirms name/identity only.","metadata_checked_utc":meta["observed_utc"],"current_answer_recorded":False,"current_specification_answer_recorded":False,"current_dimension_answer_recorded":False,"working_version_user_approved":False,"current_review_record":rel(out),"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS","current_family_review_number":1,"current_family_review_total":6,"active_family":"Decowaves","family_review_order":family_order,"family_review_evidence":rel(HERE/"metadata-links.json"),"next_review_after_keep":next_review,"displayed_identity_evidence_file_ids":[file["id"]],"displayed_identity_evidence_folder_ids":[folder["id"]],"current_component_source_notes":[x["display"] for x in items],"updated_utc":now})
cp["review_policy"]["active_family_priority"] = "Decowaves"
component["interactive_review_state"].update({"current_component_id":"BC-DECO-1","review_number":32,"current_size_finish_variant_id":"DECO-1-TERRACOTTA","current_name":review["proposed_name"],"state":cp["state"],"active_family":"Decowaves","family_review_number":1,"family_review_total":6,"specification_proposals_approved":False,"working_version_user_approved":False,"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS"})
component["review_policy"]["active_family_priority"] = "Decowaves"
component["current_component_review_record"] = rel(out)
component["last_family_media_review"] = {"family":"Decowaves","finish":"Component1 Terracotta","observed_utc":meta["observed_utc"],"scope":coverage["scope"],"family_census_files":157,"family_census_folders":12,"selected_thumbnails_inspected":15,"evidence":rel(HERE/"metadata-links.json"),"workbook_contains_this_live_media_audit":False}
component["main_family_review_reservation"] = {"component_ids":["BC-DECO-1","BC-DECO-2","BC-FDW-1","BC-FDW-2"],"global_reviews":[32,33,34,35],"status":"MAIN ACTIVE AND NEXT DECOWAVES FAMILY MEMBERS; FINISHES AND WHITE DESIGNS REVIEWED SEPARATELY"}
cp["main_family_review_reservation"] = copy.deepcopy(component["main_family_review_reservation"])
cp["after_main_family_next_unclaimed"] = {"component_id":cp["review_order"][35],"review_number":36}
component["updated_utc"] = now
docs["root"]["current_component_review"] = copy.deepcopy(component)
for key, path in paths.items():
    write(path, docs[key])
assert all(sha(path) == expected for path, expected in hashes.items())
assert read(paths["root"])["current_component_review"] == read(paths["component"])
validation = {"status":"PASS","component_id":"BC-DECO-1","review_number":32,"family_review_number":1,"individual_primary_current_hash_verified":True,"paired_rear_original_current_hash_verified":True,"public_front_visually_matches_dropbox":True,"public_price_4844_preserved":True,"new_300_price_is_unapproved_optional_proposal":True,"terracotta_native_9cm_depth_kept_separate_from_verdigris_8cm":True,"gypsum_claim_not_overwritten_with_ac730":True,"six_specification_groups":6,"family_files_listed":157,"family_folders_listed":12,"thumbnails_inspected":15,"source_model_workbook_user_decisions_and_previous_review_unchanged":True,"remote_files_changed":False}
write(HERE/"review-validation.json",validation)
print(json.dumps(validation))
