"""Build an append-only, local evidence review of three existing source offers."""
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
B = H.parents[2]
def read(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value): Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def esc(value): return html.escape(str(value), quote=True)

pointer_path = B / 'current-master.json'
pointer_bytes = pointer_path.read_bytes()
p = json.loads(pointer_bytes)
regpath = B / p['register']
assetpath = B / p['current_asset_reference_map']['path']
nativepath = B / p['current_native_reference_map']['path']
assert sha(regpath) == p['register_sha256'] == 'd10946390d3858ce1f5c6a66caca988b9a61a1ce2ab1d1776d28bebeec4453a1'
assert sha(assetpath) == p['current_asset_reference_map']['sha256']
assert sha(nativepath) == p['current_native_reference_map']['sha256']
g, assets = read(regpath), read(assetpath)
options = {x['product_id']: x for x in g['options']}
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
observations = {x['offer_ref']: x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
idxpath = B / 'components/evidence/offer_review_index.json'
index = {x['ref']: x for x in read(idxpath)}
collectionpath = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/raw-public/collection-initial.body'
assert sha(collectionpath) == '548078a564dd57cca62e466b5b3a61dc47c8d584e6eedf107f362f429686ae5c'
collection = read(collectionpath)
readbackpath = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
assert sha(readbackpath) == '908efcead04e671fdd6f9c32a164a605a53b3a6bf2bad60dfd2305e9dc5bae04'
readback = read(readbackpath)
readbacks = {x['offer_ref']: x for x in readback['entries']}
triagepath = B / 'components/parallel-reviews/unpaired43-next-evidence-20261024-B/next-evidence-review.json'
triage = {x['offer_ref']: x for x in read(triagepath)['rows']}
navpaths = [H / 'selected-image-navigation-readback.json', H / 'rust-additional-source-readback.json']
naventries = [entry for path in navpaths for entry in read(path)['entries']]
assert len(naventries) == 8 and all(x['error'] is None for x in naventries)
metadata = {x['requested_id']: x['metadata'] for x in naventries}
marginrows = {(x['ref'], x['source_order']): x for x in read(H / 'white-margin-comparison.json')['rows']}
protected = {str(path): sha(path) for path in [regpath, B / p['workbook'], regpath.parent / 'image-coverage-current.json', assetpath, nativepath]}
inputpaths = [idxpath, collectionpath, readbackpath, triagepath, H / 'case-definitions.json', H / 'cached-photo-ranking.json', H / 'white-margin-comparison.json', *navpaths]
inputs = {str(path): sha(path) for path in inputpaths}
for source in readback['sources']:
    assert sha(source['path']) == source['sha256']
    inputs[source['path']] = source['sha256']

def cached(path, representation, expected=None):
    path = Path(path)
    digest = sha(path)
    if expected: assert digest == expected
    with Image.open(path) as im: size, fmt = list(im.size), im.format
    return {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size,
            'dimensions': size, 'format': fmt, 'representation': representation,
            'reduced_resolution': min(size) < 200, 'visually_reviewed_this_turn': True,
            'matches_retained_download_hash': bool(expected), 'live_original_download_this_turn': False}

def current(fid):
    x = assets[fid]
    assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/' in x['path']
    result = {k: x[k] for k in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']}
    original = bool(x.get('original') == x['thumb'] and x.get('current_original_content_rehashed') and x.get('sha256'))
    result['cached_image'] = cached(x['thumb'], 'retained Dropbox original' if original else 'retained thumbnail', x['sha256'] if original else None)
    result['navigation_scope'] = 'Current explicit asset map; live metadata only for IDs present in this packet metadata receipts.'
    return result

def pixels(path):
    with Image.open(path) as im: return ImageOps.exif_transpose(im).convert('RGB').resize((96, 96), Image.Resampling.LANCZOS)

def rmse(left, right):
    return math.sqrt(sum(v*v for v in ImageStat.Stat(ImageChops.difference(pixels(left), pixels(right))).rms)/3)

def image_path(url):
    u = urlsplit(url)
    path = unquote(u.path)
    if path.startswith('/home/'): return path[len('/home'):].rstrip('/') + '/' + parse_qs(u.query)['preview'][0]
    if path.startswith('/preview/'): return path[len('/preview'):]
    raise ValueError(url)

cases, cards, frames, viewed = [], [], [], {}
for definition in read(H / 'case-definitions.json'):
    ref = definition['ref']
    o, source, rb, observation = options[definition['option_id']], index[ref], readbacks[ref], observations[ref]
    pid, vid, sku = definition['tuple']
    assert [rb['native_product_id'], rb['native_variant_id'], rb['sku']] == definition['tuple']
    assert observation['observed_native_source_tuple'] == {'product_id': pid, 'variant_id': vid, 'sku_raw': sku}
    assert rb['all_nine_compared_fields_equal'] and all(x['equal'] for x in rb['fields'])
    position, native = next((i, x) for i, x in enumerate(collection['items']) if x['id'] == pid)
    variants = native['structuredContent']['variants']
    assert len(variants) == 1
    variant = variants[0]
    assert (variant['id'], variant['sku']) == (vid, sku)
    assert not variant['attributes'] and not variant['optionValues'] and not variant['images'] and not variant['imageIds']
    assert native['items'][0]['assetUrl'] == rb['source_first_image_url'] == source['images'][0]['url']
    assert len(source['images']) == len(definition['photo_ids']) == 3
    rows = []
    for src, fids in zip(source['images'], definition['photo_ids']):
        original_present = Path(src['path']).is_file()
        saved = cached(src['path'] if original_present else src['thumb'], 'retained source download' if original_present else 'retained source thumbnail', src['sha256'] if original_present else None)
        matches = []
        for fid in fids:
            image = current(fid)
            viewed[fid] = image
            match = {'current_image': image, 'whole_frame_RGB_RMSE_96px': rmse(saved['path'], image['cached_image']['path']),
                     'same_image_composition_supported': True, 'source_and_Dropbox_original_bytes_identical': False,
                     'binding_basis': 'Direct visual composition comparison; numerical scores support the candidate ranking only.',
                     'fine_detail_claim': False}
            margin = marginrows.get((ref, src['order']))
            if margin:
                candidate = next((x for x in margin['ranking'] if x['file_id'] == fid), None)
                if candidate: match['white_margin_normalized_RGB_RMSE_96px'] = candidate['rmse']
            matches.append(match)
        media = next(x for x in native['items'] if x['assetUrl'] == src['url'])
        row = {'offer_ref': ref, 'source_order': src['order'], 'source_url': src['url'], 'native_media_id': media['id'],
               'source_cached_image': saved, 'historical_original_path': src['path'], 'historical_original_present': original_present,
               'historical_original_sha256': src['sha256'], 'matched_current_images': matches,
               'file_binding_status': 'MULTIPLE_CURRENT_FILE_CANDIDATES' if len(matches) > 1 else 'ONE_CORRESPONDING_FILE_IN_SCOPED_REVIEW',
               'physical_verification': False, 'new_photo_role': False}
        rows.append(row)
        frames.append(row)
    assert all(o[k] == assets[o['file_id']][k] for k in ['file_id', 'folder_id', 'folder_url'])
    file, folder = metadata[o['file_id']], metadata[o['folder_id']]
    assert image_path(o['image_url']) == image_path(assets[o['file_id']]['image_url']) == file['path_display']
    assert file['path_display'].rsplit('/', 1)[0] == folder['path_display']
    card = {k: o[k] for k in ['product_id', 'canonical_design_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url']}
    card.update(qualified_working_fields=o['master_fields'], selected_cached_image=current(o['file_id']),
                live_selected_image_and_parent_metadata={'file': file, 'folder': folder}, saved_image_URL_forms_equivalent=True,
                sale_policy='Existing individual working option retained', new_SKU_or_configuration_assignment=False)
    cards.append(card)
    case = {k: v for k, v in definition.items() if k not in ['tuple', 'photo_ids']}
    case.update(native_tuple=observation['observed_native_source_tuple'], source_url=edges[ref]['source_offer']['source_url'], native_variant=variant,
                source_variant_locator={'path': str(collectionpath), 'sha256': sha(collectionpath), 'json_pointer': f'/items/{position}/structuredContent/variants/0', 'capture_utc': '2026-10-21T12:25:34.594104+00:00'},
                source_description_html=native.get('body') or native.get('excerpt'), native_gallery_metadata=native['items'],
                retained_source_offer=edges[ref]['source_offer'], retained_BOM_members=edges[ref]['members'],
                latest_captured_export_observation=observation, source_field_readback=rb,
                retained_preparation=triage[ref]['current_preparation'], source_photo_comparisons=rows,
                source_frames_reviewed=3, captured_gallery_media_count=len(native['items']), unviewed_gallery_media_count=len(native['items'])-3,
                prior_source_relationship_retained=True, exact_current_option_configuration_certified=False,
                physical_specifications_verified=False, new_platform_pair=False, owner_question_opened=False)
    cases.append(case)

assert len(cases) == len(cards) == 3 and len(frames) == 9 and len(viewed) == 10
assert sum(len(x['matched_current_images']) for x in frames) == 10
summary = {'source_offers': 3, 'individual_working_options': 3, 'qualified_working_fields': 18,
           'source_frames_visually_reviewed': 9, 'source_downloads_rehashed': 6, 'reduced_resolution_source_downloads': 2,
           'source_thumbnail_only_frames': 3, 'current_cached_images_visually_reviewed': 10,
           'current_originals_matching_retained_asset_hash': 2, 'unique_current_family_images_machine_ranked': 80,
           'source_frames_with_image_correspondence': 9, 'source_to_current_file_correspondences': 10,
           'source_frames_with_multiple_current_file_candidates': 1, 'source_frames_without_exact_file_binding': 0,
           'captured_gallery_media_records': 32, 'gallery_records_not_visually_reviewed': 23,
           'selected_image_metadata_verified': 3, 'selected_containing_folder_metadata_verified': 3,
           'additional_Rust_image_metadata_verified': 2, 'new_products': 0, 'new_platform_pairs': 0, 'new_physical_verifications': 0}
assert sum(x['captured_gallery_media_count'] for x in cases) == 32
report = {'status': 'THREE_SOURCE_REVIEWS_COMPLETE_WITH_QUALIFIED_FILE_BINDINGS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'pointer_snapshot': {'sha256': hashlib.sha256(pointer_bytes).hexdigest(), 'status': p['status']},
          'protected_files': protected, 'source_inputs': inputs,
          'current_asset_map': {'path': str(assetpath), 'sha256': sha(assetpath), 'lookup': 'current-master.current_asset_reference_map.path'},
          'cases': cases, 'individual_options': cards, 'viewed_current_images': list(viewed.values()), 'summary': summary,
          'source_scope': 'Retained source images, 21 October public collection, retained 24 October export, current explicit asset map, and eight live Dropbox metadata reads. No new live Squarespace observation.',
          'limits': ['Nine of thirty-two captured gallery entries were visually reviewed; twenty-three remain metadata only.',
                     'Six source downloads match retained hashes, but two are 105 × 140 JPEG images. Three Rust source comparisons use thumbnails.',
                     'Two current cached originals match retained asset hashes. Source-to-Dropbox original byte identity is not claimed.',
                     'One Terracotta frame has two current file candidates. No preferred original, deduplication or deletion is proposed.',
                     'Directory session owns Rust family filing. Its proposed moves are separate and unapplied; no current image role or gap count is changed here.',
                     'All eighteen working field objects, current Frozen Fish 70 H × 15 W dimensions, accepted estimates, and existing identity, context and platform holds remain unchanged.'],
          'native_metadata_reads': 8, 'native_downloads': 0, 'native_writes': 0, 'platform_writes': 0, 'canonical_writes': 0}
write(H / 'review.json', report)
proposal = {'status': 'EVIDENCE_ONLY_FOR_MAIN_SESSION', 'apply_automatically': False,
            'baseline_register_sha256': p['register_sha256'], 'baseline_asset_map_sha256': sha(assetpath),
            'cases': [{'offer_ref': c['ref'], 'native_tuple': c['native_tuple'], 'existing_option_id': c['option_id'], 'finding': c['finding'],
                       'photo_correspondences': [{'source_order': x['source_order'], 'source_url': x['source_url'], 'file_binding_status': x['file_binding_status'],
                         'current_file_candidates': [{k: z['current_image'][k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']} for z in x['matched_current_images']]} for x in c['source_photo_comparisons']],
                       'limits': c['limits']} for c in cases],
            'new_products': 0, 'specification_changes': 0, 'new_SKU_configuration_assignments': 0,
            'native_actions': [], 'platform_actions': [], 'owner_questions': []}
write(H / 'source-photo-evidence-proposal.json', proposal)
sections = []
terminal = ['Frozen Fish Terracotta, Frozen Fish Verdigris, and Rust and Verdigris Panel', 'Three source reviews; eighteen qualified working fields retained.', '']
for case, card in zip(cases, cards):
    terminal += [case['ref'] + ' · ' + card['name'], case['finding'], 'Image: ' + card['image_url'], 'Folder: ' + card['folder_url']]
    terminal += [key + ': ' + field['display'] + ' [' + field['state'].replace('\n', '; ') + ']' for key, field in card['qualified_working_fields'].items()]
    terminal += case['limits'] + ['']
    pictures = []
    for frame in case['source_photo_comparisons']:
        saved = frame['source_cached_image']
        caption = f"Source {frame['source_order']} · {saved['representation']} · {saved['dimensions'][0]} × {saved['dimensions'][1]} px"
        group = '<figure><img src="' + esc(Path(saved['path']).as_uri()) + '"><figcaption>' + esc(caption) + ' · <a href="' + esc(frame['source_url']) + '">source image</a></figcaption></figure>'
        for match in frame['matched_current_images']:
            image = match['current_image']
            group += '<figure><img src="' + esc(Path(image['cached_image']['path']).as_uri()) + '"><figcaption>' + esc(image['name']) + '<br><a href="' + esc(image['image_url']) + '">Dropbox image</a> · <a href="' + esc(image['folder_url']) + '">folder</a></figcaption></figure>'
        pictures.append('<div class="comparison">' + group + '</div>')
    fields = ''.join('<tr><th>' + esc(key) + '</th><td>' + esc(field['display']) + '<p class="qualification">' + esc(field['state']) + '</p><details><summary>Recorded basis</summary>' + esc(field['basis']) + '</details></td></tr>' for key, field in card['qualified_working_fields'].items())
    sections.append('<section id="' + case['ref'] + '"><h2>' + esc(card['name']) + '</h2><p><a href="' + esc(card['image_url']) + '">Selected image</a> · <a href="' + esc(card['folder_url']) + '">Containing folder</a></p><p>' + esc(case['finding']) + '</p>' + ''.join(pictures) + '<table>' + fields + '</table><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in case['limits']) + '</ul></section>')
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Frozen Fish and Rust Panel source review</title><style>body{max-width:1120px;margin:36px auto;padding:0 20px;font:17px system-ui;line-height:1.5;color:#242424}section{margin-top:36px;border-top:1px solid #bbb;padding-top:18px}.comparison{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}figure{flex:1;min-width:240px;margin:0}img{width:100%;height:340px;object-fit:contain;background:#f4f4f4}figcaption,.qualification,details{font-size:14px}table{border-collapse:collapse;width:100%}td,th{padding:10px;vertical-align:top;text-align:left;border-bottom:1px solid #ddd;white-space:pre-line}th{width:22%}a{overflow-wrap:anywhere}@media(max-width:600px){figure{min-width:100%}}</style></head><body><h1>Frozen Fish and Rust Panel</h1><p>Three existing products; nine source photographs compared with ten current files. All eighteen working specification fields are retained with their qualifications. One Terracotta view has two file candidates. Two Verdigris source downloads have limited resolution.</p><p>Three selected images and their containing folders, plus two further Rust image IDs, were checked live. Twenty-three additional gallery entries remain unviewed. This review awaits main-session incorporation and changes no Dropbox files or published catalogue fields.</p>' + ''.join(sections) + '</body></html>'
(H / 'index.html').write_text(page)
(H / 'terminal-review.txt').write_text('\n'.join(terminal) + '\n')
assert all(sha(path) == expected for path, expected in protected.items())
assert pointer_path.read_bytes() == pointer_bytes
print(json.dumps({'status': report['status'], 'summary': summary}))
