"""Read back only the four completed specification records from the current master."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--register", type=Path, required=True)
parser.add_argument("--expected-sha256", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
raw = args.register.read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == args.expected_sha256
master = json.loads(raw)
packet_path = BASE / "SPECIFICATION_COMPLETION.json"
packet = json.loads(packet_path.read_text())
assert hashlib.sha256(packet_path.read_bytes()).hexdigest() == "4ac180fca5f9495d85dcf4624449ea34e5136f20a699e14df47ad9ff9ce34285"
baseline = json.loads((BASE / "inputs/canonical-count-register.json").read_text())
checks = []


def check(label: str, passed: bool) -> None:
    checks.append({"check": label, "pass": passed})


options = master["options"]
index = {o["product_id"]: o for o in options}
check("Same184 product IDs and option count as baseline", len(options) == 184 and set(index) == {o["product_id"] for o in baseline["options"]})
check("All184 options have six working fields complete", all(o.get("six_working_fields_recorded") and len(o["specifications"]) == 6 for o in options))
field_readbacks = []
for record in packet["records"]:
    actual = index[record["product_id"]]
    for name, expected in record["after_flags"].items():
        check(record["component_id"] + ":" + name, actual.get(name) == expected)
    for name, expected in record["unchanged_identity_and_media"].items():
        check(record["component_id"] + ":retained:" + name, actual.get(name) == expected)
    for heading, expected in record["specifications"].items():
        field = actual["specifications"][heading]
        check(record["component_id"] + ":" + heading + ":display", field["display"] == expected["display"])
        check(record["component_id"] + ":" + heading + ":accepted", field.get("working_accepted") is True)
        check(record["component_id"] + ":" + heading + ":source and qualifications", field.get("source_field_record") == expected["source_field_record"] and field.get("working_completion_overlay") == expected["working_completion_overlay"])
        check(record["component_id"] + ":" + heading + ":history", field.get("assertions") == expected.get("assertions") and field.get("prior_working_display") == expected["prior_working_display"] and field.get("prior_working_accepted") == expected["prior_working_accepted"])
        field_readbacks.append({"product_id": record["product_id"], "field": heading, "display": field["display"], "working_accepted": field.get("working_accepted"), "physical_verification_performed": field["source_field_record"]["physical_verification_performed"]})
    check(record["component_id"] + ":no physical verification claim", actual["physical_specifications_verified"] is False)
    check(record["component_id"] + ":stock and lead time unknown", actual["specifications"]["Availability"]["source_field_record"]["proposal"]["stock_quantity"] is None and actual["specifications"]["Availability"]["source_field_record"]["proposal"]["lead_time"] is None)
    check(record["component_id"] + ":enquiry price with no invented amount", actual["specifications"]["Individual price"]["source_field_record"]["proposal"]["price_on_enquiry"] and actual["specifications"]["Individual price"]["source_field_record"]["proposal"]["amount"] is None)
check("111 component identities retained", len(master["components"]) == 111 and {c["component_id"] for c in master["components"]} == {c["component_id"] for c in baseline["components"]})
check("Sealed prior count register remains immutable", hashlib.sha256(Path(packet["baseline_register"]["path"]).read_bytes()).hexdigest() == packet["baseline_register"]["sha256"])
check("Master unchanged during scoped readback", hashlib.sha256(args.register.read_bytes()).hexdigest() == digest)
issues = [c["check"] for c in checks if not c["pass"]]
receipt = {"schema": "boldstone.four-working-spec-import-readback.v1", "checked_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS" if not issues else "FAIL", "scope": "Four-record working-specification import and184working-field coverage; workbook/export and broader link checks belong to coordinator receipts.", "register": {"path": str(args.register.resolve()), "sha256": digest}, "packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(), "records": 4, "fields": 24, "checks": checks, "issues": issues, "field_readbacks": field_readbacks, "remote_reads": 0, "remote_writes": 0, "shared_writes": 0}
if args.output.exists():
    raise FileExistsError(args.output)
args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": receipt["status"], "checks": len(checks), "issues": issues, "receipt": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}))
raise SystemExit(0 if not issues else 1)
