"""Screen existing exported records without creating product identity matches."""
import csv
import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
SQ = Path('/Users/tprice/Library/Application Support/BoldstoneLocal/cache/squarespace-admin-export-20261024T005645Z/products_Oct-24_01-55-19AM.csv')
SH = Path('/Users/tprice/Downloads/products_export_1 (1).csv')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
pointer = read(BASE / 'current-master.json')
register_path = BASE / pointer['register']
register = read(register_path)
assert sha(register_path) == pointer['register_sha256']
assert sha(SQ) == 'cdce1939100db77c78a818a99e4081712837b9aca21602b095a6055a40c7fbbf'
assert sha(SH) == 'bfa0412dbbc6461060023e71d739ce73a4c76918730de165e2472e5436500118'
queue_path = BASE / 'components/parallel-reviews/shopify-access-readiness-20261024T005700Z/current-188-option-verification-queue.json'
ids = {x['product_id'] for x in read(queue_path)['rows'] if x['historical_shopify_disposition'] == 'NEW_CURRENT_OPTION_PLATFORM_VERIFICATION_PENDING'}
options = [o for o in register['options'] if o['product_id'] in ids]
assert len(options) == 9 and len({o['product_id'] for o in options}) == 9
offers = {x['offer_ref']: x['source_offer'] for x in register['source_offer_edges']}
rules = {'fingerprint': r'finger[\W_]*print|concentric', 'acanthus_pewter': r'acanthus',
         'egyptian_pewter': r'egyptian|(?:golden|two)[\W_]+palms?',
         'moon_shellwave_water': r'shell[\W_]*wave|half[\W_]*moon|mirror[\W_]*moons'}
specific = {'fingerprint': r'finger[\W_]*print', 'acanthus_pewter': r'pewter',
            'egyptian_pewter': r'pewter', 'moon_shellwave_water': r'water[\W_]*feature'}
scope_for = lambda o: 'fingerprint' if o['family'] == 'Fingerprint' else 'acanthus_pewter' if o['canonical_design_id'] == 'BC-AC-TWO' else 'egyptian_pewter' if o['canonical_design_id'] == 'BC-EG-1' else 'moon_shellwave_water'
scope_offers = {'fingerprint': [], 'acanthus_pewter': ['O069'], 'egyptian_pewter': ['O041', 'O042'], 'moon_shellwave_water': ['O021', 'O032', 'O033']}
notes = {
 'fingerprint': 'No Fingerprint name or numbered Concentric variant is identified in these exports. Broader concentric wording occurs on Echo Pattern, Echo Sound, a Bronze surface sculpture and a greetings card. Those references do not establish any of the six current numbered/finish options. The historical Left/Right physical alias remains unconfirmed.',
 'acanthus_pewter': 'The existing same-design source link is for the Bronze finish. Other Acanthus-named source records describe White or Gold Leaf. None of these source fields establishes the current individual Pewter finish.',
 'egyptian_pewter': 'The existing same-design references are Golden Palm (Gold Leaf) and the Two Palms arrangement. Neither establishes an individual Egyptian Palm One Pewter variant. No Pewter option value was found in the checked exports.',
 'moon_shellwave_water': 'The existing standard-design references are two- or three-panel arrangements. They do not specify this separate single-panel water-feature build. Several historical Shopify handles retain copied Moon/Shellwave names for differently titled products; handle text alone is not identity evidence.'}


def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', value or ''))).strip()


def parse(path, platform):
    reader = csv.reader(io.StringIO(path.read_bytes().decode('utf-8-sig'), newline=''))
    headers = next(reader)
    end = reader.line_num
    groups = {}
    current_product_id = None
    product_header_record = None
    for record, values in enumerate(reader, 2):
        assert len(values) == len(headers)
        row = dict(zip(headers, values))
        if platform == 'squarespace':
            if row['Product ID [Non Editable]']:
                current_product_id = row['Product ID [Non Editable]']
                product_header_record = record
            else:
                assert current_product_id and row['Variant ID [Non Editable]']
            key = current_product_id
        else:
            key = row['Handle']
        assert key
        groups.setdefault(key, []).append({'record_including_header': record, 'physical_line_start': end + 1, 'physical_line_end': reader.line_num,
                                          'effective_product_id_or_handle': key, 'product_header_record': product_header_record if platform == 'squarespace' else None, 'raw': row})
        end = reader.line_num
    products = []
    for key, records in groups.items():
        fields = ['Title', 'Description', 'Body (HTML)', 'Tags', 'SKU', 'Variant SKU', 'GTIN', 'MPN']
        descriptive = '\n'.join(plain(v) for item in records for k, v in item['raw'].items() if v and (k in fields or k.startswith('Option')))
        title = next((x['raw']['Title'] for x in records if x['raw']['Title']), '')
        routes = '\n'.join(x['raw'].get('Product URL', x['raw'].get('Handle', '')) for x in records)
        products.append({'platform': platform, 'product_id_or_handle': key, 'title': title,
                         'descriptive_text': descriptive, 'route_text': routes, 'records': records})
    return products


