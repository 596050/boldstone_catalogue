"""Read the saved B92 artefacts independently and seal only after all checks pass."""
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
import datetime
import hashlib
import json

BASE = Path(__file__).resolve().parent
REV = BASE.parents[2] / "components/reviews"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
FIELDS = ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"]
GROUPS = ["dimensions_and_depth", "weight", "material_and_finish", "fixings", "individual_price", "availability"]
LANE = "01a13fe6-495b-7253-b923-31823b4cbca8"
ROOT = "01a144ab-1a7c-7223-a403-73a4d53d70ff"


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


def save(p, d):
    assert p.is_relative_to(BASE) and not p.exists(), p
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    return ref(p)


def valid_refs(x):
    if isinstance(x, dict):
        if {"path", "sha256"} <= x.keys():
            assert Path(x["path"]).is_file(), x["path"]
            assert sha(Path(x["path"])) == x["sha256"], x["path"]
        for v in x.values():
            valid_refs(v)
    elif isinstance(x, list):
        for v in x:
            valid_refs(v)


def verify_event(ev, user=False):
    p = Path(ev.get("transcript", ev.get("transcript_path")))
    raw = p.read_bytes().splitlines(keepends=True)[ev["line"] - 1]
    if not ev["source_raw_line_digest_includes_line_ending"]:
        raw = raw.rstrip(b"\r\n")
    assert hashlib.sha256(raw).hexdigest() == ev["raw_line_sha256"]
    payload = json.loads(raw)["payload"]
    if user:
        assert payload["role"] == "user"
        assert "\n".join(c.get("text", "") for c in payload["content"]) == ev["text"]
    else:
        assert payload["output"] == ev["text"] and payload["type"] == "function_call_output"


def url_path(url):
    p = urlparse(url)
    assert p.scheme == "https" and p.netloc == "www.dropbox.com" and p.path.startswith("/home/")
    path = unquote(p.path[len("/home"):])
    preview = parse_qs(p.query).get("preview")
    return path + "/" + preview[0] if preview else path


policy = read(BASE / "CANONICAL_STANDING_POLICY.json")
fixing = read(BASE / "CANONICAL_FIXING_CHOICE_POLICY.json")
weight = read(BASE / "OWNER_APPROXIMATE_WEIGHT_POLICY.json")
allocation = read(BASE / "COORDINATOR_ALLOCATION.json")
verify_event(allocation)
assert allocation["coordinator_thread_id"] == ROOT and "Allocate B92 requested4:" in allocation["text"]
for pol in [policy, fixing, weight]:
    verify_event(pol["authoritative_user_evidence"], user=True)
    assert pol["user_statement"] == pol["authoritative_user_evidence"]["text"]
for k, ev in read(BASE / "CORRECTION_AND_ARRANGEMENT_OWNER_EVIDENCE.json").items():
    if k != "new_owner_events":
        verify_event(ev, user=True)
assert sha(BASE / "EXISTING_ARRANGEMENT_RESOLUTION.json") == "7066f3dbe81a3cf5881f2ac86ba6a7121d0e21a4153fe00697466ff7ae20fd8f"
assert sha(BASE / "OWNER_MANUFACTURE_POLICY.json") == "43e1d46c399200cb87725d976d885f6b467881bbbedfc19687b1b012e8b8afca"

current = read(BASE / "CURRENT_REFERENCE_READBACK.json")
heads = {x["request_id"]: x[x["metadata_type"]] for x in current["metadata"]}
images = read(BASE / "CACHED_IMAGE_BINDING.json")
valid_refs(images)
assert len(current["listings"]) == 6 and all(not x["has_more"] and not x["cursor"] for x in current["listings"])
entries = [e for x in current["listings"] for e in x["entries"]]
assert len(entries) == 26 and len({e["file_id"] for e in entries}) == 26
assert len(images["bindings"]) == 9 and len(images["previews"]) == 26 and len(images["contact_sheets"]) == 6
assert sorted((e["file_id"], e["name"]) for e in entries) == sorted((e["file_id"], e["name"]) for e in images["previews"])
for b in images["bindings"]:
    blob = Path(b["path"]).read_bytes()
    digest = hashlib.sha256(b"".join(hashlib.sha256(blob[i:i + 4194304]).digest()
                                    for i in range(0, len(blob), 4194304))).hexdigest()
    assert digest == b["dropbox_content_hash"]
    h = heads[b["file_id"]]
    assert len(blob) == b["bytes"] == h["size"] and h["rev"] == b["current_rev"]
    assert h["path_display"] == b["current_path_display"]
    assert b["cached_original_viewed_this_turn"] and not b["new_private_original_download"]
