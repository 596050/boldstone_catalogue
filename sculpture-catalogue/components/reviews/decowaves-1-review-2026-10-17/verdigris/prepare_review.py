"""Stage the individual verdigris finish while preserving the terracotta Keep."""
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
out = HERE / "component-review.json"
if cp.get("current_review_record") == rel(out):
    print(json.dumps({"status": "ALREADY_PREPARED", "review": rel(out)}))
    raise SystemExit(0)
assert cp["current_component_id"] == "BC-DECO-1" and cp["current_size_finish_variant_id"] == "DECO-1-TERRACOTTA" and cp["current_answer_recorded"]
terra_source = HERE.parent / "terracotta/component-review.json"
terra_approval = HERE.parent / "terracotta/identity-approval.json"
approval = read(terra_approval)
assert approval["user_statement"] == "Keep “Decowaves 1 — Terracotta”" and approval["identity_confirmed"] and not approval["specifications_approved"]
now = datetime.now(timezone.utc).isoformat()
protected = [ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"], REVIEWS / "user_classifications.json", terra_source, terra_approval]
hashes = {path: sha(path) for path in protected}
write(HERE / "before-verdigris-review.json", {"recorded_utc": now, "files": {rel(paths[key]): value for key, value in docs.items()}})
parent = progress["reviews"]["BC-DECO-1"]
parent_before = copy.deepcopy(parent)
terra = read(terra_source)
meta = read(HERE / "metadata-links.json")
file, folder = meta["primary_metadata"]["file"], meta["folder_metadata"]["folder"]
assert file["id"] == "id:cnqzTNngPVsAAAAAAAykAQ" and folder["id"] == "id:cnqzTNngPVsAAAAAAAyiXg"
assert Path(file["path_display"]).parent.as_posix() == folder["path_display"]
assert {key: len(value["entries"]) for key, value in meta["listings"].items()} == {"solo":11,"pair":21,"room":2}
assert all(not value["has_more"] and not value["cursor"] for value in meta["listings"].values())
for name in ["download-receipt.json", "pair-download-receipt.json"]:
    receipt = read(HERE / name)
    assert receipt["actual_size"] == receipt["size"] and receipt["content_hash"] == receipt["calculated_dropbox_content_hash"]
    assert sha(Path(receipt["local_path"])) == receipt["sha256"]
assert read(HERE / "public-pair-http-receipt.json")["status"] == 200
public_claims = read(HERE / "public-pair-source-claims.json")
assert public_claims["dimensions_per_panel_cm"] == [90,15,8] and public_claims["price_gbp"] == 600 and public_claims["source_pair_weight_kg"] == 14
product = read(HERE / "public-product-jsonld.json")[0]
assert product["offers"]["sku"] == "SQ2946502" and product["offers"]["price"] == 600
previews = {row["file_name"]:row for row in meta["previews"]}
primary, containing = previews[file["id"]], previews[folder["id"]]
model = read(ROOT / "components/evidence/component_register.json")
offer = next(row for row in model["platform_records"] if row["offer_ref"] == "O060")
bom = next(row for row in model["bom"] if row["offer_ref"] == "O060" and row["component_id"] == "BC-DECO-1")
url = public_claims["source_url"]
items = [
    {"proposal_id":"DECO-1-VERDIGRIS-DIMENSIONS","field":"Individual dimensions","value":{"source_height_cm":90,"source_width_cm":15,"source_overall_depth_cm":8,"current_cast_measured":False},"display":"90 H × 15 W × 8 D cm — source per-panel claim for verdigris version","status":"NATIVE AND CURRENT PUBLIC PER-COMPONENT CLAIM; CAST UNMEASURED","basis":"O060's two-panel description explicitly gives90×15×8cm for each panel. This is per-component evidence, not a division of the approximately90×30×8cm overall pair dimensions. Terracotta O050's9cm depth remains separate.","source_refs":["SS Wall Products!row65/Description",url]},
    {"proposal_id":"DECO-1-VERDIGRIS-WEIGHT","field":"Individual dry weight","value":{"proposed_estimated_range_kg":[6,9],"source_separate_pair_weight_kg":14,"current_cast_weighed":False},"display":"Approximately 6–9 kg individually — working guess","status":"INDIVIDUAL CONSTRUCTION ANALOGY; SOURCE14KG IS WHOLE PAIR ONLY","basis":"The related terracotta single is sourced at approximately6kg. A broad6–9kg range is proposed for this similar-size coloured cast while binder, reinforcement, hollowing and finish mass remain unknown. The separate14kg whole-pair claim is preserved without assigning7kg to either panel.","source_refs":["O050:individual approximate6kg; related finish only","O060:approximately14kg whole pair; not allocated"]},
    {"proposal_id":"DECO-1-VERDIGRIS-MATERIAL","field":"Material and finish","value":{"source_substrate":"Cast composite; binder unspecified","source_finish":"Hand-applied verdigris patina","proposed_binder":"Gypsum composite, by terracotta-version analogy only","actual_binder":None,"actual_metal_content":None,"actual_reinforcement":None,"actual_sealing":None},"display":"Cast composite with applied verdigris patina — source; gypsum binder is an unconfirmed guess","status":"GENERAL SUBSTRATE/FINISH SOURCE CLAIM; BINDER HYPOTHESIS","basis":"The native and freshly read public verdigris pair description specify cast composite and hand-applied verdigris patina. It does not identify gypsum, AC730, metal chemistry or sealing. Gypsum is a proposal based on the related terracotta individual offer, not a verified verdigris composition; green colour does not establish solid bronze.","source_refs":["SS Wall Products!row65/Description",url,"O050:gypsum source applies to terracotta only"]},
    {"proposal_id":"DECO-1-VERDIGRIS-FIXING","field":"Fixing","value":{"source_instruction":"Supplied ready to hang","proposed_type":"One rear keyhole plate","actual_attachment":None,"actual_wall_hardware":None,"rated_load":None},"display":"One rear keyhole plate proposed — type unconfirmed for verdigris","status":"FIXING GUESS FROM TERRACOTTA REAR; NO VERDIGRIS REAR FOUND","basis":"O060 supplies no fixing type beyond ready to hang. The actual terracotta rear images show one keyhole plate per panel, motivating an analogous proposal for this finish. None of the34 reviewed green images shows the rear, so attachment, layout, hardware and load capacity remain unknown.","source_refs":[url,"id:cnqzTNngPVsAAAAAAAye7g:terracotta paired rear only"]},
    {"proposal_id":"DECO-1-VERDIGRIS-PRICE","field":"Individual retail price","value":{"proposed_amount":325,"currency":"GBP","sale_unit":"One verdigris Decowaves 1 panel","discussion_range_gbp":[280,350],"separate_pair_offer_amount":600,"individual_price_approved":False},"display":"£325 per individual panel — new proposed price","status":"UNAPPROVED COMMERCIAL PROPOSAL; CURRENT£600 IS PAIR ONLY","basis":"Choose325 within the prepared280–350 discussion range, using the dated281.97 white90×15 individual price only as a commercial comparison and allowing an uncosted coloured-finish difference. This is not a quote, current individual offer or half of the600 pair price. It does not establish white/coloured mould or material equivalence.","source_refs":["components/reviews/decowaves-1-review-2026-10-17/terracotta/advisory-packet-used.json","retail-2025:90×15 individual dated reference; pricing analogy only",url]},
    {"proposal_id":"DECO-1-VERDIGRIS-AVAILABILITY","field":"Availability","value":{"proposed_sale_status":"Made to order individually / enquire","physical_stock_quantity":None,"production_capacity":None,"lead_time":None},"display":"Made to order individually / enquire — proposed; stock and lead time unknown","status":"PROPOSED INDIVIDUAL SALE POLICY; PUBLISHED PAIR DOES NOT PROVE STOCK","basis":"Current public O060 is a two-panel offer with an InStock schema flag; that is not evidence of physical individual stock, current mould/finish readiness, production capacity or lead time. Propose the component as an individual made-to-order enquiry, subject to owner review.","source_refs":["O060 native Unlimited and current public InStock flags",url]},
]
mapping = {"squarespace_id":offer["sq_id"],"shopify_handle":None,"sku":offer["sku"],"shared_sku":None,"offer_ref":"O060","platform_status":"SQUARESPACE VERDIGRIS PAIR IDENTIFIED; SHOPIFY COUNTERPART UNCONFIRMED","dropbox_arrangement_status":"CONFIRMED TWO-DESIGN VERDIGRIS ARRANGEMENT; CURRENT PUBLIC IMAGE VISUALLY COMPARED","sale_unit":"TWO PANELS:DECOWAVES1+2","component_role":"Broad folded-wave panel at left in the source arrangement","bom_position":bom,"individual_offer_confirmed":False,"per_component_source_dimensions_cm":[90,15,8],"separate_pair_weight_kg":14,"current_pair_price_gbp":600,"native_parts_field":offer["native_parts"],"observed_arrangement_piece_count":2,"piece_count_note":"Native parts field says1; current description and photographs show2panels. Preserve source discrepancy while keeping two separate component identities.","public_sku_verified":"SQ2946502","public_image_scope":"Current public pair and downloaded Dropbox pair show matching broad folded-wave left member and narrower grooved/spiral right member in verdigris. Exact byte equality and cast measurements are not asserted.","live_account_records_refreshed":False,"terracotta_single_offer_related_only":"O050","white_frozen_designs_merged":False}
coverage = {"complete_individual_front":True,"detail":True,"oblique_views":True,"wall_display":True,"series_arrangement":True,"room_context":True,"garden_context":True,"rear":False,"installation_provenance":"UNCONFIRMED; room/garden images are context examples, not confirmed client installations","physical_stock_inferred":False,"scope":"Fresh complete34-file census:11solo,21pair,2context in3folders; all34cached thumbnails visually inspected. Current solo primary and pair originals downloaded and Dropbox-hash verified. Remaining32originals not re-downloaded; source/public pair photo separately inspected."}
next_review = {"component_id":"BC-DECO-2","review_number":33,"family_review_number":3,"size_finish_variant_id":"DECO-2-TERRACOTTA"}
review = {"schema_version":1,"prepared_utc":now,"component_id":"BC-DECO-1","canonical_design_name":"Decowaves 1","proposed_name":"Decowaves 1 — Verdigris","display_name":"Decowaves 1 — Verdigris","family":"Decowaves","review_number":32,"family_review_number":2,"family_review_total":6,"size_finish_variant_id":"DECO-1-VERDIGRIS","variant_only_review":True,"review_decision_mode":"SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS","scope":"One depicted individual verdigris finish of the broad folded-wave Decowaves1design. The terracotta name/identity Keep does not approve this finish or its specifications. Pair dimensions, weight and price remain explicitly scoped; white Frozen Decowaves records are not merged.","primary_image_id":file["id"],"primary_folder_id":folder["id"],"primary_image_link":primary["copy_link_url"],"primary_folder_link":containing["copy_link_url"],"metadata_checked_utc":meta["observed_utc"],"reference_refresh":rel(HERE/"metadata-links.json"),"primary_original_receipt":rel(HERE/"download-receipt.json"),"pair_original_receipt":rel(HERE/"pair-download-receipt.json"),"image_review_index":rel(HERE/"image-review-index.json"),"series_image_id":"id:cnqzTNngPVsAAAAAAAyerg","series_folder_id":"id:cnqzTNngPVsAAAAAAAyeqA","series_image_link":previews["id:cnqzTNngPVsAAAAAAAyerg"]["copy_link_url"],"context_image_id":"id:cnqzTNngPVsAAAAAAAyhMA","context_folder_id":"id:cnqzTNngPVsAAAAAAAyk4A","context_image_link":previews["id:cnqzTNngPVsAAAAAAAyhMA"]["copy_link_url"],"parent_identity_approval":rel(terra_approval),"parent_identity_approval_scope":"Terracotta component name and depicted identity only; all six specification groups and price proposals remain pending.","source_offer_refs":["O060"],"related_terracotta_offer_refs":["O050"],"source_offer_snapshot":offer,"public_source_claims":public_claims,"public_page_check":{"checked_utc":read(HERE/"public-pair-http-receipt.json")["checked_utc"],"source_url":url,"web_tool_status":"Could not access page; browser-independent public HTTP GET returned200 and full visible product text plus JSON-LD were inspected","http_receipt":rel(HERE/"public-pair-http-receipt.json"),"jsonld_snapshot":rel(HERE/"public-product-jsonld.json"),"visible_text":rel(HERE/"public-pair-visible-text.txt"),"public_image_receipt":rel(HERE/"public-pair-image-receipt.json")},"specification_review_items":items,"platform_mapping":mapping,"photo_coverage":coverage,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"open_gaps":["Confirm90×15×8cm source dimensions apply to the pictured green cast","Weigh individual panel;6–9kg remains a guess and14kg source is pair only","Confirm binder/reinforcement/metal content/coating/sealing; gypsum is a hypothesis","Green rear fixing photograph, actual hardware/attachment and rated load","Approve new£325individual price and sale policy; establish stock/capacity/lead time","No individual or Shopify offer confirmed; O060 is a Squarespace pair","Verify context-image provenance and care/packing details; preserve native piece-count discrepancy"],"next_review_after_keep":next_review,"next_global_component_id":"BC-DECO-2","remote_files_changed":False,"live_platform_records_changed":False}
write(out,review)
terra_variant = {"size_finish_variant_id":"DECO-1-TERRACOTTA","canonical_name":terra["proposed_name"],"review_record":rel(terra_source),"identity_confirmed":True,"identity_approval":rel(terra_approval),"primary_image_id":terra["primary_image_id"],"primary_folder_id":terra["primary_folder_id"],"specification_proposals":copy.deepcopy(terra["specification_review_items"]),"specifications_approved":False,"proposals_approved":False,"physical_specs_verified":False,"specification_review_status":"NAME KEPT; SIX SPECIFICATION GROUPS REMAIN PENDING"}
green_variant = {"size_finish_variant_id":"DECO-1-VERDIGRIS","canonical_name":review["proposed_name"],"review_record":rel(out),"identity_confirmed":False,"primary_image_id":file["id"],"primary_folder_id":folder["id"],"specification_proposals":copy.deepcopy(items),"specifications_approved":False,"proposals_approved":False,"physical_specs_verified":False,"photo_coverage":coverage,"platform_mapping":mapping}
parent["size_finish_variants"] = {"DECO-1-TERRACOTTA":terra_variant,"DECO-1-VERDIGRIS":green_variant}
for pending in parent["pending_size_finish_variants"]:
    if pending["variant_id"] == "DECO-1-VERDIGRIS":pending.update({"review_status":"PRESENTED; AWAITING OWNER NAME/IDENTITY AND SPECIFICATION REVIEW","review_record":rel(out)})
assert {key:value for key,value in parent.items() if key not in ["size_finish_variants","pending_size_finish_variants"]} == {key:value for key,value in parent_before.items() if key not in ["size_finish_variants","pending_size_finish_variants"]}
progress["updated_utc"] = now
cp.update({"proposed_name":review["proposed_name"],"state":"Awaiting individual verdigris Decowaves1 name/identity and source/working specification review","current_size_finish_variant_id":"DECO-1-VERDIGRIS","current_review_record":rel(out),"current_family_review_number":2,"primary_image":{"file_id":file["id"],"name":file["name"],"path_display":file["path_display"],"copy_link_url":primary["copy_link_url"],"open_in_dropbox_url":primary["open_in_dropbox_url"]},"containing_folder":{"folder_id":folder["id"],"name":folder["name"],"path_display":folder["path_display"],"copy_link_url":containing["copy_link_url"],"open_in_dropbox_url":containing["open_in_dropbox_url"]},"answer_state":"No answer yet for verdigris finish; terracotta name/identity Keep preserved. Name-only replies confirm name and depicted identity only.","question_scope":"Keep Decowaves1 — Verdigris for the pictured individual broad folded-wave panel. Six groups:source90×15×8cm;individual6–9kgGUESS;sourcecastcomposite/appliedverdigris with gypsum-binderGUESS;one rear keyholeplateGUESS;£325new individualpriceproposal;individualmade-to-order/enquireproposal. Source£600and14kgcoverthewholepairandarenotallocated. A name-only reply confirms name/depicted identity only.","metadata_checked_utc":meta["observed_utc"],"current_answer_recorded":False,"current_specification_answer_recorded":False,"current_dimension_answer_recorded":False,"working_version_user_approved":False,"displayed_identity_evidence_file_ids":[file["id"]],"displayed_identity_evidence_folder_ids":[folder["id"]],"current_component_source_notes":[item["display"] for item in items],"family_review_evidence":rel(HERE/"metadata-links.json"),"next_review_after_keep":next_review,"review_decision_mode":"SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS","updated_utc":now})
receipts = [("BC-ECHO-1","ECHO-1-WHITE","components/parallel-reviews/echo-sound-2026-10-17/echo-one-white/identity-approval.json"),("BC-RUST-PANEL",None,"components/parallel-reviews/rust-seaweed-2026-10-17/rust-panel/review-approval.json")]
for cid,vid,receipt in receipts:
    if (ROOT/receipt).exists() and not any(item.get("receipt") == receipt for item in cp.setdefault("parallel_import_queue",[])):
        cp["parallel_import_queue"].append({"component_id":cid,"variant_id":vid,"receipt":receipt,"receipt_sha256":sha(ROOT/receipt),"status":"RECEIVED NAME ONLY; PENDING NEXT SERIALIZED IMPORT","scope":"Reported named Keep; six source/working specification groups remain unapproved. Independently verify exact owner transcript and review snapshot before import.","approval_imported":False,"recorded_utc":now})
component["interactive_review_state"].update({"current_name":review["proposed_name"],"state":cp["state"],"current_size_finish_variant_id":"DECO-1-VERDIGRIS","family_review_number":2,"specification_proposals_approved":False,"working_version_user_approved":False,"review_decision_mode":"SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS"})
component["current_component_review_record"] = rel(out)
component["last_family_media_review"] = {"family":"Decowaves","finish":"Component1 Verdigris","observed_utc":meta["observed_utc"],"scope":coverage["scope"],"files":34,"folders":3,"evidence":rel(HERE/"metadata-links.json"),"workbook_contains_this_live_media_audit":False}
component["updated_utc"] = now
docs["root"]["current_component_review"] = copy.deepcopy(component)
for key,path in paths.items():write(path,docs[key])
assert all(sha(path) == expected for path,expected in hashes.items())
assert read(paths["root"])["current_component_review"] == read(paths["component"])
validation = {"status":"PASS","component_id":"BC-DECO-1","variant_id":"DECO-1-VERDIGRIS","family_review_number":2,"individual_primary_hash_verified":True,"pair_original_hash_verified":True,"public_pair_html_read200":True,"current_public_pair_sku_verified":True,"source_per_panel_depth8cm_not_terra9cm":True,"whole_pair600price_and14kg_not_allocated":True,"weight_binder_fixing_price_availability_proposals_explicit":True,"files_listed_and_cached_thumbnails_inspected":34,"rear_image_missing":True,"room_garden_and_series_images_available":True,"terra_parent_keep_and_specs_preserved":True,"source_model_workbook_user_decisions_unchanged":True,"remote_files_changed":False}
write(HERE/"review-validation.json",validation)
print(json.dumps(validation))
