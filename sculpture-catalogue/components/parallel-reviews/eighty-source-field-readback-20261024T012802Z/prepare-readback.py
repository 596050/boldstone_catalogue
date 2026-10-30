"""Read-only comparison of dated catalogue source assertions and acquired CSV."""
import csv
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'components/reconciliation/physical-audit-ledger-alignment-master-2026-10-24/canonical-master-register.json'
CSV = Path('/Users/tprice/Library/Application Support/BoldstoneLocal/cache/squarespace-admin-export-20261024T005645Z/products_Oct-24_01-55-19AM.csv')
EXPECTED_BASE = '342cbb76f5cf228e4b06c4e5243481257bf088217be0ca98e1ca2ef9a2c57c34'
EXPECTED_CSV = 'cdce1939100db77c78a818a99e4081712837b9aca21602b095a6055a40c7fbbf'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(BASE) == EXPECTED_BASE and sha(CSV) == EXPECTED_CSV

base = json.loads(BASE.read_text())
raw_records = []
headers = {}
active_product = None
with CSV.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    assert reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames))
    while True:
        start = reader.line_num + 1
        try:
            raw = next(reader)
        except StopIteration:
            break
        i = len(raw_records) + 1
        if raw['Product ID [Non Editable]']:
            active_product = raw['Product ID [Non Editable]']
            headers[active_product] = {'raw': raw, 'record': i}
        assert active_product
        raw_records.append({'product_id': active_product, 'raw': raw,
                            'source': {'data_record_1based': i, 'csv_record_including_header_1based': i + 1,
                                       'physical_line_start': start, 'physical_line_end': reader.line_num}})
assert len(headers) == 208 and len(raw_records) == 376

mapping = [('Title', 'title', 'Title'), ('Description text', 'native_description', 'Description'),
           ('Price raw', 'native_price', 'Price'), ('Visible raw', 'visible', 'Visible'),
           ('Stock setting raw', 'stock', 'Stock'), ('Weight raw', 'raw_weight', 'Weight'),
           ('Length raw', 'raw_length', 'Length'), ('Width raw', 'raw_width', 'Width'),
           ('Height raw', 'raw_height', 'Height')]
clean = lambda t: ' '.join(html.unescape(re.sub('<[^>]*>', ' ', t)).split())
entries = []
unpaired = []
for index, edge in enumerate(base['source_offer_edges']):
    old = edge['source_offer']
    if not old['sq_id']:
        unpaired.append({'offer_ref': edge['offer_ref'], 'reason': 'No Squarespace product ID in retained source; not labelled absent.'})
        continue
    matches = [r for r in raw_records if r['product_id'] == old['sq_id'] and r['raw']['SKU'] == old['sku']]
    assert len(matches) == 1, edge['offer_ref']
    selected = matches[0]
    raw, product_header = selected['raw'], headers[old['sq_id']]['raw']
    fields = []
    for label, old_key, csv_key in mapping:
        current = product_header[csv_key] if csv_key in ['Title', 'Description', 'Visible'] else raw[csv_key]
        historical_value = old[old_key]
        text_field = label == 'Description text'
        left, right = (clean(historical_value), clean(current)) if text_field else (historical_value, current)
        fields.append({'field': label, 'historical_source_key': old_key, 'csv_column': csv_key,
                       'historical_value_raw': historical_value, 'current_csv_value_raw': current,
                       'comparison': 'NORMALIZED_TEXT' if text_field else 'EXACT_STRING',
                       'historical_comparison_value': left, 'current_comparison_value': right,
                       'equal': left == right})
    image_urls = product_header['Hosted Image URLs'].split()
    entries.append({
        'offer_ref': edge['offer_ref'], 'native_product_id': old['sq_id'],
        'native_variant_id': raw['Variant ID [Non Editable]'], 'sku': raw['SKU'],
        'source': selected['source'], 'product_header_data_record_1based': headers[old['sq_id']]['record'],
        'historical_source_locator': '/source_offer_edges/' + str(index) + '/source_offer',
        'historical_source_url_preserved': old['source_url'],
        'current_source_url_from_export': 'https://boldstonesculpture.com/' + product_header['Product Page'].strip('/') + '/p/' + product_header['Product URL'].strip('/'),
        'source_first_image_url': image_urls[0] if image_urls else None,
        'fields': fields, 'all_nine_compared_fields_equal': all(x['equal'] for x in fields),
        'historical_sale_unit_assertions_retained': {k: old[k] for k in ['sale_unit_state', 'native_parts', 'proposed_bom_pieces']},
        'frozen_catalogue_source_image_reference': edge.get('current_primary_reference'),
        'source_image_binding_state_retained': old['image_state'],
        'source_cautions_retained': old['cautions'],
        'no_photo_binding_identity_or_physical_upgrade': True,
    })
