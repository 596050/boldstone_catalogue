"""Read saved batch88 evidence independently, then seal import artefacts."""
from pathlib import Path
from copy import deepcopy
from urllib.parse import unquote, urlparse, parse_qs
import datetime
import hashlib
import json

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
REV = CAT / "components/reviews"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
FIELDS = ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"]
LANE = "01a13fe6-495b-7253-b923-31823b4cbca8"
ROOT = "01a144ab-1a7c-7223-a403-73a4d53d70ff"


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


def write(p, value):
    assert p.is_relative_to(BASE) and not p.exists(), p
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return ref(p)


def valid_refs(value):
    if isinstance(value, dict):
        if {"path", "sha256"} <= value.keys():
            assert sha(Path(value["path"])) == value["sha256"], value["path"]
        for v in value.values():
            valid_refs(v)
    elif isinstance(value, list):
        for v in value:
            valid_refs(v)


def owner_line(pol):
    ev = pol["authoritative_user_evidence"]
    p = Path(ev.get("transcript", ev.get("transcript_path")))
    raw = p.read_bytes().splitlines(keepends=True)[ev["line"] - 1]
    if not ev.get("source_raw_line_digest_includes_line_ending"):
        raw = raw.rstrip(b"\r\n")
    assert hashlib.sha256(raw).hexdigest() == ev["raw_line_sha256"]
    event = json.loads(raw)
    payload = event["payload"]
    assert payload["role"] == "user"
    text = "\n".join(c.get("text", "") for c in payload["content"])
    assert text == ev["text"] == pol["user_statement"]


def content_hash(blob):
    chunks = [hashlib.sha256(blob[i:i + 4194304]).digest()
              for i in range(0, len(blob), 4194304)]
    return hashlib.sha256(b"".join(chunks)).hexdigest()


def link_path(url):
    parsed = urlparse(url)
    path = unquote(parsed.path).removeprefix("/home")
    preview = parse_qs(parsed.query).get("preview")
    return path + "/" + preview[0] if preview else path


policy = read(BASE / "CANONICAL_STANDING_POLICY.json")
fixing_source = read(BASE / "GLOBAL_FIXING_CHOICE_POLICY.json")
canonical_fixing_path = REV / "parallel-import-2026-10-19-batch87/global-fixing-choice-policy.json"
canonical_fixing = read(canonical_fixing_path)
owner_line(policy)
owner_line(fixing_source)
owner_line(canonical_fixing)
assert canonical_fixing["policy_id"] == fixing_source["policy_id"]
assert canonical_fixing["offered_fixing_options"] == fixing_source["offered_fixing_options"]
assert read(REV / "parallel-import-2026-10-19-batch87/independent-readback.json")["status"] == "PASS"
allocation_path = REV / "parallel-allocation-2026-10-20-batches88-89.json"
allocation = read(allocation_path)
scoped = next(x for x in allocation["allocations"] if x["batch"] == 88)
assert scoped["owner_session"] == LANE
assert scoped["scopes"] == [["BC-AC-ONE", "AC-ONE-LEFT-SANDSTONE"], ["BC-AC-ONE", "AC-ONE-LEFT-PEWTER"]]
canonical_binding = write(BASE / "CANONICAL_FIXING_POLICY_BINDING.json", {
    "status": "PASS", "checked_utc": NOW,
    "source_policy": ref(BASE / "GLOBAL_FIXING_CHOICE_POLICY.json"),
    "canonical_shared_policy": ref(canonical_fixing_path),
    "canonical_policy_id": canonical_fixing["policy_id"],
    "root_import_readback": ref(REV / "parallel-import-2026-10-19-batch87/independent-readback.json"),
    "exact_owner_text_and_transcript_lines_verified": True,
    "same_single_global_policy_not_a_new_event": True,
    "canonical_allocation": ref(allocation_path),
    "offered_choice_not_installed_fact": True,
})

