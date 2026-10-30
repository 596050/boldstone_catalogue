import copy
import datetime
import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import quote, urlencode

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'family-keep'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
STATEMENT = 'Keep “Wall Circle — Pale Blue Marbled” and all the other Wall Circles'
OWNER = '01a13fe6-495b-7253-b923-31823b4cbca8'


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def navigation(path, preview=None):
    display = '/' + path.partition('//')[2].lstrip('/') if path.startswith('ns:') else path
    url = 'https://www.dropbox.com/home' + quote(display, safe='/')
    if preview:
        url += '?' + urlencode({'preview': preview}, quote_via=quote)
    return url


source = read(BASE / 'source-snapshot.json')
census = read(OUT / 'dropbox-current-census.json')
native = read(OUT / 'squarespace-current.json')
live = {x['file_id']: x for x in census['entries']}
assets = {x['id']: x for x in source['assets']}
groups = {x['group_ref']: x for x in source['groups']}
live_files = {k: v for k, v in live.items() if v['object_type'] == 'file'}
live_folders = {k: v for k, v in live.items() if v['object_type'] == 'folder'}
assert census['pagination_complete']
assert set(live_files) == set(assets)
assert set(live_folders) == {x['id'] for x in groups.values()}
assert len(live_files) == 167 and len(live_folders) == 13
variants = native['item']['variants']
assert len(variants) == 144
assert len({v['attributes']['Pattern'] for v in variants}) == 18
template = read(BASE / 'wc-03-pale-blue-marbled/component-review.json')
family_receipt_path = OUT / 'family-approval.json'

# The blanket Keep accepts working catalogue records; it does not certify new facts.
family = {
    'schema': 'boldstone.family-working-entry-approval.v1',
    'decision_id': 'WALL-CIRCLE:family-keep:2026-10-17',
    'recorded_utc': NOW,
    'owner_session': OWNER,
    'component_id': 'BC-WALL-CIRCLE',
    'user_statement': STATEMENT,
    'decision': 'KEEP_ALL_CURRENT_WALL_CIRCLE_WORKING_ENTRIES',
    'scope': 'WC-03 and all remaining current Wall Circle working pattern/option records in the reserved G331-G343 lane. Prior WC-01 and WC-02 approvals are preserved.',
    'folder_id': census['family_folder']['id'],
    'folder_url': navigation(census['family_folder']['path_display']),
    'group_refs': sorted(groups),
    'file_ids': sorted(assets),
    'coverage': {'folders': 13, 'files': 167, 'native_named_patterns': 18, 'native_option_rows': 144},
    'approval_meaning': 'Working-entry acceptance. Estimates, proposed applicability, generated-media provenance and unknown manufacture/stock remain labelled.',
    'working_50cm_template': {
        'dimensions': '50 cm diameter × 2.5 cm depth — working guess outside WC-01',
        'weight': 'Approximately 12 kg — estimate outside WC-01; approximate even for WC-01',
        'material': 'Plaster/gypsum composite — working guess outside WC-01',
        'fixings': 'French cleat — working proposal outside WC-01',
        'lighting': 'RGB lighting — working proposal outside WC-01',
        'price': 'GBP 600 including RGB — working proposal outside WC-01',
        'availability': 'Made to order — working proposal outside WC-01; lead time unknown'
    },
    'native_option_policy': 'Preserve all native diameter, lighting, SKU and price values separately. The 50 cm RGB template does not overwrite smaller/larger or No Light options.',
    'media_policy': 'Retain study, generated texture and scene roles. Repeated images, reflections and option rows are not counted as distinct manufactured objects.',
    'alias_policy': 'Visual review names and native pattern names may overlap; no distinct-design total is asserted until their mapping is established.',
    'scope_exclusions': ['Future files/options added after this snapshot', 'Other sculpture families', 'Publication or storefront changes'],
    'physical_manufacture_confirmation_scope': 'Only the prior WC-01 green-and-white piece has an explicit physical-existence confirmation.',
    'shared_master_import_status': 'READY_FOR_COORDINATED_IMPORT',
    'remote_mutations_performed': False
}
if family_receipt_path.exists():
    old = read(family_receipt_path)
    assert old['decision_id'] == family['decision_id'] and old['user_statement'] == STATEMENT
    family = old
else:
    write(family_receipt_path, family)

