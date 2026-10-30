"""Read saved O002/O004 evidence and write only this thread's local review lane."""

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
from urllib.parse import quote, urlsplit

from PIL import Image, ImageChops, ImageOps, ImageStat


BASE = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
OUT = Path(__file__).resolve().parent
REVIEWS = BASE / 'components/reviews'
READBACK = BASE / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
NAVIGATION = BASE / 'components/parallel-reviews/library-primary-reference-audit-01a16dbc-20261024T151647Z/findings.json'
CASES = [
    {
        'offer_ref': 'O002', 'option_id': 'BSI-0922347CC6AE',
        'native_product_id': '6a40cfc5870e0e6bc1e0bb1d',
        'native_variant_id': '5ee52805-9618-44bf-87f6-3e8eb08137ae', 'sku': 'SQ6244576',
        'directory': 'dune-ripple-spiral-review-2026-10-17/gold',
        'gallery_receipt': 'public-gallery-download-receipts.json', 'comparison_index': 1,
        'related_offer_ref': 'O039',
        'finding': 'The saved O002 gallery supports the existing Gold association. Selected Dropbox image 167 and gallery frame 2 show the same photograph, based on the stone joints, edge framing and fine broken-gold pattern. Encoded bytes and decoded pixels differ; this is a visual correspondence, not exact binary equality or a measured cast identity.',
        'scope_notes': [
            'The O002 description states 35 × 21 × 6 cm. Related O039 GDRS-1-35.20 states 35 × 20 × 5 cm; preserve both source claims.',
            'The existing 5 kg working estimate is derived from a separately unit-qualified related offer; selected image 167 remains unweighed.',
            'None of the five O002 gallery frames shows fitted rear hardware. The historical resemblance between Gold-folder rear image 172 and the Copper rear remains a separate unverified association between front and rear.',
        ],
    },
    {
        'offer_ref': 'O004', 'option_id': 'BSI-59530C6155C2',
        'native_product_id': '6a410e3f16d56f3a046ef1d7',
        'native_variant_id': '462d3d37-f550-429b-a84c-cca579fb15b1', 'sku': 'SQ0836319',
        'directory': 'dune-ripple-waves-dr1-review-2026-10-17/verdigris',
        'gallery_receipt': 'public-gallery-complete-receipts.json', 'comparison_index': 0,
        'related_offer_ref': 'O038',
        'finding': 'The saved O004 gallery supports the selected muted Verdigris reference 018. The source front and Dropbox image 018 share stone joints, framing and narrow copper-coloured ridge marks. The brighter, rust-patched O038 front remains a separate pictured version; its specification and historical platform association are not transferred.',
        'scope_notes': [
            'O004 states 35 × 21 × 6 cm; O038 states 35 × 20 × 6 cm and has a different pictured finish. No cast size has been measured here.',
            'The local filename O004-rear.jpg corresponds to public IMG_6103.jpeg. It shows the face and side edge, not the rear or hardware. Preserve the filename as historical evidence and annotate its actual view.',
            'All six O004 gallery frames show the face, side or a face-up panel. The existing keyhole/French-cleat choice does not document fitted hardware.',
        ],
    },
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text())


def save(path: Path, value: object):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def dropbox_hash(data: bytes) -> str:
    return hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def normalized(value: str) -> str:
    parser = TextOnly()
    parser.feed(value)
    return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()


checks = []
inputs = {}


def check(label: str, passed: bool, detail=None):
    checks.append({'check': label, 'pass': bool(passed), 'detail': detail})
    if not passed:
        raise ValueError(label)


def source(path: Path, expected: str | None = None):
    actual = sha(path)
    if expected:
        check('Source hash: ' + str(path), actual == expected)
    inputs[str(path)] = actual
    return load(path)


