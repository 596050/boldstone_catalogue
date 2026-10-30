"""Read back the new metadata census against original CSV and frozen source IDs."""
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
DATA = HERE / 'source-coverage-census.json'
data = json.loads(DATA.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = []


def check(name, passed, details=None):
    checks.append({'name': name, 'passed': bool(passed), 'details': details})


sources = {Path(s['path']): s['sha256'] for s in data['sources']}
check('All three pinned inputs retain exact source hashes', len(sources) == 3 and all(sha(p) == s for p, s in sources.items()))
raw_path = next(p for p in sources if p.suffix == '.csv')
base_path = next(p for p in sources if p.name == 'canonical-master-register.json')
base = json.loads(base_path.read_text())
known = {x['source_offer']['sq_id'] for x in base['source_offer_edges'] if x['source_offer']['sq_id']}
headers, variants = {}, {}
with raw_path.open(encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    product_id = None
    record_index = 0
    while True:
        line_start = reader.line_num + 1
        try:
            raw = next(reader)
        except StopIteration:
            break
        record_index += 1
        if raw['Product ID [Non Editable]']:
            product_id = raw['Product ID [Non Editable]']
            headers[product_id] = {'raw': raw, 'record': record_index, 'variant_ids': []}
        assert product_id and raw['Variant ID [Non Editable]'] not in variants
        vid = raw['Variant ID [Non Editable]']
        headers[product_id]['variant_ids'].append(vid)
        variants[vid] = {'raw': raw, 'product_id': product_id,
                         'source': {'data_record_1based': record_index, 'csv_record_including_header_1based': record_index + 1,
                                    'physical_line_start': line_start, 'physical_line_end': reader.line_num}}

other = data['other_native_products_metadata_review']
reported_known = data['recorded_source_product_id_coverage']
other_ids = {x['native_product_id'] for x in other}
check('Raw CSV independently contains208 product headers and376 unique variants', len(headers) == 208 and len(variants) == 376)
check('Known source-ID set equals exact80 frozen catalogue IDs', len(known) == 80 and known == {x['native_product_id'] for x in reported_known})
check('128 other product IDs are unique, disjoint and exhaustive for the CSV', len(other_ids) == len(other) == 128 and not (known & other_ids) and known | other_ids == set(headers))
check('Offer without Squarespace ID retained as unpaired, not absent', data['offer_refs_without_squarespace_id_not_labelled_absent'] == [x['offer_ref'] for x in base['source_offer_edges'] if not x['source_offer']['sq_id']] and len(data['offer_refs_without_squarespace_id_not_labelled_absent']) == 1)

header_errors, variant_errors = [], []
for e in other:
    h = headers[e['native_product_id']]
    raw = h['raw']
    pairs = [('title_raw', 'Title'), ('description_html_raw', 'Description'), ('category_raw', 'Categories'),
             ('visible_setting_raw', 'Visible'), ('header_sku_raw', 'SKU'),
             ('product_page_raw', 'Product Page'), ('product_url_raw', 'Product URL'),
             ('hosted_image_urls_raw', 'Hosted Image URLs')]
    if not (all(e[k] == raw[col] for k, col in pairs) and
            e['source_header_record'] == h['record'] and
            e['source'] == variants[raw['Variant ID [Non Editable]']]['source'] and
            e['source_image_urls'] == raw['Hosted Image URLs'].split() and
            e['navigation_url_from_observed_site_and_export_fields'] == 'https://boldstonesculpture.com/' + raw['Product Page'].strip('/') + '/p/' + raw['Product URL'].strip('/')):
        header_errors.append(e['native_product_id'])
    if [v['native_variant_id'] for v in e['variant_entries']] != h['variant_ids']:
        variant_errors.append({'product': e['native_product_id'], 'field': 'variant IDs'})
    for v in e['variant_entries']:
        original = variants[v['native_variant_id']]
        r = original['raw']
        if not (original['product_id'] == e['native_product_id'] and v['sku_raw'] == r['SKU'] and
                v['price_raw'] == r['Price'] and v['stock_raw'] == r['Stock'] and v['source'] == original['source']):
            variant_errors.append({'variant': v['native_variant_id']})
check('All128 reported product fields and physical-line locators match original raw CSV', not header_errors, header_errors)
check('All153 other-product variant IDs/SKUs/prices/stock/locators match exact raw records', sum(len(x['variant_entries']) for x in other) == 153 and not variant_errors, variant_errors)
check('Known223 plus other153 variants exhaust source376 without overlap', sum(len(x['variant_ids']) for x in reported_known) == 223 and {v for x in reported_known for v in x['variant_ids']} == {v for v, x in variants.items() if x['product_id'] in known} and {v['native_variant_id'] for x in other for v in x['variant_entries']} == {v for v, x in variants.items() if x['product_id'] not in known})
check('Known-ID source references and visibility are exact', all(x['offer_refs'] == [e['offer_ref'] for e in base['source_offer_edges'] if e['source_offer']['sq_id'] == x['native_product_id']] and x['visible_setting_raw'] == headers[x['native_product_id']]['raw']['Visible'] and x['variant_ids'] == headers[x['native_product_id']]['variant_ids'] for x in reported_known))

buckets = Counter(x['metadata_review_bucket'] for x in other)
check('Four review buckets retain all128 rows with98/24/3/3 counts', dict(buckets) == data['counts']['metadata_buckets'] and sorted(buckets.values()) == [3, 3, 24, 98])
paper = [x for x in other if x['metadata_review_bucket'] == 'PAPER_ART_CARD_PRINT_OR_PHOTOGRAPHY_SOURCE']
check('All98 paper/card/photo scopes supported by explicit source sale descriptions', len(paper) == 98 and all((x['category_raw'] == '/cards' and 'greetings card' in x['title_raw'].lower() and 'card' in x['description_text_for_review'].lower()) or (x['category_raw'] in ['/prints', '/photography', '/art'] and bool(re.search(r'paper|print|photograph|watercolou?r|cotton|mount|drawing', x['description_text_for_review'], re.I))) for x in paper))
objects = [x for x in other if x['metadata_review_bucket'] == 'OTHER_EXPLICITLY_DESCRIBED_OBJECT_SOURCE']
check('24 described object scopes use explicit marketed object terms', len(objects) == 24 and all(any(k in x['title_raw'].lower() for k in ['bookend', 'bowl', 'table', 'lamp', 'stool', 'balloon', 'ornament', 'candle holder']) and bool(x['description_html_raw']) for x in objects))
fixtures = [x for x in other if x['metadata_review_bucket'] == 'WALL_FIXTURE_WITHOUT_CATALOGUE_BINDING']
check('Exactly two mirrors and one sconce remain unassociated source scopes', {x['native_product_id'] for x in fixtures} == {'6a42666b21dbe14148c1805b', '6a4271efb629f94bfa4f9c90', '6a438c4e7d679361b81d0c88'} and all(x['new_existing_sculpture_binding_established'] is False and x['dropbox_folder_binding_established'] is False for x in fixtures))
hidden = [x for x in other if x['metadata_review_bucket'] == 'HIDDEN_WITHOUT_DESCRIPTION']
check('Three hidden undescribed headers remain explicitly content-unknown', {x['title_raw'] for x in hidden} == {'Fabric', 'Tiles', 'Wallpaper'} and all(x['visible_setting_raw'] == 'No' and not x['category_raw'] and not x['description_html_raw'] and 'unknown' in x['metadata_scope_reason'] for x in hidden))
check('Other products visibility count is125 Yes and3 No', Counter(x['visible_setting_raw'] for x in other) == {'Yes': 125, 'No': 3})
check('No identity, physical specification, stock or new sale-unit claim added', all(x['new_existing_sculpture_binding_established'] is False and x['physical_specifications_or_stock_verified'] is False and x['new_catalogue_sale_unit_created_or_retired'] is False for x in other) and data['counts']['new_confirmed_catalogue_identity_matches'] == 0)
check('No source images promoted to fresh binary/visual review and no live/shared writes claimed', all(x['source_images_are_links_only_not_freshly_downloaded_or_reviewed'] is True for x in other) and data['native_platform_shared_or_canonical_writes'] == 0 and data['fresh_live_reads'] == 0)


class LinkReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.extend(v for k, v in attrs if k == 'href')


page = (HERE / 'review.html').read_text()
links = LinkReader()
links.feed(page)
check('Report has exact source listing and available image links for every128 products', all(x['navigation_url_from_observed_site_and_export_fields'] in links.urls and (not x['source_image_urls'] or x['source_image_urls'][0] in links.urls) for x in other))
check('Report makes no invented Dropbox-folder navigation', not any('dropbox.com' in url for url in links.urls))
check('Pinned inputs remain unchanged after independent validation', all(sha(p) == s for p, s in sources.items()))

result = {'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'status': 'PASS' if all(x['passed'] for x in checks) else 'FAIL',
          'checks_passed': sum(x['passed'] for x in checks), 'checks_total': len(checks),
          'payload_sha256': sha(DATA), 'review_html_sha256': sha(HERE / 'review.html'), 'checks': checks,
          'scope': 'Raw original CSV versus frozen source-ID register and saved JSON/HTML. Metadata review only; no fresh UI/API/binary/physical/visual render or catalogue/workbook import verification.'}
with (HERE / 'independent-readback.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'status': result['status'], 'passed': result['checks_passed'], 'total': result['checks_total'], 'failures': [x for x in checks if not x['passed']]}))
raise SystemExit(0 if result['status'] == 'PASS' else 1)
