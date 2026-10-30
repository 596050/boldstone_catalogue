"""Independently read the final local-only crosswalk against original CSV and catalogue."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B.parent / 'reports/local-platform-crosswalk-final-20261024-root'
OUT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
checks = []


def check(name, condition, detail=None):
    checks.append({'check': name, 'pass': bool(condition), 'detail': detail})


seal = read(H / 'sealed-handoff.json')
check('Exact final handoff seal only', sha(H / 'sealed-handoff.json') == '2e1a3bd46a0dedac9db74e814d2bb437800ec796d7f21d3143b3f88352986aac')
check('All six final sealed artifacts exact', len(seal['files']) == 6 and all(sha(p) == v for p, v in seal['files'].items()))
j = read(H / 'local-platform-crosswalk.json')
check('Exact final structured report bytes', sha(H / 'local-platform-crosswalk.json') == 'b17ad05bf828b22bdbee4a6fcb8432d3075273a32580e4b23735501c2a95c7be')
for path, value in j['source_manifest'].items():
    check('Exact source manifest bytes and size: ' + path, sha(path) == value['sha256'] and Path(path).stat().st_size == value['bytes'])
for path, expected in j['baseline_protected_files'].items():
    check('Protected canonical input unchanged: ' + path, sha(path) == expected)
p = read(B / 'current-master.json')
g = read(B / p['register'])
options = {x['product_id']: x for x in g['options']}
active = set(g['active_option_ids'])
export = j['source_authority']['primary_shopify_export']
with Path(export['path']).open(encoding='utf-8-sig', newline='') as handle:
    reader = csv.DictReader(handle)
    headers = reader.fieldnames
    raw = list(reader)
check('Original local export416 rows and95 columns', len(raw) == 416 and len(headers) == 95)
check('No Shopify numeric ID columns in original export', not any(x in headers for x in ['Product ID', 'Variant ID']))
check('Selected CSV export date remains unknown', export['export_creation_date'] is None)
by_handle = defaultdict(list)
for n, row in enumerate(raw, 2):
    by_handle[row['Handle']].append((n, row))
check('All136 original product handles retained', {x['handle'] for x in j['local_shopify_records']} == set(by_handle) and len(by_handle) == len(j['local_shopify_records']) == 136)
all_variants, all_media, wall_handles = [], [], set()
product_fields = {'handle_raw': 'Handle', 'title': 'Title', 'body_html': 'Body (HTML)', 'vendor_raw': 'Vendor', 'type_raw': 'Type', 'tags_raw': 'Tags', 'published_raw': 'Published', 'status_raw': 'Status'}
variant_fields = {'sku_raw': 'Variant SKU', 'price_raw': 'Variant Price', 'compare_at_price_raw': 'Variant Compare At Price', 'grams_raw': 'Variant Grams', 'inventory_tracker_raw': 'Variant Inventory Tracker', 'inventory_policy_raw': 'Variant Inventory Policy', 'requires_shipping_raw': 'Variant Requires Shipping', 'taxable_raw': 'Variant Taxable', 'barcode_raw': 'Variant Barcode', 'variant_image_raw': 'Variant Image'}
for item in j['local_shopify_records']:
    product = item['product']
    handle = item['handle']
    header = raw[product['source_header_row']['logical_row_including_header'] - 2]
    check('Raw product fields exact: ' + handle, all(product[k] == header[c] for k, c in product_fields.items()))
    check('Product numeric IDs and live/physical claims stay absent: ' + handle, product['numeric_product_id'] is None and not product['current_admin_or_live_public_presence_verified'] and not product['physical_stock_verified'])
    expected_variant_rows = {n for n, row in by_handle[handle] if row['Option1 Value'] or row['Variant SKU'] or row['Variant Price']}
    check('Every original variant row retained: ' + handle, {v['source_row']['logical_row_including_header'] for v in item['variants']} == expected_variant_rows)
    for variant in item['variants']:
        row = raw[variant['source_row']['logical_row_including_header'] - 2]
        check('Raw SKU, economics and image cells exact: ' + variant['variant_key'], row['Handle'] == handle and all(variant[k] == row[c] for k, c in variant_fields.items()))
        expected_options = [{'position': n, 'name': row['Option' + str(n) + ' Name'] or header['Option' + str(n) + ' Name'], 'value': row['Option' + str(n) + ' Value']} for n in range(1, 4) if row['Option' + str(n) + ' Value']]
        check('Option tuple and unknown native IDs preserved: ' + variant['variant_key'], [{k: o[k] for k in ['position', 'name', 'value']} for o in variant['option_tuple']] == expected_options and variant['numeric_product_id'] is None and variant['numeric_variant_id'] is None and not variant['current_live_quantity_or_draft_state_verified'])
        all_variants.append(variant)
    expected_media_rows = {n for n, row in by_handle[handle] if row['Image Src']}
    check('Complete product gallery occurrences retained: ' + handle, {m['source_row']['logical_row_including_header'] for m in item['full_product_gallery']} == expected_media_rows)
    for media in item['full_product_gallery']:
        row = raw[media['source_row']['logical_row_including_header'] - 2]
        check('Original gallery URL, position, alt and variant-image cell exact: ' + str(media['source_row']['logical_row_including_header']), media['image_src'] == row['Image Src'] and media['image_position_raw'] == row['Image Position'] and media['image_alt_raw'] == row['Image Alt Text'] and media['variant_image_raw'] == row['Variant Image'])
        all_media.append(media)
    if product['in_preserved_wall_subset']:
        wall_handles.add(handle)
check('Exactly160 variants and416 gallery occurrences', len(all_variants) == 160 and len(all_media) == 416)
check('Wall subset38 products/38 variants/117 media retained', len(wall_handles) == 38 and sum(v['handle'] in wall_handles for v in all_variants) == 38 and sum(m['handle'] in wall_handles for m in all_media) == 117)
check('No explicit Shopify variant-image values invented', not any(v['variant_image_raw'] for v in all_variants) and not any(row['Variant Image'] for row in raw))
sources = j['squarespace_source_records']
check('All eighty source references exact', len(sources) == 80 and {s['offer_ref'] for s in sources} == {'O' + str(n).zfill(3) for n in range(1, 81)})
matched, unpaired, association_ids, total_associations = set(), set(), set(), 0
local_variants_by_sku = defaultdict(list)
for variant in all_variants:
    if variant['sku_raw'] and variant['handle'] in wall_handles:
        local_variants_by_sku[variant['sku_raw']].append(variant)
for source in sources:
    ref = source['offer_ref']
    edge = next(x for x in g['source_offer_edges'] if x['offer_ref'] == ref)
    tuple_ = source['squarespace_native_tuple']
    check('Retained source, member order/quantity and source photo scope exact: ' + ref, source['retained_source_offer'] == edge['source_offer'] and source['retained_member_scope'] == edge['members'] and source['source_image_reference'] == edge['current_primary_reference'])
    sku = tuple_['sku_raw']
    candidates = local_variants_by_sku.get(sku, []) if sku else []
    if source['shopify_local_variant']:
        matched.add(ref)
        check('Exact unique nonempty raw SKU local pair: ' + ref, bool(sku) and len(candidates) == 1 and candidates[0] == source['shopify_local_variant'] and source['shopify_local_variant']['sku_raw'] == sku and source['platform_record_match'] == 'EXACT_NONEMPTY_SHARED_SKU_IN_REQUESTED_LOCAL_FILES')
    else:
        unpaired.add(ref)
        check('No forced pair for unpaired source: ' + ref, not candidates)
    gallery = source['local_squarespace_gallery_record']
    check('Exact captured Squarespace tuple and complete gallery: ' + ref, gallery['native_product_id'] == tuple_['native_product_id'] and gallery['native_variant_id'] == tuple_['native_variant_id'] and gallery['sku_raw'] == sku and len(gallery['ordered_gallery']) == gallery['gallery_entry_count'])
    for record in source['related_current_individual_options']:
        option = options[record['product_id']]
        check('Current full fields/reference preserved without exact variant promotion: ' + ref + ':' + record['product_id'], record['master_fields'] == option['master_fields'] and record['current_reference'] == {k: option[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']} and record['new_exact_individual_variant_assignment'] is False)
        association_ids.add(record['product_id'])
        total_associations += 1
check('Exactly37 local source pairs and43 unpaired sources', matched == set(j['matched_local_source_offer_refs']) and len(matched) == 37 and unpaired == set(j['unpaired_squarespace_offer_refs']) and len(unpaired) == 43)
check('All445 complete Squarespace gallery entries retained', sum(s['local_squarespace_gallery_record']['gallery_entry_count'] for s in sources) == 445)
check('Exactly121 active Squarespace-associated options and255 scoped associations', len(association_ids) == 121 and total_associations == 255)
drafts = j['unpaired_shopify_wall_records']
check('One blank-SKU Frozen Fish draft stays unpaired context', len(drafts) == 1 and drafts[0]['product']['handle'] == 'frozen-fish' and all(not v['sku_raw'] for v in drafts[0]['variants']) and len(drafts[0]['related_current_individual_options']) == 5)
for record in drafts[0]['related_current_individual_options']:
    option = options[record['product_id']]
    check('Draft context full fields/reference retained without alias: ' + record['product_id'], record['master_fields'] == option['master_fields'] and record['current_reference'] == {k: option[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']} and record['new_exact_individual_variant_assignment'] is False)
    association_ids.add(record['product_id'])
without = j['active_options_without_existing_source_edges']
check('Exactly123 existing associations and65 remaining active options', len(association_ids) == 123 and {x['product_id'] for x in without} == active - association_ids and len(without) == 65 and len(active) == 188)
for record in without:
    option = options[record['product_id']]
    check('Unbound active option retains all six fields and reference: ' + record['product_id'], record['master_fields'] == option['master_fields'] and record['current_reference'] == {k: option[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']})


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k == 'href' and v:
                self.urls.append(v)
            if k == 'id' and v:
                self.ids.add(v)


parsed = Links()
parsed.feed((H / 'index.html').read_text())
missing = []
for url in parsed.urls:
    u = urlsplit(url)
    if u.scheme in ['', 'file']:
        target = Path(unquote(u.path)) if u.path else H / 'index.html'
        target = target if target.is_absolute() else H / target
        if not target.is_file():
            missing.append(url)
        elif u.fragment:
            other = Links()
            other.feed(target.read_text())
            if unquote(u.fragment) not in other.ids:
                missing.append(url)
check('All local report links and fragments resolve', not missing, missing)
check('No platform or canonical writes and no exact new assignments', all(j['counts'][k] == 0 for k in ['new_exact_individual_variant_assignments', 'new_numeric_Shopify_IDs_invented', 'network_calls_by_local_crosswalk', 'canonical_or_platform_writes']))
check('Same final seal and canonical inputs at end', sha(H / 'sealed-handoff.json') == '2e1a3bd46a0dedac9db74e814d2bb437800ec796d7f21d3143b3f88352986aac' and all(sha(path) == expected for path, expected in j['baseline_protected_files'].items()))
result = {'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'checks_passed': sum(x['pass'] for x in checks), 'checks_total': len(checks), 'checks': checks,
    'source_seal_sha256': sha(H / 'sealed-handoff.json'), 'source_report_sha256': sha(H / 'local-platform-crosswalk.json'),
    'counts': j['counts'], 'scope': 'Final serialized local crosswalk and exact original CSV/source proof only. No new gallery visual review, live platform claim, network call, alias or canonical write.'}
(OUT / 'readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
(OUT / 'sealed-handoff.json').write_text(json.dumps({'status': result['status'], 'files': {n: sha(OUT / n) for n in ['qa.py', 'readback.json']}}, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'checks_passed': result['checks_passed'], 'checks_total': len(checks), 'readback_sha256': sha(OUT / 'readback.json'), 'seal_sha256': sha(OUT / 'sealed-handoff.json')}))
for check_ in checks:
    if not check_['pass']:
        print('FAIL', check_)
raise SystemExit(0 if result['status'] == 'PASS' else 1)
