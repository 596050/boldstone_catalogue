"""Local metadata census only; no platform, Dropbox or catalogue mutations."""
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'components/reconciliation/spiralmoon-current-folder-refresh-master-2026-10-24/canonical-master-register.json'
CACHE = Path('/Users/tprice/Library/Application Support/BoldstoneLocal/cache/squarespace-admin-export-20261024T005645Z')
NORM = CACHE / 'normalized-inventory.json'
CSV = CACHE / 'products_Oct-24_01-55-19AM.csv'
SOURCE_HASHES = {
    BASE: '53e6656a589708f2ff8f420a2050d9c8db7e2d6e7baf9d267fd6385aedbfe1cb',
    CSV: 'cdce1939100db77c78a818a99e4081712837b9aca21602b095a6055a40c7fbbf',
    NORM: '81583afeec14a82e40cdeb5da8c7fe5a8ec1c6a71a1aa34f9dd28f6cb27e6ea0',
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


for p, expected in SOURCE_HASHES.items():
    assert sha(p) == expected, str(p)
base = json.loads(BASE.read_text())
source = json.loads(NORM.read_text())
known = {}
no_id = []
for e in base['source_offer_edges']:
    product_id = e['source_offer']['sq_id']
    if product_id:
        known.setdefault(product_id, []).append(e['offer_ref'])
    else:
        no_id.append(e['offer_ref'])
assert len(known) == 80 and len(no_id) == 1
assert set(known) == {x['squarespace_id'] for x in base['source_platform_offer_coverage'] if x['squarespace_id']}
variants = {x['native_variant_id']: x for x in source['variants']}

wall_fixtures = {
    '6a42666b21dbe14148c1805b': 'Source describes a sconce in /lighting,100x30x3cm, with a brass central bar. No exact existing wall-sculpture component or Dropbox parent is established by this metadata census.',
    '6a4271efb629f94bfa4f9c90': 'Source explicitly markets a wall mirror,1m wide x60cm high. Retain its mirror sale unit; no wall-panel or pattern identity match is established.',
    '6a438c4e7d679361b81d0c88': 'Source explicitly markets a mirror,50cm diameter and6cm depth. Matching circular form or marbled appearance would not alone establish a Wall Circle/Moon Crater sculpture configuration.',
}
boundary_notes = {
    '6aa01ade4b08934e6b0d3db1': 'Source describes a catch-all keyring bowl for a table/sideboard/desk,25x25x6cm. Spherical relief and /sculpture category do not establish a Moon Crater wall-panel sale-unit match.',
    '6aa01ad75e7636290fa6e95d': 'Source describes a multicoloured catch-all keyring bowl for a table/sideboard/desk,25x25x6cm. No shared mould, component identity or wall-panel offer is established.',
    '6a425bf2870e0e6bc1e1a24e': 'Source /sculpture category coexists with an explicit decorative stool/stand sale description. No existing wall-sculpture match is inferred.',
    '6a43e6a4b629f94bfa50bfd2': 'Source /sculpture category describes100cm decorative balloons. Physical manufacture, mounting and current Dropbox membership are not verified.',
}
kind_terms = ['bookend', 'bowl', 'table', 'lamp', 'stool', 'balloon', 'ornament', 'candle holder']
entries = []
known_entries = []
for p in source['products']:
    pid, h = p['native_product_id'], p['raw_header_fields']
    if pid in known:
        known_entries.append({'native_product_id': pid, 'offer_refs': known[pid],
                              'visible_setting_raw': h['Visible'], 'variant_ids': p['variant_ids']})
        continue
    description = ' '.join(html.unescape(re.sub(r'<[^>]*>', ' ', h['Description'])).split())
    if h['Visible'] == 'No' and not h['Description']:
        bucket = 'HIDDEN_WITHOUT_DESCRIPTION'
        reason = 'Hidden product header has no description or category. Retain title/SKU only; actual contents, draft lifecycle, individual configurations and possible sculpture coverage remain unknown.'
    elif pid in wall_fixtures:
        bucket = 'WALL_FIXTURE_WITHOUT_CATALOGUE_BINDING'
        reason = wall_fixtures[pid]
    elif h['Categories'] in ['/cards', '/prints', '/photography', '/art']:
        if h['Categories'] == '/cards':
            assert 'greetings card' in h['Title'].lower() and 'card' in description.lower()
        else:
            assert re.search(r'paper|print|photograph|watercolou?r|cotton|mount|drawing', description, re.I)
        bucket = 'PAPER_ART_CARD_PRINT_OR_PHOTOGRAPHY_SOURCE'
        reason = 'Source title/category and description market a card, print, mounted paper artwork or photographic print. A depicted sculpture, artist credit or the word wall is not an individual cast-sculpture sale offer.'
    else:
        assert any(term in h['Title'].lower() for term in kind_terms), h['Title']
        bucket = 'OTHER_EXPLICITLY_DESCRIBED_OBJECT_SOURCE'
        reason = boundary_notes.get(pid, 'Source title and description explicitly market a furniture/accessory/lighting object. No individual wall-sculpture binding or absence is inferred by this census.')
    image_urls = h['Hosted Image URLs'].split()
    assert all(x.startswith('https://images.squarespace-cdn.com/') for x in image_urls)
    first = variants[p['variant_ids'][0]]
    entries.append({
        'native_product_id': pid, 'title_raw': h['Title'], 'description_html_raw': h['Description'],
        'description_text_for_review': description, 'category_raw': h['Categories'],
        'visible_setting_raw': h['Visible'], 'header_sku_raw': h['SKU'],
        'source': first['source'], 'source_header_record': p['source_header_record'],
        'product_page_raw': h['Product Page'], 'product_url_raw': h['Product URL'],
        'navigation_url_from_observed_site_and_export_fields': 'https://boldstonesculpture.com/' + h['Product Page'].strip('/') + '/p/' + h['Product URL'].strip('/'),
        'hosted_image_urls_raw': h['Hosted Image URLs'], 'source_image_urls': image_urls,
        'source_images_are_links_only_not_freshly_downloaded_or_reviewed': True,
        'metadata_review_bucket': bucket, 'metadata_scope_reason': reason,
        'variant_entries': [
            {'native_variant_id': vid, 'sku_raw': variants[vid]['raw_fields']['SKU'],
             'price_raw': variants[vid]['raw_fields']['Price'], 'stock_raw': variants[vid]['raw_fields']['Stock'],
             'source': variants[vid]['source']} for vid in p['variant_ids']],
        'new_existing_sculpture_binding_established': False,
        'physical_specifications_or_stock_verified': False,
        'dropbox_folder_binding_established': False,
        'new_catalogue_sale_unit_created_or_retired': False,
    })

counts = Counter(x['metadata_review_bucket'] for x in entries)
assert dict(counts) == {'OTHER_EXPLICITLY_DESCRIBED_OBJECT_SOURCE': 24,
                       'PAPER_ART_CARD_PRINT_OR_PHOTOGRAPHY_SOURCE': 98,
                       'HIDDEN_WITHOUT_DESCRIPTION': 3,
                       'WALL_FIXTURE_WITHOUT_CATALOGUE_BINDING': 3}
assert len(known_entries) == 80 and len(entries) == 128
assert sum(len(x['variant_entries']) for x in entries) == 153
payload = {
    'schema': 'boldstone.native-source-coverage-census.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'PREPARED_LOCAL_METADATA_CENSUS_NOT_IMPORTED',
    'sources': [{'path': str(p), 'sha256': v} for p, v in SOURCE_HASHES.items()],
    'scope': '208 accessible native Physical product IDs from authenticated24October export.80 recorded historical Squarespace source-product IDs and128 other product IDs are disjoint and exhaustive for this export. This is not a complete live account/deleted/draft inventory or a proof of sculpture-listing absence.',
    'counts': {'source_native_products': 208, 'source_native_variants': 376,
               'recorded_source_offer_entries': 81, 'recorded_squarespace_source_product_ids': 80,
               'source_offer_without_squarespace_id': len(no_id), 'other_native_product_ids': 128,
               'other_native_variant_ids': 153, 'other_visible_yes_products': 125,
               'other_visible_no_products': 3, 'metadata_buckets': dict(counts),
               'new_confirmed_catalogue_identity_matches': 0},
    'recorded_source_product_id_coverage': known_entries,
    'offer_refs_without_squarespace_id_not_labelled_absent': no_id,
    'other_native_products_metadata_review': entries,
    'important_limits': [
        'Native physical product type does not mean every product is a cast wall sculpture; cards/prints/fixtures retain their explicit source sale units.',
        'Product titles/categories are screening evidence, not physical identities. No whole-library design total or manufacturing claim is added.',
        'Three wall fixtures have no established catalogue or Dropbox-folder binding in this review; retain as source scope questions, without a new owner photo prompt.',
        'Three hidden undescribed records remain content-unknown; hidden does not mean deleted or checkout disabled.',
        'No search, listing, download or mutation outside the authorized Dropbox Wall Sculptures root was performed. No Dropbox reads were needed.',
        'Source images are saved export links only, not new visual or binary checks. No native platform edits or canonical/workbook writes occurred.',
        'The B session owns the nine-new-option matching task; no options were matched here.',
    ],
    'native_platform_shared_or_canonical_writes': 0, 'fresh_live_reads': 0,
    'import_boundary': 'Append-only source-scope evidence for the main writer. Do not add identities, native absence flags, stock statements or image roles. Existing accepted working values and all holds remain unchanged.',
}
with (HERE / 'source-coverage-census.json').open('x', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
    f.write('\n')

E = html.escape


def link(url, label):
    return '<a href="' + E(url, quote=True) + '">' + E(label) + '</a>'


def card(e):
    links = link(e['navigation_url_from_observed_site_and_export_fields'], 'Source listing')
    if e['source_image_urls']:
        links += ' · ' + link(e['source_image_urls'][0], 'Source image')
    else:
        links += ' · No source image URL in export'
    return '<section><h3>' + E(e['title_raw']) + '</h3><p>' + links + '</p><p>' + E(e['metadata_scope_reason']) + '</p><p><code>' + E(e['native_product_id']) + '</code> · SKU' + E(e['header_sku_raw']) + ' · Visible=' + E(e['visible_setting_raw']) + '</p><p>' + E(e['description_text_for_review'] or 'No description in export.') + '</p><p>No Dropbox image/folder binding established by this source-only census.</p></section>'


parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>Other native source products: metadata census</title>',
         '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:1120px;margin:36px auto;padding:0 20px;color:#24303a}section{border-top:1px solid #ccd4dc;margin:24px 0;padding-top:12px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #d1d8df;padding:8px;text-align:left;vertical-align:top}th{background:#eef3f7}a{color:#075b95}td,p,code{overflow-wrap:anywhere}</style><body>',
         '<h1>Other native source products: metadata census</h1>',
         '<p>Local terminal review of the authenticated24October2026 Squarespace Physical CSV. The export has208 products:80 recorded Squarespace source-product IDs and128 other product IDs. All128 have been screened using their exact title, category, description and sale-unit wording. No catalogue identity was added or changed.</p>',
         '<ul><li>98 card/print/paper-art/photography source records.</li><li>24 other explicitly described objects, such as bowls, furniture, bookends, lamps and ornaments.</li><li>3 wall fixtures without an established catalogue binding: two mirrors and a sconce.</li><li>3 hidden undescribed headers: Fabric, Tiles and Wallpaper; contents remain unknown.</li></ul>',
         '<p>This source census does not prove absence of an individual sculpture listing. No live reads, fresh image review, native edits, shared catalogue changes or new photograph questions. The nine-new-option source matching review remains owned by the other session.</p><h2>Wall fixtures retained for source-scope review</h2>']
for e in entries:
    if e['metadata_review_bucket'] == 'WALL_FIXTURE_WITHOUT_CATALOGUE_BINDING':
        parts.append(card(e))
parts.append('<h2>Boundary examples: retain the source sale unit</h2>')
for e in entries:
    if e['native_product_id'] in boundary_notes:
        parts.append(card(e))
parts.append('<h2>Hidden records without descriptions</h2>')
for e in entries:
    if e['metadata_review_bucket'] == 'HIDDEN_WITHOUT_DESCRIPTION':
        parts.append(card(e))
parts += ['<details><summary>All128 source metadata decisions</summary><table><thead><tr><th>Source product</th><th>Category</th><th>Review scope</th><th>SKU / variants</th><th>Record locator</th></tr></thead><tbody>']
for e in entries:
    s = e['source']
    parts.append('<tr><td>' + link(e['navigation_url_from_observed_site_and_export_fields'], e['title_raw']) + '<br>' + (link(e['source_image_urls'][0], 'Image') if e['source_image_urls'] else 'No image URL') + '</td><td>' + E(e['category_raw']) + '</td><td>' + E(e['metadata_review_bucket']) + '<br>' + E(e['metadata_scope_reason']) + '</td><td>' + E(', '.join(x['sku_raw'] for x in e['variant_entries'])) + ' (' + str(len(e['variant_entries'])) + ')</td><td>CSV record' + str(s['csv_record_including_header_1based']) + '; physical lines' + str(s['physical_line_start']) + '-' + str(s['physical_line_end']) + '</td></tr>')
parts += ['</tbody></table></details><p>Source SHA-256:<code>' + SOURCE_HASHES[CSV] + '</code>. Frozen catalogue reference:53e6656a. Main session remains sole catalogue/workbook writer.</p></body></html>']
with (HERE / 'review.html').open('x', encoding='utf-8') as f:
    f.write('\n'.join(parts))
for p, expected in SOURCE_HASHES.items():
    assert sha(p) == expected, str(p)
print(json.dumps({'directory': str(HERE), 'payload_sha256': sha(HERE / 'source-coverage-census.json'), 'counts': payload['counts']}))