image_binding = read(BASE / "CACHED_IMAGE_BINDING.json")
current = read(BASE / "CURRENT_REFERENCE_READBACK.json")
heads = {v["request_id"]: v[v["metadata_type"]] for v in current["metadata"]}
census = current["listings"][0]
assert len(census["entries"]) == 3 and not census["has_more"] and not census["cursor"]
assert len(image_binding["bindings"]) == 4
for binding in image_binding["bindings"]:
    blob = Path(binding["path"]).read_bytes()
    head = heads[binding["file_id"]]
    assert hashlib.sha256(blob).hexdigest() == binding["sha256"]
    assert content_hash(blob) == binding["dropbox_content_hash"]
    assert len(blob) == binding["bytes"] == head["size"]
    assert binding["current_rev"] == head["rev"]
    assert binding["cached_original_viewed_this_turn"] and not binding["new_private_original_download"]
valid_refs(image_binding)

ledger = read(REV / "user_classifications.json")
all_checks = {}
packages = []
for sub, variant, primary in [
    ("sandstone", "AC-ONE-LEFT-SANDSTONE", "id:cnqzTNngPVsAAAAAAAudqw"),
    ("pewter", "AC-ONE-LEFT-PEWTER", "id:cnqzTNngPVsAAAAAAAufFw"),
]:
    directory = BASE / sub
    original = read(directory / "SOURCE_REVIEW_AT_ALLOCATION.json")
    identity = read(directory / "EXISTING_NAME_APPROVAL.json")
    review = read(directory / "REVIEW.json")
    decision = read(directory / "SPECIFICATION_APPROVAL.json")
    context = read(directory / "CONTEXT_OUTPUT_UPDATE.json")
    valid_refs(review)
    valid_refs(decision)
    original_fields = original["proposed_specifications_for_this_finish"]
    specs = decision["specifications"]
    checks = {}

    def check(name, condition):
        assert condition, (variant, name)
        checks[name] = "PASS"

    check("all_saved_source_and_evidence_hashes_match", True)
    check("allocated_existing_identity_preserved",
          decision["component_id"] == "BC-AC-ONE"
          and decision["size_finish_variant_id"] == identity["size_finish_variant_id"] == variant
          and decision["canonical_name"] == next(x["canonical_name"] for x in ledger["size_finish_variant_decisions"] if x.get("size_finish_variant_id") == variant))
    check("no_existing_working_acceptance_overwritten",
          not any(x.get("size_finish_variant_id") == variant for x in ledger["size_finish_variant_specification_decisions"]))
    check("six_unique_working_fields",
          list(specs) == FIELDS and decision["approved_field_groups"] == FIELDS
          and len(set(decision["approved_proposal_ids"])) == 6)
    check("original_six_finish_dictionaries_preserved",
          review["source_finish_specification_dictionary_retained"] == decision["source_finish_specification_dictionary_retained"] == original_fields)
    check("all_field_source_dictionaries_preserved",
          all(specs[k]["source_finish_field_retained"] == original_fields["fixings" if k == "fixing" else k] for k in FIELDS))
    check("canonical_standing_authority_not_synthetic_reply",
          decision["policy_id"] == policy["policy_id"]
          and not decision["per_card_owner_reply_received"]
          and not decision["synthetic_owner_reply_created"]
          and decision["new_owner_approval_events"] == decision["new_owner_policy_events"] == 0)
    check("all_six_working_acceptances_not_physical_certification",
          all(x["owner_accepted"] and not x["physical_value_verified"] and x["approval_basis"] == "STANDING_OWNER_POLICY" for x in specs.values())
          and not decision["physical_specs_verified"] and not decision["independently_measured_or_certified"])
    check("prepared_after_owner_policies",
          review["prepared_utc"] > policy["effective_from_utc"]
          and review["prepared_utc"] > canonical_fixing["effective_from_utc"])
    check("white_comparator_approval_not_transferred",
          not decision["white_approval_transferred_to_other_finishes"]
          and all("White" in specs[k]["basis"] for k in ["dimensions", "weight", "material_finish", "individual_price"]))
    check("dimensions_unmeasured_and_weight_unweighed",
          specs["dimensions"]["value"] == {"proposed_dimensions_cm": [30, 30, 6], "actual_measured_dimensions_cm": None}
          and specs["weight"]["value"]["proposed_weight_kg"] == 4
          and specs["weight"]["value"]["proposed_range_kg"] == [3, 5]
          and specs["weight"]["value"]["actual_weighed_kg"] is None)
    check("substrate_and_finish_chemistry_unconfirmed",
          specs["material_finish"]["value"]["actual_binder"] is None
          and specs["material_finish"]["value"]["actual_stone_or_metal_composition"] is None
          and "hypothesis" in specs["material_finish"]["display"])
    check("offered_options_from_one_global_policy",
          specs["fixing"]["value"]["offered_options"] == ["Keyhole fixing", "French cleat"]
          and decision["offered_fixing_choice_policy_id"] == canonical_fixing["policy_id"]
          and decision["offered_fixing_choice_not_installed_hardware_confirmation"])
    check("actual_fixing_type_count_and_load_unknown",
          all(specs["fixing"]["value"][k] is None for k in ["actual_fitted_type", "count", "hardware_material", "attachment", "rated_load"])
          and not specs["fixing"]["value"]["historical_proposal_is_installed_fact"])
    check("only_working_price_acceptance_changes_proposal_value",
          all(specs[k]["value"] == review["specifications"][k]["value"] for k in FIELDS if k != "individual_price")
          and {k: v for k, v in specs["individual_price"]["value"].items() if k not in ["owner_price_approved", "owner_price_approval_scope"]}
          == {k: v for k, v in review["specifications"]["individual_price"]["value"].items() if k != "owner_price_approved"})
    check("price_starting_proposal_surcharge_and_offer_unknown",
          specs["individual_price"]["value"]["proposed_starting_price_gbp"] == 175
          and specs["individual_price"]["value"]["finish_surcharge_gbp"] is None
          and not specs["individual_price"]["current_public_selling_price_verified"]
          and "historical comparison" in specs["individual_price"]["basis"])
    check("stock_reproduction_and_lead_time_unknown",
          all(specs["availability"]["value"][k] is None for k in ["physical_stock", "reproducibility", "lead_time"]))
    check("exact_platform_offer_unmatched",
          all(decision["platform_mapping"][k] is None for k in ["squarespace_id", "shopify_handle", "shared_sku"])
          and not decision["platform_mapping"]["live_platform_records_refreshed"])
    check("selected_originals_bound_to_fresh_current_metadata", len(image_binding["bindings"]) == 4)
    check("complete_three_file_census_with_no_broader_claim",
          len(census["entries"]) == 3 and image_binding["no_other_folder_completeness_asserted"])
    check("current_detail_and_folder_links_match_ids",
          decision["primary_file_id"] == primary
          and link_path(decision["image_link"]) == heads[primary]["path_display"]
          and link_path(decision["folder_link"]) == heads[decision["folder_id"]]["path_display"])
    check("group_context_bound_to_existing_target_position",
          context["context_images"] == decision["context_images"]
          and decision["context_images"]["target_position"] == original["target_position"]
          and decision["context_images"]["representative_file_id"] == "id:cnqzTNngPVsAAAAAAAuV6Q")
    check("partial_primary_whole_and_rear_photo_gaps_retained",
          "Cropped detail" in decision["primary_image_role"]
          and not decision["context_images"]["individual_complete_product_image_established"]
          and not decision["context_images"]["rear_reference_established"]
          and not decision["context_images"]["same_physical_cast_verified"])
    check("no_new_identity_manufacture_or_stock_counts",
          decision["new_name_approvals"] == decision["new_design_mould_or_stock_counts"] == 0
          and decision["new_BC_component_ids"] == []
          and decision["owner_stated_manufacture"] and not decision["manufacture_question_required"])
    check("no_shared_remote_writes_or_private_downloads",
          not decision["shared_master_writes_by_lane"]
          and decision["remote_mutations"] == decision["fresh_private_original_downloads"] == 0)
    qa = write(directory / "SEALED_PACKAGE_VERIFICATION.json", {
        "status": "PASS", "checked_utc": NOW, "check_count": len(checks),
        "checks": checks, "decision": ref(directory / "SPECIFICATION_APPROVAL.json"),
    })
    package = write(directory / "IMPORT_PACKAGE.json", {
        "schema": "boldstone.working-finish-specification-import.v1",
        "created_utc": NOW, "status": "READY_FOR_SOLE_WRITER_IMPORT",
        "reserved_batch": 88, "source_owner_session": LANE, "shared_writer_session": ROOT,
        "decision": ref(directory / "SPECIFICATION_APPROVAL.json"),
        "prepared_review": ref(directory / "REVIEW.json"),
        "owner_working_specification_policy": ref(BASE / "CANONICAL_STANDING_POLICY.json"),
        "offered_fixing_choice_policy": ref(BASE / "GLOBAL_FIXING_CHOICE_POLICY.json"),
        "canonical_offered_fixing_choice_binding": canonical_binding,
        "context_output_update": ref(directory / "CONTEXT_OUTPUT_UPDATE.json"),
        "verification": qa,
        "requested_import": "Six working fields for the existing kept finish under80, offered fixing choice under87. Preserve original six dictionaries, White-comparator estimate labels, historical price basis, unknown installed hardware and current offers, cropped primary photos and grouped context. No new owner reply or identity.",
        "new_name_approvals": 0, "new_specification_approvals": 1,
        "new_approved_field_groups": 6, "new_owner_policy_events": 0,
        "new_owner_approval_events": 0, "new_BC_component_ids": [],
        "shared_master_writes_by_lane": False, "remote_mutations": 0,
    })
    packages.append({
        "component_id": "BC-AC-ONE", "variant": variant, "package": package,
        "verification": qa, "context": ref(directory / "CONTEXT_OUTPUT_UPDATE.json"),
    })
    all_checks.update({variant + ":" + k: v for k, v in checks.items()})

