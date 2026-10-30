"""Record a kept build variant without changing its parent's approval or design count."""
import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from review_decision_counts import identity_counts, specification_counts

ROOT = Path(__file__).resolve().parents[2]
REVIEWS = ROOT / "components/reviews"


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return str(path.relative_to(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-id", required=True)
    parser.add_argument("--build-variant-id", required=True)
    parser.add_argument("--user-statement", required=True)
    args = parser.parse_args()
    paths = {
        "walkthrough": REVIEWS / "walkthrough_checkpoint.json",
        "user": REVIEWS / "user_classifications.json",
        "progress": REVIEWS / "specification_review_progress.json",
        "component": ROOT / "components/checkpoint.json",
        "root": ROOT / "checkpoint.json",
    }
    docs = {k: read(p) for k, p in paths.items()}
    cp, user, progress = docs["walkthrough"], docs["user"], docs["progress"]
    assert cp["current_component_id"] == args.component_id
    assert cp["current_build_variant_id"] == args.build_variant_id
    assert cp["review_decision_mode"] == "BUILD_VARIANT_NAME_AND_SPECIFICATIONS"
    source = ROOT / cp["current_review_record"]
    review = read(source)
    assert review["variant_only_review"] is True
    assert review["component_id"] == args.component_id
    assert review["build_variant_id"] == args.build_variant_id
    items = review["specification_review_items"]
    assert len(items) == 6 and all(x.get("proposal_id") for x in items)
    protected = [source, ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"]]
    protected_hashes = {p: sha(p) for p in protected}
    parent = progress["reviews"][args.component_id]
    parent_before = {k: copy.deepcopy(v) for k, v in parent.items() if k not in ["build_variants", "pending_build_variant"]}
    other_variants_before = {k: copy.deepcopy(v) for k, v in parent["build_variants"].items() if k != args.build_variant_id}
    parent_decisions_before = copy.deepcopy(user["decisions"])
    parent_specs_before = copy.deepcopy(user["specification_decisions"])
    now = datetime.now(timezone.utc).isoformat()
    decision_id = f"{args.component_id}:{args.build_variant_id}:name-and-specifications:keep:{now[:10]}"
    approval_path = source.parent / "water-feature-approval.json"
    backup = source.parent / "before-water-feature-approval.json"
    if not backup.exists():
        write(backup, {"recorded_utc": now, "files": {rel(paths[k]): v for k, v in docs.items()}})
    approval = {
        "schema_version": 1, "decision_id": decision_id, "recorded_utc": now,
        "component_id": args.component_id, "build_variant_id": args.build_variant_id,
        "canonical_name": review["proposed_name"], "variant_only_review": True,
        "review_number": review["review_number"], "family_review_number": review["family_review_number"],
        "action": "keep", "user_statement": args.user_statement,
        "response_context": cp["question_scope"],
        "status": "USER APPROVED BUILD VARIANT NAME AND WORKING CATALOGUE PROPOSALS",
        "scope": "Keep this water-feature build's name and six displayed proposals. Keep the parent design, wall-build approval and physical stock count unchanged. Estimates remain estimates; unknown plumbing, wet-use sealing, actual support/load, supply equipment, production and physical measurements remain open.",
        "proposal_source": rel(source), "proposal_source_sha256": protected_hashes[source],
        "approved_proposal_ids": [x["proposal_id"] for x in items],
        "approved_specification_items": copy.deepcopy(items),
        "identity_confirmed": True, "proposals_approved": True, "physical_specs_verified": False,
        "platform_mapping_confirmed": False, "shopify_match_confirmed": False,
        "primary_file_id": review["primary_image_id"], "primary_folder_id": review["primary_folder_id"],
        "previous_primary_folder_id": review["previous_primary_folder_id"],
        "image_link": review["primary_image_link"], "folder_link": review["primary_folder_link"],
        "water_system_details": copy.deepcopy(review["water_system_details"]),
        "remaining_unknowns": copy.deepcopy(review["open_gaps"]),
        "parent_wall_approval": "components/reviews/chiswick-moon-review-2026-10-17/specification-approval.json",
        "workbook_status": "Existing workbook unchanged; separate later approval overlay.",
        "remote_files_changed": False, "live_platform_records_changed": False,
    }
    if approval_path.exists():
        approval = read(approval_path)
        assert approval["decision_id"] == decision_id
        assert approval["proposal_source_sha256"] == protected_hashes[source]
        assert approval["user_statement"] == args.user_statement
    else:
        write(approval_path, approval)
    variants = user.setdefault("build_variant_decisions", [])
    if not any(x["decision_id"] == decision_id for x in variants):
        keys = ["decision_id", "recorded_utc", "component_id", "build_variant_id", "canonical_name", "review_number", "family_review_number", "action", "user_statement", "status", "scope", "approved_proposal_ids", "identity_confirmed", "proposals_approved", "physical_specs_verified", "primary_file_id", "primary_folder_id"]
        variants.append({k: approval[k] for k in keys} | {"approval_record": rel(approval_path), "platform_mapping_confirmed": False})
    names = len({x["component_id"] for x in user["decisions"]})
    specs = len({x["component_id"] for x in user["specification_decisions"]})
    component_groups = sum(len(x["approved_proposal_ids"]) for x in user["specification_decisions"])
    variant_groups = sum(len(x["approved_proposal_ids"]) for x in variants)
    user["identity_confirmation_counts"] = identity_counts(user)
    user["specification_approval_counts"] = specification_counts(user)
    user["updated_utc"] = now
    variant = parent["build_variants"][args.build_variant_id]
    variant.update({"identity_confirmed": True, "identity_confirmed_utc": approval["recorded_utc"], "canonical_name": review["proposed_name"], "specifications_approved": True, "proposals_approved": True, "specification_approval": rel(approval_path), "specification_proposals_status": approval["status"], "approved_specification_items": copy.deepcopy(items), "remaining_unknowns": copy.deepcopy(approval["remaining_unknowns"]), "physical_specs_verified": False})
    parent["pending_build_variant"].update({"status": "WORKING NAME AND SIX PROPOSALS KEPT; TECHNICAL DETAILS INCOMPLETE", "name_and_proposals_approved": True, "approval_record": rel(approval_path), "physical_specs_verified": False})
    progress.update({"updated_utc": now, "latest_build_variant_approval": rel(approval_path), "latest_specification_approval": rel(approval_path)})
    cp.update({"state": "Chiswick Moon water-feature name and six working proposal groups kept; preparing Concave Moon", "current_answer_recorded": True, "current_specification_answer_recorded": True, "last_completed_component_id": args.component_id, "last_completed_review_number": review["review_number"], "last_completed_build_variant_id": args.build_variant_id, "last_build_variant_approval": rel(approval_path), "last_specification_approval": rel(approval_path), "working_version_user_approved": True, "answer_state": approval["scope"], "updated_utc": now})
    component = docs["component"]
    component["interactive_review_state"].update({"state": cp["state"], "explicit_identity_confirmations": names, "explicit_specification_approvals": specs, "explicit_build_variant_approvals": len(variants), "approved_proposal_groups": user["specification_approval_counts"]["proposal_groups"], "specification_proposals_approved": True, "working_version_user_approved": True, "last_completed_build_variant_id": args.build_variant_id, "last_build_variant_approval": rel(approval_path), "last_specification_approval": rel(approval_path)})
    component["last_build_variant_approval"] = {"component_id": args.component_id, "build_variant_id": args.build_variant_id, "recorded_utc": approval["recorded_utc"], "approval": rel(approval_path), "proposals_approved": True, "physical_specs_verified": False, "platform_mapping_confirmed": False}
    component["updated_utc"] = now
    docs["root"]["current_component_review"] = copy.deepcopy(component)
    assert user["decisions"] == parent_decisions_before
    assert user["specification_decisions"] == parent_specs_before
    assert {k: v for k, v in parent.items() if k not in ["build_variants", "pending_build_variant"]} == parent_before
    assert {k: v for k, v in parent["build_variants"].items() if k != args.build_variant_id} == other_variants_before
    assert variant["water_system_details"] == review["water_system_details"]
    for k, path in paths.items():
        write(path, docs[k])
    event = {"event_id": decision_id, "event": "USER_KEPT_BUILD_VARIANT_NAME_AND_WORKING_SPECIFICATIONS", "recorded_utc": approval["recorded_utc"], "component_id": args.component_id, "build_variant_id": args.build_variant_id, "user_statement": args.user_statement, "approval_record": rel(approval_path), "approved_proposal_ids": approval["approved_proposal_ids"], "new_component_designs": 0, "physical_specs_verified": False, "water_system_details_resolved": False, "workbook_rebuilt": False}
    for log in [REVIEWS / "identity_review_journal.jsonl", ROOT / "review_journal.jsonl"]:
        previous = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
        if not any(x.get("event_id") == decision_id for x in previous):
            with log.open("a") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    assert all(sha(p) == h for p, h in protected_hashes.items())
    result = {"checked_utc": now, "status": "PASS", "approved_build_variant": args.build_variant_id, "parent_identity_count": names, "parent_specification_count": specs, "approved_proposal_groups": user["specification_approval_counts"]["proposal_groups"], "parent_wall_approval_unchanged": True, "water_system_unknowns_preserved": True, "source_review_model_workbook_unchanged": True, "remote_files_changed": False}
    write(source.parent / "water-feature-approval-validation.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
