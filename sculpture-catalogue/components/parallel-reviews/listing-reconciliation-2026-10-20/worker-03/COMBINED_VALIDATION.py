#!/usr/bin/env python3
"""Independent readback of the frozen listing package and bound native source rows."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv
import hashlib
import json

B = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
PAYLOAD_NAMES = ['LISTING_RECONCILIATION.json', 'MATCH_EVIDENCE.json', 'NATIVE_SOURCE_LINKS.json', 'LISTING_ISSUES.json', 'SET_ONLY_AND_MULTIPART_OFFERS.json', 'OPTION_LISTING_REVIEW.csv', 'RECONCILIATION_COUNTS.json', 'ACCESS_OBSERVATIONS.json']
checks, issues, bound_sources, raw_readbacks = [], [], [], []
cache = {}


def read(path):
    path = str(path)
    if path not in cache:
        cache[path] = json.loads(Path(path).read_text())
    return cache[path]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(ok, label, detail=None):
    checks.append({'check': label, 'status': 'PASS' if ok else 'FAIL', **({'details': detail} if detail is not None else {})})
    if not ok:
        issues.append(label)


def bind(path, digest, role):
    actual = sha(path)
    bound_sources.append({'path': str(path), 'expected_sha256': digest, 'actual_sha256': actual, 'role': role, 'status': 'MATCH' if actual == digest else 'MISMATCH'})
    check(actual == digest, 'Bound source bytes: ' + str(path))


def pointer(obj, path):
    for token in path.lstrip('/').split('/') if path else []:
        token = token.replace('~1', '/').replace('~0', '~')
        obj = obj[int(token)] if isinstance(obj, list) else obj[token]
    return obj


start_hashes = {n: sha(B / n) for n in PAYLOAD_NAMES}
L, E, N, I, SETS = [read(B / n) for n in PAYLOAD_NAMES[:5]]
G = read(B / 'inputs/master-register.json')
SOURCE = read(OUT / 'source_mapping_evidence.json')
SS = read(B / 'worker-01/SQUARESPACE_SOURCE_INVENTORY.json')
SS_MANIFEST = read(B / 'worker-01/SOURCE_MANIFEST.json')
SS_SEAL = read(B / 'worker-01/SEAL.json')
SH = read(B / 'worker-02/shopify_inventory.json')
SH_PRODUCTS = read(B / 'worker-02/shopify_products.json')
SH_VARIANTS = read(B / 'worker-02/shopify_variants.json')
SH_RECEIPTS = read(B / 'worker-02/source_receipts.json')
expected_master = '30ff291d6b6fe0aad3a2bc39e121de4ef838c09afceb5f7ab11c78ea7fa71e2c'
bind(B / 'inputs/master-register.json', expected_master, 'Frozen184-option catalogue')
bind(OUT / 'source_mapping_evidence.json', 'ebedffff69a422e0493d6e22e5fbfd65447087f64c6ce00d4d389bbd2601d169', 'Sealed184source-association evidence')
for name, row in SS_SEAL['outputs'].items():
    digest = row['sha256'] if isinstance(row, dict) else row
    bind(B / 'worker-01' / name, digest, 'Sealed Squarespace inventory output')
for row in SS_MANIFEST['raw_http_responses']:
    bind(row['body_path'], row['body_sha256'], 'Saved public response body')
    bind(row['receipt_path'], row['receipt_sha256'], 'Saved HTTP receipt')
for row in SS_MANIFEST['cached_sources'].values():
    bind(row['path'], row['sha256'], 'Preserved local Squarespace source')
for row in SH_RECEIPTS['sources']:
    bind(row['path'], row['sha256'], 'Preserved Shopify source or source context')

options = {v['product_id']: v for v in L['options']}
original = {v['product_id']: v for v in G['options']}
edges = {v['edge_id']: v for v in E['edges']}
source_edges = {v['edge_id']: v for v in SOURCE['candidate_edges']}
native = {v['offer_ref']: v for v in N['offers']}
source_offers = {v['offer_ref']: v for v in G['source_offer_edges']}
ss_products = {v['native_product_id']: v for v in SS['products']}
sh_products = {v['handle']: v for v in SH_PRODUCTS}
sh_variants = {v['variant_key']: v for v in SH_VARIANTS}
check(len(L['options']) == len(options) == 184 and set(options) == set(original), 'Exact184-option coverage without duplicate IDs')
check(len(N['offers']) == len(native) == 81 and set(native) == set(source_offers), 'Exact81-source-offer coverage without duplicate IDs')
check(len(E['edges']) == len(edges) == 262 and set(edges) == set(source_edges), 'All262 scoped source edges faithfully retained')
check(all(x['input_master_sha256'] == expected_master for x in [L]) and E['master_sha256'] == N['master_sha256'] == expected_master, 'All core payloads bind the same frozen master')
check(Counter(v['overall_disposition'] for v in L['options']) == Counter(L['counts']['overall_option_dispositions']), 'Summary dispositions recomputed from184records')
check(sum(v['individual_source_record_supported'] for v in L['options']) == L['counts']['source_supported_individual_design_options'] == 45 and sum(v['overall_disposition'] == 'INDIVIDUAL_SOURCE_RECORD_LINKED' for v in L['options']) == L['counts']['nonconflicting_source_supported_individual_record_links'] == 41 and L['counts']['options_without_supported_individual_native_record'] == 139 and L['counts']['options_without_nonconflicting_supported_individual_native_record'] == 143, '45source-design links versus41nonconflicting source links and139/143remainders remain distinct')
check(L['counts']['existing_individual_design_records_with_configuration_conflict'] == 4 and L['counts']['exact_current_option_configuration_matches_verified'] == L['counts']['authenticated_live_exact_option_configuration_verifications'] == 0, 'Four configuration conflicts and zero exact-current configuration verifications counted separately')
for platform in ['Squarespace', 'Shopify']:
    check(Counter(v['platforms'][platform]['disposition'] for v in L['options']) == Counter(L['counts'][platform + '_option_dispositions']), platform + '184platform dispositions recomputed')
check(len(SS['products']) == 208 and sum(len(p['variants']) for p in SS['products']) == 376, 'Squarespace union208products/376preferred variants matches source inventory')
public_items = []
for row in SS_MANIFEST['raw_http_responses']:
    if Path(row['body_path']).name.startswith('collection-'):
        public_items.extend(read(row['body_path'])['items'])
check(len(public_items) == len({v['id'] for v in public_items}) == 203 and sum(len(v.get('variants', [])) for v in public_items) == 370, 'Raw public collection independently gives203unique products/370variants')
check(L['counts']['fresh_public_squarespace_source_products'] == 203 and L['counts']['fresh_public_squarespace_source_variants'] == 370 and '208' in ' '.join(L['scope_and_limits']), '203returned versus208advertised discrepancy remains explicit')
check(len(SH_PRODUCTS) == 136 and len(SH_VARIANTS) == 160 and all(v['numeric_product_id'] is None and v['numeric_variant_id'] is None for v in SH_VARIANTS), 'Shopify136products/160variants; numeric IDs absent rather than invented')
check(SH['absence_from_snapshot_is_not_live_absence'] and not SH['current_inventory_completeness_verified'] and L['counts']['shopify_live_products_verified'] == 0, 'Shopify historical snapshot is not live/admin inventory completeness')

# Read the original logical and physical CSV rows independently; no writer/builder imported.
sh_primary = next(x for x in SH_RECEIPTS['sources'] if x['source_id'] == 'SH_NATIVE_CSV_S09')
csv_rows = {}
with Path(sh_primary['path']).open(newline='', encoding='utf-8-sig') as fh:
    reader = csv.DictReader(fh)
    _ = reader.fieldnames
    prior_end = reader.line_num
    for logical, row in enumerate(reader, 2):
        csv_rows[logical] = {'row': row, 'start': prior_end + 1, 'end': reader.line_num}
        prior_end = reader.line_num
check(len(csv_rows) == 416 and len(reader.fieldnames) == 95, 'Original Shopify CSV416data rows/95columns read directly')
for v in SH_VARIANTS:
    sr = v['source_row']; raw = csv_rows[sr['logical_row_including_header']]
    check(raw['row']['Handle'] == v['handle'] and raw['row']['Variant SKU'] == v['sku_raw'] and raw['row']['Variant Price'] == v['price_raw'] and raw['row']['Variant Grams'] == v['grams_raw'], 'Shopify native row preserves handle/SKU/price/grams: ' + v['variant_key'])
    check(raw['start'] == sr['physical_line_start'] and raw['end'] == sr['physical_line_end'], 'Shopify CSV physical line locator correct: ' + v['variant_key'])
    check(all(raw['row'][f"Option{o['position']} Value"] == o['value'] for o in v['option_tuple']), 'Shopify exact option tuple values preserved: ' + v['variant_key'])

# Audit exact source product/variant joins against independent inventory values and raw pointers.
ss_link_variant_count = 0
sh_link_variant_count = 0
for offer_ref, row in native.items():
    source = source_offers[offer_ref]
    check(row['original_bom_rows'] == [m['original_bom'] for m in source['members']], 'Original BOM rows unchanged: ' + offer_ref)
    for platform in ['Squarespace', 'Shopify']:
        p = row[platform]
        check(p.get('current_authenticated_admin_inventory_verified') is not True, platform + ' does not assert admin verification: ' + offer_ref)
        if not p['record_present']:
            check(p['variants'] == [], platform + ' absent recorded link does not fabricate variants: ' + offer_ref)
            continue
        if platform == 'Squarespace':
            expected_id = source['source_offer']['sq_id']
            check(p['native_product_id'] == expected_id and expected_id in ss_products, 'Squarespace exact recorded product ID lookup: ' + offer_ref)
            product = ss_products[expected_id]
            check(p['presence_state'] == product['inventory_state'] and p['fresh_public_product_observed'] == product['fresh_public_product_observed'], 'Squarespace native freshness faithfully retained: ' + offer_ref)
            iv = {v['native_variant_id']: v for v in product['variants']}
            check({v['native_variant_id'] for v in p['variants']} == set(iv), 'Squarespace complete native variant set retained: ' + offer_ref)
            for v in p['variants']:
                sv = iv[v['native_variant_id']]; ss_link_variant_count += 1
                check(v['sku_raw'] == sv['sku'] and v['option_attributes'] == sv['option_attributes'] and v['native_price'] == sv['price'] and v['native_stock_setting'] == sv['stock_setting'] and v['raw_dimensions_and_weight'] == sv['raw_dimensions_and_weight'], 'Squarespace native variant fields faithfully reused: ' + v['native_variant_id'])
                loc = v['source_locator']; raw = pointer(read(loc['path']), loc['json_pointer'])
                if 'id' in raw:
                    check(raw['id'] == v['native_variant_id'] and raw['sku'] == v['sku_raw'] and raw.get('attributes', {}) == v['option_attributes'], 'Squarespace raw response variant ID/SKU/attributes: ' + v['native_variant_id'])
                    check(raw.get('priceMoney') == v['native_price']['price_money'] and raw.get('price') == v['native_price']['native_price_integer'], 'Squarespace raw response price money/integer preserved: ' + v['native_variant_id'])
                else:
                    rv = raw['values']
                    check(raw['parent_id'] == expected_id and raw['variant_id'] == v['native_variant_id'] and rv['SKU'] == v['sku_raw'], 'Squarespace preserved native row exact IDs/SKU: ' + v['native_variant_id'])
                raw_readbacks.append({'platform': 'Squarespace', 'offer_ref': offer_ref, 'product_id': expected_id, 'variant_id': v['native_variant_id'], 'sku': v['sku_raw'], 'path': loc['path'], 'json_pointer': loc['json_pointer'], 'raw_bytes_sha256': sha(loc['path'])})
            check(set(p['exact_source_sku_variant_ids']) == {v['native_variant_id'] for v in p['variants'] if row['source_sku'] and v['sku_raw'] == row['source_sku']}, 'Squarespace exact sourceSKU filter has no title/default fallback: ' + offer_ref)
        else:
            handle = source['source_offer']['sh_handle']
            check(p['handle'] == handle and handle in sh_products and p['numeric_product_id'] is None and p['product_url'] is None, 'Shopify recorded handle and unknown IDs/domain preserved: ' + offer_ref)
            for v in p['variants']:
                sv = sh_variants[v['variant_key']]; sh_link_variant_count += 1
                check(v['product_key'] == sv['product_key'] and v['handle'] == handle and v['sku_raw'] == sv['sku_raw'] and v['option_tuple'] == sv['option_tuple'] and v['price_raw'] == sv['price_raw'], 'Shopify exact native variant row/handle/SKU/options: ' + v['variant_key'])
                check(v['numeric_product_id'] is None and v['numeric_variant_id'] is None and v['currency'] is None and v['inventory_quantity'] is None, 'Shopify unexported IDs/currency/quantity not invented: ' + v['variant_key'])
                raw_readbacks.append({'platform': 'Shopify', 'offer_ref': offer_ref, 'variant_key': v['variant_key'], 'sku': v['sku_raw'], 'source_row': sv['source_row'], 'csv_sha256': sh_primary['sha256']})
            check(set(p['exact_source_sku_variant_keys']) == {v['variant_key'] for v in p['variants'] if row['source_sku'] and v['sku_raw'] == row['source_sku']}, 'Shopify blank SKU never exact variant match: ' + offer_ref)
check(sum(len(v['original_bom_rows']) for v in N['offers']) == 122, 'All122BOM positions preserved without component quantity inflation')

# No native family/set row becomes an individual variant merely because its source SKU exists.
positive_relationships = {'SOURCE_SUPPORTED_STANDALONE_OPTION_CANDIDATE', 'SINGLE_SOURCE_OFFER_CURRENT_VERSION_CONFLICT', 'BOUND_PHOTOGRAPHED_DESIGN_CURRENT_CONFIGURATION_CONFLICT'}
for eid, e in edges.items():
    prior = source_edges[eid]
    for key in ['relationship', 'join_basis', 'compatibility', 'media_evidence', 'special_join_limits']:
        check(e[key] == prior[key], 'Scoped source identity/configuration evidence retained: ' + eid + '/' + key)
    check(not e['exact_current_configuration_certified'] and not e['title_similarity_used'], 'No exact physical configuration or title join asserted: ' + eid)
    for platform, p in e['platform_evidence'].items():
        n = native[e['offer_ref']][platform]
        loc = p['native_source_link_evidence']
        check(loc['sha256'] == start_hashes['NATIVE_SOURCE_LINKS.json'] and pointer(N, loc['json_pointer']) == n, 'Parent native evidence locator exact: ' + eid + '/' + platform)
        if p['individual_design_variant_link_supported']:
            check(e['relationship'] in positive_relationships and p['exact_native_variant_for_recorded_source_sku'], 'Individual native assignment has supported single-design relationship: ' + eid + '/' + platform)
            exact = n['exact_source_sku_variant_ids'] if platform == 'Squarespace' else n['exact_source_sku_variant_keys']
            key = 'native_variant_id' if platform == 'Squarespace' else 'variant_key'
            check({v[key] for v in p['exact_native_variant_for_recorded_source_sku']} == set(exact), 'Individual native assignment uses exact nonblank sourceSKU set: ' + eid + '/' + platform)
        else:
            check(not p['individual_option_variant_keys'] and not p['individual_skus'], 'Unresolved/family/set edge has no individual native assignment: ' + eid + '/' + platform)

for pid, row in options.items():
    old = original[pid]
    check(set(old['master_fields']) == {'Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability'} and row['canonical_key'] == old['canonical_key'] and row['name'] == old['name'] and row['source_scopes'] == old['source_scopes'] and row['working_specifications'] == {k: v['display'] for k, v in old['master_fields'].items()}, 'Current184identity and six authoritative master_fields displays preserved: ' + pid)
    check(row['catalogue_count_increment'] == 0 and not row['exact_current_configuration_certified'], 'No option count or physical-certification increment: ' + pid)
    check(row.get('exact_current_option_configuration_match_verified') is False, 'Current option configuration match explicitly unverified: ' + pid)
    check(set(row['all_evidence_edge_ids']) == {eid for eid, e in edges.items() if e['product_id'] == pid}, 'Every option enumerates its scoped edges: ' + pid)
    for platform, p in row['platforms'].items():
        check(p.get('exact_current_option_configuration_match_verified') is False, 'Current platform-option configuration match explicitly unverified: ' + pid + '/' + platform)
        check('only' in p['absence_scope'].lower() or 'not assessed' in p['absence_scope'].lower(), 'Platform absence statement is scoped rather than global: ' + pid + '/' + platform)
        check(not p['current_authenticated_admin_inventory_verified'], 'No authenticated platform inventory assertion: ' + pid + '/' + platform)
        for assignment in p['supported_individual_native_variants']:
            check(assignment.get('exact_current_option_configuration_match_verified') is False, 'Variant record link not promoted to exact current option configuration: ' + pid + '/' + platform)
            e = edges[pid + '::' + assignment['offer_ref']]
            key = 'native_variant_id' if platform == 'Squarespace' else 'variant_key'
            allowed = e['platform_evidence'][platform]['exact_native_variant_for_recorded_source_sku']
            check(assignment['native_variant'] in allowed and e['relationship'] in positive_relationships, 'Selected option variant is a supported exact source-row join: ' + pid + '/' + platform)

# Focused independent semantic cases.
def opt(pid): return options[pid]
for pid in ['BSI-9278986A1A89', 'BSI-7CDE8362BB51']:
    check(opt(pid)['overall_disposition'] == 'SET_OR_ARRANGEMENT_ASSOCIATION_ONLY' and all(not p['supported_individual_native_variants'] for p in opt(pid)['platforms'].values()), 'Bone pair SKU not assigned to individual component: ' + pid)
check(native['O034']['Squarespace']['native_sellable_unit']['quantity_per_offered_unit_source_claim'] == 2, 'Fresh Bone detail explicitly remains two-part offered unit')
check(opt('BSI-70C7029C1DB1')['overall_disposition'] == 'EXISTING_INDIVIDUAL_DESIGN_WITH_CONFIGURATION_CONFLICT' and 'BSI-70C7029C1DB1::O015' in opt('BSI-70C7029C1DB1')['selected_evidence_edge_ids'], 'O015 photographed Moon Water Catcher stays existing-design correction candidate')
check(not opt('BSI-98376D9FF006')['individual_source_record_supported'], 'O015 Concave title not reassigned as exact MCP4 White25 listing')
check(not edges['BSI-46F6DB226213::O006']['platform_evidence']['Squarespace']['individual_design_variant_link_supported'] and not edges['BSI-8298E205204F::O006']['platform_evidence']['Squarespace']['individual_design_variant_link_supported'], 'O006 exact native SKU existence does not select an unbound finish')
wall = [x for x in L['options'] if x['canonical_key'].startswith('BC-WALL-CIRCLE|')]
check(sum(len(x['working_specifications']) for x in L['options']) == 1104, 'All1104working display fields present and compared to authoritative master_fields')
check(all(x['working_specifications']['Fixing'].startswith('Offered fixing choice: Keyhole fixing or French cleat.') and x['working_specifications']['Fixing'] == original[x['product_id']]['master_fields']['Fixing']['display'] for x in wall), 'All seven Wall Circle fixing displays retain canonical offered keyhole/French-cleat prefix and installed-detail scope')
check(len(wall) == 7 and len(native['O001']['Squarespace']['variants']) == 144 and all(not p['supported_individual_native_variants'] for x in wall for p in x['platforms'].values()), 'Wall144 native variants remain separate from seven unresolved visual aliases')
check(len({v['native_variant_id'] for v in native['O001']['Squarespace']['variants']}) == 144 and len({tuple(sorted(v['option_attributes'].items())) for v in native['O001']['Squarespace']['variants']}) == 144, 'Wall144 actual native IDs and option tuples unique, not newly numbered variants')
check(opt('BSI-818D745F1357')['overall_disposition'] == 'SET_OR_ARRANGEMENT_ASSOCIATION_ONLY' and len(native['O030']['original_bom_rows']) == 5 and not opt('BSI-818D745F1357')['platforms']['Squarespace']['supported_individual_native_variants'], 'Moonphase historical1/5→current4 preserves five-piece set without standalone member SKU')
for pid in ['BSI-DB7FBD3E1323', 'BSI-6581D83760F1', 'BSI-1E0C826D896E']:
    check(opt(pid)['overall_disposition'] == 'EXISTING_INDIVIDUAL_DESIGN_WITH_CONFIGURATION_CONFLICT' and opt(pid)['individual_source_record_supported'], 'Known design survives current size/copy conflict rather than being called missing: ' + pid)
for row in L['options']:
    if row['canonical_key'].startswith(('BC-LAVA-1|', 'BC-LAVA-2|', 'BC-LAVA-3|', 'BC-MLAVA-1|', 'BC-MLAVA-2|')):
        check(row['non_offer_relations'] == SOURCE['option_associations'][row['product_id']]['non_offer_relations'] and not row['individual_source_record_supported'], 'Luciano/Lava scoped references preserved without listing/finish SKU promotion: ' + row['product_id'])

# Cross-platform identifiers and duplicate/overlap findings remain evidence issues, not edits.
types = Counter(v['issue_type'] for v in I['issues'])
check(types == Counter(I['counts_by_type']), 'Issue type counts recomputed')
check(any('MULTIPLE_PUBLIC' in t for t in types) and any('HISTORICAL' in t and 'SKU' in t for t in types), 'Explicit multi-public overlap and historical changed-SKU issue classes included')
check(any(v['issue_type'] == 'CONFIRMED_NATIVE_SKU_COLLISION_DUPLICATE_LISTING_CANDIDATE' for v in I['issues']), 'Confirmed within-platform SKU collision queued without deletion or cross-platform mirror merger')
check(I['platform_creates_updates_deletes_performed'] == 0 and I['shared_writes'] == 0 and L['remote_writes'] == 0 and L['shared_master_writes'] == 0 and L['dropbox_calls'] == 0, 'No platform/shared mutations represented')
set_ids = {ref for ref, e in source_offers.items() if e['source_offer']['sale_unit_state'] == 'Sale arrangement components'}
check({v['offer_ref'] for v in SETS['offers']} == set_ids and len(set_ids) == 25, 'All25retained source multipart/arrangement offers separately enumerated')
check(set(SETS['option_ids_with_only_set_or_arrangement_association']) == {v['product_id'] for v in L['options'] if v['overall_disposition'] == 'SET_OR_ARRANGEMENT_ASSOCIATION_ONLY'}, 'All33set-only option IDs exactly agree with184option dispositions')
echo = next(v for v in SETS['offers'] if v['offer_ref'] == 'O072')
check(echo['native_description_sale_unit']['quantity_per_offered_unit_source_claim'] is None, 'O072 combined width not divided to fabricate marketed quantity')
authority = read(B / 'OWNER_INSTRUCTION.json')
check(L['owner_instruction'] == authority and authority['line'] == 23854, 'Combined payload binds the exact current listing-reconciliation owner instruction')
with Path(authority['transcript']).open() as fh:
    for line_number, line in enumerate(fh, 1):
        if line_number == authority['line']:
            event = json.loads(line); payload = event['payload']; text = ''.join(v.get('text', '') for v in payload['content'])
            check(payload['role'] == 'user' and text == authority['text'] and hashlib.sha256(text.encode()).hexdigest() == authority['text_sha256'] and hashlib.sha256(line.encode()).hexdigest() == authority['raw_line_sha256'], 'Exact owner transcript text and raw line digest verified locally')
            break

# CSV is a faithful184row review view, with no spreadsheet edits or recalculation.
with (B / 'OPTION_LISTING_REVIEW.csv').open(newline='', encoding='utf-8-sig') as fh:
    table = list(csv.DictReader(fh))
check(len(table) == len({r['product_id'] for r in table}) == 184 and {r['product_id'] for r in table} == set(options), 'CSV exactly covers184options')
for r in table:
    o = options[r['product_id']]
    check(r['canonical_key'] == o['canonical_key'] and r['overall_disposition'] == o['overall_disposition'] and r['Squarespace_disposition'] == o['platforms']['Squarespace']['disposition'] and r['Shopify_disposition'] == o['platforms']['Shopify']['disposition'], 'CSV scope/dispositions match JSON: ' + r['product_id'])
    for platform, key in [('Squarespace', 'native_variant_id'), ('Shopify', 'variant_key')]:
        column = platform + ('_individual_variant_ids' if platform == 'Squarespace' else '_individual_variant_keys')
        ids = {a['native_variant'][key] for a in o['platforms'][platform]['supported_individual_native_variants']}
        cell = r[column]
        check(all(v in cell for v in ids) and (bool(cell) == bool(ids)), 'CSV selected variant keys faithfully reflect scoped JSON: ' + r['product_id'] + '/' + platform)
check(all(sha(B / name) == digest for name, digest in start_hashes.items()), 'All frozen parent payloads unchanged during audit')

report = {
    'schema': 'boldstone.combined184-listing-independent-validation.v1',
    'checked_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'PASS' if not issues else 'FAIL',
    'scope': 'Frozen combined local JSON/CSV and retained native evidence; no new remote survey or shared import.',
    'checks': checks, 'issues': issues,
    'counts': {'catalogue_options': len(options), 'authoritative_master_display_fields_checked': 1104, 'Wall_Circle_canonical_fixing_prefixes_checked': 7, 'source_offers': len(native), 'scoped_edges': len(edges), 'original_bom_rows': sum(len(v['original_bom_rows']) for v in N['offers']), 'source_Squarespace_variant_rows_checked': ss_link_variant_count, 'source_Shopify_variant_rows_checked': sh_link_variant_count, 'original_Shopify_variant_rows_checked': len(SH_VARIANTS), 'raw_public_products': len(public_items), 'raw_public_variants': sum(len(v.get('variants', [])) for v in public_items), 'csv_rows': len(table), 'checks': len(checks)},
    'frozen_payload_hashes': [{'path': str(B / name), 'sha256': digest, 'bytes': (B / name).stat().st_size} for name, digest in start_hashes.items()],
    'source_hash_readbacks': bound_sources,
    'raw_variant_readbacks': raw_readbacks,
    'constraints': ['Native source product/variant IDs and raw SKUs are checked, but source-supported design identity is separate from physical configuration certification.', 'Squarespace public pagination returned203products against208advertised; direct404 observations do not prove account deletion, absence of drafts or full account inventory.', 'Shopify136products/160variants are a preserved historical export, with no exported numeric IDs, evidenced store domain or live/admin completeness.', 'Set, family, gallery and historical associations do not supply standalone member SKUs;144Wall combinations remain separate from seven unresolved appearance names.', 'Configuration-conflicted existing designs remain correction/version candidates. Their source prices and dimensions do not overwrite current accepted working values.', 'Duplicate SKU collisions and public listing overlaps are review findings only; no deletion, merge or platform update is authorized by this audit.', 'This audit does not inspect or alter the master workbook; the CSV review view is checked against JSON only.', 'Only worker03 audit script/receipt files were written. Parent shared import and publication remain separate steps.'],
    'parent_builder_executed_or_imported': False, 'new_remote_reads': 0, 'remote_writes': 0, 'shared_writes': 0,
    'supersedes_provisional_readback': 'Earlier provisional display comparison used raw specifications; this final audit instead compares all1104 canonical master_fields displays and explicitly checks all seven Wall fixing prefixes.',
}
(OUT / 'COMBINED_VALIDATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'issues': issues, 'counts': report['counts'], 'report_path': str(OUT / 'COMBINED_VALIDATION.json'), 'report_sha256': sha(OUT / 'COMBINED_VALIDATION.json'), 'payload_hashes': report['frozen_payload_hashes']}, indent=2))
