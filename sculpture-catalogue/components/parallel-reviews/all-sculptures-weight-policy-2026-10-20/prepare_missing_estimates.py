"""Nine bounded working-weight estimates; no shared catalogue edits."""
from pathlib import Path
import datetime
import hashlib
import json

BASE = Path(__file__).resolve().parent
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
ref = lambda p: {"path": str(p), "sha256": sha(p)}


def save(name, value):
    p = BASE / name
    assert not p.exists(), p
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return ref(p)


policy = read(BASE / "GLOBAL_APPROXIMATE_WEIGHT_POLICY.json")
projection_path = BASE / "source-snapshots/refresh-data-batch87.json"
data = read(projection_path)
rows = {(r[0], r[1], r[3]): r for r in data["specifications"]}
reviews = {(r[0], r[1]): r for r in data["reviews"]}
source_ref = ref(projection_path)
estimates = []


def add(cid, scope, nominal, bounds, display, assumptions, method, comparators, model=None):
    key = (cid, scope)
    assert 0 < bounds[0] <= nominal <= bounds[1]
    weight = rows[(*key, "Weight")]
    dims = rows[(*key, "Dimensions / depth")]
    material = rows[(*key, "Material / finish")]
    item = {
        "decision_id": f"{cid}:{scope}:WEIGHT-ESTIMATE:POLICY90",
        "component_id": cid, "scope": scope, "canonical_name": reviews[key][2],
        "field": "Weight", "display": display,
        "nominal_estimated_dry_artwork_kg": nominal,
        "working_range_kg": bounds,
        "estimate_kind": "CONDITIONAL_COMPARATOR_ESTIMATE",
        "estimate_uncertainty": "Broad working interval; not a measured or statistically certified interval",
        "status": "WORKING_WEIGHT_ESTIMATE_ACCEPTED_UNDER_GLOBAL_OWNER_POLICY",
        "acceptance_policy_id": policy["policy_id"],
        "acceptance_basis": "GLOBAL_OWNER_WEIGHT_INSTRUCTION",
        "owner_accepted_working_estimate": True,
        "individual_owner_reply": None, "new_individual_owner_reply": False,
        "recorded_utc": NOW,
        "source_projection": source_ref,
        "prior_weight_row_preserved": weight,
        "dimension_row_preserved": dims,
        "material_row_preserved": material,
        "other_five_field_rows_preserved": [r for r in data["specifications"] if r[:2] == list(key) and r[3] != "Weight"],
        "assumptions": assumptions, "method": method,
        "comparator_rows": [rows[tuple(c)] for c in comparators],
        "calculation": model,
        "assumed_material_identified_as_actual": False,
        "assumed_construction_independently_verified": False,
        "actual_weight_measured": False, "physical_specs_verified": False,
        "packed_shipping_weight": None, "wet_operating_or_system_weight": None,
        "installation_or_load_capacity_verified": False,
        "entire_set_mass_divided": False,
        "current_image_link": weight[7], "current_folder_link": weight[8],
        "primary_file_id": weight[9], "folder_id": weight[10],
        "other_five_fields_changed": False, "new_identity_or_physical_count": 0,
        "shared_master_writes_by_lane": False, "remote_mutations": 0,
    }
    assert len(item["other_five_field_rows_preserved"]) == 5
    estimates.append(item)


add(
    "BC-FP-LEFT", "FP-LEFT-VERDIGRIS", 6, [4, 9],
    "Approximately6kg; broad working range4–9kg — conditional estimate for the owner-stated40x40cm panel, using the existing White-version6kg model as a comparison. Material, thickness, backing and actual mass remain unverified.",
    ["Owner-stated40x40cm face retained.",
     "Assume a cast mineral-composite relief with broadly similar average thickness/backing to the White-version planning model.",
     "The White model assumed2cm average solid thickness and Jesmonite-like material; neither assumption is a confirmed Verdigris fact."],
    "Retain6kg as a rounded same-footprint comparison and widen to4–9kg for unverified construction and finish. This is a new estimate for Verdigris, not a transferred owner White measurement.",
    [("BC-FP-LEFT", "FP-LEFT-WHITE", "Weight"),
     ("BC-FP-LEFT", "FP-LEFT-WHITE", "Dimensions / depth")],
    {"comparator_nominal_kg": 6, "face_area_ratio_assumed": 1,
     "working_lower_factor": 2 / 3, "working_upper_factor": 1.5},
)
for scope in ["FFS2-TERRACOTTA", "FFS2-VERDIGRIS"]:
    add(
        "BC-FFS-2", scope, 5, [3, 7],
        "Approximately5kg; working range3–7kg — conditional estimate for the listed70x15cm cast. Uses the historical White4–6kg calculation as a comparison, widened for different composite/finish; this cast is unweighed.",
        ["Listing footprint70x15cm and overall depth7cm are source claims, not measured here.",
         "Assume broadly comparable relief volume to the White historical template.",
         "The coloured listing says gypsum composite; equivalent AC730 density or construction is not confirmed."],
        "Use5kg as a rounded working nominal within the historical White4–6kg range, then broaden one kilogram at each end for finish/substrate/backing uncertainty. No source set mass is divided.",
        [("BC-FFS-2", "FFS2-WHITE", "Weight"),
         ("BC-FFS-2", "FFS2-WHITE", "Dimensions / depth")],
        {"historical_comparator_range_kg": [4, 6], "chosen_nominal_kg": 5,
         "uncertainty_extension_kg": 1},
    )
