"""Compare documented source associations; never establish new product identities."""
import csv
import hashlib
import html
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

LANE = Path(__file__).resolve().parent
ROOT = LANE.parents[2]
SOURCE = ROOT / "components/parallel-reviews/listing-reconciliation-2026-10-20/worker-02"
SQ = Path("/Users/tprice/Library/Application Support/BoldstoneLocal/cache/squarespace-admin-export-20261024T005645Z/products_Oct-24_01-55-19AM.csv")
OUT = LANE / "fresh-squarespace-comparison"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ref(path):
    return {"path": str(path), "sha256": digest(path.read_bytes())}


def read(path):
    return json.loads(path.read_text())


def save(name, data):
    path = OUT / name
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return ref(path)


def read_csv_bytes(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    output = []
    last_line = reader.line_num
    for logical_row, raw in enumerate(reader, 2):
        output.append({"logical_row": logical_row, "physical_line_start": last_line + 1,
                       "physical_line_end": reader.line_num, "raw": raw})
        last_line = reader.line_num
    return reader.fieldnames, output


pointer_bytes = (ROOT / "current-master.json").read_bytes()
pointer = json.loads(pointer_bytes)
register_path = ROOT / pointer["register"]
register_bytes = register_path.read_bytes()
assert digest(register_bytes) == pointer["register_sha256"]
register = json.loads(register_bytes)
sq_bytes = SQ.read_bytes()
assert digest(sq_bytes) == "cdce1939100db77c78a818a99e4081712837b9aca21602b095a6055a40c7fbbf"
sq_headers, sq_rows = read_csv_bytes(sq_bytes)
assert len(sq_headers) == 34 and len(sq_rows) == 376
source_receipts = read(SOURCE / "source_receipts.json")
historical_receipt = next(x for x in source_receipts["sources"] if x["source_id"] == "SH_NATIVE_CSV_S09")
historical_path = Path(historical_receipt["path"])
historical_bytes = historical_path.read_bytes()
assert digest(historical_bytes) == historical_receipt["sha256"]
historical_headers, historical_rows = read_csv_bytes(historical_bytes)
assert len(historical_headers) == 95 and len(historical_rows) == historical_receipt["data_rows"] == 416
wall = read(SOURCE / "shopify_wall_inventory.json")
assert len(wall["products"]) == len(wall["variants"]) == 38

sq_products = defaultdict(list)
sq_skus = defaultdict(list)
last_id = None
for row in sq_rows:
    last_id = row["raw"]["Product ID [Non Editable]"] or last_id
    assert last_id
    sq_products[last_id].append(row)
    if row["raw"]["SKU"]:
        sq_skus[row["raw"]["SKU"]].append({"product_id": last_id, "logical_row": row["logical_row"]})
assert len(sq_products) == 208
assert len({x["raw"]["Variant ID [Non Editable]"] for x in sq_rows}) == 376

offers_by_handle = defaultdict(list)
for offer in register["source_platform_offer_coverage"]:
    if offer.get("shopify_handle"):
        offers_by_handle[offer["shopify_handle"]].append(offer)
variants_by_handle = defaultdict(list)
for variant in wall["variants"]:
    variants_by_handle[variant["handle"]].append(variant)
options = [x for x in register["options"] if x.get("counted_as_individual_option") and x.get("catalogue_status") != "Retired"]
assert len(options) == 188
results = []
for product in wall["products"]:
    handle = product["handle"]
    variants = variants_by_handle[handle]
    assert len(variants) == 1
    variant = variants[0]
    raw_source = historical_rows[variant["source_row"]["logical_row_including_header"] - 2]
    for source_key, normalized_key in [("Variant SKU", "sku_raw"), ("Variant Price", "price_raw")]:
        assert raw_source["raw"][source_key] == variant[normalized_key]
    offers = offers_by_handle[handle]
    offer_ids = {x["offer_ref"] for x in offers}
    paired_ids = {x["squarespace_id"] for x in offers if x.get("squarespace_id")}
    assert len(paired_ids) <= 1
    pair_id = next(iter(paired_ids), None)
    current_rows = sq_products.get(pair_id, [])
    matches = [x for x in current_rows if x["raw"]["SKU"] and x["raw"]["SKU"] == variant["sku_raw"]]
    assert len(matches) <= 1
    current = matches[0] if matches else None
    references = []
    for option in options:
        scoped_refs = option.get("current_listing_reconciliation", {}).get("platforms", {}).get("Shopify", {}).get("related_offer_refs", [])
        if offer_ids.intersection(scoped_refs):
            references.append({"product_id": option["product_id"], "name": option["name"],
                               "image_url": option.get("image_url"), "folder_url": option.get("folder_url"),
                               "file_id": option.get("file_id"), "folder_id": option.get("folder_id"),
                               "technical_photo_coverage": option.get("photo_coverage"),
                               "association_scope": "Existing catalogue source association; not a new exact individual variant match"})
    fresh = None
    if current:
        raw = current["raw"]
        first = sq_products[pair_id][0]["raw"]
        fresh = {"product_id": pair_id, "variant_id": raw["Variant ID [Non Editable]"],
                 "title": raw["Title"] or first["Title"], "sku_raw": raw["SKU"],
                 "price_raw": raw["Price"], "sale_price_raw": raw["Sale Price"], "on_sale_raw": raw["On Sale"],
                 "visible_raw": raw["Visible"] or first["Visible"], "stock_raw": raw["Stock"],
                 "option_attributes": [{"name": raw[f"Option Name {i}"], "value": raw[f"Option Value {i}"]}
                                       for i in range(1, 7) if raw[f"Option Name {i}"] or raw[f"Option Value {i}"]],
                 "currency": None, "currency_state": "Not encoded in this CSV; no currency equivalence inferred",
                 "source_locator": {"path": str(SQ), "logical_row_including_header": current["logical_row"],
                                    "physical_line_start": current["physical_line_start"], "physical_line_end": current["physical_line_end"]},
                 "matched_by": "Previously documented exact product ID, then exact nonblank SKU within that product"}
    results.append({"historical_shopify_handle": handle, "historical_shopify_title": product["title"],
                    "historical_shopify_variant": {"variant_key": variant["variant_key"], "sku_raw": variant["sku_raw"],
                                                   "price_raw": variant["price_raw"], "status_raw": variant["product_status_raw"],
                                                   "currency": variant["currency"], "currency_state": variant["currency_state"],
                                                   "source_locator": variant["source_row"],
                                                   "current_product_id": None, "current_variant_id": None},
                    "documented_offer_refs": sorted(offer_ids), "documented_squarespace_product_id": pair_id,
                    "documented_source_sale_scopes": sorted({x["source_sale_scope"] for x in offers}),
                    "documented_squarespace_url": next((x["source_url"] for x in offers if x.get("squarespace_id")), None),
                    "fresh_squarespace_variant": fresh,
                    "result": "DOCUMENTED_PAIR_PRESENT_WITH_EXACT_SKU" if fresh else "NO_DOCUMENTED_SQUARESPACE_PAIR;EXISTING_DEFERRED_CASE",
                    "exported_price_strings_equal": fresh["price_raw"] == variant["price_raw"] if fresh else None,
                    "global_fresh_sku_occurrences": sq_skus.get(variant["sku_raw"], []) if variant["sku_raw"] else [],
                    "catalogue_references": references,
                    "current_shopify_presence_verified": False, "new_identity_or_physical_match_claimed": False,
                    "new_photo_question": False})

paired = [x for x in results if x["fresh_squarespace_variant"]]
assert len(results) == len({x["historical_shopify_handle"] for x in results}) == 38
assert len(paired) == 37
assert all(x["exported_price_strings_equal"] for x in paired)
assert [x["historical_shopify_handle"] for x in results if not x["fresh_squarespace_variant"]] == ["frozen-fish"]
OUT.mkdir()
now = datetime.now(timezone.utc).isoformat()
summary = {"schema": "boldstone.historical-shopify-fresh-squarespace-source-comparison.v1", "recorded_utc": now,
           "status": "READ_ONLY_SOURCE_COMPARISON_COMPLETE", "inputs": {"current_master": ref(register_path),
           "fresh_authenticated_squarespace_export": ref(SQ), "historical_shopify_export": ref(historical_path),
           "historical_wall_inventory": ref(SOURCE / "shopify_wall_inventory.json"), "historical_source_receipts": ref(SOURCE / "source_receipts.json")},
           "counts": {"historical_wall_handles": 38, "documented_pairs_checked": 37,
                      "exact_documented_squarespace_product_ids_present": 37, "exact_sku_variants_within_documented_products": 37,
                      "paired_export_price_strings_equal": 37, "paired_export_price_strings_different": 0,
                      "fresh_squarespace_product_visibility": dict(Counter(x["fresh_squarespace_variant"]["visible_raw"] for x in paired)),
                      "unpaired_historical_drafts_retained_deferred": 1, "fresh_squarespace_entire_export_products": 208,
                      "fresh_squarespace_entire_export_variants": 376, "new_logical_matches": 0,
                      "current_shopify_products_verified": 0},
           "meaning": "All 37 previously documented wall-source pairs are present under the recorded Squarespace product IDs in the fresh authenticated export. Their exact SKUs and exported price strings agree with the historical Shopify file. This does not certify current Shopify presence, currency equivalence, a current individual-option match, physical specifications or stock.",
           "deferred_case": "The historical blank-SKU frozen-fish draft has no documented Squarespace pair. Keep the existing Frozen Fish identity deferral; no new owner question.",
           "sku_collision_scope": "A separately owns the Rust O051/O067 Squarespace collision. No shared SKU among these 37 matched source rows is duplicated in this fresh export; that does not resolve other product collisions.",
           "source_time_scope": "Squarespace is the fresh 24 October 2026 authenticated export; Shopify is a preserved snapshot corroborated by a 30 August 2024 archive, not a current Shopify inventory.",
           "shared_canonical_writes": 0, "native_mutations": 0, "platform_mutations": 0,
           "rows": sorted(results, key=lambda x: x["historical_shopify_title"].casefold())}
report_ref = save("comparison.json", summary)
e = html.escape


def link(url, label):
    return '<a href="' + e(url, quote=True) + '">' + e(label) + '</a>' if url else e(label) + ": not recorded"


page = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Squarespace and historical Shopify comparison</title><style>body{font:16px system-ui;max-width:1050px;margin:40px auto;padding:0 24px;line-height:1.5;color:#22302b}a{color:#235775}details{margin:12px 0;border:1px solid #ccd5ce;border-radius:8px;padding:12px 16px}summary{cursor:pointer;font-weight:650}table{width:100%;border-collapse:collapse}th,td{padding:9px;text-align:left;border-bottom:1px solid #ddd;vertical-align:top}.note{background:#f3f6f2;padding:16px}.links{padding-left:0;list-style:none}.links li{padding:7px 0}</style></head><body><h1>Squarespace and historical Shopify comparison</h1><p><strong>37 documented wall-listing pairs checked.</strong> All 37 are present in the fresh Squarespace export with their recorded product IDs and exact SKUs. Their exported price values match the saved Shopify file.</p><p class="note">Squarespace data is from 24 October 2026. Shopify data is historical. These are product-source associations, including arrangements; they do not establish exact current Shopify products or individual variants. The CSVs do not encode store currency. Frozen Fish remains deferred.</p><p>' + link(str(SQ), 'Fresh Squarespace source') + ' · ' + link(str(historical_path), 'Historical Shopify source') + ' · ' + link('comparison.json', 'Detailed comparison') + '</p>']
for row in summary["rows"]:
    fresh = row["fresh_squarespace_variant"]
    page.append('<details><summary>' + e(row["historical_shopify_title"]) + '</summary><p>Historical handle: <code>' + e(row["historical_shopify_handle"]) + '</code></p>')
    if fresh:
        page.append('<p>' + link(row["documented_squarespace_url"], 'Squarespace listing') + ' · Existing source pair found in the current export.</p><table><tr><th>Source</th><th>SKU</th><th>Exported price value</th></tr><tr><td>Historical Shopify</td><td>' + e(row["historical_shopify_variant"]["sku_raw"]) + '</td><td>' + e(row["historical_shopify_variant"]["price_raw"]) + '</td></tr><tr><td>Squarespace 24 October 2026</td><td>' + e(fresh["sku_raw"]) + '</td><td>' + e(fresh["price_raw"]) + '</td></tr></table>')
    else:
        page.append('<p>Existing unpaired Frozen Fish draft. Identity remains deferred.</p>')
    page.append('<p>Documented sale scope: ' + e(', '.join(row["documented_source_sale_scopes"])) + '.</p><p><strong>Associated catalogue references</strong> — retained links, with no new individual-variant assignment:</p><ul class="links">')
    for item in row["catalogue_references"]:
        page.append('<li>' + e(item["name"]) + ': ' + link(item["image_url"], 'Image') + ' · ' + link(item["folder_url"], 'Containing folder') + '</li>')
    page.append('</ul></details>')
page.append('</body></html>')
html_path = OUT / "comparison.html"
with html_path.open("x", encoding="utf-8") as stream:
    stream.write(''.join(page))
assert SQ.read_bytes() == sq_bytes and historical_path.read_bytes() == historical_bytes
assert (ROOT / "current-master.json").read_bytes() == pointer_bytes
assert register_path.read_bytes() == register_bytes
saved = read(OUT / "comparison.json")
assert len(saved["rows"]) == 38 and len({x["historical_shopify_handle"] for x in saved["rows"]}) == 38
assert sum(bool(x["fresh_squarespace_variant"]) for x in saved["rows"]) == 37
seal = save("comparison-seal.json", {"status": "PASS_READ_ONLY_COMPARISON_AND_SAVED_READBACK", "recorded_utc": now,
           "comparison": report_ref, "page": ref(html_path), "counts": summary["counts"],
           "source_bytes_unchanged": True, "canonical_register_and_pointer_unchanged": True,
           "new_logical_or_physical_matches": 0, "native_mutations": 0, "platform_mutations": 0})
print(json.dumps({"status": "PASS", "output": str(OUT), "counts": summary["counts"], "seal": seal}))
