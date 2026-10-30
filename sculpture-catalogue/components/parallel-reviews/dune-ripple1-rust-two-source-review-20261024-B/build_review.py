"""Build an append-only, local evidence review of two source offers for one existing product."""
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
navpaths = [H / 'selected-image-navigation-readback.json', H / 'additional-image-navigation-readback.json']
naventries = [entry for path in navpaths for entry in read(path)['entries']]
assert len(naventries) == 6 and all(x['error'] is None for x in naventries)
metadata = {x['requested_id']: x['metadata'] for x in naventries}
downloads = {x['ref']: x for x in read(H / 'additional-source-downloads.json')['entries']}
protected = {str(path): sha(path) for path in [regpath, B / p['workbook'], regpath.parent / 'image-coverage-current.json', assetpath, nativepath]}
inputpaths = [idxpath, collectionpath, readbackpath, triagepath, H / 'case-definitions.json', H / 'cached-photo-ranking.json', H / 'rear-photo-ranking.json', H / 'additional-source-downloads.json', *navpaths]
inputs = {str(path): sha(path) for path in inputpaths}
for download in downloads.values():
    assert sha(download['path']) == download['sha256']
    inputs[download['path']] = download['sha256']
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
            'matches_recorded_file_hash': bool(expected), 'live_original_download_this_turn': False}

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
    assert len(source['images']) == 3 and len(definition['photo_ids']) == 4
    extra = downloads[ref]
    source_images = source['images'] + [{'order': 4, 'url': extra['url'], 'path': extra['path'], 'thumb': extra['path'], 'sha256': extra['sha256']}]
    rows = []
    for src, fids in zip(source_images, definition['photo_ids']):
        fresh = src['order'] == 4
        original_present = not fresh and Path(src['path']).is_file()
        saved = cached(src['path'] if fresh or original_present else src['thumb'], 'fresh source CDN download' if fresh else ('retained source download' if original_present else 'retained source thumbnail'), src['sha256'] if fresh or original_present else None)
        saved['live_original_download_this_turn'] = fresh
        if fresh: saved['download_receipt'] = extra
        matches = []
        for fid in fids:
            image = current(fid)
            viewed[fid] = image
            match = {'current_image': image, 'whole_frame_RGB_RMSE_96px': rmse(saved['path'], image['cached_image']['path']),
                     'same_image_composition_supported': not (ref == 'O051' and src['order'] == 1), 'same_scene_supported': True, 'source_and_Dropbox_original_bytes_identical': False,
                     'binding_basis': 'Direct visual composition comparison; numerical scores support the candidate ranking only.',
                     'fine_detail_claim': False}
            matches.append(match)
        media = next(x for x in native['items'] if x['assetUrl'] == src['url'])
        row = {'offer_ref': ref, 'source_order': src['order'], 'source_url': src['url'], 'native_media_id': media['id'],
               'source_cached_image': saved, 'historical_original_path': None if fresh else src['path'], 'historical_original_present': original_present,
               'historical_original_sha256': None if fresh else src['sha256'], 'matched_current_images': matches,
               'file_binding_status': 'SAME_SCENE_CANDIDATE_ONLY' if ref == 'O051' and src['order'] == 1 else 'ONE_CORRESPONDING_FILE_IN_SCOPED_REVIEW',
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
    if not any(x['product_id'] == card['product_id'] for x in cards): cards.append(card)
    case = {k: v for k, v in definition.items() if k not in ['tuple', 'photo_ids']}
    case.update(native_tuple=observation['observed_native_source_tuple'], source_url=edges[ref]['source_offer']['source_url'], native_variant=variant,
                source_variant_locator={'path': str(collectionpath), 'sha256': sha(collectionpath), 'json_pointer': f'/items/{position}/structuredContent/variants/0', 'capture_utc': '2026-10-21T12:25:34.594104+00:00'},
                source_description_html=native.get('body') or native.get('excerpt'), native_gallery_metadata=native['items'],
                retained_source_offer=edges[ref]['source_offer'], retained_BOM_members=edges[ref]['members'],
                latest_captured_export_observation=observation, source_field_readback=rb,
                retained_preparation=triage[ref]['current_preparation'], source_photo_comparisons=rows,
                source_frames_reviewed=4, captured_gallery_media_count=len(native['items']), unviewed_gallery_media_count=len(native['items'])-4,
                prior_source_relationship_retained=True, exact_current_option_configuration_certified=False,
                physical_specifications_verified=False, new_platform_pair=False, owner_question_opened=False)
    cases.append(case)

assert len(cases) == 2 and len(cards) == 1 and len(frames) == 8 and len(viewed) == 4
assert sum(len(x['matched_current_images']) for x in frames) == 8
summary = {'source_offers': 2, 'individual_working_options': 1, 'qualified_working_fields': 6,
           'source_frames_visually_reviewed': 8, 'retained_source_thumbnail_frames': 6,
           'fresh_source_CDN_downloads': 2, 'reduced_resolution_fresh_downloads': 1,
           'current_cached_images_visually_reviewed': 4, 'current_originals_matching_retained_asset_hash': 0,
           'unique_current_family_images_machine_ranked': 440, 'source_frames_with_image_correspondence': 7,
           'source_frames_with_scene_candidate_only': 1, 'source_to_current_file_candidates': 8,
           'captured_gallery_media_records': 8, 'gallery_records_not_visually_reviewed': 0,
           'current_file_metadata_verified': 4, 'containing_folder_metadata_verified': 2,
           'new_products': 0, 'new_platform_pairs': 0, 'new_physical_verifications': 0}
assert sum(x['captured_gallery_media_count'] for x in cases) == 8
report = {'status': 'TWO_SOURCE_FULL_GALLERY_REVIEWS_COMPLETE_ONE_EXISTING_OPTION', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
          'pointer_snapshot': {'sha256': hashlib.sha256(pointer_bytes).hexdigest(), 'status': p['status']},
          'protected_files': protected, 'source_inputs': inputs,
          'current_asset_map': {'path': str(assetpath), 'sha256': sha(assetpath), 'lookup': 'current-master.current_asset_reference_map.path'},
          'cases': cases, 'individual_options': cards, 'viewed_current_images': list(viewed.values()), 'summary': summary,
          'source_scope': 'Six retained source thumbnails, two fresh CDN images from retained gallery URLs, captured 21 October collection and retained 24 October export; six live Dropbox metadata reads. No live product/inventory verification.',
          'limits': ['All eight captured gallery entries were reviewed. Six are thumbnail evidence; the newly fetched O067 rear image is only 112 by 200 pixels.',
                     'O051 front remains a same-scene candidate because framing differs; exact photographic-original identity is not established.',
                     'Both rear sources correspond to the same image filed under Dune Ripple1 Verdigris. That reuse does not verify installed hardware on a Rust cast or authorize a file move.',
                     'Two distinct source product and variant tuples share a SKU. Different captured prices, stock settings and raw weights remain separate observations; no source record is merged or deleted.',
                     'One existing product and all six qualified working field objects are retained. Existing context, identity and platform holds remain unchanged.'],
          'native_metadata_reads': 6, 'native_downloads': 0, 'public_source_CDN_downloads': 2,
          'native_writes': 0, 'platform_writes': 0, 'canonical_writes': 0}
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
terminal = ['Dune Ripple1 Rust: two historical source offers', 'All eight gallery entries reviewed; one existing option and six qualified working fields retained.', '']
for case in cases:
    card = next(x for x in cards if x['product_id'] == case['option_id'])
    terminal += [case['ref'] + ' · ' + card['name'], case['finding'], 'Image: ' + card['image_url'], 'Folder: ' + card['folder_url']]
    variant = case['native_variant']
    terminal += ['Historical source price: GBP ' + variant['priceMoney']['value'],
                 'Historical stock setting: unlimited=' + str(variant['unlimited']) + ', quantity=' + str(variant['qtyInStock']),
                 'Raw source weight: ' + str(variant['weight']) + ' (unit not independently decoded)']
    if case['ref'] == 'O051':
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
    working = '<h3 id="working-specifications">Existing qualified working specifications</h3><table>' + fields + '</table>' if case['ref'] == 'O051' else '<p><a href="#working-specifications">The same existing product specifications apply.</a></p>'
    historical = '<p>Historical source price: £' + esc(variant['priceMoney']['value']) + '; unlimited stock setting: ' + esc(variant['unlimited']) + '; recorded quantity: ' + esc(variant['qtyInStock']) + '; raw weight: ' + esc(variant['weight']) + ' (unit not independently decoded). These observations do not replace the current working details.</p>'
    sections.append('<section id="' + case['ref'] + '"><h2>' + esc(card['name']) + ' · ' + case['ref'] + '</h2><p><a href="' + esc(card['image_url']) + '">Selected image</a> · <a href="' + esc(card['folder_url']) + '">Containing folder</a></p><p>' + esc(case['finding']) + '</p>' + historical + ''.join(pictures) + working + '<ul>' + ''.join('<li>' + esc(x) + '</li>' for x in case['limits']) + '</ul></section>')
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dune Ripple1 Rust source review</title><style>body{max-width:1120px;margin:36px auto;padding:0 20px;font:17px system-ui;line-height:1.5;color:#242424}section{margin-top:36px;border-top:1px solid #bbb;padding-top:18px}.comparison{display:flex;flex-wrap:wrap;gap:16px;margin:24px 0}figure{flex:1;min-width:240px;margin:0}img{width:100%;height:340px;object-fit:contain;background:#f4f4f4}figcaption,.qualification,details{font-size:14px}table{border-collapse:collapse;width:100%}td,th{padding:10px;vertical-align:top;text-align:left;border-bottom:1px solid #ddd;white-space:pre-line}th{width:22%}a{overflow-wrap:anywhere}@media(max-width:600px){figure{min-width:100%}}</style></head><body><h1>Dune Ripple 1 — Rust</h1><p>Two historical source offers, one existing product and six qualified working specification fields. All eight captured gallery entries were reviewed. Seven correspond to current photographs; O051 front remains a same-scene candidate because framing differs.</p><p>Both listings reuse a rear image filed under the Verdigris finish. It is comparison evidence, not proof of Rust hardware. The current £200 estimate and made-to-order 1–2 week policy remain unchanged. Four image IDs and two containing folders were checked live. This review awaits main-session incorporation.</p>' + ''.join(sections) + '</body></html>'
(H / 'index.html').write_text(page)
(H / 'terminal-review.txt').write_text('\n'.join(terminal) + '\n')
assert all(sha(path) == expected for path, expected in protected.items())
assert pointer_path.read_bytes() == pointer_bytes
print(json.dumps({'status': report['status'], 'summary': summary}))
