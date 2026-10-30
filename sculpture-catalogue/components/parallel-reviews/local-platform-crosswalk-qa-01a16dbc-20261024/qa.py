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
H = B.parent / 'reports/local-platform-crosswalk-corrected-20261024-root'
OUT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
checks = []


def check(name, condition, detail=None):
    checks.append({'check': name, 'pass': bool(condition), 'detail': detail})


seal = read(H / 'sealed-handoff.json')
check('Exact corrected final handoff seal', sha(H / 'sealed-handoff.json') == '39d08659707d6ad99010e64b3503caf6bcb07d330e067cafad1109143bdc7d4f')
check('All six final sealed artifacts exact', len(seal['files']) == 6 and all(sha(p) == v for p, v in seal['files'].items()))
j = read(H / 'local-platform-crosswalk.json')
check('Exact corrected structured report bytes', sha(H / 'local-platform-crosswalk.json') == 'ef7158d87d6402d1e57b8f209da3ca6421104887da9c8a1e3ea9413b72bce578')
old_h = B.parent / 'reports/local-platform-crosswalk-final-20261024-root'
old_seal = read(old_h / 'sealed-handoff.json')
check('Superseded candidate preserved byte-for-byte', sha(old_h / 'sealed-handoff.json') == '2e1a3bd46a0dedac9db74e814d2bb437800ec796d7f21d3143b3f88352986aac' and all(sha(path) == value for path, value in old_seal['files'].items()))
old_report = read(old_h / 'local-platform-crosswalk.json')
parent_keys = {'actual_parent_matches_saved_parent', 'actual_parent_matches_canonical_option_parent', 'canonical_parent_comparison_scope', 'saved_parent_comparison_state', 'canonical_option_parent_ids'}


def excluding_parent_diagnostics(value, root=True):
    if isinstance(value, dict):
        return {k: excluding_parent_diagnostics(v, False) for k, v in value.items() if k not in parent_keys and not (root and k == 'prepared_utc')}
    if isinstance(value, list):
        return [excluding_parent_diagnostics(x, False) for x in value]
    return value


check('Correction changes only parent diagnostics and preparation time', excluding_parent_diagnostics(j) == excluding_parent_diagnostics(old_report))
check('Rendered crosswalk bytes unchanged by diagnostic fix', sha(H / 'index.html') == sha(old_h / 'index.html') == 'c27d45c1c64d7d96d957c54e5b01a0521e4a28c2374be8b781ef3f8115f4bc79')
for path, value in j['source_manifest'].items():
    check('Exact source manifest bytes and size: ' + path, sha(path) == value['sha256'] and Path(path).stat().st_size == value['bytes'])
for path, expected in j['baseline_protected_files'].items():
    check('Protected canonical input unchanged: ' + path, sha(path) == expected)
p = read(B / 'current-master.json')
g = read(B / p['register'])
options = {x['product_id']: x for x in g['options']}
active = set(g['active_option_ids'])
census_path = next(Path(x) for x in j['source_manifest'] if x.endswith('all-current-6360-image-folder-links.json'))
current_census = {x['file_id']: x for x in read(census_path)}
assets = read(B / p['current_asset_reference_map']['path'])


def reference_retained(wrapper, option):
    fid = option.get('file_id') or None
    if (wrapper.get('file_id') or None) != fid or wrapper['canonical_reference_changed_by_crosswalk'] is not False:
        return False
    saved = wrapper['saved_catalogue_reference']
    if fid is None:
        return saved is None and wrapper['fresh_scoped_native_reference'] is None
    observed = wrapper['fresh_scoped_native_reference']
    return (saved == assets.get(fid)
            and observed == current_census.get(fid)
            and (observed is None or observed['folder_id'] == option['folder_id']))

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
    image_reference = source['source_image_reference']
    saved = image_reference['saved_catalogue_reference']
    primary = edge.get('current_primary_reference')
    primary_retained = saved is None if primary is None else (all(saved.get(k) == primary.get(k) for k in ['file_id', 'folder_id']) and all(saved.get(k) == assets[primary['file_id']].get(k) for k in ['file_id', 'folder_id', 'image_url', 'folder_url']))
    check('Retained source, member order/quantity and source photo identity exact: ' + ref, source['retained_source_offer'] == edge['source_offer'] and source['retained_member_scope'] == edge['members'] and primary_retained and image_reference['canonical_reference_changed_by_crosswalk'] is False)
    check('Fresh scoped source reference equals independent current census record: ' + ref, image_reference['fresh_scoped_native_reference'] == current_census.get(image_reference['file_id']))
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
        check('Current full fields/stable IDs retained and links bound to explicit maps: ' + ref + ':' + record['product_id'], record['master_fields'] == option['master_fields'] and reference_retained(record['current_reference'], option) and record['new_exact_individual_variant_assignment'] is False)
        association_ids.add(record['product_id'])
        total_associations += 1
