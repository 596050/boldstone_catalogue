"""Readback checks for the combined review, independent of its builder helpers."""
import collections
import csv
import datetime
import hashlib
import json
import pathlib

P = pathlib.Path(__file__).resolve().parent
cache = {}
checks = collections.Counter()
failures = []


def load(path):
    path = pathlib.Path(path)
    if not path.is_absolute():
        path = P / path
    if str(path) not in cache:
        cache[str(path)] = json.loads(path.read_text())
    return cache[str(path)]


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def check(kind, condition, detail=""):
    checks[kind] += 1
    if not condition:
        failures.append({"kind": kind, "detail": detail})


def resolve(locator):
    path = pathlib.Path(locator["path"])
    if "sha256" in locator:
        check("evidence_byte_hash", digest(path) == locator["sha256"], str(path))
    v = load(path)
    pointer = locator.get("json_pointer", "")
    if pointer:
        for token in pointer.lstrip("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            v = v[int(token)] if isinstance(v, list) else v[token]
    checks["resolved_json_pointers"] += 1
    return v


master = load("inputs/master-register.json")
review = load("LISTING_RECONCILIATION.json")
links = load("NATIVE_SOURCE_LINKS.json")["offers"]
edges = load("MATCH_EVIDENCE.json")["edges"]
issues = load("LISTING_ISSUES.json")
master_options = {o["product_id"]: o for o in master["options"]}
offers = {o["offer_ref"]: o for o in master["source_platform_offer_coverage"]}
options = {o["product_id"]: o for o in review["options"]}
edge_map = {e["edge_id"]: e for e in edges}
link_map = {o["offer_ref"]: o for o in links}
native_ss = load("worker-01/SQUARESPACE_SOURCE_INVENTORY.json")
native_ss_map = {p["native_product_id"]: p for p in native_ss["products"]}
native_sh = load("worker-02/shopify_products.json")
native_sh_variants = load("worker-02/shopify_variants.json")
native_sh_map = {p["handle"]: p for p in native_sh}
native_sh_variant_map = {v["variant_key"]: v for v in native_sh_variants}

check("184_unique_options", len(options) == len(review["options"]) == 184 and set(options) == set(master_options))
check("81_unique_offers", len(link_map) == len(links) == 81 and set(link_map) == set(offers))
check("262_unique_edges", len(edges) == len(edge_map) == 262)
check("122_original_bom_rows", sum(len(x["original_bom_rows"]) for x in links) == 122)
check("184_dispositions", sum(review["counts"]["overall_option_dispositions"].values()) == 184)
check("368_platform_cells", sum(len(o["platforms"]) for o in options.values()) == 368)
check("source_record_vs_configuration_counts", review["counts"]["source_supported_individual_design_options"] == 45 and review["counts"]["nonconflicting_source_supported_individual_record_links"] == 41 and review["counts"]["existing_individual_design_records_with_configuration_conflict"] == 4 and review["counts"]["options_without_supported_individual_native_record"] == 139 and review["counts"]["options_without_nonconflicting_supported_individual_native_record"] == 143)

for oid, link in link_map.items():
    src = offers[oid]
    check("native_source_ids", link["source_sku"] == src["source_sku"] and link["source_image_file_id"] == src["source_image_file_id"] and link["source_image_folder_id"] == src["source_image_folder_id"], oid)
    check("original_bom_preserved", link["original_bom_rows"] == src["bom_rows"], oid)
    check("offer_source_pointer", resolve(link["source_evidence"]) == src, oid)
    for platform in ["Squarespace", "Shopify"]:
        native = link[platform]
        if not native["record_present"]:
            continue
        if platform == "Squarespace":
            product = native_ss_map[native["native_product_id"]]
            check("squarespace_exact_product_id", native["native_product_id"] == src["squarespace_id"], oid)
            check("squarespace_native_count", len(native["variants"]) == len(product["variants"]), oid)
            for variant in native["variants"]:
                raw = resolve(variant["source_locator"])
                vid = raw.get("id", raw.get("variant_id"))
                sku = raw.get("sku", raw.get("values", {}).get("SKU"))
                check("raw_squarespace_variant_id_and_sku", vid == variant["native_variant_id"] and sku == variant["sku_raw"], oid + ":" + str(vid))
            check("squarespace_source_locator", resolve(native["native_inventory_evidence"])["native_product_id"] == native["native_product_id"], oid)
        else:
            check("shopify_exact_handle", native["handle"] == src["shopify_handle"] and native["handle"] in native_sh_map, oid)
            check("shopify_ids_not_invented", native["numeric_product_id"] is None and native["product_url"] is None, oid)
            for variant in native["variants"]:
                raw = native_sh_variant_map[variant["variant_key"]]
                check("shopify_variant_native_row", variant["handle"] == raw["handle"] and variant["sku_raw"] == raw["sku_raw"] and variant["option_tuple"] == raw["option_tuple"] and variant["source_row"] == raw["source_row"], oid)
                check("shopify_variant_numeric_ids_null", variant["numeric_product_id"] is None and variant["numeric_variant_id"] is None and variant["inventory_quantity"] is None, oid)
            check("shopify_description_native_scope", native["description_equals_retained_offer_after_html_whitespace_normalization"] is True and native["cross_platform_description_or_size_not_implicitly_inherited"] is True, oid)

for edge in edges:
    original = resolve(edge["evidence_ref"])
    check("source_edge_relationship_preserved", edge["relationship"] == original["relationship"] and edge["compatibility"] == original["compatibility"] and edge["join_basis"] == original["join_basis"], edge["edge_id"])
    check("edge_known_option_and_offer", edge["product_id"] in options and edge["offer_ref"] in offers, edge["edge_id"])
    for platform, pe in edge["platform_evidence"].items():
        check("source_link_pointer", resolve(pe["native_source_link_evidence"])["record_present"] == pe["native_record_present"], edge["edge_id"])
        check("no_exact_config_upgrade", pe["exact_current_option_configuration_match_verified"] is False and pe["exact_current_physical_configuration_certified"] is False, edge["edge_id"])
        if pe["individual_design_variant_link_supported"]:
            check("individual_relationship_gate", edge["relationship"] in {"SOURCE_SUPPORTED_STANDALONE_OPTION_CANDIDATE", "SINGLE_SOURCE_OFFER_CURRENT_VERSION_CONFLICT", "BOUND_PHOTOGRAPHED_DESIGN_CURRENT_CONFIGURATION_CONFLICT"}, edge["edge_id"])
            check("individual_design_finish_gate", edge["compatibility"]["design"]["state"] in {"BOUND_RETAINED_SOURCE_HERO_DESIGN", "EXPLICIT_SCOPED_DESIGN_ASSOCIATION"} and edge["compatibility"]["finish"]["state"] == "SOURCE_REVIEW_FINISH_SCOPE_SUPPORTED_CHEMISTRY_NOT_CERTIFIED", edge["edge_id"])
            check("one_exact_variant_for_source_sku", len(pe["exact_native_variant_for_recorded_source_sku"]) == 1 and pe["exact_native_variant_for_recorded_source_sku"][0]["sku_raw"] == offers[edge["offer_ref"]]["source_sku"], edge["edge_id"])
        else:
            check("family_set_gallery_not_individual", not pe["individual_option_variant_keys"] and not pe["individual_skus"], edge["edge_id"])

for pid, row in options.items():
    original = master_options[pid]
    check("option_identity_unchanged", row["name"] == original["name"] and row["canonical_key"] == original["canonical_key"] and row["source_scopes"] == original["source_scopes"], pid)
    check("stable_dropbox_ids_unchanged", row["primary_image_file_id"] == original.get("file_id") and row["primary_folder_id"] == original.get("folder_id") and row["context_image_file_id"] == original.get("context_file_id") and row["context_folder_id"] == original.get("context_folder_id"), pid)
    check("working_specs_preserved", row["working_specifications"] == {k: v["display"] for k, v in original["master_fields"].items()} and row["working_specification_status"] == original["working_specification_status"], pid)
    for field_name, field in original["master_fields"].items():
        check("all1104_authoritative_current_field_displays", row["working_specifications"][field_name] == field["display"], pid + ":" + field_name)
    check("option_source_pointer", resolve(row["evidence_ref"])["product_id"] == pid, pid)
    actual_edges = [e for e in edges if e["product_id"] == pid]
    check("all_edges_referenced", set(row["all_evidence_edge_ids"]) == {e["edge_id"] for e in actual_edges}, pid)
    check("option_not_upgraded_to_exact_config", row["exact_current_option_configuration_match_verified"] is False and row["exact_current_configuration_certified"] is False, pid)
    for platform, state in row["platforms"].items():
        supported = [e for e in actual_edges if e["platform_evidence"][platform]["individual_design_variant_link_supported"]]
        check("option_platform_assignments", {v["offer_ref"] for v in state["supported_individual_native_variants"]} == {e["offer_ref"] for e in supported}, pid + ":" + platform)
        check("platform_live_scope", state["current_authenticated_admin_inventory_verified"] is False and state["exact_current_option_configuration_match_verified"] is False and bool(state["absence_scope"]), pid)
        if row["canonical_component_id"] == "BC-WALL-CIRCLE" or row["canonical_component_id"] in {"BC-BONE-1", "BC-BONE-2"}:
            check("wall_bone_no_individual_sku", not state["supported_individual_native_variants"], pid)

wc = next(x for x in links if x["offer_ref"] == "O001")
check("wall144_not_promoted", len(wc["Squarespace"]["variants"]) == len(master["wall_circle_native_options"]) == 144)
check("O006_ambiguous_finish_unassigned", all(not v["individual_design_variant_link_supported"] for e in edges if e["offer_ref"] == "O006" for v in e["platform_evidence"].values()))
mw = [e for e in edges if e["offer_ref"] == "O015" and any(p["individual_design_variant_link_supported"] for p in e["platform_evidence"].values())]
check("O015_bound_photo_not_nominal_title", len(mw) == 1 and mw[0]["product_id"] == "BSI-70C7029C1DB1" and "CONFIGURATION_CONFLICT" in mw[0]["relationship"])
check("four_design_conflicts_not_missing", sum(o["overall_disposition"] == "EXISTING_INDIVIDUAL_DESIGN_WITH_CONFIGURATION_CONFLICT" for o in options.values()) == 4)
check("no_deleted_or_added_catalogue_options", all(o["catalogue_count_increment"] == 0 for o in options.values()))
check("native_collision_present", issues["counts_by_type"].get("CONFIRMED_NATIVE_SKU_COLLISION_DUPLICATE_LISTING_CANDIDATE") == 1)
check("public_overlaps_separate", issues["counts_by_type"].get("MULTIPLE_PUBLIC_INDIVIDUAL_RECORDS_FOR_ONE_CATALOGUE_DESIGN_OPTION") == 3)
check("public208_203_discrepancy_retained", any("203" in s and "208" in s for s in review["scope_and_limits"]))
with (P / "OPTION_LISTING_REVIEW.csv").open(newline="") as f:
    table = list(csv.DictReader(f))
check("csv_all184", len(table) == 184 and {r["product_id"] for r in table} == set(options))
check("no_remote_or_shared_writes", review["remote_writes"] == review["shared_master_writes"] == review["dropbox_calls"] == 0)

for item in load("INPUT_MANIFEST.json")["master_inputs"]:
    check("frozen_master_input_hash", digest(item["snapshot"]) == item["sha256"], item["snapshot"])
check("workbook_hash", digest(P / "inputs/current-master.xlsx") == review["input_workbook_sha256"])
for item in load("worker-01/SOURCE_MANIFEST.json")["cached_sources"].values():
    check("historical_source_hash", digest(item["path"]) == item["sha256"], item["path"])
for item in load("worker-02/source_receipts.json")["sources"]:
    check("historical_source_hash", digest(item["path"]) == item["sha256"], item["path"])

result = {"schema": "boldstone.combined-listing-readback.v1", "status": "PASS" if not failures else "FAIL", "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "counts": review["counts"], "checks_by_kind": dict(checks), "total_checks": sum(checks.values()), "issues": failures,
          "historical_sources_unchanged": not any(x["kind"] == "historical_source_hash" for x in failures), "writes_to_shared_master_or_platforms": 0,
          "fake_adapter_result": load("FAKE_ADAPTER_GATE.json"), "live_sandbox_tests_run": False}
(P / "VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "total_checks": result["total_checks"], "issues": failures}, indent=2))
raise SystemExit(bool(failures))
