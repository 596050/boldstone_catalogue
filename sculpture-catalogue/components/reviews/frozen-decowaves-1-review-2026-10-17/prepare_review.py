"""Prepare white FDW1 as one component, preserving source scope and conflicts."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT/"components/reviews"


def read(path):
    return json.loads(path.read_text())


def write(path,value):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    tmp.replace(path)


def rel(path):
    return str(path.relative_to(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths={"walkthrough":REVIEWS/"walkthrough_checkpoint.json","progress":REVIEWS/"specification_review_progress.json","component":ROOT/"components/checkpoint.json","root":ROOT/"checkpoint.json"}
docs={key:read(path) for key,path in paths.items()}
cp,progress,component=[docs[key] for key in ["walkthrough","progress","component"]]
out=HERE/"component-review.json"
if cp.get("current_review_record")==rel(out):
    print(json.dumps({"status":"ALREADY_PREPARED","review":rel(out)}));raise SystemExit(0)
assert cp["current_component_id"]=="BC-DECO-2" and cp["current_size_finish_variant_id"]=="DECO-2-VERDIGRIS" and cp["current_answer_recorded"]
assert cp["review_order"].index("BC-FDW-1")+1==34 and "BC-FDW-1" not in progress["reviews"]
prior_approval=REVIEWS/"decowaves-2-review-2026-10-17/verdigris/identity-approval.json"
assert read(prior_approval)["user_statement"]=="Keep “Decowaves 2 — Verdigris”" and not read(prior_approval)["specifications_approved"]
now=datetime.now(timezone.utc).isoformat()
protected=[ROOT/"components/evidence/component_register.json",ROOT/cp["register_workbook"],REVIEWS/"user_classifications.json",ROOT/cp["current_review_record"],prior_approval]
hashes={path:sha(path) for path in protected}
write(HERE/"before-white-fdw1-review.json",{"recorded_utc":now,"files":{rel(paths[key]):value for key,value in docs.items()}})
meta=read(HERE/"metadata-links.json")
file,folder=meta["primary_metadata"]["file"],meta["folder_metadata"]["folder"]
assert file["id"]=="id:cnqzTNngPVsAAAAAAAykBA" and folder["id"]=="id:cnqzTNngPVsAAAAAAAyiYA"
assert Path(file["path_display"]).parent.as_posix()==folder["path_display"]
assert {key:len(value["entries"]) for key,value in meta["listings"].items()}=={"solo":10,"pair":2,"room":53,"triple":22}
assert all(not value["has_more"] and not value["cursor"] for value in meta["listings"].values())
for name in ["download-receipt.json","pair-download-receipt.json","three-download-receipt.json"]:
    receipt=read(HERE/name)
    assert receipt["actual_size"]==receipt["size"] and receipt["content_hash"]==receipt["calculated_dropbox_content_hash"]
    assert sha(Path(receipt["local_path"]))==receipt["sha256"]
http={row["offer_ref"]:row for row in read(HERE/"public-page-http-receipts.json")}
assert all(row["status"]==200 and row["price_matches_dated_native"] and row["sku_matches_native"] for row in http.values())
assert all(row["status"]=="PASS" for row in read(HERE/"public-image-receipts.json"))
model=read(ROOT/"components/evidence/component_register.json")
offers=[row for row in model["platform_records"] if row["offer_ref"] in ["O024","O025"]]
maker=[row for row in model["claims"] if row["component_id"]=="BC-FDW-1" and ("row78" in row.get("source_ref","") or "row80" in row.get("source_ref",""))]
bom=[row for row in model["bom"] if row["component_id"]=="BC-FDW-1"]
aliases=[row for row in model["aliases"] if row["component_id"]=="BC-FDW-1"]
previews={row["file_name"]:row for row in meta["previews"]}
primary,containing=previews[file["id"]],previews[folder["id"]]
items=[
    {"proposal_id":"FDW-1-WHITE-DIMENSIONS","field":"Individual dimensions and depth","value":{"source_face_height_cm":90,"source_face_width_cm":15,"native_overall_depth_cm":8,"maker_side_depth_range_cm":[5,7],"actual_measured_depth_cm":None},"display":"90 H × 15 W cm face; listing depth8cm versus maker side5–7cm — actual projection to check","status":"SOURCE SIZE CLAIMS WITH DIFFERENT DEPTH SCOPES; CAST UNMEASURED","basis":"Native O024/O025 and public arrangement descriptions give90×15×8cm per component. Maker rows78/80 independently give approximately90×15cm and side measurement5–7cm. Keep native overall depth and maker side range separately: they may use different measurement points/versions and do not establish this cast's maximum projection.","source_refs":["manufacture-stevensons:Sheet1!rows78/80","O024/O025 native and public per-part descriptions"]},
    {"proposal_id":"FDW-1-WHITE-WEIGHT","field":"Individual dry weight","value":{"historical_maker_estimated_range_kg":[8,10],"dated_price_table_estimate_kg":8,"actual_weighed_kg":None},"display":"Approximately8–10kg per panel — historical maker estimate; dated tables also give8kg","status":"DATED INDIVIDUAL CALCULATED ESTIMATES; NOT WEIGHED","basis":"Rows78/80 give8–10kg for each standard-white AC730 cast. Dated retail tables estimate8kg per panel. Native16kg for the pair and24kg for the triptych remain arrangement values and were not divided to invent an individual measurement.","source_refs":["manufacture-stevensons:Sheet1!rows78/80","components/reviews/frozen-decowaves-1-review-2026-10-17/advisory-packet-used.json:specifications.weight"]},
    {"proposal_id":"FDW-1-WHITE-MATERIAL","field":"Material and finish","value":{"source_standard_substrate":"Jesmonite AC730","source_standard_finish":"White marble stone finish","actual_binder_batch":None,"actual_reinforcement":None,"actual_sealing":None},"display":"Jesmonite AC730 with white marble stone finish — historical maker standard","status":"SOURCE STANDARD; SPECIFIC CAST COMPOSITION UNVERIFIED","basis":"Maker rows78/80 explicitly specify the white marble stone finish in Jesmonite AC730. Native/public O024/O025 describe the white stone finish. This is the historical standard, not a chemical test of the pictured panel and not a material assignment for the separately reviewed coloured pieces.","source_refs":["manufacture-stevensons:Sheet1!rows78/80","O024/O025:finish scope"]},
    {"proposal_id":"FDW-1-WHITE-FIXING","field":"Fixing","value":{"historical_hanging_points":1,"historical_material":"Stainless steel","historical_position":"Centre rear, upper third; aligned with series","actual_hardware":None,"actual_attachment":None,"rated_load":None},"display":"One small stainless fixing, centre rear in upper third — historical maker instruction","status":"SOURCE INSTRUCTION; NO REAR PHOTOGRAPH OR LOAD SPECIFICATION","basis":"Rows78/80 specify a single small stainless fixing at centre back in the upper third, aligned across the series. No rear appears in87reviewed cached thumbnails. Actual attachment, wall fastener and load rating remain unknown; a rotated/horizontal arrangement may need a different fixing position.","source_refs":["manufacture-stevensons:Sheet1!rows78/80"]},
    {"proposal_id":"FDW-1-WHITE-PRICE","field":"Individual retail price","value":{"proposed_amount":350,"currency":"GBP","sale_unit":"One white Frozen Decowaves1 panel","discussion_range_gbp":[330,400],"dated_individual_retail_references_gbp":[281.97,337.50],"dated_trade_reference_gbp":168,"existing_individual_offer_confirmed":False},"display":"£350 per individual panel — new proposed price","status":"UNAPPROVED COMMERCIAL PROPOSAL; SOURCE PRICES ARE DATED OR WHOLE SETS","basis":"Choose350 within the prepared330–400 range, near the named2025 draft individual retail337.50. Preserve earlier individual281.97 and trade168 as separate dated price classes. Current800 pair and1200 triptych prices remain whole-set offers; neither was divided to establish this proposed individual price.","source_refs":["components/reviews/frozen-decowaves-1-review-2026-10-17/advisory-packet-used.json:specifications.individual_price"]},
    {"proposal_id":"FDW-1-WHITE-AVAILABILITY","field":"Availability","value":{"proposed_sale_status":"Made to order individually / enquire","physical_stock_quantity":None,"production_capacity":None,"lead_time":None},"display":"Made to order individually / enquire — proposed; stock and lead time unknown","status":"PROPOSED INDIVIDUAL SALE POLICY; CURRENT PHYSICAL AVAILABILITY UNKNOWN","basis":"Native/public arrangement offers and InStock/Unlimited settings do not establish individual finished stock, current mould readiness, production capacity or lead time. Propose an individual made-to-order/enquiry sale policy for owner review.","source_refs":["O024/O025:arrangement settings only"]},
]
platform=[]
for offer in offers:
    ref=offer["offer_ref"]
    platform.append({"offer_ref":ref,"squarespace_id":offer["sq_id"],"shopify_handle":offer["sh_handle"],"shared_sku":offer["sku"],"platform_pair_status":"UNIQUE SHARED SKU CONFIRMED IN EXPORTS; PUBLIC SKU REFRESHED","dropbox_arrangement_status":"CURRENT PUBLIC AND DROPBOX ARRANGEMENT IMAGES VISUALLY COMPARED","sale_unit":"TWO PANELS" if ref=="O024" else "THREE PANELS","quantity_of_this_design":1 if ref=="O024" else 2,"bom_positions":[row for row in bom if row["offer_ref"]==ref],"native_per_component_dimensions_cm":[90,15,8],"native_set_weight_kg":int(offer["source_set_weight_kg"]),"public_set_price_gbp":http[ref]["public_price"],"individual_offer_confirmed":False,"live_account_records_refreshed":False})
coverage={"complete_individual_front":True,"detail":True,"oblique_views":True,"room_context":True,"garden_context":True,"series_arrangement":True,"rear":False,"installation_provenance":"UNCONFIRMED; historical room/garden images and staged examples are not a certified client-installation history","physical_stock_inferred":False,"scope":"Fresh complete87-file census in4folders:10solo,2paired display,53context,22triptych. All87cached thumbnails inspected. Current solo primary, native-matched pair and native-matched triptych originals downloaded and Dropbox-hash verified. Remaining84originals not re-downloaded; both current public primary images separately downloaded/inspected.","arrangement_count_scope":"Three displayed panels are physical positions in an image, not proof of three distinct designs or current stock."}
next_review={"component_id":"BC-FDW-2","review_number":35,"family_review_number":6,"size_finish_variant_id":"FDW-2-WHITE"}
review={"schema_version":1,"prepared_utc":now,"component_id":"BC-FDW-1","canonical_design_name":"Frozen Decowaves 1","proposed_name":"Frozen Decowaves 1 — White","display_name":"Frozen Decowaves 1 — White","maker_code":"FDW1","orientation_alias":"FDW3","family":"Decowaves","review_number":34,"family_review_number":5,"family_review_total":6,"size_finish_variant_id":"FDW-1-WHITE","variant_only_review":False,"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS","scope":"One individual standard-white broad-wave design. The working register records FDW3 as a180-degree orientation alias, giving this design two positions in the triptych. A name Keep for the pictured panel does not independently verify mould identity, actual batch specifications or physical stock. Retain coloured Decowaves as separate unresolved mould/material relations.","primary_image_id":file["id"],"primary_folder_id":folder["id"],"primary_image_link":primary["copy_link_url"],"primary_folder_link":containing["copy_link_url"],"metadata_checked_utc":meta["observed_utc"],"reference_refresh":rel(HERE/"metadata-links.json"),"primary_original_receipt":rel(HERE/"download-receipt.json"),"pair_original_receipt":rel(HERE/"pair-download-receipt.json"),"three_original_receipt":rel(HERE/"three-download-receipt.json"),"image_review_index":rel(HERE/"image-review-index.json"),"series_image_id":"id:cnqzTNngPVsAAAAAAA52zg","series_folder_id":"id:cnqzTNngPVsAAAAAAAyk5Q","series_image_link":previews["id:cnqzTNngPVsAAAAAAA52zg"]["copy_link_url"],"pair_image_id":"id:cnqzTNngPVsAAAAAAArqPA","pair_folder_id":"id:cnqzTNngPVsAAAAAAAyk4g","pair_image_link":previews["id:cnqzTNngPVsAAAAAAArqPA"]["copy_link_url"],"advisory_preparation":rel(HERE/"advisory-packet-used.json"),"specification_review_items":items,"source_offer_refs":["O024","O025"],"source_offer_snapshots":offers,"maker_claims":maker,"working_orientation_aliases":aliases,"platform_mapping":platform,"public_page_check":{"http_receipts":rel(HERE/"public-page-http-receipts.json"),"image_receipts":rel(HERE/"public-image-receipts.json"),"tool_result":rel(HERE/"public-page-tool-result.txt"),"current_public_prices_verified":True,"current_public_skus_verified":True,"existing_individual_offer_confirmed":False},"photo_coverage":coverage,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"open_gaps":["Confirm90×15cm face and reconcile/measure8cm listing projection versus5–7cm maker side depth","Weigh actual cast;8–10kg maker and8kg dated tables remain estimates","Confirm actual AC730 standard/batch, reinforcement and sealing","Rear photograph and exact fixing/attachment/wall hardware/rated load; orientation applicability","Approve350GBPindividual price and sale policy; establish stock/capacity/lead time","Existing individual Squarespace/Shopify offer unconfirmed; O024/O025 are complete arrangements","Owner confirmation of FDW3 orientation/mould relationship; do not infer physical stock or merge coloured designs","Verify context provenance and care/packing dimensions/weight"],"next_review_after_keep":next_review,"next_global_component_id":"BC-FDW-2","remote_files_changed":False,"live_platform_records_changed":False}
write(out,review)
progress["reviews"]["BC-FDW-1"]={"reviewed_utc":now,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"proposed_name":review["proposed_name"],"size_finish_variant_id":review["size_finish_variant_id"],"specification_proposals":copy.deepcopy(items),"source_specifications_recorded":True,"source_offer_refs":["O024","O025"],"maker_claims":maker,"working_orientation_aliases":aliases,"platform_mapping":platform,"primary_image_id":file["id"],"primary_folder_id":folder["id"],"review_record":rel(out),"gaps":review["open_gaps"],"photo_coverage":coverage}
progress["updated_utc"]=now
cp.update({"current_component_id":"BC-FDW-1","current_review_number":34,"current_size_finish_variant_id":"FDW-1-WHITE","proposed_name":review["proposed_name"],"state":"Awaiting individual white Frozen Decowaves1 name/identity and source/working specification review","primary_image":{"file_id":file["id"],"name":file["name"],"path_display":file["path_display"],"copy_link_url":primary["copy_link_url"],"open_in_dropbox_url":primary["open_in_dropbox_url"]},"containing_folder":{"folder_id":folder["id"],"name":folder["name"],"path_display":folder["path_display"],"copy_link_url":containing["copy_link_url"],"open_in_dropbox_url":containing["open_in_dropbox_url"]},"answer_state":"No answer yet; name-only Keep confirms pictured individual name/identity only, not six specification groups or all orientation/mould relations.","question_scope":"Keep Frozen Decowaves1 — White for the pictured individual broad-wave panel. Six groups:source90×15cmface with8cmlistingdepth versus5–7cmmakerside;historical8–10kgindividualestimate;historicalAC730/whitemarblestandard;one rearSSfixingupperthirdhistoricalinstruction;350GBPindividualpricePROPOSAL;individualmade-to-order/enquirePROPOSAL. Pair/triptych weights and800/1200GBPprices remain entire-offer values. Name-only Keep confirms identity only.","metadata_checked_utc":meta["observed_utc"],"current_answer_recorded":False,"current_specification_answer_recorded":False,"current_dimension_answer_recorded":False,"working_version_user_approved":False,"current_review_record":rel(out),"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS","current_family_review_number":5,"current_family_review_total":6,"active_family":"Decowaves","family_review_evidence":rel(HERE/"metadata-links.json"),"next_review_after_keep":next_review,"displayed_identity_evidence_file_ids":[file["id"]],"displayed_identity_evidence_folder_ids":[folder["id"]],"current_component_source_notes":[item["display"] for item in items],"next_serialized_parallel_import":{"trigger":"AFTER_DECOWAVES_FAMILY_REVIEW_6_BEFORE_MAIN_REVIEW_36","status":"PENDING_EXACT_TRANSCRIPT_SNAPSHOT_AND_CURRENT_REFERENCE_VERIFICATION","source_queue":"parallel_import_queue","approval_inferred":False},"updated_utc":now})
receipts=[("BC-SHELL-B1",None,"components/parallel-reviews/shellmoon-2026-10-17/battersea-one-white/review-approval.json"),("BC-EG-1","EG-1-GOLD-LEAF","components/parallel-reviews/egyptian-2026-10-17/palm-one-gold-leaf/identity-approval.json")]
for cid,vid,receipt in receipts:
    if (ROOT/receipt).exists() and not any(item.get("receipt")==receipt for item in cp.setdefault("parallel_import_queue",[])):
        cp["parallel_import_queue"].append({"component_id":cid,"variant_id":vid,"receipt":receipt,"receipt_sha256":sha(ROOT/receipt),"status":"RECEIVED NAME ONLY; PENDING NEXT SERIALIZED IMPORT","scope":"Reported named Keep only. Six specification groups, water-feature/other-finish scope and physical facts remain separately unapproved. Independently verify exact owner transcript and proposal snapshot before import.","approval_imported":False,"recorded_utc":now})
component["interactive_review_state"].update({"current_component_id":"BC-FDW-1","review_number":34,"current_size_finish_variant_id":"FDW-1-WHITE","current_name":review["proposed_name"],"state":cp["state"],"family_review_number":5,"specification_proposals_approved":False,"working_version_user_approved":False,"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS"})
component["current_component_review_record"]=rel(out)
component["last_family_media_review"]={"family":"Decowaves","finish":"Frozen Decowaves1 White","observed_utc":meta["observed_utc"],"scope":coverage["scope"],"files":87,"folders":4,"evidence":rel(HERE/"metadata-links.json"),"workbook_contains_this_live_media_audit":False}
component["updated_utc"]=now
docs["root"]["current_component_review"]=copy.deepcopy(component)
for key,path in paths.items():write(path,docs[key])
assert all(sha(path)==expected for path,expected in hashes.items())
assert read(paths["root"])["current_component_review"]==read(paths["component"])
validation={"status":"PASS","component_id":"BC-FDW-1","global_review":34,"family_review":5,"complete_single_primary_original_verified":True,"pair_and_triptych_originals_verified":True,"both_public_primary_images_downloaded_and_visually_compared":True,"both_shared_skus_and_whole_set_prices_refreshed_http200":True,"all87cached_thumbnails_inspected":True,"native_depth8_and_maker_side5to7_separate":True,"individual_weight_has_independent_maker_estimate":True,"FDW3_retained_as_working_orientation_alias_without_stock_inference":True,"six_specification_groups":6,"350GBP_individual_price_unapproved":True,"source_model_workbook_and_prior_keeps_unchanged":True,"remote_files_changed":False}
write(HERE/"review-validation.json",validation)
print(json.dumps(validation))
