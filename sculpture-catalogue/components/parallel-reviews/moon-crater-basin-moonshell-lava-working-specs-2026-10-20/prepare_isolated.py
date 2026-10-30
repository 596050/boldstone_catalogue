"""Prepare the four allocated B92 working reviews; never write shared records."""
from pathlib import Path
from copy import deepcopy
from urllib.parse import quote
import datetime
import hashlib
import json

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
REV = CAT / "components/reviews"
PAR = CAT / "components/parallel-reviews"
LANE = "01a13fe6-495b-7253-b923-31823b4cbca8"
ROOT = "01a144ab-1a7c-7223-a403-73a4d53d70ff"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
TRANSCRIPT = Path("/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-" + LANE + ".jsonl")
FIELDS = ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"]
GROUPS = ["dimensions_and_depth", "weight", "material_and_finish", "fixings", "individual_price", "availability"]
SCOPES = [
    ("basin", "BC-MOON-CRATER", "build_variants", "MOON-CRATER-WHITE-BASIN"),
    ("corner", "BC-LAVA-CORNER", "size_finish_variants", "LAVA-CORNER-CURVE-WHITE"),
    ("lava-1", "BC-MLAVA-1", "size_finish_variants", "MLAVA-1-WHITE"),
    ("lava-2", "BC-MLAVA-2", "size_finish_variants", "MLAVA-2-WHITE"),
]


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


def save(p, value):
    assert p.is_relative_to(BASE) and not p.exists(), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return ref(p)


def copy(p, dest):
    assert dest.is_relative_to(BASE) and not dest.exists(), dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(p.read_bytes())
    return ref(dest)


def dbhash(blob):
    return hashlib.sha256(b"".join(hashlib.sha256(blob[i:i + 4194304]).digest()
                                  for i in range(0, len(blob), 4194304))).hexdigest()


def exact_user_line(number, text):
    raw = TRANSCRIPT.read_bytes().splitlines(keepends=True)[number - 1]
    event = json.loads(raw)
    p = event["payload"]
    actual = "\n".join(c.get("text", "") for c in p["content"])
    assert p["role"] == "user" and actual == text
    return {"transcript": str(TRANSCRIPT), "line": number, "timestamp": event["timestamp"],
            "role": "user", "text": actual, "raw_line_sha256": hashlib.sha256(raw).hexdigest(),
            "source_raw_line_digest_includes_line_ending": True}


allocations = []
for number, raw in enumerate(TRANSCRIPT.read_bytes().splitlines(keepends=True), 1):
    event = json.loads(raw)
    p = event.get("payload", {})
    out = p.get("output", "")
    if p.get("type") == "function_call_output" and isinstance(out, str) and (
        "<source_thread_id>" + ROOT + "</source_thread_id>" in out
        and "Allocate B92 requested4:" in out
    ):
        allocations.append({"transcript": str(TRANSCRIPT), "line": number,
                           "timestamp": event.get("timestamp"), "text": out,
                           "raw_line_sha256": hashlib.sha256(raw).hexdigest(),
                           "source_raw_line_digest_includes_line_ending": True,
                           "coordinator_thread_id": ROOT, "is_owner_reply": False})
assert allocations, "B92 must have an explicit coordinator allocation"
allocation_ref = save(BASE / "COORDINATOR_ALLOCATION.json", allocations[-1])

policy_ref = copy(REV / "parallel-import-2026-10-19-batch80/standing-working-acceptance-policy.json",
                  BASE / "CANONICAL_STANDING_POLICY.json")
fixing_ref = copy(REV / "parallel-import-2026-10-19-batch87/global-fixing-choice-policy.json",
                  BASE / "CANONICAL_FIXING_CHOICE_POLICY.json")
weight_ref = copy(PAR / "all-sculptures-weight-policy-2026-10-20/GLOBAL_APPROXIMATE_WEIGHT_POLICY.json",
                  BASE / "OWNER_APPROXIMATE_WEIGHT_POLICY.json")