inventories = {'squarespace': parse(SQ, 'squarespace'), 'historical_shopify': parse(SH, 'historical_shopify')}
assert len(inventories['squarespace']) == 208 and len(inventories['historical_shopify']) == 136
source_evidence = {}
scope_results = {}
for scope, pattern in rules.items():
    evidence_ids = []
    direct_refs = [offers[x] for x in scope_offers[scope]]
    for platform, products in inventories.items():
        for product in products:
            key = product['product_id_or_handle']
            related = [o['offer_ref'] for o in direct_refs if key == o.get('sq_id' if platform == 'squarespace' else 'sh_handle')]
            descriptive_hit = bool(re.search(pattern, product['descriptive_text'], re.I))
            route_hit = bool(re.search(pattern, product['route_text'], re.I))
            if not (descriptive_hit or route_hit or related):
                continue
            evidence_id = platform + ':' + key
            if evidence_id not in source_evidence:
                source_evidence[evidence_id] = product
            evidence_ids.append({'evidence_id': evidence_id, 'descriptive_term_hit': descriptive_hit,
                                 'route_only_term_hit': route_hit and not descriptive_hit and not related,
                                 'existing_sibling_offer_refs': related})
            for offer_ref in related:
                sku_key = 'SKU' if platform == 'squarespace' else 'Variant SKU'
                assert any(x['raw'][sku_key] == offers[offer_ref]['sku'] for x in product['records'])
    # Specific finish/build terms are counted separately from broad family words.
    specific_counts = {platform: sum(bool(re.search(specific[scope], x['descriptive_text'], re.I)) for x in products) for platform, products in inventories.items()}
    scope_results[scope] = {'assessment': notes[scope], 'retrieval_regex': pattern, 'specific_regex': specific[scope], 'specific_term_product_counts': specific_counts,
                            'existing_same_design_offer_refs': scope_offers[scope], 'screened_source_candidates': evidence_ids,
                            'new_exact_individual_matches_verified': 0, 'native_absence_claimed': False}
rows = []
for o in options:
    scope = scope_for(o)
    rows.append({'product_id': o['product_id'], 'name': o['name'], 'scope': scope, 'canonical_key': o['canonical_key'],
                 'image_url': o['image_url'], 'folder_url': o['folder_url'], 'file_id': o['file_id'], 'folder_id': o['folder_id'],
                 'photo_coverage': o['photo_coverage'], 'sale_unit': o['sale_unit'],
                 'accepted_working_fields': {k: v['display'] for k, v in o['master_fields'].items()},
                 'source_assessment': notes[scope], 'status': 'SOURCE_SCREENED_EXACT_CURRENT_VARIANT_UNRESOLVED',
                 'source_candidates': scope_results[scope]['screened_source_candidates'], 'new_owner_question': False})
