"""Independently read the existing A graph and prepare scoped evidence for root.

This lane writes only this isolated audit directory. It never changes a shared
register, ledger, workbook, or Dropbox item.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
import hashlib
import json

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parents[2]
A = CATALOGUE / "components/reconciliation/individual-products-2026-10-20"
SNAP = HERE / "inputs"
SNAP.mkdir(exist_ok=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(name, value):
    path = HERE / name
    assert not path.exists(), path
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(path), "sha256": sha(path)}


sources = {}
for name, source in {
    "canonical-products.json": A / "canonical-products.json",
    "refresh-data.json": A / "inputs/refresh-data.json",
    "component_register.json": A / "inputs/component_register.json",
    "specification_review_progress.json": A / "inputs/specification_review_progress.json",
    "user_classifications.json": A / "inputs/user_classifications.json",
    "wall-circle-approved-working-catalogue.json": CATALOGUE / "components/reviews/parallel-import-2026-10-17/wall-circle/approved-working-catalogue.json",
    "task-checkpoint.json": A / "task-checkpoint.json",
}.items():
    raw = source.read_bytes()
    dest = SNAP / name
    assert not dest.exists(), dest
    dest.write_bytes(raw)
    assert source.read_bytes() == raw, ("Source changed during snapshot", source)
    sources[name] = {
        "source": str(source), "snapshot": str(dest),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
assert sources["canonical-products.json"]["sha256"] == "c0e88303da05f6f17b2766cf1b08f8c3340f596fc5986ff43e884bc8fd8f3428"
save("input-manifest.json", {"sources": sources, "created_utc": datetime.now(timezone.utc).isoformat()})

graph = read(SNAP / "canonical-products.json")
data = read(SNAP / "refresh-data.json")
model = read(SNAP / "component_register.json")
progress = read(SNAP / "specification_review_progress.json")
wall = read(SNAP / "wall-circle-approved-working-catalogue.json")
products = graph["products"]
by_id = {p["product_id"]: p for p in products}
scope_map = {r["source_scope"]: r for r in graph["scope_reconciliation"]}
by_component = {r["component_id"]: r for r in model["components"]}
all_spec_rows = data["specifications"]
checks = {}


def check(label, value):
    checks[label] = bool(value)


check("173 distinct product IDs and canonical keys", len(products) == len(by_id) == len({p["canonical_key"] for p in products}) == 173)
check("278 source review scopes represented once", len(scope_map) == len(graph["scope_reconciliation"]) == len(data["reviews"]) == 278)
check("Every product keeps six labelled working fields", all(len(p["specifications"]) == 6 and p["six_working_fields_recorded"] for p in products))
check("Products do not claim physical verification or publication", all(p["physical_specifications_verified"] is False and p["platform_publication_performed"] is False for p in products))
product_source_scopes = [s for p in products for s in p["source_scopes"]]
check("174 accepted scopes have exactly one product owner", len(product_source_scopes) == len(set(product_source_scopes)) == 174)
check("Every accepted source scope maps to its product", all(scope_map[s]["targets"] == [p["product_id"]] for p in products for s in p["source_scopes"]))
check("Only documented Leaf Form White orientation scopes share a product", [p["source_scopes"] for p in products if len(p["source_scopes"]) > 1] == [["BC-LEAF-FORM|LEAF-FORM-LF1-WHITE", "BC-LEAF-FORM|LEAF-FORM-LF2-WHITE"]])

assertion_indices = []
for product in products:
    for field, item in product["specifications"].items():
        for assertion in item["assertions"]:
            idx = assertion["source_row_index"]
            original = all_spec_rows[idx]
            assertion_indices.append(idx)
            check("Source assertion preserved " + str(idx), (
                assertion["source_scope"] == "|".join(original[:2])
                and assertion["source_title"] == original[2] and field == original[3]
                and assertion["display"] == original[4] and assertion["state"] == original[5]
                and assertion["basis"] == original[6] and assertion["image_url"] == original[7]
                and assertion["folder_url"] == original[8] and assertion["file_id"] == original[9]
                and assertion["folder_id"] == original[10] and assertion["proposal_id"] == original[11]
            ))
for assertion in graph["source_only_assertions_not_applied_to_products"]:
    idx = assertion["source_row_index"]
    assertion_indices.append(idx)
    check("Unaccepted source assertion remains separate " + str(idx), assertion["original_row"] == all_spec_rows[idx])
check("All1668 source field assertions retained exactly once", sorted(assertion_indices) == list(range(1668)))

aliases = {a["source_scope"]: a for a in graph["historical_alias_reconciliation"]}
for key, alias in progress["canonical_variant_aliases"].items():
    target_key = alias["canonical_component_id"] + "|" + alias["canonical_variant_id"]
    expected = next(p["product_id"] for p in products if target_key in p["source_scopes"])
    check("Exact approved finish alias " + key, aliases[key]["targets"] == [expected] and aliases[key]["specification_assertions_inherited"] is False)
check("Concave is a historical design alias only", aliases["BC-CONCAVE|BASE"]["specification_assertions_inherited"] is False and not any(p["canonical_design_id"] == "BC-CONCAVE" for p in products))
check("Selected DR3 photograph alias does not merge historical maker design", scope_map["BC-DR-WAVE3|DR3-WHITE"]["disposition"] == "SELECTED_IMAGE_REFERENCE_ALIAS" and scope_map["BC-DR-WAVE3|BASE"]["disposition"] == "SOURCE_CANDIDATE")
check("Group references do not become additional products", all(r["counted_as_working_product"] is False for r in graph["references"]))
check("Unresolved source candidates are not counted as products", all(r["counted_as_working_product"] is False for r in graph["source_candidates"] + graph["additional_source_candidates"]))
check("No unexplained duplicate current product names", all(n == 1 for n in Counter(p["name"].casefold().strip() for p in products).values()))

# Explicit family relationships are useful to the final register even though
# the A artifact stores most family context in source coverage tables.
family_edges = []
for product in products:
    cid = product["canonical_design_id"]
    original_components = []
    if cid in by_component:
        original_components = [by_component[cid]]
    else:
        parents = {
            row["source_scope"].split("|", 1)[0]
            for row in graph["scope_reconciliation"]
            if product["product_id"] in row["targets"]
            and row["disposition"] == "HISTORICAL_DESIGN_OR_SIZE_HEADER"
        }
        original_components = [by_component[p] for p in sorted(parents) if p in by_component]
    families = sorted({c["family"] for c in original_components if c.get("family")})
    basis = "Source component register family, routed through recorded scope aliases when required"
    if not families:
        path = unquote(urlsplit(product["folder_url"]).path)
        marker = "/BOLDSTONE MASTER/Products/01 Wall Sculptures/"
        assert marker in path, product["product_id"]
        families = [path.split(marker, 1)[1].split("/", 1)[0]]
        basis = "Existing containing-folder family label; classification only, not a new identity assertion"
    assert len(families) == 1, (product["product_id"], families)
    original_family = families[0]
    alias = progress["catalogue_family_aliases"].get(original_family)
    family = alias["canonical_family"] if alias else original_family
    family_edges.append({
        "product_id": product["product_id"], "product_name": product["name"],
        "canonical_design_id": cid, "family": family, "source_family": original_family,
        "source_component_ids": [c["component_id"] for c in original_components],
        "source_group_refs": sorted({g for c in original_components for g in c.get("group_refs", [])}),
        "relationship": "BELONGS_TO_CATALOGUE_FAMILY",
        "basis": basis, "creates_extra_product": False,
    })
check("Every working product has one supported family relation", len(family_edges) == 173 and len({e["product_id"] for e in family_edges}) == 173)

arrangement_edges = []
for ref in graph["references"]:
    for pid in ref.get("member_product_ids", []):
        check("Arrangement target exists " + ref["reference_id"] + ":" + pid, pid in by_id)
        arrangement_edges.append({
            "reference_id": ref["reference_id"], "arrangement_name": ref["name"],
            "product_id": pid, "product_name": by_id[pid]["name"],
            "relationship": "OWNER_CONFIRMED_COMBINED_MEMBERSHIP",
            "source": "specification_review_progress.arrangement_component_bindings.MLAVA-1-PLUS-2-WHITE",
            "source_reference_ids": ref["source_reference_ids"],
            "reference_image_url": ref["image_url"], "reference_folder_url": ref["folder_url"],
            "creates_extra_product": False, "confirms_same_physical_cast": False,
            "position_scope": "Positions derived from prior image review; owner confirmed named membership only",
        })
check("Moonshell Lava combined reference links existing1and2 only", len(arrangement_edges) == 2 and {by_id[e["product_id"]]["canonical_design_id"] for e in arrangement_edges} == {"BC-MLAVA-1", "BC-MLAVA-2"})
check("21 canonical group references preserve22 source groups", graph["summary"]["group_source_records"] == 22 and graph["summary"]["canonical_group_references"] == 21)
check("G050 legacy reference consolidates to one collection", graph["reference_aliases"]["REF-BC-MIX-SPIRALS"]["target_reference_id"] == "REF-G050")

family_receipt = save("FAMILY_AND_ARRANGEMENT_EDGES.json", {
    "source_graph_sha256": sources["canonical-products.json"]["sha256"],
    "product_family_edges": family_edges, "explicit_arrangement_member_edges": arrangement_edges,
    "family_count": len({e["family"] for e in family_edges}),
    "family_aliases": progress["catalogue_family_aliases"],
    "other_group_references": graph["references"],
    "other_group_components_inferred": False,
    "source_offer_and_BOM_relationships_retained_in": str(A / "canonical-products.json"),
    "source_offer_count": len(graph["source_offer_coverage"]),
    "source_configuration_count": len(graph["source_configuration_coverage"]),
})

wall_records = wall["visual_working_records"]
wall_receipt = save("WALL_CIRCLE_SUPPLEMENTAL_EVIDENCE.json", {
    "source": sources["wall-circle-approved-working-catalogue.json"],
    "finding": "Seven owner-kept visual working entries exist outside the flattened278 review table and A173 product view. Preserve them explicitly in the final register; the exact native pattern/size/lighting crosswalk remains unresolved.",
    "family_approval": wall["family_approval"],
    "visual_working_records": wall_records,
    "native_option_rows": len(wall["native_option_register"]),
    "native_named_pattern_candidates": len(wall["native_pattern_candidates"]),
    "native_pattern_alias_mapping_status": wall["native_pattern_alias_mapping_status"],
    "recommendation": "Retain the seven approved visual records separately from the native option-family header. Reuse WC-01 owner-stated specifications at their exact scope. Retain other records' source/estimate labels and apply existing standing policies only through the sole canonical writer. Do not count144 native options as144 verified individual designs.",
    "new_working_acceptances_by_this_audit": 0,
    "shared_model_changes": 0,
})
check("Supplemental Wall Circle source has seven approved working names", len(wall_records) == 7 and all(r["working_entry_kept"] for r in wall_records))
check("Wall Circle native option rows remain144 with unresolved alias mapping", len(wall["native_option_register"]) == 144 and wall["native_pattern_alias_mapping_status"])

result = {
    "schema": "boldstone.product-register-independent-graph-audit.v1",
    "checked_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS_BASELINE_GRAPH_WITH_DOCUMENTED_SUPPLEMENTAL_GAP" if all(checks.values()) else "FAIL",
    "checks_passed": sum(checks.values()), "checks_failed": sum(not x for x in checks.values()),
    "failed_checks": [k for k, v in checks.items() if not v],
    "checks": {k: "PASS" if v else "FAIL" for k, v in checks.items()},
    "baseline_counts": graph["summary"],
    "family_and_arrangement_evidence": family_receipt,
    "wall_circle_evidence": wall_receipt,
    "findings_for_final_register": [
        "The A173 artifact is a valid accepted-working-scope baseline, not a complete whole-library individual-product count.",
        "Add explicit family edges and retain the existing owner-confirmed Moonshell Lava1+2 arrangement membership.",
        "Seven already-kept Wall Circle visual records require explicit representation beyond the unresolved native option family.",
        "Moon Crater Phase4 native path links require the active Dropbox writer's final move/deletion receipts before current-link publication.",
    ],
    "shared_master_writes": 0, "remote_reads": 0, "remote_writes": 0,
}
receipt = save("BASELINE_GRAPH_AUDIT.json", result)
print(json.dumps({**receipt, "status": result["status"], "passed": result["checks_passed"], "failed": result["failed_checks"], "families": len({e["family"] for e in family_edges}), "wall_circle_records": len(wall_records)}))
