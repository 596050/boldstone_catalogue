"""Apply owner-requested finish labels through versioned local review writes."""
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from channel_content import finish_retail_name, has_surface_effect, marketplace_title
from store import ReviewStore

BASE = 'http://127.0.0.1:8767'
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
read = lambda path: json.load(urllib.request.urlopen(BASE + path, timeout=120))
write = lambda name, data: (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
before = read('/api/specifications')
boot = read('/api/bootstrap')
assert boot['source']['register_sha256'] == before['source_hash']
write('finish-titles-before.json', before)
ReviewStore(boot['data_directory']).backup(OUT / 'reviews-before-finish-titles.sqlite3')
changes = []
for product in before['products']:
    if not has_surface_effect(product):
        continue
    fields = {f['key']: f for f in product['fields'] + product['listing_fields']}
    old_name = fields['Retail name']['value'] or product['name']
    new_name = finish_retail_name(product)
    description = fields['Description']['value']
    # Change the model label only. Preserve design prose and all specifications.
    description = description.replace('Model: ' + old_name + ' (', 'Model: ' + new_name + ' (')
    updates = {'Retail name': new_name, 'Marketplace title': marketplace_title(product),
               'Description': description}
    for key, value in updates.items():
        field = fields[key]
        if field['value'] == value:
            continue
        changes.append({'product_id': product['id'], 'key': key,
                        'before': field['value'], 'value': value, 'version': field['version'],
                        'field': field})
write('finish-title-plan.json', changes)
receipts = []
for change in changes:
    field = change['field']
    data = {k: field.get(k, '') for k in ('notes', 'evidence', 'certainty')}
    data.update(decision='edit', value=change['value'], certainty='confirmed',
                evidence=(data['evidence'] + '\nOwner instruction 3 November 2026: '
                          'surface-effect titles must explicitly identify the effect as a Finish.').strip())
    body = {'kind': 'field', 'product_id': change['product_id'], 'item_id': change['key'],
            'version': change['version'], 'data': data}
    request = urllib.request.Request(BASE + '/api/reviews', data=json.dumps(body).encode(),
                headers={'Content-Type': 'application/json', 'Origin': BASE,
                         'X-Review-Token': boot['csrf_token']}, method='POST')
    with urllib.request.urlopen(request, timeout=120) as response:
        receipt = json.load(response)
    receipts.append({'product_id': change['product_id'], 'key': change['key'],
                     'response': receipt})
    write('finish-title-receipts.json', receipts)
after = read('/api/specifications')
write('app-after.json', after)
old = {p['id']: p for p in before['products']}
for product in after['products']:
    previous = old[product['id']]
    assert product['photos'] == previous['photos']
    assert product['costing'] == previous['costing']
    fields = {f['key']: f for f in product['fields'] + product['listing_fields']}
    prior = {f['key']: f for f in previous['fields'] + previous['listing_fields']}
    for key, field in fields.items():
        planned = next((c for c in changes if c['product_id'] == product['id'] and c['key'] == key), None)
        assert field['value'] == (planned['value'] if planned else prior[key]['value'])
    if has_surface_effect(product):
        assert 'finish' in fields['Retail name']['value'].lower()
        assert 'finish' in fields['Marketplace title']['value'].lower()
write('finish-title-verification.json', {'status': 'PASS', 'components': len(after['products']),
    'surface_effect_components': sum(has_surface_effect(p) for p in after['products']),
    'changed_components': len({c['product_id'] for c in changes}), 'changed_fields': len(changes),
    'photos_costs_and_other_fields_preserved': True})
print((OUT / 'finish-title-verification.json').read_text())
