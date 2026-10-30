"""Adjudicate image correspondences separately from pattern-only associations."""
import hashlib
import html
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ImageChops, ImageOps, ImageStat

B = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H = Path(__file__).resolve().parent
D = B.parent / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks = []


def check(name, passed):
    checks.append({'check': name, 'pass': bool(passed)})
    assert passed, name


def visible_rgb(path):
    rgba = ImageOps.exif_transpose(Image.open(path)).convert('RGBA')
    return Image.alpha_composite(Image.new('RGBA', rgba.size, (255, 255, 255, 255)), rgba).convert('RGB')


candidate = read(H / 'photo-candidates.json')
check('Exact verified candidate diagnostic input', sha(H / 'photo-candidates.json') == '35fc55809adbe2966ccff4871afdb8204ebb6eb16438375312eadef426ec2bf9')
native = {x['file_id']: x for x in candidate['native_originals']}
by_name = {x['name']: x for x in native.values()}
check('Unique current native names within family', len(by_name) == len(native) == 159)
crop = read(H / 'dimension-derived-center-crop-diagnostics.json')
own_listing_path = B / 'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/family-listing-and-history-receipts.json'
own_listing_receipt = read(own_listing_path)['requests'][0]
own_listing = own_listing_receipt['result']['structuredContent']
own_files = {x['file_id']: x for x in own_listing['entries'] if x['object_type'] == 'file'}
own_folders = {x['file_id']: x for x in own_listing['entries'] if x['object_type'] == 'folder'}
check('Independent complete family listing has the same159 IDs', not own_listing['has_more'] and set(own_files) == set(native))
for fid, row in native.items():
    check('Exact current file path and actual containing folder: ' + fid, own_files[fid]['path'] == row['path']
          and own_folders[row['folder_id']]['path'] == row['path'].rsplit('/', 1)[0])
    check('Native cached original unchanged since159-file verification: ' + fid, sha(row['current_original']['path']) == row['current_original']['sha256'])
p = read(B / 'current-master.json')
protected_paths = [B / 'current-master.json', B / p['register'], B / p['workbook'], B / p['current_asset_reference_map']['path'],
    B / p['current_native_reference_map']['path'], (B / p['register']).parent / 'image-coverage-current.json',
    B / 'components/reviews/specification_review_progress.json', B / 'components/checkpoint.json', B / 'checkpoint.json']
protected = {str(path): sha(path) for path in protected_paths}
swatches = [(6, 1, '019', '006'), (7, 1, '022', '009'), (8, 1, '024', '011'),
    (9, 2, '023', '009'), (10, 2, '025', '011'), (11, 2, '017', '003'), (12, 2, '018', '004'),
    (13, 3, '014', '002'), (14, 3, '019', '007'), (15, 3, '022', '010'), (16, 3, '023', '011'),
    (17, 4, '016', '005'), (18, 4, '015', '004'), (19, 4, '022', '011'),
    (20, 5, '021', '002'), (21, 5, '034', '015'), (22, 5, '038', '019'), (23, 5, '030', '011')]
full_names = {order: [f'wall-circle__wall-circle-generated-series-{series:03d}__{suffix}.webp' for suffix in [first, second]] for order, series, first, second in swatches}
full_names[4] = ['wall-circle__wall-circle-yellow-and-grey-pattern-studies__012.webp']
full_names[5] = ['wall-circle__wall-circle-marbled-3-scene-studies__004.png']
composition_names = {
    1: ['wall-circle__wall-circle-marbled-2__014.webp', 'wall-circle__wall-circle-marbled-2__003.png'],
    2: ['wall-circle__wall-circle-marbled-4__019.png'],
    3: ['wall-circle__wall-circle-marbled-1__013.webp', 'wall-circle__wall-circle-marbled-1__002.png']}
