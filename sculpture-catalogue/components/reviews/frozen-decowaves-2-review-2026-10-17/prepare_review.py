"""Prepare FDW2 using its own maker row and the verified shared arrangements."""
import copy
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REVIEWS=ROOT/"components/reviews"


def read(path):
    return json.loads(path.read_text())


def write(path,data):
    tmp=path.with_name(path.name+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
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
assert cp["current_component_id"]=="BC-FDW-1" and cp["current_answer_recorded"]
assert cp["review_order"].index("BC-FDW-2")+1==35 and "BC-FDW-2" not in progress["reviews"]
base_source=REVIEWS/"frozen-decowaves-1-review-2026-10-17/component-review.json"
prior_approval=base_source.parent/"identity-approval.json"
assert read(prior_approval)["user_statement"]=="Keep “Frozen Decowaves 1 — White”" and not read(prior_approval)["specifications_approved"]
now=datetime.now(timezone.utc).isoformat()
protected=[ROOT/"components/evidence/component_register.json",ROOT/cp["register_workbook"],REVIEWS/"user_classifications.json",base_source,prior_approval]
hashes={path:sha(path) for path in protected}
write(HERE/"before-white-fdw2-review.json",{"recorded_utc":now,"files":{rel(paths[key]):value for key,value in docs.items()}})
meta=read(HERE/"metadata-links.json")
file,folder=meta["primary_metadata"]["file"],meta["folder_metadata"]["folder"]
assert file["id"]=="id:cnqzTNngPVsAAAAAAAykBQ" and folder["id"]=="id:cnqzTNngPVsAAAAAAAyiYQ"
assert Path(file["path_display"]).parent.as_posix()==folder["path_display"]
assert {key:len(value["entries"]) for key,value in meta["listings"].items()}=={"solo":5,"pair":2,"room":53,"triple":22}
assert all(not value["has_more"] and not value["cursor"] for value in meta["listings"].values())
download=read(HERE/"download-receipt.json")
assert download["actual_size"]==download["size"] and download["content_hash"]==download["calculated_dropbox_content_hash"] and sha(Path(download["local_path"]))==download["sha256"]
reuse=read(HERE/"shared-context-revalidation.json")
assert reuse["shared_context_files"]==77 and reuse["stable_ids_names_paths_modified_times_sizes_unchanged"]
assert sha(ROOT/reuse["prior_validation"])==reuse["prior_validation_sha256"]
model=read(ROOT/"components/evidence/component_register.json")
maker=[item for item in model["claims"] if item["component_id"]=="BC-FDW-2" and "row79" in item.get("source_ref","")]
assert len(maker)==5
bom=[item for item in model["bom"] if item["component_id"]=="BC-FDW-2"]
previews={entry["file_name"]:entry for entry in meta["previews"]}
primary,containing=previews[file["id"]],previews[folder["id"]]
review=copy.deepcopy(read(base_source))
items=review["specification_review_items"]
for item in items:
    item["proposal_id"]=item["proposal_id"].replace("FDW-1-WHITE","FDW-2-WHITE")
    item["basis"]=item["basis"].replace("rows78/80","row79").replace("Rows78/80","Row79")
    item["source_refs"]=[ref.replace("rows78/80","row79").replace("frozen-decowaves-1-review-2026-10-17/advisory-packet-used.json","frozen-decowaves-2-review-2026-10-17/advisory-packet-used.json") for ref in item["source_refs"]]
items[3]["basis"]="Maker row79 independently specifies one small stainless fixing at centre rear in the upper third, aligned across the series. No rear appears among the5current solo thumbnails or77shared context/arrangement images reviewed in the prior white-component pass and revalidated unchanged. Actual hardware/attachment and rated load remain unknown."
items[4]["value"]["sale_unit"]="One white Frozen Decowaves2 panel"
for mapping in review["platform_mapping"]:
    mapping["quantity_of_this_design"]=1
    mapping["bom_positions"]=[item for item in bom if item["offer_ref"]==mapping["offer_ref"]]
    assert len(mapping["bom_positions"])==1 and mapping["bom_positions"][0]["position"]==2
review.pop("orientation_alias",None)
coverage={"complete_individual_front":True,"detail":True,"oblique_views":True,"room_context":True,"garden_context":True,"series_arrangement":True,"rear":False,"installation_provenance":"UNCONFIRMED; historical/staged context examples do not certify client provenance","physical_stock_inferred":False,"scope":"Fresh complete82-file census in4folders:5solo,2paired display,53context,22triptych. All5solo cached thumbnails inspected now; current primary original downloaded/hash-verified. The77shared context images were already visually inspected during FDW1; current stable IDs/names/paths/modified times/sizes match that audit exactly. Pair/triptych originals and public images retained from that separately verified review.","shared_visual_review":rel(base_source),"shared_context_revalidation":rel(HERE/"shared-context-revalidation.json"),"arrangement_count_scope":"One FDW2panel in both two-panel and three-panel offers; repeated FDW1/FDW3 positions are separate design context, not extra FDW2designs or confirmed stock."}
next_review={"component_id":"BC-DR-WAVE1","review_number":36,"family_review_number":1}
review.update({"prepared_utc":now,"component_id":"BC-FDW-2","canonical_design_name":"Frozen Decowaves 2","proposed_name":"Frozen Decowaves 2 — White","display_name":"Frozen Decowaves 2 — White","maker_code":"FDW2","review_number":35,"family_review_number":6,"family_review_total":6,"size_finish_variant_id":"FDW-2-WHITE","scope":"One individual standard-white FDW2design with grooved arcs and a spiral, at position2in the native two- and three-panel arrangements. Do not transfer FDW1/FDW3orientation aliases or separately reviewed coloured-cast chemistry/weight to this panel. A name Keep would confirm only depicted individual identity.","primary_image_id":file["id"],"primary_folder_id":folder["id"],"primary_image_link":primary["copy_link_url"],"primary_folder_link":containing["copy_link_url"],"metadata_checked_utc":meta["observed_utc"],"reference_refresh":rel(HERE/"metadata-links.json"),"primary_original_receipt":rel(HERE/"download-receipt.json"),"image_review_index":rel(HERE/"image-review-index.json"),"pair_image_link":previews["id:cnqzTNngPVsAAAAAAArqPA"]["copy_link_url"],"series_image_link":previews["id:cnqzTNngPVsAAAAAAA52zg"]["copy_link_url"],"advisory_preparation":rel(HERE/"advisory-packet-used.json"),"maker_claims":maker,"working_orientation_aliases":[],"photo_coverage":coverage,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"open_gaps":["Confirm90×15cm face and measure maximum projection;8cm listing and5–7cm maker side remain separate source scopes","Weigh actual FDW2cast;8–10kg maker and8kg dated table estimates remain unmeasured","Confirm actual AC730 batch, reinforcement and sealing","Rear photograph and actual fixing/attachment/wall hardware/rated load","Approve350GBPindividual price and sale policy; establish stock/capacity/lead time","Existing individual Squarespace/Shopify offer unconfirmed; matched O024/O025 cover whole arrangements","Verify context provenance and care/packing dimensions/weight; coloured-design/mould equivalence unresolved"],"next_review_after_keep":next_review,"next_global_component_id":"BC-DR-WAVE1"})
review["public_page_check"]["reused_for_second_member"]=True
review["public_page_check"]["source_review"]=rel(base_source)
review["public_page_check"]["scope_note"]="Public pair/triptych SKUs and prices were checked in preceding FDW1review; retained as dated/current-at-that-check offer evidence, not newly re-fetched for this card."
write(out,review)
progress["reviews"]["BC-FDW-2"]={"reviewed_utc":now,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"proposed_name":review["proposed_name"],"size_finish_variant_id":review["size_finish_variant_id"],"specification_proposals":copy.deepcopy(items),"source_specifications_recorded":True,"source_offer_refs":["O024","O025"],"maker_claims":maker,"platform_mapping":review["platform_mapping"],"primary_image_id":file["id"],"primary_folder_id":folder["id"],"review_record":rel(out),"gaps":review["open_gaps"],"photo_coverage":coverage}
progress["updated_utc"]=now
cp.update({"current_component_id":"BC-FDW-2","current_review_number":35,"current_size_finish_variant_id":"FDW-2-WHITE","proposed_name":review["proposed_name"],"state":"Awaiting final Decowaves-family individual white FDW2name/identity and six specification groups","primary_image":{"file_id":file["id"],"name":file["name"],"path_display":file["path_display"],"copy_link_url":primary["copy_link_url"],"open_in_dropbox_url":primary["open_in_dropbox_url"]},"containing_folder":{"folder_id":folder["id"],"name":folder["name"],"path_display":folder["path_display"],"copy_link_url":containing["copy_link_url"],"open_in_dropbox_url":containing["open_in_dropbox_url"]},"answer_state":"No answer yet. A name-only Keep confirms depicted name/identity only; all six source/working specification groups remain separately open.","question_scope":"Keep Frozen Decowaves2 — White for the pictured individual grooved/spiral panel. Six groups:source90×15cmface;8cmlistingdepth versus5–7cmmakerside;historical8–10kgindividualestimate;historicalAC730/whitemarblestandard;one rearSSfixingupperthirdhistoricalinstruction;350GBPindividualpricePROPOSAL;individualmade-to-order/enquirePROPOSAL. Whole-set prices/weights remain separate. Name-only answer confirms identity only.","metadata_checked_utc":meta["observed_utc"],"current_answer_recorded":False,"current_specification_answer_recorded":False,"current_dimension_answer_recorded":False,"working_version_user_approved":False,"current_review_record":rel(out),"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS","current_family_review_number":6,"current_family_review_total":6,"family_review_evidence":rel(HERE/"metadata-links.json"),"next_review_after_keep":next_review,"displayed_identity_evidence_file_ids":[file["id"]],"displayed_identity_evidence_folder_ids":[folder["id"]],"current_component_source_notes":[item["display"] for item in items],"updated_utc":now})
for cid,vid,kind,receipt in [("BC-EG-2","EG-2-WHITE","INDIVIDUAL_VARIANT_IDENTITY_RECEIPT","components/parallel-reviews/egyptian-2026-10-17/palm-two-white/identity-approval.json"),("BC-SHELL-B2",None,"BUILD_CONFIGURATION_NAME_ONLY_RECEIPT","components/parallel-reviews/shellmoon-2026-10-17/battersea-two-water-feature/review-approval.json")]:
    if (ROOT/receipt).exists() and not any(item.get("receipt")==receipt for item in cp.setdefault("parallel_import_queue",[])):
        cp["parallel_import_queue"].append({"component_id":cid,"variant_id":vid,"scope_kind":kind,"receipt":receipt,"receipt_sha256":sha(ROOT/receipt),"status":"RECEIVED NAME ONLY; PENDING NEXT SERIALIZED IMPORT","scope":"Reported named configuration/finish identity only; all six specification groups remain unapproved source/proposal values. Independently verify exact transcript and proposal scope before import.","approval_imported":False,"recorded_utc":now})
component["interactive_review_state"].update({"current_component_id":"BC-FDW-2","review_number":35,"current_size_finish_variant_id":"FDW-2-WHITE","current_name":review["proposed_name"],"state":cp["state"],"family_review_number":6,"specification_proposals_approved":False,"working_version_user_approved":False,"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS"})
component["current_component_review_record"]=rel(out)
component["last_family_media_review"]={"family":"Decowaves","finish":"Frozen Decowaves2 White","observed_utc":meta["observed_utc"],"scope":coverage["scope"],"files":82,"folders":4,"evidence":rel(HERE/"metadata-links.json"),"workbook_contains_this_live_media_audit":False}
component["updated_utc"]=now
docs["root"]["current_component_review"]=copy.deepcopy(component)
for key,path in paths.items():write(path,docs[key])
assert all(sha(path)==expected for path,expected in hashes.items())
assert read(paths["root"])["current_component_review"]==read(paths["component"])
validation={"status":"PASS","component_id":"BC-FDW-2","global_review":35,"family_review":6,"complete_single_primary_original_verified":True,"five_solo_thumbnails_inspected_now":True,"shared77context_records_revalidated_unchanged":True,"independent_component_maker_row79_recorded":True,"one_member_at_position2_in_both_arrangements":True,"native_depth8_and_maker_side5to7_separate":True,"six_specification_groups":6,"individual350GBPprice_and_availability_unapproved":True,"source_model_workbook_and_prior_keeps_unchanged":True,"parallel_import_trigger_after_owner_answer_preserved":True,"remote_files_changed":False}
write(HERE/"review-validation.json",validation)
print(json.dumps(validation))
