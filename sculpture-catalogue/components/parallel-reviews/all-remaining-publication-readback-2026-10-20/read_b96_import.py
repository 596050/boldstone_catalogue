"""Independently compare B96's frozen decisions with imported model and ledger."""
from pathlib import Path
import datetime
import hashlib
import json

B = Path(__file__).resolve().parent
C = B.parents[2]
R = C / "components/reviews"
SOURCE = B.parent / "remaining-lane-b-working-specs-2026-10-20"
IMPORT = R / "parallel-import-2026-10-19-batch96"


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


checks = []


def check(name, good, detail=None):
    checks.append({"name": name, "status": "PASS" if good else "FAIL", "detail": detail})


receipt = read(IMPORT / "import-receipt.json")
shared_path = R / "specification_review_progress.json"
ledger_path = R / "user_classifications.json"
shared_bytes = shared_path.read_bytes()
ledger_bytes = ledger_path.read_bytes()
shared = json.loads(shared_bytes)
ledger = json.loads(ledger_bytes)
package = read(SOURCE / "IMPORT_PACKAGE.json")
by_decision = {read(x["decision"]["path"])["decision_id"]: x for x in package["existing_scopes"]}
check("Exact forty decision IDs in receipt", {x["decision_id"] for x in receipt["scopes"]} == set(by_decision) and len(receipt["scopes"]) == 40)
selected = []
for item in receipt["scopes"]:
    source_ref = by_decision[item["decision_id"]]["decision"]
    expected = read(source_ref["path"])
    key = expected["scope_key"]
    node = shared
    for name in item["model_locator"]:
        node = node[name]
    imported_path = C / item["approval_record"]
    imported = read(imported_path)
    approved = [d for d in ledger[item["ledger"]] if d.get("decision_id") == expected["decision_id"]]
    check(key + ": ledger decision exactly once", len(approved) == 1)
    check(key + ": name and approval retained", node.get("canonical_name") == expected["canonical_name"] and node.get("specifications_approved", node.get("specification_fields_fully_approved", False)))
    check(key + ": immutable raw six-field dictionaries", imported.get("source_specification_proposals_retained") == expected["source_specification_proposals_retained"] and imported.get("source_current_specification_proposals_retained") == expected["source_current_specification_proposals_retained"])
    historical_values = node.get("specification_proposals", node.get("specifications", []))
    check(key + ": historical proposal layer preserved", historical_values == expected["source_current_specification_proposals_retained"])
    values = node.get("accepted_working_specifications", historical_values)
    values = list(values.values()) if isinstance(values, dict) else values
    props = {p.get("proposal_id", p.get("id")): p for p in values}
    check(key + ": six source proposal IDs retained", set(props) == set(expected["approved_proposal_ids"]))
    for field, value in expected["specifications"].items():
        got = props.get(value["proposal_id"], {})
        check(key + ": " + field + " working data exact",
              all(got.get(k) == value.get(k) for k in ["display", "basis", "value", "source_original_field_retained", "source_current_field_retained"]) and
              got.get("owner_approved") and got.get("owner_accepted") and not got.get("physical_specs_verified"),
              {"proposal_id": value["proposal_id"], "display": got.get("display")})
    reference = node.get("current_dropbox_reference", {})
    primary = reference.get("file_id") or node.get("current_primary_image_id") or node.get("primary_image_id") or node.get("source_asset_id")
    folder = reference.get("folder_id") or node.get("current_primary_folder_id") or node.get("primary_folder_id") or node.get("source_folder_id")
    check(key + ": image and folder IDs retained", primary == expected["primary_file_id"] and folder == expected["folder_id"])
    check(key + ": physical boundary retained", not node.get("physical_specs_verified") and not imported.get("actual_stock_verified") and
          imported.get("per_card_owner_reply_received") is False and imported.get("new_BC_component_ids") == [])
    check(key + ": full context retained in imported evidence", imported.get("context_images") == expected["context_images"])
    coverage = node.get("photo_coverage", {})
    if expected["context_images"]["selected_context_available"]:
        check(key + ": contextual photo flag applied", coverage.get("contextual_images_available") is True)
    check(key + ": context evidence and photo-gap record", bool(node.get("context_output_review")) and
          item["photo_gap_id"] in shared["current_component_photograph_gaps"])
    selected.append({"scope_key": key, "model_locator": item["model_locator"], "source_decision": source_ref,
                     "imported_approval": ref(imported_path), "context_output_review": node.get("context_output_review")})

check("Frozen source manifest unchanged", all(sha(x["path"]) == x["sha256"] for x in read(SOURCE / "SEALED_MANIFEST.json")["files"]))
failed = [c for c in checks if c["status"] == "FAIL"]
result = {
    "schema": "boldstone.b96.independent-shared-import-readback.v1",
    "status": "PASS" if not failed else "FAIL",
    "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "receipt": ref(IMPORT / "import-receipt.json"),
    "shared_progress": {"path": str(shared_path), "sha256": hashlib.sha256(shared_bytes).hexdigest()},
    "ledger": {"path": str(ledger_path), "sha256": hashlib.sha256(ledger_bytes).hexdigest()},
    "checks_passed": len(checks)-len(failed), "checks_failed": len(failed), "checks": checks,
    "scope_count": 40, "working_field_groups": 240, "selected": selected,
    "coordinator_independent_receipt_exists": (IMPORT / "independent-readback.json").exists(),
    "checker_layer_correction": "Read current accepted_working_specifications separately from the deliberately unchanged historical specification_proposals/specifications. The first reader selected the historical layer and reported false field-ID mismatches; that failed receipt remains immutable.",
    "prior_checker_failure": ref(B / "B96_IMPORT_READBACK_20261020T155155Z.json") if (B / "B96_IMPORT_READBACK_20261020T155155Z.json").exists() else None,
    "workbook_publication_checked_here": False, "shared_writes_by_lane": 0, "remote_mutations": 0,
}
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
out = B / ("B96_IMPORT_READBACK_" + stamp + ".json")
assert not out.exists()
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "checks_passed": result["checks_passed"], "checks_failed": len(failed),
                  "failed_names": [x["name"] for x in failed], "receipt": ref(out)}))
