"""Create a bounded account-lookup queue, never a platform executor."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CATALOGUE = BASE.parents[2]
PRIOR = BASE.parent / "listing-resolution-2026-10-21"
BASE.mkdir(exist_ok=True)


def read(path):
    return json.loads(Path(path).read_text())


def bind(path):
    p = Path(path)
    raw = p.read_bytes()
    return {"path": str(p), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def write(name, obj):
    (BASE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


now = datetime.now(timezone.utc).isoformat()
pointer_bytes = (CATALOGUE / "current-master.json").read_bytes()
pointer = json.loads(pointer_bytes)
register = CATALOGUE / pointer["register"]
master_bytes = register.read_bytes()
assert hashlib.sha256(master_bytes).hexdigest() == pointer["register_sha256"]
assert pointer_bytes == (CATALOGUE / "current-master.json").read_bytes()
inputs = BASE / "inputs"
inputs.mkdir(exist_ok=True)
(inputs / "current-master.json").write_bytes(pointer_bytes)
(inputs / "master-register.json").write_bytes(master_bytes)
master = json.loads(master_bytes)
options = {e["product_id"]: e for e in master["options"]}
source_offers = {e["offer_ref"]: e for e in master["current_listing_source_links"]["offers"]}
scope = read(PRIOR / "OPTION_RESOLUTIONS_106.json")
nonwall = read(PRIOR / "worker-02/OPTION_RESOLUTIONS.json")
nonwall_by_id = {e["option_id"]: e for e in nonwall["entries"]}
queue = []
conditional = []
positives = []
for e in scope["entries"]:
    option = options[e["product_id"]]
    if e["source_supported_individual_record_added"]:
        positives.append({"product_id": e["product_id"], "name": e["name"], "existing_bindings": copy.deepcopy(e["supported_source_matches"]), "state": "RETAIN_ALREADY_SUPPORTED_SOURCE_BINDING; CURRENT_ADMIN_READBACK_STILL_REQUIRED"})
        continue
    if e["conditional_native_tuple"]:
        conditional.append({"product_id": e["product_id"], "name": e["name"], "existing_candidate": copy.deepcopy(e["conditional_native_tuple"]), "pattern_attribution": copy.deepcopy(e["pattern_assignment"]), "state": "CONDITIONAL_WORKING_PATTERN_AND_EXACT_NATIVE_TUPLE; NOT_PHYSICAL_CERTIFICATION", "next_action": "Read the exact existing native product/variant row. Retain the conditional pattern attribution unless maker evidence or an explicit owner pattern identification resolves it; do not create a duplicate variant."})
        continue
    related = []
    for ref in nonwall_by_id.get(e["product_id"], {}).get("related_offer_refs", []):
        offer = source_offers[ref]
        ss = offer["Squarespace"]
        sh = offer["Shopify"]
        related.append({
            "offer_ref": ref, "source_title": offer["source_title"],
            "source_sku": offer["source_sku"],
            "Squarespace_product_id": ss.get("native_product_id"),
            "Squarespace_variant_ids": [v.get("native_variant_id") for v in ss.get("variants", [])],
            "Shopify_handle": sh.get("handle"),
            "relationship": "RELATED_SOURCE_CANDIDATE_ONLY; NOT_A_STANDALONE_COMPONENT_SKU_ASSIGNMENT",
        })
    custom = e["custom_unlisted_pattern_draft"]
    if custom:
        required = "Owner exact native Pattern label or custom-pattern confirmation, followed by current account variant search."
    else:
        required = "Current authenticated product/variant/draft inventory lookup using design geometry, named finish appearance, recorded size/build and individual sale unit."
    search_terms = [e["name"], option["canonical_component_id"], *[r["source_sku"] for r in related if r["source_sku"]]]
    search_terms = list(dict.fromkeys(s for s in search_terms if s))
    queue.append({
        "product_id": e["product_id"], "canonical_key": e["canonical_key"], "name": e["name"],
        "state": "WAITING_FOR_CURRENT_ACCOUNT_LOOKUP" if not custom else "WAITING_FOR_PATTERN_IDENTITY_AND_CURRENT_ACCOUNT_LOOKUP",
        "current_resolution": e["source_resolution_disposition"],
        "account_search_terms": search_terms,
        "related_source_candidates": related,
        "current_image_file_id": option.get("primary_image_file_id"),
        "current_folder_id": option.get("primary_folder_id"),
        "source_gaps": copy.deepcopy(e["remaining_evidence_gaps"]),
        "required_evidence": required,
        "individual_draft": copy.deepcopy(e["draft_listing"]),
        "custom_pattern_scope": copy.deepcopy(custom),
        "match_criteria": [
            "Specific design geometry/source identity, not title, filename, broad family or palette alone.",
            "Owner-kept finish appearance and recorded offered size/build compatible, with material/measurement qualifications preserved.",
            "An individually offered sale unit. A set or gallery photograph does not allocate its SKU, price or weight to one member.",
            "Native product ID, variant ID, SKU and option attributes read from the same current account record, plus the record visibility/date.",
            "Different photographs or patina placement need not imply a different design; document logical design/finish scope separately from physical-cast identity.",
        ],
        "if_supported_existing_record_found": "Bind its exact native IDs/SKU and source evidence to this existing catalogue option. Preserve specification/price conflicts separately; never create a duplicate just to obtain a new SKU.",
        "if_no_record_in_complete_authenticated_inventory": "Record the native lookup scope and result, then use the existing local draft reference. No extra catalogue ID is needed. Custom Wall Circle variants still need their pattern decision.",
        "physical_stock_quantity": None, "global_live_absence_proven": False,
        "source_ref": e["source_ref"],
    })
assert len(queue) == len({e["product_id"] for e in queue}) == 100
assert len(conditional) == 4 and len(positives) == 2
assert sum(e["individual_draft"] is not None for e in queue) == 97
assert sum(e["custom_pattern_scope"] is not None for e in queue) == 3
write("ACCOUNT_VERIFICATION_QUEUE.json", {
    "schema": "boldstone.current-account-listing-verification-queue.v1", "recorded_utc": now,
    "master_epoch": bind(inputs / "master-register.json"), "entries": queue,
    "conditional_working_tuple_readbacks": conditional, "already_supported_new_links_retained": positives,
    "counts": {"unresolved_cases": 100, "draft_only_SKU_targets": 97, "custom_pattern_scopes": 3, "conditional_native_working_tuple_readbacks": 4, "new_source_bindings_retained": 2},
    "execution_performed": False,
})
with (BASE / "ACCOUNT_LOOKUP_QUEUE.csv").open("w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Catalogue option ID", "Individual sculpture", "Account search terms", "Related native source references", "Draft-only SKU", "Required next evidence", "Current resolution"])
    for e in queue:
        writer.writerow([e["product_id"], e["name"], " | ".join(e["account_search_terms"]), " | ".join(r["offer_ref"] + ": " + str(r["Squarespace_product_id"] or r["Shopify_handle"] or "unbound") for r in e["related_source_candidates"]), (e["individual_draft"] or {}).get("proposed_sku", ""), e["required_evidence"], e["current_resolution"]])

actions = read(PRIOR / "NATIVE_ACTION_DRAFTS.json")
readiness = []
for e in actions["actions"]:
    item = copy.deepcopy(e)
    item["current_gate"] = "NO_AVAILABLE_AUTHENTICATED_STORE_SURFACE"
    item["owner_authorization"] = "User explicitly requested work on these prepared corrections/SKU-overlap actions; do not ask for the same approval again. Access is separate."
    if e.get("catalogue_option_id") == "BSI-70C7029C1DB1":
        item["additional_execution_dependency"] = "Implement a consistent enquiry/purchase flow together with price-on-enquiry copy. The copy request alone does not remove nativeGBP800 checkout pricing; do not encode a zero-priced product."
    readiness.append(item)
write("ACTION_READINESS.json", {
    "schema": "boldstone.authorized-listing-action-readiness.v1", "recorded_utc": now,
    "status": "PREPARED; WAITING_FOR_WORKING_STORE_CONNECTION",
    "prior_sealed_actions": bind(PRIOR / "NATIVE_ACTION_DRAFTS.json"), "actions": readiness,
    "request_count": 7, "already_executed": 0,
    "shared_master_writes": 0, "Dropbox_or_platform_mutations": 0,
    "resume_rule": "Verify the current account/site and native before-values; stop on concurrent changes. Apply bounded authorized actions and record separate write/readback receipts. Keep all source snapshots immutable.",
})
write("LOCAL_VALIDATION.json", {
    "schema": "boldstone.listing-execution-readiness-validation.v1", "recorded_utc": now,
    "status": "PASS_LOCAL_QUEUE_AND_DRAFT_READBACK", "queue_cases": len(queue),
    "draft_SKUs": 97, "conditional_working_tuples": 4, "new_supported_links_retained": 2,
    "native_requests_prepared": len(readiness), "native_requests_executed": 0,
    "catalogue_ID_or_specification_changes": 0,
})
print(json.dumps({"status": "PREPARED_NO_NATIVE_EXECUTION", "queue_cases": 100, "conditional_tuples": 4, "retained_links": 2, "actions": 7}))
