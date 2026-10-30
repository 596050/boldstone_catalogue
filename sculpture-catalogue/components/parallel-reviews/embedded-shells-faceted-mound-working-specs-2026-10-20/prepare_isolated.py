"""Prepare two existing identities under the owner's standing working policy.

Writes only to this isolated lane. Shared import belongs to the coordinator.
"""
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
if (BASE / "CACHED_IMAGE_BINDING.json").exists():
    NOW = json.loads((BASE / "CACHED_IMAGE_BINDING.json").read_text())["checked_utc"]
FIELDS = ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"]
LABELS = ["Dimensions / depth", "Weight", "Material / finish", "Fixing", "Individual price", "Availability"]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return {"path": str(path), "sha256": sha(path)}


def save(path, data):
    assert path.is_relative_to(BASE)
    if path.exists():
        assert read(path) == data, f"Refusing to overwrite different evidence: {path}"
        return ref(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return ref(path)


def copy(source, dest):
    assert dest.is_relative_to(BASE)
    if dest.exists():
        assert sha(dest) == sha(source), f"Existing source snapshot differs: {dest}"
        return ref(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    assert sha(dest) == sha(source)
    return ref(dest)


def dbhash(blob):
    return hashlib.sha256(b"".join(
        hashlib.sha256(blob[i:i + 4194304]).digest()
        for i in range(0, len(blob), 4194304)
    )).hexdigest()


current = read(BASE / "CURRENT_REFERENCE_READBACK.json")
metadata = {
    x["request_id"]: x[x["metadata_type"]] for x in current["metadata"]
}
listings = {x["key"]: x for x in current["listings"]}
shared = read(REV / "user_classifications.json")
canonical_path = REV / "parallel-import-2026-10-19-batch80/standing-working-acceptance-policy.json"
canonical = read(canonical_path)
policy_ref = copy(canonical_path, BASE / "CANONICAL_STANDING_POLICY.json")
own_path = CAT / "components/parallel-reviews/fountain-palm-mediterranean-white-working-specs-2026-10-20/owner-working-specs-policy/OWNER_POLICY.json"
assert sha(own_path) == "690429d8014b559851688b2b320f45a4a4e72060b288436a4464b550ff00223a"
own_ref = copy(own_path, BASE / "OWNER_STANDING_POLICY.json")
assert canonical["policy_id"] == "WORKING-SPECIFICATION-AFFIRMATIVE-POLICY:01a13fbf-1cbc-7511-8416-cf339051083e:LINE18928"
assert canonical["repeat_working_specification_confirmation_questions_required"] is False
assert len(shared["working_specification_acceptance_policy_decisions"]) == 1
owner_evidence = canonical["authoritative_user_evidence"]
owner_raw = Path(owner_evidence.get("transcript", owner_evidence.get("transcript_path"))).read_bytes().splitlines(keepends=True)[owner_evidence["line"] - 1]
if not owner_evidence.get("source_raw_line_digest_includes_line_ending"):
    owner_raw = owner_raw.rstrip(b"\r\n")
assert hashlib.sha256(owner_raw).hexdigest() == owner_evidence["raw_line_sha256"]
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
for line, raw in enumerate(transcript.read_bytes().splitlines(), 1):
    event = json.loads(raw)
    p = event.get("payload", {})
    output = p.get("output", "")
    if p.get("type") == "function_call_output" and isinstance(output, str) and (
        "<source_thread_id>" + ROOT + "</source_thread_id>" in output
        and "Next disjoint B batch85 reserved" in output
    ):
        allocations.append({
            "transcript": str(transcript), "line": line,
            "timestamp": event.get("timestamp"),
            "raw_line_sha256": hashlib.sha256(raw).hexdigest(),
            "source_raw_line_digest_includes_line_ending": False,
            "coordinator_thread_id": ROOT, "text": output,
            "is_owner_reply": False,
        })
assert allocations
save(BASE / "COORDINATOR_ALLOCATION.json", allocations[-1])


def file_link(fid):
    m = metadata[fid]
    parent = m["path_display"].rsplit("/", 1)[0]
    return "https://www.dropbox.com/home" + quote(parent, safe="/") + "?preview=" + quote(m["name"], safe="")


def folder_link(fid):
    return "https://www.dropbox.com/home" + quote(metadata[fid]["path_display"], safe="/")


image_checks = []
for name, prefix in [("embedded-shells", "embedded"), ("faceted-mound", "faceted")]:
    historic = REV / (name + "-review-2026-10-18")
    old = read(historic / "metadata-links.json")
    oldmeta = {x["request_id"]: x[x["metadata_type"]] for x in old["metadata"]}
    for listing in old["listings"]:
        fresh = listings[prefix + "-" + listing["key"]]
        norm = lambda entries: sorted((x["file_id"], x["name"], x["file"].get("size", 0)) for x in entries)
        assert not fresh["has_more"] and not fresh["cursor"]
        assert norm(listing["entries"]) == norm(fresh["entries"])
    previews = read(historic / "image-review-index.json")["cached_previews"]
    for preview in previews:
        path = Path(preview["preview_path"])
        assert sha(path) == preview["sha256"] and path.stat().st_size == preview["bytes"]
    originals = []
    for item in read(historic / "download-receipts.json"):
        path = Path(item["local_path"])
        data = path.read_bytes()
        assert sha(path) == item["sha256"] and len(data) == item["size"]
        assert dbhash(data) == item["content_hash"] == item["dropbox_content_hash_verified"]
        fresh, prior = metadata[item["id"]], oldmeta[item["id"]]
        assert fresh["rev"] == prior["rev"] and fresh["size"] == len(data)
        originals.append({
            "file_id": item["id"], **ref(path), "bytes": len(data),
            "dropbox_content_hash": dbhash(data), "current_rev": fresh["rev"],
            "cached_original_viewed_this_turn": True, "new_private_download": False,
        })
    audit = read(historic / "source-audit.json")
    contact = historic / "file-review.jpg"
    assert audit["evidence_sha256"][str(contact)] == sha(contact)
    image_checks.append({
        "design": name, "complete_current_file_count": len(previews),
        "complete_current_census_matches_historical_ids_names_sizes": True,
        "cached_previews_all_hashed_and_viewed_on_contact_sheet": True,
        "contact_sheet": ref(contact), "preview_bindings": previews,
        "cached_originals": originals,
        "other_original_bytes_reverified_this_turn": False,
        "finished_rear_or_calibrated_measurement_found_in_reviewed_scope": False,
        "other_folders_not_asserted_exhaustive": True,
        "same_cast_scene_provenance_or_installation_certified": False,
        "group_scenes_decomposed_into_new_components": False,
    })
image_ref = save(BASE / "CACHED_IMAGE_BINDING.json", {
    "schema": "boldstone.cached-image-current-binding.v1", "checked_utc": NOW,
    "designs": image_checks, "cached_previews_viewed": 20,
    "cached_originals_rehashed_and_viewed": 6, "new_private_original_downloads": 0,
})

packages = []
batch_checks = {}
for name, cid, vid, cname in [
    ("embedded-shells", "BC-EMBED-SHELLS", "EMBED-SHELLS-WHITE", "Embedded Shells — White"),
    ("faceted-mound", "BC-FACET-MOUND", "FACET-MOUND-GOLD-LEAF", "Faceted Mound — Gold Leaf"),
]:
    historic = REV / (name + "-review-2026-10-18")
    target = BASE / name
    original_ref = copy(historic / "component-review.json", target / "ORIGINAL_SOURCE_REVIEW.json")
    source_name = "component-review.after-dimensions.json" if name == "embedded-shells" else "component-review.json"
    source_ref = copy(historic / source_name, target / "SOURCE_REVIEW_AT_ALLOCATION.json")
    source = read(Path(source_ref["path"]))
    original = read(Path(original_ref["path"]))
    identity_ref = copy(historic / "identity-approval.json", target / "EXISTING_NAME_APPROVAL.json")
    identity = read(Path(identity_ref["path"]))
    assert identity["component_id"] == cid and identity["size_finish_variant_id"] == vid
    assert sum(x.get("decision_id") == identity["decision_id"] for x in shared["decisions"]) == 1
    shared_identity = next(x for x in shared["decisions"] if x.get("decision_id") == identity["decision_id"])
    assert {k: v for k, v in shared_identity.items() if k != "approval_record"} == identity
    assert shared_identity["approval_record"] == str((historic / "identity-approval.json").relative_to(CAT))
    assert not any(x.get("size_finish_variant_id") == vid for x in shared["size_finish_variant_specification_decisions"])
    additions = {}
    if name == "embedded-shells":
        dimension_ref = copy(historic / "user-face-dimensions-70x15.json", target / "EXISTING_OWNER_FACE_DIMENSIONS.json")
        supplement_ref = copy(historic / "dimension-revision-supplement.json", target / "HISTORICAL_DIMENSION_REVISION.json")
        dimension = read(Path(dimension_ref["path"]))
        shared_dimension = next(x for x in shared["dimension_decisions"] if x.get("decision_id") == dimension["decision_id"])
        assert {k: v for k, v in shared_dimension.items() if k != "approval_record"} == dimension
        assert shared_dimension["approval_record"] == str((historic / "user-face-dimensions-70x15.json").relative_to(CAT))
        assert dimension["confirmed_dimensions_cm"] == {"height": 70, "width": 15, "depth": None}
        retail = CAT / "components/evidence/price-source-review-2026-10-17/Retail PRICE List 2025.docx.txt"
        assert sha(retail) == "9e0f672dffd6193c5554d78facc9ec67d14de4112fcf93ee78230305a60c7313"
        additions.update(existing_owner_face_dimensions=dimension_ref, historical_dimension_revision=supplement_ref, dated_price_analogy_source=ref(retail))
    else:
        additions["historical_other_design_price_analogies"] = copy(historic / "other-design-analogy-sources.json", target / "HISTORICAL_OTHER_DESIGN_ANALOGIES.json")

    prepared = {}
    for key, label, raw in zip(FIELDS, LABELS, source["specification_review_items"]):
        item = deepcopy(raw)
        item.update(id=item["proposal_id"], field=label, owner_accepted=False, physical_value_verified=False)
        if key == "availability":
            item["source_basis_before_manufacture_policy_overlay"] = item["basis"]
            item["basis"] = "The owner-wide policy confirms that this sculpture was physically made. It does not confirm current cast stock, a usable mould, repeatable production or delivery time. Made to order / enquire is a working sale-policy proposal."
        prepared[key] = item
    if name == "embedded-shells":
        prepared["dimensions"]["display"] = "70 H × 15 W cm — owner-stated face size; depth 5–7 cm is a working guess, unmeasured"
        prepared["individual_price"]["display"] = "£250–£350 per panel — working price-range proposal; no exact existing offer confirmed"
    else:
        prepared["individual_price"]["display"] = "£500–£800 per panel — working price-range proposal; no exact existing offer confirmed"
    primary, folder = source["primary_image_id"], source["primary_folder_id"]
    context_id, context_folder = source["context_image_id"], source["context_folder_id"]
    alternate = source.get("historical_brick_wall_image_id", source.get("alternate_setting_image_id"))
    context = {
        "status": "AVAILABLE_ROOM_AND_OUTDOOR_WALL_CONTEXT" if name == "embedded-shells" else "AVAILABLE_ROOM_CONTEXT",
        "type": "Indoor room presentation and historical brick-wall photographs" if name == "embedded-shells" else "Seven indoor room presentations",
        "image_url": file_link(context_id), "folder_url": folder_link(context_folder),
        "representative_file_id": context_id, "representative_folder_id": context_folder,
        "limitations": (
            "Complete 12-file census: one individual and eleven contextual views. All cached previews and three cached originals inspected. Indoor presentation and historical brick-wall imagery are available; scene provenance, actual installation and same physical cast are unverified. No finished rear, fixing detail, calibrated profile or separate series arrangement found in these folders. Elsewhere unknown. Other sculptures in the room remain contextual."
            if name == "embedded-shells" else
            "Complete 8-file census: one individual and seven room presentations. All cached previews and three cached originals inspected. Different apparent scales do not establish dimensions; actual installation, scene provenance and same physical cast are unverified. No finished rear, fixing detail, calibrated profile or separate series arrangement found in these folders. Elsewhere unknown."
        ),
        "individual_wider_room_available": True, "rear_reference_established": False,
        "series_relationship_established": False, "scene_provenance_verified": False,
        "actual_installation_verified": False, "same_physical_cast_verified": False,
        "new_sculpture_count": 0, "source_binding": image_ref,
        "additional_references": [{
            "type": "historical_brick_wall" if name == "embedded-shells" else "alternate_room_presentation",
            "file_id": alternate, "folder_id": context_folder,
            "image_url": file_link(alternate), "folder_url": folder_link(context_folder),
        }],
    }
    context_ref = save(target / "CONTEXT_OUTPUT_UPDATE.json", {
        "schema": "boldstone.reviewed-context-output-update.v1", "checked_utc": NOW,
        "component_id": cid, "size_finish_variant_id": vid, "canonical_name": cname,
        "context_images": context, "owner_output_requirement": "Mark contextual-image availability and limitations in the ultimate catalogue. Keep other sculptures in group scenes as context.",
        "new_name_or_specification_approvals": 0, "new_BC_component_ids": [],
        "shared_master_writes": False, "remote_mutations": 0,
    })
    review = {
        "schema": "boldstone.prepared-working-specification-review.v1",
        "prepared_utc": NOW, "review_id": vid + "-WORKING-SPECS-POLICY-01",
        "component_id": cid, "size_finish_variant_id": vid, "canonical_name": cname,
        "existing_name_approval": identity_ref, "existing_name_approval_preserved": True,
        "source_review": source_ref, "original_historical_source_review": original_ref,
        "source_specification_proposals_retained": original["specification_review_items"],
        "revised_source_specification_proposals_retained": source["specification_review_items"],
        "specifications": prepared,
        "primary_file_id": primary, "folder_id": folder,
        "image_url": file_link(primary), "folder_url": folder_link(folder),
        "current_reference": ref(BASE / "CURRENT_REFERENCE_READBACK.json"),
        "image_evidence": image_ref, "context_images": context, "context_output_update": context_ref,
        "platform_mapping": source["platform_mapping"],
        "owner_stated_manufacture": True, "owner_manufacture_policy": manufacture,
        "standing_working_specification_policy": policy_ref,
        "corroborating_owner_policy": own_ref, "policy_id": canonical["policy_id"],
        "question_suppressed_under_standing_policy": True,
        "per_card_owner_reply_received": False, "new_identity_inferred": False,
        "shared_master_writes": False, "remote_mutations": 0, **additions,
    }
    review_ref = save(target / "REVIEW.json", review)
    accepted = deepcopy(prepared)
    for key, item in accepted.items():
        item["source_status_before_policy_acceptance"] = item["status"]
        item.update(
            status="OWNER_AUTHORIZED_WORKING_ACCEPTANCE_UNDER_STANDING_POLICY; ESTIMATES_AND_UNKNOWNS_RETAINED",
            owner_approved=True, owner_accepted=True, physical_specs_verified=False,
            physical_value_verified=False, approval_basis="STANDING_OWNER_POLICY",
            policy_id=canonical["policy_id"],
            owner_approval_scope="WORKING_SPECIFICATIONS_WITH_SOURCE_CLAIMS_ESTIMATES_CONFLICTS_AND_UNKNOWNS_RETAINED",
        )
        if key == "individual_price":
            item["value"]["owner_price_approved"] = True
            item["value"]["owner_price_approval_scope"] = "WORKING_RANGE_ONLY; NOT_A_CONFIRMED_SELLING_PRICE"
            item["owner_working_price_accepted"] = True
            item["current_public_selling_price_verified"] = False
        if key == "dimensions" and name == "embedded-shells":
            item["status"] = "OWNER_STATED_FACE_70X15_CM; DEPTH_ESTIMATE_ACCEPTED_UNDER_STANDING_POLICY; NOT_PHYSICALLY_VERIFIED"
    decision = {
        "schema": "boldstone.owner-finish-working-specifications-keep.v1",
        "decision_id": cid + ":" + vid + ":WORKING-SPECS:POLICY80",
        "recorded_utc": NOW, "owner_session": LANE, "review_id": review["review_id"],
        "component_id": cid, "size_finish_variant_id": vid, "canonical_name": cname,
        "action": "accept six labelled working specifications under standing owner affirmative policy",
        "status": "WORKING_SPECIFICATIONS_ACCEPTED_UNDER_OWNER_STANDING_POLICY",
        "approval_basis": "STANDING_OWNER_POLICY",
        "standing_working_specification_policy": policy_ref,
        "corroborating_owner_policy": own_ref, "policy_id": canonical["policy_id"],
        "authoritative_user_evidence": owner_evidence,
        "user_statement": canonical["user_statement"],
        "per_card_owner_reply_received": False, "synthetic_owner_reply_created": False,
        "prepared_review": review_ref, "source_review_before_answer": review_ref,
        "source_review": source_ref, "original_historical_source_review": original_ref,
        "source_specifications_retained": prepared,
        "source_specification_proposals_retained": original["specification_review_items"],
        "revised_source_specification_proposals_retained": source["specification_review_items"],
        "specifications": accepted, "specification_review_items": list(accepted.values()),
        "approved_proposal_ids": [x["proposal_id"] for x in accepted.values()],
        "approved_field_groups": FIELDS,
        "all_six_owner_specification_fields_accepted": True,
        "specifications_approved": True, "proposals_approved": True,
        "owner_estimates_accepted": True, "source_claims_accepted_as_working": True,
        "physical_specs_verified": False, "independently_measured_or_certified": False,
        "actual_stock_verified": False, "estimate_and_proposal_labels_retained": True,
        "source_conflicts_and_unknowns_retained": True,
        "primary_file_id": primary, "folder_id": folder,
        "image_link": file_link(primary), "folder_link": folder_link(folder),
        "current_reference": review["current_reference"], "image_evidence": image_ref,
        "context_images": context, "context_output_update": context_ref,
        "platform_mapping": source["platform_mapping"],
        "existing_name_approval_preserved": True, "existing_name_approval": identity_ref,
        "owner_stated_manufacture": True, "owner_manufacture_policy": manufacture,
        "manufacture_question_required": False,
        "scope": "Existing " + cname + " only. Preserve owner-stated face size where present, conditional estimates and source attribution. No unknown material, actual weight, fixing load, stock, lead time, platform match or installation provenance is certified. No MCP4 commercial or 4kg information is transferred.",
        "new_name_approvals": 0, "new_specification_approvals": 1,
        "new_owner_approval_events": 0, "new_owner_policy_events": 0,
        "new_approved_field_groups": 6, "new_BC_component_ids": [],
        "new_design_mould_or_stock_counts": 0,
        "shared_master_import_performed": False, "shared_master_writes_by_lane": False,
        "remote_mutations": 0, "fresh_private_original_downloads": 0, **additions,
    }
    decision_ref = save(target / "SPECIFICATION_APPROVAL.json", decision)
    save(target / "WORKING_STATE.json", {
        "status": "WORKING_SPECIFICATIONS_ACCEPTED_UNDER_STANDING_POLICY_PENDING_SHARED_IMPORT",
        "updated_utc": NOW, "component_id": cid, "size_finish_variant_id": vid,
        "canonical_name": cname, "active_review_id": None,
        "closed_review_id": review["review_id"], "decision": decision_ref,
        "specifications": accepted, "policy_id": canonical["policy_id"],
        "routine_keep_question_required": False, "workbook_publication_pending": True,
        "physical_specs_verified": False, "actual_stock_verified": False,
    })
    save(target / "OWNERSHIP.json", {
        "owner_session": LANE, "shared_writer_session": ROOT,
        "component_id": cid, "size_finish_variant_id": vid,
        "allocation": ref(BASE / "COORDINATOR_ALLOCATION.json"),
        "status": "PREPARED_POLICY_ACCEPTANCE_PENDING_SHARED_IMPORT",
        "decision": decision_ref, "active_review_id": None,
        "shared_master_writes_by_lane": False, "remote_mutations": 0,
    })
    packages.append({
        "variant": vid, "component_id": cid, "target": str(target),
        "decision": decision_ref, "prepared_review": review_ref,
        "context_output_update": context_ref,
    })
save(BASE / "PREPARED_PACKAGE_INDEX.json", {
    "created_utc": NOW, "status": "PREPARED_AWAITING_INDEPENDENT_LOCAL_VERIFICATION",
    "items": packages, "new_specification_approvals": 2, "new_approved_field_groups": 12,
    "new_owner_policy_events": 0, "new_owner_approval_events": 0,
    "shared_master_writes_by_lane": False, "remote_mutations": 0,
})
print(json.dumps({"status": "PREPARED", "variants": [x["variant"] for x in packages]}))
