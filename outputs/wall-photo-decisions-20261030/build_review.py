"""Build a standalone URL-only wall photo review; never downloads image bytes."""
from pathlib import Path
from urllib.parse import urlparse, unquote, quote
from hashlib import sha256
from datetime import datetime, timezone
from collections import defaultdict, Counter
import csv
import json

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent / '01a13fe6-495b-7253-b923-31823b4cbca8/squarespace-replacement-20261030'
ROOT = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/'
load = lambda name: json.loads((SOURCE / name).read_text())
audit = load('legacy-dropbox-presence-audit.json')
snapshot = load('catalogue-snapshot.json')
backups = {r['url']: r for r in load('legacy-photo-backup-receipts.json')}
old_products = {r['product_id']: r for r in csv.DictReader((SOURCE / 'old-wall-products-to-remove.csv').open())}
by_image_id, by_url = defaultdict(list), defaultdict(list)
for r in snapshot['images']:
    by_image_id[r['image']['id']].append(r)
    by_url[r['image'].get('url', '')].append(r)

products = [dict(id=r['id'], title=r['name'], family=r['family'],
                 folder_url=r['folder_url'], app_url=r.get('app_url') or 'http://127.0.0.1:8767/#'+r['id'],
                 listing_decision=r.get('listing_decision','')) for r in snapshot['products']]
products.sort(key=lambda r: (r['family'].casefold(), r['title'].casefold()))
records = []
for r in audit['images']:
    if not r['wall_scope']:
        continue
    matches = sorted(r.get('live_matches', []), key=lambda m: (not m['path'].startswith(ROOT), m['path']))
    group = 'wall' if any(m['path'].startswith(ROOT) for m in matches) else 'elsewhere' if matches else 'missing' if r.get('dropbox_ids') else 'unmatched'
    evidence = list(by_url.get(r['url'], []))
    for file_id in set(r.get('dropbox_ids', []) + [m['id'] for m in matches]):
        evidence.extend(by_image_id.get(file_id, []))
    app_associations = {}
    for a in evidence:
        if a['product_id'] not in {p['id'] for p in products}:
            continue
        im = a['image']
        item = app_associations.setdefault(a['product_id'], dict(id=a['product_id'], title=a['product_name'], family=a['product_family'], scopes=[], uses=[], types=[], primary=False))
        item['scopes'] = sorted(set(item['scopes'] + [a.get('scope', '')]))
        item['uses'] = sorted(set(item['uses'] + im.get('selected_uses', []) + a.get('choice', {}).get('uses', [])))
        item['types'] = sorted(set(item['types'] + im.get('effective_types', im.get('types', []))))
        item['primary'] = item['primary'] or bool(im.get('primary_selected'))
    locations = []
    for m in matches:
        folder, filename = m['path'].rsplit('/', 1)
        locations.append(dict(**m, image_url='https://www.dropbox.com/home'+quote(folder)+'?preview='+quote(filename),
                              folder_url='https://www.dropbox.com/home'+quote(folder), in_wall= m['path'].startswith(ROOT)))
    old = []
    for a in r['associations']:
        p = old_products.get(a['product_id'])
        if p:
            old.append(dict(id=a['product_id'], title=a['title'], url=p['url']))
    families = sorted(set(a['family'] for a in app_associations.values()))
    dimensions = None
    if r['url'] in backups:
        b = backups[r['url']]
        dimensions = dict(width=b['width'], height=b['height'], bytes=b['bytes'], label='Squarespace original checked during the earlier audit')
    records.append(dict(id='photo-'+sha256(r['url'].encode()).hexdigest()[:20], url=r['url'],
                        filename=unquote(Path(urlparse(r['url']).path).name), group=group,
                        title=' / '.join(dict.fromkeys(a['title'] for a in old)), old_products=old,
                        locations=locations, historical_dropbox_ids=r.get('dropbox_ids', []),
                        app_associations=sorted(app_associations.values(), key=lambda a:a['title']),
                        families=families, dimensions=dimensions, local_backup_verified=r['url'] in backups))
order = {'missing':0,'unmatched':1,'elsewhere':2,'wall':3}
records.sort(key=lambda r: (order[r['group']], r['title'].casefold(), r['filename'].casefold(), r['id']))
for i,r in enumerate(records,1):
    r['number'] = i
counts = dict(Counter(r['group'] for r in records))
assert len(records) == len({r['url'] for r in records}) == len({r['id'] for r in records}) == 444
assert counts == {'missing':55, 'unmatched':35, 'elsewhere':81, 'wall':273}
data = dict(schema='boldstone-wall-photo-review-v1', created_utc=datetime.now(timezone.utc).isoformat(),
            audit_utc=audit['summary']['checked_utc'], source_event=snapshot['event_cutoff'],
            scope='Old Squarespace wall-sculpture photographs and all recorded Dropbox locations. Unrelated products excluded.',
            records=records, products=products, counts=counts)
safe_json = lambda x: json.dumps(x, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
html = (OUT/'review-template.html').read_text()
html = html.replace('/* EMBED_CSS */', (OUT/'review.css').read_text())
html = html.replace('/* EMBED_MODEL */', (OUT/'review-model.js').read_text())
html = html.replace('/* EMBED_APP */', (OUT/'review-app.js').read_text())
html = html.replace('<!-- EMBED_DATA -->', safe_json(data))
dest = OUT/'wall-sculpture-photo-decisions.htm'
dest.write_text(html)
(OUT/'build-receipt.json').write_text(json.dumps(dict(file=dest.name, records=len(records), counts=counts,
    locations=sum(len(r['locations']) for r in records), components=len(products), image_bytes_downloaded=0,
    html_bytes=dest.stat().st_size, sha256=sha256(dest.read_bytes()).hexdigest(), source_audit_utc=data['audit_utc']),indent=2))
print(json.dumps(dict(file=str(dest), records=len(records), counts=counts, image_bytes_downloaded=0, html_bytes=dest.stat().st_size)))
