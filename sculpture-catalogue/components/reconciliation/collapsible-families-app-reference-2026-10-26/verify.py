"""Audit collapsible-family release and narrowly scoped Gold Leaf tagging."""
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
D = APP / 'reviews/collapsible-families-20261026'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
q = read(D / 'HANDOFF.json')
assert sha(D / 'HANDOFF.json') == '4c2b7f1c3cb5591b8113a112ec9f3a2ce7841d0d23059063557bee731394957b'
p = read(B / 'current-master.json')
assert sha(B / 'current-master.json') == '09deec412bd572303f81796921301d9ad396262f4e77cf2079d972c2dffcb282'
previous = read(p['current_review_application']['verification'])
codes = {**previous['all_application_code_hashes'], **{str(APP / k): v for k, v in q['code_sha256'].items()}}
checks = Counter()
for f, digest in codes.items():
    assert sha(f) == digest, f
    checks['application_code_hashes'] += 1
for name in ['server.py', 'static/family-tools.js', 'static/index.html', 'static/style.css']:
    before = D / ('before-' + Path(name).name)
    assert sha(before) == previous['all_application_code_hashes'][str(APP / name)]
    checks['before_code_identity'] += 1
browser = q['browser_checks']
assert all(browser[k] is True for k in ['single_collapse_hides_child', 'open_sculpture_unchanged',
    'collapse_persists_after_reload', 'search_reveals_match', 'clearing_search_restores_collapse',
    'collapsed_heading_still_opens_overview'])
assert browser['collapse_all_count'] == browser['expand_all_count'] == 58 and browser['console_errors'] == 0
script = (APP / 'static/family-tools.js').read_text()
assert 'localStorage.getItem(familyCollapseKey)' in script and 'localStorage.setItem(familyCollapseKey' in script
assert 'filteredCollapsedFamilies.clear()' in script and 'data-family-toggle' in script
assert "button.id==='collapse-families'" in script and "button.id==='expand-families'" in script
checks['browser_behaviour_evidence'] += 8
category = read(D / 'gold-leaf-category.json')
fid = q['gold_leaf_image']['id']
assert fid == category['asset_id'] == 'id:cnqzTNngPVsAAAAAAA6wUA'
assert q['task_review_writes'] == 1 and not q['gold_leaf_image']['task_changed_listing_or_primary']
assert category['before'] == {'version': 0, 'data': {}}
assert category['after']['data'] == {'types': ['product'], 'rights': 'unknown'}
database = Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3'
def snap(path):
    c = sqlite3.connect('file:' + quote(str(path)) + '?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    c.execute('BEGIN')
    rows = {t: [dict(r) for r in c.execute('SELECT * FROM ' + t)] for t in ['reviews', 'events', 'operations', 'deletion_jobs', 'deletion_batches']}
    c.rollback()
    c.close()
    return rows
baseline = snap(APP / 'reviews/image-purpose-toggle-20261026/reviews-before.sqlite3')
now = snap(database)
events = {r['id']: r for r in now['events']}
for row in baseline['events']:
    assert events[row['id']] == row
    checks['prior_immutable_events_preserved'] += 1
key = lambda r: (r['kind'], r['product_id'], r['item_id'])
latest = {key(r): json.loads(r['after_json']) for r in now['events']}
current = {key(r): r for r in now['reviews']}
for k, row in current.items():
    assert {**row, 'data': json.loads(row['data']), 'original': json.loads(row['original'])} == latest[k]
    checks['current_review_bound_to_latest_audit_event'] += 1
old_fields = {key(r): r for r in baseline['reviews'] if r['kind'] == 'field'}
for k, row in old_fields.items():
    assert current[k] == row
    checks['working_field_rows_preserved'] += 1
before_meta = read(D / 'before.json')
before_state = {key(r): json.loads(r['after_json']) for r in now['events'] if r['id'] <= before_meta['event_cutoff']}
assert len(before_state) == before_meta['review_count'] == 1812
task_events = [r for r in now['events'] if r['id'] > before_meta['event_cutoff'] and r['kind'] == 'asset' and r['item_id'] == fid]
assert len(task_events) == 1
event = task_events[0]
assert event['id'] == 1900 and event['product_id'] == ''
saved = json.loads(event['after_json'])
assert saved['data'] == category['after']['data'] and saved['version'] == 1
assert saved['source_hash'] == p['register_sha256']
assert json.loads(events[1901]['after_json'])['kind'] == 'image' and events[1901]['item_id'] == fid
assert json.loads(events[1903]['after_json'])['kind'] == 'image' and events[1903]['item_id'] == fid
checks['task_category_write_and_owner_choices_separate'] += 6
def get(route):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/' + route, timeout=20))
health, boot = get('health'), get('bootstrap')
assert health['version'] == '2.3.3' and len(boot['products']) == 188 and len(boot['families']) == 58
assert boot['source']['register_sha256'] == p['register_sha256']
product = get('products/BSI-2CA935C1A57A')
image = next(r for r in product['images'] if r['id'] == fid)
assert 'product' in image['types'] and image['original']['dimensions'] == [2048, 1360]
native = read(H / 'native-gold-readback.json')
assert native['file']['id'] == fid and native['file']['metadata_type'] == 'file'
assert native['folder']['has_more'] is False and len(native['folder']['entries']) == 28
native_ids = {r['file_id'] for r in native['folder']['entries']}
app_ids = {r['id'] for r in product['images']}
assert native_ids <= app_ids
assert image['folder_id'] == 'id:cnqzTNngPVsAAAAAAAygGQ'
assert image['provenance']['revision'] == native['file']['rev'] and image['original']['bytes'] == native['file']['size']
checks['native_files_present_in_product_gallery'] += len(native_ids)
protected = previous['protected_source_hashes']
for f, digest in protected.items():
    assert sha(f) == digest, f
    checks['protected_sources_preserved'] += 1
receipt = {'status': 'PASS_INDEPENDENT_COLLAPSIBLE_FAMILY_AND_PRODUCT_TYPE_AUDIT',
    'checked_utc': datetime.now(timezone.utc).isoformat(), 'app_version': '2.3.3',
    'handoff_path': str(D / 'HANDOFF.json'), 'handoff_sha256': sha(D / 'HANDOFF.json'),
    'baseline_pointer_sha256': sha(B / 'current-master.json'), 'all_application_code_hashes': codes,
    'browser_checks': browser, 'gold_leaf_native_files_present': 28, 'gold_leaf_native_missing': 0,
    'gold_leaf_new_upload_visible_as_product': True, 'image_type_task_event': 1900,
    'image_type_change_does_not_import_listing_primary_identity_or_specs': True,
    'owning_thread_review_writes': 1, 'owner_listing_and_primary_events': [1901, 1903],
    'production_review_event_cutoff': max(events), 'production_review_rows_at_snapshot': len(current),
    'checks': dict(checks), 'checks_passed': sum(checks.values()), 'protected_source_hashes': protected,
    'root_review_db_writes': 0, 'root_native_mutations': 0, 'http_methods_used': ['GET'], 'sqlite_mode': 'ro',
    'evidence': {str(D / 'before.json'): sha(D / 'before.json'),
        str(D / 'gold-leaf-category.json'): sha(D / 'gold-leaf-category.json'),
        str(D / q['screenshot']): sha(D / q['screenshot']), str(H / 'native-gold-readback.json'): sha(H / 'native-gold-readback.json')}}
dump(H / 'independent-verification.json', receipt)
print(json.dumps({k: v for k, v in receipt.items() if k not in ['all_application_code_hashes', 'protected_source_hashes', 'evidence']}, indent=2))
