"""Read-only app capture; export/regression work runs on a detached SQLite copy."""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import sqlite3
import sys
import urllib.request

OUT = Path(__file__).resolve().parent
APP = OUT.parent.parent
PROJECT = APP.parent
sys.path.insert(0, str(APP))
from catalogue import Catalogue
from component_photos import component_photos
from dropbox_sync import apply_inventory
from exports import create_export, field_review_matches_source, image_review_matches_source
from filename_overlay import apply_filename_overlay
from media import MediaCache
from organisation import apply_location
from presentation import listing_value
from projection import Projection
from review_coverage import coverage
from store import ReviewStore


def read(endpoint):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/' + endpoint, timeout=45))


boot = read('bootstrap')
runtime = Path(boot['data_directory'])
MediaCache.flush = lambda self: None
cat = Catalogue(PROJECT, runtime)
assert cat.source['register_sha256'] == boot['source']['register_sha256']
live = boot['source'].get('live_dropbox')
if live:
    raw = Path(live['path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == live['sha256']
    state = json.loads(raw)
    state.update(snapshot_path=live['path'], snapshot_sha256=live['sha256'], checked_utc=live['checked_utc'])
    cat = apply_inventory(cat, state, runtime)
apply_filename_overlay(cat, runtime)
store = ReviewStore(OUT / 'isolated-runtime')
with closing(sqlite3.connect('file:' + str(runtime / 'reviews.sqlite3') + '?mode=ro', uri=True)) as source:
    with closing(sqlite3.connect(store.path)) as target:
        source.backup(target)
with store.connect() as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    jobs = [json.loads(r['result']) for r in db.execute(
        "SELECT result FROM background_jobs WHERE kind='organise' AND state='completed' ORDER BY updated_at")]
for result in jobs:
    if result.get('checked_utc', '') > (live or {}).get('checked_utc', ''):
        apply_location(cat, result)
snapshot = store.snapshot()
view = Projection(cat, snapshot['reviews'])
report = {'captured_utc': datetime.now(timezone.utc).isoformat(),
          'source': cat.source, 'event_cutoff': snapshot['event_cutoff'], 'checks': {}, 'metrics': {}}
checks = report['checks']
checks['source_unchanged_during_capture'] = read('bootstrap')['source']['register_sha256'] == cat.source['register_sha256']
checks['active_products_exactly_match_app'] = set(cat.products) == {p['id'] for p in boot['products']}
checks['retired_products_not_active'] = not set(cat.products).intersection(cat.retired_product_ids)
checks['frozen_fish_has_three_finish_products'] = sum(p['family'] == 'Frozen Fish' for p in cat.products.values()) == 3
checks['lava_moon_has_only_three_white_products'] = sorted(p['name'] for p in boot['products'] if p['family'] == 'Lava Moon') == [
    'Lava Moon 1 - White', 'Lava Moon 2 - White', 'Lava Moon 3 - White']
library = view.library()
library_ids = {a['id'] for a in library}
checks['library_contains_no_deleted_or_unavailable_files'] = not library_ids.intersection(view.deleted)
checks['exact_byte_groups_display_once'] = all(view.cid(a['id']) == a['id'] for a in library)
checks['all_retained_associations_resolve'] = all(aid in library_ids for pid in cat.products for aid in view.edges[pid])
checks['context_folders_do_not_auto_assign_components'] = all(
    not view.asset(aid)['default_component_ids'] and all(
        view.edges[pid][aid].get('tier') == 'manual' for pid in view.product_ids[aid])
    for aid in library_ids if view.library_only_default(aid))
cov = coverage(view, include_photos=True)
photo_problems = []
field_problems = []
old_field_reviews_preserved = 0
old_image_reviews_preserved = 0
primary_states = Counter()
for pid, product in cat.products.items():
    photos = component_photos(view, pid)
    observed = cov['products'][pid]
    primary_states[photos['primary_listing']['status']] += 1
    if (observed['primary_listing'] != photos['primary_listing'] or
            observed['listing']['image_ids'] != photos['listing_ids'] or
            observed['photos']['listing']['count'] != len(photos['listing_ids']) or
            len(photos['listing_ids']) != len(set(photos['listing_ids'])) or
            photos['primary_id'] and photos['listing_ids'][0] != photos['primary_id']):
        photo_problems.append(pid)
    for field in product['fields']:
        review = view.record('field', pid, field['key'])
        text = listing_value(field, review['data']) or ''
        if '—' in text:
            field_problems.append([pid, field['key'], 'em_dash'])
        if field['section'] != 'Listing copy' and not text.strip():
            field_problems.append([pid, field['key'], 'empty'])
        if review.get('version') and review.get('source_hash') != cat.source['register_sha256']:
            old_field_reviews_preserved += field_review_matches_source(review, field, cat.source['register_sha256'])
    for aid in photos['listing_ids']:
        review = view.record('image', pid, aid)
        if review.get('source_hash') != cat.source['register_sha256']:
            old_image_reviews_preserved += image_review_matches_source(view, pid, aid)
checks['photo_coverage_and_primary_selection_agree_for_all_products'] = not photo_problems
checks['specification_values_complete_and_without_em_dashes'] = not field_problems
report['photo_problems'] = photo_problems
report['field_problems'] = field_problems

# Export only the detached review snapshot; never submit a live export or write to Dropbox.
current = create_export(cat, store)
with (Path(current['path']) / 'all-product-decisions.csv').open(encoding='utf-8-sig') as stream:
    current_rows = list(csv.DictReader(stream))
checks['export_contains_every_active_product_once'] = len(current_rows) == len(cat.products) and {r['product_id'] for r in current_rows} == set(cat.products)
checks['exports_do_not_change_saved_reviews_or_audit_events'] = store.snapshot() == snapshot
report['metrics'] = {'active_products': len(cat.products), 'families': len(cov['families']),
    'retained_library_images': len(library), 'saved_review_rows': len(snapshot['reviews']),
    'primary_states': dict(primary_states), 'unchanged_field_reviews_proven_across_publication': old_field_reviews_preserved,
    'unchanged_listing_image_reviews_proven_across_publication': old_image_reviews_preserved,
    'current_listing_ready': current['listing_ready']}
report['status'] = 'PASS' if all(checks.values()) else 'FAIL'
(OUT / 'snapshot-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({'status': report['status'], 'checks': checks, 'metrics': report['metrics'],
                  'photo_problems': photo_problems, 'field_problems': field_problems}, indent=2))
assert all(checks.values()), 'Inspect snapshot-audit.json'
