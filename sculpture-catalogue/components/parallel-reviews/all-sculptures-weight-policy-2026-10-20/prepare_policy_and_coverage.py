"""Prepare global weight instruction and frozen coverage for root-only import90."""
from pathlib import Path
from collections import Counter, defaultdict
from copy import deepcopy
import datetime
import hashlib
import json
import re

BASE = Path(__file__).resolve().parent
CAT = BASE.parents[2]
REV = CAT / "components/reviews"
REFRESH = REV / "workbook-refresh-2026-10-19"
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
LANE = "01a13fe6-495b-7253-b923-31823b4cbca8"
ROOT = "01a144ab-1a7c-7223-a403-73a4d53d70ff"
STATEMENT = "The approximate weights are good, for all sculptures, if they do not have estimates, you should estimate them, otherwise accept the approximate"
POLICY_ID = f"ALL-SCULPTURES-APPROXIMATE-WEIGHT:{LANE}:LINE30053"


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def ref(p):
    return {"path": str(p), "sha256": sha(p)}


def save(p, value):
    assert p.is_relative_to(BASE) and not p.exists(), p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return ref(p)


def freeze(source, name, expected=None):
    blob = source.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    assert expected is None or digest == expected, source
    dest = BASE / "source-snapshots" / name
    assert not dest.exists(), dest
    dest.parent.mkdir(exist_ok=True)
    dest.write_bytes(blob)
    return {"source": str(source), **ref(dest)}


transcript = Path(f"/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T15-10-19-{LANE}.jsonl")
raw = transcript.read_bytes().splitlines(keepends=True)[30052]
event = json.loads(raw)
payload = event["payload"]
assert payload["role"] == "user" and payload["type"] == "message"
text = "\n".join(c.get("text", "") for c in payload["content"])
assert text == STATEMENT
assert hashlib.sha256(raw).hexdigest() == "6cbc839cd679c069e7748b64c6d063443bdac0d621a42afef1dfb68735b21563"
owner = {
    "transcript": str(transcript), "line": 30053, "timestamp": event["timestamp"],
    "role": "user", "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    "raw_line_sha256": hashlib.sha256(raw).hexdigest(),
    "source_raw_line_digest_includes_line_ending": True,
}
owner_ref = save(BASE / "OWNER_EVIDENCE.json", owner)
allocations = []
for n, line in enumerate(transcript.read_bytes().splitlines(keepends=True), 1):
    e = json.loads(line)
    v = e.get("payload", {})
    output = v.get("output")
    if v.get("type") == "function_call_output" and isinstance(output, str):
        if f"<source_thread_id>{ROOT}</source_thread_id>" in output and (
            "Reserve90:" in output or "90 scope okay;" in output
        ):
            allocations.append({"line": n, "text": output, "timestamp": e.get("timestamp"),
                               "raw_line_sha256": hashlib.sha256(line).hexdigest(),
                               "source_raw_line_digest_includes_line_ending": True})
