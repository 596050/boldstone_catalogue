"""Read-only independent check of purpose-toggle fix and isolated test history."""
from pathlib import Path
from urllib.parse import quote
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import urllib.request

H = Path(__file__).resolve().parent
B = H.parents[2]
APP = B.parent / 'catalogue-review'
D = APP / 'reviews/image-purpose-toggle-20261026'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
q = read(D / 'HANDOFF.json')
assert sha(D / 'HANDOFF.json') == '164a1710bb5db017a17692a14a6707d4e9be48d170bbc72dc43cc62dc6a66fb4'
assert q['version'] == '2.3.2' and q['automated_tests'] == 86 and q['python_tests_passed']
assert q['production_review_writes_by_task'] == 0
p = read(B / 'current-master.json')
assert sha(B / 'current-master.json') == 'd69cf087314d929a22174f189dcb52d04880aa23b7f73106fb9c19882875edd4'
previous = read(p['current_review_application']['verification'])
codes = {**previous['all_application_code_hashes'], **{str(B.parent / f): s for f, s in q['code_sha256'].items()}}
checks = Counter()
for f, digest in codes.items():
    assert sha(f) == digest, f
    checks['application_code_hashes'] += 1
assert sha(D / 'before-server.py') == previous['all_application_code_hashes'][str(APP / 'server.py')]
log = (D / 'python-tests.log').read_text()
assert 'Ran 86 tests' in log and log.rstrip().endswith('OK')
source = (APP / 'server.py').read_text()
assert "submitted.pop('reviewed_content_hash', None)" in source
assert "data['reviewed_content_hash'] = cat.assets[item].get('original', {}).get('dropbox_content_hash')" in source
assert "raise ValueError('A review version is required.')" in source
def snap(path):
    c = sqlite3.connect('file:' + quote(str(path)) + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('BEGIN')
    data = {t: [dict(r) for r in c.execute('SELECT * FROM ' + t)] for t in ['reviews', 'events', 'operations', 'deletion_jobs', 'deletion_batches']}
    c.rollback()
    c.close()
    return data
prod = Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3'
test = Path(q['browser_test_database'])
assert prod.resolve() != test.resolve() and prod.stat().st_ino != test.stat().st_ino
before = snap(D / 'reviews-before.sqlite3')
now = snap(prod)
qa = snap(test)
events = {r['id']: r for r in now['events']}
assert len(before['events']) == q['baseline_audit_events_preserved'] == 1873
for row in before['events']:
    assert events[row['id']] == row
    checks['baseline_events_preserved'] += 1
key = lambda r: (r['kind'], r['product_id'], r['item_id'])
old_reviews = {key(r): r for r in before['reviews']}
current = {key(r): r for r in now['reviews']}
assert set(old_reviews) <= set(current)
latest = {key(r): json.loads(r['after_json']) for r in now['events']}
changed = []
for k, row in current.items():
    if old_reviews.get(k) != row:
        assert {**row, 'data': json.loads(row['data']), 'original': json.loads(row['original'])} == latest[k]
        changed.append({'kind': k[0], 'product_id': k[1], 'item_id': k[2], 'version': row['version']})
        checks['later_owner_changes_have_events'] += 1
for k, row in old_reviews.items():
    if k[0] == 'field':
        assert current[k] == row
        checks['saved_field_rows_preserved'] += 1
added_native_activity = {}
for table in ['operations', 'deletion_jobs', 'deletion_batches']:
    old_rows = {r['id']: r for r in before[table]}
    new_rows = {r['id']: r for r in now[table]}
    assert set(old_rows) <= set(new_rows)
    for rid, row in old_rows.items():
        assert new_rows[rid] == row
        checks['prior_operations_deletions_and_transfers_preserved'] += 1
    added = [r for rid, r in new_rows.items() if rid not in old_rows]
    if table == 'operations':
        assert not added
    elif table == 'deletion_jobs':
        for row in added:
            assert any(e['kind'] == 'deletion' and e['item_id'] == row['file_id'] for e in now['events'] if e['id'] > 1873)
            checks['later_deletion_jobs_have_audit_events'] += 1
    elif table == 'deletion_batches':
        job_batches = {json.loads(j['payload']).get('batch_id') for j in now['deletion_jobs']}
        assert all(row['id'] in job_batches for row in added)
    added_native_activity[table] = [{k: row[k] for k in ['id', 'file_id', 'state', 'created_at'] if k in row} for row in added]
qa_events = {r['id']: r for r in qa['events']}
for check in q['qa_events']:
    event = qa_events[check['event']]
    assert event['kind'] == check['kind'] and event['product_id'] == check['product_id'] and event['item_id'] == check['item_id']
    data = json.loads(event['after_json'])
    assert data['data']['uses'] == check['uses']
    assert len(data['data']['reviewed_content_hash']) == 64
    expected = data['original']['asset']['original']['dropbox_content_hash']
    assert data['data']['reviewed_content_hash'] == expected
    checks['isolated_toggle_uses_and_native_hash'] += 3
qa_last = qa_events[q['qa_events'][-1]['event']]
last = json.loads(qa_last['after_json'])
saved_qa = next(r for r in qa['reviews'] if key(r) == key(qa_last))
assert json.loads(saved_qa['data']) == last['data']
assert last['data']['uses'] == ['reference', 'advertising']
# Identical event numbers belong to separate databases. They were not promoted.
assert qa_events[1874]['item_id'] != events[1874]['item_id']
assert qa_events[1878]['item_id'] != events[1878]['item_id']
checks['qa_database_and_final_persistence'] += 4
with urllib.request.urlopen('http://127.0.0.1:8767/api/health', timeout=10) as r:
    health = json.load(r)
assert health['version'] == '2.3.2' and health['products'] == 188
with urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap', timeout=20) as r:
    live = json.load(r)
assert live['source']['register_sha256'] == p['register_sha256']
assert len(live['products']) == 188 and live['dropbox_sync']['enabled']
protected = {}
for k in ['register', 'workbook']:
    f = B / p[k]
    assert sha(f) == p[k + '_sha256']
    protected[str(f)] = sha(f)
for k in ['current_asset_reference_map', 'current_native_reference_map']:
    f = B / p[k]['path']
    assert sha(f) == p[k]['sha256']
    protected[str(f)] = sha(f)
f = B / p['preferred_review_workbook']
assert sha(f) == p['current_comprehensive_workbook']['sha256']
protected[str(f)] = sha(f)
receipt = {'status': 'PASS_INDEPENDENT_IMAGE_PURPOSE_ROUND_TRIP_FIX',
    'checked_utc': datetime.now(timezone.utc).isoformat(), 'app_version': '2.3.2',
    'handoff_path': str(D / 'HANDOFF.json'), 'handoff_sha256': sha(D / 'HANDOFF.json'),
    'baseline_pointer_sha256': sha(B / 'current-master.json'), 'all_application_code_hashes': codes,
    'checks': dict(checks), 'checks_passed': sum(checks.values()), 'automated_tests': 86,
    'isolated_browser_toggle_saves_verified': 5, 'listing_advertising_and_other_uses_preserved': True,
    'hash_is_recomputed_by_server': True, 'strict_unknown_field_and_version_tests_retained': True,
    'baseline_audit_events_preserved': 1873, 'production_review_event_cutoff': max(events),
    'production_review_rows_at_snapshot': len(current), 'later_owner_changes': changed,
    'later_owner_native_activity_not_imported_into_inventory': added_native_activity,
    'qa_database_promoted': False, 'production_review_writes_by_root': 0, 'native_calls': 0,
    'http_methods_used': ['GET'], 'sqlite_mode': 'ro', 'protected_source_hashes': protected,
    'evidence': {str(D / 'python-tests.log'): sha(D / 'python-tests.log'),
        str(D / q['screenshot']): sha(D / q['screenshot'])}}
dump(H / 'independent-verification.json', receipt)
print(json.dumps({k: v for k, v in receipt.items() if k not in ['all_application_code_hashes', 'protected_source_hashes', 'evidence', 'later_owner_changes']}, indent=2))
