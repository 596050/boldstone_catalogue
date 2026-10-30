"""Read the coordinator's immutable candidate against independently frozen inputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
B = HERE.parent / "product-register-lane-b-audit-2026-10-20"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument("--graph", required=True)
parser.add_argument("--sha256", required=True)
parser.add_argument("--link-proof", default=str(HERE / "MCP4_MANUAL_CURRENT_LINK_OVERLAY_VERIFIED.json"))
parser.add_argument("--stage", choices=["draft", "final"], default="final")
args = parser.parse_args()
path = Path(args.graph).resolve()
assert sha(path) == args.sha256, "Candidate changed or wrong candidate requested"
g = read(path)
a = read(B / "inputs/canonical-products.json")
wall = read(B / "WALL_CIRCLE_REGISTER_SUPPLEMENT_VERIFIED.json")
links = read(args.link_proof)
family = read(B / "FAMILY_AND_ARRANGEMENT_EDGES.json")
source_model = read(B / "inputs/component_register.json")
source_rows = read(B / "inputs/refresh-data.json")
ledger = read(B / "inputs/user_classifications.json")
decisions = {d["decision_id"]: d for items in ledger.values() if isinstance(items, list) for d in items if isinstance(d, dict) and d.get("decision_id")}
checks = {}


def check(name, passed):
    checks[name] = bool(passed)


options = g["options"]
option_by_id = {o["product_id"]: o for o in options}
by_key = {o["canonical_key"]: o for o in options}
components = g["components"]
component_by_id = {c["component_id"]: c for c in components}
summary = g["summary"]
check("Unique current option IDs and scoped keys", len(options) == len(option_by_id) == len(by_key))
check("Unique component identity IDs", len(components) == len(component_by_id))
check("Every option has exactly one component family or explicit unbound-source scope", all(sum([bool(o.get("canonical_component_id")), bool(o.get("option_family_id")), bool(o.get("unbound_size_option"))]) == 1 for o in options))
photo_bound = [o for o in options if o.get("file_id") and o.get("folder_id") and o.get("image_url") and o.get("folder_url")]
photo_unbound = [o for o in options if o not in photo_bound]
check("Every missing primary image is an explicitly unbound source option", all(o.get("unbound_size_option") and o["canonical_component_id"] is None for o in photo_unbound))
check("Photo-bound option count matches actual stable-ID references", len(photo_bound) == summary.get("individual_options_with_dropbox_reference", len(options)))
check("Every named option retains six scoped field groups", all(len(o["specifications"]) == 6 for o in options))
check("Every option retains explicit individual sale-unit wording", all(o.get("sale_unit") for o in options))
check("All current options retain both globally offered fixing choices", all(set(o.get("offered_fixing_choices", [])) == {"Keyhole fixing", "French cleat"} for o in options))
check("Offered fixing choices do not certify installed hardware", all(o.get("offered_choices_do_not_confirm_current_installed_hardware") is True for o in options))
check("Component count equals actual identity records", summary["identified_component_identities"] == len(components))
check("Option count equals actual named option records", summary["individual_named_working_options"] == len(options))
check("Wall Circle not silently assigned an identified component form", all(o["canonical_component_id"] is None for o in options if o.get("option_family_id") == "BC-WALL-CIRCLE"))
check("Unknown whole-library unique design and physical counts remain unknown", all(summary[k] is None for k in ["physical_stock_quantity", "physical_mould_count", "catalogue_wide_unique_design_total_including_unresolved_sources"]))
check("Every component retains physical stock and mould uncertainty", all(c["physical_mould_count"] is None and c["physical_stock_quantity"] is None for c in components))

for component in components:
    cid = component["component_id"]
    expected = {o["product_id"] for o in options if o.get("canonical_component_id") == cid}
    check("Reciprocal component option links " + cid, set(component["option_ids"]) == expected and component["option_count"] == len(expected))
    check("Nonempty family membership " + cid, bool(component["family"]) and all(option_by_id[pid]["family"] == component["family"] for pid in expected))
check("Identified component option sum is independent of Wall Circle family", sum(c["option_count"] for c in components) == summary["individual_options_on_identified_components"])
check("No dangling option component IDs", all(not o.get("canonical_component_id") or o["canonical_component_id"] in component_by_id for o in options))
check("All original173 stable product IDs retained", set(p["product_id"] for p in a["products"]) <= set(option_by_id))
for alias in a["historical_alias_reconciliation"]:
    matching = [row for row in g["aliases"] if row["source"] == alias["source_scope"] and row["targets"] == alias["targets"]]
    check("Historical alias still resolves to same canonical targets " + alias["source_scope"], len(matching) == 1)
for source_scope, source_name in [
    ("BC-CONCAVE|CM-WHITE-25", "Concave Moon"),
    ("BC-CONCAVE|CM-SILVER-25", "Concave Moon — Silver and Bronze"),
    ("BC-CONCAVE|CM-VERDIGRIS-25", "Concave Moon — Verdigris"),
]:
    check("Historical human alias name remains searchable " + source_scope, any(row["source"] == source_scope and row.get("source_name") == source_name for row in g["aliases"]))
expected_families = {e["product_id"]: e["family"] for e in family["product_family_edges"]}
corrections = {r["product_id"]: r for r in g.get("scoped_working_corrections", {}).get("records", [])}
correction_fields = dict(zip(
    ["Dimensions / depth", "Weight", "Material / finish", "Fixing", "Individual price", "Availability"],
    ["dimensions", "weight", "material_finish", "fixing", "individual_price", "availability"],
))
if corrections:
    binding = g["input_manifest"]["scoped_working_corrections"]
    check("Four scoped corrections bound to exact sealed source package bytes", sha(binding["snapshot"]) == binding["sha256"] and read(binding["snapshot"]) == g["scoped_working_corrections"] and len(corrections) == 4)
for original in a["products"]:
    pid = original["product_id"]
    current = option_by_id[pid]
    check("Original scoped key and source names retained " + pid, current["canonical_key"] == original["canonical_key"] and current["source_scopes"] == original["source_scopes"] and set(original["retained_names"]) <= set(current["retained_names"]))
    unchanged_or_scoped = set(current["specifications"]) == set(original["specifications"])
    for field, old_field in original["specifications"].items():
        current_field = current["specifications"][field]
        original_content_preserved = all(current_field.get(k) == v for k, v in old_field.items() if k != "display")
        if current_field["display"] == old_field["display"]:
            display_traceable = True
        else:
            authorized = corrections.get(pid, {}).get("specifications", {}).get(correction_fields[field])
            display_traceable = (
                current_field.get("prior_working_display") == old_field["display"]
                and authorized is not None
                and current_field.get("scoped_current_working_overlay") == authorized
                and current_field["display"] == authorized["display"]
            )
        unchanged_or_scoped &= original_content_preserved and display_traceable
    check("Original six fields preserved or explicitly source-corrected with all prior assertions retained " + pid, unchanged_or_scoped)
    check("Source family retained " + pid, current["family"] == expected_families[pid])
    check("Original physical uncertainty retained " + pid, current["physical_specifications_verified"] is False)

# Independently check the explicit source normalization cases.
am_options = [o for o in options if o["canonical_key"].startswith("AM-")]
check("Four Ammonite size records retained", {o["canonical_key"] for o in am_options} == {"AM-S1|BASE", "AM-S2|BASE", "AM-L1|BASE", "AM-L2|BASE"})
check("Ammonite first and second panels each retain separate Small and Large choices", all({o["size_class"] for o in am_options if o["canonical_component_id"] == cid} == {"Small", "Large"} for cid in ["BC-AM-1", "BC-AM-2"]))
spice = [o for o in options if o["canonical_key"].startswith("BC-SPICE|")]
check("Two separately kept Spice panels have separate component identities", len(spice) == 2 and len({o["canonical_component_id"] for o in spice}) == 2)
leaf = [o for o in options if o["canonical_key"] == "BC-LEAF-FORM|LEAF-FORM-LF1-WHITE"]
check("Leaf Form White keeps both orientation choices in one option", len(leaf) == 1 and set(leaf[0]["orientation_options"]) == {"LF1", "LF2"} and len(leaf[0]["source_scopes"]) == 2)
for cid in ["BC-BONE-1", "BC-BONE-2"]:
    option = by_key[cid + "|BASE"]
    decision = decisions[cid + ":identity:keep"]
    check("Bone identity grounded in existing owner decision " + cid, option["identity_decision"] == decision)
    check("Bone specification gaps not promoted by identity count " + cid, option["six_working_fields_recorded"] is False and all(x["working_accepted"] is False for x in option["specifications"].values()))
    native_rows = {x[3]: x for x in source_rows["specifications"] if x[0] == cid and x[1] == "BASE"}
    check("Bone source values are not divided from set values " + cid, all(v["display"] == native_rows[k][4] for k, v in option["specifications"].items()))

field_names = dict(zip(
    ["dimensions_and_depth", "weight", "material_and_finish", "fixings_and_lighting", "individual_price", "availability"],
    ["Dimensions / depth", "Weight", "Material / finish", "Fixing", "Individual price", "Availability"],
))
for visual in wall["visual_working_records"]:
    key = "BC-WALL-CIRCLE|" + visual["review_id"]
    current = by_key[key]
    check("Exact Wall Circle visual source retained " + key, current["original_visual_record"] == visual and current["name"] == visual["working_name"] and current["file_id"] == visual["primary_file_id"] and current["folder_id"] == visual["primary_folder_id"])
    for field in visual["specification_review_items"]:
        check("Wall Circle original field retained " + key + ":" + field["group"], current["specifications"][field_names[field["group"]]]["source_field_record"] == field)
check("WC01 confirmed gypsum substrate remains in current material display", "gypsum" in by_key["BC-WALL-CIRCLE|WC-01"]["specifications"]["Material / finish"]["display"].lower())
check("Seven kept visual options have one unresolved option-family heading", len(g["option_families"]) == 1 and g["option_families"][0]["option_family_id"] == "BC-WALL-CIRCLE" and g["option_families"][0]["visual_options"] == 7 and g["option_families"][0]["identified_component_design_count"] is None)
check("All144 native Wall Circle variants retained exactly as source", g["wall_circle_native_options"] == wall["native_options"])
check("Wall Circle native rows are not added to named working option count", summary["wall_circle_native_source_combinations_not_added"] == 144 and summary["wall_circle_kept_visual_options"] == 7 and len([o for o in options if o.get("option_family_id")]) == 7)
for o in options:
    if o.get("unbound_size_option"):
        check("Unbound source size option contributes no extra component identity " + o["canonical_key"], o["canonical_component_id"] is None and o["option_family_id"] is None and o.get("owner_name_keep_recorded") is False and bool(o.get("source_closure_evidence")) and not o.get("file_id"))

for update in links["current_product_link_updates"]:
    current = option_by_id[update["product_id"]]
    check("Current MCP4 link overlay applied " + current["canonical_key"], all(current[k] == v for k, v in update["current_values"].items()) and current["file_id"] == update["primary_file_id_preserved"])
    check("Historical MCP4 primary link retained as historical source " + current["canonical_key"], all(current["historical_primary_link"][k] == v for k, v in update["historical_values"].items() if k in ["file_id", "folder_id", "image_url", "folder_url"]))
deleted_ids = set(links.get("confirmed_deleted_alias_folder_ids", [])) or {x["deleted_folder_id"] for x in links["folder_replacements"]}
check("No current product primary folder uses a deleted alias", not {o["folder_id"] for o in options}.intersection(deleted_ids))
check("Current link receipt unchanged and flattening not promoted", g["current_link_overlay"] == links and links["proposal_destinations_promoted_to_live"] is False)
check("Manual flattened paths are supported by current verification", not links.get("current_manual_change_verified") or all("/Moon Crater Phase/Moon Crater Phase 4/" not in x["current_file_path"] for x in links["moved_file_replacements"]))
check("All original1668 review assertions preserved", g["original_review_specification_assertions"] == source_rows["specifications"])
check("125 source component IDs disposed exactly once", len(g["source_component_dispositions"]) == 125 and {x["source_component_id"] for x in g["source_component_dispositions"]} == set(c["component_id"] for c in source_model["components"]))
check("278 review scopes disposed exactly once", len(g["source_review_reconciliation"]) == 278 and {x["source_scope"] for x in g["source_review_reconciliation"]} == {x["source_scope"] for x in a["scope_reconciliation"]})
check("All81 original platform offer records retained", len(g["source_offer_edges"]) == 81 and {x["offer_ref"] for x in g["source_offer_edges"]} == {x["offer_ref"] for x in source_model["platform_records"]})
source_bom = {r["bom_id"]: r for r in source_model["bom"]}
current_bom = {r["bom_id"]: r["original_bom"] for x in g["source_offer_edges"] for r in x["members"]}
check("All122 source BOM associations retained exactly", current_bom == source_bom and len(current_bom) == 122)
check("Source sets and aliases add no extra individual units", all(x["individual_count_increment"] == 0 for x in g["source_sets"] + g["aliases"]))
check("Confirmed Moonshell Lava membership retained exactly", g["confirmed_arrangement_member_edges"] == family["explicit_arrangement_member_edges"])
check("All27 original group and position references retained without decomposition", {r["reference_id"] for r in g["arrangement_context_references"]} == {r["reference_id"] for r in a["references"]} and all(r["individual_count_increment"] == 0 and r["counted_as_individual_option"] is False for r in g["arrangement_context_references"]))
for edge in g["confirmed_arrangement_member_edges"]:
    check("Reciprocal confirmed arrangement link " + edge["product_id"], edge["reference_id"] in option_by_id[edge["product_id"]]["confirmed_arrangement_ids"])
check("No source mutation during readback", sha(path) == args.sha256)
seal = read(B / "SEALED_MANIFEST.json")
check("All22 sealed B input/evidence artifacts unchanged", all(sha(B / f["relative_path"]) == f["sha256"] for f in seal["files"]))

result = {
    "schema": "boldstone.final-count-graph-independent-readback.v1",
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS" if all(checks.values()) else "FAIL",
    "stage": args.stage,
    "current_link_publication_ready": args.stage == "final" and all(checks.values()),
    "stage_limit": "Draft structure only; later verified folder moves must be applied before publication" if args.stage == "draft" else "Graph readback; saved-workbook checks are separate",
    "graph": str(path), "graph_sha256": args.sha256,
    "current_link_proof": {"path": str(Path(args.link_proof).resolve()), "sha256": sha(args.link_proof)},
    "checks_passed": sum(checks.values()), "checks_failed": sum(not c for c in checks.values()),
    "failed_checks": [k for k, v in checks.items() if not v],
    "checks": {k: "PASS" if v else "FAIL" for k, v in checks.items()},
    "summary_recomputed": {
        "identified_component_identities": len(components),
        "individual_named_working_options": len(options),
        "identified_component_options": sum(bool(o["canonical_component_id"]) for o in options),
        "wall_circle_visual_options": sum(bool(o["option_family_id"]) for o in options),
        "option_families": len(g["option_families"]),
        "documented_unbound_size_options": sum(bool(o.get("unbound_size_option")) for o in options),
        "options_with_stable_dropbox_reference": len(photo_bound),
        "group_and_arrangement_references": len(g["arrangement_context_references"]),
    },
    "root_summary": summary,
    "whole_library_unique_design_count_claimed": False,
    "physical_specifications_verified": False, "shared_master_writes": 0,
    "remote_reads": 0, "remote_writes": 0,
}
out = HERE / (args.stage.upper() + "_GRAPH_READBACK_" + args.sha256[:16] + ".json")
assert not out.exists(), out
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"path": str(out), "sha256": sha(out), "status": result["status"], "passed": result["checks_passed"], "failed": result["failed_checks"], "summary": result["summary_recomputed"]}))