assert len(allocations) >= 2
allocation_ref = save(BASE / "COORDINATOR_ALLOCATION.json", {
    "transcript": str(transcript), "coordinator_thread": ROOT, "reserved_batch": 90,
    "messages": allocations, "is_owner_statement": False,
})
policy = {
    "schema": "boldstone.owner-global-working-weight-policy.v1",
    "policy_id": POLICY_ID, "recorded_utc": event["timestamp"], "prepared_utc": NOW,
    "source_owner_session": LANE, "user_statement": STATEMENT,
    "authoritative_user_evidence": owner,
    "status": "OWNER_ACCEPTS_EXISTING_APPROXIMATE_WEIGHTS_AND_AUTHORIZES_MISSING_ESTIMATES",
    "effective_from_utc": event["timestamp"], "until_owner_changes_instruction": True,
    "applies_to": "All catalogue sculptures and their individual finish/build/component scopes, including future reviews. Group, contextual, deferred and alias-only records retain their existing scope; this instruction does not create extra products from them.",
    "accept_existing_applicable_approximate_weights_as_working": True,
    "estimate_missing_individual_sculpture_weights": True,
    "retain_existing_nominal_estimates_and_ranges": True,
    "retain_approximate_estimated_conditional_and_source_labels": True,
    "preserve_owner_specific_weight_corrections": True,
    "do_not_reactivate_superseded_or_wrong_size_estimates": True,
    "preserve_conflicting_source_ranges_without_averaging": True,
    "retain_existing_confirmed_or_owner_stated_weights": True,
    "estimate_missing_using": "Recorded dimensions, object-specific source claims and clearly identified similar-piece comparisons; state assumed construction/material and uncertainty. A conditional estimate does not establish the assumptions as facts.",
    "individual_component_scope_required": True,
    "whole_set_weights_divided_into_components": False,
    "source_alias_dimensions_or_mass_automatically_inherited": False,
    "repeat_weight_acceptance_question_required": False,
    "per_sculpture_owner_reply_created": False,
    "physical_weights_measured_or_verified_by_this_policy": False,
    "packed_weight_operating_water_weight_and_support_loads_verified": False,
    "other_five_specification_fields_approved_by_this_policy": False,
    "new_global_owner_policy_events": 1,
    "new_six_field_acceptances": 0, "new_identity_approvals": 0,
    "new_physical_sculpture_mould_or_stock_counts": 0,
    "shared_master_writes_by_lane": False, "remote_mutations": 0,
    "catalogue_display": "Approximate working weight accepted under the owner's global instruction; estimates and source limitations remain labelled.",
}
policy_ref = save(BASE / "GLOBAL_APPROXIMATE_WEIGHT_POLICY.json", policy)

data_ref = freeze(REFRESH / "refresh-data.json", "refresh-data-batch87.json")
data = read(Path(data_ref["path"]))
frozen = {"projection": data_ref}
for key in ["reviews", "decisions", "model"]:
    source = next(x for x in data["source_files"] if x.get("snapshot", "").endswith("/" + key + ".json"))
    frozen[key] = freeze(Path(source["snapshot"]), key + "-batch87.json", source["sha256"])
progress = read(Path(frozen["reviews"]["path"]))
ledger = read(Path(frozen["decisions"]["path"]))
model = read(Path(frozen["model"]["path"]))
rows = {(r[0], r[1], r[3]): r for r in data["specifications"]}
review_rows = {(r[0], r[1]): r for r in data["reviews"]}
weights = [r for r in data["specifications"] if r[3] == "Weight"]
assert len(weights) == len(data["reviews"]) == 278
assert len({(r[0], r[1]) for r in weights}) == 278

wall_path = CAT / progress["family_reviews"]["BC-WALL-CIRCLE"]["catalogue"]
frozen["wall_circle"] = freeze(wall_path, "wall-circle-approved-working-catalogue.json")
wall = read(Path(frozen["wall_circle"]["path"]))
save(BASE / "FROZEN_INPUTS.json", {
    "as_of_utc": data["as_of_utc"], "snapshot_imports_through_batch": 87,
    "captured_utc": NOW, "files": frozen,
    "projection_is_not_the_final_unique_individual_catalogue_or_stock_count": True,
})

new_scopes = {
    ("BC-CHELSEA", "BASE"): "Corrected owner250x100cm replaces smaller-size mass guess",
    ("BC-FP-LEFT", "FP-LEFT-VERDIGRIS"): "Existing owner40x40cm individual; no weight",
    ("BC-FFS-2", "FFS2-TERRACOTTA"): "Finish-specific weight absent; White historical comparator available",
    ("BC-FFS-2", "FFS2-VERDIGRIS"): "Finish-specific weight absent; White historical comparator available",
    ("BC-KNIGHT", "KNIGHT-WHITE"): "Owner100x100x50cm; assumed hollow construction must be explicit",
}
for cid, scope in [
    ("BC-GLEN-1", "GLEN-TOP-LEFT-WHITE"), ("BC-GLEN-2", "GLEN-TOP-RIGHT-WHITE"),
    ("BC-GLEN-3", "GLEN-BOTTOM-LEFT-WHITE"), ("BC-GLEN-4", "GLEN-BOTTOM-RIGHT-WHITE"),
]:
    new_scopes[(cid, scope)] = "Owner35x35cm individual panel; no existing estimate"