def image_record(path: Path, expected: str, expected_dropbox: str | None = None):
    data = path.read_bytes()
    check('Saved image SHA256: ' + path.name, hashlib.sha256(data).hexdigest() == expected)
    if expected_dropbox:
        check('Saved original Dropbox content hash: ' + path.name, dropbox_hash(data) == expected_dropbox)
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        orientation = image.getexif().get(274)
        oriented = ImageOps.exif_transpose(image).convert('RGB')
        record = {
            'path': str(path), 'sha256': expected, 'bytes': len(data),
            'stored_dimensions': list(image.size), 'exif_orientation': orientation,
            'oriented_dimensions': list(oriented.size),
            'decoded_rgb_sha256': hashlib.sha256(oriented.tobytes()).hexdigest(),
            'full_decode_passed': True, 'new_download': False,
        }
        return record, oriented.copy()


def rel(path: str | Path) -> str:
    return quote(os.path.relpath(path, OUT), safe='/')


pointer_path = BASE / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = source(pointer_path)
register = source(BASE / pointer['register'], pointer['register_sha256'])
workbook_path = BASE / pointer['workbook']
check('Published workbook hash', sha(workbook_path) == pointer['workbook_sha256'])
inputs[str(workbook_path)] = pointer['workbook_sha256']
native = source(BASE / pointer['current_native_reference_map']['path'], pointer['current_native_reference_map']['sha256'])['current_objects']
assets = source(BASE / pointer['current_asset_reference_map']['path'], pointer['current_asset_reference_map']['sha256'])
readback = source(READBACK, '908efcead04e671fdd6f9c32a164a605a53b3a6bf2bad60dfd2305e9dc5bae04')
navigation = source(NAVIGATION)
for item in readback['sources']:
    check('Retained source bytes: ' + item['path'], sha(Path(item['path'])) == item['sha256'])
    inputs[item['path']] = item['sha256']
export_path = Path(readback['sources'][1]['path'])
with export_path.open(encoding='utf-8-sig', newline='') as handle:
    export_rows = list(csv.DictReader(handle))

