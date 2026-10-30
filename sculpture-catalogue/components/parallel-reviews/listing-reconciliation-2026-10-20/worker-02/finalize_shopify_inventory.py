from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import csv
import io
import hashlib
import json
import plistlib
import re
import subprocess
from urllib.parse import urlparse

W = Path(__file__).resolve().parent
NOW = datetime.now(timezone.utc).isoformat()


def read(name):
    return json.loads((W / name).read_text())


def write(name, value):
    (W / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


I = read('shopify_inventory.json')
P = read('shopify_products.json')
V = read('shopify_variants.json')
N = read('shopify_native_rows.json')
R = read('source_receipts.json')
if 'historical_older_source_original_bytes_available_locally' in R['completeness']:
    R['completeness']['historical_older_source_original_bytes_recovered_in_this_audit'] = R['completeness'].pop('historical_older_source_original_bytes_available_locally')
    write('source_receipts.json', R)
H = read('shopify_historical_assertions.json')
SOURCE = Path(next(s for s in R['sources'] if s['source_id'] == 'SH_NATIVE_CSV_S09')['path'])
TABLE_PATH = Path(next(s for s in R['sources'] if s['source_id'] == 'PRESERVED_SOURCE_TABLES')['path'])
TABLES = json.loads(TABLE_PATH.read_text())
reader = csv.DictReader(io.StringIO(SOURCE.read_text(encoding='utf-8-sig'), newline=''))
native_headers = reader.fieldnames
native_rows = list(reader)

# These controls use direct exported fields and the previously preserved wall table.
# They do not infer current listings from the catalogue graph or source-file age.
assert len(P) == sum(bool(r['Title']) for r in native_rows) == 136
assert len(V) == sum(bool(r['Option1 Value']) for r in native_rows) == 160
assert len(N) == len(native_rows) == 416
assert all(n['raw'] == r for n, r in zip(N, native_rows))
assert len({p['handle'] for p in P}) == len(P)
assert len({v['variant_key'] for v in V}) == len(V)
assert not any(k in native_headers for k in ['ID', 'Product ID', 'Variant ID', 'Variant Inventory Qty'])
assert all(p['numeric_product_id'] is None and p['product_url'] is None for p in P)
assert all(v['numeric_variant_id'] is None and v['inventory_quantity'] is None for v in V)
assert Counter(r['role'] for r in N) == {'PRODUCT_HEADER_AND_VARIANT': 136, 'VARIANT_CONTINUATION': 24, 'MEDIA_ONLY_CONTINUATION': 256}
assert all(n['role'] != 'MEDIA_ONLY_CONTINUATION' for n in N if n['source_row']['logical_row_including_header'] in {v['source_row']['logical_row_including_header'] for v in V})


def compare(field, value):
    value = '' if value is None else str(value)
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    if field in ['Vendor', 'Image Alt Text']:
        return value.strip()
    if field in ['Published', 'Variant Requires Shipping', 'Variant Taxable', 'Gift Card',
                 'Google Shopping / Custom Product', 'Google: Custom Product (product.metafields.mm-google-shopping.custom_product)'] or field.startswith('Included / '):
        return {'1': 'true', '0': 'false'}.get(value.casefold(), value.casefold())
    if field in ['Variant Grams', 'Variant Price', 'Variant Compare At Price', 'Image Position', 'Cost per item'] or field.startswith(('Price / ', 'Compare At Price / ')):
        if value:
            try:
                return str(Decimal(value).normalize())
            except InvalidOperation:
                pass
    return value


WALL_CHECKS = []
MISMATCHES = []
for row in TABLES['SH Source Rows']:
    n = int(row['CSV record'])
    raw = native_rows[n - 2]
    assert raw['Handle'] == row['Handle']
    changed = [k for k in native_headers if compare(k, raw[k]) != compare(k, row.get(k, ''))]
    WALL_CHECKS.append({'preserved_table_row': row['_row'], 'native_logical_row': n,
                        'handle': raw['Handle'], 'fields_compared': len(native_headers),
                        'equivalent': not changed})
    for k in changed:
        MISMATCHES.append({'native_logical_row': n, 'field': k, 'native_raw': raw[k], 'preserved_raw': row.get(k, '')})
write('preserved_wall_crosscheck.json', {
    'schema': 'boldstone.shopify-preserved-wall-crosscheck.v1',
    'preserved_source_path': str(TABLE_PATH), 'native_source_path': str(SOURCE),
    'rows_compared': len(WALL_CHECKS), 'native_fields_per_row': len(native_headers),
    'row_checks': WALL_CHECKS, 'non_equivalent_fields': MISMATCHES,
    'comparison_rule': 'Raw values retained. Numeric representation, Vendor/Image Alt Text edge whitespace, explicit boolean columns (1/0 versus true/false) and line-ending differences do not change semantic equivalence.',
})

HOSTS = Counter()
for r in native_rows:
    for value in r.values():
        for u in re.findall(r'https?://[^\s<>"\']+', value):
            if urlparse(u).hostname:
                HOSTS[urlparse(u).hostname] += 1
ORIGINS = []
for source in R['sources'][:3]:
    p = Path(source['path'])
    result = subprocess.run(['/usr/bin/xattr', '-px', 'com.apple.metadata:kMDItemWhereFroms', str(p)], capture_output=True)
    safe = []
    try:
        urls = plistlib.loads(bytes.fromhex(result.stdout.decode())) if result.returncode == 0 else []
        for url in urls:
            if isinstance(url, str):
                host = urlparse(url).hostname
                safe.append({'host': host,
                             'private_export_storage': host == 'shopify-private-shop-assets.storage.googleapis.com',
                             'query_present_but_not_retained': bool(urlparse(url).query),
                             'path_not_retained': True})
        state = 'READ_AND_SANITIZED' if safe else 'NOT_PRESENT'
    except (ValueError, plistlib.InvalidFileException):
        state = 'UNAVAILABLE_OR_UNPARSEABLE'
    ORIGINS.append({'source_id': source['source_id'], 'origin_metadata_state': state, 'sanitized_hosts_only': safe})

DISCOVERY = {
    'schema': 'boldstone.shopify-store-domain-discovery.v1',
    'observed_utc': NOW,
    'source_native_url_host_counts': dict(HOSTS),
    'local_download_origin_metadata': ORIGINS,
    'local_searches': [
        {'scope': 'Pre-existing /Users/tprice/Documents/boldstone JSON/Markdown/text/CSV/HTML source records before this audit was authored, excluding dependencies/credentials/secrets',
         'query': 'myshopify.com or admin.shopify.com/store/', 'matching_paths': []},
        {'scope': 'BoldstoneLocal, BoldstoneImageConsistency and BoldstoneCatalogue CSV/text caches',
         'query': '^Handle,Title,', 'matching_native_export_paths': []},
        {'scope': 'Native CSV/XLSX product fields and sanitized local download origins',
         'query': 'A storefront host or store-specific admin origin', 'evidenced_storefront_domains': []},
    ],
    'evidenced_shopify_storefront_domain': None,
    'public_inventory_endpoint': None,
    'fresh_public_inventory_attempt_state': 'NOT_ATTEMPTED_NO_EVIDENCED_STOREFRONT_DOMAIN',
    'reason': 'The native source URLs identify Shopify CDN media. Download metadata identifies private Shopify export storage, Dropbox and a Google Sheets workbook download. None identifies the store domain. A CDN store-path segment or public business name is not used to guess an account identifier.',
    'authenticated_inventory_state': 'SHOPIFY_PLUGIN_NOT_CONNECTED_PARENT_REPORTED; NO_AUTHENTICATED_EXPORT_IN_THIS_LANE',
    'future_public_scope_limit': 'A public storefront inventory would not establish private drafts or complete admin inventory.',
    'parent_reported_fake_adapter_tests_passed_this_task': 74,
    'live_sandbox_tests_run_by_this_worker': False,
    'remote_calls': 0, 'signed_download_queries_retained': False,
    'credentials_or_private_export_downloads_requested': False,
}
write('store_domain_discovery.json', DISCOVERY)

WALL = [p for p in P if p['in_preserved_wall_subset']]
WALL_VARIANTS = [v for v in V if v['handle'] in {p['handle'] for p in WALL}]
SALE = Counter()
for p in WALL:
    states = {x['source_sale_unit_state'] for x in p['sale_unit_evidence']['frozen_master_source_offer_refs']}
    assert len(states) == 1
    SALE[next(iter(states))] += 1
write('shopify_wall_inventory.json', {
    'schema': 'boldstone.shopify-preserved-wall-native-inventory.v1',
    'scope': 'Exactly the 38 handles retained in SH Wall Products, recovered from the full local CSV. This is a historical source subset, not a claim of complete current wall listings.',
    'counts': {'products': len(WALL), 'variant_rows': len(WALL_VARIANTS),
               'product_status_snapshot': dict(Counter(p['status_raw'] for p in WALL)),
               'preserved_sale_unit_states': dict(SALE)},
    'products': WALL, 'variants': WALL_VARIANTS,
    'current_live_presence_verified': False,
})

CASEFOLD = defaultdict(list)
for v in V:
    if v['sku_trimmed_candidate']:
        CASEFOLD[v['sku_trimmed_candidate'].casefold()].append(v['variant_key'])
COLLISIONS = read('shopify_collisions.json')
COLLISIONS['trimmed_casefold_sku_collision_candidates'] = [
    {'sku_candidate': k, 'variant_keys': vals,
     'classification': 'NORMALIZATION_CANDIDATE_ONLY_NOT_EXACT_SKU_EQUIVALENCE'}
    for k, vals in CASEFOLD.items() if len(vals) > 1]
write('shopify_collisions.json', COLLISIONS)

I['counts']['wall_sale_unit_states_preserved'] = dict(SALE)
I['counts']['historical_version_sku_relations'] = dict(Counter(h['same_handle_sku_relation'] for h in H))
I['counts']['preserved_wall_rows_crosschecked'] = len(WALL_CHECKS)
I['store_domain_discovery_file'] = str(W / 'store_domain_discovery.json')
I['wall_inventory_file'] = str(W / 'shopify_wall_inventory.json')
I['public_inventory_attempt_state'] = DISCOVERY['fresh_public_inventory_attempt_state']
I['ready_for_parent_reconciliation'] = not bool(MISMATCHES)
I['source_snapshot_limit'] = 'All rows of the recovered local snapshot are normalized. Current admin product/draft/status/stock completeness remains unverified; no absent-live listing conclusion is made.'
SCOPE_AUDIT = read('UNLINKED_SCOPE_AUDIT.json')
BODY_AUDIT = read('NATIVE_BODY_AND_SALE_UNIT_CLAIMS.json')
assert len(SCOPE_AUDIT['products']) == 98 and len(BODY_AUDIT['products']) == 38
assert {p['handle'] for p in P} == {p['handle'] for p in SCOPE_AUDIT['products']} | {p['handle'] for p in BODY_AUDIT['products']}
assert not ({p['handle'] for p in SCOPE_AUDIT['products']} & {p['handle'] for p in BODY_AUDIT['products']})
assert all(c['native_equals_retained_body_after_html_whitespace_normalization'] for c in BODY_AUDIT['products'])
I['unlinked_scope_audit_file'] = str(W / 'UNLINKED_SCOPE_AUDIT.json')
I['native_body_and_sale_unit_claims_file'] = str(W / 'NATIVE_BODY_AND_SALE_UNIT_CLAIMS.json')
I['counts']['outside_wall_source_scope_dispositions'] = SCOPE_AUDIT['counts']['scope_dispositions']
I['counts']['additional_unlinked_physical_sculpture_candidates'] = SCOPE_AUDIT['counts']['plausible_unlinked_physical_sculpture_candidates']
I['counts']['native_wall_bodies_matching_retained_historical_descriptions'] = 38
write('shopify_inventory.json', I)

assert not MISMATCHES, 'Preserved wall subset differs from the recovered native dataset.'
assert len(WALL) == 38 and len(WALL_CHECKS) == 117
assert SALE == {'Sale component': 16, 'Sale arrangement components': 21, 'Photographed triptych; blank description/SKU': 1}
assert not COLLISIONS['trimmed_casefold_sku_collision_candidates']
assert len(H) == 9 and Counter(h['same_handle_sku_relation'] for h in H) == {'DIFFERENT_NONEMPTY_SKU_HISTORICAL_CANDIDATE_ONLY': 5, 'SAME_NONEMPTY_SKU_SOURCE_VERSION': 1, 'BLANK_HISTORICAL_SKU_NO_EXACT_MATCH': 3}
STABILITY = []
for s in R['sources']:
    h = hashlib.sha256(Path(s['path']).read_bytes()).hexdigest()
    STABILITY.append({'source_id': s['source_id'], 'sha256': h, 'unchanged': h == s['sha256']})
assert all(s['unchanged'] for s in STABILITY)
FILES = ['shopify_inventory.json', 'inventory_schema.json', 'shopify_products.json',
         'shopify_variants.json', 'shopify_media_rows.json', 'shopify_native_rows.json',
         'shopify_historical_assertions.json', 'shopify_collisions.json', 'source_comparison.json',
         'source_receipts.json', 'store_domain_discovery.json', 'shopify_wall_inventory.json',
         'preserved_wall_crosscheck.json', 'UNLINKED_SCOPE_AUDIT.json',
         'NATIVE_BODY_AND_SALE_UNIT_CLAIMS.json']
write('VALIDATION.json', {
    'schema': 'boldstone.shopify-inventory-validation.v1', 'validated_utc': NOW,
    'result': 'PASS_COMPLETE_LOCAL_FILE_PARSE_WITH_LIVE_ACCOUNT_LIMITS',
    'native_products': 136, 'native_variants': 160, 'media_only_continuations': 256,
    'wall_products': 38, 'wall_variants': 38,
    'preserved_wall_rows_checked_against_native': 117,
    'preserved_wall_native_fields_checked': 117 * 95,
    'non_equivalent_preserved_wall_fields': 0,
    'source_stability': STABILITY,
    'checks': [
        'All 416 native rows retained verbatim with logical and physical CSV locators.',
        '136 nonblank Title headers independently counted as source products.',
        '160 nonblank Option1 Value rows independently counted as variants; 256 media-only rows excluded.',
        'All 117 previously preserved wall rows match all 95 native columns after explicitly documented representation normalization.',
        'Both CSV snapshots and dated XLSX have equivalent listing data; source raw differences retained.',
        'No duplicate header handle, repeated nonempty SKU, casefold/trim SKU collision or duplicate option tuple found.',
        'All nine historical source assertions kept separate from native product/variant inventory.',
        'All98 outside-wall source products classified from explicit native body/type evidence; all136 headers accounted for without assuming38 is exhaustive.',
        'All38 native wall bodies compared separately with frozen historical descriptions; literal sale/size claims and two typography issues retained.',
        'Numeric product/variant IDs, current quantities, store domain and live draft completeness not invented.',
        'No remote calls, platform or Dropbox writes, or shared-master changes.',
    ],
    'outputs': [{'path': str(W / f), 'sha256': hashlib.sha256((W / f).read_bytes()).hexdigest()} for f in FILES],
})
print(json.dumps({'result': 'PASS', 'counts': I['counts'],
                  'main_inventory': str(W / 'shopify_inventory.json'),
                  'main_inventory_sha256': hashlib.sha256((W / 'shopify_inventory.json').read_bytes()).hexdigest()}, indent=2))
