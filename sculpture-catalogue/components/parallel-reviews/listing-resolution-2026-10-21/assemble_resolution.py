"""Assemble immutable evidence into a local, non-executing import proposal."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def read(name):
    return json.loads((BASE / name).read_text())


def bind(name, pointer=None):
    p = BASE / name
    b = p.read_bytes()
    result = {"path": str(p), "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    if pointer is not None:
        result["json_pointer"] = pointer
    return result


def write(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


now = datetime.now(timezone.utc).isoformat()
master = read("inputs/master-register.json")
assigned = read("ASSIGNED_106_SCOPE.json")["records"]
nonwall = read("worker-02/OPTION_RESOLUTIONS.json")
wall = read("worker-03/WALL_CIRCLE_CROSSWALK.json")
four = read("FOUR_LISTING_CORRECTIONS.json")
overlaps = read("worker-01/OVERLAP_PROPOSALS.json")
fresh = read("worker-01/FRESH_PUBLIC_INVENTORY.json")
prior_positive = read("worker-02/PRIOR_POSITIVE_ASSOCIATION_AUDIT.json")
options = {x["product_id"]: (i, x) for i, x in enumerate(master["options"])}
assigned_by_id = {x["product_id"]: x for x in assigned}
scope_entries = []
new_edges = []

for i, e in enumerate(nonwall["entries"]):
    option = options[e["option_id"]][1]
    for j, match in enumerate(e["new_supported_native_matches"]):
        new_edges.append({
            "evidence_edge_id": f"LR20261021:{e['option_id']}:{match['platform']}:{match['offer_ref']}",
            "option_id": e["option_id"],
            "canonical_key": e["canonical_key"],
            "match": copy.deepcopy(match),
            "source_ref": bind("worker-02/OPTION_RESOLUTIONS.json", f"/entries/{i}/new_supported_native_matches/{j}"),
            "exact_current_physical_or_all_six_field_configuration_certified": False,
            "native_or_catalogue_record_created": False,
        })
    prepared = e["draft_individual_listing"]
    draft = prepared if prepared.get("proposed_sku") else None
    scope_entries.append({
        "product_id": e["option_id"], "canonical_key": e["canonical_key"], "name": e["name"],
        "prior_disposition": e["prior_disposition"],
        "source_resolution_disposition": e["proposed_disposition"],
        "review_status": e["review_status"],
        "source_supported_individual_record_added": bool(e["new_supported_native_matches"]),
        "supported_source_matches": copy.deepcopy(e["new_supported_native_matches"]),
        "conditional_native_tuple": None,
        "draft_listing": copy.deepcopy(draft),
        "custom_unlisted_pattern_draft": None,
        "scope_reason": e["scope_reason"],
        "remaining_evidence_gaps": copy.deepcopy(e["remaining_evidence_gaps"]),
        "next_action": e["required_next_evidence_kind"],
        "accepted_working_fields": copy.deepcopy(option["master_fields"]),
        "accepted_working_fields_changed": False,
        "physical_configuration_verified": False,
        "authenticated_admin_inventory_verified": False,
        "proven_live_absent": False,
        "reference_epoch": "Original frozen master plus linked read-only path overlays; coordinator rebases current paths.",
        "source_ref": bind("worker-02/OPTION_RESOLUTIONS.json", f"/entries/{i}"),
        "master_ref": bind("inputs/master-register.json", f"/options/{options[e['option_id']][0]}"),
    })

for i, e in enumerate(wall["entries"]):
    option = options[e["product_id"]][1]
    lookup = e["logical_offered_variant_assignment"]
    has_lookup = lookup["exact_native_row_lookup_verified"]
    candidate = e["current_working_configuration_assignment"]["existing_native_variant_candidate"]
    scope_entries.append({
        "product_id": e["product_id"], "canonical_key": e["canonical_key"], "name": e["retained_name"],
        "prior_disposition": assigned_by_id[e["product_id"]]["prior_disposition"],
        "source_resolution_disposition": "CONDITIONAL_VISUAL_PATTERN_WITH_EXACT_NATIVE_WORKING_TUPLE_LOOKUP" if has_lookup else "NO_SUPPORTED_NAMED_PATTERN_CUSTOM_OR_UNLISTED_DRAFT_SCOPE",
        "review_status": "COMPLETE_BOUNDED_SOURCE_AUDIT; PATTERN_ATTRIBUTION_LIMITS_RETAINED",
        "source_supported_individual_record_added": False,
        "supported_source_matches": [],
        "conditional_native_tuple": copy.deepcopy(candidate),
        "conditional_tuple_semantics": copy.deepcopy(lookup),
        "all_eight_offered_tuples": copy.deepcopy(e["offered_configuration_coverage"]),
        "pattern_assignment": copy.deepcopy(e["pattern_assignment"]),
        "draft_listing": None,
        "custom_unlisted_pattern_draft": copy.deepcopy(e["custom_unlisted_draft_scope"]),
        "scope_reason": "The named-pattern attribution is conditional visual evidence. The existing selected 50cm/RGB row is an exact native table lookup, not an owner-confirmed pattern or measured physical configuration." if has_lookup else "None of the 18 checked native pattern swatches supports a safe assignment. Retain this kept visual option as a custom/unlisted draft scope without inventing a native variant or proving global absence.",
        "remaining_evidence_gaps": (["Formal owner declaration of the native pattern name remains absent; physical specimen, installed hardware/lighting and measured size remain separate."] if has_lookup else [e["remaining_owner_question"]["question"]]),
        "next_action": "Use the linked existing native tuple as a conditional working candidate; obtain exact pattern confirmation before treating it as a confirmed option-to-variant identity." if has_lookup else e["custom_unlisted_draft_scope"]["next_decision"],
        "accepted_working_fields": copy.deepcopy(option["master_fields"]),
        "accepted_working_fields_changed": False,
        "physical_configuration_verified": False,
        "authenticated_admin_inventory_verified": False,
        "proven_live_absent": False,
        "reference_epoch": "Frozen master; exact source table is current public inventory; pattern swatch captures are dated 17 October.",
        "source_ref": bind("worker-03/WALL_CIRCLE_CROSSWALK.json", f"/entries/{i}"),
        "master_ref": bind("inputs/master-register.json", f"/options/{options[e['product_id']][0]}"),
    })

scope_entries.sort(key=lambda e: options[e["product_id"]][0])
assert len(scope_entries) == len({e["product_id"] for e in scope_entries}) == 106
assert {e["product_id"] for e in scope_entries} == set(assigned_by_id)
scope_counts = {
    "assigned_options_reviewed": 106,
    "new_supported_individual_source_options": 2,
    "new_source_record_links": 3,
    "conditional_wall_circle_working_variant_lookups": 4,
    "remaining_source_scope_gaps_or_identity_candidates": 100,
    "nonwall_gap_or_candidate_drafts": 97,
    "nonwall_draft_product_groups": 76,
    "wall_circle_custom_unlisted_draft_scopes": 3,
    "accepted_working_fields_preserved": 636,
    "accepted_working_fields_changed": 0,
    "exact_physical_or_all_six_field_configurations_certified": 0,
    "authenticated_admin_inventories_verified": 0,
    "proven_live_absences": 0,
    "native_products_or_variants_created": 0,
    "native_SKUs_created_or_changed": 0,
    "source_resolution_dispositions": dict(sorted(Counter(e["source_resolution_disposition"] for e in scope_entries).items())),
}
write("OPTION_RESOLUTIONS_106.json", {
    "schema": "boldstone.listing-resolution-106.v1", "prepared_utc": now,
    "status": "COMPLETE_BOUNDED_EVIDENCE_REVIEW; LIVE_EXECUTION_NOT_PERFORMED",
    "frozen_master": bind("inputs/master-register.json"),
    "fresh_public_inventory": bind("worker-01/FRESH_PUBLIC_INVENTORY.json"),
    "counts": scope_counts, "entries": scope_entries,
    "scope_boundary": "106 reviewed is not 106 confirmed native matches. New supported source links, conditional working tuples and checked-source gaps are separate dispositions.",
})
write("NEW_SOURCE_LINKS.json", {
    "schema": "boldstone.additive-listing-source-links.v1", "prepared_utc": now,
    "edges": new_edges,
    "historical_262_edges_deleted_or_rewritten": False,
    "source_offer_count_increment": 0,
    "native_or_catalogue_record_count_increment": 0,
})

actions = []
for e in four["records"]:
    actions.append({
        "action_id": e["case_id"] + ":COPY",
        "action_type": "EXISTING_PRODUCT_COPY_CORRECTION_DRAFT",
        "catalogue_option_id": e["product_id"],
        "native_identity": copy.deepcopy(e["native_record_identity"]),
        "request_draft": copy.deepcopy(e["native_product_partial_update_draft"]),
        "preconditions": copy.deepcopy(e["execution_preconditions"]),
        "commercial_mode_dependency": copy.deepcopy(e["commercial_policy_proposal"]),
        "native_sku_action": "RETAIN",
        "inventory_and_shipping_measurements_action": "NO_CHANGE",
        "execution_status": "NOT_EXECUTED",
    })
rust = next(e for e in overlaps["proposals"] if e["case_id"] == "RUST-SKU-COLLISION")
alias = rust["canonical_alias_proposal"]
legacy_sku = alias["reversible_draft_only"]["proposed_unique_legacy_sku"]
actions.append({
    "action_id": "RUST-SKU-COLLISION:LEGACY-SKU",
    "action_type": "EXISTING_VARIANT_SKU_CORRECTION_DRAFT",
    "catalogue_option_id": "BSI-947F365275C5",
    "native_identity": {"native_product_id": alias["alias_native_product_id"], "native_variant_id": alias["alias_native_variant_id"]},
    "before_sku": "EBAY-188654649217", "proposed_sku": legacy_sku,
    "original_sku_preserved_as_historical_alias": True,
    "canonical_offer_retaining_original_sku": "O067",
    "request_draft": {"method": "POST", "path": f"/v2/commerce/products/{alias['alias_native_product_id']}/variants/{alias['alias_native_variant_id']}", "body": {"sku": {"present": True, "value": legacy_sku}}, "executable_now": False},
    "preconditions": ["Confirm the authenticated store/site and fresh exact product/variant identifiers.", "Check all current administrative variants for the proposed unique SKU before applying; public/historical uniqueness is not complete account uniqueness.", "Preserve native IDs, original SKU alias, order history, photographic sources, price conflicts and physical-stock uncertainty.", "Record a separate native write/readback receipt; this packet has no platform writes."],
    "execution_status": "NOT_EXECUTED",
})
for offer, product, reason in [
    ("O051", alias["alias_native_product_id"], "Legacy duplicate marketing record; preserve O067 as the proposed canonical workflow target. Price, stock and same physical cast remain unconfirmed."),
    ("O015", "6a5559d21b9743318cc70b4b", "Title/photo identity conflict: gallery shows Moon Water Catcher, original intended Concave/MCP4 configuration is not established."),
]:
    actions.append({
        "action_id": offer + ":VISIBILITY-QUARANTINE",
        "action_type": "REVERSIBLE_PRODUCT_VISIBILITY_QUARANTINE_DRAFT",
        "source_offer_ref": offer, "native_product_id": product,
        "request_draft": {"method": "POST", "path": f"/v2/commerce/products/{product}", "body": {"isVisible": {"present": True, "value": False}}, "executable_now": False},
        "reason": reason,
        "preconditions": ["Fresh authenticated identity, visibility and concurrent-change readback.", "Preserve identifiers, historical source values, images and prior visibility.", "Check actual direct-URL and purchase behaviour separately; isVisible=false is not a certified checkout-disable or deletion."],
        "execution_status": "NOT_EXECUTED",
        "url_access_or_checkout_disabled_claimed": False,
    })
write("NATIVE_ACTION_DRAFTS.json", {
    "schema": "boldstone.nonexecuting-native-listing-action-drafts.v1", "prepared_utc": now,
    "status": "REVIEWABLE_DRAFTS; NO_PLATFORM_EXECUTION",
    "actions": actions, "request_drafts": len(actions),
    "physical_stock_or_inventory_aggregation_performed": False,
    "price_on_enquiry_mode": {"numeric_zero_price_proposed": False, "requires_consistent_native_purchase_enquiry_flow": True, "prepared_request_drafts_do_not_implement_the_flow": True},
    "execution_access_ref": bind("ACCESS_OBSERVATIONS.json"),
    "official_platform_reference": bind("OFFICIAL_PLATFORM_REFERENCES.json"),
})

scoped = {e["product_id"]: e for e in scope_entries}
four_by_id = {e["product_id"]: e for e in four["records"]}
case_ids = {}
for case in overlaps["proposals"]:
    for product_id in case["existing_canonical_product_ids"]:
        case_ids.setdefault(product_id, []).append(case["case_id"])
# The O038 reassignment applies to the separately retained Verdigris-and-Rust option.
case_ids.setdefault("BSI-09C1A55D460D", []).append("VERDIGRIS-VERSIONS")
overlay = []
for i, option in enumerate(master["options"]):
    pid = option["product_id"]
    old = option["current_listing_reconciliation"]
    e = scoped.get(pid)
    source_present = old["individual_source_record_supported"] or bool(e and e["source_supported_individual_record_added"])
    correction = four_by_id.get(pid)
    state = e["source_resolution_disposition"] if e else ("EXISTING_RECORD_WORKING_COPY_CORRECTION_PREPARED" if correction else "PRIOR_SOURCE_RECONCILIATION_RETAINED")
    overlay.append({
        "product_id": pid, "canonical_key": option["canonical_key"], "name": option["name"],
        "family": option.get("family"),
        "prior_overall_disposition": old["overall_disposition"],
        "current_source_resolution_disposition": state,
        "source_supported_individual_record_present": source_present,
        "reviewed_in_assigned_106": e is not None,
        "assigned_106_resolution_ref": bind("OPTION_RESOLUTIONS_106.json", f"/entries/{scope_entries.index(e)}") if e else None,
        "new_supported_source_matches": copy.deepcopy(e["supported_source_matches"]) if e else [],
        "conditional_native_tuple": copy.deepcopy(e["conditional_native_tuple"]) if e else None,
        "exact_current_physical_or_all_six_field_configuration_certified": False,
        "correction_case_id": correction["case_id"] if correction else None,
        "overlap_case_ids": case_ids.get(pid, []),
        "source_photo_binding_review": "O009_CURRENT_GENERIC_VERDIGRIS_GALLERY_RETAINED; HISTORICAL_SPECKLED_HERO_APPLICABILITY_CONFLICT" if pid == "BSI-4536FDCA0DA9" else None,
        "prior_native_binding_downgraded": False,
        "accepted_working_fields_changed": False,
        "next_action": e["next_action"] if e else ("Apply the prepared native copy correction after authenticated access and fresh concurrent-change readback; retain accepted working values and source-history conflicts." if correction else old["next_action"]),
        "master_ref": bind("inputs/master-register.json", f"/options/{i}"),
    })

reviewed_ids = {e["product_id"] for e in scope_entries} | set(four_by_id) | set(case_ids) | {"BSI-4536FDCA0DA9"}
counts = {
    "catalogue_options": 184, "accepted_working_field_groups": 1104,
    "catalogue_options_added_removed_merged": 0, "working_field_groups_changed": 0,
    "original_source_offers_preserved": 81, "original_evidence_edges_preserved": 262,
    "new_additive_evidence_edges": len(new_edges),
    "prior_individual_design_source_options": sum(x["current_listing_reconciliation"]["individual_source_record_supported"] for x in master["options"]),
    "current_individual_design_source_options": sum(x["source_supported_individual_record_present"] for x in overlay),
    "four_existing_copy_corrections_prepared": len(four["records"]),
    "overlap_or_collision_cases_reviewed_including_historical": len(overlaps["proposals"]),
    "current_overlap_cases_including_recorded_SKU_collision": 3,
    "historical_overlap_cases": 2,
    "native_action_requests_prepared": len(actions),
    "unique_catalogue_options_touched_by_current_review": len(reviewed_ids),
    "wall_circle_native_variants_retained": 144,
    "wall_circle_pattern_image_bindings_covering_144_tuples": 18,
    "explicit_144_variant_image_API_assignments_claimed": False,
    "platform_writes": 0, "shared_master_writes_by_this_lane": 0,
    **scope_counts,
}
write("LISTING_RESOLUTION.json", {
    "schema": "boldstone.catalogue-listing-resolution-overlay.v1", "prepared_utc": now,
    "status": "EVIDENCE_REVIEW_AND_DRAFT_CORRECTIONS_PREPARED; SOLE_WRITER_IMPORT_PENDING; LIVE_EXECUTION_NOT_PERFORMED",
    "owner_instruction": bind("OWNER_INSTRUCTION.json"),
    "frozen_master": bind("inputs/master-register.json"),
    "counts": counts,
    "option_overlays": overlay,
    "four_listing_corrections": bind("FOUR_LISTING_CORRECTIONS.json"),
    "overlap_and_collision_cases": bind("worker-01/OVERLAP_PROPOSALS.json"),
    "new_source_links": bind("NEW_SOURCE_LINKS.json"),
    "native_action_drafts": bind("NATIVE_ACTION_DRAFTS.json"),
    "O009_prior_positive_retained_and_source_photo_review": bind("worker-02/PRIOR_POSITIVE_ASSOCIATION_AUDIT.json"),
    "fresh_public_inventory": bind("worker-01/FRESH_PUBLIC_INVENTORY.json"),
    "public_pagination_boundary_check": bind("worker-01/BOUNDARY_INVENTORY_SUPPLEMENT.json"),
    "inherited_historical_source_path_epoch_resolution": bind("HISTORICAL_REFERENCE_RESOLUTIONS.json"),
    "child_validation_refs": [bind("worker-01/VALIDATION.json"), bind("worker-02/VALIDATION.json"), bind("worker-03/FINAL_READBACK.json")],
    "global_limits": [
        "203 returned public Squarespace products / 370 variants are not authenticated admin/draft completeness; advertised208 discrepancy remains. Boundary offsets198/200/202 add no distinct product IDs.",
        "Shopify is the retained historical136-product/160-variant export, not a current authenticated store; unexported numeric IDs remain null.",
        "Two added logical design/appearance/recorded-size/sale-unit links do not certify physical casts, all-six-field equality, stock, formulation or exact installed hardware.",
        "Four Wall Circle50cm/RGB source tuples are exact deterministic lookups conditional on visual pattern attribution. Three other visual scopes have no supported named-pattern match among18 and remain draft-only, not proven live absence.",
        "97 non-Wall draft variants in76 component/design groups are proposals pending current admin duplicate checks, not97 created products. Three custom/unlisted Wall Circle scopes propose no native variant creation.",
        "All accepted specifications, original source offers, historical candidate edges and count identities remain unchanged. Source copy and native price/availability conflicts remain separately visible.",
        "Actual website copy, SKU collision, quarantine visibility and enquiry-mode changes are not executed by this packet.",
    ],
})

write("IMPORT_PLAN.json", {
    "schema": "boldstone.listing-resolution-sole-writer-import-plan.v1", "prepared_utc": now,
    "sole_writer_thread": "01a144ab-1a7c-7223-a403-73a4d53d70ff",
    "payload": bind("LISTING_RESOLUTION.json"),
    "proposed_current_resolution_key": "current_listing_resolution",
    "rules": [
        "Import the per-option overlay by immutable product_id/canonical_key only. All184 names/IDs and1104 master_fields must compare equal before and after.",
        "Rebase onto the newest verified current-master pointer, retaining Step07 and Cup/Frozen path/parent overlays; frozen child path strings are historical source epoch only.",
        "Keep the original81 source-offer table,262 original evidence edges and165 original issues intact as dated evidence. Add the3 new source-match edges in a separate overlay with their exact source pointers; never silently rewrite historical evidence.",
        "Expose the current resolution independently from the20October source status. Report47 supported individual design/source options (including4 prepared copy-conflict records and2 newly linked with qualifications),4 conditional WC working tuples, and100 gap/candidate cases within the106 review.",
        "Never count four conditional WC tuple lookups as owner-confirmed exact pattern/configuration identities; preserve144 native tuples and18 pattern-image bindings without inventing144 explicit variant-image assignments.",
        "Record O067 canonical workflow / O051 legacy-SKU draft and O059 primary / O015 identity-conflict quarantine as local resolutions and prepared native actions. Do not label these live-executed or approve the conflicting price/stock settings.",
        "O004 remains generic muted Verdigris, O038 is source-supported for the existing Verdigris-and-Rust option. O009 current gallery retains generic Verdigris; its historical speckled hero stays as dated applicability conflict. No kept finishes are merged or deleted.",
        "Keep O039 Gold as a historical design reference with unresolved size; O064 is a historical photographic duplicate alias of O003, not a second currently observed public offer.",
        "Use the accepted master_fields display and state for all specification views. Correction proposals and new draft SKUs must remain labelled prepared/draft and cannot overwrite accepted working values or source-price assertions.",
        "Refresh workbook current resolution/correction views with full semantic qualifications. Preserve existing source tabs and original workbook history. Save, reload, validate row/ID/value counts and visually inspect updated sheets.",
        "Issue a publication receipt with exact final register/workbook hashes. A lane independently reads back the published master before reporting integration complete.",
    ],
    "native_execution_authority_or_access_granted_by_import": False,
    "shared_master_written_by_A_lane": False,
})

with (BASE / "RESOLUTION_REVIEW.csv").open("w", newline="") as f:
    fields = ["product_id", "canonical_key", "name", "prior_overall_disposition", "current_source_resolution_disposition", "source_supported_individual_record_present", "reviewed_in_assigned_106", "correction_case_id", "overlap_case_ids", "conditional_native_variant_id", "conditional_native_SKU", "exact_current_physical_or_all_six_field_configuration_certified", "next_action"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for e in overlay:
        row = {k: e.get(k) for k in fields}
        row["overlap_case_ids"] = "; ".join(e["overlap_case_ids"])
        row["conditional_native_variant_id"] = (e["conditional_native_tuple"] or {}).get("native_variant_id")
        row["conditional_native_SKU"] = (e["conditional_native_tuple"] or {}).get("sku")
        writer.writerow(row)

print(json.dumps(counts, indent=2))
