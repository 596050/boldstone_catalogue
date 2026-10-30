"""Independent read-only audit of automatic image discovery and owner history."""
from pathlib import Path
from urllib.parse import quote, urlencode
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import struct
import urllib.request

H = Path(__file__).resolve().parent
B = H.parents[2]
APP = B.parent / 'catalogue-review'
D = APP / 'reviews/automatic-dropbox-images-20261026'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
key = lambda r: (r['kind'], r['product_id'], r['item_id'])
checks = Counter()
q = read(D / 'HANDOFF.json')
assert sha(D / 'HANDOFF.json') == 'ffda92321ff584fe5b5c89dda31db9d35bcaad27ebe5b8913ebb8e279e2ad419'
for name, value in q['canonical_sources'].items():
    assert sha(B.parent / name) == value, name
    checks['protected_sources'] += 1
old_code = read(B / 'components/reconciliation/six-native-deletions-and-app-review-2026-10-25/app-independent-validation.json')['all_application_code_hashes']
code = {**old_code, **{str(APP / n): v for n, v in q['code_sha256'].items()}}
for name, value in code.items():
    assert sha(name) == value, name
    checks['application_code'] += 1
for name, value in q['validation']['test_logs'].items():
    assert sha(D / name) == value
assert sha(q['validation']['screenshot']) == q['validation']['screenshot_sha256']
assert q['validation']['python_tests'] == 77 and q['validation']['refresh_controller_tests'] == 6
p = read(B / 'current-master.json')
g = read(B / p['register'])
active = set(g['active_option_ids'])
assert len(active) == 188 and not p['all_actual_specifications_complete']
baseline = read(B / p['current_native_reference_map']['path'])['current_objects']
baseline_files = {k: r for k, r in baseline.items() if r.get('object_type') == 'file' and r.get('current_wall_snapshot_present')}
assert len(baseline_files) == 6360
input_ref = read(H / 'latest-inventory-input.json')
assert sha(input_ref['snapshot_path']) == input_ref['snapshot_sha256']
inventory = read(input_ref['snapshot_path'])
assert inventory['scope']['namespace'] == '202238505'
assert inventory['scope']['root_id'] == 'id:cnqzTNngPVsAAAAAAArpsA'
root = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'
assert inventory['scope']['root_path'] == root and inventory['scan']['has_more'] is False
signature = hashlib.sha256(json.dumps({k: inventory[k] for k in ['records', 'media', 'retired']}, sort_keys=True).encode()).hexdigest()
assert signature == inventory['signature']
records = inventory['records']
folders = {v['path'].casefold(): k for k, v in records.items() if v['kind'] == 'folder'}
images = {k: v for k, v in records.items() if v['kind'] == 'file'}
assert len(images) == inventory['image_count'] == 6285
assert len(folders) == 443
for fid, row in records.items():
    assert fid == row['id'] and (row['path'] == root or row['path'].startswith(root + '/'))
    if row['kind'] == 'file':
        assert row['folder_id'] == folders[str(Path(row['path']).parent).casefold()]
        assert row['rev'] and row['content_hash'] and row['bytes'] > 0
    checks['inventory_records'] += 1
