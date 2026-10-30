"""Correct supported display-name omissions through the app's versioned API."""
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
BASE = 'http://127.0.0.1:8767'


def get(path):
    with urlopen(BASE + path, timeout=30) as response:
        return json.load(response)


def snapshot(product):
    return {**{key: product.get(key) for key in ('id', 'name', 'folder_url', 'fields', 'source_hash')},
            'reviews': [r for r in product['reviews'] if r['product_id'] == product['id']]}


def main():
    candidates = json.loads((HERE / 'white-title-candidates.json').read_text())
    inventory = json.loads((RUNTIME / 'dropbox-sync/inventory.json').read_text())
    folders = {r['path'].casefold(): r['id'] for r in inventory['records'].values() if r['kind'] == 'folder'}
    fixes, held = [], []
    for row in candidates:
        material = next(f for f in row['fields'] if f['key'] == 'Material / finish')
        # Require the recorded finish as well as the folder, never a guessed
        # colour inferred from a name or group photograph alone.
        if not re.search(r'\bwhite\b', material['value'], re.I):
            held.append({**row, 'reason': 'White folder, but recorded finish is Bath Stone or pale rather than explicitly White.'})
            continue
        path = unquote(urlparse(row['folder_url']).path).removeprefix('/home')
        assert path.casefold() in folders, ('Current folder missing', path)
        before = snapshot(get('/api/products/' + row['id']))
        assert before['name'] == row['name'], ('Name changed during audit', row['id'])
        name = re.sub(r'\s+(\([^()]+\))$', r' White \1', row['name'])
        if name == row['name']:
            name += ' White'
        review = next((r for r in before['reviews'] if r['kind'] == 'field' and r['item_id'] == 'Name'), None)
        body = {'kind': 'field', 'product_id': row['id'], 'item_id': 'Name',
                'version': review['version'] if review else 0,
                'data': {'decision': 'edit', 'value': name, 'certainty': 'source_claim',
                         'notes': 'Missing White finish added to the display title. Existing identity, aliases, specifications and photo choices are retained.',
                         'evidence': f"Recorded Material / finish: {material['value']}; current Dropbox folder: {row['folder_url']}; inventory generation {inventory['generation']}; source {before['source_hash']}."}}
        fixes.append({'id': row['id'], 'old_name': row['name'], 'name': name,
                      'folder_url': row['folder_url'], 'folder_id': folders[path.casefold()],
                      'material': material['value'], 'before': before, 'request': body})
    assert len(fixes) == 18 and len(held) == 6
    plan = {'checked_at': datetime.now(timezone.utc).isoformat(), 'active_products_audited': 186,
            'inventory_generation': inventory['generation'], 'fixes': fixes, 'held': held}
    (HERE / 'title-correction-plan.json').write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    backup = HERE / 'reviews-before-titles.sqlite3'
    assert not backup.exists(), 'Do not rerun this one-time task against changed review versions.'
    with sqlite3.connect('file:' + str(RUNTIME / 'reviews.sqlite3') + '?mode=ro', uri=True) as source:
        with sqlite3.connect(backup) as target:
            source.backup(target)
    backup.chmod(0o600)
    token = (RUNTIME / 'server-token').read_text().strip()
    for fix in fixes:
        request = Request(BASE + '/api/reviews', data=json.dumps(fix['request']).encode(),
                          headers={'Content-Type': 'application/json', 'X-Review-Token': token}, method='POST')
        with urlopen(request, timeout=30) as response:
            receipt = json.load(response)
        (HERE / (fix['id'] + '-save.json')).write_text(json.dumps(receipt, indent=2))
        after = snapshot(get('/api/products/' + fix['id']))
        assert after['name'] == fix['name']
        fields = lambda p: {f['key']: f for f in p['fields'] if f['key'] != 'Name'}
        assert fields(after) == fields(fix['before']), ('Other fields changed', fix['id'])
        reviews = lambda p: {(r['kind'], r['item_id']): r for r in p['reviews'] if not (r['kind'] == 'field' and r['item_id'] == 'Name')}
        assert reviews(after) == reviews(fix['before']), ('Other choices changed', fix['id'])
        (HERE / (fix['id'] + '-verified.json')).write_text(json.dumps(after, indent=2))
        print('VERIFIED', fix['name'], flush=True)
    result = {'status': 'PASS', 'checked_at': datetime.now(timezone.utc).isoformat(),
              'active_products_audited': 186, 'corrected': [{k: x[k] for k in ('id', 'old_name', 'name', 'folder_url', 'folder_id', 'material')} for x in fixes],
              'held': [{'id': x['id'], 'name': x['name'], 'folder_url': x['folder_url'], 'reason': x['reason'],
                       'material': next(f['value'] for f in x['fields'] if f['key'] == 'Material / finish')} for x in held],
              'non_name_fields_and_reviews_unchanged': True, 'native_file_writes': 0}
    (HERE / 'title-audit-result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