check('Exactly37 local source pairs and43 unpaired sources', matched == set(j['matched_local_source_offer_refs']) and len(matched) == 37 and unpaired == set(j['unpaired_squarespace_offer_refs']) and len(unpaired) == 43)
check('All445 complete Squarespace gallery entries retained', sum(s['local_squarespace_gallery_record']['gallery_entry_count'] for s in sources) == 445)
check('Exactly121 active Squarespace-associated options and255 scoped associations', len(association_ids) == 121 and total_associations == 255)
drafts = j['unpaired_shopify_wall_records']
check('One blank-SKU Frozen Fish draft stays unpaired context', len(drafts) == 1 and drafts[0]['product']['handle'] == 'frozen-fish' and all(not v['sku_raw'] for v in drafts[0]['variants']) and len(drafts[0]['related_current_individual_options']) == 5)
for record in drafts[0]['related_current_individual_options']:
    option = options[record['product_id']]
    check('Draft context fields/stable IDs retained with explicit map links: ' + record['product_id'], record['master_fields'] == option['master_fields'] and reference_retained(record['current_reference'], option) and record['new_exact_individual_variant_assignment'] is False)
    association_ids.add(record['product_id'])
without = j['active_options_without_existing_source_edges']
check('Exactly123 existing associations and65 remaining active options', len(association_ids) == 123 and {x['product_id'] for x in without} == active - association_ids and len(without) == 65 and len(active) == 188)
for record in without:
    option = options[record['product_id']]
    check('Unbound active option retains six fields/stable IDs and explicit links: ' + record['product_id'], record['master_fields'] == option['master_fields'] and reference_retained(record['current_reference'], option))
unique_records = {record['product_id']: record for source in sources for record in source['related_current_individual_options']}
unique_records.update({record['product_id']: record for record in drafts[0]['related_current_individual_options'] + without})
for oid, record in unique_records.items():
    wrapper = record['current_reference']
    saved, observed = wrapper['saved_catalogue_reference'], wrapper['fresh_scoped_native_reference']
    if saved and observed:
        expected = saved['folder_id'] == observed['folder_id'] if saved.get('folder_id') is not None else None
        check('Parent comparison distinguishes missing saved metadata: ' + oid, wrapper.get('actual_parent_matches_saved_parent') is expected)
        expected_canonical_parents = sorted({option['folder_id'] for option in g['options'] if option['product_id'] in active and option.get('file_id') == wrapper['file_id'] and option.get('folder_id')})
        check('Separately labelled canonical parent comparison is exact: ' + oid, wrapper['canonical_option_parent_ids'] == expected_canonical_parents and wrapper['actual_parent_matches_canonical_option_parent'] is (observed['folder_id'] in expected_canonical_parents if expected_canonical_parents else None))
findings = read(OUT / 'parent-flag-findings.json')
check('All fourteen reported false mismatch flags corrected to unknown plus true canonical comparison', len(findings['rows']) == 14 and all(unique_records[x['option_id']]['current_reference']['actual_parent_matches_saved_parent'] is None and unique_records[x['option_id']]['current_reference']['saved_parent_comparison_state'] == 'UNKNOWN_SAVED_PARENT_NOT_ENCODED' and unique_records[x['option_id']]['current_reference']['actual_parent_matches_canonical_option_parent'] is True for x in findings['rows']))


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
check('Same corrected final seal and canonical inputs at end', sha(H / 'sealed-handoff.json') == '39d08659707d6ad99010e64b3503caf6bcb07d330e067cafad1109143bdc7d4f' and all(sha(path) == expected for path, expected in j['baseline_protected_files'].items()))
result = {'status': 'PASS' if all(x['pass'] for x in checks) else 'FAIL', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'checks_passed': sum(x['pass'] for x in checks), 'checks_total': len(checks), 'checks': checks,
    'source_seal_sha256': sha(H / 'sealed-handoff.json'), 'source_report_sha256': sha(H / 'local-platform-crosswalk.json'),
    'counts': j['counts'], 'scope': 'Final serialized local crosswalk and exact original CSV/source proof only. Complete field objects and selected stable IDs/parents are unchanged. Saved navigation comes from the explicit current asset map; fresh scoped records equal the independently sealed6360-file census. Historical source-edge URL strings may differ after agreed folder changes; those original canonical records remain unchanged. No new gallery visual review, live platform claim, network call, alias or canonical write.'}
(OUT / 'readback.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
(OUT / 'sealed-handoff.json').write_text(json.dumps({'status': result['status'], 'files': {n: sha(OUT / n) for n in ['qa.py', 'readback.json']}}, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'checks_passed': result['checks_passed'], 'checks_total': len(checks), 'readback_sha256': sha(OUT / 'readback.json'), 'seal_sha256': sha(OUT / 'sealed-handoff.json')}))
for check_ in [x for x in checks if not x['pass']][:10]:
    print('FAIL', check_)
raise SystemExit(0 if result['status'] == 'PASS' else 1)
