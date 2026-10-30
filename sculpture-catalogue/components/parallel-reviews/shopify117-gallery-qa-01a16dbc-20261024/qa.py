"""Bounded serialized proof/link QA of the final117-frame Shopify wall gallery review."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image, ImageOps

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = B.parent / 'reports/shopify-wall-gallery-review-20261024-root'
OUT = Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
checks, image_proofs = [], {}


def check(name, condition):
    checks.append({'check': name, 'pass': bool(condition)})
    assert condition, name


def image_proof(path, expected, dimensions=None):
    if path not in image_proofs:
        with Image.open(path) as opened:
            opened.load()
            stored = list(opened.size)
            oriented = list(ImageOps.exif_transpose(opened).size)
            proof = {'sha256': sha(path), 'bytes': Path(path).stat().st_size, 'stored_dimensions': stored,
                     'oriented_dimensions': oriented, 'format': opened.format, 'full_decode_passed': True}
        image_proofs[path] = proof
    proof = image_proofs[path]
    return proof['sha256'] == expected and (dimensions is None or dimensions in [proof['stored_dimensions'], proof['oriented_dimensions']])


def decoded_dropbox_path(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    for prefix in ['/home', '/preview']:
        if path.startswith(prefix + '/'):
            path = path[len(prefix):]
            break
    preview = parse_qs(parsed.query).get('preview')
    return path.rstrip('/') + ('/' + preview[0] if preview else '')


seal = read(H / 'sealed-handoff.json')
check('Exact117-frame handed-off seal', sha(H / 'sealed-handoff.json') == '1cfcbdaf6107391788876fd8e29abb6c9a0d4ab172acb3887b05d5f36db3246b')
for path, expected in seal['files'].items():
    check('Every final provider artifact exact: ' + path, sha(path) == expected)
j = read(H / 'shopify-wall-gallery-visual-review.json')
for key in ['local_shopify_csv', 'crosswalk', 'native_inventory', 'native_visual_evidence', 'squarespace_gallery_input_snapshot']:
    ref = j[key]
    check('Exact input identity: ' + key, sha(ref['path']) == ref['sha256'])
for path, expected in j['protected_current_files'].items():
    check('Canonical protected file unchanged: ' + path, sha(path) == expected)
check('Provider verification724 checks all pass', read(H / 'verification.json')['status'] == 'PASS' and read(H / 'verification.json')['checks_passed'] == read(H / 'verification.json')['checks_total'] == 724)
raw_rows, physical = {}, {}
with Path(j['local_shopify_csv']['path']).open(encoding='utf-8-sig', newline='') as handle:
    reader = csv.DictReader(handle)
    _ = reader.fieldnames
    logical = 2
    while True:
        start = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        raw_rows[logical], physical[logical] = row, (start, reader.line_num)
        logical += 1
crosswalk = read(j['crosswalk']['path'])
wall_products = {x['handle']: x for x in crosswalk['local_shopify_records'] if x['product']['in_preserved_wall_subset']}
expected_occurrences = {(x['handle'], m['source_row']['logical_row_including_header']) for x in wall_products.values() for m in x['full_product_gallery']}
records = j['records']
check('Exact117 local wall media occurrences across38 products', len(records) == len(expected_occurrences) == 117 and {(x['handle'], x['exported_gallery_row']['source_row']['logical_row_including_header']) for x in records} == expected_occurrences and len({x['handle'] for x in records}) == 38)
check('All117 unique review IDs and exported image URLs', {x['review_id'] for x in records} == {'S' + str(n).zfill(3) for n in range(1, 118)} and len({x['exported_gallery_row']['image_src'] for x in records}) == 117)
inventory = read(j['native_inventory']['path'])
visual = {x['file_id']: x for x in read(j['native_visual_evidence']['path'])}
hash_receipt_path = B.parent / 'reports/dropbox-wall-complete-role-review-20261024T214349Z/fresh-all-6360-native-hash-metadata.json'
check('Exact independently retained current native hash receipt', sha(hash_receipt_path) == '94adfd135a45e2de9cf78b1f9c83d8494bbc029c297ab33139123410f7cafb05')
hashes = {x['id']: x for x in read(hash_receipt_path)['entries']}
sq = {x['gallery_entry_id']: x for x in read(j['squarespace_gallery_input_snapshot']['path'])}
uncertain, positives, sq_none, sq_yes = [], [], [], []
for record in records:
    rid, exported = record['review_id'], record['exported_gallery_row']
    locator = exported['source_row']
    raw = raw_rows[locator['logical_row_including_header']]
    product = wall_products[record['handle']]
    check('Exact original CSV handle/image/position/alt/blank variant image: ' + rid,
        record['handle'] == exported['handle'] == raw['Handle'] and exported['image_src'] == raw['Image Src']
        and exported['image_position_raw'] == raw['Image Position'] and exported['image_alt_raw'] == raw['Image Alt Text']
        and exported['variant_image_raw'] == raw['Variant Image'] == '')
    check('Exact logical and physical CSV source locator: ' + rid, locator['path'] == j['local_shopify_csv']['path']
        and (locator['physical_line_start'], locator['physical_line_end']) == physical[locator['logical_row_including_header']])
    check('Raw product SKUs and matched source refs retained: ' + rid, record['exported_skus'] == [x['sku_raw'] for x in product['variants']]
        and record['matched_squarespace_offer_refs'] == product['matched_squarespace_offer_refs'])
    downloaded = record['source_download']
    check('Fetched source file binds exact exported URL and recorded bytes: ' + rid, downloaded['requested_url'] == exported['image_src']
        and downloaded['http_status'] == 200 and downloaded['bytes'] == Path(downloaded['path']).stat().st_size
        and image_proof(downloaded['path'], downloaded['sha256'], downloaded['dimensions'])
        and downloaded['export_date_and_live_product_presence_not_verified'] is True)
    match = record['native_photo_correspondence']
    alternative = record['native_scene_or_design_candidate']
    if match:
        positives.append(rid)
        check('Positive photograph match has no competing accepted scene-only target: ' + rid, alternative is None
            and record['native_correspondence_disposition'] in ['VISUALLY_CORRESPONDING_PHOTOGRAPH_AT_DISPLAYED_RESOLUTION', 'VISUAL_CROP_FRAMING_OR_CONTRAST_RENDITION_CORRESPONDENCE'])
    else:
        uncertain.append(rid)
        check('Scene/design candidate remains explicitly unresolved: ' + rid, alternative is not None and record['native_correspondence_disposition'] == 'SAME_SCENE_OR_DESIGN_CANDIDATE_EXACT_PHOTOGRAPH_UNRESOLVED')
    target = match or alternative
    native, view = target['native_reference'], target['visual_source']
    fid = target['file_id']
    check('Exact current native ID/reference and actual parent: ' + rid, native == inventory[fid] and view == visual[fid]
        and inventory[native['folder_id']]['path'] == native['path'].rsplit('/', 1)[0]
        and native['parent_id'] == native['folder_id'])
    check('Current image and containing-folder URLs resolve to exact observed paths: ' + rid,
        decoded_dropbox_path(native['image_url']) == native['display_path'] and decoded_dropbox_path(native['folder_url']) == native['folder_path'])
    check('Displayed native image hash and recorded current-source hash bound: ' + rid, image_proof(view['source_image_path'], view['actual_visual_source_sha256'], view['source_dimensions'])
        and view['native_content_hash'] == hashes[fid]['content_hash'])
    if view['original_bytes_rehashed_current']:
        data = Path(view['source_image_path']).read_bytes()
        content = hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()
        check('Any claimed native original bytes actually match current hash/size: ' + rid, content == hashes[fid]['content_hash'] and len(data) == hashes[fid]['size'])
    else:
        check('Native preview remains qualified as derivative evidence: ' + rid, view['visual_source_kind'] == 'CACHED_DERIVATIVE_WITH_CURRENT_NATIVE_SOURCE_HASH_BINDING')
    for field in ['exact_encoded_original_bytes_or_pixel_identity_claimed', 'new_physical_specification_or_cast_identity_verified', 'variant_specific_assignment_certified', 'stock_price_or_configuration_field_transfer', 'installation_creation_origin_newly_verified', 'new_component_or_finish_record_created', 'canonical_binding_applied']:
        check('No authority promotion ' + field + ': ' + rid, record[field] is False)
    if record['squarespace_photo_correspondences']:
        sq_yes.append(rid)
    else:
        sq_none.append(rid)
    for match_sq in record['squarespace_photo_correspondences']:
        original = sq[match_sq['gallery_entry_id']]
        check('Exact retained Squarespace source-frame identity and original rendition: ' + rid + ':' + match_sq['gallery_entry_id'], match_sq['offer_ref'] == original['offer_ref']
            and match_sq['gallery_order'] == original['gallery_order'] and match_sq['source_url'] == original['source_url']
            and match_sq['squarespace_product_id'] == original['native_product_id'] and match_sq['selected_rendition'] == original['selected_rendition']
            and match_sq['variant_specific_assignment_certified'] is False)
        rendition = match_sq['selected_rendition']
        check('Retained Squarespace rendition bytes/decode preserved: ' + rid + ':' + match_sq['gallery_entry_id'], rendition['available'] is True
            and image_proof(rendition['path'], rendition['sha256'], rendition['dimensions']))
check('Only S016/S021/S022 remain scene-only candidates', uncertain == ['S016', 'S021', 'S022'] and len(positives) == 114)
check('Exactly110 distinct accepted current native photo IDs', len({x['native_photo_correspondence']['file_id'] for x in records if x['native_photo_correspondence']}) == 110)
check('Exactly115 Squarespace correspondences and two explicit unmatched frames', len(sq_yes) == 115 and sq_none == ['S006', 'S019'])
check('Source roles exhaustive and qualified', dict(Counter(x['source_visual_role'] for x in records)) == j['counts']['source_role_counts'] == {'detail': 18, 'group': 41, 'individual': 19, 'installation': 30, 'group_detail': 9})
check('Held gaps and Frozen Fish dimensions retained', j['frozen_holds'] == {'installation_gaps': 22, 'series_gaps': 1, 'legacy_frozen_fish_identity': 'DEFERRED_OWNER_QUESTION_OWNED_BY_RECOVERY', 'Frozen_Fish_current_dimensions': '70 H x 15 W cm', 'no_squarespace_writes': True})


class HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.urls = set(), []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id' and value:
                self.ids.add(value)
            if key in ['href', 'src'] and value:
                self.urls.append(value)


page = HTML()
page.feed((H / 'index.html').read_text())
check('All117 source reader section IDs exist', {x['review_id'] for x in records} <= page.ids)
for url in page.urls:
    parsed = urlsplit(url)
    if parsed.scheme in ['', 'file']:
        target = Path(unquote(parsed.path)) if parsed.path else H / 'index.html'
        target = target if target.is_absolute() else H / target
        check('Local reader image/report link resolves: ' + url, target.is_file())
        if parsed.fragment:
            other = HTML()
            other.feed(target.read_text())
            check('Local reader fragment resolves: ' + url, unquote(parsed.fragment) in other.ids)
check('All117 native target image/folder links and source gallery URLs rendered', all((x['native_photo_correspondence'] or x['native_scene_or_design_candidate'])['native_reference'][k] in page.urls for x in records for k in ['image_url', 'folder_url']) and all(x['exported_gallery_row']['image_src'] in page.urls for x in records))
acceptance = read(H / 'terminal-reader-acceptance.json')
log_path = H / 'all-38-terminal-product-readouts.txt'
check('Terminal reader117 anchors and exact38-product log retained', acceptance['reader_sha256'] == sha(H / 'index.html') and acceptance['new_gallery_seal_sha256'] == sha(H / 'sealed-handoff.json') and acceptance['source_image_anchors_present'] == 117 and acceptance['terminal_log_sha256'] == sha(log_path)
    and len([line for line in log_path.read_text().splitlines() if line.startswith('PRODUCT ')]) == 38)
for path, expected in j['protected_current_files'].items():
    check('Canonical inputs still unchanged at end: ' + path, sha(path) == expected)
check('Exact final provider seal still unchanged', sha(H / 'sealed-handoff.json') == '1cfcbdaf6107391788876fd8e29abb6c9a0d4ab172acb3887b05d5f36db3246b')
receipt = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'source_seal_sha256': sha(H / 'sealed-handoff.json'), 'source_review_sha256': sha(H / 'shopify-wall-gallery-visual-review.json'),
    'counts': j['counts'], 'image_files_independently_hashed_and_decoded': len(image_proofs),
    'scope': 'Bounded serialized source/row/hash/current-ID/parent/qualification and117-reader-link QA. Provider visual findings retain their displayed-resolution and crop qualifications; this is not a second117-frame visual adjudication. No fullR5 rerun, live call, new alias, variant image or physical/stock specification.'}
(OUT / 'readback.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
(OUT / 'image-proof-readback.json').write_text(json.dumps(image_proofs, indent=2) + '\n')
(OUT / 'sealed-handoff.json').write_text(json.dumps({'status': 'PASS', 'files': {n: sha(OUT / n) for n in ['qa.py', 'readback.json', 'image-proof-readback.json']}}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'images_hashed_decoded': len(image_proofs), 'readback_sha256': sha(OUT / 'readback.json'), 'seal_sha256': sha(OUT / 'sealed-handoff.json')}))
