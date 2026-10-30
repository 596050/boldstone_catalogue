"""Classify all24 captured Wall Circle source-gallery frames with provenance limits."""
import hashlib
import html
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageOps

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = Path(__file__).resolve().parent
OUT = H / 'wall-source-gallery-roles'
OUT.mkdir(exist_ok=True)
W = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-03'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
binding_path = H / 'wall-native-binding-readback.json'
native = read(binding_path)
patterns_path = B / 'components/parallel-reviews/wall-circle-2026-10-17/family-keep/native-pattern-image-bindings.json'
patterns = {x['image']['id']: x for x in read(patterns_path)}
gallery_receipts_path = W / 'NATIVE_GALLERY_ASSET_RECEIPTS.json'
saved_circles = {x['native_media_id']: x for x in read(gallery_receipts_path)['reads']}
public_cache_path = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z/Public_Gallery_References.json')
public = {x['image_url']: x for x in read(public_cache_path)['records']}
crosswalk_path = W / 'WALL_CIRCLE_CROSSWALK.json'
crosswalk = read(crosswalk_path)
replacement_path = H / 'deleted-reference-resolution/proposed-reference-replacements.json'
replacements = read(replacement_path)
pool_id, diagram_id = '68dc3398e650b237f2ca5f86', '68dcddccb684d43560237b60'
inputs = {str(p): sha(p) for p in [binding_path, patterns_path, gallery_receipts_path, public_cache_path, crosswalk_path, replacement_path]}
records, image_files = [], {}
for frame in native['gallery']:
    mid, url = frame['id'], frame['assetUrl']
    if mid in patterns:
        cached = patterns[mid]
        path, expected = cached['local_image'], cached['image_sha256']
        role, subtype = 'detail', 'pattern_swatch'
        qualification = 'Full rectangular surface-pattern reference. No complete panel silhouette, rear, measurement or installation is established.'
        viewed = 'Full-frame swatch visually compared on all18 boards; full cached file hashed and decoded.'
        pattern = cached['pattern']
    elif mid in saved_circles:
        cached = saved_circles[mid]
        path, expected = cached['path'], cached['sha256']
        role, subtype = 'individual', 'circular_display_reference'
        qualification = 'One complete visible circular composition with depicted halo. Capture/processing provenance, actual finish recipe, physical size and lighting build remain unverified.'
        viewed = 'Existing cached full frame opened individually in this review.'
        pattern = None
    else:
        cached = public[url]
        path, expected = cached['image_path'], cached['image_sha256']
        assert mid in [pool_id, diagram_id]
        role = 'group_context' if mid == pool_id else 'detail'
        subtype = 'poolside_scene_with_reflections' if mid == pool_id else 'fixing_cross_section_diagram'
        qualification = 'Three visible mounted circles and three water reflections. Real installation, stock quantities, individual specimen identities and physical lighting are unverified.' if mid == pool_id else 'Illustrated bracket/panel/wall cross-section. Filename labels Gemini generation; actual generation operation is not independently authenticated. This is not a photograph of fitted rear hardware, attachment or load capacity.'
        viewed = 'Existing cached full frame opened individually in this review.'
        pattern = None
    assert Path(path).is_file() and sha(path) == expected
    with Image.open(path) as image:
        image.load()
        oriented = ImageOps.exif_transpose(image).convert('RGBA')
    image_files[path] = expected
    match = next((x for x in crosswalk['entries'] if (x.get('circular_gallery_correspondence') or {}).get('native_media_id') == mid), None)
    association = None
    if match:
        proposal = next((x for x in replacements['changes'] if x['option_id'] == match['product_id']), None)
        reference = proposal['proposed'] if proposal else {k: read(B / 'current-master.json').get(k) for k in []}
        if not proposal:
            pointer = read(B / 'current-master.json')
            option = next(x for x in read(B / pointer['register'])['options'] if x['product_id'] == match['product_id'])
            reference = {k: option[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']}
        association = {'option_id': match['product_id'], 'review_id': match['review_id'], 'conditional_pattern_link_retained': True,
            'reference': reference, 'reference_status': 'Verified equivalent reference proposed; canonical publication pending' if proposal else 'Existing selected reference retained',
            'scope': 'Pattern/composition association only; edited scenes and exact physical variant applicability remain separate.'}
    record = {'native_product_id': native['native_product_id'], 'native_media_id': mid, 'display_index': frame['displayIndex'],
        'gallery_order_1based': len(records) + 1, 'source_image_url': url, 'captured_filename': frame['filename'], 'captured_title': frame['title'],
        'primary_visual_role': role, 'role_subtype': subtype, 'visual_qualification': qualification,
        'generation_or_processing_provenance_unverified': True, 'native_variant_pattern_label': pattern,
        'complete_physical_specimen_or_installed_hardware_verified': False, 'related_Dropbox_association': association,
        'saved_original': {'path': path, 'sha256': expected, 'bytes': Path(path).stat().st_size, 'dimensions': list(oriented.size),
            'full_decode_passed': True, 'decoded_RGBA_sha256': hashlib.sha256(oriented.tobytes()).hexdigest()},
        'visual_review_scope': viewed, 'new_download': False}
    if mid == pool_id:
        record.update({'visible_mounted_circles': 3, 'visible_reflections': 3, 'captured_title_count_is_misleading': True,
            'physical_stock_or_sculpture_count_asserted': False, 'verified_real_installation': False})
    if mid == diagram_id:
        record.update({'rear_hardware_diagram_only': True, 'actual_rear_photo': False})
    records.append(record)
counts = dict(Counter(x['primary_visual_role'] for x in records))
assert len(records) == len(image_files) == 24 and counts == {'individual': 4, 'detail': 19, 'group_context': 1}
assert len({x['native_media_id'] for x in records}) == 24
assert len([x for x in records if x['role_subtype'] == 'pattern_swatch']) == 18
assert [x['source_image_url'] for x in records] == [x['assetUrl'] for x in native['gallery']]
assert all(sha(path) == expected for path, expected in inputs.items())
report = {'status': 'PASS_COMPLETE_CAPTURED_24_FRAME_VISUAL_ROLE_REVIEW', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'native_product_id': native['native_product_id'], 'frames': records,
    'counts': {'gallery_frames': 24, 'source_originals_hashed_and_decoded': 24, 'source_frame_roles': counts,
        'pattern_swatches': 18, 'fixing_diagrams': 1, 'actual_rear_photographs': 0, 'verified_real_installations': 0,
        'whole_frame_swatches_reviewed_on_boards': 18, 'other_frames_opened_individually': 6, 'unviewed_captured_gallery_frames': 0,
        'new_downloads': 0, 'new_live_calls_for_role_pass': 0, 'new_identity_decisions': 0, 'native_or_platform_or_canonical_writes': 0},
    'source_inputs': inputs, 'source_image_files': image_files,
    'source_clock_scope': native['variant_image_binding_limit'],
    'scope': 'All24 gallery records whose URLs/order agree with the24October captured admin export. Existing cached bytes keep their16/17/21October acquisition clocks. Role review does not infer capture/generation provenance, exact physical specimens, source-SKU allocation or current variant-specific image bindings.',
    'identity_limits': 'Four conditional pattern associations retained; WC03/06/07 Pattern labels remain unresolved. Poolside image shows three mounted circles plus reflections; it does not add six sculptures. Diagram is not installed rear-hardware evidence.'}
(OUT / 'gallery-roles.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
e = html.escape
local = lambda p: e(quote(os.path.relpath(p, OUT), safe='/'), quote=True)
parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Wall Circle24 source-gallery roles</title><style>body{font:16px/1.5 system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}article{border:1px solid #ccc;padding:1rem}img{width:100%;height:360px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}</style></head><body><h1>Wall Circle: all24 source-gallery frames</h1><p>4 circular individual display images,18 pattern swatches,1 poolside group/context scene and1 fixing diagram. These are image-role counts; no physical stock or installed hardware is certified.</p><div class="grid">']
for record in records:
    info = record['saved_original']
    parts += [f'<article id="media-{record["native_media_id"]}"><h2>{record["gallery_order_1based"]}. {e(record["role_subtype"])}</h2><a href="{local(info["path"])}"><img loading="lazy" src="{local(info["path"])}" alt="{e(record["captured_title"] or record["role_subtype"], quote=True)}"></a>',
        f'<p>{e(record["visual_qualification"])}</p><p><a href="{e(record["source_image_url"], quote=True)}">Recorded source-image URL</a></p>']
    if record['native_variant_pattern_label']:
        parts += ['<p>' + e(record['native_variant_pattern_label']) + '</p>']
    if record['related_Dropbox_association']:
        ref = record['related_Dropbox_association']['reference']
        parts += [f'<p><a href="{e(ref["image_url"], quote=True)}">Related Dropbox image</a> · <a href="{e(ref["folder_url"], quote=True)}">Containing folder</a></p><p>{e(record["related_Dropbox_association"]["reference_status"])}</p>']
    parts += ['</article>']
parts += ['</div><p>' + e(report['scope']) + '</p><p><a href="gallery-roles.json">Full per-image records</a></p></body></html>']
(OUT / 'index.html').write_text('\n'.join(parts))
verification = {'status': 'PASS', 'checks_passed': 7, 'checks_total': 7,
    'checks': {'all24_unique_native_media_IDs': True, 'all24_captured_URLs_in_order': True, 'all24_originals_hash_and_decode': True,
        'role_counts4individual19detail1group': True, 'eighteen_swatches_and_one_diagram_explicit': True,
        'pool_three_circles_and_three_reflections_qualified': True, 'all_source_inputs_unchanged': True},
    'report_sha256': sha(OUT / 'gallery-roles.json'), 'html_sha256': sha(OUT / 'index.html')}
(OUT / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
(OUT / 'sealed-handoff.json').write_text(json.dumps({'status': 'SEALED_COMPLETE_24_SOURCE_FRAME_ROLE_REVIEW',
    'files': {str(H / 'build_wall_gallery_roles.py'): sha(H / 'build_wall_gallery_roles.py'), **{str(OUT / n): sha(OUT / n) for n in ['gallery-roles.json', 'index.html', 'verification.json']}}}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'frames': 24, 'roles': counts, 'seal_sha256': sha(OUT / 'sealed-handoff.json')}))