manufacture_ref = copy(REV / "parallel-import-2026-10-19-batch51/owner-policy.json",
                       BASE / "OWNER_MANUFACTURE_POLICY.json")
policy, fixing, weight = [read(Path(x["path"])) for x in [policy_ref, fixing_ref, weight_ref]]
old_lava = PAR / "moonshell-lava-corner-wall-2026-10-19"
correction_ref = copy(old_lava / "corner-curve-white/owner-size-correction.json",
                      BASE / "EXISTING_CORNER_SIZE_CORRECTION.json")
arrangement_ref = copy(old_lava / "ARRANGEMENT_RESOLUTION.json", BASE / "EXISTING_ARRANGEMENT_RESOLUTION.json")
owner_ref = save(BASE / "CORRECTION_AND_ARRANGEMENT_OWNER_EVIDENCE.json", {
    "corner": exact_user_line(23253, "Keep “Moonshell Lava Corner Curve — White”\nMake the panel into 30cm"),
    "arrangement": exact_user_line(23516, "This is a combined Moonshell Lava 1 White and Moonshell Lava 2 White"),
    "new_owner_events": 0,
})

shared = read(REV / "specification_review_progress.json")["reviews"]
nodes, sources, snapshots = {}, {}, {}
for sub, component, kind, variant in SCOPES:
    node = shared[component][kind][variant]
    assert node["identity_confirmed"] and not node.get("specifications_approved")
    nodes[sub] = node
    directory = BASE / sub
    source_path = CAT / node["review_record"]
    latest_path = CAT / node["latest_working_entry"]
    sources[sub] = read(source_path)
    snapshots[sub] = {
        "source_review": copy(source_path, directory / "ORIGINAL_SOURCE_REVIEW.json"),
        "latest_working_entry": copy(latest_path, directory / "LATEST_SOURCE_WORKING_ENTRY.json"),
        "current_shared_review": save(directory / "SHARED_REVIEW_AT_ALLOCATION.json", node),
        "existing_name_approval": copy(CAT / node["identity_approval"], directory / "EXISTING_NAME_APPROVAL.json"),
    }

current = read(BASE / "CURRENT_REFERENCE_READBACK.json")
heads = {x["request_id"]: x[x["metadata_type"]] for x in current["metadata"]}
file_heads = {k: v for k, v in heads.items() if "rev" in v}
assert len(heads) == 15 and len(file_heads) == 9
entries = [e for x in current["listings"] for e in x["entries"]]
assert len(current["listings"]) == 6 and len(entries) == 26
assert all(not x["has_more"] and not x["cursor"] for x in current["listings"])

media_records = {}
for source in sources.values():
    for x in [source["primary_image"], *source.get("context_images", []), *source.get("series_images", [])]:
        media_records[x["file_id"]] = x
receipts_path = old_lava / "family-media/moonshell-full-image-receipts.json"
for x in read(receipts_path)["images"]:
    media_records.setdefault(x["id"], {**x, "file_id": x["id"]})
pair_source = old_lava / "wall-pair-left-white/component-review.before-answer.json"
pair = read(pair_source)["primary_image"]
media_records[pair["file_id"]] = pair
bindings = []
for file_id, head in file_heads.items():
    source = media_records[file_id]
    path = Path(source["local_path"])
    blob = path.read_bytes()
    assert hashlib.sha256(blob).hexdigest() == source["sha256"]
    assert dbhash(blob) == source["content_hash"]
    assert len(blob) == source["size"] == head["size"]
    assert head["rev"] == source["rev"] and head["name"] == source["name"]
    assert head["path_display"] == source["path_display"]
    bindings.append({"file_id": file_id, **ref(path), "bytes": len(blob),
                     "dropbox_content_hash": dbhash(blob), "current_rev": head["rev"],
                     "current_path_display": head["path_display"],
                     "cached_original_viewed_this_turn": True,
                     "new_private_original_download": False})

