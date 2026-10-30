"""Independent artifact readback against raw CSV and frozen catalogue."""
import csv
import hashlib
import html
import itertools
import json
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CSV = Path('/Users/tprice/Library/Application Support/BoldstoneLocal/cache/squarespace-admin-export-20261024T005645Z/products_Oct-24_01-55-19AM.csv')
BASE = ROOT / 'components/reconciliation/draft-completion-and-water-reference-master-2026-10-24/canonical-master-register.json'
DATA = HERE / 'source-readback-extension.json'
data = json.loads(DATA.read_text())
base = json.loads(BASE.read_text())
options = {o['product_id']: o for o in base['options']}
checks = []


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name, passed, detail=None):
    checks.append({'name': name, 'passed': bool(passed), 'detail': detail})


source_integrity = [{'path': x['path'], 'expected': x['sha256'], 'observed': digest(Path(x['path']))} for x in data['sources']]
check('All five frozen source hashes independently match', len(source_integrity) == 5 and all(x['expected'] == x['observed'] for x in source_integrity))
check('Raw CSV pinned to acquired native export', digest(CSV) == 'cdce1939100db77c78a818a99e4081712837b9aca21602b095a6055a40c7fbbf')
check('Original download still byte-identical to private retained CSV', digest(Path('/Users/tprice/Downloads/products_Oct-24_01-55-19AM.csv')) == digest(CSV))
check('Frozen catalogue hash retained while current writer may publish elsewhere', digest(BASE) == '08e5cb133e9075a8b4a3f41149ad57060198556f124d9573f2e6f3ec919e6933')

