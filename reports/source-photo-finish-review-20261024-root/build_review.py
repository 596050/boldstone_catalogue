"""Review two retained source photographs against current named component options."""
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
B = ROOT / 'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, d: Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
digest = lambda d: hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
p = read(B / 'current-master.json')
base = (B / p['register']).parent
g = read(B / p['register'])
assets = read(base / 'current-assets.json')
options = {x['product_id']: x for x in g['options']}
sources = {x['offer_ref']: x for x in g['source_offer_edges']}
claims_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-02/SOURCE_NATIVE_CLAIMS.json'
claims = read(claims_path)['offers']
observation_path = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
photo_path = B / 'components/reviews/moon-crater-phase-review-2026-10-19/mcp2-verdigris-rust'
comparison_path = photo_path / 'public-photo-comparison.json'
public_receipt = read(photo_path / 'public-primary-download-receipt.json')
prior_comparison = read(comparison_path)
o9_manifest_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/additional-public/o009/MANIFEST.json'
o9_manifest = read(o9_manifest_path)
controls = [B / x for x in ['components/checkpoint.json', 'checkpoint.json', 'components/reviews/specification_review_progress.json']]
protected = {str(x): sha(x) for x in [B / 'current-master.json', B / p['register'], B / p['workbook'], *controls]}
for x in controls:
    assert read(x)['current_master_catalogue'] == p

source_images = []
def image_record(path, role, file_id=None, receipt=None):
    path = Path(path)
    assert path.is_file(), path
    if receipt:
        assert sha(path) == receipt['sha256']
        assert path.stat().st_size == receipt['bytes']
    with Image.open(path) as im:
        size = im.size
        orientation = im.getexif().get(274)
    row = {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size,
           'stored_dimensions': size, 'EXIF_orientation': orientation, 'role': role,
           'visually_opened_this_turn': True, 'new_network_download': False}
    if file_id:
        a = assets[file_id]
        assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/' in a['path']
        row.update(file_id=file_id, folder_id=a['folder_id'], image_url=a['image_url'], folder_url=a['folder_url'])
    source_images.append(row)
    return row

pub8 = image_record(photo_path / 'IMG_6177.jpeg', 'O008 public primary captured 19 October', receipt=public_receipt)
db8 = image_record(assets['id:cnqzTNngPVsAAAAAAAygcw']['thumb'], 'O008 current selected Dropbox photograph; original bytes rehashed', 'id:cnqzTNngPVsAAAAAAAygcw')
assert db8['sha256'] == prior_comparison['native_sha256']
blue = image_record(assets['id:cnqzTNngPVsAAAAAAAyg2Q']['thumb'], 'Separate Blue Splashes contrast reference', 'id:cnqzTNngPVsAAAAAAAyg2Q')
with Image.open(pub8['path']) as im:
    first = ImageOps.exif_transpose(im).convert('RGB')
with Image.open(db8['path']) as im:
    second = ImageOps.exif_transpose(im).convert('RGB')
assert first.size == second.size == (1512, 1943)
target = (256, round(first.height * 256 / first.width))
diff = ImageChops.difference(first.resize(target, Image.Resampling.LANCZOS), second.resize(target, Image.Resampling.LANCZOS))
rmse = math.sqrt(sum(x * x for x in ImageStat.Stat(diff).rms) / 3)
assert rmse < 2

pub9 = []
for x in o9_manifest['assets']:
    row = image_record(x['path'], 'O009 source gallery captured 21 October', receipt=x)
    row.update(source_image_url=x['requested_url'], native_media_id=x['native_media_id'], received_utc=x['received_utc'])
    pub9.append(row)
db9 = image_record(assets['id:cnqzTNngPVsAAAAAAAyegw']['thumb'], 'Current generic Verdigris selected rendition', 'id:cnqzTNngPVsAAAAAAAyegw')
hero9 = image_record(assets['id:cnqzTNngPVsAAAAAAAye3g']['thumb'], 'Historical source hero wide view; retained as history', 'id:cnqzTNngPVsAAAAAAAye3g')
copper9 = image_record(assets['id:cnqzTNngPVsAAAAAAAye4A']['thumb'], 'Separate Verdigris and Copper selected rendition', 'id:cnqzTNngPVsAAAAAAAye4A')