sources = [{'path': str(p), 'sha256': sha(p)} for p in [register_path, queue_path, SQ, SH]]
packet = {'schema': 'boldstone.nine-new-options-source-screen.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'status': 'READ_ONLY_SCREEN_COMPLETE_IDENTITIES_UNRESOLVED', 'source_master_register': pointer['register'],
          'inventory_counts': {p: {'products': len(v), 'csv_rows': sum(len(x['records']) for x in v)} for p, v in inventories.items()},
          'sources': sources, 'rows': rows, 'scopes': scope_results, 'source_evidence': source_evidence,
          'legacy_fingerprint_physical_alias_confirmed': register['latest_fingerprint_product_finalization']['legacy_physical_alias_confirmed'],
          'limits': ['Squarespace evidence is the authenticated export captured on 24 October 2026, not a later live read.',
                     'Shopify evidence is the retained historical CSV; no current store or numeric Shopify product/variant ID has been verified.',
                     'Text and existing design associations screen candidates only. Photographs, exact finish/build, aliases and sale units have not been newly matched.',
                     'Zero exact matches established does not prove absence. No source ID/SKU is assigned to these nine current options.',
                     'Approved working specifications, photo holds and existing arrangements remain unchanged.'],
          'new_exact_matches': 0, 'source_variants_created': 0, 'shared_or_native_writes': 0, 'new_owner_questions': 0}
esc = lambda x: html.escape(str(x), quote=True)
cards = []
for row in rows:
    specs = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v) + '</td></tr>' for k, v in row['accepted_working_fields'].items())
    candidates = []
    for hit in row['source_candidates']:
        e = source_evidence[hit['evidence_id']]
        label = 'Historical Shopify' if e['platform'] == 'historical_shopify' else 'Squarespace export'
        suffix = ' — copied handle wording only; no descriptive match' if hit['route_only_term_hit'] else ''
        candidates.append('<li>' + esc(label + ': ' + e['title'] + suffix) + '</li>')
    cards.append('<article id="' + esc(row['product_id']) + '"><h2>' + esc(row['name']) + '</h2><p><a href="' + esc(row['image_url']) + '">Catalogue image</a> · <a href="' + esc(row['folder_url']) + '">Containing folder</a></p><p>' + esc(row['source_assessment']) + '</p><details><summary>Export records screened</summary><ul>' + ''.join(candidates) + '</ul></details><details><summary>Accepted working specifications</summary><table>' + specs + '</table></details></article>')
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Nine new sculpture options — source check</title><style>body{font:17px system-ui;line-height:1.55;max-width:980px;margin:32px auto;padding:0 20px;color:#202526;background:#f7f5f1}article{background:white;border:1px solid #d6d4d0;border-radius:10px;padding:24px;margin:22px 0}h1,h2{line-height:1.2}a{color:#155c72}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:10px}th{width:25%}summary{cursor:pointer;font-weight:600}details{margin-top:16px}</style></head><body><h1>Nine new sculpture options — source check</h1><p>Checked the saved Squarespace export and historical Shopify extract for existing records before any new listing is proposed. No exact current individual variant was established for these nine options. This does not prove the products are absent.</p><p>Squarespace: 208 products / 376 variant rows, exported 24 October 2026. Shopify: 136 historical products / 416 CSV rows. Current Shopify access remains unresolved.</p><p>Six Fingerprint options, two Pewter options and one White Water Feature. All accepted specifications and photo holds remain in place.</p>' + ''.join(cards) + '</body></html>'
for source in sources:
    assert sha(source['path']) == source['sha256']
for name, value in [('source-screening.json', packet)]:
    with (HERE / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')
with (HERE / 'review.html').open('x', encoding='utf-8') as f:
    f.write(page)
loaded = read(HERE / 'source-screening.json')
assert len(loaded['rows']) == 9 and loaded['new_exact_matches'] == 0
assert all(esc(x['image_url']) in page and esc(x['folder_url']) in page for x in rows)
seal = {'status': 'SEALED_READ_ONLY_SOURCE_SCREEN', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'files': [{'path': str(HERE / name), 'sha256': sha(HERE / name)} for name in ['source-screening.json', 'review.html', 'build_screen.py']],
        'current_options_screened': 9, 'exact_matches_established': 0, 'shared_or_native_writes': 0}
with (HERE / 'sealed-handoff.json').open('x', encoding='utf-8') as f:
    json.dump(seal, f, ensure_ascii=False, indent=2); f.write('\n')
print(json.dumps({'options': len(rows), 'source_records': len(source_evidence), 'scope_counts': {k: len(v['screened_source_candidates']) for k, v in scope_results.items()},
                  'specific_term_counts': {k: v['specific_term_product_counts'] for k, v in scope_results.items()}, 'new_exact_matches': 0,
                  'seal': str(HERE / 'sealed-handoff.json'), 'seal_sha256': sha(HERE / 'sealed-handoff.json')}))
