"""Record an explicit keep of the current name and displayed specification proposals.

Use only when the immediately preceding user-facing question offered both.
Name-only or dimension-only answers need a narrower decision and must not use this.
"""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from review_decision_counts import identity_counts, specification_counts

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "components"
REVIEWS = BASE / "reviews"


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
    checkpoint_path = REVIEWS / "walkthrough_checkpoint.json"
    cp = read(checkpoint_path)
    assert cp["current_component_id"] == args.component_id
    source = ROOT / cp["current_review_record"]
    review = read(source)
    assert review["component_id"] == args.component_id
    assert not review.get("variant_only_review", False), "Build-variant decisions must be recorded separately from parent/wall approvals."
    items = review["specification_review_items"]
    assert len(items) == 6 and all(x.get("proposal_id") for x in items)
    now = datetime.now(timezone.utc).isoformat()
    date = now[:10]
    spec_id = f"{args.component_id}:specifications:keep:{date}"
    identity_id = f"{args.component_id}:identity:keep"
    approval_path = source.parent / "specification-approval.json"
    classifications_path = REVIEWS / "user_classifications.json"
    progress_path = REVIEWS / "specification_review_progress.json"
    component_cp_path = BASE / "checkpoint.json"
    root_cp_path = ROOT / "checkpoint.json"
    protected = [source, BASE / "evidence/component_register.json", ROOT / cp["register_workbook"]]
    protected_hashes = {p: digest(p) for p in protected}
    backup = source.parent / "before-approval.json"
    if not backup.exists():
        paths = [classifications_path, checkpoint_path, progress_path, component_cp_path, root_cp_path]
        write(backup, {"recorded_utc": now, "files": {relative(p): read(p) for p in paths}})
    approval = {
        "schema_version": 1, "decision_id": spec_id, "recorded_utc": now,
        "component_id": args.component_id, "canonical_name": review["proposed_name"],
        "review_number": review["review_number"], "family_review_number": review.get("family_review_number", 1),
        "action": "keep", "user_statement": args.user_statement,
        "response_context": cp["question_scope"],
        "status": "USER APPROVED WORKING CATALOGUE SPECIFICATIONS",
        "scope": "The depicted individual name/identity and six displayed specification groups are kept as working catalogue values. Guesses retain their uncertainty; physical verification, unknown hardware/load, stock/lead time, existing platform identity and publication are not inferred.",
        "proposal_source": relative(source), "proposal_source_sha256": protected_hashes[source],
        "approved_proposal_ids": [x["proposal_id"] for x in items],
        "approved_specification_items": copy.deepcopy(items), "proposals_approved": True,
        "physical_specs_verified": False, "shopify_match_confirmed": False,
        "primary_file_id": review["primary_image_id"], "primary_folder_id": review["primary_folder_id"],
        "image_link": review["primary_image_link"], "folder_link": review["primary_folder_link"],
        "remaining_unknowns": review.get("open_gaps", review.get("other_missing_details", [])),
        "workbook_status": "Existing workbook unchanged; this separate approval overlay records the later user decision.",
        "remote_files_changed": False, "live_platform_records_changed": False,
    }
    if approval_path.exists():
        approval = read(approval_path)
        assert approval["decision_id"] == spec_id
        assert approval["proposal_source_sha256"] == protected_hashes[source]
        assert approval["user_statement"] == args.user_statement
    else:
        write(approval_path, approval)
    user = read(classifications_path)
    if not any(x["decision_id"] == identity_id for x in user["decisions"]):
        user["decisions"].append({
            "decision_id": identity_id, "recorded_utc": now, "review_number": review["review_number"],
            "family_review_number": review.get("family_review_number", 1), "component_id": args.component_id,
            "action": "keep", "proposed_name_at_review": review["proposed_name"],
            "confirmed_name": review["proposed_name"], "prior_catalogue_name": review.get("prior_catalogue_name"),
            "identity_status": "USER CONFIRMED", "confirmed_fields": ["component name", "depicted individual component identity", "retain individual component record"],
            "not_confirmed": approval["remaining_unknowns"], "evidence_file_id": review["primary_image_id"],
            "containing_folder_id": review["primary_folder_id"], "evidence_file_ids": [review["primary_image_id"]],
            "containing_folder_ids": [review["primary_folder_id"]], "scope": approval["scope"],
            "user_statement": args.user_statement, "specification_approval": relative(approval_path),
        })
    decisions = user.setdefault("specification_decisions", [])
    if not any(x["decision_id"] == spec_id for x in decisions):
        keys = ["decision_id", "recorded_utc", "component_id", "canonical_name", "review_number", "family_review_number", "action", "user_statement", "status", "scope", "approved_proposal_ids", "proposals_approved", "physical_specs_verified", "primary_file_id", "primary_folder_id"]
        decisions.append({k: approval[k] for k in keys} | {"approval_record": relative(approval_path), "shopify_match_confirmed": False})
    names = len({x["component_id"] for x in user["decisions"]})
    specs = len({x["component_id"] for x in decisions})
    user["identity_confirmation_counts"] = identity_counts(user)
    variants = user.get("build_variant_decisions", [])
    component_groups = sum(len(x["approved_proposal_ids"]) for x in decisions)
    variant_groups = sum(len(x["approved_proposal_ids"]) for x in variants)
    user["specification_approval_counts"] = specification_counts(user)
    user["updated_utc"] = now
    write(classifications_path, user)
    progress = read(progress_path)
    records = next(x for x in progress.values() if isinstance(x, dict) and args.component_id in x)
    records[args.component_id].update({"identity_confirmed": True, "identity_confirmed_utc": now, "canonical_name": review["proposed_name"], "specifications_approved": True, "proposals_approved": True, "specification_approval": relative(approval_path), "specification_proposals_status": approval["status"], "approved_specification_items": approval["approved_specification_items"], "remaining_unknowns": approval["remaining_unknowns"], "physical_specs_verified": False})
    progress.update({"updated_utc": now, "latest_specification_approval": relative(approval_path)})
    write(progress_path, progress)
    cp.update({"state": review["proposed_name"] + " kept; preparing next component", "current_answer_recorded": True, "current_specification_answer_recorded": True, "last_completed_component_id": args.component_id, "last_completed_review_number": review["review_number"], "last_completed_specification_component_id": args.component_id, "last_specification_approval": relative(approval_path), "answer_state": "User kept the name/identity and six displayed working specification groups. All remaining uncertainty is retained in the approval record.", "updated_utc": now})
    write(checkpoint_path, cp)
    component_cp = read(component_cp_path)
    component_cp["interactive_review_state"].update({"state": cp["state"], "explicit_identity_confirmations": names, "explicit_specification_approvals": specs, "last_completed_component_ids": [args.component_id], "last_completed_review_numbers": [review["review_number"]], "specification_proposals_approved": True, "last_specification_approval": relative(approval_path)})
    component_cp["interactive_review_state"].update({"approved_proposal_groups": user["specification_approval_counts"]["proposal_groups"], "explicit_build_variant_approvals": len(variants)})
    component_cp["last_specification_approval"] = {"component_id": args.component_id, "recorded_utc": approval["recorded_utc"], "approval": relative(approval_path), "proposals_approved": True, "physical_specs_verified": False, "shopify_match_confirmed": False}
    component_cp["updated_utc"] = now
    write(component_cp_path, component_cp)
    root_cp = read(root_cp_path)
    root_cp["current_component_review"] = copy.deepcopy(component_cp)
    write(root_cp_path, root_cp)
    event = {"event_id": spec_id, "event": "USER_KEPT_COMPONENT_NAME_AND_SPECIFICATIONS", "recorded_utc": now, "component_id": args.component_id, "user_statement": args.user_statement, "approval_record": relative(approval_path), "approved_proposal_ids": approval["approved_proposal_ids"], "physical_specs_verified": False, "shopify_match_confirmed": False, "workbook_rebuilt": False}
    for log in [REVIEWS / "identity_review_journal.jsonl", ROOT / "review_journal.jsonl"]:
        prior = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        if not any(x.get("event_id") == spec_id for x in prior):
            with log.open("a") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    assert all(digest(p) == expected for p, expected in protected_hashes.items())
    result = {"checked_utc": now, "status": "PASS", "approved_component": args.component_id, "confirmed_name": review["proposed_name"], "identity_decisions": names, "specification_approval_components": specs, "approved_proposal_groups": user["specification_approval_counts"]["proposal_groups"], "source_review_unchanged": True, "source_model_unchanged": True, "workbook_unchanged": True, "physical_verification_not_inferred": True}
    write(source.parent / "approval-validation.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
