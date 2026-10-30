"""Prepare seven newer receipt deltas without changing app or master controls."""
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timezone
import hashlib
import html
import json
import sqlite3

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
pointer = B / 'current-master.json'
before = sha(pointer)
assert before == '9a54e024644dc45f22cd69ba7118cee765987a1c5a2c48bb8948be3ee729b726'
p = read(pointer)
previous = read(B / p['current_native_availability']['path'])
known = {r['file_id'] for r in previous['rows']}
assets = read(B / p['current_asset_reference_map']['path'])
native = read(B / p['current_native_reference_map']['path'])['current_objects']
g = read(B / p['register'])
active = [o for o in g['options'] if o['product_id'] in g['active_option_ids']]
database = Path.home() / 'Library/Application Support/BoldstoneReview/reviews.sqlite3'
c = sqlite3.connect('file:' + quote(str(database)) + '?mode=ro', uri=True)
c.row_factory = sqlite3.Row
c.execute('BEGIN')
cutoff = c.execute('SELECT MAX(id) FROM events').fetchone()[0]
counts = {t: c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in ['reviews', 'events', 'deletion_jobs', 'deletion_batches']}
last_native = c.execute("SELECT MAX(id) FROM events WHERE kind='deletion'").fetchone()[0]
jobs = [dict(r) for r in c.execute('SELECT * FROM deletion_jobs ORDER BY created_at')]
assert counts == {'reviews': 1799, 'events': 1852, 'deletion_jobs': 13, 'deletion_batches': 6}
assert cutoff == 1852 and last_native == 1846
rows = []
for job in jobs:
    fid = job['file_id']
    if fid in known:
        continue
    payload, result = json.loads(job['payload']), json.loads(job['result'])
    file = payload['file']
    assert job['state'] == result['state'] == 'deleted'
    assert result['verified_absent'] is True and result['delete_response_confirmed'] is True
    assert result['confirmed_file_id'] == fid == file['id']
    assert file['path'].startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/')
    assert native[fid]['current_wall_snapshot_present'] is True
    source = assets[fid]
    impacts = []
    for o in active:
        roles = [key for key in ['file_id', 'context_file_id'] if o.get(key) == fid]
        if o.get('owner_confirmed_design_reference', {}).get('file_id') == fid:
            roles.append('owner_confirmed_design_reference')
        if roles:
            impacts.append({'product_id': o['product_id'], 'name': o['name'], 'roles': roles})
    rows.append({'file_id': fid, 'name': file['name'], 'state': 'APP_RECEIPT_CONFIRMED_DELETED',
        'job_id': job['id'], 'created_at': job['created_at'], 'batch_id': payload.get('batch_id'),
        'revision_at_deletion': file['revision'], 'content_hash_at_deletion': file['content_hash'],
        'bytes_at_deletion': file['bytes'], 'path_at_deletion': file['path'],
        'source_snapshot_image_url': source['image_url'], 'source_snapshot_folder_url': source['folder_url'],
        'source_snapshot_folder_id': source['folder_id'],
        'confirmation_at': result['confirmation_at'], 'app_native_readback_utc': result['checked_utc'],
        'app_verified_absent': True, 'delete_response_confirmed': True,
        'source_master_reference_impacts': impacts,
        'independent_new_native_readback': 'PENDING_LIVE_INVENTORY_HANDOFF',
        'raw_job_record_sha256': hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()})
c.rollback()
c.close()
assert len(rows) == 7
assert sha(pointer) == before
packet = {'status': 'QUEUED_RECEIPT_DELTA_NOT_PUBLISHED', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'baseline_pointer_sha256': before, 'register_sha256': p['register_sha256'],
    'review_snapshot_event_cutoff': cutoff, 'last_native_audit_event': last_native,
    'latest_saved_review_counts': counts, 'published_native_deletion_count': len(known),
    'confirmed_deleted_jobs_in_this_snapshot': len(jobs), 'newer_receipts': rows,
    'newer_receipt_count': len(rows),
    'scope': 'Sanitized extraction of exact newer app deletion receipts. Fresh native inventory and folder readback remain with the app session. No new live file total, primary, identity or specification is inferred.',
    'canonical_app_native_or_platform_writes': 0}
dump(H / 'queued-receipt-delta.json', packet)
esc = lambda s: html.escape(str(s), quote=True)
body = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Seven queued native deletion receipts</title><style>body{font:17px/1.5 Arial;max-width:1050px;margin:40px auto;padding:0 20px}article{border:1px solid #ccc;padding:20px;margin:20px 0;overflow-wrap:anywhere}</style><h1>Seven queued native deletion receipts</h1><p>App receipts confirm native deletion. This packet is not yet imported into the published master; fresh live inventory validation is pending. Original source IDs and links are retained as history. Image links below are historical.</p>'
for r in rows:
    impacts = '; '.join(x['name'] + ': ' + ', '.join(x['roles']) for x in r['source_master_reference_impacts']) or 'No selected master example/context reference affected'
    body += '<article><h2>' + esc(r['name']) + '</h2><p>' + esc(r['file_id']) + '</p><p><a href="' + esc(r['source_snapshot_folder_url']) + '">Recorded containing folder</a> · <a href="' + esc(r['source_snapshot_image_url']) + '">Historical deleted image link</a></p><p>' + esc(impacts) + '</p><p>App native absence readback: ' + esc(r['app_native_readback_utc']) + '</p></article>'
(H / 'index.html').write_text(body + '</html>')
print(json.dumps({'status': packet['status'], 'newer_receipts': len(rows), 'review_cutoff': cutoff,
    'last_native_event': last_native, 'selected_reference_impacts': sum(len(r['source_master_reference_impacts']) for r in rows),
    'pointer_unchanged': sha(pointer) == before, 'native_calls': 0, 'app_writes': 0}, indent=2))