missing = set(baseline_files) - set(images)
new = set(images) - set(baseline_files)
assert len(missing) == 81 and len(new) == 6
native = read(H / 'independent-native-metadata.json')
lookups = {r['target']: r for r in native['metadata']}
assert all(lookups[fid]['not_found'] and lookups[fid]['isError'] for fid in missing)
assert all(lookups[fid]['metadata_type'] == 'file' and not lookups[fid]['isError'] for fid in new)
checks['independent_native_lookups'] += len(lookups)
originals = []
for fid in sorted(new):
    row, meta = images[fid], lookups[fid]['metadata']
    assert meta['rev'] == row['rev'] and meta['size'] == row['bytes'] and meta['path_display'] == row['path']
    assert lookups[row['folder_id']]['metadata']['path_display'] == str(Path(row['path']).parent)
    media = inventory['media'][fid]
    local = Path(media['path'])
    assert local.is_relative_to(Path.home() / 'Library/Application Support/BoldstoneReview/originals')
    content, outer = hashlib.sha256(), hashlib.sha256()
    with local.open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            content.update(block)
            outer.update(hashlib.sha256(block).digest())
    assert local.stat().st_size == row['bytes']
    assert outer.hexdigest() == row['content_hash'] == media['dropbox_content_hash']
    assert content.hexdigest() == media['sha256']
    with local.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR'
    assert list(struct.unpack('>II', header[16:24])) == media['dimensions']
    originals.append({'file_id': fid, 'name': row['name'], 'path': row['path'], 'folder_id': row['folder_id'],
        'image_url': 'https://www.dropbox.com/preview' + quote(row['path'], safe='/'),
        'folder_url': 'https://www.dropbox.com/home' + quote(str(Path(row['path']).parent), safe='/'),
        'revision': row['rev'], 'bytes': row['bytes'], 'sha256': content.hexdigest(),
        'dropbox_content_hash': row['content_hash'], 'dimensions': media['dimensions'], 'local_path': str(local),
        'identity_finish_and_use_from_folder_only': False})
    checks['new_original_checks'] += 7
connector = read(H / 'independent-native-listing.json')
assert connector['complete'] and not connector['pages'][-1]['has_more'] and len(connector['pages']) == 12
listed = {r['file_id']: r for r in connector['entries']}
for fid in set(listed) & set(records):
    old, row = listed[fid], records[fid]
    assert old['path'] == 'ns:202238505/' + row['path']
    assert old['name'] == row['name']
    if row['kind'] == 'file':
        assert old['file'].get('size', 0) == row['bytes']
    checks['independent_common_inventory_records'] += 1
