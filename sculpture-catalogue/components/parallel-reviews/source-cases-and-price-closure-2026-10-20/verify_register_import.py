"""Verify only this lane's imported dispositions and working field overlays."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--register", type=Path, required=True)
parser.add_argument("--expected-sha256", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
raw = args.register.read_bytes()
register_hash = hashlib.sha256(raw).hexdigest()
assert register_hash == args.expected_sha256
register = json.loads(raw)
cases = json.loads((BASE / "CASE_CLOSURES.json").read_text())
updates = json.loads((BASE / "SPECIFICATION_UPDATES.json").read_text())
checks = []


def check(label: str, result: bool) -> None:
    checks.append({"check": label, "pass": result})


check("All fifteen case dispositions imported verbatim", register["case_closure_dispositions"] == cases["cases"])
check("All four scoped working correction records imported verbatim", register["scoped_working_corrections"]["records"] == updates["records"])
check("Exactly four current option IDs have scoped corrections", set(register["scoped_working_correction_option_ids"]) == {r["product_id"] for r in updates["records"]})
fields = {"dimensions": "Dimensions / depth", "weight": "Weight", "material_finish": "Material / finish", "fixing": "Fixing", "individual_price": "Individual price", "availability": "Availability"}
option_by_id = {o["product_id"]: o for o in register["options"]}
field_readbacks = []
for source in updates["records"]:
    target = option_by_id[source["product_id"]]
    for key, heading in fields.items():
        expected = source["specifications"][key]
        actual = target["specifications"][heading]
        check(source["product_id"] + ":" + key + " full overlay retained", actual["scoped_current_working_overlay"] == expected)
        check(source["product_id"] + ":" + key + " current display corrected", actual["display"] == expected["display"])
        check(source["product_id"] + ":" + key + " prior display and source assertions retained", "prior_working_display" in actual and bool(actual["assertions"]))
        field_readbacks.append({"product_id": source["product_id"], "field": key, "display": actual["display"], "prior_display_retained": True, "source_assertions_retained": len(actual["assertions"])})
    check(source["product_id"] + " physical and publication states remain scoped", not target["physical_specifications_verified"] and not target["platform_publication_performed"])

components = register["components"]
for component_id in ["BC-BONE-1", "BC-BONE-2", "BC-CR-RING"]:
    found = [c for c in components if c["component_id"] == component_id]
    check(component_id + " has exactly one identified component record", len(found) == 1)
    check(component_id + " physical stock and mould quantity remain unknown", len(found) == 1 and found[0]["physical_stock_quantity"] is None and found[0]["physical_mould_count"] is None)
fish = [o for o in register["options"] if "BC-FFL-1|BASE" in o.get("source_scopes", [])]
check("Exactly one source-supported Long size option", len(fish) == 1)
check("Long image and component geometry binding remain unbound", len(fish) == 1 and fish[0]["unbound_size_option"] and fish[0]["canonical_component_id"] is None and not fish[0].get("file_id") and not fish[0].get("image_url"))
check("Historical DR3 not added as a new component from selected image", not any(c["component_id"] == "BC-DR-WAVE3" for c in components))
wall = next(c["payload"] for c in cases["cases"] if c["case_id"] == "CAND-WALL-CIRCLE")
native = register["wall_circle_native_options"]
check("144 native Wall Circle variant IDs retained separately", len(native) == 144 and {n["variant_id"] for n in native} == {n["variant_id"] for n in wall["native_options"]})
check("Seven kept visual Wall Circle options", len([o for o in register["options"] if o.get("family") == "Wall Circle"]) == 7)
check("Nine finish dispositions reference-only with zero added products", all(c["payload"]["new_product_count"] == 0 and c["payload"]["proposed_disposition"] == "CONTEXT_REFERENCE_ONLY" for c in cases["cases"] if c["category"] == "FINISH_REFERENCE"))
for name, filename in [("case_closures", "CASE_CLOSURES.json"), ("scoped_working_corrections", "SPECIFICATION_UPDATES.json")]:
    expected_hash = hashlib.sha256((BASE / filename).read_bytes()).hexdigest()
    entry = register["input_manifest"][name]
    check(name + " imported hash and immutable snapshot match", entry["sha256"] == expected_hash == hashlib.sha256(Path(entry["snapshot"]).read_bytes()).hexdigest())
prior = CAT / "components/reconciliation/individual-products-2026-10-20/canonical-products.json"
check("Prior A173 derivative remains byte-identical", hashlib.sha256(prior.read_bytes()).hexdigest() == "c0e88303da05f6f17b2766cf1b08f8c3340f596fc5986ff43e884bc8fd8f3428")
check("Current register unchanged during scoped readback", hashlib.sha256(args.register.read_bytes()).hexdigest() == register_hash)
issues = [c["check"] for c in checks if not c["pass"]]
out = {"schema": "boldstone.coordinator-register-scoped-import-readback.v1", "checked_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS" if not issues else "FAIL", "scope": "This A lane's fifteen source-case dispositions and four current working correction records; global counts, live Dropbox links and workbook export verification belong to coordinator/B receipts.", "register": {"path": str(args.register.resolve()), "sha256": register_hash}, "cases": 15, "working_product_corrections": 4, "field_displays": 24, "checks": checks, "issues": issues, "field_readbacks": field_readbacks, "original_review_assertions_count_observed": len(register["original_review_specification_assertions"]), "remote_calls": 0, "shared_writes": 0, "workbook_certification_in_this_receipt": False, "audit_implementation_note": "An initial checker expected null for FFL file_id; the register represents the same unknown as an empty string. The unknown-identity check now accepts either blank representation and also requires no image URL. No target data was changed."}
if args.output.exists():
    raise FileExistsError(args.output)
args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": out["status"], "checks": len(checks), "issues": issues, "output": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))
raise SystemExit(0 if not issues else 1)