cases = []
for config in CASES:
    ref = config['offer_ref']
    option = next(x for x in register['options'] if x['product_id'] == config['option_id'])
    edge = next(x for x in register['source_offer_edges'] if x['offer_ref'] == ref)
    observed = next(x for x in readback['entries'] if x['offer_ref'] == ref)
    saved_navigation = next(x for x in navigation['rows'] if x['option_id'] == config['option_id'])
    selected = assets[option['file_id']]
    file_meta, folder_meta = native[option['file_id']], native[option['folder_id']]
    check(ref + ' selected file/folder IDs agree across option, edge, asset and native maps',
          option['file_id'] == edge['current_primary_reference']['file_id'] == selected['file_id']
          and option['folder_id'] == edge['current_primary_reference']['folder_id'] == selected['folder_id'] == file_meta['parent_id'])
    check(ref + ' containing folder is the actual parent within BOLDSTONE MASTER',
          file_meta['display_path'].rsplit('/', 1)[0] == folder_meta['display_path']
          and file_meta['display_path'].startswith('/BOLDSTONE MASTER/'))
    expected_folder = 'https://www.dropbox.com/home' + quote(folder_meta['display_path'], safe='/')
    expected_image = expected_folder + '?preview=' + quote(file_meta['name'], safe='')
    check(ref + ' exact navigation preserved', option['folder_url'] == selected['folder_url'] == expected_folder
          and option['image_url'] == selected['image_url'] == expected_image)
    check(ref + ' prior native metadata has the same IDs and exact current paths',
          saved_navigation['native_file_metadata']['id'] == option['file_id']
          and saved_navigation['native_folder_metadata']['id'] == option['folder_id']
          and saved_navigation['native_file_metadata']['path_display'] == file_meta['display_path']
          and saved_navigation['native_folder_metadata']['path_display'] == folder_meta['display_path'])
    for evidence in saved_navigation['evidence']:
        source(Path(evidence['source']['path']), evidence['source']['sha256'])
    matching = [r for r in export_rows if r['Product ID [Non Editable]'] == config['native_product_id']
                and r['Variant ID [Non Editable]'] == config['native_variant_id'] and r['SKU'] == config['sku']]
    check(ref + ' one exact export product/variant/SKU tuple', len(matching) == 1)
    row = matching[0]
    check(ref + ' retained readback tuple agrees', all(observed[k] == config[k] for k in ['native_product_id', 'native_variant_id', 'sku']))
    field_comparisons = []
    for field in observed['fields']:
        actual = row[field['csv_column']]
        equal = (normalized(actual) == normalized(field['historical_value_raw'])) if field['comparison'] == 'NORMALIZED_TEXT' else actual == field['historical_value_raw']
        field_comparisons.append({'field': field['field'], 'csv_column': field['csv_column'], 'equal': equal,
                                  'historical_value_raw': field['historical_value_raw'], 'captured_csv_value_raw': actual})
    check(ref + ' nine source fields independently agree with retained source readback', len(field_comparisons) == 9 and all(x['equal'] for x in field_comparisons))
    check(ref + ' current register retained source fields equal the recorded source values',
          all(edge['source_offer'][f['historical_source_key']] == f['historical_value_raw'] for f in observed['fields']))
    check(ref + ' export has no finish/version option attributes', all(not v for k, v in row.items() if k.startswith('Option ')))
    directory = REVIEWS / config['directory']
    originals = source(directory / 'download-receipts.json')
    original = next(x for x in originals if x['id'] == option['file_id'])
    original_record, original_rgb = image_record(Path(original['local_path']), original['sha256'], original['content_hash'])
    check(ref + ' saved original matches current asset size and recorded content hash',
          original_record['bytes'] == selected['bytes'] == saved_navigation['native_file_metadata']['size']
          and original['content_hash'] == selected['source_content_hash'])
    gallery_receipt = source(directory / config['gallery_receipt'])
    gallery_receipt = gallery_receipt if isinstance(gallery_receipt, list) else gallery_receipt['gallery']
    gallery = []
    gallery_rgbs = []
    for index, item in enumerate(gallery_receipt):
        record, rgb = image_record(Path(item['local_path']), item['sha256'])
        record.update({'source_url': item.get('url', item.get('source_url')), 'gallery_position': index + 1,
                       'saved_observation_utc': item.get('checked_utc'),
                       'observed_view': 'face or side; no rear hardware visible'})
        if ref == 'O004' and Path(item['local_path']).name == 'O004-rear.jpg':
            record['filename_annotation'] = 'Historical filename retained; image is face and side edge, not a rear view.'
        gallery.append(record)
        gallery_rgbs.append(rgb)
    check(ref + ' all captured export gallery URLs match the saved gallery order', row['Hosted Image URLs'].split() == [x['source_url'] for x in gallery])
    comparison = gallery_rgbs[config['comparison_index']]
    check(ref + ' comparison image has the same oriented dimensions', original_rgb.size == comparison.size)
    difference = ImageChops.difference(original_rgb, comparison)
    comparison_record = {
        'saved_native_image': original_record['path'],
        'saved_source_image': gallery[config['comparison_index']]['path'],
        'gallery_position': config['comparison_index'] + 1,
        'exact_encoded_bytes_equal': original_record['sha256'] == gallery[config['comparison_index']]['sha256'],
        'exact_decoded_pixels_equal': difference.getbbox() is None,
        'mean_absolute_rgb_difference_0_to_255': ImageStat.Stat(difference).mean,
        'metric_interpretation': 'Diagnostic only. No numeric threshold certifies photographic or physical specimen identity.',
        'visual_assessment': config['finding'],
    }
    related = next(x['source_offer'] for x in register['source_offer_edges'] if x['offer_ref'] == config['related_offer_ref'])
    extra = []
    if ref == 'O004':
        receipts = source(directory / 'public-image-http-receipts.json')
        contrast = next(x for x in receipts if Path(x['local_path']).name == 'O038-front.jpg')
        contrast_record, _ = image_record(Path(contrast['local_path']), contrast['sha256'])
        contrast_record.update({'source_url': contrast['source_url'], 'role': 'Separate O038 bright turquoise/rust comparison; no transfer of specifications'})
        extra.append(contrast_record)
        public_receipts = source(directory / 'public-page-http-receipts.json')
        capture_clocks = [{'source_url': x['source_url'], 'recorded_utc': x.get('checked_utc'), 'http_status': x['http_status']} for x in public_receipts]
    else:
        capture_clocks = source(directory / 'public-source-receipts.json')
        source(directory / 'rear-source-comparison.json')
    check(ref + ' all six current qualified field objects retained in full', len(option['master_fields']) == 6 and all(isinstance(x, dict) and x.get('basis') for x in option['master_fields'].values()))
    cases.append({**{k: config[k] for k in ['offer_ref', 'option_id', 'native_product_id', 'native_variant_id', 'sku', 'finding', 'scope_notes']},
        'name': option['name'], 'file_id': option['file_id'], 'folder_id': option['folder_id'],
        'image_url': option['image_url'], 'folder_url': option['folder_url'],
        'working_fields': option['master_fields'], 'working_fields_sha256': digest(option['master_fields']),
        'whole_option_sha256': digest(option), 'historical_source_offer': edge['source_offer'],
        'related_source_offer': related, 'source_field_comparisons': field_comparisons,
        'captured_export_utc': '2026-10-24T00:56:45.467073+00:00',
        'export_product_variant_locator': observed['source'], 'native_navigation_evidence': saved_navigation['evidence'],
        'public_page_capture_clocks_and_access_results': capture_clocks,
        'saved_native_original': original_record, 'saved_public_gallery': gallery,
        'image_comparison': comparison_record, 'other_saved_comparisons': extra,
        'new_physical_or_platform_binding': False})

