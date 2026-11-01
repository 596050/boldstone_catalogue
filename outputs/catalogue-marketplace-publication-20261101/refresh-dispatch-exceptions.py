"""Record newly verified channel exceptions without rewriting product copy."""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[1] / 'catalogue-review'))
from channel_content import DISPATCH_EXCEPTIONS, values

BASE = 'http://127.0.0.1:8767'
AUTHORITY = ('Owner: three working days where required; ten elsewhere. '
             'Native Chairish parcel terms and Saatchi Art Packaging + Shipping '
             'require short handover; verified 1 November 2026. '
             'No artwork dimensions, stock, prices or photographs are changed.')

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return json.load(r)

def main():
    before = get('/api/specifications')
    boot = get('/api/bootstrap')
    assert boot['source']['register_sha256'] == before['source_hash']
    receipts = []
    out = OUT / 'dispatch-exceptions-refresh.json'
    for p in before['products']:
        field = next(f for f in p['fields'] + p['listing_fields'] if f['key'] == 'Dispatch exceptions')
        if field['value'] == DISPATCH_EXCEPTIONS:
            continue
        assert field['value'].startswith('Default: dispatch within 10 working days.'), (p['id'], 'Unexpected custom policy')
        body = {'kind': 'field', 'product_id': p['id'], 'item_id': field['key'],
                'version': field['version'], 'data': {'decision': 'edit',
                'value': DISPATCH_EXCEPTIONS, 'certainty': 'source_claim',
                'evidence': AUTHORITY,
                'notes': 'Saatchi: https://support.saatchiart.com/hc/en-us/articles/115003365447-Packaging-Shipping'}}
        req = urllib.request.Request(BASE + '/api/reviews', data=json.dumps(body).encode(),
            headers={'Content-Type':'application/json', 'Origin':BASE,
                     'X-Review-Token':boot['csrf_token']}, method='POST')
        with urllib.request.urlopen(req, timeout=120) as response:
            saved = json.load(response)
        assert saved['data']['value'] == DISPATCH_EXCEPTIONS
        receipts.append({'id':p['id'], 'before':field, 'after':saved})
        out.write_text(json.dumps({'receipts':receipts}, indent=2))
    after = get('/api/specifications')
    byid = {p['id']:p for p in after['products']}
    for old in before['products']:
        new = byid[old['id']]
        assert values(new)['Dispatch exceptions'] == DISPATCH_EXCEPTIONS
        for k,v in values(old).items():
            if k != 'Dispatch exceptions':
                assert values(new)[k] == v, (old['id'],k)
        for k in ('photos','costing','listing_decision'):
            assert old[k] == new[k], (old['id'],k)
    prepared_path = OUT / 'current-prepared-catalogue.json'
    prepared = json.loads(prepared_path.read_text())
    for r in prepared['records']:
        r['dispatch_exceptions'] = DISPATCH_EXCEPTIONS
    prepared_path.write_text(json.dumps(prepared, ensure_ascii=False, indent=2))
    out.write_text(json.dumps({'status':'PASS_FIELD_CAS_AND_READBACK',
        'verified_utc':datetime.now(timezone.utc).isoformat(),
        'products':len(before['products']), 'updated':len(receipts),
        'other_fields_costs_images_inclusion_unchanged':True, 'receipts':receipts}, indent=2))
    print(json.dumps({'verified_products':len(before['products']), 'updated':len(receipts)}))

if __name__ == '__main__':
    main()
