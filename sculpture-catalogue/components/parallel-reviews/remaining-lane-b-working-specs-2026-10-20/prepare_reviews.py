"""Prepare allocated B96 reviews in isolation. Never modify shared catalogue files."""
from pathlib import Path
from copy import deepcopy
from urllib.parse import quote
import datetime
import hashlib
import html
import json
import re

B = Path(__file__).resolve().parent
C = B.parents[2]
LANE = "01a13fe6-495b-7253-b923-31823b4cbca8"
ROOT = "01a144ab-1a7c-7223-a403-73a4d53d70ff"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
FIELDS = ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"]
GROUPS = dict(zip(FIELDS, ["dimensions_and_depth", "weight", "material_and_finish", "fixings", "individual_price", "availability"]))
OUT = {}


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


def stage(name, obj):
    p = B / name
    assert not p.exists() and p.is_relative_to(B), p
    data = (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode()
    OUT[p] = data
    return {"path": str(p), "sha256": hashlib.sha256(data).hexdigest()}


def copy(source, name):
    p = B / name
    assert not p.exists()
    data = Path(source).read_bytes()
    OUT[p] = data
    return {"path": str(p), "sha256": hashlib.sha256(data).hexdigest()}


def normalise(label):
    label = label.lower()
    if "dimension" in label or "depth" in label:
        return "dimensions"
    if "weight" in label:
        return "weight"
    if "material" in label:
        return "material_finish"
    if "fix" in label:
        return "fixing"
    if "price" in label:
        return "individual_price"
    if "availab" in label:
        return "availability"
    raise ValueError(label)


def fields(raw):
    pairs = raw.items() if isinstance(raw, dict) else [(x.get("group", x.get("field")), x) for x in raw]
    result = {}
    for name, value in pairs:
        key = normalise(name)
        assert key not in result
        result[key] = deepcopy(value)
    assert set(result) == set(FIELDS)
    return result


def props(node):
    return node.get("specification_proposals", node.get("specifications", node.get("specification_review_items")))


def clean(text):
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.replace("**", "")


def temporal(text):
    """The copied source remains exact; only the current display dates old claims."""
    text = clean(text)
    text = text.replace("live shipping", "historically captured shipping")
    text = text.replace("current Squarespace listing", "historically captured Squarespace listing")
    text = text.replace("current listing", "historically captured listing")
    text = text.replace("Website lists one in stock", "Historical website capture listed one in stock")
    return text


discovery = read(B / "DISCOVERED_EVIDENCE.json")
visual = read(B / "VISUAL_INDEX.json")
policy = {k: read(v["path"]) for k, v in discovery["policies"].items()}
scopes = discovery["scopes"]
assert len(scopes) == 40 and "BC-AC-FLOWER|BASE" not in {r["key"] for r in scopes}
heads, head_rows = {}, {}
for filename in ["CURRENT_METADATA.json", "CURRENT_METADATA_RETRY.json"]:
    for row in read(B / filename)["metadata"]:
        if row.get("metadata_type") in ("file", "folder") and row.get(row["metadata_type"]):
            h = row[row["metadata_type"]]
            assert h["id"] == row["request_id"]
            heads[h["id"]] = h
            head_rows[h["id"]] = deepcopy(row)
assert set(heads) == set(discovery["metadata_requests"]) and len(heads) == 125
media = {r["file_id"]: r for r in visual["media"]}
assert len(media) == 67
current_ref = stage("CURRENT_REFERENCE_BINDING.json", {
    "schema": "boldstone.bounded-current-reference-binding.v1", "checked_utc": NOW,
    "source_receipts": [ref(B / x) for x in ["CURRENT_METADATA.json", "CURRENT_METADATA_RETRY.json"]],
    "metadata": list(head_rows.values()), "unique_heads": 125, "file_heads": 67, "folder_heads": 58,
    "initial_throttled_requests": 25, "all_initial_throttles_resolved": True,
    "complete_folder_census_performed": False, "selected_references_only": True,
    "remote_mutations": 0, "new_private_original_downloads": 0,
})


def folder_url(folder_id):
    return "https://www.dropbox.com/home" + quote(heads[folder_id]["path_display"], safe="/")


def image_url(file_id):
    h = heads[file_id]
    return "https://www.dropbox.com/home" + quote(h["path_display"].rsplit("/", 1)[0], safe="/") + "?preview=" + quote(h["name"], safe="")


def observation(r):
    cid, scope = r["component_id"], r["scope"]
    notes = {
        "BC-BONE-WATER": "Selected primary is a cropped spiral detail, not a complete outer rectangle. Historical source coverage describes complete views elsewhere; those were not newly inspected. Keep the existing primary and approved working version.",
        "BC-RIYADH-1": "Broad relief panel in a workshop; an edge approaches the frame. Project dimensions remain provisionally mapped, with no calibrated scale or confirmed pictured orientation.",
        "BC-RIYADH-2": "Horizontal workshop spiral panel and wider workshop context. Photograph orientation does not resolve the project-size mapping.",
        "BC-RIYADH-3": "Complete tall pale arc panel against a clean background. Project-size mapping remains provisional.",
        "BC-RUST-PANEL": "Complete square patinated board and room-context preview. Appearance does not verify surface chemistry or the source weight unit.",
        "BC-SEAWEED-ROUGH": "Complete individual ripple panel plus paired series context. The companion remains a separate sculpture; no set specification is divided.",
        "BC-SEAWEED-SMOOTH": "Complete individual ripple panel plus paired series and blue-lit contextual scene. The blue-lit scene does not establish the same cast, dimensions or supplied lighting.",
        "BC-CORAL": "Complete coarse white spiral panel and staircase/room-context preview. Owner-stated 55 × 55 cm face is preserved; the image is not a measurement.",
        "BC-SM-SPIRAL": "Complete white spiral panel on brick, wider wall context and a multi-panel arrangement. Rotation does not create a new design or mould.",
        "BC-SM-QUARTER": "Complete individual white quarter-moon panel against a clean background. Historical arrangement evidence remains separate from the selected primary.",
        "BC-AZURE": "Complete tall narrow blue-and-white marbled panel and room scene. Neither image measures the artwork or establishes its construction. Shipping fields remain separate from artwork dimensions and the conditional net-weight estimate.",
        "BC-WBMS-WAVE": "Complete individual Wave panel and a three-position timber/corridor arrangement. The historical Wave and Moonshadow designs remain two designs; no new third design, set-weight division or exact cast match is inferred.",
        "BC-WBMS-MOON": "Complete individual Moonshadow panel and three-position arrangement. Opposite Moonshadow positions remain the existing design; no new sculpture identity or divided set specifications.",
        "BC-MOON-WATER": "Complete basin/catcher appearance on brick in the selected cached preview. Historical family context is retained; it was not newly inspected in this bounded pass.",
        "BC-MOONWAVE": "Complete curved vertical panel on brick in the selected cached preview. Historical contextual evidence is retained; it was not newly inspected in this bounded pass.",
        "UGR-G310": "Complete wide textured white work. Preserve the owner-named whole source and owner-stated 80 × 60 cm face; do not register a new BC component or decompose the picture.",
    }
    if cid in notes:
        return notes[cid]
    if cid == "BC-SHELL-B1" and scope == "BASE":
        return "Complete isolated standard panel. The garden/basin context depicts a related water-feature configuration and does not turn the standard panel into that build."
    if cid in ("BC-SHELL-B1", "BC-SHELL-B2", "BC-SHELL-I"):
        if "WATER" in scope:
            return "Existing outlet/water-feature panel depiction with garden or basin context. Keep the named build; images do not verify plumbing, waterproofing, pump/basin inclusion or filled assembly loads."
        return "Complete standard landscape spiral panel. Related garden/outlet imagery remains water-feature context, not proof that the standard panel includes plumbing."
    if cid in ("BC-DR-WAVE1", "BC-DR-SPIRAL"):
        return "Complete individual front of the existing named Dune Ripple finish. Selected group/room/garden views, where present, remain contextual. No set mass division, new identity or actual finish chemistry is inferred. Historical candidate rear images are retained, but exact cast-linked hardware remains unresolved."
    if cid == "BC-SPICE":
        return "Complete square textured panel in its existing numbered layout. Any workshop/group scene remains context. Visible texture does not establish actual spices or other inclusions."
    if scope == "MSW-HALF-MOON-BLACK-WHITE":
        return "Complete sculpture appears within room scenes; a separate isolated front is not established. Vertical and horizontal depictions do not establish distinct products or the same physical cast."
    if scope == "MSW-SHELLWAVE-WHITE-WATER-FEATURE":
        return "Primary shows an installation with two horizontal panels. Retain the existing named water-adapted Shellwave target; the other panel remains context. Do not decompose the scene or certify plumbing."
    if cid in ("BC-MSW-MOON", "BC-MSW-SPIRAL"):
        return "Complete individual white panel, garden/wall context and a multi-panel arrangement. Keep existing identities; arrangement, rotation and outdoor depiction do not prove same-cast provenance or exposure suitability."
    raise ValueError(r["key"])


observations = {r["key"]: observation(r) for r in scopes}
visual_ref = stage("VISUAL_INSPECTION_RECEIPT.json", {
    "schema": "boldstone.cached-contact-sheet-visual-inspection.v1",
    "recorded_utc": NOW, "visual_index": ref(B / "VISUAL_INDEX.json"),
    "status": "COMPLETED", "distinct_images_viewed": 67, "contact_sheets_viewed": 12,
    "cached_original_representations": 61, "cached_preview_only_representations": 6,
    "inspection_method": "Model visually inspected all twelve labelled contact-sheet derivatives from cached originals/previews during this task. This is not a full-resolution original-image inspection.",
    "full_resolution_inspection_claimed": False, "new_private_original_downloads": 0,
    "complete_folder_census_claimed": False, "observations_by_scope": observations,
    "limitations": "Uncalibrated images do not establish measurements, composition, rear hardware, price, stock or the provenance of an installation.",
})

owner_continue = copy(C / "components/parallel-reviews/remaining-working-review-inventory-2026-10-20/OWNER_CONTINUE_ALL_EVIDENCE.json", "OWNER_CONTINUE_ALL_EVIDENCE.json")
corrections = {}
correction_paths = {
    "BC-BONE-WATER|BASE": "components/reviews/bone-water-spiral-review-2026-10-17/working-face-size-approval.json",
    "BC-CORAL|CORAL-WHITE": "components/reviews/coral-spiral-review-2026-10-17/user-face-dimensions-55x55.json",
    "UGR-G310|SOUNDWAVE-WHITE-G310003": "components/reviews/parallel-import-2026-10-19-batch22/source-face-dimension-decision.json",
}
for key, path in correction_paths.items():
    corrections[key] = copy(C / path, key.replace("|", "__").lower() + "/EXISTING_FACE_DECISION.json")

shell_ref = next(r["source_snapshots"]["node"] for r in scopes if r["scope"] == "MSW-SHELLWAVE-WHITE")
azure_model = {
    "schema": "boldstone.conditional-individual-weight-estimate.v1", "created_utc": NOW,
    "component_id": "BC-AZURE", "size_finish_variant_id": "AZURE-BLUE-WHITE",
    "scope": "Dry individual artwork only; packaging excluded",
    "estimated_kg": 7, "estimated_range_kg": [4, 10], "actual_net_weight_kg": None,
    "confidence": "LOW; CONDITIONAL ON UNCONFIRMED FACE SIZE AND COMPARABLE MINERAL CAST CONSTRUCTION",
    "assumed_face_cm": [100, 16], "assumed_face_is_measured_or_owner_confirmed": False,
    "assumption_source": "Historical shipping dimensions provide only a tentative scale hypothesis, not measured panel geometry.",
    "construction_assumption": "Mineral cast relief comparable in effective thickness/density to the historical white Shellwave estimate; Azure substrate and backing are unknown.",
    "comparison": {"source": shell_ref, "historical_comparator_face_cm": [100, 22], "historical_comparator_weight_kg": [8, 10]},
    "calculation": "8–10 kg × (100×16)/(100×22) = 5.82–7.27 kg; rounded centre 7 kg and widened working range 4–10 kg for unverified geometry, relief, backing and finish.",
    "unrounded_scaled_range_kg": [8 * 16 / 22, 10 * 16 / 22],
    "shipping_record": {"source_field": "shippingWeight", "raw": 33.07, "unit": "POUND", "converted_kg": 33.07 * 0.45359237, "approximately_kg": 15},
    "shipping_weight_used_as_net_weight": False, "superseded_2_to_4_kg_light_board_guess_reactivated": False,
    "limitations": "If actual size or construction differs, the entire estimate may be invalid. This estimate does not replace the shipping record or supply a rated mounting load.",
    "approximate_weight_policy_id": policy["weight"]["policy_id"],
}
azure_ref = stage("AZURE_CONDITIONAL_NET_WEIGHT_ESTIMATE.json", azure_model)

items, allcards = [], []
for row in scopes:
    key, slug = row["key"], row["slug"]
    node = read(row["source_snapshots"]["node"]["path"])
    source = read(row["source_snapshots"]["original_review"]["path"])
    raw_current = props(node)
    raw_original = source.get("specification_review_items", source.get("specifications"))
    current, original = fields(raw_current), fields(raw_original)
    assert row["identity_kept"] and node.get("identity_confirmed")
    assert not node.get("specifications_approved") and not node.get("specification_fields_fully_approved")
    primary, folder = row["primary_file_id"], row["folder_id"]
    assert heads[primary]["path_display"].rsplit("/", 1)[0] == heads[folder]["path_display"]
    if row["scope"] == "BASE":
        kind, idkey, scopeid = "source_component_record", "base_scope", "BASE"
    elif row["component_id"] == "UGR-G310":
        kind, idkey, scopeid = "whole_source_review", "source_design_key", row["scope"]
    else:
        idkey = next(k for k in ["size_finish_variant_id", "build_variant_id", "component_layout_id"] if node.get(k))
        kind = {"size_finish_variant_id": "size_finish_variants", "build_variant_id": "build_variants", "component_layout_id": "component_layouts"}[idkey]
        scopeid = node[idkey]
        assert scopeid == row["scope"]
    scope_identity = {"component_id": row["component_id"], idkey: scopeid, "scope_key": key}
    selected_contexts = []
    for x in row["selected_contexts"]:
        m = media[x["file_id"]]
        f = m["source_asset"]["folder_id"]
        assert heads[x["file_id"]]["path_display"].rsplit("/", 1)[0] == heads[f]["path_display"]
        if x["file_id"] not in {v["file_id"] for v in selected_contexts}:
            selected_contexts.append({"file_id": x["file_id"], "folder_id": f, "image_url": image_url(x["file_id"]),
                                      "folder_url": folder_url(f), "historical_role": x["role"],
                                      "inspection_representation": m["media_type"], "same_physical_cast_verified": False})
    primary_context = row["scope"] in ["MSW-HALF-MOON-BLACK-WHITE", "MSW-SHELLWAVE-WHITE-WATER-FEATURE"] or row["component_id"] in ["BC-RIYADH-1", "BC-RIYADH-2"]
    historical_photo = {k: deepcopy(source[k]) for k in source if any(t in k for t in ["photo", "coverage", "media_review", "arrangement"])}
    context = {
        "selected_context_available": bool(selected_contexts) or primary_context,
        "selected_context_images": selected_contexts, "primary_is_context_scene": primary_context,
        "primary_is_cropped_detail": row["component_id"] == "BC-BONE-WATER",
        "isolated_front_not_established": row["scope"] == "MSW-HALF-MOON-BLACK-WHITE",
        "primary_inspection_representation": media[primary]["media_type"],
        "visual_observation": observations[key], "historical_photo_evidence_retained": historical_photo,
        "historical_context_not_newly_rechecked": row["component_id"] in ["BC-BONE-WATER", "BC-MOON-WATER", "BC-MOONWAVE", "BC-SM-QUARTER"],
        "exact_cast_linked_rear_hardware_established_this_pass": False,
        "calibrated_profile_or_depth_established_this_pass": False,
        "same_physical_cast_verified": False, "scene_provenance_verified": False, "actual_installation_verified": False,
        "new_group_scene_components_identified": 0, "complete_folder_census_performed": False,
        "scope_limit": "Selected existing files only; absence from these selected images is not a claim that no other folder photograph exists.",
    }
    context_ref = stage(slug + "/CONTEXT_OUTPUT_UPDATE.json", {
        "schema": "boldstone.reviewed-context-output-update.v1", "checked_utc": NOW, **scope_identity,
        "canonical_name": row["canonical_name"], "context_images": context,
        "source_missing_photographs": deepcopy(node.get("missing_photographs", source.get("missing_photographs", source.get("photo_gaps")))),
        "source_missing_specifications": deepcopy(node.get("missing_specifications", source.get("missing_specifications", source.get("other_missing_details")))),
        "current_unresolved_photo_requests": [
            "Exact cast-linked rear/hardware and attachment view, if not already paired in historical evidence.",
            "Calibrated profile/depth view of the exact artwork.",
        ] + (["Complete isolated front of the existing named sculpture."] if context["isolated_front_not_established"] or context["primary_is_cropped_detail"] else []),
        "owner_output_requirement": "Flag contextual sculpture images and retain their links. Group scenes do not require new individual component identification.",
        "current_reference": current_ref, "visual_inspection": visual_ref,
        "new_name_or_specification_approvals": 0, "new_BC_component_ids": [], "shared_master_writes": False,
    })
    prepared = {}
    for field in FIELDS:
        old = current[field]
        display = old.get("display", old.get("proposal", ""))
        assert isinstance(display, str) and display
        status = old.get("status", "HISTORICAL_SOURCE_CLAIM_OR_PROPOSAL; ACTUAL_VALUE_UNVERIFIED")
        basis = old.get("basis") or "Retain the complete historical source dictionary and its source claims, proposals, conflicts and unknowns."
        prepared[field] = {
            "id": key + ":B96:" + field, "proposal_id": key + ":B96:" + field,
            "field": field, "group": GROUPS[field], "display": display,
            "source_qualification": status,
            "value": deepcopy(old.get("value", old.get("complete_original_source_specification"))),
            "basis": basis, "source_refs": list(row["source_snapshots"].values()),
            "source_original_field_retained": deepcopy(original[field]), "source_current_field_retained": deepcopy(old),
            "status": "PREPARED_LABELLED_WORKING_SPECIFICATION; ACTUAL_VALUES_UNVERIFIED",
            "owner_accepted": False, "owner_approved": False, "physical_specs_verified": False,
            "physical_value_verified": False, "independently_measured_or_certified": False,
        }
    # Preserve all applicable current weight displays exactly; Azure needs a separate net estimate.
    prepared["weight"].update(approximate_weight_policy_id=policy["weight"]["policy_id"],
                              existing_weight_display_retained_exactly=row["component_id"] != "BC-AZURE")
    prepared["weight"]["source_refs"].append(discovery["policies"]["weight"])
    prepared["fixing"].update(
        display="Choice of keyhole fixing / French cleat — owner instruction. Actual installed hardware, count, attachment and load rating remain unconfirmed for this piece.",
        value={"offered_options": ["Keyhole fixing", "French cleat"], "offered_choice_owner_confirmed": True,
               "actual_fitted_type": None, "actual_fitted_count": None, "rated_load": None,
               "historical_source_hardware_claims_retained": deepcopy(current["fixing"]),
               "offered_choice_is_installed_confirmation": False},
        offered_fixing_choice_policy_id=policy["fixing"]["policy_id"])
    prepared["fixing"]["basis"] += " Policy87 supplies the catalogue choice. Historical source hardware claims remain separate and are not verified installed facts."
    prepared["fixing"]["source_refs"].append(discovery["policies"]["fixing"])
    prepared["individual_price"]["display"] = temporal(prepared["individual_price"]["display"])
    prepared["individual_price"]["basis"] += " Working price/source acceptance only. Prior captures retain their original dates; no current public price, physical stock or exact platform match was verified in this pass."
    prepared["availability"]["display"] = temporal(prepared["availability"]["display"])
    if row["scope"] == "MSW-HALF-MOON-BLACK-WHITE":
        prepared["availability"]["display"] = "Made to order / enquiry — working proposal; design physically made per owner policy51. Current stock, repeat-production readiness and lead time unknown."
    prepared["availability"]["basis"] += " Owner policy51 records that all sculpture designs have been physically made. Any prior manufacture-existence uncertainty is historical; current stock, reproducibility and lead time remain unknown."
    prepared["availability"]["source_refs"].append(discovery["policies"]["manufacture"])
    if key in corrections:
        prepared["dimensions"]["source_refs"].append(corrections[key])
        prepared["dimensions"]["owner_face_decision"] = corrections[key]
    if row["component_id"] == "BC-BONE-WATER":
        prepared["dimensions"]["display"] = "80 cm wide × 60 cm high — owner-accepted working version; approximately 5–8 cm deep — historical maker estimate, unmeasured."
        prepared["dimensions"]["basis"] += " Existing owner working-face approval supersedes the old request to select a size. The 55×55 and 110×55 source versions remain separate."
        prepared["dimensions"]["source_qualification"] = "OWNER_ACCEPTED_WORKING_FACE; DEPTH_ESTIMATED; SPECIMEN_UNMEASURED"
    if row["component_id"].startswith("BC-RIYADH-"):
        prepared["dimensions"]["display"] = "275 × 100 cm — historical project dimensions, mapping to this pictured panel provisional; approximately 5–7 cm depth — guess. Orientation and actual panel size unmeasured."
        for field in ["weight", "material_finish", "individual_price", "availability"]:
            prepared[field]["working_qualification"] = "Broad working guess/proposal; exact current artwork specifications or commercial terms not verified."
    if row["component_id"] == "UGR-G310":
        prepared["dimensions"]["display"] = "80 × 60 cm face — owner-stated; approximately 6 cm deep — working estimate, unmeasured."
        prepared["dimensions"]["source_qualification"] = "OWNER_STATED_FACE; DEPTH_WORKING_ESTIMATE"
        prepared["dimensions"]["basis"] += " Owner-stated 80×60 face supersedes the historical 60×60 brochure comparison; no new BC component is created."
    if row["component_id"] == "BC-AZURE":
        prepared["dimensions"]["display"] = "Artwork dimensions unconfirmed. Historical shipping fields convert to approximately 100 × 16 × 4 cm; these are not measured panel dimensions."
        prepared["weight"].update(
            display="Approximately 7 kg net; estimated range 4–10 kg — new low-confidence conditional guess. Historical shipping weight remains approximately 15 kg, separately recorded.",
            source_qualification=azure_model["confidence"], value=deepcopy(azure_model),
            basis=azure_model["calculation"] + " " + azure_model["limitations"],
            existing_approximation_retained=False, new_conditional_net_weight_estimate=azure_ref)
        prepared["weight"]["source_refs"].append(azure_ref)
    review = {
        "schema": "boldstone.prepared-working-specification-review.v1", "prepared_utc": NOW,
        "review_id": key + ":WORKING-SPECS-POLICY80:B96", **scope_identity, "variant_kind": kind,
        "canonical_name": row["canonical_name"], "source_snapshots": row["source_snapshots"],
        "existing_name_approval_preserved": True,
        "source_specification_proposals_retained": deepcopy(raw_original),
        "source_current_specification_proposals_retained": deepcopy(raw_current),
        "specifications": prepared, "primary_file_id": primary, "folder_id": folder,
        "image_url": image_url(primary), "folder_url": folder_url(folder),
        "current_reference": current_ref, "image_evidence": ref(B / "VISUAL_INDEX.json"), "visual_inspection": visual_ref,
        "context_images": context, "context_output_update": context_ref,
        "platform_mapping": deepcopy(node.get("platform_mapping", source.get("platform_mapping", {}))),
        "source_versions_retained": deepcopy(node.get("source_versions", source.get("source_versions"))),
        "source_scope_retained": deepcopy(source.get("scope", source.get("review_scope", node.get("scope")))),
        "owner_stated_manufacture": True, "owner_manufacture_policy": discovery["policies"]["manufacture"],
        "standing_working_specification_policy": discovery["policies"]["standing"], "policy_id": policy["standing"]["policy_id"],
        "offered_fixing_choice_policy": discovery["policies"]["fixing"], "offered_fixing_choice_policy_id": policy["fixing"]["policy_id"],
        "approximate_weight_policy": discovery["policies"]["weight"], "approximate_weight_policy_id": policy["weight"]["policy_id"],
        "owner_face_correction": corrections.get(key), "question_suppressed_under_standing_policy": True,
        "per_card_owner_reply_received": False, "new_identity_inferred": False,
        "shared_master_writes": False, "remote_mutations": 0, "new_private_original_downloads": 0,
    }
    review_ref = stage(slug + "/REVIEW.json", review)
    accepted = deepcopy(prepared)
    for field, value in accepted.items():
        value.update(status="OWNER_AUTHORIZED_WORKING_ACCEPTANCE; ESTIMATES_PROPOSALS_CONFLICTS_AND_UNKNOWNS_RETAINED",
                     owner_approved=True, owner_accepted=True, approval_basis="STANDING_OWNER_POLICY",
                     policy_id=policy["standing"]["policy_id"], owner_approval_scope="WORKING_SPECIFICATIONS_ONLY")
        if field == "weight":
            value["existing_approximation_accepted_under_weight_policy"] = row["component_id"] != "BC-AZURE"
            value["new_estimate_accepted_under_weight_policy"] = row["component_id"] == "BC-AZURE"
        if field == "individual_price":
            value["owner_working_price_accepted"] = True
            value["current_public_selling_price_verified"] = False
    decision = {
        **review, "schema": "boldstone.owner-scoped-working-specifications-keep.v1",
        "decision_id": key + ":WORKING-SPECS:POLICY80", "recorded_utc": NOW, "owner_session": LANE,
        "status": "WORKING_SPECIFICATIONS_ACCEPTED_UNDER_OWNER_STANDING_POLICY",
        "approval_basis": "STANDING_OWNER_POLICY", "prepared_review": review_ref, "source_review_before_answer": review_ref,
        "authoritative_user_evidence": policy["standing"]["authoritative_user_evidence"],
        "user_statement": policy["standing"]["user_statement"],
        "per_card_owner_reply_received": False, "synthetic_owner_reply_created": False,
        "source_specifications_retained": prepared, "specifications": accepted,
        "specification_review_items": list(accepted.values()),
        "approved_proposal_ids": [v["proposal_id"] for v in accepted.values()], "approved_field_groups": FIELDS,
        "all_six_owner_specification_fields_accepted": True, "specifications_approved": True, "proposals_approved": True,
        "owner_estimates_accepted": True, "source_claims_accepted_as_working": True,
        "physical_specs_verified": False, "independently_measured_or_certified": False, "actual_stock_verified": False,
        "estimate_and_proposal_labels_retained": True, "source_conflicts_and_unknowns_retained": True,
        "image_link": image_url(primary), "folder_link": folder_url(folder),
        "manufacture_question_required": False, "offered_fixing_choice_not_installed_hardware_confirmation": True,
        "existing_approximate_weight_retained": row["component_id"] != "BC-AZURE",
        "new_name_approvals": 0, "new_specification_approvals": 1, "new_approved_field_groups": 6,
        "new_owner_approval_events": 0, "new_owner_policy_events": 0, "new_BC_component_ids": [],
        "new_design_mould_or_stock_counts": 0, "shared_master_import_performed": False, "shared_master_writes_by_lane": False,
    }
    decision_ref = stage(slug + "/SPECIFICATION_APPROVAL.json", decision)
    items.append({**scope_identity, "variant": scopeid, "variant_kind": kind, "id_key": idkey,
                  "target": str(B / slug), "decision": decision_ref, "prepared_review": review_ref,
                  "context": context_ref, "source_snapshots": row["source_snapshots"]})
    allcards.append(decision)

index = {
    "schema": "boldstone.prepared-bulk-working-review-index.v1",
    "status": "PREPARED_AWAITING_INDEPENDENT_LOCAL_VERIFICATION", "created_utc": NOW, "reserved_batch": 96,
    "source_owner_session": LANE, "shared_writer_session": ROOT,
    "allocation": discovery["allocation"], "allocation_addendum": discovery["allocation_addendum"],
    "owner_continue_all_evidence": owner_continue, "items": items,
    "new_specification_approvals": 40, "new_approved_field_groups": 240,
    "existing_applicable_weight_displays_retained": 39, "new_conditional_net_weight_estimates": 1,
    "new_owner_policy_events": 0, "new_owner_approval_events": 0, "new_name_approvals": 0,
    "new_BC_component_ids": [], "shared_master_writes_by_lane": False, "remote_mutations": 0,
}
stage("PREPARED_PACKAGE_INDEX.json", index)
stage("REVIEW_CARDS.json", {"created_utc": NOW, "status": "WORKING_ACCEPTANCE_PREPARED_PENDING_SHARED_IMPORT",
                          "entries": allcards, "scope_count": 40, "field_count": 240,
                          "link_access": "Existing authenticated Dropbox home/preview references; no new public shared links."})

# A local review document, with all six fields and the required image/folder links.
e = html.escape
cards = []
labels = dict(zip(FIELDS, ["Dimensions", "Weight", "Material / finish", "Fixing", "Individual price", "Availability"]))
for card in allcards:
    rows = []
    for field in FIELDS:
        value = card["specifications"][field]
        rows.append("<tr><th>" + e(labels[field]) + "</th><td>" + e(clean(value["display"])) +
                    "<details><summary>Source qualification and basis</summary><p>" + e(value["source_qualification"]) +
                    "</p><p>" + e(value["basis"]) + "</p></details></td></tr>")
    context = card["context_images"]
    links = " · ".join('<a href="' + e(x["image_url"], quote=True) + '">Context image ' + str(i+1) + "</a>"
                       for i, x in enumerate(context["selected_context_images"]))
    contextlabel = "Contextual image available" if context["selected_context_available"] else "See historical coverage; no additional context selected in this pass"
    cards.append('<article id="' + e(card["scope_key"].replace("|", "--")) + '"><h2>' + e(card["canonical_name"]) +
                 '</h2><p><a href="' + e(card["image_url"], quote=True) + '">Individual / reference image</a> · <a href="' +
                 e(card["folder_url"], quote=True) + '">Containing folder</a></p><table>' + "".join(rows) +
                 "</table><p><strong>" + e(contextlabel) + ".</strong> " + e(context["visual_observation"]) +
                 "</p><p>" + links + "</p><p class=\"small\">Rear hardware and calibrated depth remain unresolved for the exact cast. " +
                 e(context["scope_limit"]) + "</p></article>")
page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Boldstone — 40 remaining working reviews</title><style>
body{font:16px/1.5 system-ui,sans-serif;color:#202925;background:#f3f3ef;margin:0}
main{max-width:1000px;margin:auto;padding:32px 20px}h1{line-height:1.15}h2{font-size:1.35rem}
article{background:white;padding:24px;margin:28px 0;border:1px solid #d6ddd7;border-radius:8px}
table{border-collapse:collapse;width:100%}th,td{padding:12px;vertical-align:top;text-align:left;border-top:1px solid #dde3df}
th{width:23%}a{color:#165d57}summary{cursor:pointer;color:#53605b;font-size:.87rem;margin-top:7px}
details p,.small{font-size:.88rem;color:#52605b}input{width:100%;box-sizing:border-box;padding:12px;font:inherit}
@media print{body{background:white}article{break-inside:avoid}input{display:none}}
</style><main><h1>Boldstone: 40 remaining working reviews</h1>
<p>Prepared on 20 October 2026 under your standing approvals. All six fields are accepted as working details;
estimates, source conflicts and unknowns remain labelled. This document is the isolated batch prepared for the catalogue coordinator.</p>
<p>All sculptures offer keyhole fixing / French cleat. Existing hardware claims remain historical.
Prices and stock references are historical captures or proposals, not newly checked offers.
Dropbox links open the existing account files; no public links were created.</p>
<p>39 existing weight displays are preserved. Azure has a new conditional 7 kg net estimate (4–10 kg); its approximately 15 kg shipping record remains separate.</p>
<label for="search">Find a sculpture</label><input id="search" type="search" placeholder="Name or specification">
<p id="count">40 entries</p>""" + "".join(cards) + """</main><script>
const input=document.getElementById('search'),cards=[...document.querySelectorAll('article')];
input.addEventListener('input',()=>{let n=0;const q=input.value.toLowerCase();for(const c of cards){c.hidden=!c.textContent.toLowerCase().includes(q);if(!c.hidden)n++}document.getElementById('count').textContent=n+' entries'});
</script></html>"""
html_path = B / "REVIEW_CARDS.html"
assert not html_path.exists()
OUT[html_path] = page.encode()
for p in OUT:
    assert not p.exists(), p
for p, data in OUT.items():
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
print(json.dumps({"prepared_scopes": 40, "prepared_field_groups": 240, "files_created": len(OUT),
                  "existing_weight_displays_retained": 39, "new_conditional_net_weight_estimates": 1}))
