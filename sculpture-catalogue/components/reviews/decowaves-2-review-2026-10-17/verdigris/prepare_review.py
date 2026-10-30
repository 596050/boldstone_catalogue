"""Stage verdigris Decowaves2, retaining all component/arrangement boundaries."""
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


paths = {"walkthrough":REVIEWS/"walkthrough_checkpoint.json","progress":REVIEWS/"specification_review_progress.json","component":ROOT/"components/checkpoint.json","root":ROOT/"checkpoint.json"}
docs = {key:read(path) for key,path in paths.items()}
cp,progress,component = [docs[key] for key in ["walkthrough","progress","component"]]
out = HERE/"component-review.json"
if cp.get("current_review_record") == rel(out):
    print(json.dumps({"status":"ALREADY_PREPARED","review":rel(out)}))
    raise SystemExit(0)
assert cp["current_component_id"] == "BC-DECO-2" and cp["current_size_finish_variant_id"] == "DECO-2-TERRACOTTA" and cp["current_answer_recorded"]
terra_source = HERE.parent/"terracotta/component-review.json"
terra_approval = HERE.parent/"terracotta/identity-approval.json"
base_source = REVIEWS/"decowaves-1-review-2026-10-17/verdigris/component-review.json"
approval = read(terra_approval)
assert approval["user_statement"] == "Keep “Decowaves 2 — Terracotta”" and approval["identity_confirmed"] and not approval["specifications_approved"]
now = datetime.now(timezone.utc).isoformat()
protected = [ROOT/"components/evidence/component_register.json",ROOT/cp["register_workbook"],REVIEWS/"user_classifications.json",terra_source,terra_approval,base_source]
hashes = {path:sha(path) for path in protected}
write(HERE/"before-verdigris-review.json",{"recorded_utc":now,"files":{rel(paths[key]):value for key,value in docs.items()}})
parent = progress["reviews"]["BC-DECO-2"]
parent_before = copy.deepcopy(parent)
terra = read(terra_source)
meta = read(HERE/"metadata-links.json")
file,folder = meta["primary_metadata"]["file"],meta["folder_metadata"]["folder"]
assert file["id"] == "id:cnqzTNngPVsAAAAAAAykAg" and folder["id"] == "id:cnqzTNngPVsAAAAAAAyiXw"
assert Path(file["path_display"]).parent.as_posix() == folder["path_display"]
assert {key:len(value["entries"]) for key,value in meta["listings"].items()} == {"solo":9,"pair":21,"room":2}
assert all(not value["has_more"] and not value["cursor"] for value in meta["listings"].values())
for name in ["download-receipt.json","pair-download-receipt.json"]:
    receipt = read(HERE/name)
    assert receipt["actual_size"] == receipt["size"] and receipt["content_hash"] == receipt["calculated_dropbox_content_hash"]
    assert sha(Path(receipt["local_path"])) == receipt["sha256"]