batch_qa = write(BASE / "BATCH_VERIFICATION.json", {
    "status": "PASS", "checked_utc": NOW, "check_count": len(all_checks),
    "checks": all_checks, "existing_variants": packages,
})
batch_package = write(BASE / "IMPORT_PACKAGE.json", {
    "schema": "boldstone.canonical-policy-working-specification-batch.v1",
    "status": "READY_FOR_SOLE_WRITER_IMPORT", "created_utc": NOW, "reserved_batch": 88,
    "source_owner_session": LANE, "shared_writer_session": ROOT,
    "allocation": ref(BASE / "COORDINATOR_ALLOCATION.json"),
    "canonical_allocation": ref(allocation_path),
    "standing_working_specification_policy": ref(BASE / "CANONICAL_STANDING_POLICY.json"),
    "policy_id": policy["policy_id"],
    "offered_fixing_choice_policy": ref(BASE / "GLOBAL_FIXING_CHOICE_POLICY.json"),
    "canonical_offered_fixing_choice_binding": canonical_binding,
    "existing_variants": packages, "verification": batch_qa,
    "new_specification_approvals": 2, "new_approved_field_groups": 12,
    "new_owner_policy_events": 0, "new_owner_approval_events": 0,
    "new_name_approvals": 0, "new_BC_component_ids": [],
    "shared_master_writes_by_lane": False, "remote_mutations": 0, "private_original_downloads": 0,
    "requested_import": "Import two existing Acanthus One Leaf Left finishes. Keep all six original source dictionaries, 30x30x6 and4kg3-5 as White-comparator estimates,175 as starting-price proposal with surcharge unknown, substance/stock/lead/exact-platform uncertainty, choice under87 separately from installed hardware, cropped-photo and group-context limits.",
})
files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.suffix in (".json", ".py"))
manifest = write(BASE / "SEALED_MANIFEST.json", {
    "created_utc": NOW, "schema": "boldstone.immutable-review-file-manifest.v1",
    "files": [ref(p) for p in files],
    "sealed_files_immutable": True,
    "later_shared_import_and_publication_status_requires_new_receipts": True,
    "control_files_included_as_immutable_initial_snapshots": True,
})
print(json.dumps({"status": "PASS", "checks": len(all_checks), "package": batch_package,
                  "verification": batch_qa, "manifest": manifest, "sealed_files": len(files)}))
