"""Record live dependencies without changing the app or its cache."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import sqlite3
import sys
import urllib.request

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from catalogue import Catalogue
from dropbox_sync import apply_inventory
from filename_overlay import apply_filename_overlay
from media import MediaCache
from organisation import apply_location
MediaCache.flush = lambda self: None

boot = json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap', timeout=90))
runtime = Path(boot['data_directory'])
cat = Catalogue(ROOT, runtime)
live = boot['source'].get('live_dropbox')
if live:
    inventory = json.loads(Path(live['path']).read_text())
    inventory.update(snapshot_path=live['path'], snapshot_sha256=live['sha256'], checked_utc=live['checked_utc'])
    cat = apply_inventory(cat, inventory, runtime)
apply_filename_overlay(cat, runtime)
with sqlite3.connect('file:' + str(runtime / 'reviews.sqlite3') + '?mode=ro', uri=True) as db:
    cutoff = db.execute('SELECT MAX(id) FROM events').fetchone()[0]
    for (raw,) in db.execute("SELECT result FROM background_jobs WHERE kind='organise' AND state='completed' ORDER BY updated_at"):
        result = json.loads(raw)
        if result.get('checked_utc', '') > (live or {}).get('checked_utc', ''):
            apply_location(cat, result)
    tables = {}
    for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        if name.startswith('sqlite_'):
            continue
        rows = db.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall()
        tables[name] = {'rows': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()}

paths = {str(Path(x[0]).resolve()) for x in cat.paths.values()}
paths.update(str(Path(x).resolve()) for x in cat.preview_paths.values())
pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
paths.update([str(ROOT / 'sculpture-catalogue/current-master.json'), cat.source['register'], cat.source['gallery_database']])
workbook = pointer['current_app_review_workbook']
upload = pointer['current_upload_preparation']
for key in ('path', 'verification', 'dropbox_receipt'):
    if workbook.get(key):
        paths.add(workbook[key])
for key in ('path', 'review_page', 'validation'):
    if upload.get(key):
        paths.add(upload[key])
package = Path(upload['path']).parent
for name in ('boldstone-wall-sculptures-upload-package.zip', 'package-manifest.json', 'all-components-upload-register.csv',
             'selected-image-upload-manifest.csv', 'shopify-new-products-draft.csv', 'shopify-existing-variant-price-updates.csv'):
    paths.add(str(package / name))

def record(path):
    p = Path(path)
    before = p.stat()
    with p.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    after = p.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
    return {'path': path, 'bytes': after.st_size, 'mtime_ns': after.st_mtime_ns, 'sha256': digest}

inside = sorted(x for x in paths if x.startswith(str(ROOT) + '/'))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    records = list(pool.map(record, inside))
(OUT / 'live-protected-before.json').write_text(json.dumps({'event_cutoff': cutoff, 'tables': tables, 'files': records}, indent=2))
print(json.dumps({'protected_files': len(records), 'event_cutoff': cutoff, 'tables': {k:v['rows'] for k,v in tables.items()}}))