manifest_paths = [
    PAR / "crater-fishwave-ring-2026-10-19/moon-crater-media/contact-sheet-manifest.json",
    old_lava / "family-media/contact-sheet-manifest.json",
]
previews, sheets = [], {}
for p in manifest_paths:
    for item in read(p):
        cached = Path(item["thumbnail_path"])
        assert sha(cached) == item["thumbnail_sha256"]
        previews.append({**item, "checked_sha256": sha(cached), "viewed_in_contact_sheet_this_turn": True})
        sheet = Path(item["sheet"])
        if not sheet.is_absolute():
            sheet = p.parent / sheet
        sheets[str(sheet)] = {**ref(sheet), "viewed_this_turn": True}
assert len(previews) == 26 and len(sheets) == 6
assert sorted((e["file_id"], e["name"]) for e in entries) == sorted((e["file_id"], e["name"]) for e in previews)
image_ref = save(BASE / "CACHED_IMAGE_BINDING.json", {
    "schema": "boldstone.complete-folder-census-and-selected-cached-original-binding.v1",
    "checked_utc": NOW, "current_reference": ref(BASE / "CURRENT_REFERENCE_READBACK.json"),
    "complete_folder_census_count": 6, "complete_folder_file_count": 26,
    "bindings": bindings, "preview_source_manifests": [ref(p) for p in manifest_paths],
    "previews": previews, "contact_sheets": list(sheets.values()),
    "selected_originals_rehashed_and_viewed": 9, "cached_previews_viewed_in_contact_sheets": 26,
    "scope_limit": "All 26 current file IDs/names match the cached preview manifests. Nine selected originals are rehashed and bound to unchanged current revision, size and path. No fresh remote-byte verification is claimed for the other 17 originals.",
    "new_private_original_downloads": 0, "remote_mutations": 0,
    "excluded_groups": ["G262 Lava Moon / Luciano detail shots"],
})


def folder_url(folder_id):
    return "https://www.dropbox.com/home" + quote(heads[folder_id]["path_display"], safe="/")


def image_url(file_id):
    head = heads[file_id]
    parent = head["path_display"].rsplit("/", 1)[0]
    return "https://www.dropbox.com/home" + quote(parent, safe="/") + "?preview=" + quote(head["name"], safe="")


