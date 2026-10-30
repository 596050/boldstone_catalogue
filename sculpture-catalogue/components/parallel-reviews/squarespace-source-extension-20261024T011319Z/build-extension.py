"""Read-only source metadata extension. Never imports or changes catalogue data."""
from __future__ import annotations

import csv
import hashlib
import html
import itertools
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'components/reconciliation/draft-completion-and-water-reference-master-2026-10-24/canonical-master-register.json'
CACHE = Path('/Users/tprice/Library/Application Support/BoldstoneLocal/cache/squarespace-admin-export-20261024T005645Z')
CSV = CACHE / 'products_Oct-24_01-55-19AM.csv'
NORMALIZED = CACHE / 'normalized-inventory.json'
CASES = ROOT / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/OVERLAP_PROPOSALS.json'
RUST_SEAL = ROOT / 'components/parallel-reviews/squarespace-admin-rust-readonly-20261024T010238Z/sealed-handoff.json'
EXPECTED = {
    BASE: '08e5cb133e9075a8b4a3f41149ad57060198556f124d9573f2e6f3ec919e6933',
    CSV: 'cdce1939100db77c78a818a99e4081712837b9aca21602b095a6055a40c7fbbf',
    NORMALIZED: '81583afeec14a82e40cdeb5da8c7fe5a8ec1c6a71a1aa34f9dd28f6cb27e6ea0',
    CASES: '3d74b90619131edef41a2f4468fae04d22a85fa4307f2390d90ba9566a70a8de',
    RUST_SEAL: 'ae71ce73759ddb9ca906d10b1eed045699eb79375bb7daa426598b91dbe1a7b8',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def objsha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def write(name, value):
    path = HERE / name
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


for path, digest in EXPECTED.items():
    assert sha(path) == digest, f'Frozen source mismatch: {path}'

base = json.loads(BASE.read_text())
inventory = json.loads(NORMALIZED.read_text())
proposals = {x['case_id']: x for x in json.loads(CASES.read_text())['proposals']}
options = {x['product_id']: x for x in base['options']}
native = {x['native_variant_id']: x for x in inventory['variants']}
products = {x['native_product_id']: x for x in inventory['products']}

# Re-read original CSV records independently; retain multiline physical locators.
raw_records = []
with CSV.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    assert len(reader.fieldnames) == len(set(reader.fieldnames))
    active_product = None
    while True:
        start = reader.line_num + 1
        try:
            fields = next(reader)
        except StopIteration:
            break
        if fields['Product ID [Non Editable]']:
            active_product = fields['Product ID [Non Editable]']
        assert active_product and None not in fields
        raw_records.append((active_product, fields, start, reader.line_num))
assert len(raw_records) == len(inventory['variants']) == 376
for i, (product_id, fields, start, end) in enumerate(raw_records, 1):
    v = inventory['variants'][i - 1]
    assert v['raw_fields'] == fields and v['native_product_id'] == product_id
    assert v['source'] == {'data_record_1based': i, 'csv_record_including_header_1based': i + 1,
                           'physical_line_start': start, 'physical_line_end': end}


def attributes(raw):
    pairs = [(raw[f'Option Name {i}'], raw[f'Option Value {i}']) for i in range(1, 7)]
    assert all(bool(n) == bool(v) for n, v in pairs)
    names = [n for n, _ in pairs if n]
    assert len(names) == len(set(names))
    return {n: v for n, v in pairs if n}


def current_tuple(variant_id):
    v = native[variant_id]
    r, p = v['raw_fields'], v['resolved_product_fields']
    return {
        'native_product_id': v['native_product_id'], 'native_variant_id': variant_id,
        'sku': r['SKU'], 'named_options': attributes(r),
        'price_raw': r['Price'], 'sale_price_raw': r['Sale Price'], 'on_sale_raw': r['On Sale'],
        'stock_setting_raw': r['Stock'], 'visible_product_setting_raw': p['Visible'],
        'dimensions_and_weight_raw': {k: r[k] for k in ['Length', 'Width', 'Height', 'Weight']},
        'currency_or_measurement_unit_columns_present': False,
        'physical_stock_or_specifications_verified': False,
        'per_variant_image_assignment_verified': False,
        'source': v['source'], 'product_header_record_1based': v['product_header_record_1based'],
        'product_id_resolution': v['product_id_resolution'],
    }


def option_ref(option_id):
    o = options[option_id]
    return {k: o[k] for k in ['product_id', 'canonical_key', 'name', 'image_url', 'folder_url', 'file_id', 'folder_id']}


def working(option_id):
    return options[option_id]['master_fields']


overlap_specs = [
    ('VERDIGRIS-VERSIONS', ['BSI-59530C6155C2'], [
        ('O004', '6a410e3f16d56f3a046ef1d7', '462d3d37-f550-429b-a84c-cca579fb15b1'),
        ('O038', '6a555a757b54f252fef707d1', '1d89ba22-d937-4064-a17c-0240bb153f90')],
     'Both records remain present and Visible=Yes. O038 still says SOLD while its raw stock setting is Unlimited. The source size/price differences remain. Retain the existing related-surface-version distinction; no exact configuration alias or additional named sale variant is established.'),
    ('MOON-WATER-OVERLAP', ['BSI-70C7029C1DB1', 'BSI-98376D9FF006'], [
        ('O059', '6a6102307b54f252fe00210b', '9d8c0d63-87c6-400e-8a85-51e4208271b3'),
        ('O015', '6a5559d21b9743318cc70b4b', '40624991-b17a-49e7-bd1d-22ffbc0b118f')],
     'Both records remain present and Visible=Yes. O015 retains the Concave Moon title/SKU and 50x50x6cm description; O059 retains Moonwater title/SKU, 50cm diameter x8cm and gypsum-composite claims. Preserve the prior visually supported catcher association and O015 identity-conflict quarantine; do not turn O015 into an exact MCP4 or catcher sale configuration.'),
]
overlaps = []
for case_id, option_ids, offers, conclusion in overlap_specs:
    old = proposals[case_id]
    assert set(old['offer_refs']) == {x[0] for x in offers}
    entries = []
    for offer_ref, product_id, variant_id in offers:
        assert product_id in json.dumps(old['canonical_alias_proposal'])
        assert variant_id in json.dumps(old['canonical_alias_proposal'])
        t = current_tuple(variant_id)
        assert t['native_product_id'] == product_id
        entries.append({'offer_ref': offer_ref, 'current_native_tuple': t})
    overlaps.append({
        'case_id': case_id, 'option_references': [option_ref(x) for x in option_ids],
        'prior_classification': old['classification'], 'current_source_entries': entries,
        'current_metadata_conclusion': conclusion,
        'prior_visual_conclusion_is_dated_not_reperformed': True,
        'prior_proposal_ref': {'path': str(CASES), 'sha256': EXPECTED[CASES],
                               'case_id': case_id},
        'current_working_field_objects_at_frozen_base': {x: working(x) for x in option_ids},
        'no_new_alias_identity_or_sale_unit_decision': True,
        'native_or_shared_changes_performed': 0,
    })

copy_notes = {
    'BSI-1E0C826D896E': 'The current native description still states 55x55x7cm. The accepted working face is80cm wide x60cm high with estimated5-8cm depth. Matching IDs/SKU and raw price1100.00 do not resolve which manufactured version the listing offers.',
    'BSI-DB7FBD3E1323': 'The current native description still states30x30x5cm. The owner-accepted working dimensions are45x40x5cm. Raw source price250.00 does not verify the physical size or base material.',
    'BSI-6581D83760F1': 'The current native description still states40x20x6cm and gypsum composite. The accepted working standard is35x35x6cm with a historical Jesmonite AC730 maker-version hypothesis. Raw source price350.00 does not resolve size or material.',
    'BSI-70C7029C1DB1': 'The current native description still states50cm diameter x8cm and gypsum composite. The working record retains maker-stated approximately51cm high x48cm wide,5-7cm side depth and the AC730/gypsum material conflict. Raw source price800.00 does not resolve the offered build.',
}
copy_targets = []
for e in base['current_existing_listing_copy_projections']['entries']:
    old = e['dated_native_tuple']
    current = current_tuple(old['variant_id'])
    assert current['native_product_id'] == old['product_id'] and current['sku'] == old['sku']
    assert e['current_working_fields'] == working(e['option_id'])
    copy_targets.append({
        'option_reference': option_ref(e['option_id']), 'historical_action_id': e['historical_action_id'],
        'frozen_projection_object_sha256': objsha(e), 'dated_native_tuple_preserved': old,
        'current_native_tuple': current, 'id_sku_tuple_reconfirmed_in_export': True,
        'current_working_fields_at_frozen_base': working(e['option_id']),
        'qualification': copy_notes[e['option_id']],
        'exact_six_field_configuration_match_verified': False,
        'platform_mutation_authorized': False, 'executable_now': False,
    })
assert len(copy_targets) == 4

circle_product_id = '68dc0a35a7ac865209b39248'
old_circle = {x['variant_id']: x for x in base['wall_circle_native_options']}
circle_ids = {x['native_variant_id'] for x in inventory['variants'] if x['native_product_id'] == circle_product_id}
assert circle_ids == set(old_circle) and len(circle_ids) == 144
circle_rows = []
for variant_id, old in old_circle.items():
    new = current_tuple(variant_id)
    assert new['sku'] == old['sku'] and new['named_options'] == old['attributes']
    assert new['price_raw'] == old['price']['value']
    other_comparison = {
        'on_sale_equal': new['on_sale_raw'] == ('Yes' if old['on_sale'] else 'No'),
        'sale_price_value_equal': new['sale_price_raw'] == old['sale_price']['value'],
        'unlimited_setting_equal': (new['stock_setting_raw'] == 'Unlimited') == old['stock_setting']['unlimited'],
        'raw_dimensions_weight_numerically_equal': all(
            Decimal(new['dimensions_and_weight_raw'][csv_key]) == Decimal(str(old['raw_dimensions_and_weight'][old_key]))
            for csv_key, old_key in [('Length', 'len'), ('Width', 'width'), ('Height', 'height'), ('Weight', 'weight')]),
    }
    circle_rows.append({'current_native_tuple': new,
                        'existing_id_sku_named_options_price_equal': True,
                        'additional_dated_metadata_comparison': other_comparison})
axes = {k: sorted({r['current_native_tuple']['named_options'][k] for r in circle_rows})
        for k in ['Pattern', 'Lighting', 'Diameter Size']}
assert [len(axes[x]) for x in axes] == [18, 2, 4]
combinations = Counter(tuple(r['current_native_tuple']['named_options'][k] for k in axes) for r in circle_rows)
assert combinations == Counter(itertools.product(*axes.values()))
conditional = []
custom = []
for e in base['current_listing_resolution_details']['entries']:
    if e.get('conditional_native_tuple'):
        t = e['conditional_native_tuple']
        now = current_tuple(t['native_variant_id'])
        assert now['native_product_id'] == t['native_product_id'] and now['sku'] == t['sku']
        assert now['named_options'] == {'Pattern': t['pattern'], 'Lighting': t['lighting_option'], 'Diameter Size': t['diameter_option']}
        assert now['price_raw'] == t['price_money_raw']['value']
        conditional.append({'option_reference': option_ref(e['product_id']), 'current_native_tuple': now,
                            'pattern_short_name_from_existing_record': t['pattern_short_name'],
                            'conditional_visual_attribution_retained': True,
                            'image_size_lighting_or_physical_binding_newly_verified': False})
    if e.get('custom_unlisted_pattern_draft'):
        custom.append({'option_reference': option_ref(e['product_id']),
                       'source_resolution_disposition_retained': e['source_resolution_disposition'],
                       'no_new_named_pattern_or_native_absence_claim': True})
assert len(conditional) == 4 and len(custom) == 3
circle = {
    'native_product_id': circle_product_id, 'variant_count': 144, 'axes': axes,
    'complete_unique_cartesian_product': True, 'rows': circle_rows,
    'conditional_existing_assignments': conditional, 'custom_scopes_retained': custom,
    'new_sculpture_or_design_count_increment': 0,
    'per_variant_images_or_physical_configuration_verified': False,
    'scope': 'Current source metadata readback only.144 selectable combinations =18 source pattern labels x2 lighting labels x4 diameter labels. These are not144 new physical sculptures. Four visual assignments remain conditional; three custom/unlisted visual scopes are not converted into named patterns or proved absent.',
}

selected_ids = {r['current_native_tuple']['native_variant_id'] for x in overlaps for r in x['current_source_entries']}
selected_ids.update(x['current_native_tuple']['native_variant_id'] for x in copy_targets)
selected_ids.update(circle_ids)
product_ids = {native[x]['native_product_id'] for x in selected_ids}
product_headers = []
for product_id in sorted(product_ids):
    p = products[product_id]
    h = p['raw_header_fields']
    first = native[p['variant_ids'][0]]
    product_headers.append({
        'native_product_id': product_id, 'source_header_record': p['source_header_record'],
        'title_raw': h['Title'], 'description_html_raw': h['Description'],
        'product_page_raw': h['Product Page'], 'product_url_raw': h['Product URL'],
        'navigation_url_from_observed_site_and_export_fields': 'https://boldstonesculpture.com/' + h['Product Page'].strip('/') + '/p/' + h['Product URL'].strip('/'),
        'visible_setting_raw': h['Visible'], 'variant_ids': p['variant_ids'],
        'hosted_image_urls_raw_sha256': hashlib.sha256(h['Hosted Image URLs'].encode()).hexdigest(),
        'hosted_urls_do_not_certify_per_variant_images_or_fresh_binary': True,
        'source': first['source'],
    })
assert len(selected_ids) == 151 and len(product_ids) == 8

payload = {
    'schema': 'boldstone.squarespace-source-extension.v1',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'PREPARED_READ_ONLY_NATIVE_SOURCE_EXTENSION_NOT_IMPORTED',
    'sources': [{'path': str(p), 'sha256': d} for p, d in EXPECTED.items()],
    'inventory_scope': 'Authenticated Physical inventory export acquired24October2026:208 products,376 variants; not deleted products, other product types, universal draft coverage or current live Shopify.',
    'normalization_scope': 'Variant IDs, SKUs, prices, stock and option values read from exact CSV record; only explicit product-block metadata supplied from its header. No variant values forward-filled. Currency and numeric measurement units are not present in CSV columns.',
    'base_master_is_frozen_not_claimed_current_after_parallel_publication': True,
    'counts': {'overlap_cases': 2, 'existing_copy_targets': 4, 'wall_circle_variants': 144,
               'conditional_wall_circle_assignments_preserved': 4, 'custom_visual_scopes_preserved': 3,
               'unique_selected_native_variants': 151, 'unique_selected_native_products': 8,
               'new_catalogue_identity_matches': 0, 'platform_or_native_changes': 0},
    'native_product_headers': product_headers,
    'remaining_overlap_readbacks': overlaps, 'existing_copy_target_readbacks': copy_targets,
    'wall_circle_source_readback': circle,
    'import_boundary': 'Main writer may append this dated native-source evidence after its current publication. Do not overwrite accepted working specifications, historical source assertions, existing image roles, conditional visual bindings, unresolved physical configuration checks or action authorization flags. A performed no shared/canonical/workbook/platform/native writes.',
    'fresh_live_ui_or_api_reads_this_extension': 0,
    'fresh_image_or_physical_review_performed': False,
    'existing_rust_seal_preserved': True,
}
write('source-readback-extension.json', payload)

E = html.escape


def link(url, label):
    return '<a href="' + E(url, quote=True) + '">' + E(label) + '</a>'


def navigation(ref):
    return link(ref['image_url'], 'Image') + ' · ' + link(ref['folder_url'], 'Containing folder')


def table(headers, rows):
    return '<table><thead><tr>' + ''.join('<th>' + E(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table>'


ph = {p['native_product_id']: p for p in product_headers}


def native_table(entries):
    rows = []
    for label, t in entries:
        p = ph[t['native_product_id']]
        loc = t['source']
        rows.append([E(label), link(p['navigation_url_from_observed_site_and_export_fields'], p['title_raw']),
                     E(t['sku']), E(t['price_raw']), E(t['stock_setting_raw']), E(t['visible_product_setting_raw']),
                     str(loc['csv_record_including_header_1based']) + ' / lines' + str(loc['physical_line_start']) + '-' + str(loc['physical_line_end'])])
    return table(['Reference', 'Source listing', 'SKU', 'Raw price', 'Stock setting', 'Visible', 'CSV record / physical lines'], rows)


parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Squarespace remaining source readback</title>',
         '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1180px;margin:36px auto;padding:0 20px;color:#202830}section{margin:34px 0;padding-top:12px;border-top:1px solid #ccd3da}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border:1px solid #d4d9de;padding:8px;vertical-align:top}th{background:#eef2f6}a{color:#075b95}code{overflow-wrap:anywhere}p,td{overflow-wrap:anywhere}</style><body>',
         '<h1>Remaining listing source readback</h1>',
         '<p>Read-only comparison of the authenticated24October2026 Physical inventory export with the frozen catalogue08e5cb13. Prepared for the main catalogue writer; not imported. All image/folder links below are retained catalogue references, not new Dropbox location checks.</p>',
         '<p>208 source products /376 variants. This extension covers2 remaining overlaps,4 existing copy targets and144 Wall Circle variants (151 unique variant IDs across8 products). No new identity decisions, physical verification or platform changes. Raw prices and dimensions below retain CSV strings; the export has no currency or measurement-unit columns.</p>']
for item in overlaps:
    parts += ['<section><h2>' + E(item['case_id']) + '</h2>']
    for ref in item['option_references']:
        parts += ['<p><strong>' + E(ref['name']) + '</strong> — ' + navigation(ref) + '</p>']
    parts += ['<p>' + E(item['current_metadata_conclusion']) + '</p>',
              native_table([(r['offer_ref'], r['current_native_tuple']) for r in item['current_source_entries']]),
              '<p>Prior image interpretation is retained as dated evidence; photographs were not re-reviewed in this metadata extension.</p></section>']
for item in copy_targets:
    ref = item['option_reference']
    parts += ['<section><h2>' + E(ref['name']) + '</h2><p>' + navigation(ref) + '</p>',
              '<p>' + E(item['qualification']) + '</p>', native_table([('Existing listing', item['current_native_tuple'])]),
              '<h3>Accepted working record, retained with its qualifications</h3>',
              table(['Specification', 'Working detail'], [[E(k), E(v['display'])] for k, v in item['current_working_fields_at_frozen_base'].items()]),
              '<p>IDs/SKU reconfirmed in this account export. Exact build, size, material, fitted hardware and physical stock remain unverified; existing copy drafts remain unexecuted.</p></section>']
parts += ['<section><h2>Wall Circle</h2><p>All144 existing variant IDs, SKUs, named option values and raw prices match the dated catalogue. The complete18-pattern ×2-lighting ×4-size matrix is present once per combination. Four existing visual assignments remain conditional; three custom/unlisted scopes retain their existing status.</p>']
for item in conditional:
    ref, t = item['option_reference'], item['current_native_tuple']
    parts += ['<p><strong>' + E(ref['name']) + '</strong> — ' + navigation(ref) + '<br>Conditional existing pattern: ' + E(item['pattern_short_name_from_existing_record']) + '; ' + E(t['named_options']['Diameter Size']) + '; ' + E(t['named_options']['Lighting']) + '; SKU' + E(t['sku']) + '.</p>']
for item in custom:
    ref = item['option_reference']
    parts += ['<p><strong>' + E(ref['name']) + '</strong> — ' + navigation(ref) + '<br>Custom/unlisted visual scope retained; no new named-pattern assignment or source-absence conclusion.</p>']
parts += ['<details><summary>Show all144 current source combinations</summary>', table(
    ['Pattern', 'Lighting', 'Diameter option', 'Variant ID', 'SKU', 'Raw price'], [
        [E(t['named_options']['Pattern']), E(t['named_options']['Lighting']), E(t['named_options']['Diameter Size']),
         '<code>' + E(t['native_variant_id']) + '</code>', E(t['sku']), E(t['price_raw'])]
        for row in circle_rows for t in [row['current_native_tuple']]]), '</details></section>',
    '<p>Source CSV SHA-256:<code>' + EXPECTED[CSV] + '</code>. Raw source remains in private local cache. Fresh Squarespace changes:0. Fresh Dropbox changes:0. Canonical/workbook/shared writes by this lane:0.</p></body></html>']
with (HERE / 'review.html').open('x', encoding='utf-8') as f:
    f.write('\n'.join(parts))
for path, digest in EXPECTED.items():
    assert sha(path) == digest, f'Source changed while preparing: {path}'
print(json.dumps({'directory': str(HERE), 'payload_sha256': sha(HERE / 'source-readback-extension.json'),
                  'counts': payload['counts'], 'additional_wall_metadata_differences': sum(not all(r['additional_dated_metadata_comparison'].values()) for r in circle_rows)}))
