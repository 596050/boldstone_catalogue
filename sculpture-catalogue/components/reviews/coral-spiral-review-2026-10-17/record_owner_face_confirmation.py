"""Apply the owner's explicit Coral Spiral face dimensions to review overlays."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PATHS = {
    "user": ROOT / "components/reviews/user_classifications.json",
    "progress": ROOT / "components/reviews/specification_review_progress.json",
    "walkthrough": ROOT / "components/reviews/walkthrough_checkpoint.json",
    "component": ROOT / "components/checkpoint.json",
    "root": ROOT / "checkpoint.json",
}


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def rel(path):
    return str(path.relative_to(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


docs = {key: read(path) for key, path in PATHS.items()}
user, progress, cp, component = [docs[key] for key in ["user", "progress", "walkthrough", "component"]]
source = HERE / "component-review.json"
revised_path = HERE / "component-review-55x55-owner.json"
decision_path = HERE / "user-face-dimensions-55x55.json"
decision_id = "BC-CORAL:CORAL-WHITE:face:user-stated:55x55"
if decision_path.exists():
    assert any(item["decision_id"] == decision_id for item in user["dimension_decisions"])
    print(json.dumps({"status": "ALREADY_APPLIED", "decision": rel(decision_path)}))
    raise SystemExit(0)

now = datetime.now(timezone.utc).isoformat()
protected_paths = [source, ROOT / "components/evidence/component_register.json", ROOT / cp["register_workbook"], HERE / "identity-approval.json"]
protected_hashes = {path: sha(path) for path in protected_paths}
original_specs = copy.deepcopy(user["specification_decisions"])
original_spec_counts = copy.deepcopy(user["specification_approval_counts"])
original_identities = copy.deepcopy(user["decisions"])
active_keys = ["current_component_id", "current_review_number", "current_size_finish_variant_id", "current_review_record", "current_answer_recorded", "current_specification_answer_recorded", "next_review_after_keep"]
active = {key: copy.deepcopy(cp[key]) for key in active_keys}
write(HERE / "before-owner-face-confirmation.json", {"recorded_utc": now, "files": {rel(PATHS[key]): value for key, value in docs.items()}})

source_review = read(source)
decision = {
    "schema_version": 1,
    "decision_id": decision_id,
    "recorded_utc": now,
    "component_id": "BC-CORAL",
    "size_finish_variant_id": "CORAL-WHITE",
    "canonical_name": "Coral Spiral",
    "review_number": 23,
    "action": "confirm individual sculpture face dimensions",
    "user_statement": "Keep “Deco Dune Ripple — Wave, Verdigris” And a correction:\nCoral Spiral needs to be 55cm x 55cm by the way",
    "response_context": "Owner explicitly identifies Coral Spiral while separately keeping the current verdigris Wave's name. Apply only the 55 by 55 cm face dimensions to the previously reviewed individual white Coral Spiral.",
    "status": "USER STATED FACE DIMENSIONS",
    "approved_face_dimensions_cm": {"height": 55, "width": 55},
    "target_confirmed": True,
    "axes_confirmed": True,
    "confirmed_fields": ["Individual Coral Spiral face height 55 cm", "Individual Coral Spiral face width 55 cm"],
    "not_confirmed": ["Depth/maximum projection", "Weight", "Material/finish/reinforcement/sealing", "Fixing hardware/layout/rated load", "Individual price", "Availability/stock/lead time", "Squarespace/Shopify offer match", "Physical measurement method"],
    "primary_file_id": source_review["primary_image_id"],
    "primary_folder_id": source_review["primary_folder_id"],
    "image_link": source_review["primary_image_link"],
    "folder_link": source_review["primary_folder_link"],
    "source_review": rel(source),
    "source_review_sha256": protected_hashes[source],
    "prior_face_evidence": "The 2016 brochure already stated 55 by 55 cm for the design. Owner now directly confirms these face dimensions for Coral Spiral.",
    "numeric_face_change": False,
    "other_estimates_rescaled_or_approved": False,
    "specifications_approved": False,
    "physical_specs_verified": False,
    "remote_files_changed": False,
    "live_platform_records_changed": False,
    "workbook_status": "Unchanged; owner face dimensions recorded in review overlay for later batch export.",
}
write(decision_path, decision)
revised = copy.deepcopy(source_review)
revised.update({
    "prepared_utc": now,
    "supersedes_review_record": rel(source),
    "scope": "One individual white Coral Spiral design/component. Owner states face dimensions 55 H by 55 W cm; depth and other specification proposals remain unapproved. Context pictures do not establish current stock or manufacture.",
    "identity_confirmed": True,
    "identity_approval": rel(HERE / "identity-approval.json"),
    "owner_face_dimension_decision": rel(decision_path),
    "user_face_dimensions_cm": {"height": 55, "width": 55},
    "face_dimension_status": "USER STATED FACE DIMENSIONS",
})
item = revised["specification_review_items"][0]
item["value"].update({"user_confirmed_face_height_cm": 55, "user_confirmed_face_width_cm": 55})
item.update({
    "display": "55 H × 55 W cm face — owner confirmed; approximately 6 cm depth, estimated 5–7 cm — unapproved guess",
    "status": "OWNER STATED FACE DIMENSIONS; DEPTH GUESS REMAINS UNAPPROVED",
    "basis": "Owner explicitly states Coral Spiral is 55 by 55 cm. This also agrees numerically with the labelled 2016 brochure. No depth was supplied: the earlier 6 cm (5–7 cm) proposal remains unchanged and unapproved. Weight, material, fixings, price and availability are not rescaled or approved by this correction.",
    "owner_confirmation": rel(decision_path),
})
revised["open_gaps"][0] = "Measure full depth/maximum projection; face 55 by 55 cm is now owner stated"
write(revised_path, revised)
user["dimension_decisions"].append(decision)
confirmed_faces = [item for item in user["dimension_decisions"] if item.get("approved_face_dimensions_cm") and item.get("target_confirmed") is not False]
user["dimension_confirmation_counts"] = {
    "components": len({item["component_id"] for item in confirmed_faces}),
    "face_size_decisions": len(confirmed_faces),
}
user["updated_utc"] = now
review_progress = progress["reviews"]["BC-CORAL"]
review_progress.update({
    "reviewed_utc": now,
    "review_record": rel(revised_path),
    "user_face_dimensions_cm": {"height": 55, "width": 55},
    "face_dimension_status": "USER STATED FACE DIMENSIONS",
    "owner_face_dimension_decision": rel(decision_path),
    "specification_proposals": copy.deepcopy(revised["specification_review_items"]),
    "gaps": copy.deepcopy(revised["open_gaps"]),
    "specification_review_status": "NAME KEPT; OWNER FACE 55 BY 55 CM; DEPTH AND OTHER SPECIFICATION PROPOSALS PENDING",
})
progress.update({"updated_utc": now, "latest_owner_face_dimension_decision": rel(decision_path)})
for pending in cp["pending_specification_reviews"]:
    if pending["component_id"] == "BC-CORAL":
        pending.update({
            "pending_fields": ["Depth / maximum projection", "Individual dry weight", "Material and finish", "Fixing", "Individual retail price", "Availability"],
            "review_record": rel(revised_path),
            "owner_face_dimensions_cm": {"height": 55, "width": 55},
            "owner_face_dimension_decision": rel(decision_path),
        })
cp.update({
    "last_dimension_decision": rel(decision_path),
    "last_working_face_size_approval": rel(decision_path),
    "last_working_face_size_approval_scope": "Coral Spiral owner face 55 by 55 cm only; depth and other proposals remain pending; active Dune review preserved",
    "updated_utc": now,
})
component["interactive_review_state"].update({
    "last_dimension_decision": rel(decision_path),
    "last_working_face_size_approval": rel(decision_path),
    "explicit_working_face_size_approvals": user["dimension_confirmation_counts"]["face_size_decisions"],
})
component["updated_utc"] = now
docs["root"]["current_component_review"] = copy.deepcopy(component)
assert {key: cp[key] for key in active_keys} == active
assert user["specification_decisions"] == original_specs
assert user["specification_approval_counts"] == original_spec_counts
assert user["decisions"] == original_identities
assert revised["specification_review_items"][1:] == source_review["specification_review_items"][1:]
for key, path in PATHS.items():
    write(path, docs[key])
event = {"event_id": decision_id, "event": "USER_CONFIRMED_COMPONENT_FACE_DIMENSIONS", "recorded_utc": now, "component_id": "BC-CORAL", "user_statement": decision["user_statement"], "dimension_decision": rel(decision_path), "dimensions_cm": {"height": 55, "width": 55}, "specification_approval_inferred": False, "active_review_preserved": True, "physical_specs_verified": False, "workbook_rebuilt": False}
for log in [ROOT / "components/reviews/identity_review_journal.jsonl", ROOT / "review_journal.jsonl"]:
    existing = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    if not any(item.get("event_id") == decision_id for item in existing):
        with log.open("a") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
assert all(sha(path) == expected for path, expected in protected_hashes.items())
assert read(PATHS["progress"])["reviews"]["BC-CORAL"]["user_face_dimensions_cm"] == {"height": 55, "width": 55}
result = {"status": "PASS", "owner_face_dimensions_cm": {"height": 55, "width": 55}, "face_dimension_counts": user["dimension_confirmation_counts"], "other_estimates_unchanged_and_unapproved": True, "active_review_preserved": True, "source_model_workbook_and_name_receipts_unchanged": True, "remote_files_changed": False}
write(HERE / "owner-face-confirmation-validation.json", result)
print(json.dumps(result))
