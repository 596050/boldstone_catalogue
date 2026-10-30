"""Review retained Moonphase renditions and source metadata, with no live access."""
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
REFS = ['O010', 'O065', 'O070', 'O074', 'O075']
OPTION_IDS = ['BSI-8C0D9152DF73', 'BSI-41E5370B1314', 'BSI-93FC0B4F78DA', 'BSI-DF431D2D9F15']
SOURCE_RELATED = {'O010': OPTION_IDS[:3], 'O065': OPTION_IDS[:1], 'O070': OPTION_IDS[3:],
                  'O074': OPTION_IDS[1:2], 'O075': OPTION_IDS[2:3]}
PHOTO_COMPARISONS = [('O010', 2, OPTION_IDS[0]), ('O010', 3, OPTION_IDS[1]),
                     ('O065', 1, OPTION_IDS[0]), ('O074', 1, OPTION_IDS[1]),
                     ('O075', 1, OPTION_IDS[2]), ('O070', 1, OPTION_IDS[3])]
READBACK = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
OFFER_INDEX = B / 'components/evidence/offer_review_index.json'
INVENTORY = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/FRESH_PUBLIC_INVENTORY.json'
NAVIGATION = B / 'components/parallel-reviews/library-primary-reference-audit-01a16dbc-20261024T151647Z/findings.json'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())
digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
checks, inputs, local_renditions, decoded = [], {}, {}, {}


def check(label, passed, detail=None):
    checks.append({'check': label, 'pass': bool(passed), 'detail': detail})
    if not passed:
        raise ValueError(label)


def source(path, expected=None):
    path = Path(path)
    actual = sha(path)
    if expected:
        check('Source hash: ' + str(path), actual == expected)
    inputs[str(path)] = actual
    return read(path)


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def dropbox_hash(data):
    return hashlib.sha256(b''.join(hashlib.sha256(data[i:i + 4194304]).digest() for i in range(0, len(data), 4194304))).hexdigest()


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


def rendition(path, role, source_url=None, declared_original=None):
    path = Path(path)
    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as opened:
        opened.load()
        rgb = ImageOps.exif_transpose(opened).convert('RGB')
        record = {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
                  'bytes': len(data), 'stored_dimensions': list(opened.size),
                  'oriented_dimensions': list(rgb.size), 'exif_orientation': opened.getexif().get(274),
                  'decoded_rgb_sha256': hashlib.sha256(rgb.tobytes()).hexdigest(),
                  'full_decode_passed': True, 'role': role, 'source_url': source_url,
                  'visually_opened_in_this_review': True, 'new_download': False,
                  'public_source_original_bytes_verified': False}
        if declared_original:
            record['declared_temporary_original_path'] = str(declared_original)
            record['declared_temporary_original_available'] = Path(declared_original).is_file()
        local_renditions[str(path)] = record['sha256']
        decoded[str(path)] = rgb.copy()
        return record


pointer_path = B / 'current-master.json'
pointer = source(pointer_path)
pointer_sha = sha(pointer_path)
register_path = B / pointer['register']
register = source(register_path, pointer['register_sha256'])
options = {x['product_id']: x for x in register['options']}
assets = source(B / pointer['current_asset_reference_map']['path'], pointer['current_asset_reference_map']['sha256'])
native_path = B / pointer['current_native_reference_map']['path']
check('Explicit native map bytes retained', sha(native_path) == pointer['current_native_reference_map']['sha256'])
inputs[str(native_path)] = sha(native_path)
workbook_path = B / pointer['workbook']
check('Current workbook bytes retained', sha(workbook_path) == pointer['workbook_sha256'])
inputs[str(workbook_path)] = pointer['workbook_sha256']
audit_path = register_path.parent / 'image-coverage-current.json'
inputs[str(audit_path)] = sha(audit_path)
for name in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']:
    inputs[str(B / name)] = sha(B / name)