report = {
    'schema': 'boldstone.read_only_source_photo_review.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'PASS', 'source_pointer_sha256': pointer_sha,
    'register_sha256': pointer['register_sha256'], 'workbook_sha256': pointer['workbook_sha256'],
    'current_native_map_sha256': pointer['current_native_reference_map']['sha256'],
    'current_asset_map_sha256': pointer['current_asset_reference_map']['sha256'],
    'cases': cases, 'source_inputs': inputs,
    'scope': {'existing_options': 2, 'full_qualified_working_field_objects': 12, 'source_csv_fields': 18,
              'saved_public_gallery_files': 11, 'saved_selected_originals': 2, 'saved_separate_comparison_files': 1,
              'new_downloads': 0, 'live_api_or_browser_reads': 0, 'native_or_platform_writes': 0,
              'shared_canonical_writes': 0, 'new_products_or_platform_pairs': 0, 'new_physical_verifications': 0,
              'owner_questions_issued': 0},
    'interpretation': 'Saved-source review at original observation clocks. No current live offer, physical stock, cast dimensions, composition or fitted hardware was independently verified. Current owner-controlled working commercial fields remain distinct from historical source prices/settings.'}
save(OUT / 'review.json', report)

e = html.escape
parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>Dune Ripple Gold and Verdigris source review</title><style>body{font:16px/1.5 system-ui;margin:2rem auto;padding:0 1rem;max-width:1200px;color:#172522;background:#f7f6f2}section{background:white;padding:1.5rem;margin:1.5rem 0;border:1px solid #d3d9d4;border-radius:12px}a{color:#175b4e;overflow-wrap:anywhere}figure{margin:0}img{width:100%;height:330px;object-fit:contain;background:#eee}figcaption{font-size:14px}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem}table{width:100%;border-collapse:collapse}td,th{border:1px solid #d3d9d4;padding:.65rem;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.note{color:#42564e}summary{cursor:pointer}td p{margin:.3rem 0}</style>',
         '<h1>Dune Ripple source photographs and working details</h1>',
         '<p>Two existing options reviewed from saved evidence. Open the selected image and its current containing folder below. Source galleries retain their capture dates; full qualified working fields are shown separately.</p>',
         '<p class="note">' + e(report['interpretation']) + '</p>']