for p in images["previews"]:
    assert sha(Path(p["thumbnail_path"])) == p["thumbnail_sha256"] == p["checked_sha256"]
    assert p["viewed_in_contact_sheet_this_turn"]
for s in images["contact_sheets"]:
    assert s["viewed_this_turn"]

index = read(BASE / "PREPARED_PACKAGE_INDEX.json")
assert {x["variant"] for x in index["items"]} == {
    "MOON-CRATER-WHITE-BASIN", "LAVA-CORNER-CURVE-WHITE", "MLAVA-1-WHITE", "MLAVA-2-WHITE"}
ledger = read(REV / "user_classifications.json")
all_checks, packages, pending = {}, [], []
for item in index["items"]:
    directory = Path(item["target"])
    variant, id_key = item["variant"], item["id_key"]
    source = read(directory / "ORIGINAL_SOURCE_REVIEW.json")
    node = read(directory / "SHARED_REVIEW_AT_ALLOCATION.json")
    identity = read(directory / "EXISTING_NAME_APPROVAL.json")
    review = read(directory / "REVIEW.json")
    decision = read(directory / "SPECIFICATION_APPROVAL.json")
    context = read(directory / "CONTEXT_OUTPUT_UPDATE.json")
    specs = decision["specifications"]
    valid_refs(review)
    valid_refs(decision)
    checks = {}

    def check(label, value):
        assert value, (variant, label)
        checks[label] = "PASS"

    check("all_saved_evidence_hashes_match", True)
    check("existing_allocated_identity_and_kind_preserved",
          decision[id_key] == identity[id_key] == variant
          and decision["component_id"] == identity["component_id"] == item["component_id"]
          and decision["canonical_name"] == identity["canonical_name"]
          and decision["variant_kind"] == item["variant_kind"])
    acceptance_rows = [r for key, rows in ledger.items() if "specification" in key and isinstance(rows, list)
                       for r in rows if isinstance(r, dict)]
    check("no_existing_acceptance_overwritten",
          not node["specifications_approved"]
          and not any(r.get(id_key) == variant for r in acceptance_rows))
    check("six_unique_fields_and_proposals", list(specs) == FIELDS
          and decision["approved_field_groups"] == FIELDS and len(set(decision["approved_proposal_ids"])) == 6)
    check("original_and_current_six_source_dictionaries_exact",
          decision["source_specification_proposals_retained"] == source["specification_review_items"]
          and decision["source_current_specification_proposals_retained"] == node["specification_proposals"])
    old = {x["group"]: x for x in source["specification_review_items"]}
    now = {x["group"]: x for x in node["specification_proposals"]}
    check("each_field_preserves_original_and_current_dictionary",
          all(specs[k]["source_original_field_retained"] == old[g]
              and specs[k]["source_current_field_retained"] == now[g] for k, g in zip(FIELDS, GROUPS)))
    check("standing_authority_without_synthetic_replies",
          decision["policy_id"] == policy["policy_id"] and not decision["per_card_owner_reply_received"]
          and not decision["synthetic_owner_reply_created"]
          and decision["new_owner_approval_events"] == decision["new_owner_policy_events"] == 0)
    check("prepared_after_all_three_owner_policies",
          all(review["prepared_utc"] > pol["effective_from_utc"] for pol in [policy, fixing, weight]))
    check("working_acceptance_not_measurement_or_certification",
          all(f["owner_accepted"] and f["owner_approved"] and not f["physical_value_verified"]
              and not f["physical_specs_verified"] for f in specs.values())
          and not decision["physical_specs_verified"] and not decision["independently_measured_or_certified"])
    check("existing_weight_display_and_range_retained",
          specs["weight"]["display"] == now["weight"]["display"]
          and specs["weight"]["value"]["existing_applicable_estimate_retained"]
          and specs["weight"]["approximate_weight_policy_id"] == weight["policy_id"]
          and specs["weight"]["value"]["actual_weighed_kg"] is None)
    check("current_offered_fixing_choice_separate_from_installed_hardware",
          specs["fixing"]["value"]["offered_options"] == ["Keyhole fixing", "French cleat"]
          and decision["offered_fixing_choice_policy_id"] == fixing["policy_id"]
          and all(specs["fixing"]["value"][k] is None for k in ["actual_fitted_type", "count", "hardware_material", "attachment", "rated_load"])
          and not specs["fixing"]["value"]["historical_proposal_is_installed_fact"])
    check("material_and_coating_remain_uncertain",
          specs["material_finish"]["value"]["actual_binder"] is None
          and specs["material_finish"]["value"]["coating_or_sealer"] is None
          and not specs["material_finish"]["value"]["water_contact_suitability_verified"])
    check("working_prices_not_current_verified_offers",
          not specs["individual_price"]["current_public_selling_price_verified"]
          and not specs["individual_price"]["value"]["exact_existing_offer_confirmed"])
    check("manufacture_policy_separate_from_unknown_stock_and_lead",
          decision["owner_stated_manufacture"] and not decision["manufacture_question_required"]
          and all(specs["availability"]["value"][k] is None for k in ["physical_stock", "reproducibility", "lead_time"]))
    check("platform_evidence_preserved_without_cross_design_mapping",
          decision["platform_mapping"] == node["platform_mapping"]
          and not decision["platform_mapping"]["current_individual_offer_confirmed"])
    check("current_image_and_folder_links_bound_to_ids",
          url_path(decision["image_link"]) == heads[decision["primary_file_id"]]["path_display"]
          and url_path(decision["folder_link"]) == heads[decision["folder_id"]]["path_display"])
    ctx = decision["context_images"]
    check("context_links_and_missing_views_retained",
          ctx == context["context_images"]
          and url_path(ctx["image_url"]) == heads[ctx["representative_file_id"]]["path_display"]
          and url_path(ctx["folder_url"]) == heads[ctx["representative_folder_id"]]["path_display"]
          and ctx["individual_complete_product_image_established"]
          and not ctx["rear_reference_established"] and not ctx["calibrated_profile_established"])
    check("scene_and_exact_cast_provenance_not_inferred",
          not ctx["scene_provenance_verified"] and not ctx["actual_installation_verified"]
          and not ctx["same_physical_cast_verified"] and ctx["new_sculpture_count"] == 0)
    check("no_new_identity_counts_shared_writes_or_remote_actions",
          decision["new_name_approvals"] == decision["new_design_mould_or_stock_counts"] == 0
          and not decision["shared_master_writes_by_lane"] and decision["new_BC_component_ids"] == []
          and decision["remote_mutations"] == decision["fresh_private_original_downloads"] == 0)
    if variant == "MOON-CRATER-WHITE-BASIN":
        check("basin_empty_mass_and_freestanding_support_preserved",
              specs["weight"]["value"]["proposed_range_kg"] == [10, 20]
              and specs["weight"]["value"]["scope"] == "Empty basin only"
              and "Freestanding" in specs["fixing"]["display"]
              and specs["fixing"]["value"]["freestanding_support_proposal"]
              and not specs["fixing"]["value"]["wall_mounted_basin_design_or_applicability_verified"])
        check("basin_price_exclusions_and_build_boundary_preserved",
              specs["individual_price"]["value"]["proposed_price_gbp"] == 600
              and specs["individual_price"]["value"]["excluded"] == ["Separate support", "Pump", "Plumbing", "Installation"]
              and decision["arrangement"] is None and id_key == "build_variant_id")
    elif variant == "LAVA-CORNER-CURVE-WHITE":
        check("corner_owner30_target_not_existing_specimen_measurement",
              specs["dimensions"]["value"]["proposed_face_cm"] == [30, 30]
              and specs["dimensions"]["value"]["face_basis"] == "OWNER_DIRECTED_TARGET_INTERPRETED_AS_SQUARE"
              and specs["dimensions"]["value"]["actual_measured_dimensions_cm"] is None
              and specs["dimensions"]["value"]["depth_range_cm"] == [5, 8])
        check("corner_superseded_size_weight_price_not_reactivated",
              specs["weight"]["value"]["proposed_range_kg"] == [3, 6]
              and specs["individual_price"]["value"]["proposed_price_gbp"] is None
              and specs["individual_price"]["value"]["current_30cm_price_unconfirmed"]
              and specs["individual_price"]["value"]["owner_price_approval_scope"] == "ENQUIRY_STATUS_ONLY_NO_NUMERIC_PRICE")
    else:
        check("lava_individual_estimates_and_price_preserved",
              specs["dimensions"]["value"]["proposed_face_cm"] == [55, 55]
              and specs["dimensions"]["value"]["depth_range_cm"] == [5, 8]
              and specs["weight"]["value"]["proposed_range_kg"] == [8, 16]
              and specs["individual_price"]["value"]["proposed_price_gbp"] == 550)
        check("owner_arrangement_membership_not_extra_products_or_lava_moon_transfer",
              decision["arrangement"]["arrangement_id"] == "MLAVA-1-PLUS-2-WHITE"
              and decision["arrangement"]["membership_basis"] == "OWNER_STATEMENT"
              and not decision["arrangement"]["same_measured_size_confirmed"]
              and not decision["arrangement"]["same_actual_cast_or_mould_confirmed"]
              and not decision["arrangement"]["Lava_Moon_or_Luciano_specifications_transferred"]
              and decision["arrangement"]["new_products_or_stock_counts"] == 0)
    pending.append((directory, item, checks))
    all_checks.update({variant + ":" + k: v for k, v in checks.items()})