http = read(HERE/"public-pair-http-receipt.json")
assert http["status"] == 200 and http["confirmed_claims"]["pair_price_gbp"] == 600 and http["confirmed_claims"]["whole_pair_weight_kg"] == 14
assert http["confirmed_claims"]["per_panel_dimensions_cm"] == [90,15,8]
previews = {item["file_name"]:item for item in meta["previews"]}
primary,containing = previews[file["id"]],previews[folder["id"]]
model = read(ROOT/"components/evidence/component_register.json")
bom = next(item for item in model["bom"] if item["component_id"] == "BC-DECO-2" and item["offer_ref"] == "O060")
review = copy.deepcopy(read(base_source))
items = review["specification_review_items"]
for item in items:item["proposal_id"] = item["proposal_id"].replace("DECO-1-VERDIGRIS","DECO-2-VERDIGRIS")
items[0]["basis"] = "O060's current two-panel description explicitly gives90×15×8cm for each verdigris panel, including Decowaves2 at the right of the matched arrangement. These are per-panel source claims, not divided overall dimensions or a measurement of the pictured cast. The9cm terracotta2 depth is a separate unconfirmed proposal."
items[1]["basis"] = "The other terracotta member, Decowaves1, has a separate approximately6kg individual source claim. Together with this similarly sized relief's unknown backing/binder/reinforcement, that motivates a broad6–9kg owner-check range. There is no sourced individual Decowaves2 mass;14kg belongs to the entire verdigris pair and has not been divided to assign7kg."
items[2]["basis"] = "The current/native green-pair source identifies cast composite and applied verdigris patina without binder chemistry. Gypsum is a hypothesis from the other terracotta member's explicit source and the white cast rear of terracotta Decowaves2. Neither the current green cast's chemistry nor AC730/solid bronze, reinforcement or sealing is established."
items[2]["value"]["proposed_binder"] = "Gypsum composite, by related terracotta-version analogy only"
items[3]["basis"] = "O060 says ready to hang without defining the fitting. The current individual terracotta Decowaves2 rear id:cnqzTNngPVsAAAAAAAye8g shows one metal keyhole plate, motivating the same fitting as a proposal for green. None of the32 reviewed green images shows the reverse, so actual attachment, wall hardware and rated load remain unknown."
items[3]["source_refs"] = ["https://boldstonesculpture.com/buy/p/two-frozen-decowaves-wall-sculpture-1","id:cnqzTNngPVsAAAAAAAye8g:terracotta2 rear; analogy only"]
items[4]["value"].update({"proposed_amount":375,"sale_unit":"One verdigris Decowaves2 panel","discussion_range_gbp":[300,400]})
items[4]["display"] = "£375 per individual panel — new proposed price"
items[4]["basis"] = "Choose375 within the prepared300–400 Decowaves2 individual discussion range. It uses dated individual white-standard pricing only as an analogy and allows an uncosted coloured-finish difference; actual production/finish costs are not established. This is not a current individual offer or half of the600 pair price, and does not approve the terracotta350 proposal."
items[4]["source_refs"] = ["components/reviews/decowaves-2-review-2026-10-17/terracotta/advisory-packet-used.json:specifications.individual_price","https://boldstonesculpture.com/buy/p/two-frozen-decowaves-wall-sculpture-1:whole pair only"]
mapping = copy.deepcopy(review["platform_mapping"])
mapping.update({"component_role":"Curled/grooved/spiral panel at right in the source arrangement","bom_position":bom,"related_terracotta_other_member_offer":"O050","public_image_scope":"Current Dropbox solo and pair originals show the same grooved/spiral right member as the retained public pair image; current public page still refers to the same two-panel offer/SKU. Exact photo-byte equality and cast measurements are not asserted."})
coverage = {"complete_individual_front":True,"detail":True,"oblique_views":True,"wall_display":True,"series_arrangement":True,"room_context":True,"garden_context":True,"rear":False,"installation_provenance":"UNCONFIRMED; room/garden examples do not establish client installation or current stock","physical_stock_inferred":False,"scope":"Fresh complete32-file census:9solo,21pair,2context in3folders; all32cached thumbnails inspected. Current solo primary and pair originals downloaded and Dropbox-hash verified. Other30originals not re-downloaded."}
next_review = {"component_id":"BC-FDW-1","review_number":34,"family_review_number":5,"size_finish_variant_id":"FDW-1-WHITE"}
review.update({"prepared_utc":now,"component_id":"BC-DECO-2","canonical_design_name":"Decowaves 2","proposed_name":"Decowaves 2 — Verdigris","display_name":"Decowaves 2 — Verdigris","review_number":33,"family_review_number":4,"family_review_total":6,"size_finish_variant_id":"DECO-2-VERDIGRIS","scope":"One individual verdigris Decowaves2finish, with grooves, curls and a lower spiral. Parent terracotta name/identity was kept only. O060 is the matched verdigris pair; its whole-set mass/price are not individual specifications. Keep white Frozen designs separate.","primary_image_id":file["id"],"primary_folder_id":folder["id"],"primary_image_link":primary["copy_link_url"],"primary_folder_link":containing["copy_link_url"],"metadata_checked_utc":meta["observed_utc"],"reference_refresh":rel(HERE/"metadata-links.json"),"primary_original_receipt":rel(HERE/"download-receipt.json"),"pair_original_receipt":rel(HERE/"pair-download-receipt.json"),"image_review_index":rel(HERE/"image-review-index.json"),"context_image_id":"id:cnqzTNngPVsAAAAAAAyk4Q","context_folder_id":"id:cnqzTNngPVsAAAAAAAyk4A","context_image_link":previews["id:cnqzTNngPVsAAAAAAAyk4Q"]["copy_link_url"],"series_image_link":previews["id:cnqzTNngPVsAAAAAAAyerg"]["copy_link_url"],"parent_identity_approval":rel(terra_approval),"parent_identity_approval_scope":"Terracotta Decowaves2name and depicted identity only; all six specification groups and price proposals remain pending.","public_source_claims":http["confirmed_claims"]|{"scope":"Dimensions are per panel;14kg and600GBP are whole pair only","source_url":http["source_url"]},"public_page_check":{"checked_utc":http["checked_utc"],"source_url":http["source_url"],"web_tool_status":"Could not access page; direct public HTTP GET returned200 and product visible text plus JSON-LD were inspected","http_receipt":rel(HERE/"public-pair-http-receipt.json"),"jsonld_snapshot":rel(HERE/"public-product-jsonld.json"),"visible_text":rel(HERE/"public-pair-visible-text.txt"),"retained_public_pair_image_receipt":"components/reviews/decowaves-1-review-2026-10-17/verdigris/public-pair-image-receipt.json"},"specification_review_items":items,"platform_mapping":mapping,"photo_coverage":coverage,"identity_confirmed":False,"specifications_approved":False,"physical_specs_verified":False,"open_gaps":["Confirm90×15×8cm source size applies to pictured green cast","Actual individual dry mass;6–9kg is a guess and14kg source is whole pair","Actual binder/reinforcement/metal content/coating/sealing; gypsum hypothesis unconfirmed","Green reverse photograph, actual fixing/attachment/wall hardware and rated load","Approve individual375GBP price and sale policy; confirm stock/capacity/lead time","Existing individual and Shopify offers remain unconfirmed; O060 is a Squarespace pair","Confirm context provenance and care/packing details; native parts1 versus visual2 discrepancy preserved"],"next_review_after_keep":next_review,"next_global_component_id":"BC-FDW-1"})
write(out,review)
terra_variant = {"size_finish_variant_id":"DECO-2-TERRACOTTA","canonical_name":terra["proposed_name"],"review_record":rel(terra_source),"identity_confirmed":True,"identity_approval":rel(terra_approval),"primary_image_id":terra["primary_image_id"],"primary_folder_id":terra["primary_folder_id"],"specification_proposals":copy.deepcopy(terra["specification_review_items"]),"specifications_approved":False,"proposals_approved":False,"physical_specs_verified":False,"specification_review_status":"NAME KEPT; SIX SPECIFICATION GROUPS REMAIN PENDING"}
green_variant = {"size_finish_variant_id":"DECO-2-VERDIGRIS","canonical_name":review["proposed_name"],"review_record":rel(out),"identity_confirmed":False,"primary_image_id":file["id"],"primary_folder_id":folder["id"],"specification_proposals":copy.deepcopy(items),"specifications_approved":False,"proposals_approved":False,"physical_specs_verified":False,"photo_coverage":coverage,"platform_mapping":mapping}
parent["size_finish_variants"] = {"DECO-2-TERRACOTTA":terra_variant,"DECO-2-VERDIGRIS":green_variant}
for pending in parent["pending_size_finish_variants"]:
    if pending["variant_id"] == "DECO-2-VERDIGRIS":pending.update({"review_status":"PRESENTED; AWAITING OWNER NAME/IDENTITY AND SPECIFICATION REVIEW","review_record":rel(out)})