backup = read(D / 'before-state.json')['backup']
database = Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3'
def snapshot(path):
    c = sqlite3.connect('file:' + quote(str(path)) + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('BEGIN')
    result = {t: [dict(r) for r in c.execute('SELECT * FROM ' + t)] for t in ['reviews', 'events', 'operations', 'deletion_jobs', 'deletion_batches']}
    c.rollback()
    c.close()
    return result
before, now = snapshot(backup), snapshot(database)
old_reviews, current = {key(r): r for r in before['reviews']}, {key(r): r for r in now['reviews']}
old_events, events = {r['id']: r for r in before['events']}, {r['id']: r for r in now['events']}
assert len(old_events) == 1852 and set(old_reviews) <= set(current)
for eid, row in old_events.items():
    assert events[eid] == row
    checks['prior_events_preserved'] += 1
for table in ['operations', 'deletion_jobs', 'deletion_batches']:
    assert now[table] == before[table], table
    checks['operations_jobs_batches_preserved'] += len(now[table])
latest = {key(r): json.loads(r['after_json']) for r in now['events']}
changed = []
for k, row in current.items():
    if row == old_reviews.get(k):
        continue
    parsed = {**row, 'data': json.loads(row['data']), 'original': json.loads(row['original'])}
    assert parsed == latest[k], k
    changed.append({'kind': k[0], 'product_id': k[1], 'item_id': k[2], 'version': row['version']})
    checks['owner_changes_bound_to_audit_events'] += 1
fields = {'Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Price', 'Availability', 'Lead time'}
for k, row in old_reviews.items():
    if k[0] == 'field':
        assert current[k] == row
        checks['saved_fields_preserved'] += 1
assert sum(k[0] == 'field' and k[2] in fields for k in current) == 1316
deletions = []
for job in now['deletion_jobs']:
    payload, result = json.loads(job['payload']), json.loads(job['result'])
    fid = job['file_id']
    assert job['state'] == result['state'] == 'deleted'
    assert result['delete_response_confirmed'] and result['verified_absent'] and fid in missing
    deletions.append({'file_id': fid, 'job_id': job['id'], 'batch_id': payload.get('batch_id'),
        'name': payload['file']['name'], 'revision': payload['file']['revision'],
        'confirmation_at': result['confirmation_at'], 'app_absence_checked_utc': result['checked_utc']})
assert len(deletions) == 13
deleted_ids = {r['file_id'] for r in deletions}
absence_rows = []
for fid in sorted(missing):
    row = baseline_files[fid]
    absence_rows.append({'file_id': fid, 'name': row['name'], 'family': row.get('family'),
        'historical_path': row['display_path'],
        'state': 'OWNER_CONFIRMED_APP_DELETION' if fid in deleted_ids else 'NATIVE_NOT_FOUND_WITHOUT_APP_DELETION_RECEIPT',
        'owner_deletion_receipt_present': fid in deleted_ids,
        'native_not_found_checked_utc': native['checked_utc']})
def get(route):
    with urllib.request.urlopen('http://127.0.0.1:8767/api/' + route, timeout=20) as response:
        return json.load(response)
health, status, bootstrap, library = get('health'), get('dropbox-sync'), get('bootstrap'), get('library')
assert health['version'] == '2.3' and health['products'] == 188
assert {r['id'] for r in bootstrap['products']} == active
assert bootstrap['source']['register_sha256'] == p['register_sha256']
live_ids = {r['id'] for r in library['images']}
assert new <= live_ids and not missing.intersection(live_ids)
assert status['enabled'] and status['interval_seconds'] == 60 and not status['error']
for row in originals:
    response = urllib.request.urlopen('http://127.0.0.1:8767/api/image?' + urlencode({'id': row['file_id']}), timeout=20)
    assert response.status == 200 and hashlib.sha256(response.read()).hexdigest() == row['sha256']
    checks['new_original_http_bytes'] += 1
for name, digest in q['canonical_sources'].items():
    assert sha(B.parent / name) == digest
dump(H / 'new-images.json', originals)
dump(H / 'native-absence-register.json', {'snapshot_generation': inventory['generation'], 'rows': absence_rows,
    'confirmed_app_deletions': deletions, 'no_deletion_action_inferred_for_other_absences': True})
dump(H / 'saved-review-state.json', {'event_cutoff': max(events), 'reviews': len(current),
    'new_event_ids': sorted(set(events) - set(old_events)), 'changed_or_added_reviews': changed,
    'prior_1852_events_preserved': True, 'saved_field_reviews_unchanged': checks['saved_fields_preserved'],
    'operations_deletions_and_transfers_unchanged': True,
    'current_new_image_choices': [{'product_id': k[1], 'file_id': k[2], 'version': row['version'],
        'data': json.loads(row['data'])} for k, row in current.items() if k[0] == 'image' and k[2] in new]})
receipt = {'status': 'PASS_INDEPENDENT_AUTOMATIC_IMAGE_INVENTORY_AND_REVIEW_HISTORY',
    'checked_utc': datetime.now(timezone.utc).isoformat(), 'app_version': '2.3', 'handoff_sha256': sha(D / 'HANDOFF.json'),
    'input_snapshot': input_ref, 'source_baseline_files': 6360, 'snapshot_images': len(images),
    'snapshot_folders_including_root': len(folders), 'new_native_images': len(new),
    'baseline_files_native_not_found': len(missing), 'owner_confirmed_app_deletions': len(deleted_ids),
    'other_native_absences_without_app_deletion_receipts': len(missing - deleted_ids),
    'native_counts_are_a_fixed_snapshot': True, 'live_sync_at_audit': status,
    'products': 188, 'specification_fields_preserved': 1316, 'review_event_cutoff': max(events),
    'saved_review_rows': len(current), 'checks': dict(checks), 'checks_passed': sum(checks.values()),
    'all_application_code_hashes': code, 'protected_source_hashes': q['canonical_sources'],
    'http_methods': ['GET'], 'sqlite_mode': 'ro', 'native_mutations': 0, 'active_review_db_writes': 0,
    'canonical_identity_specification_or_image_choice_imports': 0}
dump(H / 'independent-verification.json', receipt)
print(json.dumps({k: v for k, v in receipt.items() if k not in ['all_application_code_hashes', 'protected_source_hashes', 'checks']}, indent=2))
