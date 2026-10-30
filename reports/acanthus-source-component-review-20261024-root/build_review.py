"""Review four Acanthus source records while preserving their qualified fields."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

H = Path(__file__).resolve().parent
ROOT = H.parents[1]
B = ROOT / 'sculpture-catalogue'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

assert not (H / 'sealed-handoff.json').exists(), 'Closed review packets are immutable.'
p = read(B / 'current-master.json')
assert sha(B / p['register']) == p['register_sha256']
assert sha(B / p['current_asset_reference_map']['path']) == p['current_asset_reference_map']['sha256']
g = read(B / p['register'])
assets = read(B / p['current_asset_reference_map']['path'])
options = {o['product_id']: o for o in g['options']}
edges = {e['offer_ref']: e for e in g['source_offer_edges']}
inventory_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/FRESH_PUBLIC_INVENTORY.json'
products = {o['native_product_id']: o for o in read(inventory_path)['products']}
readback_path = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
field_readback = read(readback_path)
readbacks = {o['offer_ref']: o for o in field_readback['entries']}
observed = {o['offer_ref']: o for o in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
native = read(H / 'native-readback.json')
native_by_id = {o['id']: o for o in native['records']}
assert len(native_by_id) == 13 and all('/BOLDSTONE MASTER/Products/01 Wall Sculptures/Acanthus/' in o['path_display'] for o in native['records'])
work = read(H / 'image-worklist.json')
screen = read(H / 'image-comparison-candidates.json')
scored = {(o['offer_ref'], o['gallery_index']): o for o in screen['results']}
checked = {'O069': {0, 1, 2}, 'O071': {0, 1, 2, 8}, 'O076': {0, 1, 2, 3, 4}, 'O077': {0, 1, 2, 3}}
matched = {k: v - ({3} if k == 'O077' else set()) for k, v in checked.items()}
controls = [B / x for x in ['components/checkpoint.json', 'checkpoint.json', 'components/reviews/specification_review_progress.json']]
protected = {str(x): sha(x) for x in [B / 'current-master.json', B / p['register'], B / p['workbook'],
    B / p['current_asset_reference_map']['path'], B / p['current_native_reference_map']['path'], Path(p['latest_image_coverage_audit']['path']), *controls]}
for c in controls:
    assert read(c)['current_master_catalogue'] == p

def current_image(fid):
    a = assets[fid]
    d = {k: a[k] for k in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']}
    d.update(cached_path=a['thumb'], cached_sha256=sha(a['thumb']), cached_bytes=Path(a['thumb']).stat().st_size,
        native_metadata_checked_this_batch=fid in native_by_id)
    if fid in native_by_id:
        n = native_by_id[fid]
        parent = native_by_id[a['folder_id']]
        assert n['type'] == 'file' and parent['type'] == 'folder'
        assert n['path_display'].rsplit('/', 1)[0] == parent['path_display']
        assert n['size'] == a['bytes'] and n['name'] == a['name']
        d.update(path='ns:202238505/' + n['path_display'],
            image_url='https://www.dropbox.com/preview' + quote(n['path_display'], safe='/'),
            folder_url='https://www.dropbox.com/home' + quote(parent['path_display'], safe='/'),
            native_metadata=n, native_parent_metadata=parent)
    return d

definitions = [
 ('O069', 'BSI-A9FE7D79863A', 'The three checked source frames correspond to Bronze photographs001,003 and005. The retained source reference003 is the second gallery frame; the selected individual front001 is the first.',
  '30 × 30 × 6 cm and plaster/bronze-brown surface are source claims. Approximately5kg remains the accepted estimate. The earlier rear006 observation is not transferred as proof for the selected cast.'),
 ('O071', 'BSI-2CA935C1A57A', 'The first source image is the retained Gold Leaf display scene; the second and third show the individual Gold Leaf panel001/002. Gallery8 is a rear photograph reused in the White source gallery.',
  '50 × 30 × 6 cm, approximately8kg and plaster with gold leaf remain source claims. The photograph does not establish leaf composition, cast chemistry, fitted fixing applicability or stock.'),
 ('O076', 'BSI-9C7406B46836', 'The first source image corresponds to the selected Full White panel002. The next two show the same design in two wall placements. Gallery3 is an individual view004; gallery4 repeats the Gold gallery rear photograph.',
  'The two displayed placements do not create another component design or establish an offered pair. The reused rear photograph does not certify White hardware. Existing individual selling policy and source claims remain qualified.'),
 ('O077', 'BSI-C02D6DF365D3', 'The first source image corresponds to the Flower fireplace scene; gallery1/2 correspond to individual photographs001/003. Gallery3 contains Flower on the right of a mixed garden display.',
  'The garden image is arrangement context; no exact Dropbox file was established by the77-reference Acanthus cache screen. This is not a whole-library absence claim or a new photograph request. Current individual dimensions, weight, material and fixing retain their qualifications.'),
]
components, cases, bindings, viewed, current_pictures = [], [], [], {}, {}
for ref, oid, finding, limitation in definitions:
    edge = edges[ref]
    product = products[edge['source_offer']['sq_id']]
    assert len(product['variants']) == 1
    variant = product['variants'][0]
    rb = readbacks[ref]
    tup = {'product_id': product['native_product_id'], 'variant_id': variant['native_variant_id'], 'sku_raw': variant['sku']}
    assert observed[ref]['observed_native_source_tuple'] == tup
    assert (rb['native_product_id'], rb['native_variant_id'], rb['sku']) == (tup['product_id'], tup['variant_id'], tup['sku_raw'])
    assert rb['all_nine_compared_fields_equal'] and all(x['equal'] for x in rb['fields'])
    assert variant['native_image_ids'] == [] and variant['option_attributes'] == {}
    media = []
    for row in work['source_media']:
        if row['offer_ref'] != ref:
            continue
        x = dict(row)
        x['visually_reviewed_this_batch'] = x['gallery_index'] in checked[ref]
        x['numerically_screened_this_batch'] = bool(x['cached_path'])
        if x['cached_path']:
            assert sha(x['cached_path']) == x['sha256']
        if x['visually_reviewed_this_batch']:
            viewed[x['cached_path']] = {'path': x['cached_path'], 'sha256': x['sha256'], 'role': 'Source frame', 'visually_reviewed': True}
        if x['gallery_index'] in matched[ref]:
            candidate = scored[(ref, x['gallery_index'])]['closest_candidates'][0]
            assert candidate['whole_frame_RGB_RMSE_96px'] < 2
            target = current_image(candidate['file_id'])
            current_pictures[target['file_id']] = target
            binding = {'offer_ref': ref, 'gallery_index': x['gallery_index'], 'native_media_id': x['media_id'],
                'source_url': x['url'], 'source_cached_path': x['cached_path'], 'source_cached_sha256': x['sha256'],
                'current_reference': target, 'whole_frame_RGB_RMSE_96px': candidate['whole_frame_RGB_RMSE_96px'],
                'source_and_target_visually_reviewed': True, 'same_photograph_correspondence_supported': True,
                'identical_original_encoded_bytes_verified': False, 'physical_cast_or_build_verified': False,
                'new_platform_pair_or_variant_assignment': False, 'new_image_role': False}
            bindings.append(binding)
        media.append(x)
    o = options[oid]
    assert o['product_id'] in g['active_option_ids'] and len(o['master_fields']) == 6
    assert all(o[k] == assets[o['file_id']][k] for k in ['folder_id', 'image_url', 'folder_url'])
    reference = current_image(o['file_id'])
    assert reference['native_metadata_checked_this_batch']
    current_pictures[reference['file_id']] = reference
    components.append({'product_id': oid, 'name': o['name'], 'canonical_component_id': o['canonical_component_id'],
        'source_offer_ref': ref, 'source_SKU': variant['sku'], 'current_reference': reference,
        'finding': finding, 'limitation': limitation, 'master_fields': o['master_fields']})
    cases.append({'offer_ref': ref, 'native_tuple': tup, 'source_url': edge['source_offer']['source_url'],
        'source_locator': product['source_locator'], 'native_variant': variant,
        'captured_export_observation': observed[ref], 'all_nine_source_fields_readback': rb,
        'retained_source_offer': edge['source_offer'], 'retained_member_scope': edge['members'],
        'recorded_source_reference_before_review': edge['current_primary_reference'],
        'actual_source_reference': current_image(edge['current_primary_reference']['file_id']),
        'source_description_text': product['description_text'], 'gallery': media,
        'finding': finding, 'limitation': limitation,
        'historical_shopify_handle': edge['source_offer']['sh_handle'] or None,
        'current_shopify_inventory_absence_not_inferred': True})

for target in current_pictures.values():
    viewed[target['cached_path']] = {'path': target['cached_path'], 'sha256': target['cached_sha256'], 'role': 'Dropbox rendition', 'visually_reviewed': True}
assert len(bindings) == 15 and len(current_pictures) == 14 and len(viewed) == 29
assert sum(len(x) for x in checked.values()) == 16
assert work['source_media_total'] == 34 and work['source_renditions_available'] == 31
flower = current_image('id:cnqzTNngPVsAAAAAAAyh5Q')
old_flower = assets[flower['file_id']]
assert flower['path'].lower() == old_flower['path'].lower() and flower['path'] != old_flower['path']
navigation = {'status': 'CASE_ONLY_LINK_REFRESH_PREPARED_NO_NATIVE_CHANGE', 'file_id': flower['file_id'],
    'folder_id': flower['folder_id'], 'previous_reference': {k: old_flower[k] for k in ['path', 'image_url', 'folder_url']},
    'fresh_reference': {k: flower[k] for k in ['path', 'image_url', 'folder_url']},
    'actual_file_or_folder_parent_changes': 0, 'native_writes': 0, 'same_component_and_roles': True}
write(H / 'prepared-flower-case-link-refresh.json', navigation)
inputs = {str(x): sha(x) for x in [inventory_path, readback_path, H / 'native-readback.json', H / 'image-worklist.json', H / 'image-comparison-candidates.json']}
for source in field_readback['sources']:
    assert sha(source['path']) == source['sha256']
    inputs[source['path']] = source['sha256']
counts = {'existing_individual_options': 4, 'full_qualified_working_fields': 24, 'retained_source_offers': 4,
    'gallery_media_records': 34, 'source_renditions_available_and_numerically_screened': 31,
    'source_media_frames_visually_reviewed': 16, 'distinct_source_renditions_viewed': 15,
    'distinct_Dropbox_renditions_viewed': 14, 'total_distinct_images_viewed': 29,
    'photo_correspondences_supported': 15, 'unviewed_media_records': 18,
    'live_metadata_file_readbacks': 7, 'live_metadata_folder_readbacks': 6,
    'new_platform_pairs': 0, 'new_product_records': 0, 'new_physical_verifications': 0,
    'new_owner_questions': 0, 'native_or_platform_writes': 0, 'canonical_writes': 0}
observations = [
    'The four existing individual options retain all24 complete qualified field objects and their accepted names.',
    'Source and individual photographs are compared by their complete frames. Saved renditions support photograph correspondence; original encoded-byte equality and physical cast identity are not certified.',
    'The Gold and White Full galleries reuse the same rear photograph: O071 gallery8 and O076 gallery4, current Gold folder010. Two visible keyhole-style plates belong to that photograph only; no fitted-hardware transfer between finishes.',
    'The Full White display scene contains two wall placements of the existing design. It does not establish a second design, physical stock count or a new pair SKU.',
    'The Flower garden frame is a mixed display. It is retained as source context without an exact Dropbox binding; only77 cached Acanthus references were screened, with no whole-library absence claim.',
    'Live metadata confirms seven key files and six containing folders. Flower White In Situ has a capitalization-only link correction; its stable file and folder IDs and actual parent are unchanged.',
    'The31 available source renditions were numerically screened;16 media frames were visually reviewed. Eighteen further gallery records remain unviewed, including three without a saved source rendition.',
    'Four captured Squarespace product/variant/SKU tuples are preserved. None has a recorded historical Shopify handle; no current account-wide absence or new shared-SKU pair is inferred.',
    'Existing prices remain working estimates and availability remains the owner1–2 week made-to-order policy. The source stock settings do not certify physical stock. Custom sizes, finishes, textures, materials and orientation remain offered under existing policy.',
]
result = {'status': 'ACANTHUS_SOURCE_COMPONENT_REVIEW_COMPLETE_NO_CANONICAL_CHANGES',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'baseline_protected_files': protected,
    'asset_map_binding': p['current_asset_reference_map'], 'components': components, 'source_records': cases,
    'photo_bindings': bindings, 'images_viewed': list(viewed.values()), 'observations': observations,
    'counts': counts, 'source_inputs': inputs, 'native_metadata_readback': str(H / 'native-readback.json'),
    'prepared_navigation_refresh': navigation,
    'analysis_method': 'Whole-frame EXIF-normalized96px RGB comparison in memory, followed by visual inspection of the15 recorded correspondences. No listing images created, edited or cropped.',
    'standing_holds_retained': True}
write(H / 'review.json', result)

cards = []
for c in components:
    x = c['current_reference']
    rows = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<p class="qualification">' + esc(v['state']) + '</p></td></tr>' for k, v in c['master_fields'].items())
    cards.append('<article id="' + esc(c['product_id']) + '"><h2>' + esc(c['name']) + '</h2><p>' + esc(c['finding']) + '</p><p>' + esc(c['limitation']) + '</p><p><a href="' + esc(x['image_url']) + '">Individual image</a> · <a href="' + esc(x['folder_url']) + '">Containing folder</a></p><img class="primary" src="' + esc(x['cached_path']) + '"><p>Source ' + esc(c['source_offer_ref']) + ', SKU ' + esc(c['source_SKU']) + '</p><table>' + rows + '</table><p><small>' + esc(x['file_id']) + ' / ' + esc(x['folder_id']) + '</small></p></article>')
comparisons = []
for x in bindings:
    a = x['current_reference']
    comparisons.append('<section><h3>' + esc(x['offer_ref']) + ' gallery ' + str(x['gallery_index']) + '</h3><p><a href="' + esc(a['image_url']) + '">Dropbox image</a> · <a href="' + esc(a['folder_url']) + '">Containing folder</a></p><div class="images"><figure><img loading="lazy" src="' + esc(x['source_cached_path']) + '"><figcaption>Saved source rendition</figcaption></figure><figure><img loading="lazy" src="' + esc(a['cached_path']) + '"><figcaption>' + esc(a['name']) + '</figcaption></figure></div></section>')
garden = next(x for x in work['source_media'] if x['offer_ref'] == 'O077' and x['gallery_index'] == 3)
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Acanthus individual source reviews</title><style>body{font:17px Arial;line-height:1.5;max-width:1100px;margin:40px auto;padding:0 20px;color:#222}article,section{border-top:1px solid #bbb;padding:24px 0}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd;overflow-wrap:anywhere}.primary{max-width:450px;width:100%}.qualification{font-size:13px;color:#555}.images{display:flex;gap:18px;flex-wrap:wrap}figure{width:400px;margin:0}figure img{width:100%;max-height:530px;object-fit:contain}figcaption{font-size:14px}</style></head><body><h1>Acanthus individual source reviews</h1><p>Four existing individual options, with their current image and folder IDs and24 complete qualified specification fields.</p><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in observations) + '</ul>' + ''.join(cards) + '<h2>Checked photograph correspondences</h2><p>Gallery indices are zero-based. Comparison of saved renditions supports the photograph links; original encoded-byte identity is unverified.</p>' + ''.join(comparisons) + '<h2>Mixed garden display retained as source context</h2><p>No exact Dropbox file binding established in the scoped Acanthus cache screen. Flower appears on the right; the other designs do not become components of the individual Flower offer.</p><img class="primary" src="' + esc(garden['cached_path']) + '"><h2>Fresh Flower display-folder link</h2><p><a href="' + esc(flower['image_url']) + '">Display image</a> · <a href="' + esc(flower['folder_url']) + '">Actual containing folder</a>. The same file and folder IDs are retained.</p></body></html>'
(H / 'index.html').write_text(page)
for path, expected in protected.items():
    assert sha(path) == expected, path
verification = {'status': 'PASS', 'counts': counts, 'all24full_qualified_fields_preserved': True,
    'all_four_product_variant_SKU_tuples_and36_source_fields_checked': True,
    'all15_recorded_photo_correspondences_visually_checked': True,
    'all13live_metadata_ID_readbacks_match_expected_objects': True,
    'selected_options_and_photograph_roles_unchanged': True, 'all_protected_files_unchanged': True,
    'review_sha256': sha(H / 'review.json'), 'page_sha256': sha(H / 'index.html')}
write(H / 'verification.json', verification)
sealed = [Path(__file__), H / 'review.json', H / 'verification.json', H / 'index.html',
    H / 'native-readback.json', H / 'image-worklist.json', H / 'image-comparison-candidates.json', H / 'prepared-flower-case-link-refresh.json']
write(H / 'sealed-handoff.json', {'status': 'SEALED_LOCAL_ACANTHUS_SOURCE_COMPONENT_REVIEW',
    'recorded_utc': result['recorded_utc'], 'files': {str(x): sha(x) for x in sealed}})
for i, c in enumerate(components, 1):
    print('ITEM', i, c['name'])
    print('Image:', c['current_reference']['image_url'])
    print('Containing folder:', c['current_reference']['folder_url'])
    print('Finding:', c['finding'])
    for k, v in c['master_fields'].items():
        print(k + ': ' + v['display'])
print(json.dumps(verification, ensure_ascii=False))
