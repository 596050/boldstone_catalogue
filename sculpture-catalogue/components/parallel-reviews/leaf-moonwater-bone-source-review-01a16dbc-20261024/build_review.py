"""Review three retained source galleries locally, preserving all catalogue fields."""
from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from PIL import Image, ImageChops, ImageOps, ImageStat

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = Path(__file__).resolve().parent
REFS = ['O058', 'O059', 'O079']
OPTION_IDS = ['BSI-6581D83760F1', 'BSI-70C7029C1DB1', 'BSI-1E0C826D896E']
SOURCE_RELATED = dict(zip(REFS, OPTION_IDS))
READBACK = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
OFFER_INDEX = B / 'components/evidence/offer_review_index.json'
INVENTORY = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/FRESH_PUBLIC_INVENTORY.json'
NAVIGATION = B / 'components/parallel-reviews/library-primary-reference-audit-01a16dbc-20261024T151647Z/findings.json'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
checks, inputs, local_images, decoded = [], {}, {}, {}


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def check(label, passed, detail=None):
    checks.append({'check': label, 'pass': bool(passed), 'detail': detail})
    if not passed:
        save(H / 'failed-build-diagnostic.json', {'checks': checks})
        raise ValueError(label)


def source(path, expected=None):
    path = Path(path)
    actual = sha(path)
    if expected:
        check('Source hash: ' + str(path), actual == expected)
    inputs[str(path)] = actual
    return read(path)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def normalized(value):
    parser = PlainText()
    parser.feed(value)
    return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()


def image_record(path, role, visually_opened=True):
    path = Path(path)
    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as opened:
        opened.load()
        rgb = ImageOps.exif_transpose(opened).convert('RGB')
        record = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
                  'bytes': len(data), 'stored_dimensions': list(opened.size),
                  'oriented_dimensions': list(rgb.size), 'exif_orientation': opened.getexif().get(274),
                  'decoded_rgb_sha256': hashlib.sha256(rgb.tobytes()).hexdigest(),
                  'full_decode_passed': True, 'role': role,
                  'visually_opened_in_this_review': visually_opened, 'new_download': False}
        local_images[str(path)] = record['sha256']
        decoded[str(path)] = rgb.copy()
        return record


pointer_path = B / 'current-master.json'
pointer = source(pointer_path, '0864dc18f3496f3172b5430de48c1bbfa972858d84bbd38abd13ade424154966')
pointer_sha = sha(pointer_path)
register_path = B / pointer['register']
register = source(register_path, pointer['register_sha256'])
options = {x['product_id']: x for x in register['options']}
assets = source(B / pointer['current_asset_reference_map']['path'], pointer['current_asset_reference_map']['sha256'])
native = source(B / pointer['current_native_reference_map']['path'], pointer['current_native_reference_map']['sha256'])
workbook_path = B / pointer['workbook']
check('Current workbook bytes retained', sha(workbook_path) == pointer['workbook_sha256'])
inputs[str(workbook_path)] = pointer['workbook_sha256']
for path in [register_path.parent / 'image-coverage-current.json',
             B / 'components/reviews/specification_review_progress.json', B / 'components/checkpoint.json', B / 'checkpoint.json']:
    inputs[str(path)] = sha(path)
readback = source(READBACK, '908efcead04e671fdd6f9c32a164a605a53b3a6bf2bad60dfd2305e9dc5bae04')
offer_index = source(OFFER_INDEX, '5ca94881309b8cacdef1a785775e30affa8068780061bc6c45505e34aea80b58')
inventory = source(INVENTORY, '4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd')
navigation = source(NAVIGATION)
for entry in readback['sources']:
    check('Captured export/source bytes: ' + entry['path'], sha(entry['path']) == entry['sha256'])
    inputs[entry['path']] = entry['sha256']
with Path(readback['sources'][1]['path']).open(encoding='utf-8-sig', newline='') as handle:
    export_rows = list(csv.DictReader(handle))

