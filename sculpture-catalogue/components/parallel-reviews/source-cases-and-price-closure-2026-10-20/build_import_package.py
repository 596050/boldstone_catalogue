"""Bind sealed source-case work to owner authority without editing shared masters."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
MAIN_THREAD = "01a144ab-1a7c-7223-a403-73a4d53d70ff"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(relative: str) -> dict:
    return json.loads((BASE / relative).read_text())


def reference(relative: str) -> dict:
    p = BASE / relative
    return {"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size}


def write(name: str, value: dict) -> None:
    p = BASE / name
    if p.exists():
        raise FileExistsError(p)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


authority = load("owner-instruction.json")
with Path(authority["transcript"]).open() as stream:
    for line_number, raw in enumerate(stream, 1):
        if line_number == authority["line"]:
            assert hashlib.sha256(raw.encode()).hexdigest() == authority["raw_line_sha256"]
            assert hashlib.sha256(authority["text"].encode()).hexdigest() == authority["text_sha256"]
            event = json.loads(raw)
            assert event["payload"]["role"] == "user"
            assert authority["text"] == "\n".join(part["text"] for part in event["payload"]["content"] if "text" in part)
            break
    else:
        raise AssertionError("Owner instruction transcript line missing")

frozen = load("input-manifest.json")
for item in frozen["inputs"]:
    assert sha(Path(item["snapshot"])) == item["sha256"]

design = load("worker-01/closure-proposals.json")
finish = load("worker-02/proposed_dispositions.json")
price = load("worker-03/four-product-closure-proposals.json")
wall = load("wall-circle/WALL_CIRCLE_CASE_CLOSURE.json")
assert load("worker-01/validation.json")["status"] == "PASS"
assert sha(BASE / "worker-01/closure-proposals.json") == "ad4c1c6b6a1ad462b0f24542dee7dd7bf3f90fe6493987fa9d4c9310556cd3db"
assert load("worker-02/VALIDATION.json")["cases"] == 9
assert load("worker-03/readback-validation.json")["status"] == "PASS"
assert sha(BASE / "worker-02/proposed_dispositions.json") == "93308a89c4f00c52c65ba95dc244c51035a291142b568f9ac16d1a6dd797d416"
assert sha(BASE / "worker-03/four-product-closure-proposals.json") == "ca1738b1bdb2182c87d0142c9052252c777c780e3bd7e3e16aacafd06c1861e2"
assert sha(BASE / "wall-circle/WALL_CIRCLE_CASE_CLOSURE.json") == "e4a11b4cef786129d9597c42210ada7d75eddf6afb6825b31ba7aded047552bb"

baseline = load("inputs/canonical-products.json")
candidate_by_component = {c["component_id"]: c["candidate_id"] for c in baseline["source_candidates"]}
finish_candidate_by_configuration = {configuration: c["candidate_id"] for c in baseline["additional_source_candidates"] for configuration in c["source_configuration_ids"]}
cases = []
for entry in design["entries"]:
    cases.append({
        "case_id": candidate_by_component[entry["component_id"]],
        "category": "DESIGN_OR_SALE_UNIT",
        "review_outcome": entry["closure"],
        "case_closure_scope": "Current catalogue disposition; remaining physical, photographic and historical-code limits retained in evidence.",
        "source_packet": reference("worker-01/closure-proposals.json"),
        "payload": entry,
    })
cases.append({
    "case_id": wall["candidate_id"],
    "category": "DESIGN_OR_SALE_UNIT",
    "review_outcome": wall["proposed_review_status"],
    "case_closure_scope": "Native sale options and previously accepted visual records reconciled as overlapping layers; no invented crosswalk.",
    "source_packet": reference("wall-circle/WALL_CIRCLE_CASE_CLOSURE.json"),
    "payload": wall,
})
for entry in finish["cases"]:
    cases.append({
        "case_id": finish_candidate_by_configuration[entry["configuration_id"]],
        "category": "FINISH_REFERENCE",
        "review_outcome": entry["proposed_review_status"],
        "case_closure_scope": "Source reference disposition only; no new individually sellable finish or chemical certificate.",
        "source_packet": reference("worker-02/proposed_dispositions.json"),
        "payload": entry,
    })
assert len(cases) == len({c["case_id"] for c in cases}) == 15
assert {c["case_id"] for c in cases if c["category"] == "DESIGN_OR_SALE_UNIT"} == {c["candidate_id"] for c in baseline["source_candidates"]}
assert {c["case_id"] for c in cases if c["category"] == "FINISH_REFERENCE"} == {c["candidate_id"] for c in baseline["additional_source_candidates"]}
now = datetime.now(timezone.utc).isoformat()
common = {
    "prepared_utc": now,
    "owner_authority": authority,
    "bound_prior_working_configuration_graph_sha256": frozen["inputs"][0]["sha256"],
    "sole_shared_register_and_workbook_writer": MAIN_THREAD,
    "shared_master_import_performed_by_this_lane": False,
    "remote_writes": 0,
    "new_live_reads": 0,
    "new_owner_keep_or_individual_reply_events": 0,
}
closures = {
    "schema": "boldstone.fifteen-source-case-dispositions.v1",
    **common,
    "status": "OWNER_AUTHORIZED_IMPORT_READY; INDEPENDENT_PARENT_PACKAGE_CHECK_PENDING",
    "cases": cases,
    "counts": {"design_option_cases_reviewed": 6, "finish_reference_cases_reviewed": 9, "total_cases": 15},
    "working_record_actions": {
        "retain_or_promote_two_owner_kept_bone_components": 2,
        "source_supported_cup_ring_individual": 1,
        "documented_long_fish_size_option_without_exact_image_binding": 1,
        "extra_historical_dr3_product_from_selected_image": 0,
        "wall_circle_existing_approved_visual_records_to_restore": 7,
        "wall_circle_native_options_retained_separately": 144,
        "finish_cases_retained_as_reference_only": 9,
        "deduplicated_finish_source_groups": 7,
        "global_new_product_or_stock_total": None,
    },
    "counting_limit": "Main coordinator owns whole-library count semantics. Size options, component geometries, media, arrangements, physical mould inventory and physical stock are separate quantities; these local actions are not an additive global total.",
    "design_source_references": design["source_refs"],
    "finish_reference_groups": finish["reference_groups"],
    "remaining_specific_evidence_limits": [
        "Cup Ring has a complete ring visible in a paired reference and a labelled complete maker illustration; an isolated current full-product photograph remains missing.",
        "Frozen Fish Long is documented as an individually sellable100×22cm option associated with the source Frozen Fish Solo family; exact current image and same-geometry relationship to short models remain unbound.",
        "Historical DR3 selected image is already an alias/reference to existing DR1-WHITE; a whole historical mould-code crosswalk remains unresolved.",
        "Wall Circle's seven kept visual names have no exact crosswalk to eighteen native patterns. Both are retained without summing or automatic aliasing.",
        "The nine finish references are preserved as two surface details and seven source-case group/scene contexts. Individual finish allocation and chemical composition have not been certified.",
    ],
}
write("CASE_CLOSURES.json", closures)

records = copy.deepcopy(price["records"])
assert len(records) == 4 and all(len(r["specifications"]) == 6 for r in records)
updates = {
    "schema": "boldstone.price-size-normalization-import-package.v1",
    **common,
    "status": "OWNER_AUTHORIZED_IMPORT_READY; INDEPENDENT_PARENT_PACKAGE_CHECK_PENDING",
    "source_packet": reference("worker-03/four-product-closure-proposals.json"),
    "source_evidence": reference("worker-03/source-evidence.json"),
    "records": records,
    "counts": {"existing_products": 4, "normalized_fields": 24, "accepted_working_numeric_prices": 3, "price_on_enquiry": 1},
    "additional_enquiry_record_fields": [
        {"component_id": e["component_id"], "source_scope": e["source_scope"], "identity_state": e["identity_state"], "specifications": e["specifications"], "source_packet": reference("worker-01/closure-proposals.json")}
        for e in design["entries"] if e["component_id"] != "BC-DR-WAVE3"
    ],
    "historical_source_claims": "Retain every raw source assertion and accepted historical event; normalize the current working display without overwriting source history.",
    "publication_scope": "Local catalogue review only. No website, Shopify, Squarespace, pricing feed or Dropbox write.",
}
write("SPECIFICATION_UPDATES.json", updates)

sources = [
    "input-manifest.json", "owner-instruction.json", "fake-adapter-gate.json",
    "worker-01/closure-proposals.json", "worker-01/validation.json", "worker-01/visual-review-manifest.json",
    "worker-02/proposed_dispositions.json", "worker-02/IMAGE_REVIEW.json", "worker-02/VALIDATION.json",
    "worker-03/four-product-closure-proposals.json", "worker-03/source-evidence.json", "worker-03/readback-validation.json",
    "wall-circle/WALL_CIRCLE_CASE_CLOSURE.json", "wall-circle/NATIVE_SWATCH_VISUAL_REVIEW.json", "wall-circle/native-visual-inputs.json",
]
write("SOURCE_MANIFEST.json", {
    "schema": "boldstone.source-case-import-manifest.v1", "prepared_utc": now,
    "source_packets": [reference(s) for s in sources],
    "frozen_historical_inputs": frozen["inputs"],
    "derived_import_payloads": [reference("CASE_CLOSURES.json"), reference("SPECIFICATION_UPDATES.json")],
    "prior_derivative_not_modified": True,
    "no_remote_mutations": True,
})
write("HANDOFF_STATUS.json", {
    "schema": "boldstone.source-case-handoff-status.v1", "prepared_utc": now,
    "status": "PREPARED_AWAITING_INDEPENDENT_PACKAGE_AUDIT",
    "recipient_thread": MAIN_THREAD,
    "owner_authority": reference("owner-instruction.json"),
    "manifest": reference("SOURCE_MANIFEST.json"),
    "shared_import_confirmed": False,
    "remote_mutations": 0,
    "live_sandbox_tests_run": False,
    "fake_adapter_gate": reference("fake-adapter-gate.json"),
    "remaining_limits": closures["remaining_specific_evidence_limits"],
})
print(json.dumps({"status": "PREPARED", "cases": 15, "price_products": 4, "case_payload_sha256": sha(BASE / "CASE_CLOSURES.json"), "specification_payload_sha256": sha(BASE / "SPECIFICATION_UPDATES.json")}))
