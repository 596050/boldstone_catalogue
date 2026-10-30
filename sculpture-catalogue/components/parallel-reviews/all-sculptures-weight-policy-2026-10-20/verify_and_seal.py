"""Verify saved policy, source units, coverage, estimate arithmetic and scopes."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import math
import re

BASE = Path(__file__).resolve().parent
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ref = lambda p: {"path": str(p), "sha256": sha(p)}
checks = {}


def check(name, value):
    assert value, name
    checks[name] = "PASS"


def save(name, value):
    p = BASE / name
    assert not p.exists(), p
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return ref(p)


def verify_refs(obj):
    if isinstance(obj, dict):
        if {"path", "sha256"} <= obj.keys():
            assert sha(Path(obj["path"])) == obj["sha256"], obj["path"]
        for v in obj.values():
            verify_refs(v)
    elif isinstance(obj, list):
        for v in obj:
            verify_refs(v)


policy = read(BASE / "GLOBAL_APPROXIMATE_WEIGHT_POLICY.json")
audit = read(BASE / "WEIGHT_COVERAGE_AUDIT.json")
inputs = read(BASE / "FROZEN_INPUTS.json")
recovery = read(BASE / "EXISTING_WEIGHT_DISPLAY_RECOVERIES.json")
est = read(BASE / "MISSING_WEIGHT_ESTIMATES.json")
unit = read(BASE / "EXPLICIT_UNIT_AND_FAMILY_SCOPE_CHECK.json")
data = read(Path(inputs["files"]["projection"]["path"]))
progress = read(Path(inputs["files"]["reviews"]["path"]))
model = read(Path(inputs["files"]["model"]["path"]))
wall = read(Path(inputs["files"]["wall_circle"]["path"]))
rows = {(r[0], r[1], r[3]): r for r in data["specifications"]}
for document in [policy, audit, inputs, recovery, est, unit]:
    verify_refs(document)
check("all_saved_source_hashes_match", True)
ev = policy["authoritative_user_evidence"]
raw = Path(ev["transcript"]).read_bytes().splitlines(keepends=True)[ev["line"] - 1]
event = json.loads(raw)
text = "\n".join(c.get("text", "") for c in event["payload"]["content"])
check("exact_owner_message_and_hash_verified",
      event["payload"]["role"] == "user" and text == policy["user_statement"] == ev["text"]
      and hashlib.sha256(raw).hexdigest() == ev["raw_line_sha256"])
check("one_global_policy_not_per_card_replies",
      policy["new_global_owner_policy_events"] == 1 and not policy["per_sculpture_owner_reply_created"]
      and not policy["repeat_weight_acceptance_question_required"])
check("working_weight_not_measured_or_other_five_fields",
      not policy["physical_weights_measured_or_verified_by_this_policy"]
      and not policy["other_five_specification_fields_approved_by_this_policy"])
check("existing_weights_and_owner_corrections_preserved",
      policy["retain_existing_nominal_estimates_and_ranges"]
      and policy["preserve_owner_specific_weight_corrections"]
      and policy["do_not_reactivate_superseded_or_wrong_size_estimates"]
      and policy["preserve_conflicting_source_ranges_without_averaging"])
check("complete_278_scope_partition",
      len(audit["rows"]) == 278
      and len({(r["component_id"], r["scope"]) for r in audit["rows"]}) == 278
      and Counter(r["disposition"] for r in audit["rows"]) == audit["disposition_counts"])
check("all_original_weight_rows_preserved",
      all(r["original_weight_row"] == rows[(r["component_id"], r["scope"], "Weight")] for r in audit["rows"]))
check("nine_estimates_seven_recoveries214_existing",
      len(est["items"]) == 9 and len(recovery["items"]) == 7
      and audit["disposition_counts"]["EXISTING_SCOPED_APPROXIMATION_ACCEPTED"] == 214)
expected_new = {(r["component_id"], r["scope"]) for r in audit["rows"] if r["disposition"] == "NEW_CONDITIONAL_ESTIMATE_PREPARED"}
check("estimate_scopes_exactly_match_audit", {(r["component_id"], r["scope"]) for r in est["items"]} == expected_new)
expected_recovery = {(r["component_id"], r["scope"]) for r in audit["rows"] if r["disposition"] == "EXISTING_ESTIMATE_DISPLAY_RECOVERY"}
check("recovery_scopes_exactly_match_audit", {(r["component_id"], r["scope"]) for r in recovery["items"]} == expected_recovery)
for item in est["items"]:
    key = (item["component_id"], item["scope"])
    check(f"{key}:positive_bounded_estimate", 0 < item["working_range_kg"][0] <= item["nominal_estimated_dry_artwork_kg"] <= item["working_range_kg"][1])
    check(f"{key}:source_and_other_five_fields_preserved",
          item["prior_weight_row_preserved"] == rows[(*key, "Weight")]
          and item["other_five_field_rows_preserved"] == [r for r in data["specifications"] if r[:2] == list(key) and r[3] != "Weight"])
    check(f"{key}:assumptions_not_physical_facts",
          item["assumptions"] and item["comparator_rows"]
          and not item["actual_weight_measured"]
          and not item["assumed_construction_independently_verified"]
          and item["individual_owner_reply"] is None
          and not item["entire_set_mass_divided"])
    check(f"{key}:source_ids_and_links_retained",
          [item["current_image_link"], item["current_folder_link"], item["primary_file_id"], item["folder_id"]]
          == rows[(*key, "Weight")][7:11])
    if key[0].startswith("BC-GLEN-"):
        calc = item["calculation"]
        check(f"{key}:area_ratio_arithmetic",
              math.isclose(calc["area_scaled_nominal_kg"], 4 * 35 * 35 / (30 * 30))
              and item["working_range_kg"][0] < calc["area_scaled_range_kg"][0]
              and item["working_range_kg"][1] > calc["area_scaled_range_kg"][1])
chelsea = next(r for r in est["items"] if r["component_id"] == "BC-CHELSEA")
check("chelsea_corrected_face_old25kg_superseded_source002_excluded",
      chelsea["scope"] == "BASE" and chelsea["calculation"]["owner_face_area_m2"] == 2.5
      and chelsea["nominal_estimated_dry_artwork_kg"] == 100
      and not chelsea["calculation"]["prior25kg_model_reactivated"]
      and ("BC-CHELSEA", "SOURCE-G233002") not in expected_new)
check("chelsea_comparison_arithmetic",
      chelsea["calculation"]["icarus_comparison"]["scaled_kg"] == 60 / 2 * 2.5
      and math.isclose(chelsea["calculation"]["chiswick_comparison"]["scaled_kg"], 35 / (0.7 * 0.95) * 2.5))
knight = next(r for r in est["items"] if r["component_id"] == "BC-KNIGHT")
check("knight_owner50cm_literal_and_hollow_assumption",
      knight["calculation"]["owner_outer_dimensions_cm"] == [100, 100, 50]
      and knight["calculation"]["assumed_open_back"]
      and not knight["calculation"]["solid_bounding_box_volume_used"]
      and "conditional" in knight["display"] and "solid construction" in knight["display"])
check("knight_surface_model_arithmetic",
      knight["calculation"]["assumed_shell_surface_area_m2"] == 3
      and [3 * x for x in knight["calculation"]["assumed_surface_mass_range_kg_m2"]] == knight["working_range_kg"])
bar = next(x for x in model["platform_records"] if x["offer_ref"] == "O078")
check("barbados83kg_explicit_artwork_not_raw_units",
      "weighing approximately 83 kg" in bar["native_description"]
      and bar["native_parts"] == 1 and bar["sale_unit_state"] == "Sale component"
      and unit["barbados_wave"]["raw_numeric_weight_field_not_converted"])
for r in recovery["items"]:
    if r["component_id"].startswith("AM-"):
        check(r["component_id"] + ":source_conflicts_unchanged",
              r["display"] == progress["reviews"][r["component_id"]]["weight_available"]
              and not r["pair_weight_divided"])
check("mp2_existing_weight_models_not_other_design_approval",
      all(not r.get("other_design_border_approval_transferred", False) and r["existing_value_recovered_not_new_estimate"] for r in recovery["items"]))
check("wall_circle12kg_only_approved50cm_template",
      "12 kg" in wall["family_approval"]["working_50cm_template"]["weight"]
      and not unit["wall_circle"]["all_native_option_weight_units_inferred"]
      and unit["wall_circle"]["native_option_rows_preserved"] == len(wall["native_option_register"]))
check("aliases_groups_and_deferred_not_new_individuals",
      audit["disposition_counts"]["SOURCE_GROUP_POSITION_REFERENCE"] == 5
      and audit["disposition_counts"]["CANONICAL_COMPONENT_REFERENCE_ONLY"] == 5
      and audit["disposition_counts"]["OWNER_DEFERRED_COLLECTION_REFERENCE"] == 1
      and all(r["new_physical_count"] == 0 for r in audit["rows"]))
check("no_remote_shared_writes_downloads_or_new_six_field_acceptances",
      not audit["shared_master_writes_by_lane"] and audit["remote_mutations"] == audit["private_original_downloads"] == 0
      and est["new_six_field_acceptances"] == 0
      and all(not r["shared_master_writes_by_lane"] and r["remote_mutations"] == 0 for r in est["items"]))

by_new = {(r["component_id"], r["scope"]): r for r in est["items"]}
by_recovery = {(r["component_id"], r["scope"]): r for r in recovery["items"]}
overlays = []
for audit_row in audit["rows"]:
    key = (audit_row["component_id"], audit_row["scope"])
    original = audit_row["original_weight_row"]
    disposition = audit_row["disposition"]
    chosen = by_new.get(key) or by_recovery.get(key)
    overlay = {
        "component_id": key[0], "scope": key[1], "field": "Weight",
        "disposition": disposition, "before_row": original,
        "acceptance_policy_id": policy["policy_id"],
        "new_individual_owner_reply": False, "other_five_fields_changed": False,
    }
    if chosen:
        overlay.update(display=chosen["display"], status="Owner accepted approximate working weight under global instruction; actual mass unverified",
                       basis=chosen.get("method", chosen.get("basis", "Existing scoped estimate recovered from source dictionary.")))
    elif disposition == "EXISTING_SCOPED_APPROXIMATION_ACCEPTED":
        overlay.update(display=original[4], original_display_retained_exactly=True,
                       status=original[5] + "\nApplicable approximate weight accepted under global owner instruction; source conflicts and conditions retained.",
                       basis=original[6])
    else:
        overlay.update(reference_only=True, scope_note=audit_row["basis"],
                       references=audit_row["references"], numeric_mass_assigned=None)
    overlays.append(overlay)
check("all214_existing_numeric_displays_preserved_exactly",
      all(x["display"] == x["before_row"][4] for x in overlays if x["disposition"] == "EXISTING_SCOPED_APPROXIMATION_ACCEPTED"))
check("all16_missing_or_hidden_weight_displays_numeric",
      all(re.search(r"\d\s*kg", x["display"], re.I) for x in overlays if (x["component_id"], x["scope"]) in expected_new | expected_recovery))
overlay_ref = save("WEIGHT_OUTPUT_OVERLAYS.json", {
    "schema": "boldstone.global-weight-projection-overlays.v1", "prepared_utc": NOW,
    "reserved_batch": 90, "policy_id": policy["policy_id"], "rows": overlays,
    "review_scope_count": 278, "existing_numeric_displays_retained": 214,
    "new_conditional_weight_estimates": 9, "recovered_existing_numeric_displays": 7,
    "reference_or_deferred_rows_without_new_mass": 48,
    "counts_are_overlapping_review_scopes_not_unique_sculptures": True,
    "canonical_shared_application_by_root_required": True,
    "workbook_publication_pending": True, "shared_master_writes_by_lane": False,
})
qa_ref = save("VERIFICATION.json", {
    "status": "PASS", "checked_utc": NOW, "check_count": len(checks), "checks": checks,
    "policy": ref(BASE / "GLOBAL_APPROXIMATE_WEIGHT_POLICY.json"),
    "coverage": ref(BASE / "WEIGHT_COVERAGE_AUDIT.json"),
    "new_estimates": ref(BASE / "MISSING_WEIGHT_ESTIMATES.json"),
    "display_recoveries": ref(BASE / "EXISTING_WEIGHT_DISPLAY_RECOVERIES.json"),
    "proposed_overlays": overlay_ref,
})
package_ref = save("IMPORT_PACKAGE.json", {
    "schema": "boldstone.owner-global-weight-policy-import.v1",
    "status": "READY_FOR_SOLE_WRITER_IMPORT", "prepared_utc": NOW, "reserved_batch": 90,
    "source_owner_session": "01a13fe6-495b-7253-b923-31823b4cbca8",
    "shared_writer_session": "01a144ab-1a7c-7223-a403-73a4d53d70ff",
    "policy": ref(BASE / "GLOBAL_APPROXIMATE_WEIGHT_POLICY.json"),
    "owner_evidence": ref(BASE / "OWNER_EVIDENCE.json"),
    "allocation": ref(BASE / "COORDINATOR_ALLOCATION.json"),
    "frozen_inputs": ref(BASE / "FROZEN_INPUTS.json"),
    "coverage": ref(BASE / "WEIGHT_COVERAGE_AUDIT.json"),
    "new_estimates": ref(BASE / "MISSING_WEIGHT_ESTIMATES.json"),
    "display_recoveries": ref(BASE / "EXISTING_WEIGHT_DISPLAY_RECOVERIES.json"),
    "unit_and_family_scope_verification": ref(BASE / "EXPLICIT_UNIT_AND_FAMILY_SCOPE_CHECK.json"),
    "proposed_weight_overlays": overlay_ref, "verification": qa_ref,
    "new_global_owner_policy_events": 1, "new_conditional_numeric_weight_estimates": 9,
    "existing_numeric_display_recoveries": 7,
    "existing_scoped_numeric_weight_displays_retained": 214,
    "new_individual_owner_replies": 0, "new_six_field_acceptances": 0,
    "new_identity_or_physical_counts": 0, "shared_master_writes_by_lane": False,
    "remote_mutations": 0, "private_original_downloads": 0,
    "requested_import": "Apply one global working-weight policy, nine bounded estimates and seven source-weight display recoveries. Keep all prior source fields immutable and source/finish/owner corrections explicit; no group mass division or source002 Chelsea transfer. Use current88/89/91 weight values when later imports add exact scoped working reviews; this package does not overwrite their other five fields. Accept future applicable approximations without another routine question.",
    "followup_flag": "Barbados and Ammonite projection also omit some other structured fields; flagged only, not changed by this weights-only package.",
})
files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.suffix in (".py", ".json"))
manifest_ref = save("SEALED_MANIFEST.json", {
    "schema": "boldstone.immutable-review-file-manifest.v1", "created_utc": NOW,
    "files": [ref(p) for p in files], "sealed_files_immutable": True,
    "later_shared_import_and_publication_status_requires_additive_receipts": True,
})
print(json.dumps({"status": "PASS", "check_count": len(checks), "package": package_ref,
                  "verification": qa_ref, "manifest": manifest_ref, "sealed_files": len(files)}))
