"""Import only the completed In situ Listing-use removal, with exact readbacks."""
from pathlib import Path
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import csv, hashlib, json, sqlite3

H = Path(__file__).resolve().parent
BASE = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, d: Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
m = read(H / 'input-manifest.json')
CUT = Path(m['input_directory'])
src = m['sources']
before, after = [read(src[k]['snapshot']) for k in ['policy_before', 'policy_after']]
receipt = read(src['policy_verification']['snapshot'])
plan = read(src['policy_plan']['snapshot'])
applied = [json.loads(line) for line in Path(src['policy_apply_results']['snapshot']).read_text().splitlines()]
key = lambda r: (r['kind'], r['product_id'], r['item_id'])
br, ar = [{key(r): r for r in library['reviews']} for library in [before, after]]
images = {r['id']: r for r in after['images']}
def effective_types(fid):
    return ar.get(('asset', '', fid), {}).get('data', {}).get('types', images.get(fid, {}).get('types', []))
original = read(src['register']['snapshot'])
g = deepcopy(original)
active = set(g['active_option_ids'])
options = {o['product_id']: o for o in g['options']}
targets = {(r['product_id'], r['asset_id']): r for r in plan['targets']}
assert receipt['status'] == 'PASS' and not receipt['remaining_in_situ_with_listing']
assert before['images'] == after['images'], 'Image types, originals or component associations changed'
assert set(br) == set(ar) and len(targets) == len(applied) == 91
assert {(r['product_id'], r['asset_id']) for r in applied} == set(targets)
assert {k for k in br if br[k] != ar[k]} == {('image', *k) for k in targets}
for k in before:
    if k != 'reviews': assert before[k] == after[k]
db = sqlite3.connect(Path(src['app_review_cut']['snapshot']).as_uri() + '?mode=ro', uri=True)
db.row_factory = sqlite3.Row
exclusions, byproduct = [], defaultdict(list)
for row in applied:
    pid, fid = row['product_id'], row['asset_id']
    a, b = row['before'], row['after']
    assert pid in active and row['state'] == 'updated' and 'in_situ' in effective_types(fid)
    assert br[('image', pid, fid)]['data'] == a
    saved = ar[('image', pid, fid)]
    assert saved['data'] == b and saved['version'] == row['after_version'] == row['before_version'] + 1
    assert b['uses'] == [x for x in a['uses'] if x != 'listing'] and 'listing' in a['uses']
    assert b.get('primary', False) is False
    assert {k: v for k, v in b.items() if k not in {'uses', 'primary', 'reviewed_content_hash'}} == {k: v for k, v in a.items() if k not in {'uses', 'primary', 'reviewed_content_hash'}}
    live = dict(db.execute('SELECT * FROM reviews WHERE kind=? AND product_id=? AND item_id=?', ('image', pid, fid)).fetchone())
    assert json.loads(live['data']) == b and live['version'] == saved['version'], 'Captured DB differs from completed app save'
    e = {'product_id': pid, 'name': options[pid]['name'], 'file_id': fid,
         'folder_id': images[fid]['folder_id'], 'image_url': row['image_url'], 'folder_url': row['folder_url'],
         'effective_image_types': effective_types(fid), 'excluded_use': 'listing',
         'remaining_uses': b['uses'], 'primary_cleared': bool(a.get('primary')),
         'before_review_version': row['before_version'], 'review_version': row['after_version'],
         'review_updated_at': saved['updated_at'], 'decision_source_register_sha256': saved['source_hash'],
         'before_review_data': a, 'after_review_data': b,
         'basis': 'Explicit owner instruction, applied and independently read back in the app.',
         'scope': 'Listing-use exclusion only. In situ types, other purposes, originals and component associations retained.'}
    exclusions.append(e); byproduct[pid].append(e)
