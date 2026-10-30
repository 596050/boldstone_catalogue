"""Prepare a separate terracotta Decowaves2 review with explicit evidence states."""
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
docs = {key: read(path) for key,path in paths.items()}
cp, progress, component = [docs[key] for key in ["walkthrough","progress","component"]]
out = HERE / "component-review.json"
if cp.get("current_review_record") == rel(out):
    print(json.dumps({"status":"ALREADY_PREPARED","review":rel(out)}))
    raise SystemExit(0)
assert cp["current_component_id"] == "BC-DECO-1" and cp["current_size_finish_variant_id"] == "DECO-1-VERDIGRIS" and cp["current_answer_recorded"]
assert cp["review_order"].index("BC-DECO-2") + 1 == 33 and "BC-DECO-2" not in progress["reviews"]
prior_approval = REVIEWS / "decowaves-1-review-2026-10-17/verdigris/identity-approval.json"
assert read(prior_approval)["user_statement"] == "Keep “Decowaves 1 — Verdigris”" and not read(prior_approval)["specifications_approved"]
now = datetime.now(timezone.utc).isoformat()
protected = [ROOT/"components/evidence/component_register.json",ROOT/cp["register_workbook"],REVIEWS/"user_classifications.json",ROOT/cp["current_review_record"],prior_approval]
hashes = {path:sha(path) for path in protected}
write(HERE/"before-decowaves2-review.json",{"recorded_utc":now,"files":{rel(paths[key]):value for key,value in docs.items()}})
meta = read(HERE/"metadata-links.json")
file,folder = meta["primary_metadata"]["file"],meta["folder_metadata"]["folder"]
assert file["id"] == "id:cnqzTNngPVsAAAAAAAye6Q" and folder["id"] == "id:cnqzTNngPVsAAAAAAAyiXQ"
assert Path(file["path_display"]).parent.as_posix() == folder["path_display"]
assert {key:len(value["entries"]) for key,value in meta["listings"].items()} == {"solo":7,"pair":8}
assert all(not value["has_more"] and not value["cursor"] for value in meta["listings"].values())
for name in ["download-receipt.json","rear-download-receipt.json"]:
    receipt = read(HERE/name)
    assert receipt["actual_size"] == receipt["size"] and receipt["content_hash"] == receipt["calculated_dropbox_content_hash"]
    assert sha(Path(receipt["local_path"])) == receipt["sha256"]
