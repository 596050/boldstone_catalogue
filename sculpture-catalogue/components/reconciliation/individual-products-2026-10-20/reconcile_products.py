"""Create an additive individual-product view from the sealed review97 sources.

No source records, approval ledgers, application code or remote content are changed.
The output counts catalogue configurations, not physical casts, moulds or stock.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def write(name, obj):
    path = HERE / name
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)
manifest = read(HERE / "input-manifest.json")
for item in manifest["sources"]:
    assert sha(Path(item["snapshot"])) == item["sha256"], item["snapshot"]
data = read(HERE / "inputs/refresh-data.json")
progress = read(HERE / "inputs/specification_review_progress.json")
model = read(HERE / "inputs/component_register.json")
decisions = read(HERE / "inputs/user_classifications.json")
FIELDS = ["Dimensions / depth", "Weight", "Material / finish", "Fixing", "Individual price", "Availability"]
rows = {"|".join(r[:2]): r for r in data["reviews"]}
assert len(rows) == len(data["reviews"]) == 278
specs = defaultdict(list)
for i, row in enumerate(data["specifications"]):
    specs["|".join(row[:2])].append((i, row))
for key, values in specs.items():
    assert len(values) == 6 and {r[3] for _, r in values} == set(FIELDS), key


def accepted(row):
    return row[5].startswith("Owner accepted")


working = {k for k in rows if all(accepted(r) for _, r in specs[k])}
assert len(working) == 174

# This one consolidation uses an explicit maker statement about the same mould.
# Both owner-kept names and every differently scoped assertion remain traceable.
orientation_primary = {"BC-LEAF-FORM|LEAF-FORM-LF2-WHITE": "BC-LEAF-FORM|LEAF-FORM-LF1-WHITE"}
orientation_basis = "component_register.aliases: LF2/LF1, manufacture-stevensons Sheet1 row34; one mould, opposite orientations"


def product_id(key):
    return "BSI-" + hashlib.sha256(key.encode()).hexdigest()[:12].upper()


product_scopes = defaultdict(list)
for key in working:
    product_scopes[orientation_primary.get(key, key)].append(key)
products = []
scope_to_product = {}
for key, source_keys in product_scopes.items():
    source_keys.sort(key=lambda s: (s != key, s))
    row = rows[key]
    pid = product_id(key)
    for source_key in source_keys:
        scope_to_product[source_key] = pid
    fields = {}
    for field in FIELDS:
        assertions = []
        for source_key in source_keys:
            i, s = next((i, s) for i, s in specs[source_key] if s[3] == field)
            assertions.append({"source_scope": source_key, "source_title": rows[source_key][2],
                               "display": s[4], "state": s[5], "basis": s[6],
                               "proposal_id": s[11], "source_row_index": i,
                               "image_url": s[7], "folder_url": s[8],
                               "file_id": s[9], "folder_id": s[10]})
        unique = list(dict.fromkeys(a["display"] for a in assertions))
        display = unique[0] if len(unique) == 1 else "\n\n".join(
            ("LF1 orientation" if "LF1-WHITE" in a["source_scope"] else "LF2 orientation") + ": " + a["display"]
            for a in assertions)
        fields[field] = {"display": display, "assertions": assertions,
                         "working_accepted": all(accepted(next(s for _, s in specs[a["source_scope"]] if s[3] == field)) for a in assertions)}
    item = {"product_id": pid, "canonical_key": key, "canonical_design_id": row[0],
            "name": "Leaf Form — White" if len(source_keys) > 1 else row[2],
            "retained_names": list(dict.fromkeys(rows[s][2] for s in source_keys)),
            "source_scopes": source_keys, "record_type": "INDIVIDUAL_WORKING_CATALOGUE_PRODUCT",
            "sale_unit": "One individually described sculpture or panel; no physical stock quantity asserted",
            "orientation_options": ["LF1", "LF2"] if len(source_keys) > 1 else [],
            "orientation_evidence": orientation_basis if len(source_keys) > 1 else "",
            "specifications": fields, "six_working_fields_recorded": all(fields[f]["working_accepted"] for f in FIELDS),
            "physical_specifications_verified": False, "platform_publication_performed": False,
            "image_url": row[7], "folder_url": row[8], "file_id": row[9], "folder_id": row[10],
            "context_status": row[13], "context_description": row[14],
            "context_image_url": row[15], "context_folder_url": row[16],
            "original_gap_notes": "\n".join(dict.fromkeys(rows[s][11] for s in source_keys if rows[s][11])),
            "source_scope_notes": "\n".join(dict.fromkeys(rows[s][12] for s in source_keys if rows[s][12]))}
    if key == "BC-CHELSEA|BASE":
        item["commercial_gap"] = "Obtain a current quote for the owner-stated 250 × 100 cm version; historical £1,100 is not a current asking price."
    products.append(item)
products.sort(key=lambda p: (p["name"].casefold(), p["canonical_key"]))
by_id = {p["product_id"]: p for p in products}


def ids_for_component(cid):
    return sorted({scope_to_product[k] for k in scope_to_product if k.split("|", 1)[0] == cid})


candidates = {
    "BC-BONE-1": ("Bone Spiral 1 / narrow panel (BS1)", "INDIVIDUAL_SOURCE_CANDIDATE", "Source and individual design references exist. Individual sale policy/current price and kept six-field review remain unconfirmed; do not divide the pair price or width."),
    "BC-BONE-2": ("Bone Spiral 2 / wide panel (BS2)", "INDIVIDUAL_SOURCE_CANDIDATE", "Source and individual design references exist. Individual sale policy/current price and kept six-field review remain unconfirmed; do not divide the pair price or width."),
    "BC-FFL-1": ("Frozen Fish Long (FFL1)", "INDIVIDUAL_SOURCE_CANDIDATE", "Dated maker 100 × 22 cm option exists. Exact current sculpture/reference and intended individually sold version remain unconfirmed; do not equate it with a shorter photograph."),
    "BC-CR-RING": ("Cup Ring (CRS2)", "INDIVIDUAL_SOURCE_CANDIDATE", "Documented maker design. Complete individual image and source-to-object identity remain unresolved; arrangement photograph is retained as context."),
    "BC-DR-WAVE3": ("Dune Ripple Waves — DR3", "INDIVIDUAL_SOURCE_CANDIDATE", "Separate plain-waves mould is documented. Current DR3/White applicability and individual review remain pending. DR3 is not the DDR3 orientation alias."),
    "BC-WALL-CIRCLE": ("Wall Circle pattern / lighting options", "OPTION_FAMILY_CANDIDATE", "One offered option family has 144 native option rows. Exact individually sellable size/pattern/lighting combinations need reconciliation; no 144 physical products or stock quantities are inferred."),
}
candidate_records = []
for cid, (name, kind, gap) in candidates.items():
    keys = [k for k in rows if k.split("|", 1)[0] == cid and k not in working]
    if cid == "BC-DR-WAVE3":
        keys = [cid + "|BASE"]
    candidate_records.append({"candidate_id": "CAND-" + cid.removeprefix("BC-"), "component_id": cid,
                              "name": name, "record_type": kind, "source_scopes": keys,
                              "required_information": gap,
                              "image_url": rows[keys[-1]][7], "folder_url": rows[keys[-1]][8],
                              "source_specifications": {k: [r for _, r in specs[k]] for k in keys},
                              "counted_as_working_product": False})

component_alias_targets = {
    "BC-AM-1": [p["product_id"] for p in products if p["canonical_design_id"] in ["AM-S1", "AM-L1"]],
    "BC-AM-2": [p["product_id"] for p in products if p["canonical_design_id"] in ["AM-S2", "AM-L2"]],
}
for old, new in progress["historical_source_component_to_catalogue_aliases"].items():
    component_alias_targets[old] = [scope_to_product[k] for k in working if k.split("|", 1)[1] in new]

reference_components = {
    "BC-PORTMAN-1": "Existing courtyard position only. No additional distinct individually sold sculpture established; retain owner reference disposition.",
    "BC-PORTMAN-2": "Unresolved courtyard position. No additional distinct individually sold sculpture established; component identification in group photographs remains deferred.",
    "BC-BAR-STUDY-1": "Workshop group position, not an identified extra individually sold design; retain as reference under group-photo policy.",
    "BC-BAR-STUDY-2": "Workshop group position, not an identified extra individually sold design; retain as reference under group-photo policy.",
    "BC-BAR-STUDY-3": "Workshop group position, not an identified extra individually sold design; retain as reference under group-photo policy.",
    "BC-MIX-SPIRALS": "Owner-deferred G050 collection reference. Individual identity and sale-unit review remain excluded until requested.",
}
resolved_wall_references = {d["component_id"]: d for d in decisions["component_identity_relationship_decisions"]
                            if d.get("relationship") == "POSITION_REFERENCE_IN_OWNER_CONFIRMED_COMBINED_ARRANGEMENT"}
assert set(resolved_wall_references) == {"BC-MLAVA-WALL-1", "BC-MLAVA-WALL-2"}
family_alias_components = {"BC-LUCIANO-1", "BC-LUCIANO-2", "BC-LUCIANO-3"}
mapping = []
for index, (key, row) in enumerate(rows.items()):
    cid, variant = row[:2]
    targets = []
    if key in scope_to_product:
        targets = [scope_to_product[key]]
        disposition = "ORIENTATION_OPTION" if key in orientation_primary else "INDIVIDUAL_PRODUCT"
        reason = orientation_basis if key in orientation_primary else "Kept individual scope with all six accepted working fields; preserve exact size, finish and build scope."
    elif key == "BC-DR-WAVE3|DR3-WHITE":
        targets = [scope_to_product["BC-DR-WAVE1|DR1-WHITE"]]
        disposition = "SELECTED_IMAGE_REFERENCE_ALIAS"
        reason = "Owner confirmed the selected image depicts the same design as DR1 White. This does not equate the historical DR3 maker code/mould; all six unapproved source assertions remain separate and are not inherited."
    elif cid in candidates:
        disposition, reason = "SOURCE_CANDIDATE", candidates[cid][2]
        targets = ["CAND-" + cid.removeprefix("BC-")]
    elif cid in component_alias_targets:
        disposition, reason = "HISTORICAL_DESIGN_OR_SIZE_HEADER", "Historical component heading maps to current size/finish records. Its generic claims are not copied over the scoped working specifications."
        targets = sorted(set(component_alias_targets[cid]))
    elif cid in resolved_wall_references:
        resolved = resolved_wall_references[cid]
        target_key = resolved["canonical_component_id"] + "|" + resolved["canonical_size_finish_variant_id"]
        disposition, targets = "RESOLVED_ARRANGEMENT_POSITION_REFERENCE", [scope_to_product[target_key]]
        reason = "Owner identified the combined arrangement as Moonshell Lava 1 White plus Moonshell Lava 2 White. Displayed left/right links derive from the reviewed image comparison; no extra product, physical cast or mould equivalence, or new specification approval."
    elif cid in reference_components:
        disposition, reason = "DEFERRED_COLLECTION_REFERENCE" if cid == "BC-MIX-SPIRALS" else "GROUP_POSITION_REFERENCE", reference_components[cid]
        targets = ["REF-G050" if cid == "BC-MIX-SPIRALS" else "REF-" + cid]
    elif cid in family_alias_components:
        disposition = "HISTORICAL_PROJECT_ALIAS"
        reason = "Owner confirms Luciano Moonshell Lava and Lava Moon are the same design family. Keep historical positions/finish/version separate; no exact position or finish allocation inferred."
        targets = sorted({pid for c in ["BC-LAVA-1", "BC-LAVA-2", "BC-LAVA-3"] for pid in ids_for_component(c)})
    elif key == "BC-CHELSEA|SOURCE-G233002":
        disposition, reason = "SAME_DESIGN_SOURCE_ALIAS", "Owner consolidated this Moon Ripple source under Chelsea Moonwave. Its source-specific unapproved specifications are not inherited as measurements of the 250 × 100 cm version."
        targets = ids_for_component("BC-CHELSEA")
    elif variant == "BASE" and ids_for_component(cid):
        disposition, reason = "DESIGN_HEADER", "Generic source/design heading; use the separately scoped individual finish/build records. No additional product or additional six-field approval."
        targets = ids_for_component(cid)
    else:
        raise AssertionError(("UNCLASSIFIED_SCOPE", key))
    mapping.append({"source_scope": key, "source_title": row[2], "source_review_index": index,
                    "disposition": disposition, "targets": targets, "reason": reason,
                    "image_url": row[7], "folder_url": row[8],
                    "specification_assertions_inherited": key in working,
                    "source_locator": f"refresh-data.json:reviews[{index}]"})

# Keep aliases removed from the current view traceable, without creating products.
alias_mapping = []
for old_key, alias in progress["canonical_variant_aliases"].items():
    new_key = alias["canonical_component_id"] + "|" + alias["canonical_variant_id"]
    assert new_key in scope_to_product
    alias_mapping.append({"source_scope": old_key, "source_title": old_key,
                          "disposition": "HISTORICAL_FINISH_ALIAS", "targets": [scope_to_product[new_key]],
                          "reason": "Recorded owner-confirmed canonical finish equivalence. Original specification approvals retain their original scope.",
                          "source_locator": alias["approval_record"], "specification_assertions_inherited": False})
for old_cid, alias in progress["canonical_component_consolidations"].items():
    alias_mapping.append({"source_scope": old_cid + "|BASE", "source_title": alias["former_name"],
                          "disposition": "HISTORICAL_DESIGN_ALIAS", "targets": ids_for_component(alias["canonical_component_id"]),
                          "reason": "Owner-confirmed design consolidation. Keep finish-specific specifications and the historical source component identifier; no additional Concave Moon listing.",
                          "source_locator": alias["approval_record"], "specification_assertions_inherited": False})

reference_alias = {"FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022": "FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001"}
reference_groups = defaultdict(list)
for row in data["groups"]:
    reference_groups[reference_alias.get(row[0], row[0])].append(row)
references = []
for ref, group_rows in reference_groups.items():
    row = next((r for r in group_rows if r[0] == ref), group_rows[0])
    name_status = row[2]
    name_correction = ""
    if ref in ["FINGERPRINT-WAVY-WHITE-G156001", "FINGERPRINT-SEGMENTED-WHITE-G156002"]:
        # These two older view rows omitted identity_confirmed despite sealed Keeps.
        hits = [d for d in decisions["source_design_name_decisions"] if d.get("source_design_key") == ref and d.get("approved_name") == row[1]]
        assert len(hits) == 1, ref
        name_status = "Owner kept source name; owner says design was made"
        name_correction = "Name-only view correction from existing source_design_name_decisions; no specification or individual sale approval added."
    references.append({"reference_id": "REF-" + ref, "name": row[1], "source_reference_ids": [r[0] for r in group_rows],
                       "record_type": "ARRANGEMENT_OR_COLLECTION_REFERENCE", "name_status": name_status,
                       "component_identification": row[3], "specifications": [{"source": r[0], "display": r[4], "state": r[5]} for r in group_rows],
                       "sale_unit_status": row[10], "notes": "\n".join(dict.fromkeys(r[10] for r in group_rows)),
                       "image_url": row[6], "folder_url": row[7], "name_display_correction": name_correction,
                       "images": [{"file_id": r[8], "folder_id": r[9], "image_url": r[6], "folder_url": r[7]} for r in group_rows],
                       "counted_as_working_product": False})
for cid, reason in reference_components.items():
    row = rows[cid + "|BASE"]
    if cid == "BC-MIX-SPIRALS":
        existing_collection = next(r for r in references if r["reference_id"] == "REF-G050")
        existing_collection["source_reference_ids"].append(cid + "|BASE")
        existing_collection["notes"] += "\n" + reason
        continue
    references.append({"reference_id": "REF-" + cid, "name": row[2], "source_reference_ids": [cid + "|BASE"],
                       "record_type": "SOURCE_POSITION_OR_COLLECTION_REFERENCE", "name_status": row[4],
                       "component_identification": "Deferred or unresolved; no additional individual product",
                       "sale_unit_status": "Not established", "notes": reason,
                       "image_url": row[7], "folder_url": row[8], "counted_as_working_product": False})
wall_pair = decisions["arrangement_membership_decisions"][0]
assert wall_pair["arrangement_id"] == "MLAVA-1-PLUS-2-WHITE" and wall_pair["owner_combined_membership_confirmed"]
wall_ref = wall_pair["current_dropbox_reference"]
references.append({"reference_id": "REF-MLAVA-1-PLUS-2-WHITE", "name": wall_pair["canonical_name"],
                   "source_reference_ids": [cid + "|BASE" for cid in sorted(resolved_wall_references)],
                   "record_type": "OWNER_CONFIRMED_COMBINED_ARRANGEMENT_REFERENCE", "name_status": "Owner confirmed the two named members",
                   "component_identification": "Moonshell Lava 1 White and Moonshell Lava 2 White; displayed positions derive from reviewed image comparison",
                   "member_product_ids": [scope_to_product[resolved_wall_references[c]["canonical_component_id"] + "|" + resolved_wall_references[c]["canonical_size_finish_variant_id"]] for c in sorted(resolved_wall_references)],
                   "sale_unit_status": "Two existing individual product records; no additional combined-product offer inferred",
                   "notes": "Owner-confirmed combined membership retained. This arrangement does not create a second version of either individual panel or confirm physical cast/mould identity.",
                   "image_url": wall_ref["image_url"], "folder_url": wall_ref["folder_url"],
                   "counted_as_working_product": False})

summary = {"working_products": len(products), "accepted_working_source_scopes": len(working),
           "product_field_groups": len(products) * 6, "accepted_source_field_assertions": len(working) * 6,
           "current_review_scopes_reconciled": len(mapping), "historical_aliases_mapped": len(alias_mapping),
           "source_candidates_requiring_information": len(candidate_records),
           "source_individual_design_candidates": sum(c["record_type"] == "INDIVIDUAL_SOURCE_CANDIDATE" for c in candidate_records),
           "option_families_requiring_information": sum(c["record_type"] == "OPTION_FAMILY_CANDIDATE" for c in candidate_records),
           "group_source_records": len(data["groups"]), "canonical_group_references": len(reference_groups),
           "total_reference_records_including_source_positions": len(references),
           "orientation_source_scopes_consolidated": len(orientation_primary),
           "all_kept_working_scopes_have_one_product_target": all(len([p for p in m["targets"] if p.startswith("BSI-")]) == 1 for m in mapping if m["source_scope"] in working),
           "all_six_working_fields_recorded": all(p["six_working_fields_recorded"] for p in products),
           "all_source_candidates_resolved": False, "all_actual_specifications_verified": False,
           "entire_physical_stock_or_mould_count_verified": False,
           "remote_reads": 0, "remote_writes": 0}
result = {"schema": "boldstone.canonical-individual-working-products.v1",
          "created_utc": datetime.now(timezone.utc).isoformat(), "source_review_batch": 97,
          "baseline_workbook_sha256": manifest["baseline_workbook_sha256"],
          "product_definition": "One reviewed individually described design, finish, size and build configuration. Documented opposite orientations of one mould share one product. This is a catalogue configuration count, not physical stock or a mould inventory.",
          "summary": summary, "products": products, "scope_reconciliation": mapping,
          "historical_alias_reconciliation": alias_mapping, "source_candidates": candidate_records,
          "references": references, "orientation_aliases": [a for a in model["aliases"] if a["relationship"] == "Same mould; orientation option"],
          "source_offer_coverage": [], "source_configuration_coverage": [], "source_manifest": "input-manifest.json"}
result["reference_aliases"] = {"REF-BC-MIX-SPIRALS": {
    "target_reference_id": "REF-G050",
    "reason": "The historical stacked-spiral source position belongs to the same owner-deferred G050 collection. Preserve the old reference key without creating another collection record."}}
result["source_only_assertions_not_applied_to_products"] = [
    {"source_scope": key, "source_row_index": i, "original_row": r}
    for key in rows if key not in working for i, r in specs[key]]
assert len(result["source_only_assertions_not_applied_to_products"]) + summary["accepted_source_field_assertions"] == 1668
summary["all_review97_field_assertions_accounted_for"] = 1668
coverage_path = HERE / "source-coverage-manifest.json"
if coverage_path.exists():
    coverage_manifest = read(coverage_path)
    for item in coverage_manifest["files"]:
        assert sha(Path(item["snapshot"])) == item["sha256"]
    result["source_offer_coverage"] = read(HERE / "inputs/source_offer_coverage.json")
    result["source_configuration_coverage"] = read(HERE / "inputs/source_configuration_coverage.json")
    assert len(result["source_offer_coverage"]) == 81
    assert len(result["source_configuration_coverage"]) == 199
    for offer in result["source_offer_coverage"]:
        offer["related_product_ids"] = sorted(set(offer.get("exact_supported_target_ids", []) + offer.get("covered_family_product_ids", [])))
        offer["component_ids"] = sorted({row["component_id"] for row in offer["bom_rows"]})
        offer["scope_note"] = "\n".join(dict.fromkeys([str(offer.get("source_cautions", "")), *offer.get("audit_notes", []), offer.get("source_unit_limits", "")]))
    for config in result["source_configuration_coverage"]:
        config["related_product_ids"] = sorted(set(config.get("exact_supported_target_ids", []) + config.get("covered_family_product_ids", [])))
    summary["source_platform_records_accounted_for"] = 81
    summary["source_configuration_records_accounted_for"] = 199
    summary["source_bom_rows_preserved"] = sum(len(o["bom_rows"]) for o in result["source_offer_coverage"])
    assert summary["source_bom_rows_preserved"] == 122
    summary["source_offer_coverage_states"] = dict(Counter(o["canonical_graph_coverage_state"] for o in result["source_offer_coverage"]))
    summary["source_configuration_coverage_states"] = dict(Counter(c["canonical_graph_coverage_state"] for c in result["source_configuration_coverage"]))
    assets = {a["id"]: a for a in model["assets"]}
    assets.update({a["id"]: a for a in data["asset_updates"]})
    additional = []
    for config in result["source_configuration_coverage"]:
        appearance = config["baseline_finish_appearance"]
        if config["canonical_graph_coverage_state"] != "COVERED_FAMILY_EXACT_SCOPE_PENDING":
            continue
        if appearance in ["Unspecified / mixed appearance", "Multicolour patina"]:
            continue
        file_id = next((f for f in config["example_file_ids"] if f in assets), "")
        asset = assets.get(file_id, {})
        file_path = asset.get("path", "")
        if file_path.startswith("ns:"):
            file_path = "/" + file_path.split("//", 1)[1].lstrip("/")
        folder_path = file_path.rsplit("/", 1)[0] if file_path else ""
        image = "https://www.dropbox.com/home" + quote(folder_path, safe="/") + "?preview=" + quote(file_path.rsplit("/", 1)[-1]) if file_path else ""
        folder = "https://www.dropbox.com/home" + quote(folder_path, safe="/") if folder_path else ""
        group_only = config["source_component_id"].startswith("BC-MCP-")
        gap = ("Shared Rust set/context reference. A standalone source or maker finish key is needed to determine whether this is a separate Rust-only finish or an existing Verdigris-and-Rust product. Keep group component identification deferred."
               if group_only else "The source appearance is recorded, but a complete individual reference or authoritative source-to-design/finish match is missing. Confirm an exact existing alias or intended separate sale variant before adding a product. Do not infer material chemistry from the colour label.")
        additional.append({"candidate_id": "FINISH-" + config["configuration_id"],
                           "name": config["source_component_name"] + " — " + appearance + " (source reference)",
                           "record_type": "UNRESOLVED_SOURCE_APPEARANCE_NOT_AN_ADDITIONAL_PRODUCT",
                           "required_information": gap, "source_configuration_ids": [config["configuration_id"]],
                           "source_file_ids": config["example_file_ids"],
                           "covered_family_product_ids": config.get("covered_family_product_ids", []),
                           "image_url": image, "folder_url": folder,
                           "source_notes": config.get("notes", []), "counted_as_working_product": False})
    result["additional_source_candidates"] = additional
    summary["named_source_appearances_without_exact_individual_match"] = len(additional)
    summary["all_source_offers_and_configurations_accounted_for"] = True
    summary["all_exact_source_variant_matches_resolved"] = False
write("canonical-products.json", result)
print(json.dumps(summary, ensure_ascii=False))
