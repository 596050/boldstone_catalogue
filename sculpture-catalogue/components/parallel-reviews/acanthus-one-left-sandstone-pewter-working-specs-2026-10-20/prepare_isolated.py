"""Prepare allocated batch88 without changing shared records or frozen sources."""
from pathlib import Path
from copy import deepcopy
from urllib.parse import quote
import datetime
import hashlib
import json

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
REV = CAT / "components/reviews"
LANE = "01a13fe6-495b-7253-b923-31823b4cbca8"
ROOT = "01a144ab-1a7c-7223-a403-73a4d53d70ff"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
FIELDS = ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"]
LABELS = ["Dimensions / depth", "Weight", "Material / finish", "Fixing", "Individual price", "Availability"]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return {"path": str(path), "sha256": sha(path)}


def save(path, value):
    assert path.is_relative_to(BASE) and not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return ref(path)


def copy(source, target):
    assert target.is_relative_to(BASE) and not target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    return ref(target)


def content_hash(blob):
    return hashlib.sha256(b"".join(
        hashlib.sha256(blob[i:i + 4194304]).digest()
        for i in range(0, len(blob), 4194304)
    )).hexdigest()


policy_path = REV / "parallel-import-2026-10-19-batch80/standing-working-acceptance-policy.json"
policy = read(policy_path)
policy_ref = copy(policy_path, BASE / "CANONICAL_STANDING_POLICY.json")
fixing_path = CAT / "components/parallel-reviews/embedded-shells-faceted-mound-working-specs-2026-10-20/owner-fixing-correction-and-options-2026-10-20/GLOBAL_FIXING_CHOICE_POLICY.json"
assert sha(fixing_path) == "3a5d5f8c2e86417a5d1aea0b6d055564b34e7c43b5f7860a5a9c2cd62057fc76"
fixing_policy = read(fixing_path)
fixing_ref = copy(fixing_path, BASE / "GLOBAL_FIXING_CHOICE_POLICY.json")
manufacture_path = REV / "parallel-import-2026-10-19-batch51/owner-policy.json"
assert sha(manufacture_path) == "43e1d46c399200cb87725d976d885f6b467881bbbedfc19687b1b012e8b8afca"
manufacture = {
    "policy_id": "ALL-SCULPTURES-PHYSICALLY-MADE-OWNER-LINE17365",
    "source": str(manufacture_path), "sha256": sha(manufacture_path),
    "evidence_level": "OWNER_STATED_UNIVERSAL_MANUFACTURE",
    "specification_or_stock_approval_inferred": False,
}
transcript = Path("/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-" + LANE + ".jsonl")
allocations = []
for number, raw in enumerate(transcript.read_bytes().splitlines(), 1):
    event = json.loads(raw)
    p = event.get("payload", {})
    text = p.get("output", "")
    if p.get("type") == "function_call_output" and isinstance(text, str) and (
        "<source_thread_id>" + ROOT + "</source_thread_id>" in text
        and "Reserve next B88:" in text
    ):
        allocations.append({
            "transcript_path": str(transcript), "line": number,
            "timestamp": event.get("timestamp"), "text": text,
            "raw_line_sha256": hashlib.sha256(raw).hexdigest(),
            "source_raw_line_digest_includes_line_ending": False,
            "coordinator_thread_id": ROOT, "is_owner_reply": False,
        })
assert allocations
allocation_ref = save(BASE / "COORDINATOR_ALLOCATION.json", allocations[-1])
for pol in [policy, fixing_policy]:
    ev = pol["authoritative_user_evidence"]
    path = Path(ev.get("transcript", ev.get("transcript_path")))
    raw = path.read_bytes().splitlines(keepends=True)[ev["line"] - 1]
    if not ev.get("source_raw_line_digest_includes_line_ending"):
        raw = raw.rstrip(b"\r\n")
    assert hashlib.sha256(raw).hexdigest() == ev["raw_line_sha256"]