db.close()
remaining = [key(r) for r in after['reviews'] if r['kind'] == 'image' and r['product_id'] in active and 'listing' in r['data'].get('uses', []) and 'in_situ' in effective_types(r['item_id'])]
assert not remaining
assert len({e['file_id'] for e in exclusions}) == 68 and len(byproduct) == 30
cleared = {r['product_id']: r for r in receipt['primary_choices_cleared']}
assert set(cleared) == {e['product_id'] for e in exclusions if e['primary_cleared']} and len(cleared) == 4
primary_changes = []
for pid, rows in byproduct.items():
    o = options[pid]
    previous = deepcopy(o.get('image_use_exclusions', []))
    assert not previous, 'Review an existing exclusion import before merging'
    o['image_use_exclusions'] = rows
    if pid not in cleared: continue
    e = next(x for x in rows if x['primary_cleared'])
    assert o['file_id'] == e['file_id'] == cleared[pid]['asset_id']
    old = deepcopy(o)
    o['historical_primary_reference'] = {'file_id': o['file_id'], 'folder_id': o['folder_id'],
        'image_url_at_previous_publication': o['image_url'], 'folder_url': o['folder_url'],
        'status': 'Listing use removed by owner In situ policy; original retained for its other purposes.',
        'reason': 'in_situ_listing_exclusion', 'selection_before_exclusion': deepcopy(o.get('current_primary_selection')),
        'review_version': e['review_version'], 'policy_receipt': src['policy_verification']}
    o['file_id'] = None
    o['image_url'] = ''
    o['current_primary_selection'] = {'status': 'Cleared by explicit owner In situ Listing-use exclusion',
        'review_version': e['review_version'], 'review_updated_at': e['review_updated_at'],
        'scope': 'Replacement Primary remains unselected. No new identity, physical or platform inference.'}
    o['photo_coverage']['individual'] = 'Current Primary unbound — In situ image excluded from Listing by owner; choose a permitted full view'
    primary_changes.append({'product_id': pid, 'name': o['name'], 'before_file_id': old['file_id'],
        'file_id': None, 'folder_id': o['folder_id'], 'image_url': '', 'folder_url': o['folder_url'],
        'review_version': e['review_version'], 'reason': 'in_situ_listing_exclusion'})
allowed = {'file_id', 'image_url', 'historical_primary_reference', 'current_primary_selection', 'photo_coverage', 'image_use_exclusions'}
for a, b in zip(original['options'], g['options']):
    changed = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert changed <= allowed
    if a['product_id'] not in byproduct: assert a == b
    assert a['specifications'] == b['specifications'] and a.get('master_fields') == b.get('master_fields')
g['summary']['individual_options_with_dropbox_reference'] = sum(o['product_id'] in active and bool(o.get('file_id')) for o in g['options'])
g['latest_in_situ_listing_policy_import'] = {'status': 'COMPLETED_APP_POLICY_EXCLUSIONS_INDEPENDENTLY_READ_BACK',
    'policy_cut_utc': m['policy_cut_utc'], 'native_inventory_cut_utc_retained': m['native_inventory_cut_utc'],
    'previous_register_sha256': src['register']['sha256'], 'verification': src['policy_verification'],
    'updated_choices': 91, 'unique_images': 68, 'affected_active_options': 30,
    'cleared_primary_options': sorted(cleared), 'remaining_in_situ_listing_choices': 0,
    'policy': plan['policy'], 'shared_types_originals_other_purposes_component_associations_preserved': True,
    'new_primary_choices_inferred': 0, 'new_physical_or_commercial_verifications': 0,
    'publisher_native_app_or_platform_writes': 0}
assert len(active) == 186 and len(g['options']) == 189
assert len(g['original_review_specification_assertions']) == 1668
assert g['summary']['individual_options_with_dropbox_reference'] == 179
write(H/'canonical-master-register.json', g)
write(H/'listing-use-exclusions.json', exclusions)
overlay = read(CUT/'current-image-overlay-source.json')
for r in overlay:
    r['selected_references'] = [s for s in r['selected_references'] if not (s['role'] == 'primary' and s['product_id'] in cleared and r['file_id'] == cleared[s['product_id']]['asset_id'])]
write(H/'current-image-overlay.json', overlay)
report = {'status': 'SCOPED_LISTING_USE_POLICY_REGISTER_PREPARED', 'active_options': 186, 'retained_options': 189,
    'current_scoped_files': len(overlay), 'current_primary_references': 179, 'current_context_references': 158,
    'primary_changes': primary_changes, 'context_changes': [], 'series_changes': [], 'new_context_losses': [],
    'new_series_losses': [], 'effective_context_owner_holds': original['latest_verified_native_filename_import']['effective_context_owner_holds'],
    'exclusion_choices': 91, 'excluded_unique_images': 68, 'affected_active_options': 30,
    'primary_requests': 6, 'source_assertions_preserved': 1668,
    'originals_and_other_purposes_preserved': True, 'physical_commercial_and_platform_changes': 0,
    'source_register_sha256': src['register']['sha256'], 'register_sha256': sha(H/'canonical-master-register.json')}
write(H/'register-preparation.json', report)
write(H/'policy-independent-readback.json', {'status': 'PASS', 'choices_verified': len(exclusions),
    'images_verified': 68, 'active_sculptures': 30, 'shared_image_records_unchanged': len(images),
    'review_delta_exactly_the_91_targets': True, 'remaining_in_situ_listing_choices': remaining,
    'captured_database_matches_completed_saves': True, 'cleared_primary_product_ids': sorted(cleared),
    'no_other_purpose_original_type_component_or_physical_changes': True,
    'source_hashes': {k: src[k]['sha256'] for k in ['policy_before', 'policy_after', 'policy_verification', 'policy_apply_results']}})
print(json.dumps(report, ensure_ascii=False, indent=2))