items = []
for sub, component, kind, variant in SCOPES:
    directory, node, original = BASE / sub, nodes[sub], sources[sub]
    id_key = "build_variant_id" if kind == "build_variants" else "size_finish_variant_id"
    current_fields = {x["group"]: x for x in node["specification_proposals"]}
    original_fields = {x["group"]: x for x in original["specification_review_items"]}
    assert set(current_fields) == set(original_fields) == set(GROUPS)
    primary, folder = node["primary_image_id"], node["primary_folder_id"]
    assert heads[primary]["path_display"].rsplit("/", 1)[0] == heads[folder]["path_display"]
    context_id = {"basin": "id:cnqzTNngPVsAAAAAAAylWQ", "corner": "id:cnqzTNngPVsAAAAAAA52LQ",
                  "lava-1": "id:cnqzTNngPVsAAAAAAAuUFA", "lava-2": "id:cnqzTNngPVsAAAAAAAuUFA"}[sub]
    context_folder = {"basin": "id:cnqzTNngPVsAAAAAAAyiuA", "corner": folder,
                      "lava-1": "id:cnqzTNngPVsAAAAAAAyi7Q", "lava-2": "id:cnqzTNngPVsAAAAAAAyi7Q"}[sub]
    context = {
        "status": "AVAILABLE_CONTEXT_WITH_PROVENANCE_UNVERIFIED",
        "type": {"basin": "Outdoor basin and garden scene", "corner": "Individual panel against timber boards",
                 "lava-1": "Owner-confirmed two-panel arrangement", "lava-2": "Owner-confirmed two-panel arrangement"}[sub],
        "representative_file_id": context_id, "representative_folder_id": context_folder,
        "image_url": image_url(context_id), "folder_url": folder_url(context_folder),
        "individual_complete_product_image_established": True, "rear_reference_established": False,
        "calibrated_profile_established": False, "scene_provenance_verified": False,
        "actual_installation_verified": False, "same_physical_cast_verified": False,
        "new_sculpture_count": 0, "source_binding": image_ref,
        "limitations": {
            "basin": "Complete individual form, bowl details and outdoor scene are available. Underside, base/body joint, anchoring, calibrated height/depth, drain and plumbing are not established. Water shown in a photograph does not certify lasting water-contact suitability.",
            "corner": "Complete clean-background depiction, timber-board context and details are available. Rear/hardware and calibrated profile are absent from the reviewed folder; photographs do not measure or prove production at the new 30 cm target.",
            "lava-1": "Individual folder has one complete clean-background depiction; five wall-arrangement frames show both panels. Owner-confirmed membership is retained, with left position based on visual comparison/review context. No new component, mould, stock or equal measured-size claim.",
            "lava-2": "Individual folder has one complete clean-background depiction; five wall-arrangement frames show both panels. Owner-confirmed membership is retained, with right position based on visual comparison/review context. No new component, mould, stock or equal measured-size claim.",
        }[sub],
    }
    arrangement = None
    if sub.startswith("lava-"):
        arrangement = {
            "arrangement_id": "MLAVA-1-PLUS-2-WHITE", "owner_confirmed_membership": True,
            "membership_basis": "OWNER_STATEMENT", "position_basis": "VISUAL_COMPARISON_AND_REVIEW_CONTEXT",
            "position": "left" if sub == "lava-1" else "right", "resolution": arrangement_ref,
            "owner_evidence": owner_ref, "same_measured_size_confirmed": False,
            "same_actual_cast_or_mould_confirmed": False, "new_products_or_stock_counts": 0,
            "Lava_Moon_or_Luciano_specifications_transferred": False,
        }
        context["arrangement"] = arrangement
    context_ref = save(directory / "CONTEXT_OUTPUT_UPDATE.json", {
        "schema": "boldstone.reviewed-context-output-update.v1", "checked_utc": NOW,
        "component_id": component, id_key: variant, "canonical_name": node["canonical_name"],
        "context_images": context, "missing_photographs": original["missing_photographs"],
        "owner_output_requirement": "Mark contextual images in the ultimate output; retain missing rear and calibrated depth views. Group scenes remain context.",
        "new_name_or_specification_approvals": 0, "new_BC_component_ids": [],
        "shared_master_writes": False, "remote_mutations": 0,
    })
    values = {
        "dimensions": {"face_range_cm": [45, 60], "overall_height_range_cm": [10, 18], "actual_measured_dimensions_cm": None} if sub == "basin" else {
            "proposed_face_cm": [30, 30] if sub == "corner" else [55, 55],
            "depth_range_cm": [5, 8], "actual_measured_dimensions_cm": None,
            "face_basis": "OWNER_DIRECTED_TARGET_INTERPRETED_AS_SQUARE" if sub == "corner" else "UNMEASURED_WORKING_GUESS",
        },
        "weight": {"proposed_range_kg": [10, 20] if sub == "basin" else [3, 6] if sub == "corner" else [8, 16],
                   "actual_weighed_kg": None, "scope": "Empty basin only" if sub == "basin" else "Individual panel only",
                   "existing_applicable_estimate_retained": True, "filled_system_or_packed_weight_kg": None},
        "material_finish": {"proposed_substrate": "Cast composite", "descriptive_finish": "Pale/white stone effect",
                            "actual_binder": None, "coating_or_sealer": None, "water_contact_suitability_verified": False},
        "fixing": {"offered_options": ["Keyhole fixing", "French cleat"], "offered_choice_owner_confirmed": True,
                   "actual_fitted_type": None, "count": None, "hardware_material": None, "attachment": None, "rated_load": None,
                   "historical_proposed_count": None if sub == "basin" else 2,
                   "historical_proposal_is_installed_fact": False,
                   "freestanding_support_proposal": "Suitable level base; support/anchoring and filled load unresolved" if sub == "basin" else None,
                   "wall_mounted_basin_design_or_applicability_verified": False},
        "individual_price": {"proposed_price_gbp": 600 if sub == "basin" else None if sub == "corner" else 550,
                             "unit": "basin only" if sub == "basin" else "per panel",
                             "owner_price_approved": False, "exact_existing_offer_confirmed": False},
        "availability": {"proposed_policy": "Enquiry only / bespoke commission" if sub == "basin" else "Enquiry only / bespoke reproduction",
                         "physical_stock": None, "reproducibility": None, "lead_time": None,
                         "physical_manufacture_owner_stated_under_policy51": True},
    }
    if sub == "corner":
        values["dimensions"]["owner_size_correction"] = correction_ref
        values["individual_price"].update(superseded_larger_size_proposal_gbp=500, current_30cm_price_unconfirmed=True)
    if sub == "basin":
        values["individual_price"]["excluded"] = ["Separate support", "Pump", "Plumbing", "Installation"]
        values["individual_price"]["supplied_body_base_assembly_confirmed"] = False
    prepared = {}
    for key, group in zip(FIELDS, GROUPS):
        field = current_fields[group]
        prepared[key] = {
            "proposal_id": variant + "-B92-" + key.upper(), "id": variant + "-B92-" + key.upper(),
            "group": group, "field": key, "display": field["display"], "value": values[key],
            "status": "PREPARED_LABELLED_WORKING_SPECIFICATION; ACTUAL_VALUES_UNVERIFIED",
            "basis": field["basis"], "source_refs": list(snapshots[sub].values()),
            "source_original_field_retained": deepcopy(original_fields[group]),
            "source_current_field_retained": deepcopy(field),
            "owner_approved": False, "owner_accepted": False, "physical_specs_verified": False,
            "physical_value_verified": False,
        }
    prepared["weight"].update(approximate_weight_policy_id=weight["policy_id"], existing_weight_display_retained_exactly=True)
    prepared["weight"]["source_refs"].append(weight_ref)
    prepared["fixing"]["display"] = (
        "Freestanding on a suitable level base — working support proposal. Catalogue choice of keyhole fixing / French cleat is retained under the owner-wide instruction; application to this basin and any wall-mounted design remain unresolved."
        if sub == "basin" else
        "Choice of keyhole fixing or French cleat — owner instruction; actual installed hardware, count and load rating unknown."
    )
    prepared["fixing"]["basis"] += (
        " Owner policy87 offers both choices catalogue-wide. Preserve the freestanding support boundary; this instruction does not establish a wall-hung basin or a suitable rated support."
        if sub == "basin" else
        " Owner policy87 now supplies the offered choice. The historical two-point proposal remains an unverified idea, not an installed count; type, attachment, spacing and load remain unknown."
    )
    prepared["fixing"].update(offered_fixing_choice_policy_id=fixing["policy_id"])
    prepared["fixing"]["source_refs"].append(fixing_ref)
    prepared["availability"]["basis"] += " Policy51 now records owner-stated physical manufacture; current stock, mould condition and repeat production remain unverified."
    prepared["availability"]["source_refs"].append(manufacture_ref)
    if sub == "corner":
        prepared["dimensions"]["source_refs"] += [correction_ref, owner_ref]
        prepared["individual_price"]["display"] = "Price on enquiry for the 30 × 30 cm target; no current price established. Earlier £500 larger-size proposal is superseded."
    review = {
        "schema": "boldstone.prepared-working-specification-review.v1", "prepared_utc": NOW,
        "review_id": variant + "-WORKING-SPECS-POLICY-B92", "component_id": component, id_key: variant,
        "canonical_name": node["canonical_name"], "variant_kind": kind, **snapshots[sub],
        "existing_name_approval_preserved": True,
        "source_specification_proposals_retained": deepcopy(original["specification_review_items"]),
        "source_current_specification_proposals_retained": deepcopy(node["specification_proposals"]),
        "specifications": prepared, "primary_file_id": primary, "folder_id": folder,
        "primary_image_role": original["primary_image"]["role"],
        "image_url": image_url(primary), "folder_url": folder_url(folder),
        "current_reference": ref(BASE / "CURRENT_REFERENCE_READBACK.json"), "image_evidence": image_ref,
        "context_images": context, "context_output_update": context_ref,
        "platform_mapping": deepcopy(node["platform_mapping"]),
        "owner_stated_manufacture": True, "owner_manufacture_policy": manufacture_ref,
        "standing_working_specification_policy": policy_ref, "policy_id": policy["policy_id"],
        "offered_fixing_choice_policy": fixing_ref, "offered_fixing_choice_policy_id": fixing["policy_id"],
        "approximate_weight_policy": weight_ref, "approximate_weight_policy_id": weight["policy_id"],
        "arrangement": arrangement, "corner_size_correction": correction_ref if sub == "corner" else None,
        "question_suppressed_under_standing_policy": True, "per_card_owner_reply_received": False,
        "new_identity_inferred": False, "shared_master_writes": False, "remote_mutations": 0,
    }
    review_ref = save(directory / "REVIEW.json", review)
    accepted = deepcopy(prepared)
    for key, field in accepted.items():
        field["source_status_before_policy_acceptance"] = field["status"]
        field.update(status="OWNER_AUTHORIZED_WORKING_ACCEPTANCE; ESTIMATES_PROPOSALS_CONFLICTS_AND_UNKNOWNS_RETAINED",
                     owner_approved=True, owner_accepted=True, approval_basis="STANDING_OWNER_POLICY",
                     policy_id=policy["policy_id"], owner_approval_scope="WORKING_SPECIFICATIONS_ONLY")
        if key == "weight":
            field["existing_approximation_accepted_under_weight_policy"] = True
        if key == "individual_price":
            field["owner_working_price_accepted"] = True
            field["current_public_selling_price_verified"] = False
            field["value"]["owner_price_approved"] = True
            field["value"]["owner_price_approval_scope"] = "ENQUIRY_STATUS_ONLY_NO_NUMERIC_PRICE" if sub == "corner" else "UNCOSTED_WORKING_PROPOSAL_ONLY"
    decision = {
        "schema": "boldstone.owner-variant-working-specifications-keep.v1",
        "decision_id": component + ":" + variant + ":WORKING-SPECS:POLICY80",
        "recorded_utc": NOW, "owner_session": LANE, "component_id": component, id_key: variant,
        "variant_kind": kind, "canonical_name": node["canonical_name"], "review_id": review["review_id"],
        "status": "WORKING_SPECIFICATIONS_ACCEPTED_UNDER_OWNER_STANDING_POLICY",
        "action": "Accept six labelled working fields under standing policy80; retain applicable estimates under90 and fixing choice under87",
        "approval_basis": "STANDING_OWNER_POLICY", "policy_id": policy["policy_id"],
        "standing_working_specification_policy": policy_ref,
        "authoritative_user_evidence": policy["authoritative_user_evidence"], "user_statement": policy["user_statement"],
        "per_card_owner_reply_received": False, "synthetic_owner_reply_created": False,
        "prepared_review": review_ref, "source_review_before_answer": review_ref, **snapshots[sub],
        "source_specification_proposals_retained": review["source_specification_proposals_retained"],
        "source_current_specification_proposals_retained": review["source_current_specification_proposals_retained"],
        "source_specifications_retained": prepared, "specifications": accepted,
        "specification_review_items": list(accepted.values()),
        "approved_proposal_ids": [x["proposal_id"] for x in accepted.values()], "approved_field_groups": FIELDS,
        "all_six_owner_specification_fields_accepted": True, "specifications_approved": True, "proposals_approved": True,
        "owner_estimates_accepted": True, "source_claims_accepted_as_working": True,
        "physical_specs_verified": False, "independently_measured_or_certified": False, "actual_stock_verified": False,
        "estimate_and_proposal_labels_retained": True, "source_conflicts_and_unknowns_retained": True,
        "primary_file_id": primary, "folder_id": folder, "image_link": image_url(primary), "folder_link": folder_url(folder),
        **{k: review[k] for k in ["primary_image_role", "current_reference", "image_evidence", "context_images",
                                 "context_output_update", "platform_mapping", "owner_stated_manufacture",
                                 "owner_manufacture_policy", "standing_working_specification_policy",
                                 "offered_fixing_choice_policy", "offered_fixing_choice_policy_id",
                                 "approximate_weight_policy", "approximate_weight_policy_id", "arrangement",
                                 "corner_size_correction"]},
        "existing_name_approval_preserved": True, "manufacture_question_required": False,
        "offered_fixing_choice_not_installed_hardware_confirmation": True,
        "existing_approximate_weight_retained": True,
        "scope": "Existing kept individual/build only. Preserve original and current six source dictionaries. Corner30 target is not a measured specimen; freestanding basin support is not a verified wall-mounted design. Moonshell1+2 arrangement remains two existing components, separate from Lava Moon/Luciano.",
        "new_name_approvals": 0, "new_specification_approvals": 1, "new_approved_field_groups": 6,
        "new_owner_approval_events": 0, "new_owner_policy_events": 0, "new_BC_component_ids": [],
        "new_design_mould_or_stock_counts": 0, "shared_master_import_performed": False,
        "shared_master_writes_by_lane": False, "remote_mutations": 0, "fresh_private_original_downloads": 0,
    }
    decision_ref = save(directory / "SPECIFICATION_APPROVAL.json", decision)
    save(directory / "OWNERSHIP.json", {
        "owner_session": LANE, "shared_writer_session": ROOT, "component_id": component, id_key: variant,
        "allocation": allocation_ref, "reserved_batch": 92, "status": "PREPARED_PENDING_VERIFICATION_AND_SHARED_IMPORT",
        "active_review_id": None, "decision": decision_ref, "shared_master_writes_by_lane": False,
    })
    save(directory / "WORKING_STATE.json", {
        "status": "WORKING_SPECIFICATIONS_ACCEPTED_UNDER_STANDING_POLICY_PENDING_SHARED_IMPORT",
        "updated_utc": NOW, "component_id": component, id_key: variant, "canonical_name": node["canonical_name"],
        "decision": decision_ref, "specifications": accepted, "routine_keep_question_required": False,
        "workbook_publication_pending": True, "physical_specs_verified": False, "actual_stock_verified": False,
    })
    items.append({"component_id": component, "variant": variant, "variant_kind": kind, "id_key": id_key,
                  "target": str(directory), "decision": decision_ref, "prepared_review": review_ref, "context": context_ref})
save(BASE / "PREPARED_PACKAGE_INDEX.json", {
    "status": "PREPARED_AWAITING_INDEPENDENT_LOCAL_VERIFICATION", "created_utc": NOW, "reserved_batch": 92,
    "items": items, "new_specification_approvals": 4, "new_approved_field_groups": 24,
    "new_owner_policy_events": 0, "new_owner_approval_events": 0, "shared_master_writes_by_lane": False,
    "remote_mutations": 0,
})
print(json.dumps({"status": "PREPARED", "variants": [x["variant"] for x in items]}))
