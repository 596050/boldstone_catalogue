"""Capture a coherent catalogue/review snapshot for the requested workbook."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import sys
import urllib.request

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from catalogue import Catalogue
from component_photos import component_photos
from dropbox_sync import apply_inventory
from filename_overlay import apply_filename_overlay
from media import MediaCache, TYPES
from organisation import apply_location
from projection import Projection
from specifications import specification_overview
from store import ReviewStore


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=90) as response:
        return json.load(response)


boot = get('/api/bootstrap')
runtime = Path(boot['data_directory'])
snapshot_db = OUT / 'review-snapshot.sqlite3'
with closing(sqlite3.connect('file:' + str(runtime / 'reviews.sqlite3') + '?mode=ro', uri=True)) as source:
    with closing(sqlite3.connect(snapshot_db)) as target:
        source.backup(target)
created = datetime.now(timezone.utc).isoformat()
with closing(sqlite3.connect(snapshot_db)) as db:
    db.row_factory = sqlite3.Row
    reviews = [ReviewStore.unpack(row) for row in db.execute('SELECT * FROM reviews ORDER BY updated_at')]
    cutoff = db.execute('SELECT MAX(id) FROM events').fetchone()[0]
    jobs = [json.loads(r['result']) for r in db.execute("SELECT result FROM background_jobs WHERE kind='organise' AND state='completed' ORDER BY updated_at")]

# Use the app's projection functions, but never persist incidental media-cache changes.
MediaCache.flush = lambda self: None
cat = Catalogue(ROOT, runtime)
for key in ('register_sha256', 'gallery_sha256'):
    assert cat.source[key] == boot['source'][key], 'Publisher changed during capture'
live = boot['source'].get('live_dropbox')
if live:
    raw = Path(live['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == live['sha256']
    inventory = json.loads(raw)
    inventory.update(snapshot_path=live['path'], snapshot_sha256=live['sha256'], checked_utc=live['checked_utc'])
    cat = apply_inventory(cat, inventory, runtime)
apply_filename_overlay(cat, runtime)
for result in jobs:
    if result.get('checked_utc', '') > (live or {}).get('checked_utc', ''):
        apply_location(cat, result)
view = Projection(cat, reviews)
specs = specification_overview(cat, view.reviews)
rows = []
covered = set()
for p in specs['products']:
    pid = p['id']
    photos = component_photos(view, pid, include_removed=True)
    p['photos'] = {k: v for k, v in photos.items() if k not in ('images', 'related_images')}
    p['source_reference_id'] = view.cid(cat.products[pid].get('primary_id'))
    p['source_notes'] = cat.products[pid].get('source_notes', '')
    p['app_url'] = BASE + '/#' + pid
    for scope, items in [('Associated', photos['images']), ('Related candidate', photos['related_images'])]:
        for image in items:
            aid = image['id']
            covered.add(aid)
            if image.get('association', {}).get('tier') == 'removed':
                scope_label = 'Removed association'
            else:
                scope_label = scope
            rows.append({'product_id': pid, 'product_name': p['name'], 'product_family': p['family'],
                         'scope': scope_label, 'image': image,
                         'choice': view.decision('image', pid, aid), 'metadata': view.decision('asset', '', aid)})
    p['associated_count'] = len(photos['images'])
    p['candidate_count'] = sum(a.get('association', {}).get('tier') != 'removed' for a in photos['related_images'])
    p['removed_count'] = sum(a.get('association', {}).get('tier') == 'removed' for a in photos['related_images'])

library = view.library()
for image in library:
    if image['id'] not in covered:
        rows.append({'product_id': '', 'product_name': '', 'product_family': image.get('family', ''),
                     'scope': 'Library only', 'image': image,
                     'choice': view.decision('image', '__library__', image['id']),
                     'metadata': view.decision('asset', '', image['id'])})
assert len(specs['products']) == len(boot['products']) == 181
assert set(p['id'] for p in specs['products']) == set(p['id'] for p in boot['products'])
assert not any(row['image']['id'] in view.deleted for row in rows)
assert len({(row['product_id'], row['image']['id']) for row in rows}) == len(rows)
payload = {'created_utc': created, 'event_cutoff': cutoff, 'source': cat.source,
           'products': specs['products'], 'images': rows, 'image_types': TYPES,
           'summary': {**specs['totals'], 'families': len(specs['families']),
                       'image_rows': len(rows), 'unique_images': len(library),
                       'associated_image_rows': sum(r['scope'] == 'Associated' for r in rows),
                       'related_candidate_rows': sum(r['scope'] == 'Related candidate' for r in rows),
                       'library_only_rows': sum(r['scope'] == 'Library only' for r in rows)}}
(OUT / 'catalogue-snapshot.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
after = get('/api/bootstrap')
assert after['source']['register_sha256'] == cat.source['register_sha256']
print(json.dumps({'created_utc': created, 'event_cutoff': cutoff, **payload['summary']}, indent=2))