current = read(BASE / "CURRENT_REFERENCE_READBACK.json")
heads = {x["request_id"]: x[x["metadata_type"]] for x in current["metadata"]}
fresh = current["listings"][0]
old_base = CAT / "components/parallel-reviews/acanthus-mixed-groups-2026-10-19/evidence"
old = read(old_base / "fresh-read-receipt.json")
old_heads = {x["file"]["id"]: x["file"] for x in old["heads"] if x.get("file")}
old_list = next(x for x in old["listings"] if any(e["file_id"] == "id:cnqzTNngPVsAAAAAAAudqw" for e in x["entries"]))
norm = lambda entries: sorted((x["file_id"], x["name"], x["file"]["size"]) for x in entries)
assert not fresh["has_more"] and not fresh["cursor"] and norm(fresh["entries"]) == norm(old_list["entries"])
selected = ["id:cnqzTNngPVsAAAAAAAudqw", "id:cnqzTNngPVsAAAAAAAufFw", "id:cnqzTNngPVsAAAAAAAuV6Q", "id:cnqzTNngPVsAAAAAAAt-VQ"]
bindings = []
for file_id in selected:
    item = next(x for x in old["downloads"] if x["id"] == file_id)
    path = Path(item["local_path"])
    blob = path.read_bytes()
    assert sha(path) == item["sha256"] and len(blob) == item["size"]
    assert content_hash(blob) == item["content_hash"]
    assert heads[file_id]["rev"] == old_heads[file_id]["rev"]
    assert heads[file_id]["size"] == len(blob)
    bindings.append({
        "file_id": file_id, **ref(path), "bytes": len(blob),
        "dropbox_content_hash": content_hash(blob), "current_rev": heads[file_id]["rev"],
        "cached_original_viewed_this_turn": True,
        "scope": "White comparison only" if file_id == selected[3] else "Allocated Assorted Colours evidence",
        "new_private_original_download": False,
    })
image_ref = save(BASE / "CACHED_IMAGE_BINDING.json", {
    "schema": "boldstone.cached-image-current-binding.v1", "checked_utc": NOW,
    "complete_assorted_colours_file_count": 3,
    "selected_white_comparator_originals": 1, "bindings": bindings,
    "all_four_cached_originals_rehashed_and_viewed": True,
    "no_other_folder_completeness_asserted": True,
    "new_private_original_downloads": 0, "remote_mutations": 0,
    "observations": {
        selected[0]: "Cropped granular, speckled warm pale relief detail; no whole perimeter or rear.",
        selected[1]: "Cropped reflective/brushed-looking relief detail under warm light; metal composition cannot be identified.",
        selected[2]: "Grouped workshop table scene. Existing owner-kept target positions are retained; other objects are context, with no new identity, mould or stock counts.",
        selected[3]: "Existing White comparison on a wooden wall; no calibrated scale or rear view.",
    },
})
comparison_ref = copy(old_base / "visual-comparison.json", BASE / "HISTORICAL_VISUAL_COMPARISON.json")
white_source = REV / "acanthus-component-review-2026-10-17/one-leaf-left-specification-proposals.json"
white_ref = copy(white_source, BASE / "WHITE_COMPARATOR_WORKING_PROPOSALS.json")
white_approval_ref = copy(
    REV / "acanthus-component-review-2026-10-17/one-leaf-left-specification-approval.json",
    BASE / "WHITE_COMPARATOR_APPROVAL.json",
)
shared = read(REV / "user_classifications.json")


def image_url(file_id):
    m = heads[file_id]
    parent = m["path_display"].rsplit("/", 1)[0]
    return "https://www.dropbox.com/home" + quote(parent, safe="/") + "?preview=" + quote(m["name"], safe="")


def folder_url(folder_id):
    return "https://www.dropbox.com/home" + quote(heads[folder_id]["path_display"], safe="/")