assert len(entries) == 80 and len(unpaired) == 1
assert all(e['all_nine_compared_fields_equal'] for e in entries)
refs = [e for e in entries if e['frozen_catalogue_source_image_reference']]
missing = [e['offer_ref'] for e in entries if not e['frozen_catalogue_source_image_reference']]
assert len(refs) == 78 and set(missing) == {'O006', 'O007'}
payload = {'schema': 'boldstone.eighty-source-field-readback.v1',
           'recorded_utc': datetime.now(timezone.utc).isoformat(),
           'status': 'PREPARED_CURRENT_NATIVE_METADATA_CORROBORATION_NOT_IMPORTED',
           'sources': [{'path': str(BASE), 'sha256': EXPECTED_BASE}, {'path': str(CSV), 'sha256': EXPECTED_CSV}],
           'counts': {'recorded_offers_with_squarespace_id': 80, 'selected_exact_id_sku_tuples': 80,
                      'compared_field_groups': 720, 'exact_string_field_groups': 640,
                      'normalized_description_text_groups': 80, 'changed_comparison_values': 0,
                      'retained_catalogue_source_image_references': 78,
                      'retained_unresolved_source_image_bindings': 2, 'unpaired_non_squarespace_offer': 1},
           'entries': entries, 'unpaired_source_offers': unpaired,
           'unresolved_source_image_offer_refs': missing,
           'scope': 'Current accessible Physical product CSV corroborates nine historical source values per exact product-ID/SKU tuple. Description comparisons normalize HTML entities/tags/whitespace; raw HTML remains distinct. No per-variant images, all-option variant matrices, physical stock or actual manufactured configurations are certified.',
           'interpretation': 'Unchanged source metadata does not resolve existing conflicts with accepted working values or corrected catalogue names. Raw price agreement does not adopt source prices; raw numeric size/weight strings have no unit columns. Retained links come from frozen catalogue342cbb76, not a new Dropbox presence check.',
           'import_boundary': 'Append dated current-source corroboration only. Retain historical source assertions, accepted working specifications, source sale units, photo holds, identity uncertainties and platform action authorization flags. No canonical/workbook, Dropbox or platform mutation was performed.',
           'fresh_live_reads_or_native_shared_writes': 0, 'new_physical_or_identity_claims': 0}
with (HERE / 'source-field-readback.json').open('x', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
    f.write('\n')

E = html.escape
link = lambda url, label: '<a href="' + E(url, quote=True) + '">' + E(label) + '</a>'
parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>80 source offers: current metadata readback</title>',
         '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1120px;margin:36px auto;padding:0 20px;color:#22303a}section{border-top:1px solid #ccd5de;margin:30px 0;padding-top:12px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #d1d9df;padding:8px;text-align:left;vertical-align:top}th{background:#edf3f7}a{color:#075b95}p,td,code{overflow-wrap:anywhere}</style><body>',
         '<h1>80 source offers: current metadata readback</h1>',
         '<p>All80 recorded Squarespace source-product IDs and their selected SKUs are present in the authenticated24October2026 Physical export.720 comparisons agree with the retained historical source values:640 exact strings and80 descriptions after HTML/entity/whitespace normalization. This does not assert that the source descriptions are the correct accepted catalogue specifications.</p>',
         '<p>78 offers retain catalogue source-image/folder references. O006 and O007 retain their unresolved exact source-image binding; no replacement image association was inferred. The one Shopify-only source without a Squarespace ID remains unpaired, not absent.</p>',
         '<p>Raw prices and numeric size/weight strings remain source assertions. The CSV has no currency or measurement-unit columns. Photo, identity, sale-unit and physical qualifications remain intact. These links are from frozen catalogue342cbb76; no new Dropbox location or binary verification.</p>']
for e in entries:
    title = e['fields'][0]['current_csv_value_raw']
    parts += ['<section id="' + E(e['offer_ref']) + '"><h2>' + E(e['offer_ref'] + ' — ' + title) + '</h2>',
              '<p>' + link(e['current_source_url_from_export'], 'Source listing') + ' · ' + link(e['source_first_image_url'], 'Source image') + '</p>']
    ref = e['frozen_catalogue_source_image_reference']
    if ref:
        parts.append('<p>Retained catalogue reference: ' + link(ref['image_url'], 'Image') + ' · ' + link(ref['folder_url'], 'Containing folder') + '</p>')
    else:
        parts.append('<p>Exact source photograph and corresponding Dropbox folder remain unresolved.</p>')
    unit = e['historical_sale_unit_assertions_retained']
    parts.append('<p>Retained source sale scope: ' + E(unit['sale_unit_state']) + '; source parts assertion' + E(str(unit['native_parts'])) + '. This is a source statement, not a new physical quantity or individual price allocation.</p>')
    if e['source_cautions_retained']:
        parts.append('<p>Retained caution: ' + E(e['source_cautions_retained']) + '</p>')
    parts.append('<details><summary>Show nine source field comparisons</summary><table><tr><th>Field</th><th>Retained source value</th><th>Current CSV comparison value</th><th>Comparison</th></tr>')
    for x in e['fields']:
        parts.append('<tr><td>' + E(x['field']) + '</td><td>' + E(x['historical_comparison_value']) + '</td><td>' + E(x['current_comparison_value']) + '</td><td>' + E(x['comparison']) + ': equal</td></tr>')
    s = e['source']
    parts += ['</table></details><p><code>' + E(e['native_product_id']) + '</code> · Variant' + E(e['native_variant_id']) + ' · SKU' + E(e['sku']) + ' · CSV record' + str(s['csv_record_including_header_1based']) + ' / physical lines' + str(s['physical_line_start']) + '-' + str(s['physical_line_end']) + '</p></section>']