rows = {}
headers = {}
product = None
with CSV.open(encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    assert len(set(reader.fieldnames)) == len(reader.fieldnames)
    assert not any(x.lower() in ['currency', 'weight unit', 'length unit'] for x in reader.fieldnames)
    record = 0
    while True:
        start = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        record += 1
        explicit = row['Product ID [Non Editable]']
        if explicit:
            product = explicit
            headers[product] = (row, record)
        assert product and row['Variant ID [Non Editable]'] not in rows
        rows[row['Variant ID [Non Editable]']] = {'raw': row, 'product': product,
            'source': {'data_record_1based': record, 'csv_record_including_header_1based': record + 1,
                       'physical_line_start': start, 'physical_line_end': reader.line_num},
            'header_record': headers[product][1]}
check('Direct raw source independently gives208 physical products and376 unique variants', len(headers) == 208 and len(rows) == 376 and {h[0]['Product Type [Non Editable]'] for h in headers.values()} == {'PHYSICAL'})


def raw_options(row):
    return {row[f'Option Name {i}']: row[f'Option Value {i}'] for i in range(1, 7) if row[f'Option Name {i}']}


tuples = [r['current_native_tuple'] for c in data['remaining_overlap_readbacks'] for r in c['current_source_entries']]
tuples += [r['current_native_tuple'] for r in data['existing_copy_target_readbacks']]
tuples += [r['current_native_tuple'] for r in data['wall_circle_source_readback']['rows']]
errors = []
for t in tuples:
    source = rows[t['native_variant_id']]
    raw = source['raw']
    product_header = headers[source['product']][0]
    expected = {
        'native_product_id': source['product'], 'sku': raw['SKU'], 'named_options': raw_options(raw),
        'price_raw': raw['Price'], 'sale_price_raw': raw['Sale Price'], 'on_sale_raw': raw['On Sale'],
        'stock_setting_raw': raw['Stock'], 'visible_product_setting_raw': product_header['Visible'],
        'dimensions_and_weight_raw': {k: raw[k] for k in ['Length', 'Width', 'Height', 'Weight']},
        'source': source['source'], 'product_header_record_1based': source['header_record'],
    }
    for key, value in expected.items():
        if t[key] != value:
            errors.append({'variant': t['native_variant_id'], 'field': key})
check('All152 tuple occurrences independently match exact raw fields and product header scope', len(tuples) == 152 and not errors, errors)
check('151 unique selected variants across8 native products', len({t['native_variant_id'] for t in tuples}) == 151 and len({t['native_product_id'] for t in tuples}) == 8)
check('No tuple converts raw units, certifies physical stock or assigns fresh variant images', all(t['currency_or_measurement_unit_columns_present'] is False and t['physical_stock_or_specifications_verified'] is False and t['per_variant_image_assignment_verified'] is False for t in tuples))
product_errors = []
for p in data['native_product_headers']:
    raw, record = headers[p['native_product_id']]
    if not (p['source_header_record'] == rows[raw['Variant ID [Non Editable]']]['source'] and
            p['title_raw'] == raw['Title'] and p['description_html_raw'] == raw['Description'] and
            p['product_page_raw'] == raw['Product Page'] and p['product_url_raw'] == raw['Product URL'] and
            p['visible_setting_raw'] == raw['Visible'] and
            p['hosted_image_urls_raw_sha256'] == hashlib.sha256(raw['Hosted Image URLs'].encode()).hexdigest()):
        product_errors.append(p['native_product_id'])
check('Eight selected product headers retain raw description, identity, visibility and image-reference hash', len(data['native_product_headers']) == 8 and not product_errors, product_errors)

copies = data['existing_copy_target_readbacks']
old_copies = {x['option_id']: x for x in base['current_existing_listing_copy_projections']['entries']}
check('Exact four existing target option IDs retained', {x['option_reference']['product_id'] for x in copies} == set(old_copies))
check('Copy targets retain all24 full working field objects exactly', all(x['current_working_fields_at_frozen_base'] == options[x['option_reference']['product_id']]['master_fields'] and len(x['current_working_fields_at_frozen_base']) == 6 for x in copies))
check('Dated copy tuples and historical action IDs preserved', all(x['dated_native_tuple_preserved'] == old_copies[x['option_reference']['product_id']]['dated_native_tuple'] and x['historical_action_id'] == old_copies[x['option_reference']['product_id']]['historical_action_id'] for x in copies))
check('No target becomes executable, authorized or exact physical configuration matched', all(x['executable_now'] is False and x['platform_mutation_authorized'] is False and x['exact_six_field_configuration_match_verified'] is False for x in copies))
cases = {x['case_id']: x for x in data['remaining_overlap_readbacks']}
check('Exactly the two previously unsealed overlap cases reviewed', set(cases) == {'VERDIGRIS-VERSIONS', 'MOON-WATER-OVERLAP'})
verd = {x['offer_ref']: rows[x['current_native_tuple']['native_variant_id']]['raw'] for x in cases['VERDIGRIS-VERSIONS']['current_source_entries']}
check('Verdigris SOLD/Unlimited conflict still supported by current original description', 'SOLD' in verd['O038']['Description'] and verd['O038']['Stock'] == 'Unlimited' and verd['O004']['Price'] == '45.00' and verd['O038']['Price'] == '250.00')
moon = {x['offer_ref']: rows[x['current_native_tuple']['native_variant_id']]['raw'] for x in cases['MOON-WATER-OVERLAP']['current_source_entries']}
check('Moonwater and Concave nominal identity conflict remains in exact current records', moon['O015']['Title'] == 'Concave Moon wall sculpture' and moon['O015']['SKU'] == 'CM-1-50.50' and moon['O059']['Title'] == 'Moonwater wall sculpture' and moon['O059']['SKU'] == 'MWTR-1-50')
check('Overlap working records unchanged with dated visual scope retained', all(x['current_working_field_objects_at_frozen_base'] == {r['product_id']: options[r['product_id']]['master_fields'] for r in x['option_references']} and x['prior_visual_conclusion_is_dated_not_reperformed'] is True and x['no_new_alias_identity_or_sale_unit_decision'] is True for x in cases.values()))

circle = data['wall_circle_source_readback']
circle_rows = [x['current_native_tuple'] for x in circle['rows']]
old_circle = {x['variant_id']: x for x in base['wall_circle_native_options']}
check('Wall Circle exact144 variant IDs retained without extras', {t['native_variant_id'] for t in circle_rows} == set(old_circle) and len(circle_rows) == 144)
check('Wall Circle SKU, option-name mapping and raw price match frozen144 variants', all(t['sku'] == old_circle[t['native_variant_id']]['sku'] and t['named_options'] == old_circle[t['native_variant_id']]['attributes'] and t['price_raw'] == old_circle[t['native_variant_id']]['price']['value'] for t in circle_rows))
axes = {key: {t['named_options'][key] for t in circle_rows} for key in ['Pattern', 'Lighting', 'Diameter Size']}
actual = Counter((t['named_options']['Pattern'], t['named_options']['Lighting'], t['named_options']['Diameter Size']) for t in circle_rows)
check('144 combinations are unique complete18x2x4 source option matrix', [len(v) for v in axes.values()] == [18, 2, 4] and actual == Counter(itertools.product(*axes.values())))
conditional_old = {x['product_id']: x for x in base['current_listing_resolution_details']['entries'] if x.get('conditional_native_tuple')}
cond = circle['conditional_existing_assignments']
check('Four prior conditional assignments retain exact IDs/SKUs/options/price without upgrading physical binding', len(cond) == 4 and {x['option_reference']['product_id'] for x in cond} == set(conditional_old) and all(x['current_native_tuple']['native_variant_id'] == conditional_old[x['option_reference']['product_id']]['conditional_native_tuple']['native_variant_id'] and x['conditional_visual_attribution_retained'] is True and x['image_size_lighting_or_physical_binding_newly_verified'] is False for x in cond))
custom_old = {x['product_id']: x['source_resolution_disposition'] for x in base['current_listing_resolution_details']['entries'] if x.get('custom_unlisted_pattern_draft')}
custom = circle['custom_scopes_retained']
check('Three custom/unlisted visual scopes retain exact prior dispositions', len(custom) == 3 and {x['option_reference']['product_id']: x['source_resolution_disposition_retained'] for x in custom} == custom_old and all(x['no_new_named_pattern_or_native_absence_claim'] is True for x in custom))
check('No new identity/design count, live read or physical/image review claimed', data['counts']['new_catalogue_identity_matches'] == 0 and data['counts']['platform_or_native_changes'] == 0 and data['fresh_live_ui_or_api_reads_this_extension'] == 0 and data['fresh_image_or_physical_review_performed'] is False and circle['new_sculpture_or_design_count_increment'] == 0)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls += [v for k, v in attrs if k == 'href']


page = (HERE / 'review.html').read_text()
parser = Links()
parser.feed(page)
refs = [r for c in cases.values() for r in c['option_references']]
refs += [x['option_reference'] for x in copies + cond + custom]
expected_urls = {r[k] for r in refs for k in ['image_url', 'folder_url']}
check('Every reviewed option has unchanged image and containing-folder links in report', len({r['product_id'] for r in refs}) == 13 and expected_urls <= set(parser.urls) and all(all(r[k] == options[r['product_id']][k] for k in ['name', 'image_url', 'folder_url', 'file_id', 'folder_id']) for r in refs))
check('Report includes every144 variant ID and SKU', all(html.escape(t['native_variant_id']) in page and html.escape(t['sku']) in page for t in circle_rows))

result = {
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL',
    'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks),
    'payload_sha256': digest(DATA), 'review_html_sha256': digest(HERE / 'review.html'),
    'source_integrity': source_integrity, 'checks': checks,
    'scope': 'Independent raw CSV and frozen-master readback only. No fresh UI, API, binary, physical, workbook-cell or visual-render verification.',
}
with (HERE / 'source-readback-validation-001.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': result['checks_total'], 'failed': [x for x in checks if not x['passed']]}))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
