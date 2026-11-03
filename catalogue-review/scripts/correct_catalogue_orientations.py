"""Label three existing measurements using source axes and reviewed photos."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from store import ReviewStore

OUT = Path(sys.argv[1]).resolve()
BASE = 'http://127.0.0.1:8767'
read = lambda route: json.load(urllib.request.urlopen(BASE + route, timeout=120))
write = lambda name, data: (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
before = json.loads((OUT / 'app-before.json').read_text())
current = read('/api/specifications')
products = {p['id']: p for p in current['products']}
old = {p['id']: p for p in before['products']}
assert all(p['fields'] == old[pid]['fields'] and p['listing_fields'] == old[pid]['listing_fields'] for pid, p in products.items())
boot = read('/api/bootstrap')
ReviewStore(boot['data_directory']).backup(OUT / 'reviews-before-orientations.sqlite3')
rows = [
 ('BSI-DB7FBD3E1323', '45 × 40 × 5 cm', 40, 45, 5, 'GS-1-30.30', '01-b42ddca78190c193d68f54e12ac7a88cee24ab94ad34df942c8a61ccb3184402.png'),
 ('BSI-CAB0D722062D', '40 × 45 × 6 cm', 40, 45, 6, 'PF2-40.45', '01-1d99961f32daaa115804cebad2906811aa8bafe746d1dd6bb4af73c28a7bd5e7.png'),
 ('BSI-5819104A663F', '50 × 30 × 7 cm', 30, 50, 7, 'BOLD-5819104A663F', '01-9875194eb81adffea800458a675a8054aedb0f3fee1810436ba3b9195ac8b128.png'),
]
plan, changes, receipts = [], [], []
for pid, source, width, height, depth, sku, filename in rows:
    p = products[pid]
    f = {f['key']: f for f in p['fields'] + p['listing_fields']}
    assert f['Dimensions / depth']['value'] == source and f['Seller SKU']['value'] == sku
    photo = ROOT / 'outputs/catalogue-marketplace-publication-20261101/chairish-current/photos' / sku / filename
    digest = hashlib.sha256(photo.read_bytes()).hexdigest()
    observation = ('Width and height agree with the explicitly labelled centimetre axes in the owner-supplied Chairish spreadsheet. '
                   'Selected product photograph visually reviewed in its shown display orientation. '
                   'Existing measurements retained; no physical size inferred from pixels.')
    evidence = f'Owner request 3 November 2026: add the three missing dimension orientations. {observation} Photo SHA256 {digest}.'
    value = f'{height} cm high × {width} cm wide × {depth} cm deep'
    plan.append({'catalogue_id': pid, 'sku': sku, 'source': source, 'width_cm': width, 'height_cm': height,
                 'depth_cm': depth, 'value': value, 'photo': str(photo), 'photo_sha256': digest,
                 'observation': observation, 'reviewed_utc': datetime.now(timezone.utc).isoformat()})
    for key, new in [('Dimensions / depth', value), ('Description', f['Description']['value'].replace('Dimensions: ' + source, 'Dimensions: ' + value))]:
        field = f[key]
        assert new != field['value']
        data = {'decision': 'edit', 'value': new, 'certainty': 'source_claim',
                'evidence': evidence, 'notes': 'Axis labels added only. Existing numerical dimensions and qualifications retained.'}
        changes.append({'product_id': pid, 'key': key, 'before': field['value'], 'value': new})
        request = urllib.request.Request(BASE + '/api/reviews', method='POST',
            data=json.dumps({'kind': 'field', 'product_id': pid, 'item_id': key, 'version': field['version'], 'data': data}).encode(),
            headers={'Content-Type': 'application/json', 'Origin': BASE, 'X-Review-Token': boot['csrf_token']})
        receipt = json.load(urllib.request.urlopen(request, timeout=120))
        receipts.append({'product_id': pid, 'key': key, 'response': receipt})
        write('orientation-receipts.json', receipts)
write('orientation-review.json', plan)
write('orientation-changes.json', changes)
after = read('/api/specifications')
for p in after['products']:
    prior = old[p['id']]
    assert p['photos'] == prior['photos']
    assert {k:v for k,v in p['costing'].items() if k != 'inputs'} == {k:v for k,v in prior['costing'].items() if k != 'inputs'}
    expected = {f['key']: f['value'] for f in prior['fields'] + prior['listing_fields']}
    expected.update({c['key']: c['value'] for c in changes if c['product_id'] == p['id']})
    assert {f['key']: f['value'] for f in p['fields'] + p['listing_fields']} == expected
write('app-after.json', after)
write('orientation-verification.json', {'status': 'PASS', 'components': len(after['products']), 'orientations_added': 3,
    'field_changes': len(changes), 'prices_costs_photos_and_other_fields_preserved': True})
print((OUT / 'orientation-verification.json').read_text())
