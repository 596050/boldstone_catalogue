"""Prepare four scoped working-specification updates for the sole master writer."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
PREVIOUS = CAT / "components/parallel-reviews/source-cases-and-price-closure-2026-10-20"
REGISTER = CAT / "components/reconciliation/individual-catalogue-count-2026-10-20/canonical-count-register.json"
EXPECTED_REGISTER = "fd08a1759bcabacd2b332188a83ca17644ca3fb25086e44cb801daad66e6e2a0"
SOURCE_EXPECTED = {
    PREVIOUS / "SPECIFICATION_UPDATES.json": "bf53fd5a5e87e666ee6ab5d8044418db35035ee988917f9f0b718b07e5347a0f",
    PREVIOUS / "worker-01/closure-proposals.json": "ad4c1c6b6a1ad462b0f24542dee7dd7bf3f90fe6493987fa9d4c9310556cd3db",
    PREVIOUS / "worker-03/FINAL_INDEPENDENT_PACKAGE_CHECK.json": "2814217969e3651c15e1dc35e03985c60c8e8cdb5b44e0955ee78e8a032c1307",
}
FIELDS = {"dimensions": "Dimensions / depth", "weight": "Weight", "material_finish": "Material / finish", "fixing": "Fixing", "individual_price": "Individual price", "availability": "Availability"}
TARGETS = {"BC-BONE-1", "BC-BONE-2", "BC-CR-RING", "BC-FFL-1"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def obj_hash(obj: object) -> str:
    return sha(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def write(name: str, value: dict) -> None:
    p = BASE / name
    if p.exists():
        raise FileExistsError(p)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


authority = json.loads((BASE / "owner-instruction.json").read_text())
with Path(authority["transcript"]).open() as stream:
    for number, raw_line in enumerate(stream, 1):
        if number != authority["line"]:
            continue
        event = json.loads(raw_line)
        text = "\n".join(c["text"] for c in event["payload"]["content"] if "text" in c)
        assert event["payload"]["role"] == "user" and text == authority["text"]
        assert sha(text.encode()) == authority["text_sha256"]
        assert sha(raw_line.encode()) == authority["raw_line_sha256"]
        break
    else:
        raise AssertionError("Exact owner instruction not found")

manifest = []
for path, expected in SOURCE_EXPECTED.items():
    raw = path.read_bytes()
    assert sha(raw) == expected
    manifest.append({"path": str(path), "sha256": expected, "bytes": len(raw)})
register_raw = REGISTER.read_bytes()
assert sha(register_raw) == EXPECTED_REGISTER
snapshot = BASE / "inputs/canonical-count-register.json"
if snapshot.exists():
    raise FileExistsError(snapshot)
snapshot.write_bytes(register_raw)
register = json.loads(register_raw)
source = json.loads((PREVIOUS / "SPECIFICATION_UPDATES.json").read_text())
design = json.loads((PREVIOUS / "worker-01/closure-proposals.json").read_text())
source_fields = {r["component_id"]: r for r in source["additional_enquiry_record_fields"]}
assert set(source_fields) == TARGETS
entries = {e["component_id"]: e for e in design["entries"] if e["component_id"] in TARGETS}
source_hash_checks = {}
for ref in design["source_refs"].values():
    if "path" in ref and "sha256" in ref:
        path = Path(ref["path"])
        if not path.is_absolute():
            path = CAT / path
        key = (str(path), ref["sha256"])
        if key not in source_hash_checks:
            actual = sha(path.read_bytes())
            assert actual == ref["sha256"], str(path)
            source_hash_checks[key] = {"path": str(path), "sha256": actual, "pass": True}

records = []
for component_id in ["BC-BONE-1", "BC-BONE-2", "BC-CR-RING", "BC-FFL-1"]:
    prepared = source_fields[component_id]
    matches = [o for o in register["options"] if prepared["source_scope"] in o.get("source_scopes", [])]
    assert len(matches) == 1
    option = matches[0]
    assert not option["six_working_fields_recorded"]
    assert set(prepared["specifications"]) == set(FIELDS)
    before = {"product_id": option["product_id"], "source_scopes": option["source_scopes"], "record_type": option["record_type"], "six_working_fields_recorded": option["six_working_fields_recorded"], "specifications": option["specifications"]}
    specifications = {}
    for key, heading in FIELDS.items():
        field = copy.deepcopy(prepared["specifications"][key])
        assert field["display"] and not field["physical_verification_performed"]
        assert field["working_acceptance"] == "OWNER_AUTHORIZED_WORKING_ACCEPTANCE_UNDER_STANDING_POLICY"
        assert not field["requires_repeat_owner_approval"]
        current = copy.deepcopy(option["specifications"][heading])
        current["prior_working_display"] = current["display"]
        current["prior_working_accepted"] = current.get("working_accepted", False)
        current["display"] = field["display"]
        current["working_accepted"] = True
        current["source_field_record"] = field
        current["working_completion_overlay"] = {
            "normalization_id": "FOUR-WORKING-SPEC-COMPLETE:20261020:" + component_id + ":" + key,
            "prepared_source_field": field,
            "owner_authority_ref": "owner-instruction.json",
            "acceptance_scope": "WORKING_SPECIFICATION_ONLY",
            "physical_value_verified": False,
            "source_packet_sha256": SOURCE_EXPECTED[PREVIOUS / "SPECIFICATION_UPDATES.json"],
            "source_locator": "additional_enquiry_record_fields[component_id=" + component_id + "].specifications." + key,
        }
        specifications[heading] = current
    assert prepared["specifications"]["individual_price"]["proposal"]["price_on_enquiry"]
    availability = prepared["specifications"]["availability"]["proposal"]
    assert availability["made_to_order_proposal"] and availability["stock_quantity"] is None and availability["lead_time"] is None

    if component_id.startswith("BC-BONE-"):
        record_type = "INDIVIDUAL_WORKING_ENQUIRY_PRODUCT"
        note = "Six working specifications complete. Price on enquiry for one component; made to order as working availability. Actual cast measurements, material recipe, installed hardware/load, stock and lead time remain unverified. Dated weight conflicts are retained as source evidence."
    elif component_id == "BC-CR-RING":
        record_type = option["record_type"]
        note = "Six working specifications complete. Price on enquiry for one Cup Ring; made to order as working availability. A complete isolated current photograph remains missing; current cast measurements, installed hardware/load, stock and lead time remain unverified."
    else:
        record_type = option["record_type"]
        note = "Six working specifications complete for the documented100×22cm Long option. Price on enquiry; made to order as working availability. Exact current photograph and component geometry parent remain unbound; measurements, installed hardware/load, stock and lead time remain unverified."
    records.append({
        "component_id": component_id,
        "product_id": option["product_id"],
        "canonical_key": option["canonical_key"],
        "name": option["name"],
        "source_scope": prepared["source_scope"],
        "before_target_fingerprint": obj_hash(before),
        "before_target": before,
        "after_flags": {
            "six_working_fields_recorded": True,
            "working_specification_status": "COMPLETE_SIX_WORKING_FIELDS",
            "physical_specifications_verified": False,
            "record_type": record_type,
            "readiness_note": note,
            "working_commercial_policy": "PRICE_ON_ENQUIRY; MADE_TO_ORDER_WORKING_AVAILABILITY; STOCK_AND_LEAD_TIME_UNKNOWN",
        },
        "specifications": specifications,
        "unchanged_identity_and_media": {k: option.get(k) for k in ["canonical_design_id", "canonical_component_id", "option_family_id", "source_scopes", "file_id", "folder_id", "image_url", "folder_url", "unbound_size_option", "owner_name_keep_recorded", "identity_decision", "source_size_relationship"] if k in option},
        "remaining_evidence_gaps": entries[component_id]["missing_evidence"],
        "remaining_gaps_interpretation": "Evidence, measured-product and fixed-price gaps remain visible. They are independent of completion of the six accepted working fields; the commercial working value is enquiry, with stock and lead time unknown.",
    })

now = datetime.now(timezone.utc).isoformat()
packet = {
    "schema": "boldstone.four-working-spec-completion.v1",
    "prepared_utc": now,
    "status": "OWNER_AUTHORIZED_IMPORT_READY_PENDING_INDEPENDENT_CHECK",
    "owner_authority": authority,
    "baseline_register": {"path": str(REGISTER), "snapshot": str(snapshot), "sha256": EXPECTED_REGISTER},
    "prepared_specification_source": manifest[0],
    "source_identity_packet": manifest[1],
    "previous_independent_source_check": manifest[2],
    "source_refs": design["source_refs"],
    "records": records,
    "counts": {"existing_options": 4, "working_fields": 24, "completion_flags_false_to_true": 4, "bone_missing_prices_resolved_as_enquiry": 2, "new_products": 0, "new_component_identities": 0},
    "completion_definition": "Six nonblank, source-bound working values accepted under standing policy and this exact current owner instruction. Complete does not mean measured, chemically verified, fixed-price retail-ready, physically in stock, or photographically complete.",
    "expected_working_coverage_after_import": {"total_options": 184, "six_working_fields_recorded_true": 184, "six_working_fields_recorded_false": 0},
    "import_rules": [
        "Only the four named product IDs and their six working fields/statuses are in scope. Preserve all other option records.",
        "Compare each target fingerprint, not merely the global graph hash; rebase unrelated verified link changes without overwriting them.",
        "Copy prior display/acceptance and assertions as historical evidence; retain source_field_record and working_completion_overlay.",
        "Apply after_flags to the existing option. Preserve identity, counts, media bindings, photo/geometry gaps and all historical owner decisions.",
        "Maintain enquiry/MTO qualifications and unknown stock/lead time; do not allocate pair prices or claim a current numeric retail quote.",
        "Keep previous count register/workbook and all sealed inputs as immutable historical versions; append the new current projection and receipt.",
    ],
    "sole_shared_writer_thread": "01a144ab-1a7c-7223-a403-73a4d53d70ff",
    "new_owner_name_or_identity_events": 0,
    "physical_verification_performed": False,
    "remote_reads": 0,
    "remote_writes": 0,
    "shared_master_writes_by_A": 0,
}
assert len(records) == len({r["product_id"] for r in records}) == 4
assert sum(len(r["specifications"]) for r in records) == 24
write("SPECIFICATION_COMPLETION.json", packet)
write("INPUT_MANIFEST.json", {"schema": "boldstone.four-working-spec-inputs.v1", "prepared_utc": now, "sources": manifest, "baseline": packet["baseline_register"], "owner_instruction_sha256": sha((BASE / "owner-instruction.json").read_bytes()), "historical_source_hash_checks": list(source_hash_checks.values()), "historical_inputs_modified": False, "shared_writes": 0})
print(json.dumps({"status": "PREPARED", "records": 4, "fields": 24, "packet_sha256": sha((BASE / "SPECIFICATION_COMPLETION.json").read_bytes()), "source_files_rehashed": len(source_hash_checks)}))
