"""Read-only checks of the scoped MSW2 Water owner image-policy import."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def record(path):
    return {"path": str(path), "sha256": digest(path)}


parser = argparse.ArgumentParser()
parser.add_argument("register", type=Path)
parser.add_argument("--expected-sha", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--published", action="store_true")
args = parser.parse_args()
lane = Path(__file__).resolve().parent
root = lane.parents[2]
approval_path = lane / "owner-approved-group-listing-reference.json"
approval = read(approval_path)
target = approval["product_id"]
before_ref = approval["current_master_at_acceptance"]["register"]
before = read(before_ref["path"])
candidate_start_sha = digest(args.register)
after = read(args.register)
checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})


check("Exact owner receipt unchanged", digest(approval_path) == "a80b9f582a48962209c81fecae2a39f9125c472d6a4148a6e8ff7ac2e73d7db9")
check("Exact owner reply retained", approval["owner_text"] == "group image")
check("Baseline register unchanged", digest(before_ref["path"]) == before_ref["sha256"])
check("Candidate identity matches declared version", candidate_start_sha == args.expected_sha)
old_options = {x["product_id"]: x for x in before["options"]}
new_options = {x["product_id"]: x for x in after["options"]}
check("All retained option identities preserved without duplicates", len(after["options"]) == len(new_options) == 189 and set(old_options) == set(new_options))
check("188 active options preserved", sum(bool(x.get("counted_as_individual_option")) and x.get("catalogue_status") != "Retired" for x in after["options"]) == 188)
check("Other option objects unchanged", all(new_options[k] == v for k, v in old_options.items() if k != target))
for key in ["canonical_key", "canonical_design_id", "name", "sale_unit", "specifications", "master_fields", "selling_details", "file_id", "folder_id", "image_url", "folder_url", "context_file_id", "context_folder_id", "context_image_url", "context_folder_url", "photo_coverage", "current_component_source_scope", "physical_specifications_verified", "platform_publication_performed", "current_listing_resolution", "current_listing_reconciliation"]:
    check("Target preserved: " + key, old_options[target].get(key) == new_options[target].get(key))

old_cov = read(before["latest_image_coverage_audit"]["path"])
cov_path = Path(after["latest_image_coverage_audit"]["path"])
coverage = read(cov_path)
coverage_start_sha = digest(cov_path)
old_rows = {x["option_id"]: x for x in old_cov["coverage"]}
new_rows = {x["option_id"]: x for x in coverage["coverage"]}
check("Coverage rows preserved", set(old_rows) == set(new_rows))
check("Other coverage rows unchanged", all(new_rows[k] == v for k, v in old_rows.items() if k != target))
for role in ["in_situ", "series"]:
    check("Target " + role + " role unchanged", old_rows[target][role] == new_rows[target][role])
check("Target series requirement unchanged", old_rows[target]["series_required"] == new_rows[target]["series_required"])
individual = new_rows[target]["individual"]
for key in ["status", "reference", "physical_cast_or_size_certified", "exact_member_position", "complete_standalone_image"]:
    check("Individual source fact preserved: " + key, individual.get(key) == old_rows[target]["individual"].get(key))
check("Technical photo coverage remains Group only", individual["status"] == "Group only" and individual["complete_standalone_image"] is False)
counts = coverage["counts"]
active_actions = [x for x in coverage["missing_pictures"] if x.get("status") in ["Open", "Optional"]]
check("Active role counts match underlying rows", counts["actions_by_role"] == dict(Counter(x["role"] for x in active_actions)))
check("Active type counts match underlying rows", counts["actions_by_type"] == dict(Counter(x["action_type"] for x in active_actions)))
check("Active row count matches underlying rows", counts["active_action_rows"] == len(active_actions))
check("Required row count matches underlying rows", counts["required_picture_actions"] == sum(x.get("status") == "Open" for x in coverage["missing_pictures"]))
check("Resolved row count matches underlying rows", counts["resolved_action_rows"] == sum(x.get("status") == "Resolved" for x in coverage["missing_pictures"]))
for key, expected in {"individual_gaps": 1, "separate_photographs_required": 0, "legacy_identity_deferred": 1, "technical_individual_gaps": 11, "scoped_accepted_group_or_combined_exceptions": 10}.items():
    check("Coverage queue count: " + key, coverage["individual_capture_queue_counts"].get(key) == expected)
for key, expected in {"individual_options": 188, "technical_individual_reference_gaps": 11, "outstanding_individual_image_or_identity_actions": 1, "separate_individual_photographs_required": 0, "owner_accepted_group_or_combined_reference_exceptions": 10, "required_picture_actions": 24}.items():
    check("Coverage count: " + key, counts.get(key) == expected)
for key in ["individual_statuses", "in_situ_statuses", "series_statuses", "series_required_options"]:
    check("Technical count unchanged: " + key, counts[key] == old_cov["counts"][key])
requirements = after["current_individual_photo_capture_policy"]["current_requirements"]
for key, expected in {"individual_gaps": 1, "separate_individual_images_required": 0, "deferred_identity": 1, "technical_individual_gaps": 11, "scoped_accepted_group_or_combined_exceptions": 10}.items():
    check("Capture requirement: " + key, requirements.get(key) == expected)
old_exceptions = before["current_individual_photo_capture_policy"]["current_requirements"]["scoped_owner_exception_option_ids"]
check("Only this owner exception added", set(requirements["scoped_owner_exception_option_ids"]) == set(old_exceptions) | {target})
check("Coverage/register capture policy agrees", coverage["current_individual_photo_capture_policy"]["current_requirements"] == requirements)
source_path = Path(after["latest_active_photo_source_review"]["path"])
source = read(source_path)
source_start_sha = digest(source_path)
old_source = read(before["latest_active_photo_source_review"]["path"])
check("No active source photo requests remain", source["requests"] == [])
for key in ["held_requests", "held_context_cases", "global_context_owner_hold", "held_series_requests", "held_series_cases", "owner_optional_series_requests", "owner_optional_series_policies"]:
    check("Held/optional source policy preserved: " + key, source.get(key) == old_source.get(key))
check("Source report hash bound to register", source_start_sha == after["latest_active_photo_source_review"]["sha256"])
corpus = json.dumps([after, coverage, source], ensure_ascii=False)
check("Exact approval receipt bound in candidate", digest(approval_path) in corpus)
check("Approved one-panel caption retained", approval["approved_caption"] in corpus)

published = None
if args.published:
    pointer_path = root / "current-master.json"
    pointer_bytes = pointer_path.read_bytes()
    pointer = json.loads(pointer_bytes)
    check("Published pointer names candidate register", (root / pointer["register"]).resolve() == args.register.resolve())
    check("Published register hash matches", pointer["register_sha256"] == candidate_start_sha)
    check("Published workbook bytes match pointer", digest(root / pointer["workbook"]) == pointer["workbook_sha256"])
    check("Published active/retained counts agree", pointer["current_option_count"] == 188 and pointer["retained_option_count"] == 189)
    check("Published pointer stable during readback", pointer_path.read_bytes() == pointer_bytes)
    published = {"pointer": record(pointer_path), "workbook": {"path": str(root / pointer["workbook"]), "sha256": pointer["workbook_sha256"]}}
check("Read inputs stable", digest(args.register) == candidate_start_sha and digest(cov_path) == coverage_start_sha and digest(source_path) == source_start_sha)
failed = [x["name"] for x in checks if not x["passed"]]
result = {"schema": "boldstone.scoped-group-listing-policy-readback.v1", "recorded_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS" if not failed else "FAIL", "scope": "MSW2 White Water Feature image policy and preserved canonical evidence only. Platform draft action audit belongs to reviewer A; workbook contents are not inspected here.", "register": record(args.register), "coverage": record(cov_path), "source_review": record(source_path), "approval": record(approval_path), "publication": published, "checks": checks, "failed_checks": failed, "canonical_writes": 0, "native_mutations": 0, "platform_mutations": 0}
with args.output.open("x") as stream:
    json.dump(result, stream, indent=2, ensure_ascii=False)
    stream.write("\n")
print(json.dumps({"status": result["status"], "passed": len(checks) - len(failed), "total": len(checks), "failed": failed, "receipt": record(args.output)}))
raise SystemExit(bool(failed))
