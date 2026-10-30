"""Read back the assembled proposal, its evidence identities and preserved values."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CATALOGUE = BASE.parents[2]
checks = []
files = {}
parsed = {}
historical_resolutions = json.loads((BASE / "HISTORICAL_REFERENCE_RESOLUTIONS.json").read_text())["resolutions"]


def check(label, condition):
    checks.append({"check": label, "pass": bool(condition)})


def read(name):
    return json.loads((BASE / name).read_text())


def pointer(doc, value):
    if not value:
        return doc
    for token in value.strip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        doc = doc[int(token)] if isinstance(doc, list) else doc[token]
    return doc


def inspect_refs(value, context):
    if isinstance(value, dict):
        if "path" in value and ("sha256" in value or "body_sha256" in value):
            path = Path(value["path"])
            if not path.is_absolute():
                path = CATALOGUE / path
            if str(path) not in files:
                raw = path.read_bytes()
                files[str(path)] = (hashlib.sha256(raw).hexdigest(), raw)
            sha, raw = files[str(path)]
            expected = value.get("sha256", value.get("body_sha256"))
            if sha != expected:
                recovered = next((r for r in historical_resolutions if r["original_path"] == value["path"] and r["expected_historical_sha256"] == expected), None)
                if recovered:
                    historical = Path(recovered["historical_snapshot"]["path"]).read_bytes()
                    check(f"dated source exact bytes recovered {context}", hashlib.sha256(historical).hexdigest() == expected)
                    raw = historical
                else:
                    check(f"source hash {context}", False)
            else:
                check(f"source hash {context}", True)
            if "bytes" in value:
                check(f"source byte count {context}", len(raw) == value["bytes"])
            if "json_pointer" in value:
                try:
                    if str(path) not in parsed:
                        parsed[str(path)] = json.loads(raw)
                    pointer(parsed[str(path)], value["json_pointer"])
                    valid = True
                except (ValueError, KeyError, IndexError, TypeError):
                    valid = False
                check(f"source JSON pointer {context}", valid)
        for key, item in value.items():
            inspect_refs(item, f"{context}/{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            inspect_refs(item, f"{context}/{i}")


master = read("inputs/master-register.json")
original = {e["product_id"]: e for e in master["options"]}
payload = read("LISTING_RESOLUTION.json")
scope = read("OPTION_RESOLUTIONS_106.json")
four = read("FOUR_LISTING_CORRECTIONS.json")
edges = read("NEW_SOURCE_LINKS.json")
actions = read("NATIVE_ACTION_DRAFTS.json")
fresh = read("worker-01/FRESH_PUBLIC_INVENTORY.json")
inventory = {e["native_product_id"]: e for e in fresh["products"]}
variants = {v["native_variant_id"]: (e, v) for e in fresh["products"] for v in e["variants"]}
assigned = read("ASSIGNED_106_SCOPE.json")["records"]
check("184 original unique IDs", len(original) == len(master["options"]) == 184)
check("1104 original working field groups", sum(len(e["master_fields"]) for e in original.values()) == 1104)
check("184 overlay IDs unique and exactly preserved", len(payload["option_overlays"]) == 184 and {e["product_id"] for e in payload["option_overlays"]} == set(original))
check("106 assigned IDs covered exactly once", len(scope["entries"]) == 106 and len({e["product_id"] for e in scope["entries"]}) == 106 and {e["product_id"] for e in scope["entries"]} == {e["product_id"] for e in assigned})
check("all original81 offers retained", len(master["current_listing_source_links"]["offers"]) == 81)
check("all original262 edges retained", len(master["current_listing_match_evidence"]["edges"]) == 262)
for e in payload["option_overlays"]:
    old = original[e["product_id"]]
    check(f"identity unchanged {e['product_id']}", e["name"] == old["name"] and e["canonical_key"] == old["canonical_key"])
    check(f"no physical exactness upgrade {e['product_id']}", e["exact_current_physical_or_all_six_field_configuration_certified"] is False)
    check(f"no prior positive downgrade {e['product_id']}", e["prior_native_binding_downgraded"] is False)
for e in scope["entries"]:
    pid = e["product_id"]
    check(f"six exact accepted working fields {pid}", e["accepted_working_fields"] == original[pid]["master_fields"])
    check(f"scope does not prove live absence {pid}", e["proven_live_absent"] is False)
    check(f"scope does not claim admin/physical check {pid}", not e["physical_configuration_verified"] and not e["authenticated_admin_inventory_verified"])
    if e["conditional_native_tuple"]:
        v = e["conditional_native_tuple"]
        product, native = variants[v["native_variant_id"]]
        check(f"real WC native tuple {pid}", native["sku"] == v["sku"] and native["option_attributes"]["Diameter Size"] == "50cm/19.7in" and native["option_attributes"]["Lighting"] == "RGB Color Light" and product["native_product_id"] == v["native_product_id"])
        check(f"conditional pattern label {pid}", e["pattern_assignment"]["state"] == "CONDITIONAL_VISUAL_PATTERN_DESIGN_LINK" and not e["pattern_assignment"]["formal_owner_native_pattern_declaration_found"])
    if e["custom_unlisted_pattern_draft"]:
        custom = e["custom_unlisted_pattern_draft"]
        check(f"WC custom no native identifier {pid}", custom["native_variant_id"] is None and custom["native_sku"] is None and custom["proposed_new_native_variant"] is False)
    for match in e["supported_source_matches"]:
        if match["platform"] == "Squarespace":
            product, native = variants[match["native_variant_id"]]
            check(f"new native match exact IDs/SKU/attributes {pid}", product["native_product_id"] == match["native_product_id"] and native["sku"] == match["sku_raw"] and native["option_attributes"] == match["option_attributes"])
            check(f"new match retains raw current price {pid}", native["price"] == match["native_price"])
            check(f"new match limited logical scope {pid}", match["physical_configuration_verified"] is False and match["all_six_native_fields_equal_to_working_fields"] is False)
        else:
            check(f"historical Shopify numeric IDs not invented {pid}", match["numeric_product_id"] is None and match["numeric_variant_id"] is None and match["current_live_inventory_verified"] is False)
    draft = e["draft_listing"]
    if draft:
        check(f"draft fields exact {pid}", draft["six_working_fields"] == original[pid]["master_fields"])
        check(f"draft identifier labelled {pid}", draft["sku_state"] == "PROPOSED_ONLY_NOT_AN_EXISTING_PLATFORM_IDENTIFIER" and draft["proposed_sku"].startswith("DRAFT-") and draft["current_native_target"] is None)

new_ids = {e["option_id"] for e in edges["edges"]}
check("exactly two new supported option links", new_ids == {"BSI-09C1A55D460D", "BSI-46F6DB226213"})
check("three additive source edges", len(edges["edges"]) == 3 and len({e["evidence_edge_id"] for e in edges["edges"]}) == 3)
check("47 source-supported individual design options", sum(e["source_supported_individual_record_present"] for e in payload["option_overlays"]) == 47)
check("4 conditional WC lookups distinct from positive links", sum(e["conditional_native_tuple"] is not None for e in scope["entries"]) == 4)
check("100 gap/candidate cases still explicit", sum(not e["source_supported_individual_record_added"] and not e["conditional_native_tuple"] for e in scope["entries"]) == 100)
check("3 custom WC scopes", sum(e["custom_unlisted_pattern_draft"] is not None for e in scope["entries"]) == 3)

drafts = [e["draft_listing"] for e in scope["entries"] if e["draft_listing"]]
draft_skus = [e["proposed_sku"] for e in drafts]
check("97 unique draft-only SKUs", len(draft_skus) == len(set(draft_skus)) == 97)
check("76 nonwall component/design groups", len({e["proposed_product_group_id"] for e in drafts}) == 76)
native_skus = {v["sku"] for p in fresh["products"] for v in p["variants"]}
historical_shopify = json.loads((BASE.parent / "listing-reconciliation-2026-10-20/worker-02/shopify_variants.json").read_text())
def sku_values(value):
    found = set()
    if isinstance(value, dict):
        for k, v in value.items():
            if "sku" in k.lower() and isinstance(v, str) and v:
                found.add(v)
            else:
                found |= sku_values(v)
    elif isinstance(value, list):
        for v in value:
            found |= sku_values(v)
    return found
native_skus |= sku_values(historical_shopify)
check("draft-only SKUs avoid checked current and historical native identifiers", not (set(draft_skus) & native_skus))
legacy = next(e for e in actions["actions"] if e["action_id"] == "RUST-SKU-COLLISION:LEGACY-SKU")
check("legacy SKU not in checked sources or draft set", legacy["proposed_sku"] not in native_skus | set(draft_skus) and len(legacy["proposed_sku"]) <= 60)
check("original SKU collision in exact two expected records", {p["native_product_id"] for p in fresh["products"] for v in p["variants"] if v["sku"] == "EBAY-188654649217"} == {"6aa01aad7f3077314dd71e8c", "6a5a621422d8fb7a65ba5a77"})
for e in four["records"]:
    check(f"four correction fields exact {e['product_id']}", e["accepted_working_specifications"] == {k: v["display"] for k, v in original[e["product_id"]]["master_fields"].items()})
    check(f"four correction shipping unchanged {e['product_id']}", e["shipping_measurements_policy"]["action"] == "NO_CHANGE")
check("7 request drafts prepared only", len(actions["actions"]) == 7)
for e in actions["actions"]:
    req = e["request_draft"]
    check(f"request not executable/executed {e['action_id']}", req["executable_now"] is False and e["execution_status"] == "NOT_EXECUTED")
    allowed = {"name", "description"} if e["action_type"] == "EXISTING_PRODUCT_COPY_CORRECTION_DRAFT" else ({"sku"} if e["action_type"] == "EXISTING_VARIANT_SKU_CORRECTION_DRAFT" else {"isVisible"})
    check(f"partial request exact field boundary {e['action_id']}", set(req["body"]) == allowed and all(v.get("present") is True for v in req["body"].values()))
    check(f"request native target exists {e['action_id']}", any(p in req["path"] for p in inventory))
check("O009 existing generic binding retained", read("worker-02/PRIOR_POSITIVE_ASSOCIATION_AUDIT.json")["entries"][0]["option_id"] == "BSI-4536FDCA0DA9")
check("no platform writes", payload["counts"]["platform_writes"] == 0 and actions["status"] == "REVIEWABLE_DRAFTS; NO_PLATFORM_EXECUTION")
for name in ["LISTING_RESOLUTION.json", "OPTION_RESOLUTIONS_106.json", "FOUR_LISTING_CORRECTIONS.json", "NEW_SOURCE_LINKS.json", "NATIVE_ACTION_DRAFTS.json", "IMPORT_PLAN.json"]:
    inspect_refs(read(name), name)
csv_rows = list(csv.DictReader((BASE / "RESOLUTION_REVIEW.csv").open()))
check("review CSV same184 IDs and order", [r["product_id"] for r in csv_rows] == [r["product_id"] for r in payload["option_overlays"]])
failures = [e for e in checks if not e["pass"]]
out = {
    "schema": "boldstone.parent-listing-resolution-readback.v1",
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS_BOUNDED_EVIDENCE_AND_DRAFTS" if not failures else "FAIL",
    "checks_passed": len(checks) - len(failures), "checks_total": len(checks),
    "unique_source_files_hash_verified": len(files), "failures": failures, "checks": checks,
    "platform_writes": 0, "shared_master_writes": 0,
}
(BASE / "VALIDATION.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: v for k, v in out.items() if k != "checks"}, indent=2))
raise SystemExit(bool(failures))
