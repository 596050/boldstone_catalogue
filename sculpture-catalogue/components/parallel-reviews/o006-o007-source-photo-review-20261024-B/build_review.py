"""Bounded cached-photograph review; writes only this review directory."""
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

HERE = Path(__file__).resolve().parent
B = HERE.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
esc = lambda v: html.escape(str(v), quote=True)
recorded = datetime.now(timezone.utc).isoformat()

base = B / 'components/reconciliation/current-six-url-case-navigation-master-2026-10-24'
register_path = base / 'canonical-master-register.json'
pointer_path = B / 'current-master.json'
pointer_bytes = pointer_path.read_bytes()
pointer = json.loads(pointer_bytes)
pointer_sha = hashlib.sha256(pointer_bytes).hexdigest()
assets_path = B / pointer['current_asset_reference_map']['path']
assert sha(assets_path) == pointer['current_asset_reference_map']['sha256']
g = read(register_path)
assets = read(assets_path)
previous_assets = read(base / 'current-assets.json')
moon_scope = lambda rows: {k: v for k, v in rows.items() if '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moon Crater Phase/' in v.get('path', '')}
assert moon_scope(assets) == moon_scope(previous_assets)
options = {x['product_id']: x for x in g['options']}
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
observations = {x['offer_ref']: x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
index_path = B / 'components/evidence/offer_review_index.json'
index = {x['ref']: x for x in read(index_path)}
claims_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-02/SOURCE_NATIVE_CLAIMS.json'
claims = read(claims_path)['offers']
readback_path = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
triage_path = B / 'components/parallel-reviews/unpaired43-next-evidence-20261024-B/next-evidence-review.json'
protected_paths = [register_path, B / pointer['workbook'], base / 'image-coverage-current.json']
protected = {str(p): sha(p) for p in protected_paths}
assert protected[str(register_path)] == 'd10946390d3858ce1f5c6a66caca988b9a61a1ce2ab1d1776d28bebeec4453a1'
assert protected[str(B / pointer['workbook'])] == '4c1bb8cccbf1cc5111e747e3084052937346828b80c2f8de203450bfa43ccae6'

def image_record(path):
    path = Path(path)
    with Image.open(path) as im:
        size = list(im.size)
        orientation = im.getexif().get(274)
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size,
            'stored_dimensions': size, 'EXIF_orientation': orientation}