assert {key:value for key,value in parent.items() if key not in ["size_finish_variants","pending_size_finish_variants"]} == {key:value for key,value in parent_before.items() if key not in ["size_finish_variants","pending_size_finish_variants"]}
progress["updated_utc"] = now
cp.update({"proposed_name":review["proposed_name"],"state":"Awaiting individual verdigris Decowaves2 name/identity and six source/working specification groups","current_size_finish_variant_id":"DECO-2-VERDIGRIS","current_review_record":rel(out),"current_family_review_number":4,"primary_image":{"file_id":file["id"],"name":file["name"],"path_display":file["path_display"],"copy_link_url":primary["copy_link_url"],"open_in_dropbox_url":primary["open_in_dropbox_url"]},"containing_folder":{"folder_id":folder["id"],"name":folder["name"],"path_display":folder["path_display"],"copy_link_url":containing["copy_link_url"],"open_in_dropbox_url":containing["open_in_dropbox_url"]},"answer_state":"No answer yet for verdigris variant. Terracotta name/identity Keep preserved; a name-only reply approves this depicted variant name and identity only.","question_scope":"Keep Decowaves2 — Verdigris for this individual grooved/spiral panel. Six groups:source90H×15W×8Dcm;individual6–9kgGUESS;sourcecastcomposite/appliedverdigris with gypsum-binderGUESS;one rear keyholeplateGUESS;375GBPindividualpricePROPOSAL;individualmade-to-order/enquirePROPOSAL. Source600GBPand14kgcoverwholepaironly. Name-only answer confirms identity only.","metadata_checked_utc":meta["observed_utc"],"current_answer_recorded":False,"current_specification_answer_recorded":False,"current_dimension_answer_recorded":False,"working_version_user_approved":False,"displayed_identity_evidence_file_ids":[file["id"]],"displayed_identity_evidence_folder_ids":[folder["id"]],"current_component_source_notes":[item["display"] for item in items],"family_review_evidence":rel(HERE/"metadata-links.json"),"next_review_after_keep":next_review,"review_decision_mode":"SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS","updated_utc":now})
component["interactive_review_state"].update({"current_name":review["proposed_name"],"state":cp["state"],"current_size_finish_variant_id":"DECO-2-VERDIGRIS","family_review_number":4,"specification_proposals_approved":False,"working_version_user_approved":False,"review_decision_mode":"SIZE_FINISH_VARIANT_NAME_AND_SPECIFICATIONS"})
component["current_component_review_record"] = rel(out)
component["last_family_media_review"] = {"family":"Decowaves","finish":"Component2 Verdigris","observed_utc":meta["observed_utc"],"scope":coverage["scope"],"files":32,"folders":3,"evidence":rel(HERE/"metadata-links.json"),"workbook_contains_this_live_media_audit":False}
component["updated_utc"] = now
docs["root"]["current_component_review"] = copy.deepcopy(component)
for key,path in paths.items():write(path,docs[key])
assert all(sha(path) == expected for path,expected in hashes.items())
assert read(paths["root"])["current_component_review"] == read(paths["component"])
validation = {"status":"PASS","component_id":"BC-DECO-2","variant_id":"DECO-2-VERDIGRIS","family_review_number":4,"complete_individual_primary_and_pair_originals_verified":True,"public_pair_claims_and_sku_refreshed_http200":True,"source_per_panel_depth8cm":True,"individual_6to9kg_weight_and375GBP_price_are_proposals":True,"whole_pair14kg_and600GBP_not_allocated":True,"rear_missing_room_and_series_available":True,"all32cached_thumbnails_inspected":True,"terra_parent_keep_and_all_prior_decisions_source_model_workbook_unchanged":True,"remote_files_changed":False}
write(HERE/"review-validation.json",validation)
print(json.dumps(validation))
