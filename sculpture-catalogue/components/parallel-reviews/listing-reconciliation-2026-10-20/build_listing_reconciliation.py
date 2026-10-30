"""Read-only native record reconciliation. Writes only this review packet.

Native record identity, catalogue design identity, configuration and sale unit
are deliberately independent assertions. The shared master is never written.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import html
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
MASTER_HASH = "30ff291d6b6fe0aad3a2bc39e121de4ef838c09afceb5f7ab11c78ea7fa71e2c"
WORKBOOK_HASH = "5df82453966899176ae18ce376027623cc34b4a3555354f9ac52a1eb96db0e18"
SINGLE = "SOURCE_SUPPORTED_STANDALONE_OPTION_CANDIDATE"
CONFLICTS = {"SINGLE_SOURCE_OFFER_CURRENT_VERSION_CONFLICT", "BOUND_PHOTOGRAPHED_DESIGN_CURRENT_CONFIGURATION_CONFLICT"}
SET = "SOURCE_SET_MEMBER_SCOPE_ASSOCIATION"
UNRESOLVED = "SINGLE_SOURCE_OFFER_SCOPE_CANDIDATE_UNRESOLVED"
WALL = "FAMILY_OFFER_ONLY_EXACT_VISUAL_NATIVE_PATTERN_ALIAS_UNRESOLVED"
GALLERY = {"GALLERY_MEMBER_ASSOCIATION_SALE_UNIT_UNRESOLVED", "HISTORICAL_DRAFT_CONTEXT_MEMBER_ASSOCIATION"}
FAMILY = {"SIBLING_OR_FAMILY_OPTION_ASSOCIATION_ONLY", "CONFLICTING_TITLE_OR_INTENDED_BOM_ONLY_NOT_THE_BOUND_HERO_DESIGN"}
STATUS = {
    "matched": "INDIVIDUAL_SOURCE_RECORD_LINKED",
    "conflict": "EXISTING_INDIVIDUAL_DESIGN_WITH_CONFIGURATION_CONFLICT",
    "unresolved": "INDIVIDUAL_LISTING_CANDIDATE_SCOPE_UNRESOLVED",
    "set": "SET_OR_ARRANGEMENT_ASSOCIATION_ONLY",
    "wall": "WALL_CIRCLE_FAMILY_ONLY_EXACT_VARIANT_UNRESOLVED",
    "gallery": "GALLERY_OR_DRAFT_CONTEXT_SALE_UNIT_UNRESOLVED",
    "family": "RELATED_FAMILY_ONLY_NO_INDIVIDUAL_MATCH",
    "none": "NO_SUPPORTED_INDIVIDUAL_ASSOCIATION_IN_CHECKED_SOURCES",
}
NOW = dt.datetime.now(dt.timezone.utc).isoformat()


def read(path):
    return json.loads((HERE / path).read_text())


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def ref(name, pointer=""):
    p = HERE / name
    return {"path": str(p), "sha256": sha(p), "json_pointer": pointer}


def textnorm(value):
    value = html.unescape(re.sub(r"<[^>]*>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()


def counter(rows, field):
    return dict(sorted(collections.Counter(x[field] for x in rows).items()))


def dimension_grade(edge):
    state = edge["compatibility"]["size"]["state"]
    if state in {"KNOWN_SOURCE_VS_CURRENT_WORKING_VERSION_CONFLICT", "SOURCE_FACE_NUMBERS_DIFFER_FROM_CURRENT_WORKING_CLAIM", "FACE_COMPATIBLE_DEPTH_CLAIMS_DIFFER"}:
        return "RECORDED_DIMENSION_OR_VERSION_CONFLICT"
    if state == "NUMERIC_DIMENSION_CLAIMS_COMPATIBLE_UNMEASURED":
        return "SOURCE_NUMERIC_CLAIMS_COMPATIBLE_NOT_PHYSICALLY_VERIFIED"
    return "SOURCE_SIZE_APPLICABILITY_PARTLY_OR_WHOLLY_UNRESOLVED"


def ss_variant(v):
    return {
        "native_product_id": v["native_product_id"],
        "native_variant_id": v["native_variant_id"],
        "sku_raw": v["sku"],
        "option_attributes": v["option_attributes"],
        "native_price": v["price"],
        "native_stock_setting": v["stock_setting"],
        "raw_dimensions_and_weight": v["raw_dimensions_and_weight"],
        "dimensions_weight_units": v["dimensions_weight_units"],
        "source_locator": v["source_locator"],
        "price_scope": "Whole offered unit; no member-price allocation",
    }


def sh_variant(v):
    return {k: v[k] for k in [
        "variant_key", "product_key", "handle", "numeric_product_id", "numeric_variant_id", "id_state", "sku_raw", "option_tuple",
        "price_raw", "currency", "grams_raw", "exported_weight_unit_raw", "inventory_quantity", "inventory_quantity_state",
        "product_status_raw", "published_raw", "status_scope", "source_row", "source_row_role", "product_url", "variant_url",
    ]}


master_path = HERE / "inputs/master-register.json"
workbook_path = HERE / "inputs/current-master.xlsx"
assert sha(master_path) == MASTER_HASH
assert sha(workbook_path) == WORKBOOK_HASH
master = read("inputs/master-register.json")
mapping = read("worker-03/source_mapping_evidence.json")
ss = read("worker-01/SQUARESPACE_SOURCE_INVENTORY.json")
sh_products = read("worker-02/shopify_products.json")
sh_variants = read("worker-02/shopify_variants.json")
sh_inventory = read("worker-02/shopify_inventory.json")
ss_by_id = {p["native_product_id"]: p for p in ss["products"]}
sh_by_handle = {p["handle"]: p for p in sh_products}
sh_by_product = collections.defaultdict(list)
sh_by_sku = collections.defaultdict(list)
for variant in sh_variants:
    sh_by_product[variant["handle"]].append(variant)
    if variant["sku_raw"]:
        sh_by_sku[variant["sku_raw"]].append(variant)
offer_source = {r["offer_ref"]: r["source_offer"] for r in master["source_offer_edges"]}
edge_groups = collections.defaultdict(list)
for edge in mapping["candidate_edges"]:
    edge_groups[edge["product_id"]].append(edge)

links = []
for idx, offer in enumerate(master["source_platform_offer_coverage"]):
    oid = offer["offer_ref"]
    source = offer_source[oid]
    p = ss_by_id.get(offer["squarespace_id"])
    ss_record = {"record_present": False, "presence_state": "NO_RECORDED_SQUARESPACE_SOURCE_ID", "variants": [], "individual_variant_assignment": False}
    if p:
        prior_description = next((x["description_text"] for x in p["observations"] if x["source_kind"] == "CACHED_WALL_NATIVE_EXTRACT"), None)
        ss_record = {
            "record_present": True,
            "identifier_match_grade": "EXACT_RECORDED_NATIVE_PRODUCT_ID",
            "native_product_id": p["native_product_id"], "title": p["title"], "url": p["url"],
            "presence_state": p["inventory_state"], "fresh_public_product_observed": p["fresh_public_product_observed"],
            "public_collection_observed": p["public_collection_observed"],
            "source_locator": p["preferred_source_locator"],
            "public_detail_checks": p.get("public_detail_checks", []),
            "variants": [ss_variant(v) for v in p["variants"]],
            "exact_source_sku_variant_ids": [v["native_variant_id"] for v in p["variants"] if v["sku"] == offer["source_sku"] and offer["source_sku"]],
            "all_variant_ids_are_not_individual_option_assignments": True,
            "native_sellable_unit": p["native_sellable_unit"],
            "description_text": p["description_text"],
            "description_equals_retained_wall_extract_after_whitespace_normalization": None if prior_description is None else textnorm(prior_description) == textnorm(p["description_text"]),
            "native_inventory_evidence": ref("worker-01/SQUARESPACE_SOURCE_INVENTORY.json", f"/products/{ss['products'].index(p)}"),
            "current_authenticated_admin_inventory_verified": False,
        }
    h = offer["shopify_handle"]
    hp = sh_by_handle.get(h)
    sh_record = {"record_present": False, "presence_state": "NO_RECORDED_HANDLE_IN_SELECTED_SHOPIFY_EXPORT", "variants": [],
                 "unrecorded_handle_same_sku_candidates": [sh_variant(v) for v in sh_by_sku.get(offer["source_sku"], [])] if offer["source_sku"] else [],
                 "not_found_in_export_is_not_live_absence": True}
    if hp:
        rows = sh_by_product[h]
        sh_record = {
            "record_present": True, "identifier_match_grade": "EXACT_RECORDED_HANDLE_IN_NATIVE_CSV",
            "presence_state": "HISTORICAL_NATIVE_EXPORT_PRESENT_CURRENT_STATE_UNVERIFIED",
            "product_key": hp["product_key"], "handle": h, "numeric_product_id": None,
            "numeric_ids_state": "NOT_EXPORTED_IN_THIS_SCHEMA", "title": hp["title"], "product_url": None,
            "product_url_state": hp["product_url_state"], "source_header_row": hp["source_header_row"],
            "status_raw": hp["status_raw"], "published_raw": hp["published_raw"], "status_scope": hp["status_scope"],
            "variants": [sh_variant(v) for v in rows],
            "exact_source_sku_variant_keys": [v["variant_key"] for v in rows if v["sku_raw"] == offer["source_sku"] and offer["source_sku"]],
            "blank_source_sku_is_not_an_identifier_match": True,
            "native_description_html": hp["body_html"],
            "native_description_text": textnorm(hp["body_html"]),
            "description_equals_retained_offer_after_html_whitespace_normalization": textnorm(hp["body_html"]) == textnorm(source["native_description"]),
            "cross_platform_description_or_size_not_implicitly_inherited": True,
            "source_dates": hp["source_dates"],
            "product_evidence": ref("worker-02/shopify_products.json", f"/{sh_products.index(hp)}"),
            "current_authenticated_admin_inventory_verified": False,
        }
    option_edges = [e for e in mapping["candidate_edges"] if e["offer_ref"] == oid]
    links.append({
        "offer_ref": oid, "source_title": offer["source_title"], "source_sku": offer["source_sku"],
        "retained_source_sale_scope": offer["source_sale_scope"], "native_parts_raw": offer["native_parts"],
        "original_bom_rows": offer["bom_rows"],
        "source_image_file_id": offer["source_image_file_id"], "source_image_folder_id": offer["source_image_folder_id"],
        "Squarespace": ss_record, "Shopify": sh_record,
        "linked_option_ids_by_relationship": {r: sorted({e["product_id"] for e in option_edges if e["relationship"] == r}) for r in sorted({e["relationship"] for e in option_edges})},
        "source_evidence": ref("inputs/master-register.json", f"/source_platform_offer_coverage/{idx}"),
        "count_increment": 0,
    })
links_by_offer = {x["offer_ref"]: x for x in links}
write("NATIVE_SOURCE_LINKS.json", {"schema": "boldstone.listing-native-source-links.v1", "prepared_utc": NOW, "source_offer_count": len(links), "offers": links,
    "scope": "Exact native identifier lookup for retained offers; no native variant is assigned to a catalogue option merely by this table", "master_sha256": MASTER_HASH})

evidence = []
for edge_index, edge in enumerate(mapping["candidate_edges"]):
    oid = edge["offer_ref"]
    link = links_by_offer[oid]
    platform_evidence = {}
    for platform in ["Squarespace", "Shopify"]:
        native = link[platform]
        exact_variant_refs = []
        if native["record_present"] and len(native["variants"]) == 1 and link["source_sku"] and native["variants"][0]["sku_raw"] == link["source_sku"]:
            exact_variant_refs = native["variants"]
        relevant_single = edge["relationship"] == SINGLE or edge["relationship"] in CONFLICTS
        design_supported = edge["compatibility"]["design"]["state"] in {"BOUND_RETAINED_SOURCE_HERO_DESIGN", "EXPLICIT_SCOPED_DESIGN_ASSOCIATION"}
        finish_supported = edge["compatibility"]["finish"]["state"] == "SOURCE_REVIEW_FINISH_SCOPE_SUPPORTED_CHEMISTRY_NOT_CERTIFIED"
        native_set_conflict = platform == "Squarespace" and native["record_present"] and native["native_sellable_unit"]["classification"] == "EXPLICIT_MULTIPART_DESCRIPTION"
        supported_link = relevant_single and design_supported and finish_supported and len(exact_variant_refs) == 1 and not native_set_conflict
        if supported_link:
            grade = "SOURCE_SUPPORTED_DESIGN_FINISH_TO_EXACT_NATIVE_SOURCE_VARIANT"
        elif native["record_present"]:
            grade = "PROVISIONAL_RELATED_NATIVE_RECORD_NOT_AN_INDIVIDUAL_VARIANT_MATCH"
        else:
            grade = "UNVERIFIED_NO_RECORDED_NATIVE_PLATFORM_LINK_IN_CHECKED_SOURCES"
        platform_evidence[platform] = {
            "native_record_present": native["record_present"], "presence_state": native["presence_state"],
            "native_identifier_match_grade": native.get("identifier_match_grade", "NO_IDENTIFIER_LINK"),
            "catalogue_to_native_match_grade": grade,
            "exact_native_variant_for_recorded_source_sku": exact_variant_refs,
            "individual_design_variant_link_supported": supported_link,
            "individual_option_variant_keys": [v.get("native_variant_id", v.get("variant_key")) for v in exact_variant_refs] if supported_link else [],
            "individual_skus": [v["sku_raw"] for v in exact_variant_refs] if supported_link else [],
            "native_record_variant_count": len(native["variants"]),
            "family_set_gallery_variant_is_not_individual_variant": not supported_link,
            "native_source_link_evidence": {"path": str(HERE / "NATIVE_SOURCE_LINKS.json"), "sha256": sha(HERE / "NATIVE_SOURCE_LINKS.json"), "json_pointer": f"/offers/{list(links_by_offer).index(oid)}/{platform}"},
            "description_scope": "FRESH_OR_RETAINED_NATIVE_SQUARESPACE_DESCRIPTION" if platform == "Squarespace" else "SHOPIFY_EXPORT_NATIVE_BODY; NO_SQUARESPACE_SPECIFICATION_TRANSFER",
            "description_equals_retained_source": native.get("description_equals_retained_wall_extract_after_whitespace_normalization") if platform == "Squarespace" else native.get("description_equals_retained_offer_after_html_whitespace_normalization"),
            "exact_current_physical_configuration_certified": False,
            "exact_current_option_configuration_match_verified": False,
        }
    evidence.append({
        "edge_id": edge["edge_id"], "product_id": edge["product_id"], "canonical_key": edge["canonical_key"], "offer_ref": oid,
        "relationship": edge["relationship"], "join_basis": edge["join_basis"],
        "compatibility": edge["compatibility"], "dimension_grade": dimension_grade(edge),
        "media_evidence": edge["media_evidence"], "special_join_limits": edge["special_join_limits"],
        "source_match_flags_retained": edge["source_match_flags_retained"], "source_cautions_retained": edge["source_cautions_retained"],
        "platform_evidence": platform_evidence,
        "evidence_ref": ref("worker-03/source_mapping_evidence.json", f"/candidate_edges/{edge_index}"),
        "exact_current_configuration_certified": False, "title_similarity_used": False,
    })
write("MATCH_EVIDENCE.json", {"schema": "boldstone.listing-scoped-option-native-matches.v1", "prepared_utc": NOW, "edges": evidence,
    "source_record_identifier_match_is_not_physical_configuration_certification": True, "master_sha256": MASTER_HASH})
evidence_by_option = collections.defaultdict(list)
for e in evidence:
    evidence_by_option[e["product_id"]].append(e)


def summarize_edges(edges, platform=None):
    if platform:
        edges = [e for e in edges if e["platform_evidence"][platform]["native_record_present"]]
    single = [e for e in edges if e["relationship"] == SINGLE and any(v["individual_design_variant_link_supported"] for k, v in e["platform_evidence"].items() if platform is None or k == platform)]
    conflicts = [e for e in edges if e["relationship"] in CONFLICTS and any(v["individual_design_variant_link_supported"] for k, v in e["platform_evidence"].items() if platform is None or k == platform)]
    # A compatible listing takes precedence, but every conflicting overlap stays
    # attached as an issue and is never silently discarded.
    if single:
        return STATUS["matched"], single
    if conflicts:
        return STATUS["conflict"], conflicts
    if any(e["relationship"] == UNRESOLVED for e in edges):
        return STATUS["unresolved"], [e for e in edges if e["relationship"] == UNRESOLVED]
    if any(e["relationship"] == SET for e in edges):
        return STATUS["set"], [e for e in edges if e["relationship"] == SET]
    if any(e["relationship"] == WALL for e in edges):
        return STATUS["wall"], [e for e in edges if e["relationship"] == WALL]
    if any(e["relationship"] in GALLERY for e in edges):
        return STATUS["gallery"], [e for e in edges if e["relationship"] in GALLERY]
    if edges:
        return STATUS["family"], edges
    return STATUS["none"], []


def action(status):
    return {
        STATUS["matched"]: "Retain the supported native record linkage. Preserve configuration qualifiers; reconcile any additional overlapping offers or SKU collisions before platform edits.",
        STATUS["conflict"]: "Correct or version the existing design listing using accepted working details. Resolve conflicting title/size/finish before claiming an exact current configuration match; do not create a duplicate merely because specifications differ.",
        STATUS["unresolved"]: "Resolve the exact design/finish/configuration against the native listing media and source evidence before binding its variant or creating another listing.",
        STATUS["set"]: "Keep the set or arrangement offer separate. Locate or prepare a standalone component offer and its own variant/SKU; never reuse the set SKU or allocate set price/weight.",
        STATUS["wall"]: "Confirm visual pattern aliases and applicable diameter/lighting choices against the native144 grid before assigning exact variant/SKU. Do not add seven fictitious native variants.",
        STATUS["gallery"]: "Establish which component and quantity the offer sells. A gallery image or historical draft is insufficient evidence of an individual listing.",
        STATUS["family"]: "Find the exact finish/size/build offer within current platform admin or prepare a distinct missing option after checking drafts. Related family records cannot supply an individual variant/SKU.",
        STATUS["none"]: "Check current platform admin/drafts for an individual offer; if absent, prepare it from this catalogue option with a distinct platform variant/SKU. Snapshot non-match is not global live absence.",
    }[status]


options = []
for idx, option in enumerate(master["options"]):
    edges = evidence_by_option[option["product_id"]]
    status, chosen = summarize_edges(edges)
    platforms = {}
    for platform in ["Squarespace", "Shopify"]:
        pst, selected = summarize_edges(edges, platform)
        matched = [e for e in edges if e["platform_evidence"][platform]["individual_design_variant_link_supported"]]
        variants = []
        for e in matched:
            variants += [{"offer_ref": e["offer_ref"], "relationship": e["relationship"], "dimension_grade": e["dimension_grade"],
                          "native_variant": v, "presence_state": e["platform_evidence"][platform]["presence_state"],
                          "exact_current_option_configuration_match_verified": False,
                          "match_scope": "SOURCE_SUPPORTED_DESIGN_FINISH; EXACT_NATIVE_IDENTIFIER; CONFIGURATION_QUALIFIERS_RETAINED"}
                         for v in e["platform_evidence"][platform]["exact_native_variant_for_recorded_source_sku"]]
        platforms[platform] = {
            "disposition": pst, "selected_evidence_edge_ids": [e["edge_id"] for e in selected],
            "supported_individual_native_variants": variants,
            "related_offer_refs": sorted({e["offer_ref"] for e in edges if e["platform_evidence"][platform]["native_record_present"]}),
            "individual_native_variant_assignment_count": len(variants),
            "native_numeric_ids_missing": platform == "Shopify",
            "current_authenticated_admin_inventory_verified": False,
            "exact_current_option_configuration_match_verified": False,
            "source_supported_individual_design_record_present": bool(variants),
            "source_configuration_coverage": "NO_KNOWN_SOURCE_CONFLICT_FULL_CONFIGURATION_NOT_VERIFIED" if pst == STATUS["matched"] else "EXISTING_DESIGN_CONFIGURATION_CONFLICT" if pst == STATUS["conflict"] else "EXACT_INDIVIDUAL_CONFIGURATION_UNRESOLVED",
            "absence_scope": "Checked public Squarespace and retained sources only; hidden/draft account records not assessed" if platform == "Squarespace" else "Selected historical native Shopify export only; current live/draft inventory not assessed",
            "next_action": action(pst),
        }
    source_association = mapping["option_associations"][option["product_id"]]
    has_link = status in {STATUS["matched"], STATUS["conflict"]}
    options.append({
        "product_id": option["product_id"], "canonical_key": option["canonical_key"], "name": option["name"],
        "canonical_component_id": option["canonical_component_id"], "family": option["family"],
        "source_scopes": option["source_scopes"], "sale_unit": option["sale_unit"],
        "primary_image_file_id": option.get("file_id"), "primary_folder_id": option.get("folder_id"),
        "primary_image_url": option.get("image_url"), "primary_folder_url": option.get("folder_url"),
        "context_image_file_id": option.get("context_file_id"), "context_folder_id": option.get("context_folder_id"),
        "photo_coverage": option.get("photo_coverage", {}),
        "working_specifications": {k: v["display"] for k, v in option["master_fields"].items()},
        "working_specification_status": option["working_specification_status"],
        "overall_disposition": status, "selected_evidence_edge_ids": [e["edge_id"] for e in chosen],
        "individual_source_record_supported": has_link,
        "match_grade": "SOURCE_SUPPORTED_INDIVIDUAL_IDENTITY_WITH_CONFIGURATION_QUALIFICATIONS" if has_link else "PROVISIONAL_OR_UNVERIFIED_INDIVIDUAL_PLATFORM_MATCH",
        "exact_current_configuration_certified": False,
        "exact_current_option_configuration_match_verified": False,
        "source_configuration_coverage": "NO_KNOWN_SOURCE_CONFLICT_FULL_CONFIGURATION_NOT_VERIFIED" if status == STATUS["matched"] else "EXISTING_DESIGN_CONFIGURATION_CONFLICT" if status == STATUS["conflict"] else "EXACT_INDIVIDUAL_CONFIGURATION_UNRESOLVED",
        "platforms": platforms, "all_evidence_edge_ids": [e["edge_id"] for e in edges],
        "set_member_offer_refs": sorted({e["offer_ref"] for e in edges if e["relationship"] == SET}),
        "conflicting_individual_offer_refs": sorted({e["offer_ref"] for e in edges if e["relationship"] in CONFLICTS}),
        "unsafe_exact_configuration_reasons": source_association["unsafe_exact_configuration_reasons"],
        "non_offer_relations": source_association["non_offer_relations"],
        "next_action": action(status), "catalogue_count_increment": 0,
        "evidence_ref": ref("inputs/master-register.json", f"/options/{idx}"),
    })

counts = {
    "catalogue_options": len(options), "source_offers": len(links), "scoped_candidate_edges": len(evidence),
    "overall_option_dispositions": counter(options, "overall_disposition"),
    "Squarespace_option_dispositions": dict(sorted(collections.Counter(o["platforms"]["Squarespace"]["disposition"] for o in options).items())),
    "Shopify_option_dispositions": dict(sorted(collections.Counter(o["platforms"]["Shopify"]["disposition"] for o in options).items())),
    "platform_option_cells": len(options) * 2,
    "source_supported_individual_design_options": sum(o["individual_source_record_supported"] for o in options),
    "nonconflicting_source_supported_individual_record_links": sum(o["overall_disposition"] == STATUS["matched"] for o in options),
    "existing_individual_design_records_with_configuration_conflict": sum(o["overall_disposition"] == STATUS["conflict"] for o in options),
    "options_without_supported_individual_native_record": sum(not o["individual_source_record_supported"] for o in options),
    "options_without_nonconflicting_supported_individual_native_record": sum(o["overall_disposition"] != STATUS["matched"] for o in options),
    "exact_current_option_configuration_matches_verified": 0,
    "authenticated_live_exact_option_configuration_verifications": 0,
    "current_exact_physical_configurations_certified": 0,
    "fresh_public_squarespace_source_products": ss["counts"]["fresh_public_collection_product_ids"],
    "fresh_public_squarespace_source_variants": ss["counts"]["fresh_public_collection_variant_rows"],
    "Squarespace_union_product_ids": ss["counts"]["all_observed_product_ids_union"],
    "Squarespace_preferred_variant_rows_including_source_only": ss["counts"]["normalized_preferred_variant_rows_including_source_only"],
    "Shopify_snapshot_products": len(sh_products), "Shopify_snapshot_variants": len(sh_variants),
    "shopify_live_products_verified": 0, "native_wall_circle_variants_retained_separately": len(master["wall_circle_native_options"]),
}

LIMITS = [
    "All184 catalogue options receive a disposition, not184 claims of existing native listings. No catalogue options are added or removed.",
    "Exact native source identifiers are distinguished from source-supported catalogue identity and from exact physical configuration; manufactured size/material/hardware remain qualified.",
    "Public Squarespace yielded203 products/370 variants after following the returned pagination to completion; advertised itemCount208 remains an unresolved discrepancy. Five union source-only records have404 at their checked exact URLs, not proof of account deletion or hidden/draft absence.",
    "Squarespace preferred source precedence: fresh exact product-detail JSON, fresh collection JSON, cached wall extract, saved native CSV. All historical observations remain retained in the normalized inventory.",
    "Shopify136 products/160 variants are a historical native export.256 media-only continuation rows are not variants. Numeric product/variant IDs, quantity, store domain and live/admin completeness are unavailable; handles, option tuples, raw SKUs and exact source rows are retained instead.",
    "A set SKU, pictured arrangement, family association or default title is not an individual component variant. Set prices, weights and total dimensions are never divided among components.",
    "Wall Circle144 native pattern/diameter/lighting variants remain a separate configuration layer; exact aliases for the seven visual records are unresolved.",
    "Same SKU across platforms can be an intentional mirror. Same SKU across distinct native variants within one platform is a collision requiring review, not automatic duplicate deletion.",
    "A native listing with a bound design but conflicting copy or dimensions is an existing correction/version candidate, not automatically a missing listing.",
]
write("LISTING_RECONCILIATION.json", {
    "schema": "boldstone.all184-listing-reconciliation.v1", "status": "PREPARED_READ_ONLY_LISTING_RECONCILIATION",
    "publication_state": "SEPARATE_COORDINATOR_PUBLICATION_RECEIPT_REQUIRED",
    "prepared_utc": NOW, "owner_instruction": read("OWNER_INSTRUCTION.json"),
    "input_master_sha256": MASTER_HASH, "input_workbook_sha256": WORKBOOK_HASH,
    "counts": counts, "options": options, "scope_and_limits": LIMITS,
    "native_source_links_file": str(HERE / "NATIVE_SOURCE_LINKS.json"), "match_evidence_file": str(HERE / "MATCH_EVIDENCE.json"),
    "remote_writes": 0, "shared_master_writes": 0, "dropbox_calls": 0,
})

issues = []
for o in options:
    if not o["individual_source_record_supported"]:
        issues.append({"issue_id": "INDIVIDUAL:" + o["product_id"], "issue_type": o["overall_disposition"], "product_ids": [o["product_id"]],
            "name": o["name"], "evidence_edge_ids": o["all_evidence_edge_ids"], "next_action": o["next_action"],
            "not_found_is_not_live_absence": True})
    for oid in o["conflicting_individual_offer_refs"]:
        issues.append({"issue_id": "CONFIG:" + o["product_id"] + ":" + oid, "issue_type": "EXISTING_INDIVIDUAL_DESIGN_CONFIGURATION_OR_COPY_CONFLICT", "product_ids": [o["product_id"]],
            "offer_refs": [oid], "name": o["name"], "evidence_edge_ids": [o["product_id"] + "::" + oid], "next_action": action(STATUS["conflict"])})
for collision in ss["duplicate_sku_candidates"]:
    issues.append({"issue_id": "SS-SKU:EBAY-188654649217", "issue_type": "CONFIRMED_NATIVE_SKU_COLLISION_DUPLICATE_LISTING_CANDIDATE", "native_collision_evidence": collision,
        "offer_refs": ["O051", "O067"], "product_ids": [o["product_id"] for o in options if o["canonical_key"] == "BC-DR-WAVE1|DR-WAVES-RUST"],
        "next_action": "Compare the two native product/variant records and intended size/offer history. Select the canonical listing or retain genuinely distinct versions with distinct SKUs. No automatic deletion or merge.",
        "duplicate_physical_stock_or_cast_claimed": False})
for o in options:
    current_records = [v for v in o["platforms"]["Squarespace"]["supported_individual_native_variants"] if v["presence_state"] == "FRESH_PUBLIC_OBSERVED"]
    if len({v["native_variant"]["native_product_id"] for v in current_records}) > 1:
        issues.append({"issue_id": "PUBLIC-OVERLAP:" + o["product_id"], "issue_type": "MULTIPLE_PUBLIC_INDIVIDUAL_RECORDS_FOR_ONE_CATALOGUE_DESIGN_OPTION",
            "product_ids": [o["product_id"]], "name": o["name"], "native_records": current_records,
            "identity_basis": "Source-supported design/finish scope; specification or offer-version differences remain separate",
            "next_action": "Compare intended size/configuration and listing history. Consolidate only genuinely duplicate offers; retain distinct intended versions with distinct identifiers. No platform deletion or merge performed.",
            "automatically_equivalent_physical_items": False})
for group in [(["O002", "O039"], "Dune Ripple Spiral — Gold"), (["O003", "O064"], "Moon Crater Phase4 — Silver and Bronze")]:
    issues.append({"issue_id": "HISTORY:" + ":".join(group[0]), "issue_type": "HISTORICAL_OVERLAPPING_DESIGN_OFFERS_NOT_TWO_CONFIRMED_CURRENT_PUBLIC_LISTINGS", "offer_refs": group[0], "name": group[1],
        "current_public_states": {oid: links_by_offer[oid]["Squarespace"]["presence_state"] for oid in group[0]},
        "next_action": "Preserve historical aliases; reconcile intended versions. A checked404 does not establish deletion from native account."})
historical_skus = read("worker-02/shopify_historical_assertions.json")
for i, row in enumerate(historical_skus):
    if row["same_handle_sku_relation"] == "DIFFERENT_NONEMPTY_SKU_HISTORICAL_CANDIDATE_ONLY":
        issues.append({"issue_id": "SH-HISTORICAL-SKU:" + str(i), "issue_type": "HISTORICAL_SHOPIFY_SKU_VERSION_DIFFERENCE_NOT_AN_EXACT_ALIAS",
            "handle": row["handle"], "historical_sku_raw": row["sku_raw"], "selected_export_skus_raw": row["later_primary_skus_raw"],
            "historical_assertion_evidence": ref("worker-02/shopify_historical_assertions.json", f"/{i}"),
            "next_action": "Preserve the historical SKU and source row; do not silently treat a changed SKU as the same native variant. Current numeric variant lineage requires admin evidence."})
scope_audit = read("worker-01/UNLINKED_SCOPE_AUDIT.json")
for i in scope_audit["candidate_entry_indices"]:
    row = scope_audit["entries"][i]
    issues.append({"issue_id": "NATIVE-SCOPE:" + row["native_product_id"], "issue_type": "ADJACENT_NATIVE_SCULPTURAL_DECOR_SCOPE_REVIEW",
        "native_product_id": row["native_product_id"], "title": row["title"], "url": row["url"],
        "classification": row["classification"], "scope_evidence": ref("worker-01/UNLINKED_SCOPE_AUDIT.json", f"/entries/{i}"),
        "new_catalogue_option_created": False, "canonical_design_match_claimed": False,
        "next_action": "Review whether this functional/sculptural decor product belongs in a future catalogue scope. It has no evidenced exact link to one of the184 wall-sculpture options."})
write("LISTING_ISSUES.json", {"schema": "boldstone.listing-reconciliation-issues.v1", "prepared_utc": NOW, "issues": issues,
    "counts_by_type": counter(issues, "issue_type"), "global_access_and_completeness_limits": LIMITS,
    "platform_creates_updates_deletes_performed": 0, "shared_writes": 0})

set_rows = []
for link in links:
    member_ids = link["linked_option_ids_by_relationship"].get(SET, [])
    native_class = link["Squarespace"].get("native_sellable_unit", {}).get("classification")
    if member_ids or native_class == "EXPLICIT_MULTIPART_DESCRIPTION":
        set_rows.append({"offer_ref": link["offer_ref"], "source_title": link["source_title"], "source_sku": link["source_sku"],
            "native_squarespace_product_id": link["Squarespace"].get("native_product_id"), "native_shopify_handle": link["Shopify"].get("handle"),
            "native_description_sale_unit": link["Squarespace"].get("native_sellable_unit"),
            "member_option_ids": member_ids, "original_bom_rows": link["original_bom_rows"],
            "member_options_without_any_supported_standalone_source_record": [pid for pid in member_ids if not next(o for o in options if o["product_id"] == pid)["individual_source_record_supported"]],
            "set_sku_assigned_to_individual_members": False, "set_price_or_mass_allocated": False,
            "shopify_native_sale_scope_not_implicitly_inherited_from_squarespace": True})
write("SET_ONLY_AND_MULTIPART_OFFERS.json", {"schema": "boldstone.listing-set-and-arrangement-scope.v1", "prepared_utc": NOW, "offers": set_rows,
    "option_ids_with_only_set_or_arrangement_association": [o["product_id"] for o in options if o["overall_disposition"] == STATUS["set"]],
    "arrangement_description_is_not_automatically_an_explicit_fulfilment_quantity": True})

# CSVs are review/import intermediates. The coordinator alone authors the master
# workbook with the spreadsheet workflow; original native spreadsheets are read-only.
with (HERE / "OPTION_LISTING_REVIEW.csv").open("w", newline="") as f:
    columns = ["product_id", "canonical_key", "name", "overall_disposition", "Squarespace_disposition", "Squarespace_individual_product_ids", "Squarespace_individual_variant_ids", "Squarespace_individual_skus", "Shopify_disposition", "Shopify_individual_handles", "Shopify_individual_variant_keys", "Shopify_individual_skus", "set_member_offer_refs", "conflicting_offer_refs", "primary_image_file_id", "primary_folder_id", "next_action"]
    w = csv.DictWriter(f, columns); w.writeheader()
    for o in options:
        sv = o["platforms"]["Squarespace"]["supported_individual_native_variants"]
        hv = o["platforms"]["Shopify"]["supported_individual_native_variants"]
        row = {k: o.get(k, "") for k in ["product_id", "canonical_key", "name", "overall_disposition", "primary_image_file_id", "primary_folder_id", "next_action"]}
        row.update({"Squarespace_disposition": o["platforms"]["Squarespace"]["disposition"], "Shopify_disposition": o["platforms"]["Shopify"]["disposition"],
            "Squarespace_individual_product_ids": ";".join(sorted({v["native_variant"]["native_product_id"] for v in sv})),
            "Squarespace_individual_variant_ids": ";".join(v["native_variant"]["native_variant_id"] for v in sv),
            "Squarespace_individual_skus": ";".join(v["native_variant"]["sku_raw"] for v in sv),
            "Shopify_individual_handles": ";".join(sorted({v["native_variant"]["handle"] for v in hv})),
            "Shopify_individual_variant_keys": ";".join(v["native_variant"]["variant_key"] for v in hv),
            "Shopify_individual_skus": ";".join(v["native_variant"]["sku_raw"] for v in hv),
            "set_member_offer_refs": ";".join(o["set_member_offer_refs"]), "conflicting_offer_refs": ";".join(o["conflicting_individual_offer_refs"])})
        w.writerow(row)
write("RECONCILIATION_COUNTS.json", counts)
print(json.dumps(counts, indent=2))