for cid, scope in [
    ("BC-GLEN-1", "GLEN-TOP-LEFT-WHITE"), ("BC-GLEN-2", "GLEN-TOP-RIGHT-WHITE"),
    ("BC-GLEN-3", "GLEN-BOTTOM-LEFT-WHITE"), ("BC-GLEN-4", "GLEN-BOTTOM-RIGHT-WHITE"),
]:
    add(
        cid, scope, 5, [3, 8],
        "Approximately5kg per panel; broad working range3–8kg — estimate for the owner-specified35x35cm face. Assumes a cast mineral/plaster relief of broadly comparable construction to the Acanthus30x30cm working model; depth, composition and actual mass remain unverified.",
        ["Owner specified each individual panel35x35cm; this estimate does not divide a whole-arrangement weight.",
         "Assume a cast mineral/plaster relief with similar average material thickness/backing to the comparator.",
         "Actual panel depths, binder, hollowing, reinforcement and finish mass remain unknown."],
        "Area-scale the existing Acanthus30x30cm nominal4kg and3–5kg working range by(35/30)^2. This gives5.44kg and4.08–6.81kg; use rounded5kg with a wider3–8kg working range for unverified relief depth and construction.",
        [("BC-AC-ONE", "BASE", "Weight"), ("BC-AC-ONE", "BASE", "Dimensions / depth")],
        {"comparator_face_cm": [30, 30], "owner_face_cm": [35, 35],
         "area_ratio": (35 / 30) ** 2, "area_scaled_nominal_kg": 4 * (35 / 30) ** 2,
         "area_scaled_range_kg": [3 * (35 / 30) ** 2, 5 * (35 / 30) ** 2],
         "rounded_and_widened_working_range_kg": [3, 8]},
    )