for directory, item, checks in pending:
    qa = save(directory / "SEALED_PACKAGE_VERIFICATION.json", {
        "status": "PASS", "checked_utc": NOW, "check_count": len(checks), "checks": checks,
        "decision": ref(directory / "SPECIFICATION_APPROVAL.json"),
    })
    package = save(directory / "IMPORT_PACKAGE.json", {
        "schema": "boldstone.working-variant-specification-import.v1", "created_utc": NOW,
        "status": "READY_FOR_SOLE_WRITER_IMPORT", "reserved_batch": 92, "source_owner_session": LANE,
        "shared_writer_session": ROOT, "component_id": item["component_id"], item["id_key"]: item["variant"],
        "variant_kind": item["variant_kind"], "decision": ref(directory / "SPECIFICATION_APPROVAL.json"),
        "prepared_review": ref(directory / "REVIEW.json"), "verification": qa,
        "context_output_update": ref(directory / "CONTEXT_OUTPUT_UPDATE.json"),
        "requested_import": "Six working fields under80; offered fixing choice87 and applicable approximate weight90. Retain original and current six source dictionaries, owner corrections, per-component boundaries and photograph gaps.",
        "new_specification_approvals": 1, "new_approved_field_groups": 6, "new_name_approvals": 0,
        "new_owner_approval_events": 0, "new_owner_policy_events": 0, "new_BC_component_ids": [],
        "shared_master_writes_by_lane": False, "remote_mutations": 0, "private_original_downloads": 0,
    })
    packages.append({"component_id": item["component_id"], "variant": item["variant"],
                     "variant_kind": item["variant_kind"], "package": package,
                     "verification": qa, "context": ref(directory / "CONTEXT_OUTPUT_UPDATE.json")})
