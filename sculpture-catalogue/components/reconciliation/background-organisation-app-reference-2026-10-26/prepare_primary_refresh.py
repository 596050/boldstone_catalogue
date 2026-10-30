"""Read current primary choices and receipts, without changing any live state."""
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import quote
import hashlib
import json
import sqlite3
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
OUT = HERE / 'anchor-review'
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text())


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767' + path, timeout=30) as response:
        return json.load(response)


def link(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(path, safe='/')


pointer_path = BASE / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = read(pointer_path)
register = read(BASE / pointer['register'])
assert sha(BASE / pointer['register']) == pointer['register_sha256']
bootstrap = get('/api/bootstrap')
assert bootstrap['source']['register_sha256'] == pointer['register_sha256']
native_path = Path(bootstrap['source']['live_dropbox']['path'])
assert sha(native_path) == bootstrap['source']['live_dropbox']['sha256']
native = read(native_path)['records']
folders = {row['path']: row for row in native.values() if row['kind'] == 'folder'}
database = Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3'
connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
connection.row_factory = sqlite3.Row
try:
    connection.execute('BEGIN')
    event_cutoff = connection.execute('SELECT MAX(id) FROM events').fetchone()[0]
    saved = [dict(row) for row in connection.execute('SELECT * FROM reviews')]
    events = [dict(row) for row in connection.execute('SELECT id,after_json FROM events ORDER BY id')]
finally:
    connection.close()
for row in saved:
    row['data'] = json.loads(row['data'])
deletions = {row['item_id']: row for row in saved if row['kind'] == 'deletion'}
image_reviews = [row for row in saved if row['kind'] == 'image']
audit = []
queued = []
preview_names = {
    'BSI-C02D6DF365D3': 'acanthus-flower-approved.image',
    'BSI-A76B86DA7928': 'barbados-wave-approved.image',
    'BSI-A1EB68571F0F': 'brancusi1-gold-approved.image',
}

for option in register['options']:
    pid = option['product_id']
    if pid not in register['active_option_ids']:
        continue
    fid = option.get('file_id', '')
    receipt = deletions.get(fid, {}).get('data', {})
    deleted = receipt.get('state') == 'deleted' and receipt.get('result', {}).get('verified_absent') is True
    if not fid:
        state = 'no_exact_file_binding'
    elif fid in native:
        assert not deleted
        state = 'selected_primary_present_in_wall_snapshot'
    elif deleted:
        state = 'selected_primary_has_recorded_verified_deletion'
    else:
        state = 'selected_primary_outside_or_absent_from_wall_snapshot'
    row = {'product_id': pid, 'name': option['name'], 'retained_source_file_id': fid, 'state': state}
    audit.append(row)
    if not deleted:
        continue
    candidates = [r for r in image_reviews if r['product_id'] == pid
                  and r['data'].get('primary') is True
                  and r['data'].get('decision') == 'reviewed'
                  and 'listing' in r['data'].get('uses', [])
                  and r['item_id'] in native]
    assert len(candidates) == 1, (option['name'], 'Requires exact primary choice readback')
    choice = candidates[0]
    assert choice['source_hash'] == pointer['register_sha256']
    chosen_id = choice['item_id']
    detail = get('/api/products/' + pid)
    assert any(a['id'] == chosen_id and pid in a.get('component_ids', []) for a in detail['images'])
    api_choice = next(r for r in detail['reviews'] if r['kind'] == 'image' and r['item_id'] == chosen_id)
    assert api_choice['version'] == choice['version'] and api_choice['data'] == choice['data']
    current = native[chosen_id]
    parent = folders[str(PurePosixPath(current['path']).parent)]
    assert current['folder_id'] == parent['id']
    matching_events = [e for e in events
                       if json.loads(e['after_json']).get('kind') == 'image'
                       and json.loads(e['after_json']).get('product_id') == pid
                       and json.loads(e['after_json']).get('item_id') == chosen_id]
    assert matching_events
    selected_event = matching_events[-1]
    after = json.loads(selected_event['after_json'])
    if isinstance(after.get('data'), str):
        after['data'] = json.loads(after['data'])
    assert after['version'] == choice['version'] and after['data'] == choice['data']
    cached = OUT / 'previews' / preview_names[pid]
    blocks = hashlib.sha256()
    with cached.open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            blocks.update(hashlib.sha256(block).digest())
    queued.append({
        'product_id': pid, 'name': option['name'],
        'status': 'RECORDED_APP_PRIMARY_CHOICE_QUEUED_FINAL_NATIVE_PATH_READBACK',
        'historical_source_file_id_preserved': fid,
        'deletion_receipt': {'review_version': deletions[fid]['version'],
                            'operation_id': receipt.get('operation_id'),
                            'result': receipt['result']},
        'proposed_current_file_id': chosen_id,
        'proposed_current_folder_id': parent['id'],
        'observed_file_path': current['path'],
        'observed_image_url': link(current['path']),
        'observed_folder_url': link(parent['path'], folder=True),
        'native_content_hash': current['content_hash'],
        'native_bytes': current['bytes'],
        'review_version': choice['version'], 'review_updated_at': choice['updated_at'],
        'review_data': choice['data'],
        'review_source_hash': choice['source_hash'],
        'approval_event_id': selected_event['id'],
        'cached_visual_preview': str(cached.resolve()), 'cached_visual_preview_sha256': sha(cached),
        'cached_bytes_equal_native_original': blocks.hexdigest() == current['content_hash'],
        'mapping_basis': 'Exact saved product-specific Primary and Listing choices; surviving file ID and containing-folder ID checked.',
        'no_new_owner_identity_or_physical_specification_claim': True,
        'canonical_or_app_changes_applied': False,
    })

counts = dict(Counter(row['state'] for row in audit))
assert len(audit) == 187 and len(queued) == 3
assert counts == {'selected_primary_present_in_wall_snapshot': 182,
                  'selected_primary_has_recorded_verified_deletion': 3,
                  'selected_primary_outside_or_absent_from_wall_snapshot': 1,
                  'no_exact_file_binding': 1}
assert sha(pointer_path) == pointer_sha
report = {
    'status': 'READ_ONLY_ALL_187_PRIMARY_REFERENCES_AND_THREE_RECORDED_REPLACEMENTS',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'canonical_pointer_sha256': pointer_sha,
    'register_sha256': pointer['register_sha256'],
    'inventory': str(native_path), 'inventory_sha256': sha(native_path),
    'inventory_checked_utc': bootstrap['source']['live_dropbox']['checked_utc'],
    'review_event_cutoff': event_cutoff,
    'counts': counts, 'options': audit, 'queued_updates': queued,
    'final_native_filename_readback_required': True,
    'root_native_app_review_and_canonical_writes': 0,
}
(OUT / 'primary-reference-refresh.json').write_text(json.dumps(report, indent=2) + '\n')
cards = []
for row in queued:
    cards.append('<article><h2>' + escape(row['name']) + '</h2><p>The old primary has a recorded verified deletion. A surviving replacement is already marked Primary and Listing in the review app.</p><p><a href="' + escape(row['observed_image_url'], quote=True) + '">Selected replacement image</a> · <a href="' + escape(row['observed_folder_url'], quote=True) + '">Actual containing folder</a></p><p><small>File ID: ' + escape(row['proposed_current_file_id']) + '<br>Folder ID: ' + escape(row['proposed_current_folder_id']) + '<br>Selection event: ' + str(row['approval_event_id']) + '</small></p></article>')
html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Recorded primary photograph replacements</title><style>body{max-width:920px;margin:36px auto;padding:0 22px;font:17px/1.5 system-ui;color:#202725}article{border-top:1px solid #ced6d1;padding:18px 0}h1{font-size:30px}h2{font-size:22px}a{color:#14583f}small{overflow-wrap:anywhere}</style><body><h1>Recorded primary photograph replacements</h1><p>All 187 active catalogue primary references checked: 182 present in the current Wall snapshot; 3 with verified deletion receipts and recorded replacement choices; 1 archive reference outside the Wall snapshot; 1 historical option without an exact file binding.</p><p>These exact saved choices are queued for the master link refresh after final native filename verification. Deletion decisions, historical source evidence and physical specification qualifications remain preserved.</p><p>Snapshot: ' + escape(report['inventory_checked_utc']) + '. Stable IDs are retained while filenames change.</p>' + ''.join(cards) + '<p><a href="folder-anchor-review.html">Folder mapping review and Cup Ring match</a></p></body></html>'
(OUT / 'primary-reference-refresh.html').write_text(html)
print(json.dumps({'status': report['status'], 'counts': counts,
                  'queued_updates': [{'name': row['name'], 'file_id': row['proposed_current_file_id'], 'event_id': row['approval_event_id']} for row in queued]}, indent=2))