components, selected_by_id = [], {}
for oid in OPTION_IDS:
    option = options[oid]
    asset = assets[option['file_id']]
    prior = next(x for x in navigation['rows'] if x['option_id'] == oid)
    check('Existing active option and selected asset IDs/URLs retained: ' + oid,
          oid in register['active_option_ids'] and all(option[k] == asset[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']))
    check('Recorded selected file and immediate parent retained: ' + oid,
          prior['file_id'] == option['file_id'] and prior['folder_id'] == option['folder_id']
          and asset['path'] == 'ns:202238505/' + prior['native_file_metadata']['path_display']
          and prior['native_folder_metadata']['path_display'] == prior['native_file_metadata']['path_display'].rsplit('/', 1)[0])
    for evidence in prior['evidence']:
        path, expected = evidence['source']['path'], evidence['source']['sha256']
        if path not in inputs:
            source(path, expected)
        else:
            check('Reused native receipt bytes: ' + oid, inputs[path] == expected)
    check('Six complete qualified field objects: ' + oid,
          len(option['master_fields']) == 6 and all(x.get('display') and x.get('state') and 'basis' in x and x.get('source_scopes') and x.get('proposal_ids') for x in option['master_fields'].values()))
    check('Reviewed source remains related without exact-version source promotion: ' + oid,
          REFS[OPTION_IDS.index(oid)] in option['related_platform_offer_refs']
          and REFS[OPTION_IDS.index(oid)] not in option['source_supported_platform_scope_refs'])
    image = image_record(asset['thumb'], 'Saved selected-image rendition; original byte identity not verified')
    image.update({'file_id': option['file_id'], 'recorded_native_content_hash': asset['source_content_hash'],
                  'recorded_native_bytes': asset['bytes'], 'declared_original_path': asset.get('full'),
                  'declared_original_available': bool(asset.get('full')) and Path(asset['full']).is_file(),
                  'native_original_byte_identity_verified': False})
    selected_by_id[option['file_id']] = image
    components.append({k: option[k] for k in ['product_id', 'name', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url', 'master_fields']})
    components[-1].update({'whole_option_sha256': digest(option), 'working_fields_sha256': digest(option['master_fields']),
        'existing_related_offer_refs': option['related_platform_offer_refs'],
        'existing_source_supported_offer_refs': option['source_supported_platform_scope_refs'],
        'saved_selected_rendition': image, 'prior_native_navigation_evidence': prior['evidence'],
        'recorded_native_file_metadata': prior['native_file_metadata'],
        'asset_display_label_differs_from_recorded_native_path': asset['display_path'] != prior['native_file_metadata']['path_display'],
        'asset_display_label_retained': asset['display_path'],
        'navigation_scope': 'Existing URLs and asset.path retained. Leaf Form has an older asset.display_path label; recorded native path and explicit native map use Leaf Form 1 White. No path correction or fresh metadata read.' if oid == OPTION_IDS[0] else 'Saved selected ID, path and immediate parent retained; original observation clocks preserved.'})

FINDINGS = {
    'O058': 'Saved gallery1 corresponds to selected050: square White leaf relief, brick joints, sunlight and shadow align. Galleries2 and3 show two panels in different orientations. This remains the existing single-item source; the paired gallery does not add a sale component or establish an exact LF1/LF2 SKU version. The 40×20×6 cm listing claim remains separate from the accepted 35×35×6 cm working standard.',
    'O059': 'Saved gallery2 corresponds to retained source-reference048, a close-up within the scoop. Selected option photo002 is a different framing and is not claimed as a whole-frame source match. Gallery1 shows a wider square panel on brick. The listing’s 50 cm diameter×8 cm wording remains separate from maker-stated approximately51H×48W cm and5–7 cm side depth. Water function and actual material are not established by the name or photographs.',
    'O079': 'Saved gallery1 corresponds to retained source context001; saved gallery3 corresponds to selected close-up010. Gallery2 shows a water-stream variation of the garden scene. These are display/context evidence with unverified physical-installation and image-production provenance. No operating water system, physical cast or dimension is certified. The listing’s55×55×7 cm claim remains separate from the accepted80×60 cm working version and5–8 cm depth estimate; this family is distinct from the directory session’s pending Bone Spiral filing plan.'
}

cases, references_by_ref = [], {}
for ref in REFS:
    edge = next(x for x in register['source_offer_edges'] if x['offer_ref'] == ref)
    retained = edge['source_offer']
    observed = next(x for x in readback['entries'] if x['offer_ref'] == ref)
    indexed = next(x for x in offer_index if x['ref'] == ref)
    public = next(x for x in inventory['products'] if x['native_product_id'] == retained['sq_id'])
    variants = [x for x in public['variants'] if x['native_variant_id'] == observed['native_variant_id'] and x['sku'] == observed['sku']]
    rows = [x for x in export_rows if x['Product ID [Non Editable]'] == retained['sq_id'] and x['Variant ID [Non Editable]'] == observed['native_variant_id'] and x['SKU'] == observed['sku']]
    check('Exact retained/native/captured-export tuple: ' + ref, len(variants) == len(rows) == 1
          and retained['sq_id'] == indexed['pid'] == observed['native_product_id'] and retained['sku'] == indexed['sku'] == observed['sku'])
    variant, row = variants[0], rows[0]
    check('Default variant has no version attributes or image IDs: ' + ref, not variant['option_attributes'] and not variant['native_image_ids'])
    comparisons = []
    for field in observed['fields']:
        actual = row[field['csv_column']]
        equal = normalized(actual) == normalized(field['historical_value_raw']) if field['comparison'] == 'NORMALIZED_TEXT' else actual == field['historical_value_raw']
        comparisons.append({'field': field['field'], 'csv_column': field['csv_column'], 'comparison': field['comparison'],
            'equal': equal, 'retained_value_raw': field['historical_value_raw'], 'captured_csv_value_raw': actual})
    check('Nine source fields independently agree: ' + ref, len(comparisons) == 9 and all(x['equal'] for x in comparisons)
          and all(retained[x['historical_source_key']] == x['historical_value_raw'] for x in observed['fields']))
    locator = public['source_locator']
    body = source(locator['path'], locator['body_sha256']) if locator['path'] not in inputs else read(locator['path'])
    node = body
    for part in locator['json_pointer'].strip('/').split('/'):
        node = node[int(part)] if isinstance(node, list) else node[part]
    check('Captured locator resolves exact product: ' + ref, sha(locator['path']) == locator['body_sha256'] and node['id'] == retained['sq_id'])
    media = sorted(public['native_media_items'], key=lambda x: x['displayIndex'])
    check('Complete captured gallery order agrees with later admin export: ' + ref, [x['assetUrl'] for x in media] == row['Hosted Image URLs'].split())
    check('Every saved URL belongs to this exact captured product gallery: ' + ref, all(x['url'] in {m['assetUrl'] for m in media} for x in indexed['images']))
    viewed = []
    for item in indexed['images']:
        original_path = Path(item['path'])
        available = original_path.is_file()
        thumb = image_record(item['thumb'], 'Retained source thumbnail', visually_opened=not available)
        original = image_record(original_path, 'Retained source original; bytes rehashed against preserved index') if available else None
        if original:
            check('Saved source original hash: ' + ref + ':' + str(item['order']), original['sha256'] == item['sha256'])
        image = dict(original or thumb)
        image.update({'source_url': item['url'], 'retained_image_order': item['order'],
            'declared_original_path': item['path'], 'declared_original_sha256': item['sha256'],
            'source_original_available': available, 'source_original_bytes_verified_against_preserved_index': available,
            'retained_thumbnail': thumb, 'original': original})
        viewed.append(image)
    viewed_urls = {x['source_url'] for x in viewed}
    gallery = [{'native_media_id': x['id'], 'display_index': x['displayIndex'], 'filename': x.get('filename'), 'url': x['assetUrl'],
        'saved_view_reviewed': x['assetUrl'] in viewed_urls, 'observation_utc': locator['observed_utc']} for x in media]
    check('Single existing BOM member and canonical target retained: ' + ref, len(edge['members']) == 1
          and edge['members'][0]['quantity'] == 1 and edge['members'][0]['position'] == 1
          and edge['members'][0]['canonical_component_targets'] == [options[SOURCE_RELATED[ref]]['canonical_component_id']]
          and retained['sale_unit_state'] == 'Sale component')
    reference = edge['current_primary_reference']
    asset = assets[reference['file_id']]
    check('Existing retained source-reference IDs and URLs retained: ' + ref, all(asset[k] == reference[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']))
    if reference['file_id'] in selected_by_id:
        reference_image = selected_by_id[reference['file_id']]
    else:
        reference_image = image_record(asset['thumb'], 'Saved retained source-reference rendition; distinct from selected option photo')
        reference_image.update({'file_id': reference['file_id'], 'recorded_native_content_hash': asset['source_content_hash'],
            'recorded_native_bytes': asset['bytes'], 'native_original_byte_identity_verified': False,
            'declared_original_path': asset.get('full'), 'declared_original_available': bool(asset.get('full')) and Path(asset['full']).is_file()})
    references_by_ref[ref] = reference_image
    cases.append({'offer_ref': ref, 'title': retained['title'], 'native_product_id': retained['sq_id'], 'native_variant_id': observed['native_variant_id'],
        'sku': retained['sku'], 'related_option_ids': [SOURCE_RELATED[ref]], 'finding': FINDINGS[ref],
        'retained_source_offer': retained, 'retained_BOM_members': edge['members'],
        'retained_current_source_reference': reference, 'saved_source_reference_rendition': reference_image,
        'source_reference_is_selected_option_photo': reference['file_id'] == options[SOURCE_RELATED[ref]]['file_id'],
        'historical_source_url': retained['source_url'], 'captured_export_source_url': observed['current_source_url_from_export'],
        'captured_export_utc': '2026-10-24T00:56:45.467073+00:00', 'captured_native_source_locator': locator,
        'captured_variant': variant, 'raw_dimension_weight_units': retained['raw_units'],
        'source_field_comparisons': comparisons, 'viewed_source_renditions': viewed, 'all_captured_media_records': gallery,
        'gallery_scope': {'captured_media_records': len(media), 'saved_views_reviewed': len(viewed),
                          'unviewed_media_records': sum(not x['saved_view_reviewed'] for x in gallery)},
        'new_source_SKU_assignment_or_platform_pair': False})

photo_comparisons = []
for ref, order, target, role in [('O058', 1, selected_by_id[components[0]['file_id']], 'selected option photograph'),
        ('O059', 2, references_by_ref['O059'], 'retained source detail, distinct from selected002'),
        ('O079', 1, references_by_ref['O079'], 'retained source garden context'),
        ('O079', 3, selected_by_id[components[2]['file_id']], 'selected option photograph')]:
    source_image = next(x for x in next(c for c in cases if c['offer_ref'] == ref)['viewed_source_renditions'] if x['retained_image_order'] == order)
    s, t = decoded[source_image['path']], decoded[target['path']]
    rounding_error = abs(s.width / s.height - t.width / t.height) / (s.width / s.height)
    check('Whole-frame aspect ratio differs only by rendition rounding: ' + ref + ':' + str(order), rounding_error < .003, rounding_error)
    size = (384, round(384 * s.height / s.width))
    delta = ImageChops.difference(s.resize(size, Image.Resampling.LANCZOS), t.resize(size, Image.Resampling.LANCZOS))
    photo_comparisons.append({'offer_ref': ref, 'retained_source_gallery_order': order, 'target_file_id': target['file_id'], 'target_role': role,
        'source_path': source_image['path'], 'source_sha256': source_image['sha256'], 'target_path': target['path'], 'target_sha256': target['sha256'],
        'comparison_size': list(size), 'relative_aspect_ratio_rounding_difference': rounding_error,
        'mean_absolute_RGB_difference_0_to_255': ImageStat.Stat(delta).mean,
        'visual_result': 'Whole-frame photographic correspondence supported by scene framing and local relief/background details.',
        'diagnostic_scope': 'Existing images resized as complete frames; no crop, rotation or threshold was fitted. Different encoded bytes are not claimed equal. Original native bytes and physical identity are unverified.'})

counts = {'source_offers': 3, 'existing_individual_options': 3, 'full_qualified_working_fields': 18,
    'captured_source_field_comparisons': 27, 'captured_media_records': sum(len(x['all_captured_media_records']) for x in cases),
    'source_views_reviewed': sum(len(x['viewed_source_renditions']) for x in cases),
    'source_originals_rehashed_against_preserved_index': sum(x['source_original_available'] for c in cases for x in c['viewed_source_renditions']),
    'source_views_with_only_saved_thumbnail': sum(not x['source_original_available'] for c in cases for x in c['viewed_source_renditions']),
    'selected_renditions_viewed': 3, 'additional_retained_source_reference_renditions_viewed': 2,
    'unviewed_media_records': sum(x['gallery_scope']['unviewed_media_records'] for x in cases),
    'whole_frame_photo_correspondences': 4, 'matched_selected_photo_ids': 2,
    'local_image_files_hashed_and_decoded': len(local_images), 'fresh_native_original_byte_verifications': 0,
    'new_downloads': 0, 'live_calls': 0, 'new_product_records': 0, 'new_platform_pairs': 0,
    'new_source_SKU_assignments': 0, 'new_physical_verifications': 0, 'new_owner_questions': 0, 'native_or_platform_or_shared_writes': 0}
check('Eleven captured gallery records equal eight reviewed views and three unviewed records',
      (counts['captured_media_records'], counts['source_views_reviewed'], counts['unviewed_media_records']) == (11, 8, 3))
check('Five source originals verified; three Bone views remain thumbnail-only',
      (counts['source_originals_rehashed_against_preserved_index'], counts['source_views_with_only_saved_thumbnail']) == (5, 3))
check('Three complete options retain eighteen full fields', len(components) == 3 and sum(len(x['master_fields']) for x in components) == 18)
check('Four correspondences preserve five distinct native rendition roles', len(photo_comparisons) == 4 and len(selected_by_id) + 2 == 5)
check('All eighteen local image files unchanged', len(local_images) == 18 and all(sha(path) == expected for path, expected in local_images.items()))
for path, expected in inputs.items():
    check('Source/protected file unchanged after review: ' + path, sha(path) == expected)

report = {'schema': 'boldstone.read_only_source_component_review.v1', 'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_pointer_sha256': pointer_sha, 'register_sha256': pointer['register_sha256'], 'workbook_sha256': pointer['workbook_sha256'],
    'current_asset_map': pointer['current_asset_reference_map'], 'current_native_map': pointer['current_native_reference_map'],
    'components': components, 'cases': cases, 'photo_comparisons': photo_comparisons, 'counts': counts, 'source_inputs': inputs,
    'local_image_files': local_images,
    'scope': 'Local saved-image and captured-metadata review at original clocks. Four whole-frame photograph correspondences comprise two selected option photographs and two distinct retained source-reference photographs. Moon Water Catcher selected002 remains a different framing. No exact-version source scope is promoted.',
    'source_original_availability': 'Five Leaf Form/Moonwater originals are present and match preserved source hashes. Three Bone Water Spiral temporary originals are absent at their indexed paths; saved thumbnails were reviewed. All five native views are cached renditions, without original-byte verification. This local-path observation is not a global content absence claim.',
    'standing_owner_hold': 'The existing Acanthus physical question remains with its current session. Owner photo holds, working estimates and pending directory move proposals remain unchanged.',
    'application_validation': 'Application code unchanged in this packet. Prior fake-adapter checks remain separate; no new live read, live sandbox run or test result is claimed.'}
save(H / 'review.json', report)

e = html.escape
relative = lambda path: e(quote(os.path.relpath(path, H), safe='/'), quote=True)
parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
    '<title>Leaf Form, Moon Water Catcher and Bone Water Spiral source review</title><style>body{font:16px/1.5 system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;background:#f5f4ef;color:#1d2927}section{padding:1.5rem;background:white;border:1px solid #d8ded9;border-radius:12px;margin:1.5rem 0}a{color:#175d4a;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}figure{margin:0}img{width:100%;height:320px;object-fit:contain;background:#eee}figcaption{font-size:14px}table{width:100%;border-collapse:collapse}td,th{padding:.65rem;border:1px solid #d8ded9;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}td p{white-space:pre-wrap;margin:.2rem 0}summary{cursor:pointer}</style></head><body>',
    '<h1>Leaf Form, Moon Water Catcher and Bone Water Spiral</h1><p>Three retained source offers, three existing options and all18 qualified working fields. Eight saved source views reviewed from11 captured media records; three Bone gallery entries remain unviewed.</p>',
    '<p>Five source originals were rehashed against the preserved index. Native images below are cached renditions. Four whole-frame photograph correspondences preserve the distinct selected and source-reference roles. Photographs do not verify actual size, composition, stock, hardware or water-system operation.</p>',
    '<p><a href="#sources">Source galleries and findings</a> · <a href="review.json">Structured review</a> · <a href="verification.json">Verification receipt</a></p>']
for component in components:
    parts += [f'<section id="{e(component["product_id"])}"><h2>{e(component["name"])}</h2>',
        f'<p><a href="{e(component["image_url"], quote=True)}">Selected Dropbox image</a> · <a href="{e(component["folder_url"], quote=True)}">Containing folder</a></p>',
        f'<figure><a href="{relative(component["saved_selected_rendition"]["path"])}"><img src="{relative(component["saved_selected_rendition"]["path"])}" alt="{e(component["name"], quote=True)}"></a><figcaption>Existing selected image and role retained; saved rendition.</figcaption></figure>',
        '<h3>Complete current working fields</h3><table><tr><th>Field</th><th>Working value and qualification</th></tr>']
    for label, field in component['master_fields'].items():
        parts.append(f'<tr><th>{e(label)}</th><td><p>{e(field["display"])}</p><details><summary>State, basis and full qualified field</summary><pre>{e(json.dumps(field, ensure_ascii=False, indent=2))}</pre></details></td></tr>')
    parts += ['</table></section>']
parts += ['<h2 id="sources">Source records and gallery coverage</h2>']
for case in cases:
    scope, ref = case['gallery_scope'], case['retained_current_source_reference']
    parts += [f'<section id="{e(case["offer_ref"])}"><h2>{e(case["offer_ref"])} · {e(case["title"])}</h2><p>{e(case["finding"])}</p>',
        f'<p><a href="{e(case["captured_export_source_url"], quote=True)}">Captured listing URL</a> · <a href="{e(ref["image_url"], quote=True)}">Retained source-reference image</a> · <a href="{e(ref["folder_url"], quote=True)}">Source-reference folder</a> · <a href="#{case["related_option_ids"][0]}">Current option and full fields</a></p>',
        f'<p>{scope["captured_media_records"]} captured gallery records; {scope["saved_views_reviewed"]} saved views reviewed; {scope["unviewed_media_records"]} records unviewed. Source variant has no version attributes or variant-specific image IDs.</p><div class="grid">']
    for image in case['viewed_source_renditions']:
        qualification = 'Retained original, hash verified' if image['source_original_available'] else 'Saved thumbnail; indexed original unavailable'
        parts.append(f'<figure><a href="{relative(image["path"])}"><img loading="lazy" src="{relative(image["path"])}" alt="{case["offer_ref"]} saved gallery {image["retained_image_order"]}"></a><figcaption>Gallery {image["retained_image_order"]}: {qualification} · <a href="{e(image["source_url"], quote=True)}">Recorded source-image URL</a></figcaption></figure>')
    parts += ['</div><details><summary>Complete source fields, original BOM and captured gallery inventory</summary><pre>' + e(json.dumps(case, ensure_ascii=False, indent=2)) + '</pre></details></section>']
parts += ['<details><summary>Evidence scope and comparison diagnostics</summary><pre>' + e(json.dumps({k: report[k] for k in ['scope', 'source_original_availability', 'counts', 'photo_comparisons', 'application_validation']}, ensure_ascii=False, indent=2)) + '</pre></details></body></html>']
(H / 'index.html').write_text('\n'.join(parts))


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.local, self.fragments, self.ids = [], [], set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id':
                self.ids.add(value)
            if key in ['href', 'src'] and value and not urlsplit(value).scheme:
                if value.startswith('#'):
                    self.fragments.append(value[1:])
                else:
                    self.local.append(H / unquote(urlsplit(value).path))


parser = Links()
parser.feed((H / 'index.html').read_text())
check('All local image/report links resolve', all(x.is_file() for x in parser.local if x.name != 'verification.json'))
check('All internal anchors resolve', all(x in parser.ids for x in parser.fragments))
check('Published pointer unchanged by report rendering', sha(pointer_path) == pointer_sha)
verification = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'checks_passed': len(checks),
    'checks_total': len(checks), 'checks': checks, 'counts': counts, 'register_sha256': pointer['register_sha256'],
    'workbook_sha256': pointer['workbook_sha256'], 'review_sha256': sha(H / 'review.json'), 'html_sha256': sha(H / 'index.html')}
save(H / 'verification.json', verification)
save(H / 'sealed-handoff.json', {'status': 'SEALED_READ_ONLY_SOURCE_COMPONENT_REVIEW', 'recorded_utc': verification['recorded_utc'],
    'source_pointer_sha256': pointer_sha, 'source_offer_refs': REFS, 'counts': counts,
    'files': {n: sha(H / n) for n in ['build_review.py', 'review.json', 'index.html', 'verification.json']}})
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'counts': counts, 'review': str(H / 'index.html'), 'seal_sha256': sha(H / 'sealed-handoff.json')}, ensure_ascii=False))
