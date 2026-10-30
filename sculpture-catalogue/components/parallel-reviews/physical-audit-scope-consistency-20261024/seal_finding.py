"""Record a read-only comparison of the bound audit and current checklist."""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
TARGET = "BSI-C3AA3700F7DA"
FIELDS = ["Dimensions / depth", "Weight", "Material / finish", "Fixing"]
sources = {}


def read_source(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    sources[str(path)] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    return raw


def read_json(path):
    return json.loads(read_source(path))


def save(name, value):
    with (HERE / name).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


pointer_path = BASE / "current-master.json"
pointer = read_json(pointer_path)
register_path = BASE / pointer["register"]
register = read_json(register_path)
assert sources[str(register_path.resolve())]["sha256"] == pointer["register_sha256"]
scope = pointer["current_specification_verification"]
ledger_path = BASE / scope["physical_source_evidence_ledger"]
ledger = read_json(ledger_path)
assert sources[str(ledger_path.resolve())]["sha256"] == scope["physical_source_evidence_ledger_sha256"]
report_path = BASE / scope["path"]
report = read_json(report_path)
assert sources[str(report_path.resolve())]["sha256"] == scope["sha256"]
csv_path = BASE / Path(scope["physical_source_evidence_review"]).parent / "Physical_Source_Audit_752_Field_Groups.csv"
reader = csv.reader(io.StringIO(read_source(csv_path).decode("utf-8-sig"), newline=""))
headers = next(reader)
rows = []
prior_end = reader.line_num
for record, values in enumerate(reader, 2):
    assert len(values) == len(headers)
    rows.append({"csv_record_including_header": record, "physical_line_start": prior_end + 1,
                 "physical_line_end": reader.line_num, "values": dict(zip(headers, values))})
    prior_end = reader.line_num
active = {o["product_id"]: o for o in register["options"] if o["product_id"] in register["active_option_ids"]}
audited = {o["option_id"]: o for o in ledger["options"]}
assert set(active) - set(audited) == {TARGET} and not set(audited) - set(active)
assert len(active) == 188 and len(audited) == 187 and len(rows) == 752
assert len(ledger["field_rows"]) == 748
assert {(x["values"]["option_id"], x["values"]["field"]) for x in rows} == {(i, f) for i in active for f in FIELDS}
for item in rows:
    row = item["values"]
    assert row["working_detail"] == active[row["option_id"]]["master_fields"][row["field"]]["display"]
    assert row["new_physical_verification"] == "False"
for option_id, old in audited.items():
    for field in old["physical_fields"]:
        current = active[option_id]["master_fields"][field["field"]]
        for current_key, historical_key in [("display", "current_working_detail"), ("state", "recorded_state"), ("basis", "recorded_basis")]:
            assert current.get(current_key, "") == field.get(historical_key, "")
target_rows = [x for x in rows if x["values"]["option_id"] == TARGET]
assert len(target_rows) == 4 and sum(int(x["values"]["source_assertions"]) for x in rows) == 684
target = active[TARGET]
for row in target_rows:
    assert row["values"]["source_assertions"] == "0"
    for key in ["image_url", "folder_url", "file_id", "folder_id"]:
        assert row["values"][key] == target[key]
finding = {
    "schema": "boldstone.physical-audit-scope-consistency.v1",
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "status": "DIVERGENT_SCOPE_CONFIRMED_NO_SHARED_CHANGES",
    "source_thread_id": "01a13fe6-495b-7253-b923-31823b4cbca8",
    "published_register": sources[str(register_path.resolve())],
    "bound_pointer_fields": {k: scope[k] for k in ["physical_source_evidence_ledger", "physical_source_evidence_ledger_sha256", "physical_options_source_audited", "physical_field_groups_source_audited", "new_physical_field_groups_source_reviewed"]},
    "bound_ledger_summary": ledger["summary"],
    "report_count_fields": {k: report["counts"][k] for k in ["physical_options_source_audited", "physical_field_groups_source_audited", "physical_options_source_audited_this_refresh", "physical_field_groups_source_audited_this_refresh", "new_physical_verifications"]},
    "checklist_scope": {"options": 188, "field_groups": 752, "source_assertions": 684, "new_physical_verifications": 0},
    "comparison": {"checklist_values_matching_current_master": 752, "historical_options_with_unchanged_physical_displays_states_and_bases": 187, "current_options_absent_from_bound_ledger": [TARGET], "historical_options_absent_from_current_register": [], "missing_from_checklist": [], "target_csv_source_assertions": 0},
    "target": {k: target[k] for k in ["product_id", "name", "image_url", "folder_url", "file_id", "folder_id", "photo_coverage"]},
    "target_csv_rows": target_rows,
    "scope_explanation": "The 188-option/752-row checklist includes four qualified comparator or offered-choice rows for MSW2 water. The pointer-bound structured source audit retains 187 options/748 groups and does not contain that option. Checklist presence is not a new physical verification or a new historical source assertion.",
    "handoff": "Main writer to reconcile the pointer, structured source-audit scope and report labels after Spiralmoon publication. Preserve the historical 187-option audit and qualified estimates; do not silently relabel it as 188 options. No duplicate physical walkthrough or owner question requested.",
    "shared_files_written": 0,
    "native_writes": 0,
    "new_physical_reviews_performed": 0,
    "accepted_fields_changed": 0,
    "sources": list(sources.values()),
}
for source in sources.values():
    if source["path"] != str(pointer_path.resolve()):
        assert hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() == source["sha256"]
finding["pointer_unchanged_during_read"] = hashlib.sha256(pointer_path.read_bytes()).hexdigest() == sources[str(pointer_path.resolve())]["sha256"]
save("consistency-finding.json", finding)
seal = {"status": "SEALED_BOUNDED_FINDING", "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "files": [{"path": str(HERE / name), "sha256": hashlib.sha256((HERE / name).read_bytes()).hexdigest()} for name in ["consistency-finding.json", "seal_finding.py"]],
        "shared_writes": 0, "native_writes": 0}
save("sealed-handoff.json", seal)
print(json.dumps({"status": finding["status"], "matching_values": 752, "missing_ledger_option": TARGET,
                  "seal": str(HERE / "sealed-handoff.json"), "seal_sha256": hashlib.sha256((HERE / "sealed-handoff.json").read_bytes()).hexdigest()}))
