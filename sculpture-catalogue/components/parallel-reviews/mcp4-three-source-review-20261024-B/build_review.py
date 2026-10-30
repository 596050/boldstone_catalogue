"""Save three source-image crosswalks while retaining source/version qualifications."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
esc = lambda x: html.escape(str(x), quote=True)
pointer_path = B / 'current-master.json'
pointer_bytes = pointer_path.read_bytes()
p = json.loads(pointer_bytes)
register_path = B / p['register']
assets_path = B / p['current_asset_reference_map']['path']
assert sha(register_path) == p['register_sha256']
assert sha(assets_path) == p['current_asset_reference_map']['sha256']
g, assets = read(register_path), read(assets_path)
options = {x['product_id']: x for x in g['options']}
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
observations = {x['offer_ref']: x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
index_path = B / 'components/evidence/offer_review_index.json'
index = {x['ref']: x for x in read(index_path)}
claims_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-02/SOURCE_NATIVE_CLAIMS.json'
claims = read(claims_path)['offers']
readback_path = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
readback = read(readback_path)
readbacks = {x['offer_ref']: x for x in readback['entries']}
photos = read(H / 'photo-comparisons.json')
assert photos['current_asset_map']['sha256'] == sha(assets_path)
protected_files = {str(path): sha(path) for path in [register_path, B / p['workbook'], register_path.parent / 'image-coverage-current.json', assets_path, B / p['current_native_reference_map']['path']]}
source_inputs = {str(path): sha(path) for path in [index_path, claims_path, readback_path, H / 'photo-comparisons.json']}
for source in readback['sources']:
    assert sha(source['path']) == source['sha256']
    source_inputs[source['path']] = source['sha256']

def cached_native(fid):
    a = assets[fid]
    path = Path(a['thumb'])
    with Image.open(path) as im: dimensions = list(im.size)
    row = {k: a[k] for k in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']}
    row.update(cached_path=str(path), cached_sha256=sha(path), cached_dimensions=dimensions,
               cached_representation='original' if a.get('current_original_content_rehashed') and a.get('original') == a['thumb'] else 'thumbnail',
               visually_reviewed_this_turn=True)
    if row['cached_representation'] == 'original': assert row['cached_sha256'] == a['sha256']
    return row

definitions = [
    {'ref': 'O011', 'option': 'BSI-8298E205204F',
     'finding': 'All three retained source images correspond to tighter crops of existing Verdigris photographs 006, 004 and 005. This strengthens the photo-level association with the existing 25 cm MCP4 Verdigris option.',
     'features': ['The turquoise surface texture, thin brown rim and square backing agree in all three views.',
                  'Panel edges, adjoining stone joints and background marks align after fitting only an axis-aligned crop.',
                  'The third source view corresponds to selected current photograph 005; the first two correspond to existing 006 and 004.'],
     'source_scope': 'Three retained source image thumbnails; all three media items from the saved 21 October collection are represented.',
     'remaining': 'Original source-download bytes were unavailable at the recorded temporary paths. Exact current size/build and physical measurements remain unverified; the existing provisional specimen qualification is retained.',
     'source_price_note': 'The retained export records 40.00 with currency unencoded; the 16 October public capture records £40 GBP. The accepted working estimate is £120; the historical source amount does not overwrite it.'},
    {'ref': 'O003', 'option': 'BSI-1AF0A83FAA37',
     'finding': 'The first three retained listing images are the same photographs as existing Silver and Bronze references 001, 002 and 003. O064 reuses these three views. Keep the existing single Silver and Bronze catalogue option and both separate source records.',
     'features': ['Panel edges, stone joints and the silver/dark patch pattern match reference 001 in the front view.',
                  'The landscape front and angled views match references 002 and 003.',
                  'The current selected image 004 shows another view of the same depicted finish pattern; this review does not replace it.'],
     'source_scope': 'Three retained source image thumbnails out of seven media items in the saved 21 October collection. Four further source media items are metadata only in this review.',
     'remaining': 'Original source-download bytes were unavailable at the recorded temporary paths. Same photographs and a matching 25 × 25 × 6 cm source claim do not verify a physical cast or authorize choosing between native listing records.',
     'source_price_note': 'Captured native amount 350.00, visibility Yes and stock setting Unlimited. These are retained source settings; the catalogue £350 remains a working estimate.'},
    {'ref': 'O064', 'option': 'BSI-1AF0A83FAA37',
     'finding': 'The three retained O064 image renditions reuse the same photographs as O003 and existing Silver and Bronze references 001, 002 and 003. This supports the existing alias relationship without adding a second catalogue product.',
     'features': ['All three saved source views match O003 despite JPEG/WebP rendition differences.',
                  'The 24 October export retains a distinct product ID, variant ID and EBAY-prefixed SKU.',
                  'The older public page capture was unavailable and the 21 October public collection did not return this product. Its captured visibility No comes from the export; no current deletion or account-wide absence is inferred.'],
     'source_scope': 'Three retained source-index thumbnails. The complete public gallery is not established: the page was unavailable in the older capture and the saved public collection did not return this product.',
     'remaining': 'Original source-download bytes were unavailable at the recorded temporary paths. Preserve the two distinct source offers, their prices and visibility. Native record selection and exact current sale configuration remain unresolved.',
     'source_price_note': 'Captured native amount 80.33, visibility No and stock setting 1 differ from O003. No live availability or physical stock count is inferred; neither amount overrides the accepted £350 working estimate.'},
]

cases = []
viewed_native = {}
for definition in definitions:
    ref, oid = definition['ref'], definition['option']
    option, edge, ob, rb = options[oid], edges[ref], observations[ref], readbacks[ref]
    assert option['canonical_design_id'] == 'BC-MCP-4'
    expected_tuple = {'product_id': rb['native_product_id'], 'variant_id': rb['native_variant_id'], 'sku_raw': rb['sku']}
    assert ob['observed_native_source_tuple'] == expected_tuple
    assert ob['observed_first_source_image_url'] == index[ref]['images'][0]['url'] == rb['source_first_image_url']
    assert rb['all_nine_compared_fields_equal']
    assert all(field['equal'] for field in rb['fields'])
    source = claims[ref]['Squarespace']
    if 'variants' in source:
        assert len(source['variants']) == 1
        variant = source['variants'][0]
        assert variant['native_product_id'] == rb['native_product_id'] and variant['native_variant_id'] == rb['native_variant_id'] and variant['sku'] == rb['sku']
        rawpath = Path(variant['source_locator']['path'])
        assert sha(rawpath) == variant['source_locator']['body_sha256']
        raw_variant = read(rawpath)
        for part in variant['source_locator']['json_pointer'].strip('/').split('/'):
            raw_variant = raw_variant[int(part)] if isinstance(raw_variant, list) else raw_variant[part]
        assert raw_variant == variant['native_record']
        source_inputs[str(rawpath)] = sha(rawpath)
        assert not variant['native_image_ids'] and not variant['option_attributes']
    else:
        assert ref == 'O064' and source['state'] == 'NOT_RETURNED_IN_THIS_CHECKED_PUBLIC_COLLECTION'
    case_photos = [x for x in photos['comparisons'] if x['offer_ref'] == ref]
    assert len(case_photos) == 3
    for row in case_photos:
        assert sha(row['source_cached_path']) == row['source_cached_sha256']
        assert sha(row['native_cached_path']) == row['native_cached_sha256']
        current = assets[row['file_id']]
        assert all(row[k] == current[k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url'])
        assert '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moon Crater Phase/' in row['native_path']
        if ref != 'O064':
            assert row['source_url'] in {m['assetUrl'] for m in source['native_media_items']}
        row['same_photograph_supported'] = True
        row['binding_level'] = 'Retained rendition photo correspondence; original file-byte identity and physical cast not certified'
        viewed_native[row['file_id']] = cached_native(row['file_id'])
    selected = cached_native(option['file_id'])
    viewed_native[option['file_id']] = selected
    historical = cached_native(edge['source_offer']['image_file_id'])
    viewed_native[historical['file_id']] = historical
    case = dict(definition)
    case.update(
        offer_ref=ref, option_id=oid, name=option['name'], native_tuple=expected_tuple,
        current_selected_reference={k: option[k] for k in ['product_id', 'canonical_design_id', 'name', 'file_id', 'folder_id', 'image_url', 'folder_url']},
        source_url=edge['source_offer']['source_url'],
        retained_source_offer=edge['source_offer'], retained_BOM_members=edge['members'],
        latest_captured_export_observation=ob, retained_source_field_readback=rb,
        historical_public_collection_evidence=source,
        retained_source_index_metadata={k: v for k, v in index[ref].items() if k != 'images'},
        source_photo_correspondences=case_photos,
        current_selected_cached_image=selected,
        historical_source_reference_current_navigation=historical,
        qualified_working_fields=option['master_fields'],
        text_size_claim='25 × 25 × 6 cm — description claim; not independently measured',
        raw_source_units='Raw exported numeric fields retain unencoded units; no conversion to physical dimensions or weight asserted.',
        appearance_association_supported=True,
        source_original_byte_identity_verified=False,
        exact_current_sale_configuration_verified=False,
        physical_specifications_verified=False,
        new_platform_pair=False, new_source_SKU_assignment=False, new_product=False,
    )
    cases.append(case)

assert len(viewed_native) == 8
report = {
    'status': 'THREE_SOURCE_PHOTO_CROSSWALKS_COMPLETED_NO_CANONICAL_CHANGE',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'pointer_at_start': {'path': str(pointer_path), 'sha256': hashlib.sha256(pointer_bytes).hexdigest(), 'status': p['status']},
    'current_asset_map': {'path': str(assets_path), 'sha256': sha(assets_path), 'lookup': 'current-master.current_asset_reference_map.path'},
    'protected_files': protected_files, 'source_inputs': source_inputs,
    'cases': cases, 'viewed_native_images': list(viewed_native.values()),
    'source_to_source_photo_comparisons': photos['O003_O064_source_pairs'],
    'summary': {'source_offers': 3, 'existing_working_options': 2, 'source_renditions_viewed': 9,
                'current_cached_images_viewed': 8, 'photo_correspondences_supported': 9,
                'unique_matched_current_photo_ids': 6, 'source_original_byte_verifications': 0,
                'new_product_records': 0, 'new_platform_pairs': 0, 'new_physical_verifications': 0},
    'comparison_limits': photos['limitations'],
    'source_clock_scope': 'Saved 16 October source-image index/renditions, 21 October public collection and retained 24 October export readback. No new public-page, Dropbox or account observation.',
    'source_configuration_limits': [
        'O003 and O064 have separate source tuples and different captured price/visibility settings. Same imagery is not authority to merge or delete native listings.',
        'O003 and O011 captured default variants have no option attributes or per-variant image IDs. O064 variant tuple is supported by the retained 24 October export; its public-collection variant payload was not available.',
        'All three source descriptions state 25 × 25 × 6 cm. No 50 cm source claims are transferred and no actual measurements are certified.',
        'Existing rear-hardware notes retain their earlier front/back pairing and load qualifications. This review adds no rear-photo proof.',
        'No new owner question or change to existing context, series, Wall Circle or Frozen Fish holds.'
    ],
    'native_calls': 0, 'native_writes': 0, 'platform_writes': 0, 'canonical_writes': 0,
}
write(H / 'review.json', report)
write(H / 'photo-binding-proposal.json', {
    'status': 'EVIDENCE_ONLY_READY_FOR_MAIN_REVIEW', 'apply_automatically': False,
    'purpose': 'Link source-photo correspondence evidence without rewriting historical source records or promoting physical/configuration claims.',
    'baseline_register_sha256': p['register_sha256'], 'asset_map_sha256': sha(assets_path),
    'cases': [{'offer_ref': c['offer_ref'], 'option_id': c['option_id'],
               'source_tuple': c['native_tuple'], 'source_first_photo_corresponding_file_id': c['source_photo_correspondences'][0]['file_id'],
               'source_frames': [{k: x[k] for k in ['source_order', 'source_url', 'file_id', 'folder_id', 'image_url', 'folder_url', 'binding_level']} for x in c['source_photo_correspondences']],
               'original_source_reference_retained': c['retained_source_offer'],
               'exact_current_sale_configuration_verified': False} for c in cases],
    'new_products': 0, 'specification_changes': 0, 'historical_source_rewrites': 0,
    'native_actions': [], 'platform_actions': []})

cards = []
terminal = ['MCP4: O011 Verdigris and O003/O064 Silver and Bronze source-photo review', 'Photo correspondences only; existing catalogue entries and qualifications unchanged.', '']
for c in cases:
    figures = []
    for x in c['source_photo_correspondences']:
        figures.append('<div class="pair"><figure><img src="' + esc(Path(x['source_cached_path']).as_uri()) + '"><figcaption>Source image ' + str(x['source_order']) + ' — retained thumbnail<br><a href="' + esc(x['source_url']) + '">Source image link</a></figcaption></figure><figure><img src="' + esc(Path(x['native_cached_path']).as_uri()) + '"><figcaption>Corresponding current photograph<br><a href="' + esc(x['image_url']) + '">Dropbox image</a> · <a href="' + esc(x['folder_url']) + '">Containing folder</a></figcaption></figure></div>')
    o = c['current_selected_reference']
    specs = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<p class="note">' + esc(v['state']) + '</p></td></tr>' for k, v in c['qualified_working_fields'].items())
    cards.append('<article id="' + c['offer_ref'] + '"><h2>' + esc(c['offer_ref'] + ' · ' + c['name']) + '</h2><p>' + esc(c['finding']) + '</p><p><a href="' + esc(o['image_url']) + '">Current selected image</a> · <a href="' + esc(o['folder_url']) + '">Containing folder</a> · <a href="' + esc(c['source_url']) + '">Historical source listing</a></p><p>' + esc(c['source_scope']) + '</p><ul>' + ''.join('<li>' + esc(f) + '</li>' for f in c['features']) + '</ul>' + ''.join(figures) + '<p>' + esc(c['source_price_note']) + '</p><p>' + esc(c['remaining']) + '</p><details><summary>Existing working specifications</summary><table>' + specs + '</table></details></article>')
    terminal.extend([c['offer_ref'] + ': ' + c['name'], c['finding'], 'Selected image: ' + o['image_url'], 'Containing folder: ' + o['folder_url'], 'Native source tuple: ' + json.dumps(c['native_tuple']), c['source_price_note']])
    for x in c['source_photo_correspondences']:
        terminal.extend(['Source image ' + str(x['source_order']) + ': ' + x['source_url'], 'Corresponding Dropbox photograph: ' + x['image_url']])
    terminal.extend(k + ': ' + v['display'] for k, v in c['qualified_working_fields'].items())
    terminal.extend([c['remaining'], ''])
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MCP4 source photographs and aliases</title><style>body{max-width:1100px;margin:36px auto;padding:0 20px;font:17px system-ui;line-height:1.5;color:#222}article{border-top:1px solid #bbb;margin-top:40px;padding-top:20px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin:24px 0}figure{margin:0}img{width:100%;height:390px;object-fit:contain;background:#f4f4f4}figcaption,.note{font-size:14px}table{width:100%;border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top;white-space:pre-line}th{width:23%}@media(max-width:600px){.pair{grid-template-columns:1fr}img{height:300px}}</style></head><body><h1>Moon Crater Phase 4: source photographs and aliases</h1><p>Nine saved source-image renditions correspond to six current Dropbox photographs across the existing Verdigris and Silver and Bronze options. The original source downloads are unavailable at their historical temporary paths; this review verifies cached rendition correspondence, not identical original bytes or physical specifications.</p><p>The two Silver and Bronze source offers retain separate product IDs, variant IDs, SKUs, prices and visibility settings. No catalogue products, specifications or platform records were changed.</p>' + ''.join(cards) + '</body></html>'
(H / 'index.html').write_text(page)
(H / 'terminal-review.txt').write_text('\n'.join(terminal) + '\n')
assert all(sha(path) == expected for path, expected in protected_files.items())
print(json.dumps({'status': report['status'], 'summary': report['summary']}))