# Complete the currently displayed WC-03 without promoting its estimates.
wc03dir = BASE / 'wc-03-pale-blue-marbled'
wc03 = read(wc03dir / 'component-review.json')
wc03before = copy.deepcopy(wc03)
wc03approval = {
    'schema': 'boldstone.isolated-working-entry-approval.v1',
    'decision_id': 'WC-03:keep:pale-blue-marbled',
    'recorded_utc': NOW, 'owner_session': OWNER, 'review_id': 'WC-03',
    'component_id': 'BC-WALL-CIRCLE', 'group_ref': 'G339',
    'file_id': wc03['primary_image']['id'], 'folder_id': wc03['containing_folder']['id'],
    'user_statement': STATEMENT, 'decision': 'KEEP_WORKING_ENTRY',
    'approved_working_name': wc03['working_name'],
    'approved_specification_snapshot': copy.deepcopy(wc03['specification_review_items']),
    'scope': 'The displayed WC-03 working entry, retaining every estimate/proposal and unresolved manufacture status.',
    'family_approval_record': str(family_receipt_path),
    'physical_specs_independently_verified': False,
    'shared_master_import_status': 'READY_FOR_COORDINATED_IMPORT'
}
if not (wc03dir / 'before-complete-entry-keep.json').exists():
    write(wc03dir / 'before-complete-entry-keep.json', wc03before)
if not (wc03dir / 'review-approval.json').exists():
    write(wc03dir / 'review-approval.json', wc03approval)
wc03['approval'].update({
    'status': 'KEPT_WORKING_ENTRY_WITH_PROPOSALS', 'user_statement': STATEMENT,
    'full_entry_keep_recorded': True, 'physical_specs_verified': False,
    'estimates_remain_estimates_after_keep': True,
    'approval_record': str(wc03dir / 'review-approval.json'),
    'family_approval_record': str(family_receipt_path)
})
for item in wc03['specification_review_items']:
    item['working_approval'] = 'KEPT_WITH_EXISTING_UNCERTAINTY_LABEL'
wc03['updated_utc'] = NOW
write(wc03dir / 'component-review.json', wc03)

# Remaining visually identified patterns get review records, not asserted new physical inventory.
remaining = [
    ('WC-04', 'G341', 'id:cnqzTNngPVsAAAAAAAs9QA', 'Wall Circle — Terracotta Marbled', 'Terracotta/rust, cream and pale fragments; a lit rim is depicted', 'AI_SOURCE_RENDITION_MATCH'),
    ('WC-05', 'G343', 'id:cnqzTNngPVsAAAAAAAr1IQ', 'Wall Circle — Yellow and Grey Marbled', 'Yellow/ochre and grey fragmented pattern', 'PATTERN_STUDY'),
    ('WC-06', 'G331', 'id:cnqzTNngPVsAAAAAAAr1JQ', 'Wall Circle — Blue and White Marbled', 'Blue, cream/white and dark fragmented disc; a lit rim is depicted', 'PATTERN_STUDY'),
    ('WC-07', 'G331', 'id:cnqzTNngPVsAAAAAAAr1KQ', 'Wall Circle — Mixed Colour Marbled', 'Yellow, cream, burgundy, green and blue/grey swirled disc', 'PATTERN_STUDY')
]
all_visual = [
    ('WC-01', 'G337', BASE / 'component-review.json', BASE / 'review-approval.json'),
    ('WC-02', 'G338', BASE / 'wc-02-turquoise-marbled/component-review.json', BASE / 'wc-02-turquoise-marbled/review-approval.json'),
    ('WC-03', 'G339', wc03dir / 'component-review.json', wc03dir / 'review-approval.json')
]
for rid, gr, fid, name, appearance, provenance in remaining:
    g = groups[gr]
    a, lf, lg = assets[fid], live[fid], live[g['id']]
    record = copy.deepcopy(template)
    record.update({
        'review_id': rid, 'group_ref': gr, 'created_utc': NOW,
        'working_name': name, 'existing_folder_label': g['name'],
        'identity_status': 'Working pattern entry retained by explicit family-wide Keep; physical manufacture and exact native option identity are unconfirmed.',
        'primary_image': {'id': fid, 'name': lf['name'], 'path_ns': lf['path'], 'image_url': navigation(lg['path'], lf['name']), 'local_original': a.get('full'), 'catalogue_content_hash': a['content_hash'], 'visual_observation': appearance},
        'containing_folder': {'id': g['id'], 'name': lg['name'], 'path_ns': lg['path'], 'folder_url': navigation(lg['path'])},
        'image_provenance_status': provenance,
        'image_provenance_note': g.get('source_decision', {}),
        'new_distinct_physical_component_asserted': False,
        'manufacture_status': 'UNCONFIRMED',
        'approval': {'status': 'KEPT_BY_FAMILY_SCOPE_WITH_PROPOSALS', 'user_statement': STATEMENT, 'full_entry_keep_recorded': True, 'physical_specs_verified': False, 'estimates_remain_estimates_after_keep': True, 'approval_record': str(family_receipt_path), 'working_name_basis': 'Descriptive working label under family-wide Keep; not a recovered manufacturer model name.'}
    })
    for item in record['specification_review_items']:
        item['proposal_id'] = rid + ':' + item['group']
        item['working_approval'] = 'KEPT_WITH_EXISTING_UNCERTAINTY_LABEL'
        item['basis'] = 'Inherited working proposal from WC-01; no physical confirmation for this pattern.'
        if item['group'] == 'material_and_finish':
            item['proposal'] = 'Plaster/gypsum composite — guess; ' + appearance + ' — visual description only'
    path = OUT / 'visual-pattern-records' / (rid + '.json')
    write(path, record)
    all_visual.append((rid, gr, path, family_receipt_path))