def native_record(fid, role, visually_viewed=True):
    a = assets[fid]
    assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moon Crater Phase/' in a['path']
    result = {k: a[k] for k in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']}
    result.update(image_record(a['thumb']))
    result['native_path'] = a['path']
    result['role'] = role
    result['visually_opened_this_turn'] = visually_viewed
    result['cached_representation'] = 'original' if a.get('current_original_content_rehashed') and a.get('original') == a['thumb'] else 'thumbnail'
    result['new_download'] = False
    if result['cached_representation'] == 'original':
        assert result['sha256'] == a['sha256']
    return result

definitions = [
    {
        'offer_ref': 'O006', 'option_id': 'BSI-46F6DB226213', 'design_id': 'BC-MCP-4',
        'status': 'APPEARANCE_ASSOCIATION_SUPPORTED_EXACT_SOURCE_FILE_UNRESOLVED',
        'finding': 'The three retained source frames support an appearance association with the existing Moon Crater Phase 4 — Verdigris and Rust option. They show the same distinctive rust-and-turquoise patch arrangement as current references 001, 002 and selected 003. An exact original-file binding is not established.',
        'features': [
            'Broad turquoise plate with connected rust patches across the upper centre and right, a separate left-lower rust island, and a lower-right rust island.',
            'The same patch arrangement is visible in the three source frames and the existing Verdigris and Rust references despite different framing/backgrounds.',
            'The separate MCP4 Verdigris reference is predominantly turquoise with much less rust; the source title alone must not merge the two accepted options.'
        ],
        'appearance_association_supported': True,
        'current_reference_ids': [
            ('id:cnqzTNngPVsAAAAAAAylRA', 'Current selected MCP4 Verdigris and Rust reference 003'),
            ('id:cnqzTNngPVsAAAAAAAylQw', 'Existing MCP4 Verdigris and Rust close reference 001'),
            ('id:cnqzTNngPVsAAAAAAAuRMg', 'Existing MCP4 Verdigris and Rust close reference 002'),
            ('id:cnqzTNngPVsAAAAAAAygog', 'Separate MCP4 Verdigris option; contrast only'),
        ],
        'next_evidence': 'A retained original-file/provenance link would be needed to certify the exact source photograph as a Dropbox file. The supported appearance association can be retained without changing product count, source identifiers or specifications.'
    },
    {
        'offer_ref': 'O007', 'option_id': 'BSI-EBD43DF0704F', 'design_id': 'BC-MCP-1',
        'status': 'EXACT_SOURCE_PHOTO_AND_SELECTED_APPEARANCE_BINDING_UNRESOLVED',
        'finding': 'The three retained source frames do not establish an exact photograph or patch-pattern match to the current MCP1 Verdigris and Rust selected reference. The source has a more pronounced outer ring and a different rust pattern. Preserve the earlier proposed MCP1 relationship as qualified; do not create a pure Verdigris product or substitute another component from visual similarity alone.',
        'features': [
            'The source first frame shows a pronounced outer ring around a smaller centre, with extensive rust along the left edge and lower ring.',
            'MCP1 selected 002 and supporting 003/004/007 show a broader centre and a different large central rust patch with turquoise toward the upper/right portions.',
            'MCP2 and MCP3 contrast photographs share circular geometry but do not establish the same source photograph or patch arrangement.',
            'The older structured Product image names IMG_6171 (a detail), while the gallery/export first image is IMG_6168. These source roles are retained separately.'
        ],
        'appearance_association_supported': False,
        'current_reference_ids': [
            ('id:cnqzTNngPVsAAAAAAAygZw', 'Current selected MCP1 Verdigris and Rust reference 002'),
            ('id:cnqzTNngPVsAAAAAAAygaA', 'MCP1 Verdigris and Rust reference 003; contrast'),
            ('id:cnqzTNngPVsAAAAAAAygaQ', 'MCP1 Verdigris and Rust reference 004; contrast'),
            ('id:cnqzTNngPVsAAAAAAAygZg', 'MCP1 Verdigris and Rust reference 007; contrast'),
            ('id:cnqzTNngPVsAAAAAAAygfw', 'MCP3 Verdigris and Rust reference 002; contrast only'),
            ('id:cnqzTNngPVsAAAAAAAygcw', 'MCP2 Verdigris and Rust reference 003; contrast only'),
        ],
        'next_evidence': 'An exact original photograph or a direct identity/provenance record is needed before replacing the qualified source-to-component association. No new owner question is raised by this packet.'
    }
]

cases = []
source_images = []
native_images = []
source_inputs = {str(p): sha(p) for p in [index_path, claims_path, readback_path, triage_path, register_path, assets_path]}
for definition in definitions:
    ref = definition['offer_ref']
    o = options[definition['option_id']]
    assert o['canonical_design_id'] == definition['design_id']
    a = assets[o['file_id']]
    assert all(o[k] == a[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url'])
    c = claims[ref]['Squarespace']
    assert len(c['variants']) == 1
    v = c['variants'][0]
    ob = observations[ref]
    assert ob['observed_native_source_tuple'] == {'product_id': v['native_product_id'], 'variant_id': v['native_variant_id'], 'sku_raw': v['sku']}
    assert not v['native_image_ids'] and not v['native_images'] and not v['option_attributes']
    assert ob['observed_first_source_image_url'] == c['native_media_items'][0]['assetUrl'] == index[ref]['images'][0]['url']
    assert all(edges[ref]['source_offer'][k] == '' for k in ['image_file_id', 'image_folder_id', 'image_path'])
    rawpath = Path(v['source_locator']['path'])
    assert sha(rawpath) == v['source_locator']['body_sha256']
    raw = read(rawpath)
    raw_variant = raw
    for part in v['source_locator']['json_pointer'].strip('/').split('/'):
        raw_variant = raw_variant[int(part)] if isinstance(raw_variant, list) else raw_variant[part]
    assert raw_variant == v['native_record']
    source_inputs[str(rawpath)] = sha(rawpath)
    pictures = []
    for im in index[ref]['images']:
        row = image_record(im['path'])
        assert row['sha256'] == im['sha256']
        media = next(m for m in c['native_media_items'] if m['assetUrl'] == im['url'])
        row.update(offer_ref=ref, gallery_order=im['order'], source_image_url=im['url'],
                   native_media_id=media['id'], filename=media['filename'],
                   native_reported_original_dimensions=media['originalSize'],
                   role='Retained source gallery rendition; 16 October evidence index',
                   visually_opened_this_turn=True, new_download=False,
                   cached_representation='750-pixel-wide retained rendition; not original-sized bytes')
        pictures.append(row)
        source_images.append(row)
    for fid, role in definition['current_reference_ids']:
        row = native_record(fid, role)
        pictures.append(row)
        native_images.append(row)
    structured = next(x for x in index[ref]['structured'] if x.get('@type') == 'Product')
    case = {k: val for k, val in definition.items() if k != 'current_reference_ids'}
    case.update(
        name=o['name'], native_tuple=ob['observed_native_source_tuple'],
        native_variant_locator=v['source_locator'], native_variant_raw=v['native_record'],
        latest_captured_export_observation=ob,
        retained_source_offer=edges[ref]['source_offer'], retained_BOM_members=edges[ref]['members'],
        source_url=c['url'], source_description=c['description_text'],
        native_gallery_metadata=c['native_media_items'], native_gallery_count=len(c['native_media_items']),
        source_frames_visually_reviewed=len(index[ref]['images']),
        remaining_native_gallery_frames_not_visually_reviewed=len(c['native_media_items']) - len(index[ref]['images']),
        first_gallery_image_url=c['native_media_items'][0]['assetUrl'],
        structured_Product_image_url=structured['image'],
        current_reference={k: o[k] for k in ['product_id', 'canonical_design_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url']},
        master_fields=o['master_fields'], images=pictures,
        exact_source_original_file_bound=False, exact_photo_equivalence_certified=False,
        new_platform_pair=False, new_variant_SKU_assignment=False,
        exact_current_size_build_or_physical_cast_verified=False,
        physical_specifications_verified=False, new_photo_role=False, new_product=False,
        source_clock_scope='Retained 16 October gallery renditions; 21 October collection metadata; retained 24 October export readback. No new network observation.'
    )
    cases.append(case)

# Full-frame similarity is a reproducible candidate-ranking aid, not an identity test.
def screen_pixels(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert('RGB').resize((64, 64), Image.Resampling.LANCZOS)

candidates = []
pixels = {}
for fid, a in sorted(assets.items()):
    if '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moon Crater Phase/' not in a.get('path', ''):
        continue
    p = Path(a['thumb'])
    assert p.is_file()
    candidates.append({'file_id': fid, 'folder_id': a['folder_id'], 'native_path': a['path'], 'cached_path': str(p), 'cached_sha256': sha(p)})
    pixels[fid] = screen_pixels(p)
assert len(candidates) == 178
screen_rows = []
for source in source_images:
    first = screen_pixels(source['path'])
    scores = []
    for fid, second in pixels.items():
        diff = ImageChops.difference(first, second)
        score = math.sqrt(sum(x * x for x in ImageStat.Stat(diff).rms) / 3)
        scores.append({'file_id': fid, 'RGB_RMSE_0_255': round(score, 6)})
    screen_rows.append({'offer_ref': source['offer_ref'], 'source_filename': source['filename'],
                        'source_sha256': source['sha256'], 'ranked_candidates': sorted(scores, key=lambda x: (x['RGB_RMSE_0_255'], x['file_id']))})
screen = {'method': 'EXIF-normalized RGB entire frame resized in memory to 64 by 64, channel RMSE. No crops, generated images or edited image files.',
          'purpose': 'Bounded ranking of cached candidates only. Different crops, aspect ratios and backgrounds can give high scores for related pictures. Scores do not certify absence or identity.',
          'candidate_count': len(candidates), 'source_frame_count': len(source_images), 'candidates': candidates, 'scores': screen_rows,
          'whole_library_absence_inferred': False, 'all_candidates_visually_reviewed': False}
dump(HERE / 'cached-candidate-screen.json', screen)

report = {
    'status': 'BOUNDED_CACHED_PHOTO_REVIEW_COMPLETE_NO_CANONICAL_CHANGES', 'recorded_utc': recorded,
    'baseline_protected_files': protected,
    'pointer_observed_at_start': {'path': str(pointer_path), 'sha256': pointer_sha, 'status': pointer['status']},
    'asset_navigation_binding': {'path': str(assets_path), 'sha256': sha(assets_path), 'lookup': 'Explicit current-master.current_asset_reference_map.path', 'Moon_Crater_Phase_subset_equal_to_previous_map': True},
    'source_inputs': source_inputs, 'cases': cases,
    'visually_reviewed_source_renditions': len(source_images), 'visually_reviewed_Dropbox_cached_images': len(native_images),
    'source_gallery_scope': 'Three of eight source media items viewed for each offer; six viewed frames total. Ten additional native gallery metadata rows are retained but not visually claimed.',
    'bounded_cached_candidate_screen': {'path': str(HERE / 'cached-candidate-screen.json'), 'sha256': sha(HERE / 'cached-candidate-screen.json')},
    'outcome': {'appearance_associations_supported': 1, 'exact_original_file_bindings_added': 0,
                'unresolved_exact_source_photo_cases_retained': 2, 'new_product_records': 0,
                'new_platform_pairs': 0, 'new_physical_verifications': 0},
    'ownership': 'B reviewer isolated local evidence packet; main remains sole canonical publisher. Echo navigation publication belongs to main/recovery and is independent.',
    'standing_boundaries': ['Existing qualified source/BOM relationships and working specifications retained.',
                            'No pure Verdigris MCP1 product created and no selected image replaced.',
                            'No whole-library absence, physical stock, mould, hardware or current live offer inferred.',
                            'Existing context/series/Wall Circle/Frozen Fish holds retained; no new owner question.'],
    'native_calls': 0, 'native_writes': 0, 'platform_writes': 0, 'shared_canonical_writes': 0,
}
dump(HERE / 'review.json', report)

cards = []
lines = ['O006 / O007 cached source photograph review', 'Evidence only; no catalogue or Dropbox changes.', '']
for case in cases:
    figures = []
    for im in case['images']:
        links = ('<a href="' + esc(im['image_url']) + '">Dropbox image</a> · <a href="' + esc(im['folder_url']) + '">Containing folder</a>') if 'file_id' in im else '<a href="' + esc(im['source_image_url']) + '">Source image URL</a>'
        figures.append('<figure><img loading="lazy" src="' + esc(Path(im['path']).as_uri()) + '"><figcaption>' + esc(im['role']) + '<p>' + links + '</p><small>' + esc(im['cached_representation']) + '</small></figcaption></figure>')
    fields = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<p class="note">' + esc(v['state']) + '</p></td></tr>' for k, v in case['master_fields'].items())
    o = case['current_reference']
    cards.append('<article id="' + case['offer_ref'] + '"><h2>' + esc(case['offer_ref'] + ' · ' + case['name']) + '</h2><p>' + esc(case['finding']) + '</p><p><a href="' + esc(case['source_url']) + '">Source listing</a> · <a href="' + esc(o['image_url']) + '">Current image</a> · <a href="' + esc(o['folder_url']) + '">Containing folder</a></p><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in case['features']) + '</ul><p>Viewed 3 of 8 retained source gallery items. The source variant contains no image IDs or option attributes.</p><div class="images">' + ''.join(figures) + '</div><h3>Existing working specifications, unchanged</h3><table>' + fields + '</table><p>' + esc(case['next_evidence']) + '</p></article>')
    lines.extend([case['offer_ref'] + ': ' + case['name'], case['finding'], 'Image: ' + o['image_url'], 'Containing folder: ' + o['folder_url'], 'Source photograph: ' + case['first_gallery_image_url'], 'Source tuple: ' + json.dumps(case['native_tuple'])])
    lines.extend(k + ': ' + v['display'] for k, v in case['master_fields'].items())
    lines.append('')
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Moon Crater Phase source photo checks</title><style>body{font:17px system-ui;line-height:1.5;max-width:1140px;margin:35px auto;padding:0 20px;color:#222}article{margin-top:45px;border-top:1px solid #bbb;padding-top:20px}.images{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:22px}figure{margin:0}img{width:100%;height:340px;object-fit:contain;background:#f5f5f5}figcaption,.note{font-size:14px}small{color:#555}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top;white-space:pre-line}th{width:22%}</style></head><body><h1>Moon Crater Phase: two source-photo checks</h1><p>One appearance association is supported; exact original-photo bindings remain unresolved for both source records. This isolated review uses retained local evidence. Existing products, specifications and source relationships are unchanged.</p><p>Source coverage: six viewed cached gallery frames, ten viewed Dropbox references, and a machine-ranking screen of 178 cached Moon Crater Phase images. This is not a new Dropbox inventory or proof that an original is absent.</p>' + ''.join(cards) + '</body></html>'
(HERE / 'index.html').write_text(page)
(HERE / 'terminal-review.txt').write_text('\n'.join(lines) + '\n')
assert all(sha(p) == expected for p, expected in protected.items())
dump(HERE / 'input-manifest.json', {'recorded_utc': recorded, 'protected_files': protected, 'source_inputs': source_inputs,
                                  'source_renditions': source_images, 'viewed_Dropbox_cached_images': native_images})
print(json.dumps({'status': report['status'], 'source_frames_viewed': 6, 'Dropbox_references_viewed': len(native_images), 'candidates_ranked': len(candidates), 'outcome': report['outcome']}))
