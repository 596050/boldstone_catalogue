from pathlib import Path
import datetime
import hashlib
import json
import sqlite3
import urllib.parse
import urllib.request

PROJECT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
RUNTIME = Path('/Users/tprice/Library/Application Support/BoldstoneReview')
BEFORE = json.loads((OUT / 'before-state.json').read_text())

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def snapshot(path):
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        return {t: [dict(r) for r in db.execute('SELECT * FROM ' + t + ' ORDER BY rowid')]
                for t in BEFORE['table_rows']}

old, now = snapshot(BEFORE['backup']), snapshot(RUNTIME / 'reviews.sqlite3')
for table in ('operations', 'deletion_jobs', 'deletion_batches'):
    assert old[table] == now[table], table
assert now['events'][:len(old['events'])] == old['events']
events = now['events'][len(old['events']):]
key = lambda r: (r['kind'], r['product_id'], r['item_id'])
old_reviews = {key(r): r for r in old['reviews']}
now_reviews = {key(r): r for r in now['reviews']}
assert not (old_reviews.keys() - now_reviews.keys())
latest = {key(e): json.loads(e['after_json']) for e in events}
changed = []
for k, row in now_reviews.items():
    if row == old_reviews.get(k):
        continue
    parsed = {**row, 'data': json.loads(row['data']), 'original': json.loads(row['original'])}
    assert parsed == latest[k], k
    changed.append({'kind': k[0], 'product_id': k[1], 'item_id': k[2], 'version': row['version']})

protected = {
    'sculpture-catalogue/current-master.json': '9a54e024644dc45f22cd69ba7118cee765987a1c5a2c48bb8948be3ee729b726',
    'sculpture-catalogue/components/reconciliation/matched-listing-master-2026-10-25/canonical-master-register.json': '9b4b15ca857bea027637b3dd1474bfb98c87746bb842b49003b526da6770e748',
    'sculpture-catalogue/components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261025T121532991771Z/complete-image-platform-register.sqlite': '26a09ffd64380e7c87dde27882b503d022bf8275510909f965718ee36aa9b591',
    'sculpture-catalogue/outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Master_Catalogue_2026-10-20.xlsx': '178d00ee841c1035a923904dcabc0b7a85264803ff5351bbb3c42c48a327528a',
    'sculpture-catalogue/outputs/01a13fe6-495b-7253-b923-31823b4cbca8/all-source-register-2026-10-25/Boldstone_Wall_Sculptures_Unified_2026-10-25_v4.xlsx': '0a77db1aec0e227acb9191c46aaa82c7f9a112761605bec7f5f7edbba6c965b9',
}
assert {p: digest(PROJECT / p) for p in protected} == protected

def get(route):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/' + route))

health, status = get('health'), get('dropbox-sync')
product, library = get('products/BSI-C02D6DF365D3'), get('library')
image = next(a for a in product['images'] if a['id'] == 'id:cnqzTNngPVsAAAAAAA6wRQ')
assert image['original']['dimensions'] == [2048, 1360]
assert image['original']['bytes'] == 4340943
assert image['association']['tier'] == 'folder'
assert image['product_ids'] == ['BSI-C02D6DF365D3']
response = urllib.request.urlopen('http://127.0.0.1:8767/api/image?' + urllib.parse.urlencode({'id': image['id']}))
blob = response.read()
assert hashlib.sha256(blob).hexdigest() == image['original']['sha256']
assert all(j['state'] == 'deleted' for j in now['deletion_jobs'])
assert not {a['id'] for a in library['images']}.intersection(j['file_id'] for j in now['deletion_jobs'])
inventory = json.loads((RUNTIME / 'dropbox-sync/inventory.json').read_text())
scan = {k: inventory[k] for k in ('generation', 'checked_utc', 'scan', 'image_count', 'new_image_count',
                                'pending_previews', 'native_writes', 'snapshot_path', 'snapshot_sha256')}
assert digest(scan['snapshot_path']) == scan['snapshot_sha256']
code = ['dropbox_sync.py', 'dropbox_sync_worker.py', 'server.py', 'projection.py', 'media.py', 'live_review.py',
        'static/app.js', 'static/sync-tools.js', 'static/index.html', 'static/style.css',
        'tests/test_dropbox_sync.py', 'tests/sync-refresh.mjs', 'README.md']
receipt = {
    'schema': 'boldstone-automatic-images-handoff/v1',
    'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'Read-only automatic Wall Sculptures image availability in app v2.3. No canonical publication or native mutations. New images start unreviewed; separately saved choices are preserved.',
    'app': health, 'sync': status, 'native_scan': scan, 'new_acanthus_image': image,
    'current_image_reviews': [r for r in product['reviews'] if r['item_id'] == image['id']],
    'new_image_http': {'status': response.status, 'content_type': response.headers['Content-Type'],
                       'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()},
    'saved_state': {'backup': BEFORE['backup'],
        'tables': {t: {'rows': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
                   for t, rows in now.items()},
        'baseline_event_history_preserved': True, 'all_review_changes_have_new_audit_events': True,
        'new_event_ids': [e['id'] for e in events], 'changed_or_added_reviews': changed,
        'deletions_and_transfers_unchanged': True, 'deleted_jobs_hidden': len(now['deletion_jobs']),
        'note': 'Owner continued saving reviews during implementation. Those recorded changes, including new image selections, were preserved. This task made no review API writes.'},
    'canonical_sources': protected, 'canonical_sources_unchanged': True,
    'code_sha256': {p: digest(PROJECT / 'catalogue-review' / p) for p in code},
    'validation': {'python_tests': 77, 'refresh_controller_tests': 6, 'javascript_syntax': 'passed',
        'browser_console_errors': 0,
        'browser_verification': 'New image, original dimensions and size, and advancing automatic check time visible. Manual Check now succeeded. A second new image was collected by the subsequent background scan.',
        'test_logs': {p: digest(OUT / p) for p in ('python-tests.log', 'refresh-tests.log')},
        'screenshot': str(OUT / 'acanthus-automatic-image.jpg'),
        'screenshot_sha256': digest(OUT / 'acanthus-automatic-image.jpg')},
    'reconciliation_note': 'Use the complete native inventory for reconciliation. Do not infer that changes since the old catalogue consist only of the seven queued deletions and the new uploads.',
}
path = OUT / 'HANDOFF.json'
assert not path.exists(), 'Seal already exists'
path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'handoff': str(path), 'sha256': digest(path), 'reviews': len(now['reviews']),
                  'events': len(now['events']), 'new_events': [e['id'] for e in events],
                  'image_count': scan['image_count'], 'new_images': scan['new_image_count'],
                  'generation': scan['generation'], 'native_snapshot': scan['snapshot_path']}, indent=2))