visual_index = []
for rid, gr, path, approval in all_visual:
    d = read(path)
    visual_index.append({'review_id': rid, 'group_ref': gr, 'working_name': d['working_name'], 'record': str(path), 'approval_record': str(approval), 'image_url': d['primary_image']['image_url'], 'folder_url': d['containing_folder']['folder_url'], 'approval_status': d['approval']['status'], 'physical_manufacture_confirmed': rid == 'WC-01'})
write(OUT / 'visual-pattern-index.json', visual_index)

media_groups = []
for gr, g in sorted(groups.items()):
    lg = live[g['id']]
    children = [a for a in assets.values() if a['folder_id'] == g['id']]
    media_groups.append({'group_ref': gr, 'folder_id': g['id'], 'name': lg['name'], 'path_ns': lg['path'], 'folder_url': navigation(lg['path']), 'file_ids': sorted(a['id'] for a in children), 'file_count': len(children), 'role': g['role'], 'working_approval': 'KEPT_BY_FAMILY_SCOPE', 'approval_record': str(family_receipt_path), 'source_provenance_preserved': g.get('source_decision', {}), 'creates_additional_physical_component_count': False})
write(OUT / 'media-group-register.json', media_groups)

native_rows = []
for v in variants:
    native_rows.append({'variant_id': v['id'], 'sku': v.get('sku'), 'attributes': v['attributes'], 'price': v.get('priceMoney'), 'on_sale': v.get('onSale'), 'sale_price': v.get('salePriceMoney'), 'stock_setting': {'unlimited': v.get('unlimited'), 'qty_in_stock': v.get('qtyInStock')}, 'raw_dimensions_and_weight': {k: v.get(k) for k in ['len', 'width', 'height', 'weight']}, 'raw_units': 'Not asserted; retain native numeric values without conversion', 'image_id': v.get('mainImageId'), 'image_url': v.get('mainImage', {}).get('assetUrl'), 'working_approval': 'KEPT_EXISTING_NATIVE_OPTION_BY_FAMILY_SCOPE', 'approval_record': str(family_receipt_path), 'physical_stock_verified': False, 'dropbox_exact_image_binding': 'NO_EXACT_BYTE_MATCH_IN_CURRENT_CHECK', 'relationship_to_visual_review_names': 'UNRESOLVED_NO_NEW_DISTINCT_DESIGN_COUNT'})
write(OUT / 'native-option-register.json', native_rows)

index = {
    'schema': 'boldstone.family-import-package.v1', 'created_utc': NOW,
    'owner_session': OWNER, 'component_id': 'BC-WALL-CIRCLE',
    'family_approval_record': str(family_receipt_path),
    'visual_pattern_index': str(OUT / 'visual-pattern-index.json'),
    'media_group_register': str(OUT / 'media-group-register.json'),
    'native_option_register': str(OUT / 'native-option-register.json'),
    'coverage': family['coverage'], 'visual_review_records': 7,
    'approval_status': 'ALL_CURRENT_WALL_CIRCLE_WORKING_ENTRIES_KEPT',
    'shared_master_import_status': 'READY_FOR_COORDINATED_IMPORT',
    'merge_policy': 'Import per variant/group identity without replacing the main interactive checkpoint; preserve prior WC-01 explicit confirmations and all remaining uncertainty labels. Native options, visual aliases and media rows are separate layers and must not be summed as distinct physical sculptures.',
    'main_owner_session': '01a144ab-1a7c-7223-a403-73a4d53d70ff'
}
write(OUT / 'IMPORT_PACKAGE.json', index)