case_defs = [
    ('O008', 'BSI-2E097B70CD7F', 'BSI-177C94BD0EFF',
     'The source primary is the same photograph as the selected Verdigris and Rust reference. Keep the accepted finish identity; the source title Blue does not bind the separate Blue Splashes option.',
     ['Same stone joints, panel edges and detailed turquoise/rust patch constellation.',
      'Blue Splashes has broad blue, white and dark painted areas, which the source primary does not show.'],
     [pub8, db8, blue]),
    ('O009', 'BSI-4536FDCA0DA9', 'BSI-9299D69FEF08',
     'The four source gallery frames support the existing generic Verdigris association. Keep the denser speckled Verdigris and Copper reference separate; the historical source hero is not a variant-specific selection.',
     ['Broad turquoise channels with thin copper-coloured ridge wear and irregular copper patches along the lower edge appear across the four source frames and the generic Verdigris reference.',
      'The historical wide hero and the Verdigris and Copper reference show much denser, more uniform copper speckling.',
      'The captured default variant has no finish attributes or per-variant image IDs. It cannot independently assign its SKU to an additional finish.'],
     [*pub9, db9, hero9, copper9]),
]
cases = []
observations = g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']
for ref, oid, contrast, finding, features, pictures in case_defs:
    o = options[oid]
    source = claims[ref]['Squarespace']
    variants = source['variants']
    assert len(variants) == 1
    observation = next(x for x in observations if x['offer_ref'] == ref)
    assert observation['observed_native_source_tuple']['sku_raw'] == variants[0]['sku']
    assert observation['observed_first_source_image_url'] == source['native_media_items'][0]['assetUrl']
    cases.append({
        'offer_ref': ref, 'option_id': oid, 'name': o['name'], 'finding': finding, 'discriminating_features': features,
        'native_tuple': {k: variants[0][k] for k in ['native_product_id', 'native_variant_id', 'sku']},
        'native_variant_locator': variants[0]['source_locator'],
        'source_offer': sources[ref]['source_offer'],
        'source_url': source['url'], 'source_description_text': source['description_text'],
        'source_first_image_url': source['native_media_items'][0]['assetUrl'],
        'source_media_count': len(source['native_media_items']),
        'source_photo_scope': 'Retained captures; no new source-page or source-image fetch this turn.',
        'current_reference': {k: o[k] for k in ['product_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url']},
        'contrast_reference': {k: options[contrast][k] for k in ['product_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url']},
        'master_fields': o['master_fields'], 'images': pictures,
        'appearance_association_supported': True,
        'new_platform_pair': False, 'new_variant_SKU_assignment': False,
        'exact_current_custom_size_build_or_cast_verified': False,
        'physical_specifications_verified': False,
        'shopify_handle': sources[ref]['source_offer']['sh_handle'] or None,
        'current_shopify_absence_inferred': False,
    })
