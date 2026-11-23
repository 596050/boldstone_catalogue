"""Read a coherent current catalogue snapshot without starting background jobs."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from catalogue import Catalogue
from component_photos import component_photos
from dropbox_sync import apply_inventory, read_inventory
from filename_overlay import apply_filename_overlay
from media import MediaCache
from organisation import apply_location
from projection import Projection
from review_coverage import coverage
from specifications import specification_overview
from store import ReviewStore
from channel_content import values, finish_retail_name, has_surface_effect

IDS = []
MediaCache.flush = lambda self: None
cat = Catalogue(ROOT, RUNTIME)
inventory = read_inventory(RUNTIME / 'dropbox-sync/inventory.json')
cat = apply_inventory(cat, inventory, RUNTIME)
apply_filename_overlay(cat, RUNTIME, inventory['checked_utc'])
with closing(sqlite3.connect((RUNTIME / 'reviews.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
    db.row_factory = sqlite3.Row
    db.execute('BEGIN')
    reviews = [ReviewStore.unpack(r) for r in db.execute('SELECT * FROM reviews ORDER BY updated_at')]
    cutoff = db.execute('SELECT MAX(id) FROM events').fetchone()[0]
    jobs = [json.loads(r['result']) for r in db.execute(
        "SELECT result FROM background_jobs WHERE kind='organise' AND state='completed' ORDER BY updated_at")]
for job in jobs:
    if job.get('checked_utc', '') > inventory['checked_utc']:
        apply_location(cat, job)
view = Projection(cat, reviews)
specs = specification_overview(cat, view.reviews)
covered = coverage(view)
products = {p['id']: p for p in specs['products']}
chosen = []
for pid, product in products.items():
    fields = values(product)
    title = finish_retail_name(product)
    cover = covered['products'].get(pid, {})
    primary = cover.get('primary_listing') or {}
    if not title.endswith(' - White') or not primary.get('image_id'):
        continue
    photos = component_photos(view, pid, include_removed=True)
    image = next((i for i in photos['images'] if i['id'] == primary['image_id']), None)
    if not image or not image.get('primary_eligible') or image.get('withheld_reasons'):
        continue
    chosen.append({'catalogue_id': pid, 'title': title, 'sku': fields['Seller SKU'],
                   'fields': fields, 'surface_effect': has_surface_effect(product),
                   'price_gbp': product['costing']['pricing']['marked_up_price'],
                   'product': product, 'coverage': cover, 'photo': image})
payload = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'event_cutoff': cutoff,
           'inventory_checked_utc': inventory['checked_utc'], 'source': cat.source, 'products': chosen}
(OUT/'candidate-snapshot.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
(OUT/'specifications.json').write_text(json.dumps(specs,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'eligible_white_candidates':len(chosen),'event_cutoff':cutoff,'inventory_checked_utc':inventory['checked_utc']}))