add(
    "BC-CHELSEA", "BASE", 100, [75, 140],
    "Approximately100kg dry panel; broad working range75–140kg — new conditional estimate for the owner-confirmed250x100cm Chelsea reference. Assumes a cast mineral relief with backing comparable to the cited large-panel examples; actual construction/mass remain unknown. Supersedes the25kg smaller-size guess; does not apply to source002.",
    ["The owner-confirmed face is250cm high by100cm wide, area2.5m², for this specific reference only.",
     "Assume a cast mineral-composite relief/backing broadly comparable to the Icarus and Chiswick planning examples.",
     "The previous10cm overall-depth guess is not treated as uniform solid thickness.",
     "Do not transfer these dimensions or this estimate to unscaled Chelsea source002/G233."],
    "Use separate large-panel comparisons to bound a new planning estimate: Icarus60kg/2m² suggests75kg at2.5m²; Chiswick35kg/0.665m² suggests about132kg. Choose a rounded100kg planning nominal and widen the upper end to140kg. These are analogies between different pieces, not conflicting Chelsea measurements or an averaged source claim.",
    [("BC-ICARUS", "BASE", "Weight"), ("BC-ICARUS", "BASE", "Dimensions / depth"),
     ("BC-CHISWICK", "CHISWICK-WALL", "Weight"),
     ("BC-CHISWICK", "CHISWICK-WALL", "Dimensions / depth")],
    {"owner_face_area_m2": 2.5,
     "icarus_comparison": {"artwork_kg": 60, "face_area_m2": 2, "scaled_kg": 75},
     "chiswick_comparison": {"artwork_kg": 35, "face_area_m2": 0.665,
                            "scaled_kg": 35 / 0.665 * 2.5},
     "chosen_heuristic_nominal_kg": 100, "prior25kg_model_reactivated": False},
)
add(
    "BC-KNIGHT", "KNIGHT-WHITE", 100, [60, 180],
    "Approximately100kg dry sculpture; very broad60–180kg working range — conditional on an assumed hollow, open-backed mineral-composite shell for the owner-stated100x100x50cm form. Actual material, wall thickness, internal structure and mass are unknown; solid construction would require a different estimate. Water/system and packed weights are excluded.",
    ["Keep owner dimensions100x100x50cm literally;50cm is overall body depth.",
     "Assume a hollow/open-backed cast mineral-composite form rather than a solid bounding box.",
     "For this model only, approximate one1x1m face plus four1x0.5m returns, giving about3m² of shell surface.",
     "Assume20–60kg of dry shell/backing per square metre as a deliberately broad model interval, informed by catalogue large-panel comparisons around30 and53kg/m².",
     "No supplied proof establishes the actual shell, material, wall thickness, sump, internal supports or reinforcement.",
     "No retained water, pump/plumbing, packaging or transport supports are included."],
    "Multiply the assumed3m² shell surface by the assumed20–60kg/m² planning interval to obtain60–180kg. Use100kg as a rounded provisional nominal (about33kg/m²), not a measured mass. No50mm reinterpretation and no solid1x1x0.5m volume calculation.",
    [("BC-ICARUS", "BASE", "Weight"), ("BC-ICARUS", "BASE", "Dimensions / depth"),
     ("BC-CHISWICK", "CHISWICK-WALL", "Weight"),
     ("BC-CHISWICK", "CHISWICK-WALL", "Dimensions / depth")],
    {"owner_outer_dimensions_cm": [100, 100, 50], "assumed_open_back": True,
     "assumed_shell_surface_area_m2": 1 * 1 + 4 * 1 * 0.5,
     "assumed_surface_mass_range_kg_m2": [20, 60], "resulting_conditional_range_kg": [60, 180],
     "chosen_heuristic_nominal_kg": 100, "solid_bounding_box_volume_used": False},
)
assert len(estimates) == 9
estimate_ref = save("MISSING_WEIGHT_ESTIMATES.json", {
    "schema": "boldstone.missing-weight-working-estimates.v1", "prepared_utc": NOW,
    "status": "READY_FOR_INDEPENDENT_CHECK_AND_SOLE_WRITER_IMPORT",
    "policy_id": policy["policy_id"], "new_conditional_weight_estimates": 9,
    "new_owner_policy_events": 0, "new_individual_owner_replies": 0,
    "new_six_field_acceptances": 0, "new_identity_or_physical_counts": 0,
    "items": estimates, "shared_master_writes_by_lane": False, "remote_mutations": 0,
})

model_path = BASE / "source-snapshots/model-batch87.json"
model = read(model_path)
bar = next(x for x in model["platform_records"] if x["offer_ref"] == "O078")
phrase = "weighing approximately 83 kg"
assert phrase in bar["native_description"] and bar["native_parts"] == 1 and bar["sale_unit_state"] == "Sale component"
wall_path = BASE / "source-snapshots/wall-circle-approved-working-catalogue.json"
wall = read(wall_path)
assert "12 kg" in wall["family_approval"]["working_50cm_template"]["weight"]
assert wall["wc01_owner_stated_entry"]["weight"] == "Approximately 12 kg"
save("EXPLICIT_UNIT_AND_FAMILY_SCOPE_CHECK.json", {
    "checked_utc": NOW, "status": "PASS",
    "barbados_wave": {
        "source": ref(model_path), "pointer": "platform_records[offer_ref=O078].native_description",
        "explicit_unit_excerpt": phrase, "native_parts": 1, "sale_unit_state": "Sale component",
        "artwork_mass_not_packed_shipping_mass": True,
        "raw_numeric_weight_field_not_converted": True,
        "raw_export_weight_preserved_separately": bar["raw_weight"],
        "dated_source_only_no_live_price_or_platform_refresh_claim": True,
    },
    "wall_circle": {
        "source": ref(wall_path), "owner_piece_weight": wall["wc01_owner_stated_entry"]["weight"],
        "family_template_weight": wall["family_approval"]["working_50cm_template"]["weight"],
        "scope": "Existing approved50cm family working template only; approximately12kg remains an estimate outside WC01 and approximate for WC01. Native18.5/36/100cm options are not overwritten.",
        "all_native_option_weight_units_inferred": False,
        "native_option_rows_preserved": len(wall["native_option_register"]),
        "new_physical_inventory_count": 0,
    },
})
print(json.dumps({"status": "PREPARED", "estimates": estimate_ref,
                  "values": [{"name": e["canonical_name"], "kg": e["nominal_estimated_dry_artwork_kg"],
                              "range_kg": e["working_range_kg"]} for e in estimates]}))