previews = {entry["file_name"]:entry for entry in meta["previews"]}
primary,containing = previews[file["id"]],previews[folder["id"]]
model = read(ROOT/"components/evidence/component_register.json")
base = next(item for item in model["components"] if item["component_id"] == "BC-DECO-2")
related = [item for item in model["platform_records"] if item["offer_ref"] in ["O050","O060"]]
items = [
    {"proposal_id":"DECO-2-TERRACOTTA-DIMENSIONS","field":"Individual dimensions","value":{"proposed_height_cm":90,"proposed_width_cm":15,"proposed_overall_depth_cm":9,"estimated_depth_range_cm":[8,10],"actual_measurement":None},"display":"Approximately 90 H × 15 W × 9 D cm — guess; depth estimated8–10cm","status":"UNCONFIRMED TERRACOTTA2 SIZE/DEPTH PROPOSAL","basis":"The visually related verdigris Decowaves2 is described at90×15×8cm per panel; terracotta Decowaves1 has a separate90×15×9cm source claim. Together with comparable proportions in the individual/paired photographs, these motivate a90×15cm face and9cm working depth proposal for this terracotta member. No ruler establishes its dimensions, and neither other version's specification is transferred as a fact.","source_refs":["O060:verdigris version only","O050:terracotta Decowaves1 only","id:cnqzTNngPVsAAAAAAAye6Q"]},
    {"proposal_id":"DECO-2-TERRACOTTA-WEIGHT","field":"Individual dry weight","value":{"proposed_estimated_range_kg":[6,9],"actual_weighed_kg":None},"display":"Approximately 6–9 kg individually — guess","status":"CONSTRUCTION ANALOGY; NO INDIVIDUAL TERRACOTTA2 MASS SOURCE","basis":"The related terracotta Decowaves1 listing gives approximately6kg. A broad6–9kg range is proposed for this similarly sized hollow-backed relief, allowing unknown wall thickness, binder, reinforcement and finish. It is not derived by dividing O060's14kg verdigris-pair weight.","source_refs":["O050:related component approximate6kg only","id:cnqzTNngPVsAAAAAAAye8g:recessed rear observation"]},
    {"proposal_id":"DECO-2-TERRACOTTA-MATERIAL","field":"Material and finish","value":{"proposed_substrate":"Gypsum composite","proposed_finish":"Terracotta-effect coloured surface","actual_binder":None,"actual_reinforcement":None,"actual_coating_process":None,"actual_sealing":None},"display":"Gypsum composite with terracotta-effect surface — guess","status":"MATERIAL/FINISH HYPOTHESIS; REAR COLOUR IS NOT CHEMISTRY","basis":"The front is reddish terracotta coloured and the rear shows a white cast body with substantial recesses. Related Decowaves1's terracotta offer explicitly uses gypsum composite. That makes gypsum with a coloured surface a reviewable hypothesis for Decowaves2, not a chemically verified composition, fired terracotta claim, AC730 assignment or exterior-performance specification.","source_refs":["O050:related terracotta Decowaves1 material only","id:cnqzTNngPVsAAAAAAAye6Q","id:cnqzTNngPVsAAAAAAAye8g"]},
    {"proposal_id":"DECO-2-TERRACOTTA-FIXING","field":"Fixing","value":{"observed_rear_plate_count":1,"observed_type":"Metal keyhole plate on rear bridge","actual_metal_alloy":None,"actual_attachment_specification":None,"actual_wall_hardware":None,"rated_load":None},"display":"One metal keyhole plate visible on rear — image observation; hardware/load unknown","status":"CURRENT REAR IMAGE OBSERVED; NO INSTALLATION/LOAD SPECIFICATION","basis":"The current individual rear original id:cnqzTNngPVsAAAAAAAye8g shows one metal keyhole plate fixed across the bridge between rear recesses. Its alloy, attachment strength, matching wall screw, substrate suitability and rated load cannot be established from the photograph.","source_refs":["id:cnqzTNngPVsAAAAAAAye8g"]},
    {"proposal_id":"DECO-2-TERRACOTTA-PRICE","field":"Individual retail price","value":{"proposed_amount":350,"currency":"GBP","sale_unit":"One terracotta Decowaves2 panel","discussion_range_gbp":[300,400],"actual_current_offer_price":None},"display":"£350 per individual panel — new proposal","status":"UNAPPROVED COMMERCIAL GUESS; NO EXACT TERRACOTTA2 OFFER","basis":"Choose350 within the prepared300–400 individual discussion range, informed by dated white-standard price comparisons and an uncosted coloured-finish difference. This is not a current offer, production quote, O050's48.44 Decowaves1 price or half of O060's600 verdigris-pair price. Historical comparisons do not establish material/mould equivalence.","source_refs":["components/reviews/decowaves-2-review-2026-10-17/terracotta/advisory-packet-used.json:specifications.individual_price"]},
    {"proposal_id":"DECO-2-TERRACOTTA-AVAILABILITY","field":"Availability","value":{"proposed_sale_status":"Made to order individually / enquire","physical_stock_quantity":None,"lead_time":None,"production_capacity":None},"display":"Made to order individually / enquire — proposed; stock and lead time unknown","status":"PROPOSED INDIVIDUAL SALE POLICY; ACTUAL AVAILABILITY UNCONFIRMED","basis":"Photographs and other-version offers do not establish current finished stock, production readiness, mould availability or dispatch time for this individual terracotta panel. Propose a made-to-order/enquiry sale policy for owner review.","source_refs":["components/reviews/decowaves-2-review-2026-10-17/terracotta/advisory-packet-used.json:specifications.availability"]},
]
mapping = {"squarespace_id":None,"shopify_handle":None,"shared_sku":None,"status":"NO CONFIRMED EXACT TERRACOTTA DECOWAVES2 OFFER","individual_offer_confirmed":False,"related_verdigris_pair_offer":"O060","related_verdigris_squarespace_id":"6a9ff9707f3077314dd70146","related_verdigris_sku":"SQ2946502","related_pair_component_position":2,"related_terracotta_other_member_offer":"O050","scope":"O060 is the verdigris two-panel arrangement; O050 is the other individual terracotta member, Decowaves1. Neither is an exact terracotta Decowaves2 platform record. Keep all set/other-member values separately scoped.","live_account_records_refreshed":False,"white_frozen_designs_merged":False}
coverage = {"complete_individual_front":True,"oblique_views":True,"rear":True,"series_arrangement":True,"wall_display":True,"wider_room":False,"dedicated_close_up":False,"installation_provenance":"UNCONFIRMED","physical_stock_inferred":False,"scope":"Fresh complete15-file census:7solo and8terracotta pair images in2folders; all15cached thumbnails visually inspected. Current individual front and single-panel rear originals downloaded and Dropbox-hash verified. Other13originals not re-downloaded.","rear_identity_scope":"Individual rear is filed with this component and has a handwritten number2 marking; the paired rear context contains two separate backs. Marking is retained as image evidence, not proof of white Frozen Decowaves mould equivalence."}
next_review = {"component_id":"BC-DECO-2","review_number":33,"family_review_number":4,"size_finish_variant_id":"DECO-2-VERDIGRIS"}
review = {"schema_version":1,"prepared_utc":now,"component_id":"BC-DECO-2","canonical_design_name":"Decowaves 2","proposed_name":"Decowaves 2 — Terracotta","display_name":"Decowaves 2 — Terracotta","family":"Decowaves","review_number":33,"family_review_number":3,"family_review_total":6,"size_finish_variant_id":"DECO-2-TERRACOTTA","variant_only_review":False,"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS","scope":"One individual terracotta Decowaves2design, with curled relief/grooves and a spiral near the bottom. Review separately from Decowaves1, verdigris Decowaves2 and the white Frozen Decowaves records; source dimensions and prices from those versions are analogy only.","primary_image_id":file["id"],"primary_folder_id":folder["id"],"primary_image_link":primary["copy_link_url"],"primary_folder_link":containing["copy_link_url"],"metadata_checked_utc":meta["observed_utc"],"reference_refresh":rel(HERE/"metadata-links.json"),"primary_original_receipt":rel(HERE/"download-receipt.json"),"rear_original_receipt":rel(HERE/"rear-download-receipt.json"),"image_review_index":rel(HERE/"image-review-index.json"),"rear_image_id":"id:cnqzTNngPVsAAAAAAAye8g","rear_folder_id":folder["id"],"rear_image_link":previews["id:cnqzTNngPVsAAAAAAAye8g"]["copy_link_url"],"series_image_id":"id:cnqzTNngPVsAAAAAAAye5g","series_folder_id":"id:cnqzTNngPVsAAAAAAAye5A","series_image_link":previews["id:cnqzTNngPVsAAAAAAAye5g"]["copy_link_url"],"advisory_preparation":rel(HERE/"advisory-packet-used.json"),"specification_review_items":items,"source_offer_refs":[],"related_offer_refs":["O050","O060"],"related_offer_snapshots":related,"baseline_component_snapshot":base,"platform_mapping":mapping,"photo_coverage":coverage,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"open_gaps":["Owner check or measure actual face dimensions and maximum depth;90×15×9cm is a proposal","Weigh actual panel;6–9kg is a guess","Confirm binder, reinforcement, finish process and sealing; gypsum remains a hypothesis","Rear plate alloy/attachment, matching wall hardware and rated load","Approve proposed individual£350price and sale policy; establish stock/capacity/lead time","Exact Squarespace/Shopify/shared-SKU counterpart remains unconfirmed","Wider room/customer-installation image and dedicated close-up for this terracotta finish not identified","Care/packing dimensions and weight; white Frozen mould equivalence unresolved"],"next_review_after_keep":next_review,"next_global_component_id":"BC-FDW-1","remote_files_changed":False,"live_platform_records_changed":False}
write(out,review)
progress["reviews"]["BC-DECO-2"] = {"reviewed_utc":now,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"proposed_name":review["proposed_name"],"size_finish_variant_id":review["size_finish_variant_id"],"specification_proposals":copy.deepcopy(items),"source_specifications_recorded":True,"source_offer_refs":[],"related_offer_refs":["O050","O060"],"platform_mapping":mapping,"primary_image_id":file["id"],"primary_folder_id":folder["id"],"review_record":rel(out),"gaps":review["open_gaps"],"photo_coverage":coverage,"pending_size_finish_variants":[{"variant_id":"DECO-2-VERDIGRIS","proposed_name":"Decowaves 2 — Verdigris","review_status":"NOT YET PRESENTED","primary_file_id":"id:cnqzTNngPVsAAAAAAAykAg","primary_folder_id":"id:cnqzTNngPVsAAAAAAAyiXw"}]}
progress["updated_utc"] = now
cp.update({"current_component_id":"BC-DECO-2","current_review_number":33,"current_size_finish_variant_id":"DECO-2-TERRACOTTA","proposed_name":review["proposed_name"],"state":"Awaiting individual terracotta Decowaves2 name/identity and six specification groups","primary_image":{"file_id":file["id"],"name":file["name"],"path_display":file["path_display"],"copy_link_url":primary["copy_link_url"],"open_in_dropbox_url":primary["open_in_dropbox_url"]},"containing_folder":{"folder_id":folder["id"],"name":folder["name"],"path_display":folder["path_display"],"copy_link_url":containing["copy_link_url"],"open_in_dropbox_url":containing["open_in_dropbox_url"]},"answer_state":"No answer yet; a name-only Keep confirms name and depicted identity only, not the six specification groups.","question_scope":"Keep Decowaves2 — Terracotta for this individual curled/grooved panel. Display six groups:approximately90H×15W×9DcmGUESS;6–9kgGUESS;gypsumcomposite/terracottaeffectGUESS;one rear metalkeyholeplateOBSERVEDwithhardware/loadunknown;£350individualpricePROPOSAL;individualmade-to-order/enquirePROPOSALwithstock/leadtimeunknown. Other-member/finish or pair values are not treated as this panel's source facts. Name-only answer confirms identity only.","metadata_checked_utc":meta["observed_utc"],"current_answer_recorded":False,"current_specification_answer_recorded":False,"current_dimension_answer_recorded":False,"working_version_user_approved":False,"current_review_record":rel(out),"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS","current_family_review_number":3,"current_family_review_total":6,"active_family":"Decowaves","family_review_evidence":rel(HERE/"metadata-links.json"),"next_review_after_keep":next_review,"displayed_identity_evidence_file_ids":[file["id"]],"displayed_identity_evidence_folder_ids":[folder["id"]],"current_component_source_notes":[item["display"] for item in items],"updated_utc":now})
for cid,vid,receipt in [("BC-ECHO-2","ECHO-2-WHITE","components/parallel-reviews/echo-sound-2026-10-17/echo-two-white/identity-approval.json"),("BC-SEAWEED-ROUGH",None,"components/parallel-reviews/rust-seaweed-2026-10-17/seaweed-rough/review-approval.json")]:
    if (ROOT/receipt).exists() and not any(item.get("receipt") == receipt for item in cp.setdefault("parallel_import_queue",[])):
        cp["parallel_import_queue"].append({"component_id":cid,"variant_id":vid,"receipt":receipt,"receipt_sha256":sha(ROOT/receipt),"status":"RECEIVED NAME ONLY; PENDING NEXT SERIALIZED IMPORT","scope":"Reported named Keep; six specification groups remain source/working proposals. Independently verify exact owner statement and source snapshot before import.","approval_imported":False,"recorded_utc":now})