result = {
    'status': 'RETAINED_SOURCE_PHOTO_ASSOCIATIONS_CHECKED_NO_CATALOGUE_CHANGES',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'baseline': protected,
    'register_sha256': p['register_sha256'], 'workbook_sha256': p['workbook_sha256'],
    'cases': cases, 'images_checked': source_images,
    'O008_image_analysis': {'method': 'EXIF normalized RGB, entire frame resized in memory to256px wide, channel RMSE; no image files edited or cropped.',
        'resized_RGB_RMSE_0_255': rmse, 'encoded_bytes_equal': pub8['sha256'] == db8['sha256'],
        'photo_level_match_supported_by_visual_review': True, 'physical_cast_identity_not_inferred': True},
    'source_inputs': {str(x): sha(x) for x in [claims_path, observation_path, comparison_path, photo_path / 'public-primary-download-receipt.json', o9_manifest_path]},
    'standing_boundaries': ['All source clocks retained. No live product availability or account access claimed.',
        'Keep actual dimensions, weight, material and fitted fixing unverified where the master already labels them.',
        'No rear photograph transferred across finish options.', 'No new owner question or change to existing photo holds.'],
    'native_writes': 0, 'platform_writes': 0, 'canonical_writes': 0,
    'new_physical_verifications': 0, 'new_platform_pairs': 0,
}
write(H / 'review.json', result)
esc = lambda x: html.escape(str(x), quote=True)
cards = []
for c in cases:
    images = ''.join('<figure><img loading="lazy" src="' + esc(x['path']) + '"><figcaption>' + esc(x['role']) +
        ('<p><a href="' + esc(x['image_url']) + '">Dropbox image</a> · <a href="' + esc(x['folder_url']) + '">Containing folder</a></p>' if x.get('file_id') else '') + '</figcaption></figure>' for x in c['images'])
    fields = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<p class="qualification">' + esc(v['state']) + '</p></td></tr>' for k, v in c['master_fields'].items())
    n = c['native_tuple']
    cards.append('<article id="' + esc(c['offer_ref']) + '"><h2>' + esc(c['name']) + '</h2><p>' + esc(c['finding']) +
        '</p><p><a href="' + esc(c['source_url']) + '">Source listing</a> · <a href="' + esc(c['current_reference']['image_url']) +
        '">Current Dropbox image</a> · <a href="' + esc(c['current_reference']['folder_url']) + '">Containing folder</a></p>' +
        '<p>Source product ' + esc(n['native_product_id']) + '; variant ' + esc(n['native_variant_id']) + '; SKU ' + esc(n['sku']) +
        '. No recorded Shopify handle.</p><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in c['discriminating_features']) +
        '</ul><div class="images">' + images + '</div><h3>Current working specifications</h3><table>' + fields + '</table></article>')
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Source photograph and finish review</title><style>body{font:17px Arial;line-height:1.5;max-width:1100px;margin:40px auto;padding:0 20px;color:#222}article{border-top:1px solid #bbb;padding-top:24px;margin-top:40px}.images{display:flex;flex-wrap:wrap;gap:20px}figure{width:300px;margin:0 0 20px}img{width:100%;max-height:430px;object-fit:contain}figcaption{font-size:14px}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd}th{width:23%}.qualification{font-size:13px;color:#555;white-space:pre-line}</style></head><body><h1>Source photograph and finish review</h1><p>Two retained source-photo comparisons. Appearance associations are supported; existing working specifications and platform relationships retain their qualifications. All pictures below were opened from existing local evidence. No Dropbox or platform changes were made.</p>' + ''.join(cards) + '</body></html>'
(H / 'index.html').write_text(page)
assert all(sha(x) == expected for x, expected in protected.items())
verification = {'status': 'PASS', 'cases': 2, 'viewed_local_images': len(source_images), 'qualified_working_fields': 12,
    'source_tuple_checks': 2, 'new_platform_pairs': 0, 'new_physical_verifications': 0,
    'canonical_and_controls_unchanged': True, 'review_sha256': sha(H / 'review.json'), 'page_sha256': sha(H / 'index.html')}
write(H / 'verification.json', verification)
write(H / 'sealed-handoff.json', {'status': 'SEALED_LOCAL_REVIEW', 'recorded_utc': result['recorded_utc'],
    'files': {str(x): sha(x) for x in [Path(__file__), H / 'review.json', H / 'index.html', H / 'verification.json']}})
for i, c in enumerate(cases, 1):
    print(f"ITEM {i}: {c['name']}\n{c['finding']}\nImage: {c['current_reference']['image_url']}\nContaining folder: {c['current_reference']['folder_url']}")
    print('Source tuple:', json.dumps(c['native_tuple']))
    for k, v in c['master_fields'].items():
        print(k + ': ' + v['display'])
print(json.dumps(verification))