recoveries = []
for cid in ["AM-S1", "AM-S2", "AM-L1", "AM-L2"]:
    n = progress["reviews"][cid]
    recoveries.append({
        "component_id": cid, "scope": "BASE", "canonical_component_id": n["component_id"],
        "name": n["individual_listing_name"], "display": n["weight_available"],
        "source_pointer": ["reviews", cid, "weight_available"],
        "source": frozen["reviews"], "original_field": n["weight_available"],
        "basis": n["sources"], "existing_value_recovered_not_new_estimate": True,
        "current_specimen_unweighed": True, "source_conflicts_preserved": True,
        "pair_weight_divided": False,
    })
bar_weight = next(x for x in progress["reviews"]["BC-BAR-WAVE"]["specification_review_items"] if "weight" in x["field"].lower())
assert bar_weight["value"]["approximate_kg"] == 83
recoveries.append({
    "component_id": "BC-BAR-WAVE", "scope": "BASE", "name": "Barbados Wave",
    "display": bar_weight["display"] + " — existing source approximation; current specimen unweighed",
    "source_pointer": ["reviews", "BC-BAR-WAVE", "specification_review_items"],
    "source": frozen["reviews"], "original_field": bar_weight,
    "basis": bar_weight["source_ref"], "existing_value_recovered_not_new_estimate": True,
    "current_specimen_unweighed": True, "source_conflicts_preserved": True,
    "owner_keep_text_did_not_replace_the_numeric_source_weight": True,
})
for suffix in ["WHITE-AND-GOLD", "WHITE-WITH-BORDER"]:
    cid = "MOONPHASE-CURRENT-2"
    scope = cid + ":" + suffix
    alias = progress["catalogue_alias_reviews"][scope]
    binding = alias["historical_name_keep_bindings"][0]
    original = binding["historical_specification_proposals"]["weight"]
    source_path = CAT / binding["source_review_snapshot"]
    source_ref = freeze(source_path, scope.replace(":", "__") + "-source.json", source_path.stem)
    if suffix == "WHITE-AND-GOLD":
        assert original["conditional_maker_AC730_kg_range"] == [3, 5]
        display = "3–5 kg — conditional historical maker AC730 estimate; dated White trade5.5kg and retail6.5kg references retained separately. This finish is unweighed and its construction unconfirmed."
    else:
        assert original["model_estimate_kg"] == 6 and original["rough_range_kg"] == [4, 9]
        display = "Approximately6kg; rough range4–9kg — existing conditional bordered-panel estimate. Assumes30x30cm core within about35x35cm outer panel and modelled AC730 construction; actual dimensions/material/mass unverified."
        source_ref["weight_model"] = freeze(Path(original["model"]), "MP2-bordered-existing-weight-model.json", original["model_sha256"])
    recoveries.append({
        "component_id": cid, "scope": scope, "name": alias["canonical_name"],
        "display": display, "source": source_ref,
        "source_pointer": ["historical_name_keep_bindings", 0, "historical_specification_proposals", "weight"],
        "binding_record": binding["binding_record"], "original_field": original,
        "existing_value_recovered_not_new_estimate": True,
        "current_specimen_unweighed": True, "source_conflicts_preserved": True,
        "other_design_border_approval_transferred": False,
    })
for item in recoveries:
    key = (item["component_id"], item["scope"])
    item["before_projected_row"] = rows[(*key, "Weight")]
    item["acceptance_policy_id"] = POLICY_ID
    item["status"] = "EXISTING_APPROXIMATE_WEIGHT_ACCEPTED_UNDER_GLOBAL_POLICY"
    item["new_individual_owner_reply"] = False
    item["other_five_fields_changed"] = False
recovery_ref = save(BASE / "EXISTING_WEIGHT_DISPLAY_RECOVERIES.json", {
    "status": "PREPARED_FOR_SOLE_WRITER", "policy_id": POLICY_ID,
    "recovery_count": len(recoveries), "new_numeric_estimates": 0,
    "items": recoveries, "shared_master_writes_by_lane": False,
})
recovery_keys = {(x["component_id"], x["scope"]) for x in recoveries}

children = defaultdict(list)
for (cid, scope), row in review_rows.items():
    if scope != "BASE" and row[3] != "Source alias review":
        children[cid].append(scope)
