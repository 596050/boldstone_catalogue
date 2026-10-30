"""Read-only Echo Pattern photo/member review against the published Echo navigation."""
import hashlib
import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
esc = lambda x: html.escape(str(x), quote=True)
pointer_bytes = (B / 'current-master.json').read_bytes()
p = json.loads(pointer_bytes)
register_path = B / p['register']
asset_path = B / p['current_asset_reference_map']['path']
native_map_path = B / p['current_native_reference_map']['path']
assert sha(register_path) == p['register_sha256']
assert sha(asset_path) == p['current_asset_reference_map']['sha256']
assert sha(native_map_path) == p['current_native_reference_map']['sha256']
g, assets = read(register_path), read(asset_path)
options = {x['product_id']: x for x in g['options']}
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
observations = {x['offer_ref']: x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
index_path = B / 'components/evidence/offer_review_index.json'
index = {x['ref']: x for x in read(index_path)}
collection_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/raw-public/collection-initial.body'
assert sha(collection_path) == '548078a564dd57cca62e466b5b3a61dc47c8d584e6eedf107f362f429686ae5c'
collection = read(collection_path)
readback_path = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
readback = read(readback_path)
readbacks = {x['offer_ref']: x for x in readback['entries']}
triage_path = B / 'components/parallel-reviews/unpaired43-next-evidence-20261024-B/next-evidence-review.json'
triage = {x['offer_ref']: x for x in read(triage_path)['rows']}
protected = {str(path): sha(path) for path in [register_path, B / p['workbook'], register_path.parent / 'image-coverage-current.json', asset_path, native_map_path]}
inputs = {str(path): sha(path) for path in [index_path, collection_path, readback_path, triage_path]}
for source in readback['sources']:
    assert sha(source['path']) == source['sha256']
    inputs[source['path']] = source['sha256']

def cached_image(path):
    path = Path(path)
    with Image.open(path) as im: size = list(im.size); orientation = im.getexif().get(274)
    return {'cached_path': str(path), 'cached_sha256': sha(path), 'cached_bytes': path.stat().st_size,
            'cached_dimensions': size, 'EXIF_orientation': orientation, 'visually_reviewed_this_turn': True}

def current_image(fid):
    a = assets[fid]
    assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Echo Sound/' in a['path']
    d = {k: a[k] for k in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']}
    d.update(cached_image(a['thumb']))
    d['cached_representation'] = 'thumbnail'
    return d

def pixels(path):
    with Image.open(path) as im: return ImageOps.exif_transpose(im).convert('RGB').resize((96,96), Image.Resampling.LANCZOS)

def image_rmse(a, b):
    return math.sqrt(sum(x*x for x in ImageStat.Stat(ImageChops.difference(pixels(a), pixels(b))).rms)/3)

definitions = [
    {
        'offer_ref': 'O057',
        'option_ids': ['BSI-BF85B0E4D43E', 'BSI-F8398FA248EE'],
        'expected_tuple': ('6a61021f90af307b67cfe621', '67336a45-a266-49bb-a3ca-a51e61673957', 'EP-30.30'),
        'photo_ids': ['id:cnqzTNngPVsAAAAAAAubWQ'],
        'finding': 'The retained White listing image is the same group photograph as current Echo Sound 1 and Echo Sound 2 White reference 087. Both existing individual White options remain separate, with the group photograph retained as context.',
        'photo_features': ['Matching two-panel composition, concentric ridges, panel edges and timber-board background.'],
        'configuration_limit': 'The captured default variant has no component choice or per-variant image IDs. The photograph shows two panels, but the source text/SKU does not establish whether that source offer supplies EP1, EP2 or both. No individual SKU assignment is added.',
        'commercial_limit': 'The source variant records £480. The owner-approved working estimates remain £225 per individual White panel. Neither a new pair price nor an allocation of £480 between components is made.',
        'weight_limit': 'The accepted approximately 4 kg per panel comes from the retained historical maker estimate, with the later 5.5/6.5 kg draft conflict preserved. The raw exported weight 4.0 has no encoded unit and is not newly certified.',
    },
    {
        'offer_ref': 'O072',
        'option_ids': ['BSI-0BE032939501', 'BSI-EF421C1D2C92'],
        'expected_tuple': ('6aa01ae74b08934e6b0d3dbe', 'f39360d5-9a28-4997-af2b-c31eae8453c9', 'EBAY-188721196311'),
        'photo_ids': ['id:cnqzTNngPVsAAAAAAAyfmA', 'id:cnqzTNngPVsAAAAAAAyflw', 'id:cnqzTNngPVsAAAAAAAyfmQ'],
        'finding': 'The three retained source frames match current Echo Pattern Two Verdigris photographs 002, 003 and 004. These checked frames all show Two. One remains an existing individual option and retained pair member; these three frames do not independently bind its appearance to this source.',
        'photo_features': ['Matching ridge pattern, turquoise channels and brown raised surfaces.', 'The panel edges, individual stone joints and wider wall framing agree with current 002, 003 and 004.'],
        'configuration_limit': 'The source describes two 30 × 30 × 7 cm panels with 60 cm combined width, while the three reviewed frames depict Two. Eighteen further gallery media records are retained as metadata only. No claim is made that the entire source gallery lacks One. The captured variant has no member choice or per-variant image IDs.',
        'commercial_limit': 'The source offer records £360. The current working estimate remains £250 per individual Verdigris panel. The source amount is not assigned to either component or divided between them.',
        'weight_limit': 'The description gives approximately 8 kg for the combined sculpture. The existing approximately 4 kg per panel is a separately qualified estimate based on the White maker estimate; this review does not divide the pair weight or certify either coloured cast.',
    },
]

cases, comparisons, option_cards = [], [], {}
native_images = {}
for definition in definitions:
    ref = definition['offer_ref']
    rb, ob, edge = readbacks[ref], observations[ref], edges[ref]
    product_id, variant_id, sku = definition['expected_tuple']
    assert (rb['native_product_id'], rb['native_variant_id'], rb['sku']) == (product_id, variant_id, sku)
    assert ob['observed_native_source_tuple'] == {'product_id': product_id, 'variant_id': variant_id, 'sku_raw': sku}
    assert rb['all_nine_compared_fields_equal'] and all(x['equal'] for x in rb['fields'])
    position, native = next((i,x) for i,x in enumerate(collection['items']) if x['id'] == product_id)
    variants = native['structuredContent']['variants']
    assert len(variants) == 1
    variant = variants[0]
    assert (variant['id'], variant['sku']) == (variant_id, sku)
    assert variant['attributes'] == {} and variant['optionValues'] == [] and variant['imageIds'] == [] and variant['images'] == []
    assert native['items'][0]['assetUrl'] == rb['source_first_image_url'] == index[ref]['images'][0]['url']
    assert len(index[ref]['images']) == len(definition['photo_ids'])
    rows = []
    for source, fid in zip(index[ref]['images'], definition['photo_ids']):
        row = {'offer_ref': ref, 'source_order': source['order'], 'source_url': source['url'],
               'source_cached_image': cached_image(source['thumb']),
               'historical_source_original_path': source['path'],
               'historical_source_original_present': Path(source['path']).is_file(),
               'historical_original_sha256_not_reverified': source['sha256'],
               'current_image': current_image(fid),
               'same_photograph_supported': True, 'original_byte_identity_verified': False,
               'physical_cast_verified': False, 'new_photo_role': False}
        media = next(x for x in native['items'] if x['assetUrl'] == source['url'])
        row['native_media_id'] = media['id']
        row['whole_frame_RGB_RMSE_96px'] = image_rmse(source['thumb'], assets[fid]['thumb'])
        assert row['whole_frame_RGB_RMSE_96px'] < 1.3
        rows.append(row); comparisons.append(row); native_images[fid] = row['current_image']
    for oid in definition['option_ids']:
        o = options[oid]
        a = assets[o['file_id']]
        assert all(o[k] == a[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url'])
        assert o['canonical_design_id'] in ['BC-ECHO-1', 'BC-ECHO-2']
        card = {k: o[k] for k in ['product_id', 'canonical_design_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url']}
        card.update(qualified_working_fields=o['master_fields'], selected_cached_image=current_image(o['file_id']),
                    sale_policy='Existing individually purchasable working option retained', new_individual_native_SKU_assignment=False)
        option_cards[oid] = card; native_images[o['file_id']] = card['selected_cached_image']
    case = {k:v for k,v in definition.items() if k not in ['photo_ids', 'expected_tuple']}
    case.update(native_tuple=ob['observed_native_source_tuple'], source_url=edge['source_offer']['source_url'],
                source_variant_locator={'path': str(collection_path), 'sha256': sha(collection_path), 'json_pointer': f'/items/{position}/structuredContent/variants/0', 'capture_utc': '2026-10-21T12:25:34.594104+00:00'},
                native_variant=variant, native_gallery_metadata=native['items'],
                source_variant_price_basis='structuredContent.variants[0].priceMoney; historical source setting, not verified live offer',
                retained_source_offer=edge['source_offer'], retained_BOM_members=edge['members'],
                latest_captured_export_observation=ob, source_field_readback=rb,
                retained_preparation=triage[ref]['current_preparation'],
                source_photo_comparisons=rows,
                source_frames_viewed=len(rows), native_gallery_media_count=len(native['items']),
                unviewed_gallery_media_count=len(native['items'])-len(rows),
                exact_native_component_choice_verified=False, physical_specifications_verified=False,
                new_platform_pair=False, source_prices_or_weights_allocated_to_members=False,
                owner_question_opened=False)
    cases.append(case)

assert len(option_cards) == 4 and len(native_images) == 7 and len(comparisons) == 4
report = {
    'status': 'TWO_SOURCE_PHOTO_AND_MEMBER_REVIEWS_COMPLETE', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'pointer_snapshot': {'sha256': hashlib.sha256(pointer_bytes).hexdigest(), 'status': p['status']},
    'current_asset_map': {'path': str(asset_path), 'sha256': sha(asset_path), 'lookup': 'current-master.current_asset_reference_map.path'},
    'protected_files': protected, 'source_inputs': inputs,
    'cases': cases, 'individual_options': list(option_cards.values()), 'viewed_current_images': list(native_images.values()),
    'summary': {'source_offers': 2, 'individual_working_options': 4, 'qualified_working_fields': 24,
                'source_renditions_viewed': 4, 'current_cached_images_viewed': 7,
                'source_photo_correspondences_supported': 4, 'unviewed_O072_media_records': 18,
                'new_products': 0, 'new_native_component_choices': 0, 'new_platform_pairs': 0, 'new_physical_verifications': 0},
    'source_scope': 'Saved source-image index and thumbnails, 21 October public collection metadata and retained 24 October export readback. No new source-page, Dropbox or account fetch.',
    'limitations': ['Source temporary downloads unavailable; current hashes verify retained renditions, not identical original source bytes.',
                    'The White group photograph remains context. No group image split or crop created.',
                    'Only three of twenty-one O072 source images were visually reviewed. No gallery-wide absence conclusion.',
                    'Current individual sale policy is settled. Exact source variant/member mapping is not established by the photographs.',
                    'No physical measurements, material formulation, fitted fixing, support load or stock quantity certified.',
                    'Existing context/series/Wall Circle/Frozen Fish holds and the sole separate Acanthus physical prompt are unchanged.'],
    'native_calls': 0, 'native_writes': 0, 'platform_writes': 0, 'canonical_writes': 0,
}
write(H / 'review.json', report)
write(H / 'source-photo-evidence-proposal.json', {
    'status': 'EVIDENCE_ONLY_FOR_MAIN_SESSION', 'apply_automatically': False,
    'baseline_register_sha256': p['register_sha256'], 'asset_map_sha256': sha(asset_path),
    'cases': [{'offer_ref': c['offer_ref'], 'native_tuple': c['native_tuple'], 'option_ids': c['option_ids'],
               'photo_correspondences': [{'source_order': x['source_order'], 'source_url': x['source_url'],
                                          'file_id': x['current_image']['file_id'], 'folder_id': x['current_image']['folder_id'],
                                          'image_url': x['current_image']['image_url'], 'folder_url': x['current_image']['folder_url'],
                                          'binding_level': 'Retained rendition photo correspondence only'} for x in c['source_photo_comparisons']],
               'configuration_limit': c['configuration_limit']} for c in cases],
    'new_products': 0, 'specification_changes': 0, 'source_member_SKU_assignments': 0,
    'native_actions': [], 'platform_actions': [], 'owner_questions': []})

sections = []
terminal = ['Echo Pattern: four individual options and two source offers', 'Read-only saved-evidence review; individual sale policies retained.', '']
for c in cases:
    pictures=[]
    for x in c['source_photo_comparisons']:
        a=x['current_image'];s=x['source_cached_image']
        pictures.append('<div class="pair"><figure><img src="'+esc(Path(s['cached_path']).as_uri())+'"><figcaption>Saved source image '+str(x['source_order'])+'<br><a href="'+esc(x['source_url'])+'">Source image link</a></figcaption></figure><figure><img src="'+esc(Path(a['cached_path']).as_uri())+'"><figcaption>Corresponding current photograph<br><a href="'+esc(a['image_url'])+'">Dropbox image</a> · <a href="'+esc(a['folder_url'])+'">Containing folder</a></figcaption></figure></div>')
    sections.append('<section id="'+c['offer_ref']+'"><h2>'+esc(c['offer_ref']+' · '+c['retained_source_offer']['title'])+'</h2><p>'+esc(c['finding'])+'</p><p><a href="'+esc(c['source_url'])+'">Historical source listing</a></p>'+''.join(pictures)+'<p>'+esc(c['configuration_limit'])+'</p><p>'+esc(c['commercial_limit'])+'</p><p>'+esc(c['weight_limit'])+'</p></section>')
    terminal.extend([c['offer_ref']+': '+c['finding'], c['configuration_limit'], c['commercial_limit'], c['weight_limit'], ''])
for o in option_cards.values():
    fields=''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display'])+'<p class="note">'+esc(v['state'])+'</p></td></tr>' for k,v in o['qualified_working_fields'].items())
    sections.append('<article id="'+o['product_id']+'"><h2>'+esc(o['name'])+'</h2><p><a href="'+esc(o['image_url'])+'">Individual image</a> · <a href="'+esc(o['folder_url'])+'">Containing folder</a></p><img class="individual" src="'+esc(Path(o['selected_cached_image']['cached_path']).as_uri())+'"><table>'+fields+'</table></article>')
    terminal.extend([o['name'], 'Individual image: '+o['image_url'], 'Containing folder: '+o['folder_url']])
    terminal.extend(k+': '+v['display'] for k,v in o['qualified_working_fields'].items());terminal.append('')
page='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Echo Pattern: source photographs and individual options</title><style>body{max-width:1080px;margin:35px auto;padding:0 20px;font:17px system-ui;line-height:1.5;color:#222}section,article{margin-top:40px;padding-top:20px;border-top:1px solid #bbb}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:22px 0}figure{margin:0}img{width:100%;height:330px;object-fit:contain;background:#f4f4f4}img.individual{max-width:420px}figcaption,.note{font-size:14px}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;vertical-align:top;white-space:pre-line;border-bottom:1px solid #ddd}th{width:23%}@media(max-width:600px){.pair{grid-template-columns:1fr}}</style></head><body><h1>Echo Pattern: two source offers and four individual options</h1><p>Four saved source images have corresponding current Dropbox photographs. The White source is a group photograph. The three reviewed Verdigris source frames show Two; eighteen further source media records remain unviewed. The four existing individually purchasable options and all twenty-four qualified working fields are retained.</p><p>No source SKU, pair price or combined weight is assigned to an individual component by this review. Current links use the published Echo navigation map.</p>'+''.join(sections)+'</body></html>'
(H / 'index.html').write_text(page)
(H / 'terminal-review.txt').write_text('\n'.join(terminal)+'\n')
assert all(sha(path)==expected for path,expected in protected.items())
print(json.dumps({'status': report['status'], 'summary': report['summary']}))