component["interactive_review_state"].update({"current_component_id":"BC-DECO-2","review_number":33,"current_size_finish_variant_id":"DECO-2-TERRACOTTA","current_name":review["proposed_name"],"state":cp["state"],"family_review_number":3,"specification_proposals_approved":False,"working_version_user_approved":False,"review_decision_mode":"COMPONENT_NAME_AND_SPECIFICATIONS"})
component["current_component_review_record"] = rel(out)
component["last_family_media_review"] = {"family":"Decowaves","finish":"Component2 Terracotta","observed_utc":meta["observed_utc"],"scope":coverage["scope"],"files":15,"folders":2,"evidence":rel(HERE/"metadata-links.json"),"workbook_contains_this_live_media_audit":False}
component["updated_utc"] = now
docs["root"]["current_component_review"] = copy.deepcopy(component)
for key,path in paths.items():write(path,docs[key])
assert all(sha(path) == expected for path,expected in hashes.items())
assert read(paths["root"])["current_component_review"] == read(paths["component"])
validation = {"status":"PASS","component_id":"BC-DECO-2","variant_id":"DECO-2-TERRACOTTA","global_review":33,"family_review":3,"complete_individual_primary_verified":True,"single_rear_original_verified":True,"one_keyhole_plate_observed":True,"six_groups_with_explicit_guess_or_observation_states":True,"source_dimensions_weight_price_from_other_versions_not_promoted":True,"files_listed_and_cached_thumbnails_inspected":15,"wider_room_still_missing":True,"prior_decowaves1_keeps_source_model_workbook_unchanged":True,"remote_files_changed":False}
write(HERE/"review-validation.json",validation)
print(json.dumps(validation))
