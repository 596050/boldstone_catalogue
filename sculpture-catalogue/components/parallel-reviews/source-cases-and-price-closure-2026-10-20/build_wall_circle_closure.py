"""Prepare an isolated, evidence-bound Wall Circle import proposal."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
PROOF = CAT / "components/reconciliation/product-register-lane-b-audit-2026-10-20/WALL_CIRCLE_REGISTER_SUPPLEMENT_VERIFIED.json"
EXPECTED_PROOF = "e27efbd04455587ef38beaedbca1ad7018eb317c772f890d1f1d509e13a0c1dc"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dbx_hash(path: Path) -> str:
    total = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            total.update(hashlib.sha256(chunk).digest())
    return total.hexdigest()


def write(name: str, value: dict) -> None:
    path = BASE / "wall-circle" / name
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


assert digest(PROOF) == EXPECTED_PROOF
proof = json.loads(PROOF.read_text())
assert proof["status"] == "PASS"
inputs_path = BASE / "wall-circle/native-visual-inputs.json"
inputs = json.loads(inputs_path.read_text())
assert len(inputs["records"]) == 18
assert len(inputs["boards"]) == 6
observations = []
all_ids = set()
for entry in inputs["records"]:
    native = entry["native_image"]
    assert digest(Path(native["path"])) == native["sha256"]
    assert dbx_hash(Path(native["path"])) == native["dropbox_content_hash"]
    assert len(entry["candidates"]) == 2
    assert len(set(entry["native_option_ids"])) == 8
    for candidate in entry["candidates"]:
        assert candidate["file_id"] not in all_ids
        all_ids.add(candidate["file_id"])
        assert digest(Path(candidate["path"])) == candidate["sha256"]
        assert dbx_hash(Path(candidate["path"])) == candidate["dropbox_content_hash"]
        assert candidate["sha256"] != native["sha256"]
    observations.append({
        **entry,
        "review_method": "Full composition viewed on native-size comparison board; source originals independently byte-checked against saved hashes.",
        "visual_finding": "VISUALLY_CONFIRMED_SAME_SWATCH_COMPOSITION",
        "specific_basis": "Matching texture boundaries, fragment layout, veins and crop across native pattern image and both cached Dropbox representations.",
        "byte_equality": False,
        "scope": "Named catalogue pattern image to historical texture-swatch representation only.",
        "not_established": ["WC-01 to WC-07 visual-name alias", "same physical cast", "chemical finish", "manufacture of each option", "physical stock"],
    })
assert len(all_ids) == 36
now = datetime.now(timezone.utc).isoformat()
visual = {
    "schema": "boldstone.wall-circle-native-swatch-visual-review.v1",
    "reviewed_utc": now,
    "reviewer": "parent A lane; model visual inspection",
    "input_manifest": {"path": str(inputs_path), "sha256": digest(inputs_path)},
    "boards": [{"path": p, "sha256": digest(Path(p))} for p in inputs["boards"]],
    "records": observations,
    "counts": {"native_patterns": 18, "dropbox_representations": 36, "visually_reviewed_matches": 36},
    "new_remote_reads": 0,
    "current_server_presence_or_revision_verified": False,
    "historical_cache_evidence_preserved": True,
}
write("NATIVE_SWATCH_VISUAL_REVIEW.json", visual)

options = copy.deepcopy(proof["native_options"])
review_by_id = {option: record for record in observations for option in record["native_option_ids"]}
assert len(review_by_id) == 144
for option in options:
    review = review_by_id[option["variant_id"]]
    assert option["attributes"]["Pattern"] == review["pattern"]
    option["dropbox_exact_image_binding"] = "VISUALLY_CONFIRMED_SAME_SWATCH_COMPOSITION; ENCODED_BYTES_DIFFER"
    for candidate in option["dropbox_image_candidates"]:
        assert candidate["file_id"] in {c["file_id"] for c in review["candidates"]}
        candidate["evidence_level"] = "VISUALLY_CONFIRMED_SAME_SWATCH_COMPOSITION"
        candidate["current_path_verified_in_this_batch"] = False
    option["relationship_to_visual_review_names"] = "UNRESOLVED; DO_NOT_SUM_OR_AUTOMERGE_WITH_WC01_TO_WC07"
    option["pattern_image_binding_scope"] = "Cached texture swatch composition; no claim of byte equality or physical specimen identity."

combinations = [tuple(sorted(o["attributes"].items())) for o in options]
assert len(set(combinations)) == len(options) == 144
axes = proof["native_option_axes"]
assert (len(axes["Pattern"]), len(axes["Diameter Size"]), len(axes["Lighting"])) == (18, 4, 2)
visual_path = BASE / "wall-circle/NATIVE_SWATCH_VISUAL_REVIEW.json"
closure = {
    "schema": "boldstone.wall-circle-option-case-closure-proposal.v1",
    "prepared_utc": now,
    "candidate_id": "CAND-WALL-CIRCLE",
    "configuration_id": "CFG-348134C39A",
    "component_id": "BC-WALL-CIRCLE",
    "proposed_review_status": "CLOSED_AS_SEPARATE_VISUAL_WORKING_AND_NATIVE_OPTION_LAYERS",
    "proposed_disposition": "RETAIN_ONE_FAMILY_WITH_SEVEN_APPROVED_VISUAL_REFERENCES_AND_144_DATED_NATIVE_OPTIONS",
    "authority": json.loads((BASE / "owner-instruction.json").read_text()),
    "existing_family_approval_evidence": proof["family_owner_evidence"],
    "verified_source_proof": {"path": str(PROOF), "sha256": EXPECTED_PROOF},
    "swatch_visual_review": {"path": str(visual_path), "sha256": digest(visual_path)},
    "sale_unit_decision": "One Wall Circle in one selected pattern, diameter and lighting option. The family header and swatch photographs add no sculpture unit.",
    "native_option_axes": axes,
    "native_option_count": 144,
    "native_product_id": proof["native_product_id"],
    "native_product_url": proof["native_product_url"],
    "native_options": options,
    "dated_native_source_prices_by_diameter_gbp": proof["source_price_by_diameter_gbp"],
    "native_source_price_state": "Dated source offer claims retained, not freshly verified current platform prices.",
    "visual_working_records": proof["visual_working_records"],
    "working_50cm_template_scope": proof["family_working_50cm_template"],
    "source_disposition": proof["preferred_register_disposition"],
    "remaining_limits": [
        "Seven owner-kept visual descriptions have no exact crosswalk to the eighteen native pattern names; do not add the two layers or invent aliases.",
        "WC-01 owner facts stay at WC-01 scope. Other visual entries retain their previously accepted proposal/estimate labels.",
        "No conversion of unknown-unit native raw weight or depth values.",
        "Native unlimited-stock setting does not verify stock, lead time, or manufacture of every combination.",
        "Saved paths are historical source pointers, not a live path verification in this batch.",
    ],
    "new_owner_approval_events": 0,
    "new_physical_stock_or_mould_claims": 0,
    "new_remote_reads": 0,
    "remote_writes": 0,
    "shared_master_writes": 0,
    "import_owner": "Main/root coordinator only",
}
write("WALL_CIRCLE_CASE_CLOSURE.json", closure)
print(json.dumps({"status": "PREPARED", "visual_matches": 36, "native_options": 144, "visual_records": 7, "closure_sha256": digest(BASE / "wall-circle/WALL_CIRCLE_CASE_CLOSURE.json")}))