checkpoint = read(BASE / 'walkthrough_checkpoint.json')
checkpoint.update({'updated_utc': NOW, 'current_review_id': 'WC-FAMILY', 'current_group_ref': None, 'current_review_record': str(family_receipt_path), 'current_answer_recorded': True, 'current_specifications_answer_recorded': True, 'current_answer_scope': 'Family-wide Keep of all current Wall Circle working entries, with uncertainty preserved', 'awaiting_complete_entry_keep': False, 'latest_decision': str(family_receipt_path), 'last_completed_review_id': 'WC-FAMILY', 'last_completed_group_ref': None, 'last_approval_record': str(family_receipt_path), 'state': 'WALL_CIRCLE_WORKING_REVIEW_COMPLETE', 'next_step': 'Coordinated shared-register import pending. No further Wall Circle Keep prompts for this approved snapshot.'})
write(BASE / 'walkthrough_checkpoint.json', checkpoint)
ownership = read(BASE / 'OWNERSHIP.json')
ownership.update({'updated_utc': NOW, 'active_review_id': None, 'active_group_ref': None, 'kept_reviews': [x[0] for x in all_visual], 'family_keep_record': str(family_receipt_path), 'approval_status': 'All current Wall Circle working entries kept; physical/specification unknowns and generated-media roles remain.', 'handoff_package': str(OUT / 'IMPORT_PACKAGE.json')})
write(BASE / 'OWNERSHIP.json', ownership)

journal = BASE / 'review-journal.jsonl'
seen = {json.loads(x).get('decision_id') for x in journal.read_text().splitlines() if x.strip()}
with journal.open('a') as stream:
    for event, receipt in [('USER_KEPT_COMPLETE_WORKING_ENTRY', wc03approval), ('USER_KEPT_ALL_WALL_CIRCLE_WORKING_ENTRIES', family)]:
        if receipt['decision_id'] not in seen:
            stream.write(json.dumps({'event': event, **receipt}, ensure_ascii=False) + '\n')

checks = {
    'complete_live_census': census['pagination_complete'],
    'all_167_files_accounted_once': sorted(fid for g in media_groups for fid in g['file_ids']) == sorted(assets),
    'all_13_groups_approved': len(media_groups) == 13 and all(g['working_approval'] == 'KEPT_BY_FAMILY_SCOPE' for g in media_groups),
    'all_144_native_options_preserved': len(native_rows) == 144 and len({x['variant_id'] for x in native_rows}) == 144,
    'all_18_native_patterns_preserved': len({x['attributes']['Pattern'] for x in native_rows}) == 18,
    'seven_visual_records_covered': len(visual_index) == 7,
    'wc01_user_confirmation_preserved': read(BASE / 'component-review.json')['material']['value'] == 'plaster/gypsum composite',
    'wc01_weight_remains_approximate': read(BASE / 'component-review.json')['weight']['approximate'],
    'wc02_proposals_remain_labelled': read(BASE / 'wc-02-turquoise-marbled/component-review.json')['approval']['physical_specs_verified'] is False,
    'wc03_proposals_remain_labelled': read(wc03dir / 'component-review.json')['approval']['physical_specs_verified'] is False,
    'no_extra_manufacture_claims': sum(x['physical_manufacture_confirmed'] for x in visual_index) == 1,
    'no_pending_keep_prompt': checkpoint['awaiting_complete_entry_keep'] is False
}
assert all(checks.values()), checks
write(OUT / 'VALIDATION.json', {'checked_utc': NOW, 'status': 'PASS', 'checks': checks, 'remote_mutations_performed': False, 'shared_master_files_written': False})
print(json.dumps({'status': 'PASS', 'approval': str(family_receipt_path), 'import_package': str(OUT / 'IMPORT_PACKAGE.json'), 'coverage': family['coverage'], 'visual_review_records': 7, 'shared_master_import': 'pending'}, indent=2))
