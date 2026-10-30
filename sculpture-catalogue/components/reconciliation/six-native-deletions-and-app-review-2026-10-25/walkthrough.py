"""Walk one option at a time, keeping saved app reviews and sources distinct."""
from pathlib import Path
import argparse
import hashlib
import json

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
arg = argparse.ArgumentParser()
arg.add_argument('--option', type=int, default=1)
arg.add_argument('--id')
arg.add_argument('--app-fields', action='store_true')
arg.add_argument('--deleted', action='store_true')
a = arg.parse_args()
p = read(B / 'current-master.json')
assert sha(B / p['register']) == p['register_sha256']
g = read(B / p['register'])
overlay = read(H / 'availability-overlay.json')
assert p['register_sha256'] == overlay['baseline_register_sha256']
assert sha(H / 'availability-overlay.json') == '174cdf148b1483216aa5cceec69d708d96679dc95926aed068096dcf4a9d3e37'
deleted = {r['file_id']: r for r in overlay['rows']}
options = {o['product_id']: o for o in g['options']}
if a.deleted:
    for r in overlay['rows']:
        print(r['name'] + '\nStatus: deleted; native absence verified\nStable file ID: ' + r['file_id'] + '\nContaining folder: ' + r['folder_url'] + '\n')
else:
    if a.id:
        assert a.id in g['active_option_ids']
        o = options[a.id]
        number = g['active_option_ids'].index(a.id) + 1
    else:
        assert 1 <= a.option <= 188
        plan = read(g['current_listing_treatment_plan']['register'])
        o = options[plan['options'][a.option - 1]['product_id']]
        number = a.option
    print('OPTION ' + str(number) + '/188: ' + o['name'] + ' / ' + o['product_id'])
    if a.app_fields:
        report = B.parent / 'catalogue-review/reviews/specification-completion-20261025/all-188-readback.json'
        assert sha(report) == '4600d04d0ad3d1df2cb3ca136c0143047276b70eeabb52d12636680c4937f713'
        row = next(r for r in read(report) if r['product_id'] == o['product_id'])
        ref = row['image_reference']
        assert ref['id'] not in deleted
        print('Saved app name: ' + row['name'] + '\nSaved app image reference: ' + ref['url'] + '\nContaining folder: ' + ref['folder_url'] + '\nStable file ID: ' + ref['id'])
        assets = read(B / p['current_asset_reference_map']['path'])
        print('Folder ID: ' + str(assets.get(ref['id'], {}).get('folder_id', 'See retained source inventory')))
        for field, value in row['values'].items():
            print(field + ': ' + value + '\nSeparate evidence status: ' + row['provenance'][field]['certainty'])
        print('Saved app review through event 1830. Display values are separate from original source specifications; no physical measurement or canonical specification import is implied.')
    else:
        ref = o if o.get('file_id') else o['owner_confirmed_design_reference']
        if ref['file_id'] in deleted:
            print('Source image unavailable: owner-confirmed native deletion. Historical ID retained; no replacement chosen by this reconciliation.')
        else:
            print('Source image: ' + ref['image_url'])
        print('Containing folder: ' + ref['folder_url'] + '\nStable source file ID: ' + ref['file_id'] + '\nFolder ID: ' + ref['folder_id'])
        for field, value in o['master_fields'].items():
            print(field + ': ' + value['display'] + '\nSource evidence: ' + value['state'])
    print('Review this sculpture: http://127.0.0.1:8767/#' + o['product_id'])
print('Native availability scope: six exact confirmed deletions from the retained baseline; receipt snapshot event 347, last native deletion event 342. Existing owner holds remain in force.')