audit = []
for row in weights:
    cid, scope, name = row[:3]
    key = (cid, scope)
    node = progress["reviews"].get(cid, {})
    disposition, basis, references = None, "", []
    if key in new_scopes:
        disposition, basis = "NEW_CONDITIONAL_ESTIMATE_PREPARED", new_scopes[key]
    elif key in recovery_keys:
        disposition, basis = "EXISTING_ESTIMATE_DISPLAY_RECOVERY", "Existing source dictionary has scoped numeric weights omitted by current projection."
    elif cid == "BC-WALL-CIRCLE" and scope == "BASE":
        disposition, basis = "FAMILY_WEIGHT_REFERENCE", "Use approved Wall Circle family working catalogue; do not create a new weight for this header."
        references = [frozen["wall_circle"]]
    elif node.get("status", "").startswith("RESOLVED_") and "NO_ADDITIONAL_PRODUCT" in node.get("status", ""):
        disposition, basis = "CANONICAL_COMPONENT_REFERENCE_ONLY", node["status"]
        references = [{"component_id": node.get("canonical_component_id"), "scope": node.get("canonical_size_finish_variant_id")}]
    elif cid == "BC-MIX-SPIRALS":
        disposition, basis = "OWNER_DEFERRED_COLLECTION_REFERENCE", "Individual identification/specifications remain deferred by owner; no new products inferred."
    elif key == ("BC-CHELSEA", "SOURCE-G233002"):
        disposition, basis = "SOURCE_ALIAS_REFERENCE_ONLY", "Existing Chelsea design reference, not an additional individual product.250x100cm/base mass must not transfer to this unscaled source image."
    elif re.search(r"\d\s*(?:kg|kilogram)", row[4], re.I):
        disposition, basis = "EXISTING_SCOPED_APPROXIMATION_ACCEPTED", "Retain exact currently displayed numeric weight/range, its scope, conflicts and conditional source labels; no averaging."
    elif scope == "BASE" and children[cid]:
        disposition, basis = "USE_FINISH_OR_BUILD_WEIGHT_RECORDS", "Source/family heading; use individually scoped finish/build records rather than assign one mass across versions."
        references = [{"component_id": cid, "scope": s} for s in children[cid]]
    elif cid.startswith("BC-PORTMAN-") or cid.startswith("BC-BAR-STUDY-"):
        disposition, basis = "SOURCE_GROUP_POSITION_REFERENCE", "Existing context/source position, with no object-specific size/construction established. Retain scope; no new individual specification or extra product invented from grouped scene."
    else:
        raise AssertionError(("Unhandled weight coverage scope", key, row[:7]))
    audit.append({
        "component_id": cid, "scope": scope, "name": name,
        "review_kind": review_rows[key][3], "identity_status": review_rows[key][4],
        "original_weight_row": row, "disposition": disposition, "basis": basis,
        "references": references, "new_physical_count": 0,
    })
summary = dict(Counter(x["disposition"] for x in audit))
audit_ref = save(BASE / "WEIGHT_COVERAGE_AUDIT.json", {
    "status": "COMPLETE_FOR_FROZEN_BATCH87_REVIEW_PROJECTION",
    "checked_utc": NOW, "policy_id": POLICY_ID,
    "source_projection": data_ref, "source_imports_through_batch": 87,
    "review_weight_rows": len(audit), "counts_are_overlapping_review_scopes_not_unique_sculptures": True,
    "disposition_counts": summary, "rows": audit,
    "additional_family_catalogue_source": frozen["wall_circle"],
    "new_estimate_scopes": [{"component_id": a, "scope": b, "reason": c} for (a, b), c in new_scopes.items()],
    "display_recoveries": recovery_ref,
    "unhandled_projected_weight_rows": 0, "shared_master_writes_by_lane": False,
    "remote_mutations": 0, "private_original_downloads": 0,
})
save(BASE / "PREPARED_INDEX.json", {
    "reserved_batch": 90, "policy": policy_ref, "owner_evidence": owner_ref,
    "allocation": allocation_ref, "coverage_audit": audit_ref,
    "display_recoveries": recovery_ref, "new_estimates_pending_separate_file": 9,
    "source_owner_session": LANE, "shared_writer_session": ROOT,
})
print(json.dumps({"status": "PREPARED", "policy": policy_ref, "audit": audit_ref,
                  "dispositions": summary, "recoveries": len(recoveries)}))
