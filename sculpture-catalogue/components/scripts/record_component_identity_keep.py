"""Record a component name-only keep, preserving unapproved specification proposals."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from review_decision_counts import identity_counts

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / "components/reviews"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-id", required=True)
    parser.add_argument("--user-statement", required=True)
    args = parser.parse_args()
    paths = {"walkthrough": REVIEWS / "walkthrough_checkpoint.json", "user": REVIEWS / "user_classifications.json", "progress": REVIEWS / "specification_review_progress.json", "component": ROOT / "components/checkpoint.json", "root": ROOT / "checkpoint.json"}
    docs = {k: read(p) for k, p in paths.items()}
    cp, user, progress, component = (docs[k] for k in ["walkthrough", "user", "progress", "component"])
    assert cp["current_component_id"] == args.component_id
    source = ROOT / cp["current_review_record"]
    review = read(source)
    assert review["component_id"] == args.component_id and not review.get("variant_only_review", False)
    previous_specs = copy.deepcopy(user["specification_decisions"])
    previous_spec_counts = copy.deepcopy(user["specification_approval_counts"])
    protected = [source, ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"]]
    hashes = {p: digest(p) for p in protected}
    now = datetime.now(timezone.utc).isoformat()
    backup = source.parent / "before-identity-approval.json"
    if not backup.exists():
        write(backup, {"recorded_utc": now, "files": {relative(paths[k]): v for k, v in docs.items()}})
    decision_id = f"{args.component_id}:identity:keep"
    approval_path = source.parent / "identity-approval.json"
    decision = {"schema_version": 1, "decision_id": decision_id, "recorded_utc": now, "component_id": args.component_id, "canonical_name": review["proposed_name"], "confirmed_name": review["proposed_name"], "proposed_name_at_review": review["proposed_name"], "size_finish_variant_id": review.get("size_finish_variant_id"), "review_number": review["review_number"], "family_review_number": review.get("family_review_number", 1), "action": "keep", "user_statement": args.user_statement, "identity_status": "USER CONFIRMED", "status": "USER CONFIRMED NAME AND IDENTITY ONLY", "scope": "The explicit name-only answer confirms this depicted individual component name/identity. The displayed specification proposals, actual measurements/materials/fixings/load, price/stock/lead time and any unresolved platform match remain unapproved. No physical-stock or manufacture confirmation is inferred.", "confirmed_fields": ["component name", "depicted individual component identity", "retain individual component record"], "not_confirmed": [x["field"] for x in review["specification_review_items"]] + review["open_gaps"], "identity_confirmed": True, "specifications_approved": False, "proposals_approved": False, "approved_proposal_ids": [], "physical_specs_verified": False, "proposal_source": relative(source), "proposal_source_sha256": hashes[source], "evidence_file_id": review["primary_image_id"], "containing_folder_id": review["primary_folder_id"], "evidence_file_ids": [review["primary_image_id"]], "containing_folder_ids": [review["primary_folder_id"]], "image_link": review["primary_image_link"], "folder_link": review["primary_folder_link"], "remote_files_changed": False, "live_platform_records_changed": False, "workbook_status": "Unchanged; later user decision stored in review overlay."}
    if approval_path.exists():
        decision = read(approval_path)
        assert decision["decision_id"] == decision_id and decision["proposal_source_sha256"] == hashes[source] and decision["user_statement"] == args.user_statement
    else:
        write(approval_path, decision)
    if not any(x["decision_id"] == decision_id for x in user["decisions"]):
        user["decisions"].append(copy.deepcopy(decision) | {"approval_record": relative(approval_path)})
    names = len({x["component_id"] for x in user["decisions"]})
    user["identity_confirmation_counts"] = identity_counts(user)
    user["updated_utc"] = now
    progress["reviews"][args.component_id].update({"identity_confirmed": True, "identity_confirmed_utc": decision["recorded_utc"], "canonical_name": review["proposed_name"], "identity_approval": relative(approval_path), "specifications_approved": False, "proposals_approved": False, "physical_specs_verified": False, "specification_review_status": "NAME KEPT; SIX SPECIFICATION GROUPS REMAIN PENDING"})
    progress.update({"updated_utc": now, "latest_component_identity_approval": relative(approval_path)})
    queue = cp.setdefault("pending_specification_reviews", [])
    variant_id = review.get("size_finish_variant_id")
    if not any(x.get("component_id") == args.component_id and x.get("size_finish_variant_id") == variant_id for x in queue):
        queue.append({"component_id": args.component_id, "size_finish_variant_id": variant_id, "canonical_name": review["proposed_name"], "identity_approved": True, "specifications_approved": False, "pending_fields": [x["field"] for x in review["specification_review_items"]], "review_record": relative(source), "identity_approval": relative(approval_path), "image_link": review["primary_image_link"], "folder_link": review["primary_folder_link"]})
    cp.update({"state": review["proposed_name"] + " name/identity kept; specifications pending; preparing next review", "current_answer_recorded": True, "current_specification_answer_recorded": False, "working_version_user_approved": False, "last_completed_component_id": args.component_id, "last_completed_review_number": review["review_number"], "last_completed_size_finish_variant_id": variant_id, "last_identity_approval": relative(approval_path), "answer_state": decision["scope"], "updated_utc": now})
    component["interactive_review_state"].update({"state": cp["state"], "explicit_identity_confirmations": names, "last_completed_component_ids": [args.component_id], "last_completed_review_numbers": [review["review_number"]], "last_completed_size_finish_variant_id": variant_id, "last_identity_approval": relative(approval_path), "specification_proposals_approved": False, "working_version_user_approved": False})
    component["interactive_review_state"]["components_with_any_identity_scope"] = user["identity_confirmation_counts"]["components_with_any_identity_scope"]
    component["updated_utc"] = now
    docs["root"]["current_component_review"] = copy.deepcopy(component)
    assert user["specification_decisions"] == previous_specs and user["specification_approval_counts"] == previous_spec_counts
    for k, path in paths.items():
        write(path, docs[k])
    event = {"event_id": decision_id, "event": "USER_KEPT_COMPONENT_NAME_ONLY", "recorded_utc": decision["recorded_utc"], "component_id": args.component_id, "user_statement": args.user_statement, "approval_record": relative(approval_path), "specification_approval_inferred": False, "physical_specs_verified": False, "workbook_rebuilt": False}
    for log in [REVIEWS / "identity_review_journal.jsonl", ROOT / "review_journal.jsonl"]:
        prior = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        if not any(x.get("event_id") == decision_id for x in prior):
            with log.open("a") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    assert all(digest(path) == expected for path, expected in hashes.items())
    result = {"status": "PASS", "name_kept": review["proposed_name"], "identity_component_count": names, "specification_proposals_approved": False, "approved_proposal_group_count_unchanged": previous_spec_counts["proposal_groups"], "source_model_workbook_unchanged": True, "remote_files_changed": False}
    write(source.parent / "identity-approval-validation.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