items = []
for sub, batch, variant, filename, name in [
    ("sandstone", 16, "AC-ONE-LEFT-SANDSTONE", "a50ba371170fcc255cd10582d9fd136cabb2262d398fa885760c9225d64286d5.json", "Acanthus One Leaf Left — Sandstone"),
    ("pewter", 17, "AC-ONE-LEFT-PEWTER", "9ae983272eff9ec637891c3b457f05ad3a63517bafdedb784f33983a21e0e18a.json", "Acanthus One Leaf Left — Pewter"),
]:
    target = BASE / sub
    imported = REV / ("parallel-import-2026-10-19-batch" + str(batch))
    source_path = imported / "sources" / filename
    assert sha(source_path) == filename[:-5]
    source_ref = copy(source_path, target / "SOURCE_REVIEW_AT_ALLOCATION.json")
    source = read(source_path)
    identity_path = imported / "decisions/BC-AC-ONE" / variant / "identity-approval.json"
    identity_ref = copy(identity_path, target / "EXISTING_NAME_APPROVAL.json")
    identity = read(identity_path)
    assert identity["component_id"] == "BC-AC-ONE" and identity["size_finish_variant_id"] == variant
    current_identity = next(x for x in shared["size_finish_variant_decisions"] if x.get("size_finish_variant_id") == variant)
    assert current_identity["canonical_name"] == name
    assert not any(x.get("size_finish_variant_id") == variant for x in shared["size_finish_variant_specification_decisions"])
    raw_specifications = source["proposed_specifications_for_this_finish"]
    assert set(raw_specifications) == {"dimensions", "weight", "material_finish", "fixings", "individual_price", "availability"}
    primary = source["primary_image"]["id"]
    folder = source["folder_id"]
    context_id = source["overview_image"]["id"]
    context = {
        "status": "AVAILABLE_GROUPED_WORKSHOP_CONTEXT_ONLY",
        "type": "Grouped workshop reference with the existing owner-kept target",
        "image_url": image_url(context_id), "folder_url": folder_url(folder),
        "representative_file_id": context_id, "representative_folder_id": folder,
        "target_position": source["target_position"],
        "limitations": "Complete three-file Assorted Colours census: two cropped details and one grouped workshop photograph. All three cached originals and the separate White comparator were viewed and rehashed. Isolated complete target under neutral light, finished rear/fixings, calibrated profile and individual room installation were not established in these three files; availability elsewhere remains unknown. Exact same cast across the detail and overview is unconfirmed. Other depicted objects remain context without new component, mould or stock counts.",
        "individual_complete_product_image_established": False,
        "individual_wider_room_established": False, "rear_reference_established": False,
        "grouped_workshop_context_available": True, "scene_provenance_verified": False,
        "actual_installation_verified": False, "same_physical_cast_verified": False,
        "new_sculpture_count": 0, "source_binding": image_ref,
    }
    context_ref = save(target / "CONTEXT_OUTPUT_UPDATE.json", {
        "schema": "boldstone.reviewed-context-output-update.v1", "checked_utc": NOW,
        "component_id": "BC-AC-ONE", "size_finish_variant_id": variant,
        "canonical_name": name, "context_images": context,
        "owner_output_requirement": "Identify contextual images and missing individual/rear photographs in the ultimate output; do not newly identify objects from grouped scenes.",
        "new_name_or_specification_approvals": 0, "new_BC_component_ids": [],
        "shared_master_writes": False, "remote_mutations": 0,
    })
    values = {
        "dimensions": {"proposed_dimensions_cm": [30, 30, 6], "actual_measured_dimensions_cm": None},
        "weight": {"proposed_weight_kg": 4, "proposed_range_kg": [3, 5], "actual_weighed_kg": None, "same_construction_as_white_confirmed": False},
        "material_finish": {"proposed_substrate": "Cast plaster", "descriptive_finish": "Sandstone effect" if sub == "sandstone" else "Pewter-coloured metallic effect", "actual_binder": None, "actual_stone_or_metal_composition": None, "sealer": None},
        "fixing": {"offered_options": ["Keyhole fixing", "French cleat"], "offered_choice_owner_confirmed": True, "actual_fitted_type": None, "count": None, "hardware_material": None, "attachment": None, "rated_load": None, "historical_proposed_count": 1, "historical_proposal_is_installed_fact": False},
        "individual_price": {"proposed_starting_price_gbp": 175, "finish_surcharge_gbp": None, "exact_existing_offer_confirmed": False, "owner_price_approved": False},
        "availability": {"proposed_policy": "Made to order / enquire subject to reproduction confirmation", "physical_stock": None, "reproducibility": None, "lead_time": None},
    }
    displays = {
        "dimensions": "Approximately 30 × 30 × 6 cm — White-comparator estimate; this finish unmeasured",
        "weight": "Approximately 4 kg; working range 3–5 kg — White-comparator estimate; unweighed",
        "material_finish": (
            "Cast plaster with sandstone-effect finish — hypothesis; actual binder, stone content and finish recipe unknown"
            if sub == "sandstone" else
            "Cast plaster with pewter-coloured metallic-effect finish — hypothesis; actual binder, metal content and finish recipe unknown"
        ),
        "fixing": "Choice of keyhole fixing or French cleat — owner instruction; installed hardware, fixing count and load rating unconfirmed",
        "individual_price": "£175 per panel as a working starting-price proposal; finish surcharge and exact selling price unconfirmed",
        "availability": "Made to order / enquire — working proposal; stock, reproducibility and lead time unknown",
    }
    bases = {
        "dimensions": "The earlier finish draft copied the White working estimate. White itself used related Flower/Two Leaves 30 × 30 × 6 cm source claims as an analogy. These photographs are uncalibrated; accepting the finish estimate does not measure it or transfer White approval as a physical fact.",
        "weight": "The earlier finish draft uses the White 4 kg, 3–5 kg working estimate. White was based on a different Flower listing's approximate mass. Actual binder, backing, relief volume and finish application are unknown; no group mass is divided and no finish has been weighed here.",
        "material_finish": (
            "The owner-kept Sandstone name and visible granular pale surface describe the finish. Cast plaster was a hypothesis borrowed from related White proposals, not an object-specific material certificate. Actual stone content, binder, reinforcement, sealer and suitability remain unknown."
            if sub == "sandstone" else
            "The owner corrected the name to Pewter. Warm-lit reflective photographs do not establish pewter metal, solid-metal construction, alloy or coating formulation. Cast plaster remains a White-comparator hypothesis; actual binder, reinforcement, sealer and suitability are unknown."
        ),
        "fixing": "The owner now requests a choice of keyhole fixing or French cleat for all sculptures. This is an offered catalogue choice, not evidence of installed hardware on this finish. The earlier one-recessed-hanger guess remains in the frozen source dictionary; neither its count nor attachment/load is confirmed. The separate keyhole-type confirmations for Embedded Shells and Faceted Mound are not transferred.",
        "individual_price": "The earlier finish draft proposed £175 using the White starting-price proposal. White used different Flower/Full £175 public snapshots dated 16 October 2026. This is a historical comparison, not a current price for this finish. Finish surcharge, costing, VAT/delivery treatment and exact platform offer remain unresolved.",
        "availability": "The existing owner-wide instruction records physical manufacture. Made to order / enquire is a working sale-policy proposal; current cast stock, usable mould, repeatable manufacture and lead time remain unknown.",
    }
    prepared = {}
    for key, label in zip(FIELDS, LABELS):
        raw_key = "fixings" if key == "fixing" else key
        prepared[key] = {
            "proposal_id": variant + "-" + key.upper(), "id": variant + "-" + key.upper(),
            "field": label, "display": displays[key], "value": values[key],
            "status": "PREPARED_WORKING_ESTIMATE_OR_PROPOSAL; ACTUAL_VALUES_UNVERIFIED",
            "basis": bases[key], "source_refs": [source_ref, white_ref],
            "source_finish_field_retained": deepcopy(raw_specifications[raw_key]),
            "owner_approved": False, "owner_accepted": False,
            "physical_specs_verified": False, "physical_value_verified": False,
        }
    prepared["fixing"]["source_refs"].append(fixing_ref)
    prepared["fixing"]["offered_fixing_choice_policy_id"] = fixing_policy["policy_id"]
    prepared["fixing"]["status"] = "OWNER_OFFERED_FIXING_CHOICE; INSTALLED_DETAILS_UNKNOWN"
    platform = {
        "status": "EXACT_FINISH_SQUARESPACE_SHOPIFY_OFFER_UNCONFIRMED",
        "squarespace_id": None, "shopify_handle": None, "shared_sku": None,
        "white_or_other_design_platform_ids_transferred": False,
        "public_comparator_prices_are_historical": True,
        "live_platform_records_refreshed": False,
    }
    review = {
        "schema": "boldstone.prepared-working-specification-review.v1", "prepared_utc": NOW,
        "review_id": variant + "-WORKING-SPECS-POLICY-01", "component_id": "BC-AC-ONE",
        "size_finish_variant_id": variant, "canonical_name": name,
        "existing_name_approval": identity_ref, "existing_name_approval_preserved": True,
        "source_review": source_ref,
        "source_specification_proposals_retained": raw_specifications,
        "source_finish_specification_dictionary_retained": raw_specifications,
        "specifications": prepared,
        "primary_file_id": primary, "folder_id": folder,
        "primary_image_role": "Cropped detail of the existing owner-kept finish",
        "image_url": image_url(primary), "folder_url": folder_url(folder),
        "current_reference": ref(BASE / "CURRENT_REFERENCE_READBACK.json"),
        "image_evidence": image_ref, "context_images": context,
        "context_output_update": context_ref, "platform_mapping": platform,
        "white_comparator_approval": white_approval_ref,
        "white_approval_transferred_to_other_finishes": False,
        "historical_visual_comparison": comparison_ref,
        "owner_stated_manufacture": True, "owner_manufacture_policy": manufacture,
        "standing_working_specification_policy": policy_ref, "policy_id": policy["policy_id"],
        "offered_fixing_choice_policy": fixing_ref,
        "offered_fixing_choice_policy_id": fixing_policy["policy_id"],
        "question_suppressed_under_standing_policy": True,
        "per_card_owner_reply_received": False, "new_identity_inferred": False,
        "shared_master_writes": False, "remote_mutations": 0,
    }
    review_ref = save(target / "REVIEW.json", review)
    accepted = deepcopy(prepared)
    for key, field in accepted.items():
        field["source_status_before_policy_acceptance"] = field["status"]
        field.update(
            status="OWNER_AUTHORIZED_WORKING_ACCEPTANCE_UNDER_STANDING_POLICY; ESTIMATES_AND_UNKNOWNS_RETAINED",
            owner_approved=True, owner_accepted=True,
            approval_basis="STANDING_OWNER_POLICY", policy_id=policy["policy_id"],
            owner_approval_scope="WORKING_SPECIFICATIONS_ONLY; NO_ACTUAL_MEASUREMENT_OR_HARDWARE_CERTIFICATION",
        )
        if key == "fixing":
            field["status"] = "OWNER_OFFERED_KEYHOLE_OR_FRENCH_CLEAT_CHOICE; INSTALLED_HARDWARE_COUNT_AND_LOAD_UNKNOWN"
        if key == "individual_price":
            field["value"]["owner_price_approved"] = True
            field["value"]["owner_price_approval_scope"] = "WORKING_STARTING_PRICE_ONLY; SURCHARGE_UNRESOLVED"
            field["owner_working_price_accepted"] = True
            field["current_public_selling_price_verified"] = False
    decision = {
        "schema": "boldstone.owner-finish-working-specifications-keep.v1",
        "decision_id": "BC-AC-ONE:" + variant + ":WORKING-SPECS:POLICY80",
        "recorded_utc": NOW, "owner_session": LANE, "review_id": review["review_id"],
        "component_id": "BC-AC-ONE", "size_finish_variant_id": variant, "canonical_name": name,
        "action": "accept six labelled working specifications under standing owner affirmative policy",
        "status": "WORKING_SPECIFICATIONS_ACCEPTED_UNDER_OWNER_STANDING_POLICY",
        "approval_basis": "STANDING_OWNER_POLICY", "policy_id": policy["policy_id"],
        "standing_working_specification_policy": policy_ref,
        "authoritative_user_evidence": policy["authoritative_user_evidence"],
        "user_statement": policy["user_statement"],
        "per_card_owner_reply_received": False, "synthetic_owner_reply_created": False,
        "prepared_review": review_ref, "source_review_before_answer": review_ref,
        "source_review": source_ref, "source_specifications_retained": prepared,
        "source_specification_proposals_retained": raw_specifications,
        "source_finish_specification_dictionary_retained": raw_specifications,
        "specifications": accepted, "specification_review_items": list(accepted.values()),
        "approved_proposal_ids": [x["proposal_id"] for x in accepted.values()],
        "approved_field_groups": FIELDS, "all_six_owner_specification_fields_accepted": True,
        "specifications_approved": True, "proposals_approved": True,
        "owner_estimates_accepted": True, "source_claims_accepted_as_working": True,
        "physical_specs_verified": False, "independently_measured_or_certified": False,
        "actual_stock_verified": False, "estimate_and_proposal_labels_retained": True,
        "source_conflicts_and_unknowns_retained": True,
        "primary_file_id": primary, "folder_id": folder,
        "image_link": image_url(primary), "folder_link": folder_url(folder),
        "primary_image_role": review["primary_image_role"],
        "current_reference": review["current_reference"], "image_evidence": image_ref,
        "context_images": context, "context_output_update": context_ref,
        "platform_mapping": platform,
        "existing_name_approval_preserved": True, "existing_name_approval": identity_ref,
        "white_comparator_approval": white_approval_ref,
        "white_approval_transferred_to_other_finishes": False,
        "owner_stated_manufacture": True, "owner_manufacture_policy": manufacture,
        "manufacture_question_required": False,
        "offered_fixing_choice_policy": fixing_ref,
        "offered_fixing_choice_policy_id": fixing_policy["policy_id"],
        "offered_fixing_choice_not_installed_hardware_confirmation": True,
        "scope": "Existing " + name + " only. Retain White-comparator estimates and original finish dictionaries. Offer keyhole or French cleat under the separate global instruction without confirming current fitted hardware, count or rating. Keep grouped workshop imagery as context; no new components, moulds or stock inferred.",
        "new_name_approvals": 0, "new_specification_approvals": 1,
        "new_owner_approval_events": 0, "new_owner_policy_events": 0,
        "new_approved_field_groups": 6, "new_BC_component_ids": [],
        "new_design_mould_or_stock_counts": 0,
        "shared_master_import_performed": False, "shared_master_writes_by_lane": False,
        "remote_mutations": 0, "fresh_private_original_downloads": 0,
    }
    decision_ref = save(target / "SPECIFICATION_APPROVAL.json", decision)
    save(target / "OWNERSHIP.json", {
        "owner_session": LANE, "shared_writer_session": ROOT,
        "component_id": "BC-AC-ONE", "size_finish_variant_id": variant,
        "allocation": allocation_ref, "reserved_batch": 88,
        "status": "SEALED_PREPARATION_PENDING_SHARED_IMPORT",
        "active_review_id": None, "decision": decision_ref,
        "shared_master_writes_by_lane": False, "remote_mutations": 0,
    })
    save(target / "WORKING_STATE.json", {
        "status": "WORKING_SPECIFICATIONS_ACCEPTED_UNDER_STANDING_POLICY_PENDING_SHARED_IMPORT",
        "updated_utc": NOW, "component_id": "BC-AC-ONE", "size_finish_variant_id": variant,
        "canonical_name": name, "active_review_id": None, "decision": decision_ref,
        "specifications": accepted, "policy_id": policy["policy_id"],
        "offered_fixing_choice_policy_id": fixing_policy["policy_id"],
        "routine_keep_question_required": False, "workbook_publication_pending": True,
        "physical_specs_verified": False, "actual_stock_verified": False,
    })
    items.append({
        "variant": variant, "target": str(target), "decision": decision_ref,
        "prepared_review": review_ref, "context_output_update": context_ref,
    })
save(BASE / "PREPARED_PACKAGE_INDEX.json", {
    "status": "PREPARED_AWAITING_INDEPENDENT_LOCAL_VERIFICATION", "created_utc": NOW,
    "reserved_batch": 88, "items": items,
    "new_specification_approvals": 2, "new_approved_field_groups": 12,
    "new_owner_policy_events": 0, "new_owner_approval_events": 0,
    "shared_master_writes_by_lane": False, "remote_mutations": 0,
})
print(json.dumps({"status": "PREPARED", "variants": [x["variant"] for x in items]}))
