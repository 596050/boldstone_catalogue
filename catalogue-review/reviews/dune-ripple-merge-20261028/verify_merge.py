"""Read-only acceptance checks for the owner-requested Dune Ripple merge."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request

OUT = Path(__file__).resolve().parent
PROJECT = OUT.parents[2]
BASE = PROJECT / 'sculpture-catalogue'
OLD = 'BSI-4536FDCA0DA9'
KEEP = 'BSI-9299D69FEF08'


def get(endpoint):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/' + endpoint, timeout=30))


def read(path):
    return json.loads(path.read_text())


before_pointer = read(OUT / 'master-before.json')
pointer = read(BASE / 'current-master.json')
register_path = BASE / pointer['register']
raw = register_path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == pointer['register_sha256']
register = json.loads(raw)
if OLD in register['active_option_ids']:
    print(json.dumps({'state': 'waiting_for_publication'}))
    raise SystemExit(2)
assert KEEP in register['active_option_ids']
assert OLD in register['retired_option_ids']
before_register = read(BASE / before_pointer['register'])
options = {p['product_id']: p for p in register['options']}
before_options = {p['product_id']: p for p in before_register['options']}
assert set(register['active_option_ids']) == set(before_register['active_option_ids']) - {OLD}
unrelated_changed = [pid for pid in before_options if pid not in (OLD, KEEP) and options.get(pid) != before_options[pid]]
assert not unrelated_changed, unrelated_changed
survivor = options[KEEP]
assert before_options[OLD]['name'] in survivor['retained_names']
for field in ('source_scopes', 'related_platform_offer_refs', 'source_supported_platform_scope_refs'):
    expected = set(before_options[OLD].get(field, [])) | set(before_options[KEEP].get(field, []))
    assert expected <= set(survivor.get(field, [])), field
assert survivor['canonical_component_id'] == before_options[KEEP]['canonical_component_id']

boot = get('bootstrap')
assert OLD not in {p['id'] for p in boot['products']}
assert sum(p['id'] == KEEP for p in boot['products']) == 1
assert len(boot['products']) == len(register['active_option_ids'])
try:
    get('products/' + OLD)
except urllib.error.HTTPError as error:
    assert error.code == 404
    retired_response = json.load(error)
    assert 'removed from the active catalogue' in retired_response['error']
else:
    raise AssertionError('Retired duplicate still opens as an active product')

before_old = read(OUT / (OLD + '-before.json'))
before_keep = read(OUT / (KEEP + '-before.json'))
product = get('products/' + KEEP)
assert product['name'] == 'Dune Ripple 2 - Verdigris and Copper'
assert product['source_hash'] == pointer['register_sha256']
assert product['folder_url'] == before_keep['folder_url']
before_reviews = {(r['kind'], r['item_id']): r for r in before_keep['reviews'] if r['product_id'] == KEEP}
after_reviews = {(r['kind'], r['item_id']): r for r in product['reviews'] if r['product_id'] == KEEP}
for key, review in before_reviews.items():
    assert key in after_reviews, key
    assert after_reviews[key]['version'] == review['version'], key
    assert after_reviews[key]['data'] == review['data'], key
before_fields = {f['key']: f for f in before_keep['fields']}
after_fields = {f['key']: f for f in product['fields']}
assert set(before_fields) == set(after_fields)
for field, original in before_fields.items():
    expected = {**original, 'value': original['value'].replace('—', '-')} if field == 'Name' else original
    assert after_fields[field] == expected, field
expected_images = {a['id'] for p in (before_old, before_keep) for a in p['images']}
images = {a['id']: a for a in product['images']}
assert set(images) == expected_images, {'lost': sorted(expected_images-set(images)), 'new': sorted(set(images)-expected_images)}
for aid in ('id:cnqzTNngPVsAAAAAAAyegw', 'id:cnqzTNngPVsAAAAAAAykxw'):
    assert images[aid]['association']['tier'] == 'accepted', (aid, images[aid]['association'])
for aid, image in images.items():
    assert OLD not in image.get('component_ids', []), aid

overview = get('component-overview/' + KEEP)
previous_overview = read(OUT / (KEEP + '-overview-before.json'))
assert overview['primary_id'] == previous_overview['primary_id']
assert overview['listing_ids'] == previous_overview['listing_ids']
assert set(previous_overview['in_situ_ids']) <= set(overview['in_situ_ids'])
assert 'id:cnqzTNngPVsAAAAAAAykxw' in overview['in_situ_ids']

receipt = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(),
           'keep_id': KEEP, 'retired_id': OLD, 'name': product['name'],
           'active_products': len(boot['products']), 'image_associations': len(images),
           'primary_id': overview['primary_id'], 'listing_ids': overview['listing_ids'],
           'in_situ_ids': overview['in_situ_ids'], 'keeper_reviews_preserved': len(before_reviews),
           'source_fields_unchanged': True, 'unrelated_options_unchanged': True,
           'aliases': survivor['retained_names'], 'platform_offer_refs': survivor['related_platform_offer_refs'],
           'register': str(register_path), 'register_sha256': pointer['register_sha256'],
           'retired_link_response': retired_response}
(OUT / 'app-merge-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
(OUT / 'merged-product.json').write_text(json.dumps(product, indent=2) + '\n')
(OUT / 'merged-overview.json').write_text(json.dumps(overview, indent=2) + '\n')
print(json.dumps(receipt))