boards = read(D / 'families/wall-circle/contact-board-index.json')
board_inputs = {x['path']: sha(x['path']) for x in boards}
records = []
for source in candidate['sources']:
    order = source['gallery_order_1based']
    full = order in full_names
    names = full_names.get(order, composition_names.get(order, []))
    source_image = source['source_image']
    check('Saved source image unchanged: ' + str(order), sha(source_image['path']) == source_image['sha256'])
    source_rgb = visible_rgb(source_image['path'])
    matches = []
    for name in names:
        target = by_name[name]
        original = target['current_original']
        diagnostic = next(x for x in source['ranked_whole_frame_candidates'] if x['file_id'] == target['file_id'])
        details = dict(diagnostic)
        if full:
            other = visible_rgb(original['path'])
            if other.size != source_rgb.size:
                check('Pool scene requires only full-frame size rounding: ' + name, order == 5 and diagnostic['relative_aspect_ratio_difference'] < .001)
                other = other.resize(source_rgb.size, Image.Resampling.LANCZOS)
            delta = ImageChops.difference(source_rgb, other)
            details.update({'full_source_size_comparison': list(source_rgb.size), 'full_frame_mean_absolute_RGB_difference': ImageStat.Stat(delta).mean,
                'full_frame_RMS_RGB_difference': ImageStat.Stat(delta).rms,
                'comparison_transform': 'Both images composited over white when alpha is present; original RGBA hashes retained. Complete-frame resize to retained source dimensions; only poolscene differs in dimensions. No crop, rotation, colour fitting or acceptance threshold.'})
        matches.append({'current_file_id': target['file_id'], 'current_folder_id': target['folder_id'], 'name': name,
            'image_url': target['image_url'], 'folder_url': target['folder_url'], 'current_native_path': target['path'],
            'current_original': original, 'current_native_metadata': target['current_native_metadata'],
            'native_metadata_clock': target['native_hash_observed_scope'],
            'relation': 'SAME_FULL_FRAME_IMAGE_RENDITION' if full else 'CIRCULAR_COMPOSITION_ONLY',
            'source_picture_match_supported': full, 'original_encoded_or_decoded_pixel_identity': False,
            'diagnostics': details,
            'visual_evidence': 'All frame edges and distinctive internal pattern/background landmarks correspond. Separate current encodings remain separate file IDs.' if full else 'Disc pattern and depicted halo/wall composition correspond, but crop, placement or aspect differs. Exact same-photo origin is not established; do not join as a source-picture match.'})
    grade = 'SAME_FULL_FRAME_IMAGE_RENDITION' if full else 'CIRCULAR_COMPOSITION_ONLY' if names else 'UNRESOLVED_WITHIN_CURRENT_WALL_CIRCLE_FAMILY'
    records.append({'offer_ref': 'O001', 'native_product_id': '68dc0a35a7ac865209b39248', 'native_media_id': source['native_media_id'],
        'gallery_order_1based': order, 'source_image_url': source['source_image_url'], 'source_image': source_image,
        'source_image_role': source['primary_visual_role'], 'role_subtype': source['role_subtype'], 'grade': grade,
        'source_picture_match_supported': full, 'current_file_correspondences': matches,
        'circular_center_crop_hypothesis': [x for x in crop['comparisons'] if x['order'] == order],
        'source_identity_scope': 'Image/reference-graphic correspondence only; no new individual specimen, physical finish, size, stock, variant allocation or owner identity decision.',
        'unresolved_note': 'No corresponding fixing diagram was identified among the159 current family originals. This is not a claim of absence outside this current family scope.' if order == 24 else None})
counts = {'source_gallery_frames': len(records), 'current_native_originals_verified': 159, 'complete_frame_diagnostic_comparisons': 3816,
    'source_frames_with_supported_whole_frame_rendition_correspondence': sum(x['source_picture_match_supported'] for x in records),
    'supported_source_picture_to_current_file_links': sum(len(x['current_file_correspondences']) for x in records if x['source_picture_match_supported']),
    'composition_only_source_frames': sum(x['grade'] == 'CIRCULAR_COMPOSITION_ONLY' for x in records),
    'composition_only_candidate_links': sum(len(x['current_file_correspondences']) for x in records if x['grade'] == 'CIRCULAR_COMPOSITION_ONLY'),
    'unresolved_source_frames_in_current_family': sum(x['grade'] == 'UNRESOLVED_WITHIN_CURRENT_WALL_CIRCLE_FAMILY' for x in records),
    'encoded_byte_equal_source_native_pairs': 0, 'full_decoded_pixel_equal_source_native_pairs': 0,
    'current_native_contact_boards_reopened': 8, 'new_live_calls': 0, 'new_downloads': 0,
    'new_owner_questions': 0, 'new_identity_decisions': 0, 'native_or_platform_or_canonical_writes': 0}
check('All24 sources retain20 full-frame,3 composition-only and1 unresolved outcomes',
    (counts['source_gallery_frames'], counts['source_frames_with_supported_whole_frame_rendition_correspondence'], counts['composition_only_source_frames'], counts['unresolved_source_frames_in_current_family']) == (24, 20, 3, 1))
check('Thirty-eight positive current-file links remain separate from five composition candidates', counts['supported_source_picture_to_current_file_links'] == 38 and counts['composition_only_candidate_links'] == 5)
check('No source/native encoded or full-pixel equality promoted', all(not x['encoded_exact_matches'] and not x['decoded_exact_matches'] for x in candidate['sources']))
check('Five attempted dimension-derived center crops retained as negative diagnostics', len(crop['comparisons']) == 5 and all(x['mean_difference'] > 20 for x in crop['comparisons']))
inputs = {str(H / n): sha(H / n) for n in ['photo-candidates.json', 'dimension-derived-center-crop-diagnostics.json', 'corrected-source-handoff.json', 'initial-source-hash-diagnostic.json', 'clock-label-correction-note.json', 'alpha-diagnostic-correction-note.json']}
inputs.update(candidate['source_inputs'])
inputs[str(own_listing_path)] = sha(own_listing_path)
inputs.update(board_inputs)
for path, expected in inputs.items():
    check('Bound source evidence unchanged: ' + path, sha(path) == expected)
for path, expected in protected.items():
    check('Canonical input unchanged: ' + path, sha(path) == expected)
