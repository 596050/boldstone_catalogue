"""Freeze the current thirteen missing, qualified uploads without changing the app."""
import hashlib
import importlib.util
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from delete_dropbox import connection

pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
saved = json.loads((OUT.parent / 'resume-0600/workbook/app-specifications.json').read_text())
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications', timeout=120) as response:
    live = json.load(response)
relevant = lambda app: {p['id']:{k:p[k] for k in ['fields','listing_fields','costing','photos','listing_decision']} for p in app['products']}
assert relevant(saved) == relevant(live), 'App records changed; reconcile before publishing'
book = Path(pointer['path']).read_bytes()
assert hashlib.sha256(book).hexdigest() == pointer['sha256']
audit = json.loads((OUT / 'saatchi-fresh-whole-portfolio.json').read_text())
assert audit['total_native_artworks'] == audit['published'] == 126
spec = importlib.util.spec_from_file_location('saatchi', ROOT / 'catalogue-review/scripts/prepare_saatchi_catalogue.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
bindings = module.native_artwork_bindings(ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
queue = json.loads((OUT.parent / 'resume-0600/remaining-native-ready-queue.json').read_text())
assert len(queue) == 13 and len(bindings) == 126
(OUT / 'packets').mkdir(exist_ok=True)
metadata = {}
prepared = []
with connection(ROOT) as (db, _):
    for item in queue:
        packet = item['packet']
        assert packet['sku'] not in bindings and not packet.get('native_artwork_id')
        photo = packet['photo']
        assert photo['width'] >= 1500 and photo['height'] >= 1200
        assert hashlib.sha256(Path(photo['native_upload_path']).read_bytes()).hexdigest() == photo['native_upload_sha256']
        if photo['image_id'] not in metadata:
            native = db.files_get_metadata(photo['image_id'])
            assert native.id == photo['image_id'] and native.rev == photo['revision']
            assert native.content_hash == photo['content_hash'] and native.size == photo['bytes']
            metadata[native.id] = dict(id=native.id, rev=native.rev, content_hash=native.content_hash,
                                       size=native.size, path_display=native.path_display)
        assert packet['description_characters'] == len(packet['description']) <= 1000
        assert packet['quantity_per_sale'] == 1 and packet['edition_cap'] == 50
        assert 'gypsum-based material' in packet['description'] and 'Sally Price' in packet['description']
        packet.update(current_source_workbook_sha256=pointer['sha256'],
                      whole_native_portfolio_audit=str(OUT / 'saatchi-fresh-whole-portfolio.json'),
                      current_preflight_utc=datetime.now(timezone.utc).isoformat())
        path = OUT / 'packets' / f'{packet["catalogue_id"]}.json'
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
        prepared.append(dict(sku=packet['sku'], title=packet['title'], packet_path=str(path)))
(OUT / 'remaining-preflight.json').write_text(json.dumps(dict(status='PASS', prepared=prepared,
             native_original_metadata=list(metadata.values()), current_workbook_sha256=pointer['sha256'],
             app_records_unchanged=True, native_create_calls=0), indent=2) + '\n')
print(json.dumps(dict(status='PASS_CURRENT_APP_AND_ORIGINALS', missing_ready=len(prepared),
                      unique_originals=len(metadata), existing_native_artworks=len(bindings))))