qa = save(BASE / "BATCH_VERIFICATION.json", {
    "status": "PASS", "checked_utc": NOW, "check_count": len(all_checks), "checks": all_checks,
    "policy_transcript_and_correction_bindings_verified": True,
    "current_metadata_count": 15, "complete_listings": 6, "listed_files": 26,
    "cached_originals_rehashed_and_viewed": 9, "cached_previews_rehashed_and_viewed_in_sheets": 26,
    "contact_sheets_rehashed_and_viewed": 6, "existing_variants": packages,
})
package = save(BASE / "IMPORT_PACKAGE.json", {
    "schema": "boldstone.canonical-policy-working-specification-batch.v1",
    "status": "READY_FOR_SOLE_WRITER_IMPORT", "created_utc": NOW, "reserved_batch": 92,
    "source_owner_session": LANE, "shared_writer_session": ROOT,
    "allocation": ref(BASE / "COORDINATOR_ALLOCATION.json"),
    "standing_working_specification_policy": ref(BASE / "CANONICAL_STANDING_POLICY.json"),
    "offered_fixing_choice_policy": ref(BASE / "CANONICAL_FIXING_CHOICE_POLICY.json"),
    "approximate_weight_policy": ref(BASE / "OWNER_APPROXIMATE_WEIGHT_POLICY.json"),
    "policy_id": policy["policy_id"], "existing_variants": packages, "verification": qa,
    "new_specification_approvals": 4, "new_approved_field_groups": 24,
    "new_owner_policy_events": 0, "new_owner_approval_events": 0, "new_name_approvals": 0,
    "new_BC_component_ids": [], "shared_master_writes_by_lane": False,
    "remote_mutations": 0, "private_original_downloads": 0,
    "requested_import": "Four existing kept scopes, one build and three finishes. Preserve all original/current source dictionaries. Basin empty10–20kg and freestanding support remain distinct from offered fixing choices; wall-mounted basin applicability unresolved. Corner30×30 target/depth5–8guess/3–6kg retained; no current price and superseded500 not revived. Lava1/2 each55×55depth5–8guess,8–16kg,550proposal; owner-confirmed combined arrangement remains two existing components. No Lava Moon/Luciano transfer. Context images and missing rear/calibrated views retained.",
})
files = sorted(p for p in BASE.rglob("*") if p.is_file())
seal = save(BASE / "SEALED_MANIFEST.json", {
    "schema": "boldstone.immutable-review-package-manifest.v1", "status": "SEALED_READY_FOR_IMPORT",
    "sealed_utc": NOW, "reserved_batch": 92, "package": package, "verification": qa,
    "files": [ref(p) for p in files],
    "scope": "All listed files, including controls and scripts, are immutable. Later import/publication status belongs in additive receipts.",
    "self_not_in_file_list": True,
})
print(json.dumps({"status": "SEALED_READY_FOR_IMPORT", "checks": len(all_checks), "package": package,
                  "verification": qa, "seal": seal, "sealed_files_excluding_manifest": len(files)}))
