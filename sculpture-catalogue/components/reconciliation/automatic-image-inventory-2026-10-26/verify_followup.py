"""Verify folder tags, all renamed native IDs, and the later saved owner state."""
from pathlib import Path
from urllib.parse import quote
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import urllib.request

H = Path(__file__).resolve().parent
P = H / 'post-folder-followup'
P.mkdir(exist_ok=True)
B = H.parents[2]
APP = B.parent / 'catalogue-review'
D = APP / 'reviews/dropbox-folder-types-20261026'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
checks = Counter()
q = read(D / 'HANDOFF.json')
assert sha(D / 'HANDOFF.json') == 'f6b9cd4c2f870fd2a7b44a920958ac9fc2c9cb76e0e215edf0c3664707f57d9b'
for name, digest in q['evidence_sha256'].items():
    assert sha(D / name) == digest
code = read(H / 'independent-verification.json')['all_application_code_hashes']
code.update({str(APP / k): v for k, v in q['code_sha256'].items()})
for name, digest in code.items():
    assert sha(name) == digest, name
    checks['current_application_code'] += 1
assert q['tests']['python_passed'] == 84
assert q['policy'].startswith('In Situ folder labels provide default types.')
source = q['live_source']
assert sha(source['path']) == source['sha256']
state = read(source['path'])
assert state['generation'] == 8 and state['image_count'] == 6284 and state['scan']['has_more'] is False
assert state['scope']['namespace'] == '202238505'
assert state['scope']['root_id'] == 'id:cnqzTNngPVsAAAAAAArpsA'
signature = hashlib.sha256(json.dumps({k: state[k] for k in ['records', 'media', 'retired']}, sort_keys=True).encode()).hexdigest()
assert signature == state['signature']
plan = read(D / 'deco-rename-plan.json')['entries']
assert len(plan) == 18
direct = read(H / 'deco-independent-parent-readback.json')
assert direct['has_more'] is False and len(direct['entries']) == 18
observed = {r['file_id']: r for r in direct['entries']}
before = read(D / 'deco-before-native-records.json')['records']
after = state['records']
family = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Deco Palm and Spiral'
actual_family = {fid: r for fid, r in after.items() if r['path'].startswith(family + '/')}
assert set(before) == set(actual_family) and len(before) == 647
receipt = read(D / 'deco-move-result.json')
assert receipt['status'] == 'completed' and len(receipt['move_result']['entries']) == 18
assert all(r['entry_status'] == 'success' for r in receipt['move_result']['entries'])
normal = lambda p: p.removeprefix('ns:202238505/')
renames = []
for r in plan:
    fid = r['file_id']
    assert fid in observed and after[fid]['name'] == observed[fid]['name'] == r['destination_name']
    assert r['destination_name'] == 'Deco Palm and Spiral ' + r['source_name']
    assert observed[fid]['path'] == r['destination_path']
    assert after[fid]['path'] == normal(r['destination_path'])
    renames.append({'folder_id': fid, 'before': normal(r['source_path']), 'after': normal(r['destination_path'])})
    checks['renamed_folder_id_path_name'] += 1
files = revisions = 0
for fid, old in before.items():
    new = after[fid]
    move = next(r for r in renames if old['path'] == r['before'] or old['path'].startswith(r['before'] + '/'))
    assert new['path'] == move['after'] + old['path'][len(move['before']):]
    assert new['id'] == old['id'] and new['kind'] == old['kind']
    if old['kind'] == 'file':
        files += 1
        assert all(new[k] == old[k] for k in ['name', 'bytes', 'content_hash'])
        revisions += new['rev'] != old['rev']
    checks['renamed_descendant_identity_and_contents'] += 1
assert files == revisions == 629
old_input = read(H / 'latest-inventory-input.json')
old_state = read(old_input['snapshot_path'])
extra_absent = set(old_state['records']) - set(after)
assert extra_absent == {'id:cnqzTNngPVsAAAAAAAt-0g'}
assert not (set(after) - set(old_state['records']))
extra = read(H / 'additional-native-absence.json')
assert extra['target'] in extra_absent and extra['not_found'] and extra['isError']
for fid in set(old_state['records']) & set(after):
    old, new = old_state['records'][fid], after[fid]
    if fid in before:
        continue
    assert old == new
    checks['other_native_records_preserved'] += 1
