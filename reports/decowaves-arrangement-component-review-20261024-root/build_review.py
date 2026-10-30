"""Seal a scoped Decowaves photograph review without changing catalogue records."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

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
options = {x['product_id']: x for x in g['options']}
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
inventory_path = B / 'components/parallel-reviews/listing-resolution-2026-10-21/worker-01/FRESH_PUBLIC_INVENTORY.json'
products = {x['native_product_id']: x for x in read(inventory_path)['products']}
rb_path = B / 'components/parallel-reviews/eighty-source-field-readback-20261024T012802Z/source-field-readback.json'
field_readback = read(rb_path)
readbacks = {x['offer_ref']: x for x in field_readback['entries']}
observed = {x['offer_ref']: x for x in g['current_authenticated_squarespace_inventory_observation']['retained_offer_observations']}
native = read(H / 'native-readback.json')
by_id = {x['id']: x for x in native['records']}
assert native['request_count'] == len(by_id) == 16
assert all('/BOLDSTONE MASTER/Products/01 Wall Sculptures/Decowaves/' in x['path_display'] for x in by_id.values())
work = read(H / 'source-image-worklist.json')
screened = {(x['ref'], x['gallery_index']): x for x in work['sources']}
assert len(screened) == 12 and work['screened_family_references'] == 157
controls = [B / x for x in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
protected = {str(x): sha(x) for x in [B / 'current-master.json', B / p['register'], B / p['workbook'],
    B / p['current_asset_reference_map']['path'], B / p['current_native_reference_map']['path'],
    Path(p['latest_image_coverage_audit']['path']), *controls]}
assert all(read(x)['current_master_catalogue'] == p for x in controls)

def current(fid):
    a = assets[fid]
    d = {k: a[k] for k in ['file_id', 'folder_id', 'name', 'path', 'image_url', 'folder_url']}
    d.update(cached_path=a['thumb'], cached_sha256=sha(a['thumb']),
             original_encoded_bytes_compared=False, live_metadata_checked_this_batch=fid in by_id)
    if fid in by_id:
        n, parent = by_id[fid], by_id[a['folder_id']]
        assert n['type'] == 'file' and parent['type'] == 'folder'
        assert n['name'] == a['name'] and n['size'] == a['bytes']
        assert n['path_display'].rsplit('/', 1)[0] == parent['path_display']
        assert a['path'] == 'ns:202238505/' + n['path_display']
        d.update(native_metadata=n, native_parent_metadata=parent)
    return d

case_definitions = {
 'O024': ('White two-panel arrangement',
  'The first three checked frames show the two existing White designs upright on timber, horizontally on timber, and horizontally in a courtyard. The courtyard scene has two current file candidates; unique original-file selection is not established.',
  'The source claims each panel is 90 × 15 × 8 cm and the pair is 90 × 30 × 8 cm excluding gaps. The £800 source price and source set-weight fields remain whole-offer evidence; they are not divided into individual values.'),
 'O025': ('White three-panel arrangement',
  'The hero shows the existing 1–2–1 design arrangement, with the repeated outer design rotated. Current hero versions012/003 and retained015 differ in colour and framing, so the exact original file remains qualified. Gallery1 repeats the same horizontal pair photograph as O024 gallery1; gallery2 is also a pair scene.',
  'Three positions use two existing designs. Pair context in the gallery does not change the three-panel sale quantity. Each90 × 15 × 8 cm and overall90 × 45 × 8 cm excluding gaps are source claims; £1200 and source weight remain set evidence.'),
 'O050': ('Decowaves 1 — Terracotta',
  'The front and both angled source frames correspond to the current individual Terracotta photographs004/005/006. The selected individual photograph004 is the first source frame.',
  '90 × 15 × 9 cm, approximately6kg, gypsum composite and a terracotta surface effect are source claims. The £48.44 historical source price does not replace the £300 current working estimate. A rear photograph reused in the separate Frozen Fish source is not proof of this cast’s fitted fixing.'),
 'O060': ('Verdigris two-panel arrangement',
  'The three checked source frames correspond to current pair photographs006/010/002. Design1 is on the left and design2 on the right. The retained source reference010 is the second gallery frame.',
  'Each90 × 15 × 8 cm, pair90 × 30 × 8 cm, approximately14kg combined and cast composite with applied verdigris are source claims. The £600 whole-offer price and combined weight are not allocated to individual panels. Sixteen further gallery records remain unviewed.'),
}
option_defs = [
 ('BSI-8CC6C8AABCB7', ['O024', 'O025'], 'White design1 is retained for both the pair and the repeated positions1/3 in the three-panel arrangement.'),
 ('BSI-837E9B0B3B36', ['O024', 'O025'], 'White design2 is retained for the pair and the central position of the three-panel arrangement.'),
 ('BSI-BFB0D3D29852', ['O050'], 'The Terracotta source front corresponds to the current selected individual photograph004.'),
 ('BSI-612EF4DBB555', ['O060'], 'Verdigris design1 is the left member of the checked pair photographs.'),
 ('BSI-FE830AE502C3', ['O060'], 'Verdigris design2 is the right member of the checked pair photographs.'),
]
components = []
current_pictures = {}
for oid, refs, finding in option_defs:
    o = options[oid]
    assert oid in g['active_option_ids'] and len(o['master_fields']) == 6
    assert all(o[k] == assets[o['file_id']][k] for k in ['folder_id', 'image_url', 'folder_url'])
    target = current(o['file_id'])
    assert target['live_metadata_checked_this_batch']
    current_pictures[target['file_id']] = target
    components.append({'product_id': oid, 'name': o['name'], 'canonical_component_id': o['canonical_component_id'],
        'source_offer_refs': refs, 'current_reference': target, 'master_fields': o['master_fields'], 'finding': finding,
        'limitation': 'Design correspondence preserves existing owner decisions. Exact specimen, size, material, fitted hardware, stock and individual commercial terms remain separately qualified.'})

bindings, cases, source_viewed = [], [], []
for ref, (title, finding, limitation) in case_definitions.items():
    edge = edges[ref]
    product = products[edge['source_offer']['sq_id']]
    assert len(product['variants']) == 1
    variant = product['variants'][0]
    tup = {'product_id': product['native_product_id'], 'variant_id': variant['native_variant_id'], 'sku_raw': variant['sku']}
    assert observed[ref]['observed_native_source_tuple'] == tup
    rb = readbacks[ref]
    assert (rb['native_product_id'], rb['native_variant_id'], rb['sku']) == (tup['product_id'], tup['variant_id'], tup['sku_raw'])
    assert rb['all_nine_compared_fields_equal'] and len(rb['fields']) == 9 and all(x['equal'] for x in rb['fields'])
    assert variant['native_image_ids'] == [] and variant['option_attributes'] == {}
    gallery = []
    for gi, media in enumerate(product['native_media_items']):
        row = {'gallery_index': gi, 'native_media_id': media['id'], 'source_url': media['assetUrl'],
               'source_media_record': media, 'visually_reviewed_this_batch': (ref, gi) in screened}
        if (ref, gi) in screened:
            src = screened[(ref, gi)]
            assert src['url'] == media['assetUrl'] and sha(src['path']) == src['sha256']
            source_viewed.append({'offer_ref': ref, 'gallery_index': gi, 'path': src['path'], 'sha256': src['sha256'],
                                  'representation': src['representation'], 'visually_reviewed': True})
            row.update(cached_path=src['path'], cached_sha256=src['sha256'])
            # Ambiguous alternate files remain candidates; numeric closeness is not byte identity.
            if (ref, gi) == ('O025', 0):
                candidates = src['candidates'][:2] + [{'file_id': edge['current_primary_reference']['file_id']}]
                status = 'SAME_ARRANGEMENT_COLOUR_AND_FRAMING_DIFFERENCES_EXACT_ORIGINAL_UNCONFIRMED'
            else:
                count = 2 if (ref, gi) in [('O024', 2), ('O025', 2)] else 1
                candidates = src['candidates'][:count]
                status = 'SAME_PHOTOGRAPH_CORRESPONDENCE_SAVED_RENDITIONS'
            targets = []
            for candidate in candidates:
                target = current(candidate['file_id'])
                current_pictures[target['file_id']] = target
                targets.append({'current_reference': target, 'whole_frame_RGB_RMSE_96px': candidate.get('RGB_RMSE_96px'),
                                'source_and_target_visually_reviewed': True})
            binding = {'offer_ref': ref, 'gallery_index': gi, 'source_cached_path': src['path'], 'source_cached_sha256': src['sha256'],
                'source_url': src['url'], 'current_candidates': targets, 'status': status,
                'unique_original_file_verified': False, 'identical_original_encoded_bytes_verified': False,
                'physical_cast_or_build_verified': False, 'new_platform_pair_or_variant_assignment': False, 'new_image_role': False}
            bindings.append(binding)
        gallery.append(row)
    selected = current(edge['current_primary_reference']['file_id'])
    assert selected['live_metadata_checked_this_batch']
    cases.append({'offer_ref': ref, 'title': title, 'native_tuple': tup, 'source_url': edge['source_offer']['source_url'],
        'source_locator': product['source_locator'], 'native_variant': variant,
        'captured_export_observation': observed[ref], 'all_nine_source_fields_readback': rb,
        'retained_source_offer': edge['source_offer'], 'retained_member_scope': edge['members'],
        'recorded_source_reference_before_review': edge['current_primary_reference'], 'actual_source_reference': selected,
        'source_description_text': product['description_text'], 'gallery': gallery, 'finding': finding, 'limitation': limitation,
        'historical_shopify_handle': edge['source_offer']['sh_handle'] or None,
        'current_shopify_inventory_absence_not_inferred': True})

assert [x['source_component_id'] for x in edges['O025']['members']] == ['BC-FDW-1', 'BC-FDW-2', 'BC-FDW-1']
assert screened['O024', 1]['sha256'] == screened['O025', 1]['sha256']
assert len(current_pictures) == 19 and len(bindings) == 12
assert sum(len(x['gallery']) for x in cases) == 34
source_inputs = {str(x): sha(x) for x in [inventory_path, rb_path, H / 'native-readback.json', H / 'source-image-worklist.json']}
for x in field_readback['sources']:
    assert sha(x['path']) == x['sha256']
    source_inputs[x['path']] = x['sha256']
counts = {'existing_individual_options': 5, 'full_qualified_working_fields': 30, 'retained_source_offers': 4,
    'gallery_media_records': 34, 'source_media_frames_visually_reviewed': 12,
    'distinct_reviewed_source_encoded_hashes': len({x['sha256'] for x in source_viewed}),
    'distinct_Dropbox_renditions_visually_reviewed': len(current_pictures),
    'photograph_correspondence_frames': 11, 'arrangement_only_colour_framing_qualified_frames': 1,
    'current_file_candidates_for_reviewed_frames': sum(len(x['current_candidates']) for x in bindings),
    'unviewed_media_records': 22, 'cached_family_references_numerically_screened': 157,
    'live_metadata_file_readbacks': 8, 'live_metadata_folder_readbacks': 8,
    'new_platform_pairs': 0, 'new_product_records': 0, 'new_physical_verifications': 0,
    'native_or_platform_writes': 0, 'canonical_writes': 0, 'new_owner_questions': 0}
observations = [
 'Five existing individual options retain all30 complete qualified fields and their current selected file and parent IDs.',
 'The White three-panel offer retains three positions using two existing designs, 1–2–1. The repeated design is rotated; no third design or new physical inventory is inferred.',
 'The three-panel hero has colour/framing differences from current versions012/003 and retained015. Arrangement correspondence is supported; unique original-file equivalence remains unconfirmed.',
 'O024 gallery1 and O025 gallery1 have identical retained source bytes at different source URLs. A pair photograph in the three-panel gallery is context, not a sale-quantity correction.',
 'The O024 courtyard frame and O025 upright pair frame each have two plausible current file versions. Both IDs are retained without selecting a unique original.',
 'The O050 Terracotta first three source frames correspond to004/005/006. The source£48.44 and current£300 estimate are separate; source90 ×15 ×9cm and6kg are not transferred across finishes.',
 'The Verdigris source gallery shows design1 left and design2 right. Approximately14kg and£600 are whole-pair claims; individual working weights and£325/£375 estimates remain unchanged.',
 'Twelve of34 gallery records were visually reviewed;22 remain unviewed. Nineteen current cached renditions were inspected. Saved photograph renditions do not certify original encoded-byte identity or physical specifications.',
 'Eight key files and eight actual containing folders were read back by stable ID, under BOLDSTONE MASTER only. No native file move, folder rename or canonical data change is needed in this review.',
 'Four captured Squarespace product/variant/SKU tuples and their36 source fields are retained. Historical Shopify handles on O024/O025 are preserved; no new current platform pair is certified.',
]
review = {'status': 'DECOWAVES_SOURCE_COMPONENT_REVIEW_COMPLETE_NO_CANONICAL_CHANGES',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'baseline_protected_files': protected,
    'asset_map_binding': p['current_asset_reference_map'], 'components': components, 'source_records': cases,
    'photo_bindings': bindings, 'source_frames_viewed': source_viewed, 'current_images_viewed': list(current_pictures.values()),
    'counts': counts, 'observations': observations, 'source_inputs': source_inputs,
    'analysis_method': 'Whole-frame EXIF-normalized96px RGB cache screening in memory, followed by visual review. No listing images created, edited or cropped.',
    'standing_holds_retained': True}
write(H / 'review.json', review)

cards = []
for c in components:
    a = c['current_reference']
    rows = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v['display']) + '<p class="qualification">' + esc(v['state']) + '</p></td></tr>' for k, v in c['master_fields'].items())
    cards.append('<article id="' + esc(c['product_id']) + '"><h2>' + esc(c['name']) + '</h2><p>' + esc(c['finding']) + '</p><p><a href="' + esc(a['image_url']) + '">Individual image</a> · <a href="' + esc(a['folder_url']) + '">Containing folder</a></p><img class="primary" src="' + esc(a['cached_path']) + '"><table>' + rows + '</table><p><small>' + esc(a['file_id']) + ' / ' + esc(a['folder_id']) + '</small></p></article>')
source_cards = []
for c in cases:
    a = c['actual_source_reference']
    comparisons = []
    for x in bindings:
        if x['offer_ref'] != c['offer_ref']:
            continue
        targets = ''.join('<figure><img loading="lazy" src="' + esc(t['current_reference']['cached_path']) + '"><figcaption><a href="' + esc(t['current_reference']['image_url']) + '">' + esc(t['current_reference']['name']) + '</a> · <a href="' + esc(t['current_reference']['folder_url']) + '">Folder</a></figcaption></figure>' for t in x['current_candidates'])
        comparisons.append('<section><h3>Gallery ' + str(x['gallery_index']) + '</h3><p>' + esc(x['status']) + '</p><div class="images"><figure><img loading="lazy" src="' + esc(x['source_cached_path']) + '"><figcaption>Retained source rendition</figcaption></figure>' + targets + '</div></section>')
    v = c['native_variant']
    source_cards.append('<article id="' + esc(c['offer_ref']) + '"><h2>' + esc(c['offer_ref'] + ' ' + c['title']) + '</h2><p>' + esc(c['finding']) + '</p><p>' + esc(c['limitation']) + '</p><p><a href="' + esc(a['image_url']) + '">Retained source-reference image</a> · <a href="' + esc(a['folder_url']) + '">Actual containing folder</a></p><p>SKU ' + esc(v['sku']) + ' · captured product ' + esc(c['native_tuple']['product_id']) + ' · variant ' + esc(c['native_tuple']['variant_id']) + '</p>' + ''.join(comparisons) + '</article>')
(H / 'index.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Decowaves component and arrangement review</title><style>body{font:17px Arial;line-height:1.5;max-width:1150px;margin:40px auto;padding:0 20px;color:#222}article,section{border-top:1px solid #bbb;padding:24px 0}table{border-collapse:collapse;width:100%}td,th{padding:10px;vertical-align:top;text-align:left;border-bottom:1px solid #ddd}.qualification,figcaption{font-size:13px;color:#555}.images{display:flex;flex-wrap:wrap;gap:15px}figure{width:270px;margin:0;overflow-wrap:anywhere}figure img{width:100%;max-height:450px;object-fit:contain}.primary{max-height:450px;max-width:450px}small{overflow-wrap:anywhere}</style></head><body><h1>Decowaves individual components and arrangements</h1><p>Five existing options;30 full qualified fields;four retained source offers. Twelve of34 source gallery records checked. No new products, platform pairs or physically verified specifications.</p><ul>' + ''.join('<li>' + esc(x) + '</li>' for x in observations) + '</ul><h2>Individual components</h2>' + ''.join(cards) + '<h2>Source photographs and arrangement scope</h2><p>Gallery indices are zero-based. Multiple current file candidates are deliberately retained.</p>' + ''.join(source_cards) + '</body></html>')
for path, expected in protected.items():
    assert sha(path) == expected, path
checks = {'five_existing_option_ids_preserved': len(components) == 5,
 'all30_complete_field_objects_preserved': all(c['master_fields'] == options[c['product_id']]['master_fields'] for c in components),
 'four_source_product_variant_SKU_tuples_preserved': len(cases) == 4,
 'all36_captured_source_fields_equal': all(c['all_nine_source_fields_readback']['all_nine_compared_fields_equal'] for c in cases),
 'all16_metadata_ids_and_actual_parents_checked': len(by_id) == 16,
 'twelve_source_frames_rehashed_and_visually_reviewed': len(source_viewed) == 12,
 'nineteen_current_renditions_rehashed_and_visually_reviewed': len(current_pictures) == 19,
 'all22_unviewed_source_media_labelled': sum(not x['visually_reviewed_this_batch'] for c in cases for x in c['gallery']) == 22,
 'three_positions_two_designs_BOM_preserved': [x['source_component_id'] for x in edges['O025']['members']] == ['BC-FDW-1', 'BC-FDW-2', 'BC-FDW-1'],
 'all_protected_catalogue_files_unchanged': all(sha(path) == expected for path, expected in protected.items())}
assert all(checks.values())
verification = {'status': 'PASS', 'checks_passed': sum(checks.values()), 'checks_total': len(checks), 'checks': checks,
    'counts': counts, 'review_sha256': sha(H / 'review.json'), 'page_sha256': sha(H / 'index.html')}
write(H / 'verification.json', verification)
lines = []
for i, c in enumerate(components, 1):
    a = c['current_reference']
    lines.extend([f"ITEM {i}: {c['name']}", 'Image: ' + a['image_url'], 'Containing folder: ' + a['folder_url'], 'Finding: ' + c['finding']])
    lines.extend(k + ': ' + v['display'] for k, v in c['master_fields'].items())
    lines.append('')
(H / 'terminal-review.txt').write_text('\n'.join(lines))
files = [Path(__file__), H / 'review.json', H / 'verification.json', H / 'index.html',
         H / 'native-readback.json', H / 'source-image-worklist.json', H / 'terminal-review.txt']
write(H / 'sealed-handoff.json', {'status': 'SEALED_LOCAL_DECOWAVES_SOURCE_COMPONENT_REVIEW',
    'recorded_utc': review['recorded_utc'], 'files': {str(x): sha(x) for x in files}})
print(json.dumps({**verification, 'seal_sha256': sha(H / 'sealed-handoff.json')}))
