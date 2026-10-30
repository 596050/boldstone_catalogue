"""Independently check the serialized metadata-only alignment candidate."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
CANDIDATE = BASE / "components/reconciliation/physical-audit-ledger-alignment-master-2026-10-24"
TARGET = "BSI-C3AA3700F7DA"
FIELDS = {"Dimensions / depth", "Weight", "Material / finish", "Fixing"}
checks = []
sources = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path).resolve()
    sources[str(path)] = sha(path)
    return json.loads(path.read_text())


def check(name, passed, detail=None):
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def csv_rows(path):
    sources[str(Path(path).resolve())] = sha(path)
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


manifest = read(CANDIDATE / "input-manifest.json")
for name, item in manifest.items():
    check("snapshot digest: " + name, sha(item["snapshot"]) == item["sha256"])
old = read(manifest["master_register"]["snapshot"])
new = read(CANDIDATE / "canonical-master-register.json")
ledger = read(CANDIDATE / "physical-source-audit.json")
prior = read(manifest["legacy_ledger"]["snapshot"])
report = read(CANDIDATE / "report-verification.json")
check("requested candidate bytes", sha(CANDIDATE / "canonical-master-register.json") == "342cbb76f5cf228e4b06c4e5243481257bf088217be0ca98e1ca2ef9a2c57c34")
check("requested ledger bytes", sha(CANDIDATE / "physical-source-audit.json") == "0b00d1a5ae0ac475ba1f2e1f74c0f825f1d750c960a82bdb19bd7da81eb92d80")
changed = [k for k in old.keys() | new.keys() if old.get(k) != new.get(k)]
check("only two audit metadata fields differ", set(changed) == {"latest_physical_source_audit", "latest_physical_audit_scope_alignment"}, sorted(changed))
check("every product option unchanged", old["options"] == new["options"])
active = {x["product_id"]: x for x in new["options"] if x["product_id"] in new["active_option_ids"]}
check("188 active options unchanged", len(active) == 188 and old["active_option_ids"] == new["active_option_ids"])
check("historical 187 option records preserved", ledger["options"][:187] == prior["options"])
check("historical 748 field rows preserved", ledger["field_rows"][:748] == prior["field_rows"])
check("historical source validation preserved", ledger["recorded_source_reference_validation"] == prior["recorded_source_reference_validation"])
check("one added option only", len(ledger["options"]) == 188 and ledger["options"][-1]["option_id"] == TARGET)
check("all active options covered once", Counter(x["option_id"] for x in ledger["options"]) == Counter({k: 1 for k in active}))
flat = [f for o in ledger["options"] for f in o["physical_fields"]]
check("nested and flat rows agree", flat == ledger["field_rows"])
expected_keys = {(i, f) for i in active for f in FIELDS}
actual_keys = [(x["option_id"], x["field"]) for x in flat]
check("752 distinct physical field groups", len(flat) == 752 and len(set(actual_keys)) == 752 and set(actual_keys) == expected_keys)
added = ledger["field_rows"][748:]
check("four added fields have exact target scope", len(added) == 4 and all(x["option_id"] == TARGET for x in added) and {x["field"] for x in added} == FIELDS)
check("no added historical source assertions", all(x["source_assertions"] == [] and x["source_assertions_count"] == 0 for x in added))
check("684 source assertions retained", sum(x["source_assertions_count"] for x in flat) == sum(len(x["source_assertions"]) for x in flat) == 684)
check("zero physical verification flags", all(x["physically_verified"] is False and x["new_measurement_or_hardware_evidence"] is False for x in flat) and all(x["complete_physical_verification"] is False for x in ledger["options"]))
check("added rows retain explicit qualifications", all(x["verification_outcome"] == "QUALIFIED_ESTIMATE_OR_COMPARATOR; NOT_PHYSICALLY_VERIFIED" and "zero independent water-build source assertions" in x["source_scope_limit"] for x in added))
details_match = all(all(x[a] == active[x["option_id"]]["master_fields"][x["field"]][b] for a, b in [("current_working_detail", "display"), ("recorded_state", "state"), ("recorded_basis", "basis")]) for x in flat)
check("752 working details, states and bases match register", details_match)
target = active[TARGET]
ref = {k: target[k] for k in ["file_id", "folder_id", "image_url", "folder_url"]}
check("four new rows retain exact approved image and folder", all(x["image_reference"] == ref for x in added))
check("new rows retain comparator references", all(x["working_source_references"] == target["master_fields"][x["field"]]["source_references"] for x in added))
checklist_rows = csv_rows(manifest["current_csv"]["snapshot"])
csv_index = {(x["option_id"], x["field"]): x for x in checklist_rows}
check("current CSV covers same 752 keys", len(checklist_rows) == 752 and set(csv_index) == expected_keys)
check("all CSV details and source counts agree", all(csv_index[(x["option_id"], x["field"])]["working_detail"] == x["current_working_detail"] and int(csv_index[(x["option_id"], x["field"])]["source_assertions"]) == x["source_assertions_count"] and csv_index[(x["option_id"], x["field"])]["new_physical_verification"] == "False" for x in flat))
check("new CSV scope and evidence caveats agree", all(csv_index[(TARGET, x["field"])]["physical_evidence_needed"] == x["requires_object_specific_evidence"] and all(csv_index[(TARGET, x["field"])][k] == v for k, v in ref.items()) for x in added))
inputs = csv_rows(manifest["physical_input"]["snapshot"])
measurement_columns = ["actual_width_cm", "actual_height_cm", "actual_maximum_depth_cm", "bare_panel_measured_weight_kg", "maker_material_recipe", "fitted_fixing_type", "fitted_fixing_count", "measured_or_inspected_by", "measurement_date", "measurement_method", "object_or_batch_reference", "supporting_evidence_reference"]
check("188 measurement-input rows and no entered evidence", len(inputs) == 188 and all(not x[k].strip() for x in inputs for k in measurement_columns))
summary = ledger["summary"]
check("ledger summary matches actual rows", summary["active_options_reviewed"] == 188 and summary["physical_field_groups_reviewed"] == 752 and summary["source_assertions_reviewed"] == 684)
check("summary outcome counts match rows", summary["verification_outcomes"] == dict(Counter(x["verification_outcome"] for x in flat)))
check("summary records four qualified groups and zero new evidence", summary["new_qualified_comparator_field_groups_reviewed"] == 4 and summary["new_independent_physical_source_assertions"] == 0 and summary["new_physical_verifications"] == 0 and summary["rows_with_entered_measurements"] == 0 and summary["accepted_working_fields_changed"] == 0 and summary["physical_access_available"] is False)
expected_summary = {**summary, "ledger_sha256": sha(CANDIDATE / "physical-source-audit.json"), "review": str(BASE / "outputs" / CANDIDATE.name / "physical-ledger-alignment.html")}
check("register summary binds exact corrected ledger", new["latest_physical_source_audit"] == expected_summary)
check("historical navigation explicitly qualified", "original187 recorded image references remain dated evidence" in ledger["scope_alignment_provenance"]["current_navigation_basis"])
check("report count agreement", report["register_sha256"] == sha(CANDIDATE / "canonical-master-register.json") and report["counts"]["physical_options_source_audited"] == 188 and report["counts"]["physical_field_groups_source_audited"] == 752 and report["counts"]["new_physical_verifications"] == 0)
old_dir = Path(manifest["master_register"]["path"]).parent
for name in ["image-coverage-current.json", "current-native-reference-map.json", "current-assets.json", "photo-review-queue.json", "guided-owner-review-state.json", "pending-followups.json"]:
    check("unchanged policies or references: " + name, sha(CANDIDATE / name) == sha(old_dir / name))
check("shared workbook unchanged by bytes", sha(manifest["workbook"]["path"]) == manifest["workbook"]["sha256"] == sha(manifest["workbook"]["snapshot"]))


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.text = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs).get("href", ""))
    def handle_data(self, data):
        self.text.append(data)


page_path = BASE / "outputs" / CANDIDATE.name / "physical-ledger-alignment.html"
page = Page()
page.feed(page_path.read_text())
check("review page has exact image and folder links", target["image_url"] in page.links and target["folder_url"] in page.links)
check("review page preserves all four qualified display strings", all(x["current_working_detail"] in "".join(page.text) for x in added))
check("review page digest matches report", any(x["path"] == str(page_path) and x["sha256"] == sha(page_path) for x in report["pages"]))
source_checks = {}
def inspect_refs(value):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            choices = [value.get("snapshot"), value["path"]]
            source_checks[(value["path"], value["sha256"])] = any(p and Path(p).is_file() and sha(p) == value["sha256"] for p in choices)
        for v in value.values(): inspect_refs(v)
    elif isinstance(value, list):
        for v in value: inspect_refs(v)
inspect_refs([x["working_source_references"] for x in added])
check("new-row recorded proposal references resolve", bool(source_checks) and all(source_checks.values()), {"distinct_references": len(source_checks)})
check("inputs stable during QA", all(sha(path) == digest for path, digest in sources.items()))
receipt = {"status": "PASS" if all(x["passed"] for x in checks) else "FAIL", "recorded_utc": datetime.now(timezone.utc).isoformat(), "checks_passed": sum(x["passed"] for x in checks), "checks_total": len(checks), "checks": checks, "candidate_register_sha256": sha(CANDIDATE / "canonical-master-register.json"), "candidate_ledger_sha256": sha(CANDIDATE / "physical-source-audit.json"), "workbook_sha256": sha(manifest["workbook"]["path"]), "sources": sources, "scope": "Serialized candidate/read-only comparison only; publication and pointer/control alignment are not yet certified.", "review_page": str(page_path), "owner_question_created": False, "shared_or_native_writes": 0, "new_physical_verifications": 0, "script_sha256": sha(__file__)}
destination = HERE / "candidate-readback-342cbb76.json"
with destination.open("x", encoding="utf-8") as f:
    json.dump(receipt, f, ensure_ascii=False, indent=2)
    f.write("\n")
print(json.dumps({"status": receipt["status"], "passed": receipt["checks_passed"], "total": receipt["checks_total"], "failures": [x for x in checks if not x["passed"]], "receipt": str(destination), "sha256": sha(destination)}))