current = read(B / 'current-master.json')
assert sha(B / 'current-master.json') == '9a54e024644dc45f22cd69ba7118cee765987a1c5a2c48bb8948be3ee729b726'
g = read(B / current['register'])
assets = read(B / current['current_asset_reference_map']['path'])
def snap(path):
    c = sqlite3.connect('file:' + quote(str(path)) + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('BEGIN')
    rows = {t: [dict(r) for r in c.execute('SELECT * FROM ' + t)] for t in ['reviews', 'events', 'operations', 'deletion_jobs', 'deletion_batches']}
    c.rollback()
    c.close()
    return rows
old_db = snap(q['saved_state']['backup'])
now_db = snap(Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3')
events = {r['id']: r for r in now_db['events']}
for row in old_db['events']:
    assert events[row['id']] == row
    checks['prior_owner_events_preserved'] += 1
key = lambda r: (r['kind'], r['product_id'], r['item_id'])
old_reviews = {key(r): r for r in old_db['reviews']}
now_reviews = {key(r): r for r in now_db['reviews']}
assert set(old_reviews) <= set(now_reviews)
latest = {key(r): json.loads(r['after_json']) for r in now_db['events']}
for k, row in now_reviews.items():
    if old_reviews.get(k) != row:
        assert {**row, 'data': json.loads(row['data']), 'original': json.loads(row['original'])} == latest[k]
        checks['later_owner_changes_have_events'] += 1
for k, row in old_reviews.items():
    if k[0] == 'field':
        assert row == now_reviews[k]
        checks['working_field_reviews_preserved'] += 1
for table in ['operations', 'deletion_jobs', 'deletion_batches']:
    assert now_db[table] == old_db[table]
def get(route):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/' + route, timeout=20))
health = get('health')
assert health['version'] == '2.3.1' and health['products'] == 188
pid = 'BSI-BCAB636141CC'
product = get('products/' + pid)
target = {'id:cnqzTNngPVsAAAAAAA6wUg', 'id:cnqzTNngPVsAAAAAAA6wUw', 'id:cnqzTNngPVsAAAAAAA6wVA'}
found = {r['id']: r for r in product['images'] if r['id'] in target}
assert set(found) == target
for fid, r in found.items():
    assert 'in_situ' in r['types'] and r['product_ids'] == [pid]
    assert r['association']['tier'] == 'folder' and r['folder_id'] == 'id:cnqzTNngPVsAAAAAAA6wUQ'
    assert r['folder_type_evidence'][0]['basis'] == 'Current Dropbox folder is labelled In Situ'
    checks['exact_component_in_situ_images'] += 1
input_ref = {'snapshot_path': source['path'], 'snapshot_sha256': source['sha256'], 'generation': 8,
    'checked_utc': source['checked_utc'], 'immutable_snapshot_captured_utc': state['checked_utc'],
    'image_count': state['image_count'], 'new_image_count': state['new_image_count'],
    'scan': state['scan'], 'native_writes': 0}
dump(P / 'latest-inventory-input.json', input_ref)
new_images = read(H / 'new-images.json')
for r in new_images:
    live = after[r['file_id']]
    assert all(live[k] == r[v] for k, v in [('bytes', 'bytes'), ('content_hash', 'dropbox_content_hash'), ('path', 'path')])
dump(P / 'new-images.json', new_images)
absence = read(H / 'native-absence-register.json')
fid = next(iter(extra_absent))
old = assets[fid]
absence['rows'].append({'file_id': fid, 'name': old['name'], 'family': old['family'],
    'historical_path': old['display_path'], 'state': 'NATIVE_NOT_FOUND_WITHOUT_APP_DELETION_RECEIPT',
    'owner_deletion_receipt_present': False, 'native_not_found_checked_utc': extra['checked_utc']})
absence['snapshot_generation'] = 8
assert len(absence['rows']) == 82
dump(P / 'native-absence-register.json', absence)
new_ids = {r['file_id'] for r in new_images}
dump(P / 'saved-review-state.json', {'event_cutoff': max(events), 'reviews': len(now_reviews),
    'current_new_image_choices': [{'product_id': k[1], 'file_id': k[2], 'version': r['version'], 'data': json.loads(r['data'])}
        for k, r in now_reviews.items() if k[0] == 'image' and k[2] in new_ids]})
receipt = {'status': 'PASS_INDEPENDENT_FOLDER_TAGS_RENAMES_AND_NATIVE_FOLLOWUP',
    'checked_utc': datetime.now(timezone.utc).isoformat(), 'handoff_path': str(D / 'HANDOFF.json'),
    'handoff_sha256': sha(D / 'HANDOFF.json'), 'app_version': '2.3.1', 'input_snapshot': input_ref,
    'renamed_folders': 18, 'retained_deco_descendant_ids': 647, 'retained_deco_file_ids_hashes_sizes_names': 629,
    'file_revisions_advanced_by_native_folder_move': revisions, 'native_images': 6284, 'folders_including_root': 443,
    'new_uploads': 6, 'native_not_found_baseline_files': 82, 'confirmed_app_deletion_receipts': 13,
    'other_native_absences_without_app_deletion_receipt': 69,
    'exact_one_leaf_white_context_images': 3, 'review_event_cutoff': max(events), 'saved_review_rows': len(now_reviews),
    'all_application_code_hashes': code, 'checks': dict(checks), 'checks_passed': sum(checks.values()),
    'base_native_verification': {'path': str(H / 'independent-verification.json'), 'sha256': sha(H / 'independent-verification.json')},
    'native_mutations_by_root': 0, 'active_review_db_writes_by_root': 0, 'source_field_or_identity_imports': 0,
    'known_authorized_native_mutations_by_owning_thread': '18 same-ID folder renames; separately sealed receipt',
    'http_methods_used': ['GET'], 'sqlite_mode': 'ro'}
dump(P / 'independent-verification.json', receipt)
print(json.dumps({k: v for k, v in receipt.items() if k not in ['all_application_code_hashes', 'checks']}, indent=2))