report = {'status': 'COMPLETE_BOUNDED_SOURCE_IMAGE_CORRESPONDENCE_REVIEW', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_pointer_sha256': protected[str(B / 'current-master.json')], 'register_sha256': p['register_sha256'], 'workbook_sha256': p['workbook_sha256'],
    'frames': records, 'counts': counts, 'source_inputs': inputs, 'protected_canonical_inputs': protected,
    'grade_contract': {'SAME_FULL_FRAME_IMAGE_RENDITION': 'Same full-frame image content visually supported, with re-encoding/resizing explicitly qualified. Original native bytes are verified independently against captured fresh native hash/size; no equality of source/native bytes or decoded pixels is claimed.',
        'CIRCULAR_COMPOSITION_ONLY': 'Same disc pattern/composition candidate. Not an exact-picture edge, physical identity or native-variant match.',
        'UNRESOLVED_WITHIN_CURRENT_WALL_CIRCLE_FAMILY': 'No supported correspondence in the159 reviewed current family originals; no global absence claim.'},
    'visual_scope': 'All159 current family images reopened on eight full-frame contact boards. All24 retained source frames were previously opened individually or as full-frame swatches on all18 comparison boards; all183 local image files rehashed and decoded. Three circular candidates also reopened at full original size. Review HTML preserves source/current frames without editing them.',
    'unchanged_identity_questions': 'The pending exact FFL1-to-FFS2 question and three unresolved Wall Circle Pattern labels remain separate. No answer, new alias or physical specification is inferred.',
    'clock_scope': 'Source bytes retain16/17/21October acquisition clocks and24October captured gallery membership. Native hash receipt recorded2026-10-24T21:50:18.948Z and completed21:55:27.947Z; this pass rehashed existing local originals without a new native call.'}
(H / 'review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
e = html.escape
local = lambda p: e(quote(os.path.relpath(p, H), safe='/'), quote=True)
parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wall Circle24 exact-image review</title><style>body{font:16px/1.5 system-ui;max-width:1250px;margin:2rem auto;padding:0 1rem}section{border-top:1px solid #bbb;padding:1.5rem 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem}figure{margin:0}img{width:100%;height:350px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}</style></head><body><h1>Wall Circle:24 source frames against159 current originals</h1><p>20 source frames have supported whole-frame image-rendition correspondences to38 current files. Three circular frames retain composition-only candidates. The fixing diagram remains unresolved in this current family. No source/native encoded bytes or complete decoded pixels are identical.</p><p>Each current original was rehashed against the captured fresh native content hash and size. Source matches do not certify physical specimens, variant allocation, stock, lighting or fitted hardware.</p><p><a href="review.json">Structured per-frame results</a> · <a href="verification.json">Verification receipt</a></p>']
for record in records:
    source = record['source_image']
    parts += [f'<section id="media-{record["native_media_id"]}"><h2>{record["gallery_order_1based"]}. {e(record["grade"])}</h2><p>{e(record["role_subtype"])}</p><div class="grid">',
        f'<figure><a href="{local(source["path"])}"><img src="{local(source["path"])}" alt="Retained source frame{record["gallery_order_1based"]}"></a><figcaption>Retained source frame · <a href="{e(record["source_image_url"], quote=True)}">Recorded source-image URL</a></figcaption></figure>']
    for match in record['current_file_correspondences']:
        original = match['current_original']
        parts += [f'<figure><a href="{local(original["path"])}"><img loading="lazy" src="{local(original["path"])}" alt="{e(match["name"], quote=True)}"></a><figcaption>{e(match["name"])}<br><a href="{e(match["image_url"], quote=True)}">Current Dropbox image</a> · <a href="{e(match["folder_url"], quote=True)}">Containing folder</a><br>{e(match["relation"])}</figcaption></figure>']
    parts += ['</div>']
    if record['unresolved_note']:
        parts += ['<p>' + e(record['unresolved_note']) + '</p>']
    parts += ['<details><summary>Full comparison proof and qualifications</summary><pre>' + e(json.dumps(record, ensure_ascii=False, indent=2)) + '</pre></details></section>']
parts += ['<p>' + e(report['clock_scope']) + '</p><p>' + e(report['unchanged_identity_questions']) + '</p></body></html>']
(H / 'index.html').write_text('\n'.join(parts))
verification = {'status': 'PASS', 'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'review_sha256': sha(H / 'review.json'), 'html_sha256': sha(H / 'index.html'), 'counts': counts}
(H / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
names = ['prepare_candidates.py', 'build_review.py', 'photo-candidates.json', 'dimension-derived-center-crop-diagnostics.json',
    'corrected-source-handoff.json', 'initial-source-hash-diagnostic.json', 'clock-label-correction-note.json', 'alpha-diagnostic-correction-note.json', 'review.json', 'index.html', 'verification.json']
(H / 'sealed-handoff.json').write_text(json.dumps({'status': 'SEALED_BOUNDED_SOURCE_IMAGE_CORRESPONDENCE_REVIEW', 'recorded_utc': report['recorded_utc'],
    'files': {n: sha(H / n) for n in names}}, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'checks_passed': len(checks), 'counts': counts, 'seal_sha256': sha(H / 'sealed-handoff.json')}))