parts.append('<p>Prepared separately for the sole main catalogue writer. Squarespace, Dropbox and the shared catalogue remain unchanged by this lane.</p></body></html>')
with (HERE / 'review.html').open('x', encoding='utf-8') as f:
    f.write('\n'.join(parts))

# Saved-artifact readback against original CSV, not a workbook or live-state claim.
saved = json.loads((HERE / 'source-field-readback.json').read_text())
checks = []
checks.append(('Saved80 IDs and selected SKUs exactly match all retained Sq source offers',
               {(e['offer_ref'], e['native_product_id'], e['sku']) for e in saved['entries']} ==
               {(e['offer_ref'], e['source_offer']['sq_id'], e['source_offer']['sku']) for e in base['source_offer_edges'] if e['source_offer']['sq_id']}))
field_errors = []
for e in saved['entries']:
    r = next(r for r in raw_records if r['raw']['Variant ID [Non Editable]'] == e['native_variant_id'])
    original = base['source_offer_edges'][int(e['historical_source_locator'].split('/')[2])]['source_offer']
    for x in e['fields']:
        expected_current = headers[r['product_id']]['raw'][x['csv_column']] if x['csv_column'] in ['Title', 'Description', 'Visible'] else r['raw'][x['csv_column']]
        if x['historical_value_raw'] != original[x['historical_source_key']] or x['current_csv_value_raw'] != expected_current:
            field_errors.append((e['offer_ref'], x['field']))
    if e['source'] != r['source']:
        field_errors.append((e['offer_ref'], 'source locator'))
checks.append(('Saved720 source field groups and all physical-line locators read back exactly', not field_errors))
checks.append(('640 exact strings and80 normalized descriptions remain equal', Counter(x['comparison'] for e in saved['entries'] for x in e['fields']) == {'EXACT_STRING': 640, 'NORMALIZED_TEXT': 80} and all(x['equal'] and x['historical_comparison_value'] == x['current_comparison_value'] for e in saved['entries'] for x in e['fields'])))
checks.append(('78 retained image references and2 unresolved photo associations preserved', sum(bool(e['frozen_catalogue_source_image_reference']) for e in saved['entries']) == 78 and saved['unresolved_source_image_offer_refs'] == ['O006', 'O007']))
checks.append(('All existing image references, cautions and sale scopes retained exactly', all(e['frozen_catalogue_source_image_reference'] == base['source_offer_edges'][int(e['historical_source_locator'].split('/')[2])].get('current_primary_reference') and e['source_cautions_retained'] == base['source_offer_edges'][int(e['historical_source_locator'].split('/')[2])]['source_offer']['cautions'] and e['historical_sale_unit_assertions_retained'] == {k: base['source_offer_edges'][int(e['historical_source_locator'].split('/')[2])]['source_offer'][k] for k in ['sale_unit_state', 'native_parts', 'proposed_bom_pieces']} for e in saved['entries'])))


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.extend(v for k, v in attrs if k == 'href')


page = (HERE / 'review.html').read_text()
parser = Links()
parser.feed(page)
checks.append(('All80 source URLs and78 catalogue image/folder links appear in report', all(e['current_source_url_from_export'] in parser.urls and (not e['frozen_catalogue_source_image_reference'] or all(e['frozen_catalogue_source_image_reference'][k] in parser.urls for k in ['image_url', 'folder_url'])) for e in saved['entries'])))
checks.append(('One unpaired non-Squarespace source remains outside Sq comparison', len(saved['unpaired_source_offers']) == 1 and saved['counts']['unpaired_non_squarespace_offer'] == 1))
checks.append(('No photo/identity/physical or write authority upgrade', all(e['no_photo_binding_identity_or_physical_upgrade'] is True for e in saved['entries']) and saved['new_physical_or_identity_claims'] == 0 and saved['fresh_live_reads_or_native_shared_writes'] == 0))
checks.append(('Both pinned source byte hashes unchanged', sha(BASE) == EXPECTED_BASE and sha(CSV) == EXPECTED_CSV))
validation = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'PASS' if all(x[1] for x in checks) else 'FAIL',
              'checks': [{'name': k, 'passed': bool(v)} for k, v in checks],
              'checks_passed': sum(bool(x[1]) for x in checks), 'checks_total': len(checks),
              'payload_sha256': sha(HERE / 'source-field-readback.json'), 'report_sha256': sha(HERE / 'review.html'),
              'field_errors': field_errors, 'scope': 'Saved JSON/HTML source-field readback only; not an independent live/account, physical or image verification.'}
with (HERE / 'saved-readback.json').open('x', encoding='utf-8') as f:
    json.dump(validation, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': validation['status'], 'checks_passed': validation['checks_passed'], 'checks_total': len(checks), 'counts': saved['counts'], 'payload_sha256': validation['payload_sha256']}))
raise SystemExit(0 if validation['status'] == 'PASS' else 1)
