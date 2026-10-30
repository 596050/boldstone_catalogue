"""Clarify existing source scopes without making any new variant assignment."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, html, json, sqlite3

OUT = Path(__file__).resolve().parent
H = OUT.parent
B = H.parents[2]
ROOT = H.parents[3]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
pointer = read(B / 'current-master.json')
regpath = B / pointer['register']
assert sha(regpath) == 'db3527f68d36f366f4cffe1630b8cfdd3e2b2fb9feca7c5fc507ea4553ad910f'
reg = read(regpath)
crosspath = ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/local-platform-crosswalk.json'
assert sha(crosspath) == 'ef7158d87d6402d1e57b8f209da3ca6421104887da9c8a1e3ea9413b72bce578'
cross = read(crosspath)
run = H / 'published-projections/20261024T233018571196Z'
assert sha(run / 'sealed-handoff.json') == '1b138c884ab5ad1b77c1c221d0b6202dd6e573170fcbf5476c22d778ab807b93'
db = sqlite3.connect('file:' + str(run / 'complete-image-platform-register.sqlite') + '?mode=ro', uri=True)
images = {fid: json.loads(blob) for fid, blob in db.execute('SELECT file_id,record_json FROM images')}
current_component_edges = list(db.execute('SELECT offer_ref,product_id,relationship FROM source_product_links'))
assert len(current_component_edges) == 260
gap_ids = {x['product_id'] for x in cross['active_options_without_existing_source_edges']}
assert len(gap_ids) == 65 and not (gap_ids & {x[1] for x in current_component_edges})
options = {x['product_id']: x for x in reg['options'] if x['product_id'] in gap_ids}
offers = {x['offer_ref']: x for x in cross['squarespace_source_records']}
component_offer_index = defaultdict(list)
for row in reg['source_offer_edges']:
    for member in row['members']:
        for cid in member['canonical_component_targets']:
            component_offer_index[cid].append(row['offer_ref'])
gallery = {x['gallery_entry_id']: x for x in read(run / 'source-gallery-review.json')}
photo_by_id = defaultdict(list)
for row in read(run / 'source-photo-correspondences.json'):
    photo_by_id[row['file_id']].append(row)
related_links, photo_links, entries = [], [], []
for pid, option in options.items():
    assert not component_offer_index.get(option.get('canonical_component_id'))
    related = option.get('related_platform_offer_refs', [])
    for ref in related:
        assert pid in reg['master_platform_association_overlays'][ref]['related_option_ids']
        assert ref == 'O001'
        related_links.append({'product_id': pid, 'name': option['name'], 'offer_ref': ref, 'source_title': offers[ref]['source_title'], 'relationship': 'EXISTING_PARENT_FAMILY_ASSOCIATION_ONLY', 'source_gallery': str(run / 'source-galleries' / (ref + '.html')), 'evidence_json_pointers': ['/options/' + str(reg['options'].index(option)) + '/related_platform_offer_refs', '/master_platform_association_overlays/' + ref], 'exact_variant_assignment': False})
    selected_photos = []
    for key in ['file_id', 'context_file_id']:
        fid = option.get(key)
        grouped = defaultdict(list)
        for match in photo_by_id.get(fid, []): grouped[match['gallery_entry_id']].append(match)
        for gid, matches in grouped.items():
            source = gallery[gid]
            row = {'product_id': pid, 'name': option['name'], 'selected_reference_field': key, 'file_id': fid, 'offer_ref': source['offer_ref'], 'gallery_order': source['gallery_order'], 'visual_role': source['visual_role'], 'image_url': images[fid]['image_url'], 'folder_url': images[fid]['folder_url'], 'source_gallery': str(run / 'source-galleries' / (source['offer_ref'] + '.html')) + '#sq-' + str(source['gallery_order']), 'relationship': 'SELECTED_REFERENCE_PHOTOGRAPH_APPEARS_IN_SOURCE_GALLERY_ONLY', 'original_qualified_photo_evidence': matches, 'exact_variant_assignment': False, 'new_component_identity': False}
            selected_photos.append(row); photo_links.append(row)
    if related:
        disposition = 'EXISTING_PARENT_FAMILY_LINK_EXACT_VARIANT_UNRESOLVED'
        explanation = 'The Wall Circle parent listing is already linked in the canonical register. The component-only join omitted this family link. Appearance-to-pattern and exact variant qualifications remain unchanged.'
    elif pid == 'BSI-04D6E8690F30':
        disposition = 'OWNER_IDENTITY_QUESTION_PENDING'
        explanation = 'Legacy Frozen Fish FFL1 versus FFS2 remains the exact-pair question already held by the Recovery session. No answer or source alias has been inferred.'
    elif option.get('family') == 'Fingerprint':
        disposition = 'NEW_NUMBERED_OPTION_NO_SUPPORTED_LOCAL_NATIVE_RECORD'
        explanation = 'The six owner-selected Concentric 1–3 Cream/White options have no supported exact product/variant record in the checked local evidence. Superseded Left/Right records remain history, not exact aliases.'
    else:
        disposition = 'NO_SUPPORTED_EXACT_COMPONENT_RECORD_IN_LOCAL_EVIDENCE'
        explanation = 'No current canonical component-to-source edge or parent-family overlay is recorded for this option in the checked local export evidence. This is a bounded evidence gap, not a claim about records outside the supplied exports.'
    im = images.get(option.get('file_id'), {})
    resolution = option.get('current_listing_resolution', {})
    conditional = resolution.get('conditional_native_tuple')
    entries.append({'product_id': pid, 'name': option['name'], 'family': option.get('family'), 'canonical_component_id': option.get('canonical_component_id'), 'disposition': disposition, 'explanation': explanation, 'product_reader': str(run / 'products' / (pid + '.html')), 'current_selected_image_url': im.get('image_url'), 'current_selected_folder_url': im.get('folder_url'), 'existing_parent_offer_refs': related, 'selected_reference_source_photo_links': selected_photos, 'retained_prior_resolution': resolution.get('current_source_resolution_disposition'), 'retained_conditional_native_tuple': conditional, 'conditional_tuple_not_promoted_to_approved_match': bool(conditional), 'new_exact_variant_assignment': False})
assert len(related_links) == 7 and {x['offer_ref'] for x in related_links} == {'O001'}
assert len(photo_links) == 2 and {x['product_id'] for x in photo_links} == {'BSI-1A7497B69626', 'BSI-65520F070145'}
counts = dict(Counter(x['disposition'] for x in entries))
assert sorted(counts.values()) == [1, 6, 7, 51]
soundwave = next(x for x in cross['local_shopify_records'] if x['product']['title'] == 'Soundwave Greetings Card')
assert soundwave['product']['type_raw'] == 'Greeting & Note Cards'
assert soundwave['variants'][0]['sku_raw'] == 'GC-SW-Sq-15.15'
assert 'Card size' in soundwave['product']['body_html']
scope_note = {'local_Shopify_product_records_retained': 136, 'local_Shopify_variant_rows_retained': 160, 'local_Shopify_image_rows_retained': 416, 'Squarespace_source_products_reviewed': 80, 'source_scope': 'Owner-requested local records. No account access, live inventory or new platform publication is required or claimed.', 'same_named_different_product_type_example': {'handle': soundwave['handle'], 'title': soundwave['product']['title'], 'type': soundwave['product']['type_raw'], 'source_row': soundwave['product']['source_header_row'], 'sku': soundwave['variants'][0]['sku_raw'], 'disposition': 'Printed greeting card, not an exact Soundwave sculpture sale variant. Its photographs were not newly classified in this component-association audit.'}}
summary = {'status': 'COMPLETED_BOUNDED_65_CASE_SOURCE_ASSOCIATION_CLARIFICATION', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'component_edge_gaps': 65, 'existing_parent_family_associations_within_65': 7, 'remaining_without_existing_component_or_parent_family_association': 58, 'disposition_counts': counts, 'selected_reference_photo_reuse_pairs': 2, 'distinct_options_with_parent_or_selected_photo_source_links': 8, 'new_exact_variant_assignments': 0, 'existing_260_component_source_edges_unchanged': True, 'canonical_and_sealed_reader_and_platform_writes': 0, 'source_scope': scope_note, 'identity_owner_thread': '01a16dbc-036d-7003-8ebd-34cb76b5b667', 'no_identity_questions_reissued': True, 'suggested_current_wording': '65 options lack a current component-to-source association. Seven already have a parent Wall Circle family link; 58 have no supported component or parent-family association in the checked local evidence. Photograph reuse is recorded separately from an exact variant assignment.'}
write(OUT / 'summary.json', summary)
write(OUT / 'all-65-case-dispositions.json', entries)
write(OUT / 'existing-parent-family-links.json', related_links)
write(OUT / 'selected-reference-source-photo-links.json', photo_links)
sources = [regpath, crosspath, run / 'sealed-handoff.json', run / 'source-gallery-review.json', run / 'source-photo-correspondences.json', ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/sealed-handoff.json']
write(OUT / 'input-manifest.json', {str(p): sha(p) for p in sources})
e = lambda v: html.escape(str(v or ''), quote=True)
link = lambda u, label: '<a href="' + e(u) + '">' + e(label) + '</a>' if u else e(label)
page = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Clarifying 65 source associations</title><style>body{font:16px system-ui;max-width:1200px;margin:35px auto;padding:0 20px;line-height:1.5}a{color:#1c6354}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:12px}small{color:#46574f}.note{background:#f4f0e4;padding:14px}h2{margin-top:35px}</style><h1>Clarifying 65 source associations</h1><p class="note">65 options lack a current component-to-source association. Seven already have a parent Wall Circle family link; 58 have no supported component or parent-family association in the checked local evidence. These are not 65 missing photographs. Exact variant identities remain qualified.</p><p>' + link(run / 'index.html', 'Current catalogue image index') + ' · ' + link(ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/index.html', 'Local platform records') + '</p><h2>Recovered navigation to existing source evidence</h2><ul>'
for row in related_links: page += '<li>' + link(run / 'products' / (row['product_id'] + '.html'), row['name']) + ' → ' + link(row['source_gallery'], 'Wall Circle parent gallery') + ' — existing family association; exact variant remains unresolved.</li>'
for row in photo_links: page += '<li>' + link(run / 'products' / (row['product_id'] + '.html'), row['name']) + ' → ' + link(row['source_gallery'], row['offer_ref'] + ' source image ' + str(row['gallery_order'])) + ' · ' + link(row['image_url'], 'Dropbox image') + ' · ' + link(row['folder_url'], 'Containing folder') + ' — reused ' + e(row['visual_role']) + ' photograph; no new exact selling-variant assignment.</li>'
page += '</ul><h2>All 65 dispositions</h2><p>Six Fingerprint options are new numbered records, one Frozen Fish identity remains with its existing review owner, and 51 other options have no supported exact component record in the checked local evidence. The seven Wall Circle family links are shown above; four retain conditional native tuples and three retain their existing pattern/custom scope questions.</p><table><thead><tr><th>Catalogue option</th><th>Current reference</th><th>Local evidence disposition</th></tr></thead><tbody>'
for row in sorted(entries, key=lambda x: x['name'].casefold()):
    page += '<tr id="' + e(row['product_id']) + '"><td>' + link(row['product_reader'], row['name']) + '</td><td>' + link(row['current_selected_image_url'], 'Image' if row['current_selected_image_url'] else 'No verified selected image link') + '<br>' + link(row['current_selected_folder_url'], 'Containing folder' if row['current_selected_folder_url'] else '') + '</td><td>' + e(row['explanation'])
    if row['selected_reference_source_photo_links']: page += '<p>Selected photograph appears in a source gallery; the source-picture link above does not establish the sculpture selling variant.</p>'
    if row['retained_conditional_native_tuple']: page += '<p><small>Retained conditional pattern: ' + e(row['retained_conditional_native_tuple'].get('pattern_short_name')) + '. Still conditional.</small></p>'
    page += '</td></tr>'
page += '</tbody></table><p>Soundwave also appears in the local Shopify export as a printed greeting card. That is a separate product type, not an exact sculpture listing. No artwork, identity, specification, price or stock field has changed.</p><p>' + link('all-65-case-dispositions.json', 'Detailed evidence records') + ' · ' + link('summary.json', 'Audit scope and counts') + '</p>'
(OUT / 'index.html').write_text(page)
assert sha(regpath) == pointer['register_sha256']
assert sha(run / 'sealed-handoff.json') == '1b138c884ab5ad1b77c1c221d0b6202dd6e573170fcbf5476c22d778ab807b93'
print(json.dumps(summary, indent=2))
