#!/usr/bin/env python3
"""Read back the active publication and review app after duplicate retirement."""
from pathlib import Path
import hashlib
import json
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
BASE = 'http://127.0.0.1:8767'
OLD = 'BSI-E7CDC2CFAC9D'
KEEP = 'BSI-93ADE7C4103D'

def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=30))

pointer = json.loads((PROJECT/'sculpture-catalogue/current-master.json').read_text())
register_path = PROJECT/'sculpture-catalogue'/pointer['register']
register_bytes = register_path.read_bytes()
register = json.loads(register_bytes)
assert hashlib.sha256(register_bytes).hexdigest() == pointer['register_sha256']
if OLD in register['active_option_ids']:
    print(json.dumps({'state': 'waiting_for_publication'}))
    raise SystemExit(2)
assert OLD in register['retired_option_ids'] and KEEP in register['active_option_ids']
boot = get('/api/bootstrap')
assert OLD not in {p['id'] for p in boot['products']}
assert len([p for p in boot['products'] if p['id'] == KEEP]) == 1
assert len(boot['products']) == len(register['active_option_ids'])
try:
    get('/api/products/' + OLD)
except urllib.error.HTTPError as exc:
    assert exc.code == 404
    retired_response = json.load(exc)
    assert 'removed from the active catalogue' in retired_response['error']
else:
    raise AssertionError('The retired product still opens as an active product')
keeper = get('/api/products/' + KEEP)
assert keeper['name'] == 'Acanthus Two Leaves White'
before = json.loads((HERE/(KEEP+'-pre-consolidation.json')).read_text())
reviews_before = {(r['kind'], r['item_id']): r['data'] for r in before['reviews']}
reviews_after = {(r['kind'], r['item_id']): r['data'] for r in keeper['reviews']}
assert all(reviews_after[k] == value for k, value in reviews_before.items())
photo = get('/api/component-overview/' + KEEP)
assert photo['primary_listing']['status'] == 'set'
assert photo['primary_id'] == 'id:cnqzTNngPVsAAAAAAAufMQ'
assert 'id:cnqzTNngPVsAAAAAAAyj8Q' in photo['listing_ids']
assert 'advertising' in reviews_after[('image', 'id:cnqzTNngPVsAAAAAAAyj8Q')]['uses']
associated = {a['id'] for a in photo['images']}
assert 'id:cnqzTNngPVsAAAAAAAyluQ' in associated
assert 'id:cnqzTNngPVsAAAAAAAyluQ' in photo['in_situ_ids']
assert 'id:cnqzTNngPVsAAAAAAAyluA' not in associated
assert keeper['source_hash'] == pointer['register_sha256']
receipt = {'status': 'PASS', 'active_products': len(boot['products']),
    'register': str(register_path), 'register_sha256': pointer['register_sha256'],
    'retired_product': OLD, 'keeper': KEEP, 'name': keeper['name'],
    'old_link_response': retired_response, 'primary_id': photo['primary_id'],
    'listing_ids': photo['listing_ids'], 'in_situ_ids': photo['in_situ_ids'],
    'existing_keeper_reviews_unchanged': True, 'shared_context_preserved': True,
    'missing_image_not_resurrected': True}
(HERE/'consolidation-app-verification.json').write_text(json.dumps(receipt, indent=2))
(HERE/'component-overview-final.json').write_text(json.dumps(photo, indent=2))
print(json.dumps(receipt))
