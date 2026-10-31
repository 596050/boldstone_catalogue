"""Version-checked writes through the review app; preserve canonical names."""
from pathlib import Path
from datetime import datetime, timezone
import json, urllib.request

OUT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'
plan = json.loads((OUT/'retail-plan.json').read_text())
snapshot = json.loads((OUT/'catalogue-snapshot.json').read_text())
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=120) as r: return json.load(r)
boot = get('/api/bootstrap')
assert boot['source']['register_sha256'] == snapshot['source']['register_sha256']
specs = {p['id']:p for p in get('/api/specifications')['products']}
receipts = []
for n,p in enumerate(plan['products'],1):
    current = specs[p['catalogue_id']]
    assert current['name'] == p['catalogue_name'], 'Concurrent canonical name change'
    field = next(f for f in current['listing_fields'] if f['key']=='Retail name')
    if field['value'] and field['value'] != p['retail_name']:
        raise RuntimeError('Retail title was edited concurrently: '+p['catalogue_id'])
    if field['value'] == p['retail_name']:
        continue
    body={'kind':'field','product_id':p['catalogue_id'],'item_id':'Retail name','version':field['version'],
          'data':{'decision':'edit','value':p['retail_name'],'certainty':'confirmed',
                  'evidence':'Retail wording created under the owner instruction of 31 October 2026. Does not change sculpture identity, finish, SKU, dimensions or price.',
                  'notes':'The catalogue name is retained separately for matching and source provenance.'}}
    req=urllib.request.Request(BASE+'/api/reviews',data=json.dumps(body).encode(),method='POST',
        headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token'],'Origin':BASE})
    with urllib.request.urlopen(req,timeout=120) as response: result=json.load(response)
    assert result['data']['value']==p['retail_name']
    receipts.append({'catalogue_id':p['catalogue_id'],'retail_name':result['data']['value'],
                     'version':result['version'],'updated_at':result.get('updated_at')})
    (OUT/'app-retail-receipts.json').write_text(json.dumps(receipts,indent=2))
    if n%20==0: print(json.dumps({'retail_names_saved':n,'total':len(plan['products'])}),flush=True)
after={p['id']:p for p in get('/api/specifications')['products']}
assert all(after[p['catalogue_id']]['retail_name']==p['retail_name'] for p in plan['products'])
assert all(after[p['catalogue_id']]['name']==p['catalogue_name'] for p in plan['products'])
assert all(after[p['id']]['fields']==p['fields'] for p in snapshot['products'])
print(json.dumps({'status':'PASS_APP_READBACK','retail_names':len(after),'canonical_names_and_specifications_unchanged':True}))