for case in cases:
    parts += [f'<section id="{e(case["offer_ref"])}"><h2>{e(case["name"])} · {e(case["offer_ref"])}</h2>',
              f'<p><a href="{e(case["image_url"], quote=True)}">Selected Dropbox image</a> · <a href="{e(case["folder_url"], quote=True)}">Current containing folder</a> · <a href="{e(case["historical_source_offer"]["source_url"], quote=True)}">Source listing link</a></p>',
              f'<p>{e(case["finding"])}</p><ul>' + ''.join('<li>' + e(x) + '</li>' for x in case['scope_notes']) + '</ul>',
              '<div class="gallery">']
    visuals = [(case['saved_native_original'], 'Selected original retained locally')]
    visuals += [(x, f'Saved source gallery {x["gallery_position"]}' + (' · face and side edge (historical filename: O004-rear.jpg)' if 'filename_annotation' in x else '')) for x in case['saved_public_gallery']]
    visuals += [(x, x['role']) for x in case['other_saved_comparisons']]
    for record, caption in visuals:
        url = e(rel(record['path']), quote=True)
        parts += [f'<figure><a href="{url}"><img loading="lazy" src="{url}" alt="{e(caption, quote=True)}"></a><figcaption>{e(caption)}<br>{e(Path(record["path"]).name)}</figcaption></figure>']
    parts += ['</div><h3>Current working catalogue fields</h3><table><tr><th>Field</th><th>Working value and qualification</th></tr>']
    for name, field in case['working_fields'].items():
        parts += [f'<tr><th>{e(name)}</th><td><p>{e(field["display"])}</p><details><summary>State, basis and complete field object</summary><pre>{e(json.dumps(field, ensure_ascii=False, indent=2))}</pre></details></td></tr>']
    parts += ['</table><details><summary>Saved source tuples, clocks, image integrity and comparison</summary><pre>' + e(json.dumps({k: v for k, v in case.items() if k != 'working_fields'}, ensure_ascii=False, indent=2)) + '</pre></details></section>']
parts += ['<p><a href="review.json">Structured review</a> · <a href="verification.json">Verification receipt</a></p></html>']
(OUT / 'index.html').write_text('\n'.join(parts))

class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(v for k, v in attrs if k in ('href', 'src') and v)


from urllib.parse import unquote

parser = LocalLinks()
parser.feed((OUT / 'index.html').read_text())
local_urls = [x for x in parser.urls if not urlsplit(x).scheme and not x.startswith('#')]
# The verification receipt is written immediately below; all other targets must already exist.
check('Every local review image/link resolves', all((OUT / unquote(urlsplit(x).path)).is_file() for x in local_urls if x != 'verification.json'), len(local_urls))
check('Published pointer unchanged during local review', sha(pointer_path) == pointer_sha)
for path, expected in inputs.items():
    check('Source unchanged after review: ' + path, sha(Path(path)) == expected)
verification = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'passed': len(checks),
                'failed': 0, 'checks': checks, 'report_sha256': sha(OUT / 'review.json'),
                'html_sha256': sha(OUT / 'index.html'), 'script_sha256': sha(Path(__file__)),
                'scope': report['scope']}
save(OUT / 'verification.json', verification)
save(OUT / 'sealed-handoff.json', {'status': 'SEALED_READ_ONLY_REVIEW', 'recorded_utc': verification['recorded_utc'],
    'source_pointer_sha256': pointer_sha, 'register_sha256': pointer['register_sha256'],
    'workbook_sha256': pointer['workbook_sha256'],
    'files': {n: sha(OUT / n) for n in ['review.py', 'review.json', 'index.html', 'verification.json']},
    'scope': report['scope']})
for case in cases:
    print(case['offer_ref'], case['name'])
    print('Image:', case['image_url'])
    print('Folder:', case['folder_url'])
    print('Finding:', case['finding'])
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'review': str(OUT / 'index.html'),
                  'seal_sha256': sha(OUT / 'sealed-handoff.json'), 'scope': report['scope']}, ensure_ascii=False))