readback = source(READBACK, '908efcead04e671fdd6f9c32a164a605a53b3a6bf2bad60dfd2305e9dc5bae04')
offer_index = source(OFFER_INDEX, '5ca94881309b8cacdef1a785775e30affa8068780061bc6c45505e34aea80b58')
inventory = source(INVENTORY, '4445986b548ef256c7ab2f4f8c80f34ade0f590ce9e9e6adbdf4ea9118726bfd')
navigation = source(NAVIGATION)
for entry in readback['sources']:
    check('Captured export/source bytes: ' + entry['path'], sha(entry['path']) == entry['sha256'])
    inputs[entry['path']] = entry['sha256']
export_path = Path(readback['sources'][1]['path'])
with export_path.open(encoding='utf-8-sig', newline='') as handle:
    export_rows = list(csv.DictReader(handle))

components = []
for oid in OPTION_IDS:
    option = options[oid]
    asset = assets[option['file_id']]
    check('Existing option is active: ' + oid, oid in register['active_option_ids'])
    check('Selected image/folder matches explicit current asset map: ' + oid,
          all(option[k] == asset[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url'])
          and asset['path'].startswith('ns:202238505//BOLDSTONE MASTER/'))
    prior = next(x for x in navigation['rows'] if x['option_id'] == oid)
    check('Prior selected native metadata has exact same IDs and paths: ' + oid,
          prior['file_id'] == option['file_id'] and prior['folder_id'] == option['folder_id']
          and prior['native_file_metadata']['path_display'] == asset['display_path']
          and prior['native_folder_metadata']['path_display'] == asset['display_path'].rsplit('/', 1)[0])
    for evidence in prior['evidence']:
        path, expected = evidence['source']['path'], evidence['source']['sha256']
        if path not in inputs:
            source(path, expected)
        else:
            check('Reused native evidence source identity: ' + oid, inputs[path] == expected)
    check('Six complete current field objects: ' + oid, len(option['master_fields']) == 6
          and all(x.get('display') and x.get('state') and 'basis' in x and x.get('source_scopes') and x.get('proposal_ids') for x in option['master_fields'].values()))
    image = rendition(asset['thumb'], 'Recorded selected-image rendition; original byte identity not reverified', declared_original=asset.get('full'))
    image['recorded_native_content_hash'] = asset['source_content_hash']
    image['cached_dropbox_content_hash'] = dropbox_hash(Path(asset['thumb']).read_bytes())
    image['cached_native_original_matches_recorded_hash'] = image['cached_dropbox_content_hash'] == asset['source_content_hash'] and image['bytes'] == asset['bytes']
    image['native_original_verification_scope'] = 'Compared local cache bytes with recorded asset-map content hash and size; no fresh native metadata or binary read.'
    if image['cached_native_original_matches_recorded_hash']:
        image['role'] = 'Retained cached native original; size and Dropbox content hash match recorded asset metadata'
    components.append({k: option[k] for k in ['product_id', 'name', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url', 'master_fields']})
    components[-1].update({'whole_option_sha256': digest(option), 'working_fields_sha256': digest(option['master_fields']),
                           'existing_related_offer_refs': option['related_platform_offer_refs'],
                           'existing_source_supported_offer_refs': option['source_supported_platform_scope_refs'],
                           'saved_selected_rendition': image, 'prior_native_navigation_evidence': prior['evidence']})
    if oid in OPTION_IDS[:3]:
        check('O010 remains related gallery scope, without source-supported individual offer promotion: ' + oid,
              'O010' in option['related_platform_offer_refs'] and 'O010' not in option['source_supported_platform_scope_refs'])

cases = []
for ref in REFS:
    edge = next(x for x in register['source_offer_edges'] if x['offer_ref'] == ref)
    retained = edge['source_offer']
    observed = next(x for x in readback['entries'] if x['offer_ref'] == ref)
    indexed = next(x for x in offer_index if x['ref'] == ref)
    public = next(x for x in inventory['products'] if x['native_product_id'] == retained['sq_id'])
    variant = [x for x in public['variants'] if x['native_variant_id'] == observed['native_variant_id'] and x['sku'] == observed['sku']]
    row = [x for x in export_rows if x['Product ID [Non Editable]'] == retained['sq_id']
           and x['Variant ID [Non Editable]'] == observed['native_variant_id'] and x['SKU'] == observed['sku']]
    check('Exact retained/native/captured-export tuple: ' + ref, len(variant) == len(row) == 1
          and retained['sq_id'] == indexed['pid'] == observed['native_product_id']
          and retained['sku'] == indexed['sku'] == observed['sku'])
    variant, row = variant[0], row[0]
    check('Captured native variant has no version attributes or variant-specific image IDs: ' + ref,
          not variant['option_attributes'] and not variant['native_image_ids'])
    comparisons = []
    for field in observed['fields']:
        actual = row[field['csv_column']]
        equal = normalized(actual) == normalized(field['historical_value_raw']) if field['comparison'] == 'NORMALIZED_TEXT' else actual == field['historical_value_raw']
        comparisons.append({'field': field['field'], 'csv_column': field['csv_column'], 'equal': equal,
                            'retained_value_raw': field['historical_value_raw'], 'captured_csv_value_raw': actual})
    check('Nine captured export fields agree with retained register source: ' + ref, len(comparisons) == 9 and all(x['equal'] for x in comparisons)
          and all(retained[x['historical_source_key']] == x['historical_value_raw'] for x in observed['fields']))
    locator = public['source_locator']
    if locator['path'] not in inputs:
        source(locator['path'], locator['body_sha256'])
    else:
        check('Captured native body identity: ' + ref, inputs[locator['path']] == locator['body_sha256'])
    body = read(locator['path'])
    node = body
    for part in locator['json_pointer'].strip('/').split('/'):
        node = node[int(part)] if isinstance(node, list) else node[part]
    check('Captured product locator resolves exact product ID: ' + ref, node['id'] == retained['sq_id'])
    media = public['native_media_items']
    media_urls = {x['assetUrl'] for x in media}
    check('Every retained source rendition URL belongs to the captured exact product gallery: ' + ref,
          all(x['url'] in media_urls for x in indexed['images']))
    viewed = []
    for item in indexed['images']:
        image = rendition(item['thumb'], 'Retained source rendition; full temporary download unavailable', item['url'], item['path'])
        image.update({'retained_image_order': item['order'], 'declared_original_sha256_not_reverified': item['sha256']})
        viewed.append(image)
    viewed_urls = {x['source_url'] for x in viewed}
    gallery = [{'native_media_id': x['id'], 'display_index': x.get('displayIndex'), 'filename': x.get('filename'),
                'url': x['assetUrl'], 'caption': x.get('title'), 'saved_rendition_viewed': x['assetUrl'] in viewed_urls,
                'observation_utc': locator['observed_utc']} for x in media]
    targets = {t for m in edge['members'] for t in m['canonical_component_targets']}
    check('Existing BOM targets and related options are retained: ' + ref,
          targets == {options[oid]['canonical_component_id'] for oid in SOURCE_RELATED[ref]}
          and all(ref in options[oid]['related_platform_offer_refs'] for oid in SOURCE_RELATED[ref]))
    if ref == 'O010':
        finding = 'The lead source rendition shows three White panels, in current order One, Two, Three from left to right. Saved gallery details2 and3 correspond to selected White One and Two photos. The retained single Dropbox reference remains the White Three detail; it is not the group hero. The one native default variant has no image IDs or member choices. Preserve the existing gallery relationship and unresolved sale quantity.'
    else:
        name = options[SOURCE_RELATED[ref][0]]['name']
        finding = 'The saved lead source rendition corresponds to the existing selected photograph for ' + name + '. Scene framing, stone joints and surface/relief details support photographic correspondence. Existing source relationships are retained; cast measurements, composition, physical stock and fitted hardware are not newly verified.'
    cases.append({'offer_ref': ref, 'title': retained['title'], 'native_product_id': retained['sq_id'],
                  'native_variant_id': observed['native_variant_id'], 'sku': retained['sku'],
                  'finding': finding, 'related_option_ids': SOURCE_RELATED[ref],
                  'retained_source_offer': retained, 'retained_BOM_members': edge['members'],
                  'retained_current_source_reference': edge['current_primary_reference'],
                  'historical_source_url': retained['source_url'], 'captured_export_source_url': observed['current_source_url_from_export'],
                  'captured_export_utc': '2026-10-24T00:56:45.467073+00:00',
                  'captured_native_source_locator': locator, 'captured_variant': variant,
                  'source_field_comparisons': comparisons, 'viewed_source_renditions': viewed,
                  'all_captured_media_records': gallery,
                  'gallery_scope': {'captured_media_records': len(media), 'saved_renditions_viewed': len(viewed),
                                    'unviewed_media_records': sum(not x['saved_rendition_viewed'] for x in gallery)},
                  'new_source_SKU_assignment_or_platform_pair': False})

photo_comparisons = []
for ref, order, oid in PHOTO_COMPARISONS:
    source_case = next(x for x in cases if x['offer_ref'] == ref)
    image = next(x for x in source_case['viewed_source_renditions'] if x['retained_image_order'] == order)
    component = next(x for x in components if x['product_id'] == oid)
    native_image = component['saved_selected_rendition']
    source_rgb, native_rgb = decoded[image['path']], decoded[native_image['path']]
    check('Whole-frame comparison uses matching aspect ratios: ' + ref + ':' + str(order),
          source_rgb.width * native_rgb.height == source_rgb.height * native_rgb.width)
    source_small = source_rgb.resize((192, 256), Image.Resampling.LANCZOS)
    native_small = native_rgb.resize((192, 256), Image.Resampling.LANCZOS)
    delta = ImageChops.difference(source_small, native_small)
    photo_comparisons.append({'offer_ref': ref, 'retained_source_gallery_order': order, 'option_id': oid,
        'selected_file_id': component['file_id'], 'source_rendition': image['path'],
        'selected_rendition': native_image['path'], 'source_url': image['source_url'],
        'comparison_size': [192, 256], 'mean_absolute_RGB_difference_0_to_255': ImageStat.Stat(delta).mean,
        'encoded_rendition_bytes_equal': image['sha256'] == native_image['sha256'],
        'full_original_byte_equality_or_physical_identity_claimed': False,
        'visual_result': 'Whole-frame photo correspondence supported by framing, stone joints and local surface features.',
        'metric_scope': 'Diagnostic on existing renditions. No threshold or crop was fitted to prove specimen, dimensions, formulation, stock or variant allocation.'})

counts = {'source_offers': 5, 'existing_individual_options': 4, 'full_qualified_working_fields': 24,
          'captured_source_field_comparisons': 45, 'captured_media_records': sum(len(x['all_captured_media_records']) for x in cases),
          'source_renditions_viewed': sum(len(x['viewed_source_renditions']) for x in cases),
          'selected_renditions_viewed': 4, 'unviewed_media_records': sum(x['gallery_scope']['unviewed_media_records'] for x in cases),
          'whole_frame_photo_comparisons': len(photo_comparisons), 'matched_selected_photo_ids': 4,
          'public_source_original_bytes_verified': 0,
          'cached_native_originals_matching_recorded_hash': sum(x['saved_selected_rendition']['cached_native_original_matches_recorded_hash'] for x in components),
          'fresh_native_original_byte_verifications': 0, 'new_downloads': 0, 'live_calls': 0,
          'new_product_records': 0, 'new_platform_pairs': 0, 'new_source_SKU_assignments': 0,
          'new_physical_verifications': 0, 'new_owner_questions': 0, 'native_or_platform_or_shared_writes': 0}
check('All40 captured media records accounted for as13 viewed renditions plus27 unviewed records',
      (counts['captured_media_records'], counts['source_renditions_viewed'], counts['unviewed_media_records']) == (40, 13, 27))
check('Four complete options and24 full qualified fields retained', len(components) == 4 and sum(len(x['master_fields']) for x in components) == 24)
check('Six whole-frame photo correspondences remain four selected IDs', len(photo_comparisons) == 6 and len({x['selected_file_id'] for x in photo_comparisons}) == 4)
check('Silver cached original matches recorded hash; three White views remain renditions', counts['cached_native_originals_matching_recorded_hash'] == 1 and components[3]['saved_selected_rendition']['cached_native_original_matches_recorded_hash'])
check('All17 viewed rendition files stable', len(local_renditions) == 17 and all(sha(path) == expected for path, expected in local_renditions.items()))
for path, expected in inputs.items():
    check('Source/protected file unchanged after local review: ' + path, sha(path) == expected)

report = {'schema': 'boldstone.read_only_source_component_review.v1', 'status': 'PASS',
          'recorded_utc': datetime.now(timezone.utc).isoformat(), 'source_pointer_sha256': pointer_sha,
          'register_sha256': pointer['register_sha256'], 'workbook_sha256': pointer['workbook_sha256'],
          'current_asset_map': pointer['current_asset_reference_map'], 'current_native_map': pointer['current_native_reference_map'],
          'components': components, 'cases': cases, 'photo_comparisons': photo_comparisons,
          'counts': counts, 'source_inputs': inputs,
          'scope': 'Review of saved renditions and captured source metadata at their original clocks. One cached Silver original matches its recorded native content hash and size. No new live access, public-source original verification or fresh native byte verification. The group source quantity, material/version differences and physical qualifications remain explicit.',
          'source_original_availability': 'The 13 referenced public-source temporary originals and 4 selected temporary originals were unavailable at their recorded temporary paths. The existing Silver cache retains a full native original matching recorded content hash and size; the three White selected views are renditions. This is a local-path observation, not a global Dropbox absence claim.',
          'standing_owner_hold': 'The existing Acanthus physical-details question stays with its current session. No new owner question, context-photo request or folder action is issued.'}
save(H / 'review.json', report)

e = html.escape
relative = lambda path: e(quote(os.path.relpath(path, H), safe='/'), quote=True)
parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>Moonphase White and Silver source review</title><style>body{font:16px/1.5 system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;background:#f5f4ef;color:#1d2927}section{padding:1.5rem;background:#fff;border:1px solid #d8ded9;border-radius:12px;margin:1.5rem 0}a{color:#175d4a;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1rem}figure{margin:0}img{width:100%;height:320px;object-fit:contain;background:#eee}figcaption{font-size:14px}table{width:100%;border-collapse:collapse}td,th{padding:.65rem;border:1px solid #d8ded9;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}td p{white-space:pre-wrap;margin:.2rem 0}.note{color:#465e53}summary{cursor:pointer}</style></head><body>',
         '<h1>Moonphase White and Silver: source photographs and working details</h1>',
         '<p>Four existing options and five retained source offers. Open each selected image and its containing folder below.</p>',
         '<p class="note">Saved renditions support six whole-frame photograph correspondences. All 24 qualified working fields are retained. The 40 captured gallery records comprise 13 viewed source renditions and 27 unviewed records. The cached Silver original matches its recorded content hash; no fresh native binary verification was performed. No current physical stock, cast specification or source SKU allocation is certified.</p>',
         '<p><a href="#sources">Five source records and gallery coverage</a> · <a href="review.json">Structured review</a> · <a href="verification.json">Verification receipt</a></p>',
         '<section><h2>Numbering and source quantity</h2><p>The existing historical component codes remain separate from current display numbers:</p><table><tr><th>Historical code</th><th>Current option</th><th>Retained source scope</th></tr>']
for old, component, refs in zip(['BC-MP-2', 'BC-MP-3', 'BC-MP-4', 'BC-MP-5'], components, ['O010 / O065', 'O010 / O074', 'O010 / O075', 'O070']):
    parts.append(f'<tr><td>{e(old)}</td><td><a href="#{e(component["product_id"])}">{e(component["name"])}</a></td><td>{e(refs)}</td></tr>')
parts += ['</table><p>O010 opens with the three-panel arrangement. Its retained single Dropbox reference is the White Three detail. The native default variant has no component choices or image IDs; the existing “Gallery proposal; sale quantity unresolved” state remains.</p></section>']
for component in components:
    parts += [f'<section id="{e(component["product_id"])}"><h2>{e(component["name"])}</h2>',
              f'<p><a href="{e(component["image_url"], quote=True)}">Selected Dropbox image</a> · <a href="{e(component["folder_url"], quote=True)}">Containing folder</a></p>',
              f'<figure><a href="{relative(component["saved_selected_rendition"]["path"])}"><img src="{relative(component["saved_selected_rendition"]["path"])}" alt="{e(component["name"], quote=True)}"></a><figcaption>{e(component["saved_selected_rendition"]["role"])}. Current image ID and role retained.</figcaption></figure>',
              '<h3>Complete current working fields</h3><table><tr><th>Field</th><th>Working value and qualification</th></tr>']
    for label, field in component['master_fields'].items():
        parts.append(f'<tr><th>{e(label)}</th><td><p>{e(field["display"])}</p><details><summary>State, basis and full qualified field</summary><pre>{e(json.dumps(field, ensure_ascii=False, indent=2))}</pre></details></td></tr>')
    parts.append('</table></section>')
parts += ['<h2 id="sources">Source records and saved gallery views</h2>']
for case in cases:
    scope = case['gallery_scope']
    parts += [f'<section id="{e(case["offer_ref"])}"><h2>{e(case["offer_ref"])} · {e(case["title"])}</h2>',
              f'<p>{e(case["finding"])}</p><p>Gallery: {scope["captured_media_records"]} captured records; {scope["saved_renditions_viewed"]} saved renditions viewed; {scope["unviewed_media_records"]} records unviewed.</p>',
              '<p>' + ' · '.join(f'<a href="#{e(oid)}">{e(options[oid]["name"])}</a>' for oid in case['related_option_ids']) + '</p><div class="grid">']
    for image in case['viewed_source_renditions']:
        parts.append(f'<figure><a href="{relative(image["path"])}"><img loading="lazy" src="{relative(image["path"])}" alt="{e(case["offer_ref"])} saved gallery {image["retained_image_order"]}"></a><figcaption>Saved rendition {image["retained_image_order"]} · <a href="{e(image["source_url"], quote=True)}">Recorded source-image URL</a></figcaption></figure>')
    parts += ['</div><details><summary>Complete captured gallery inventory, source tuple and retained member scope</summary><pre>' + e(json.dumps(case, ensure_ascii=False, indent=2)) + '</pre></details></section>']
parts += ['<details><summary>Scope, source clocks and photograph comparison diagnostics</summary><pre>' + e(json.dumps({k: report[k] for k in ['scope', 'source_original_availability', 'counts', 'photo_comparisons']}, ensure_ascii=False, indent=2)) + '</pre></details></body></html>']
(H / 'index.html').write_text('\n'.join(parts))


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.local = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ['href', 'src'] and value and not urlsplit(value).scheme and not value.startswith('#'):
                self.local.append(H / unquote(urlsplit(value).path))


parser = Links()
parser.feed((H / 'index.html').read_text())
check('All local image/report links resolve', all(x.is_file() for x in parser.local if x.name != 'verification.json'), len(parser.local))
check('Published pointer unchanged by report rendering', sha(pointer_path) == pointer_sha)
verification = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
                'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
                'counts': counts, 'register_sha256': pointer['register_sha256'], 'workbook_sha256': pointer['workbook_sha256'],
                'review_sha256': sha(H / 'review.json'), 'html_sha256': sha(H / 'index.html')}
save(H / 'verification.json', verification)
save(H / 'sealed-handoff.json', {'status': 'SEALED_READ_ONLY_SOURCE_COMPONENT_REVIEW', 'recorded_utc': verification['recorded_utc'],
    'source_pointer_sha256': pointer_sha, 'source_offer_refs': REFS, 'counts': counts,
    'files': {n: sha(H / n) for n in ['build_review.py', 'review.json', 'index.html', 'verification.json']}})
for component in components:
    print(component['name'], '\nImage:', component['image_url'], '\nFolder:', component['folder_url'])
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'counts': counts, 'review': str(H / 'index.html'),
                  'seal_sha256': sha(H / 'sealed-handoff.json')}, ensure_ascii=False))
