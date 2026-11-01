"""Apply the user's zero labour rate through the versioned app API."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import json, urllib.request

BASE = 'http://127.0.0.1:8767'
OUT = Path(__file__).resolve().parent
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=90) as response:
        return json.load(response)
def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

assert not (OUT/'labour-change-receipt.json').exists(), 'Inspect the existing receipt before retrying.'
boot = get('/api/bootstrap')
before = get('/api/costs')
products = get('/api/specifications')['products']
save('cost-settings-before.json',before)
save('products-before.json',products)
data = dict(before['settings'])
data['labour_hourly'] = 0
receipt = {'status':'SUBMITTING', 'started_utc':datetime.now(timezone.utc).isoformat(),
           'before_rate':before['settings']['labour_hourly'],'requested_rate':0,'before_version':before['version']}
save('labour-change-receipt.json',receipt)
if before['settings']['labour_hourly'] != 0:
    body = {'kind':'cost_settings','product_id':'','item_id':'','version':before['version'],
            'settings_version':before['version'],'data':data}
    request = urllib.request.Request(BASE+'/api/reviews',data=json.dumps(body).encode(),method='POST',
                headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token'],'Origin':BASE})
    with urllib.request.urlopen(request,timeout=90) as response:
        result = json.load(response)
    save('cost-settings-save-response.json',result)
after = get('/api/costs')
current = get('/api/specifications')['products']
assert after['settings'] == data, 'Cost settings readback differs from the requested change.'
old = {p['id']:p for p in products}
assert set(old) == {p['id'] for p in current}
changes=[]
for p in current:
    c = p['costing'];b = old[p['id']]['costing']
    assert c['labour_cost'] == 0, p['id']
    assert c['manufacturing_cost'] == b['manufacturing_cost'],p['id']
    assert c['total_cost'] == c['manufacturing_cost'],p['id']
    assert c['inputs'] == b['inputs'],p['id']
    pricing=c['pricing']
    if pricing['mode'] == 'markup' and not pricing.get('price_omitted'):
        assert abs(pricing['marked_up_price']-round(c['manufacturing_cost']*(1+pricing['markup_percent']/100),2))<.005,p['id']
    changes.append({'id':p['id'],'name':p['name'],'manufacturing_cost':c['manufacturing_cost'],
                    'labour_before':b['labour_cost'],'labour_after':c['labour_cost'],
                    'price_before':b['pricing']['listing_value'],'price_after':pricing['listing_value']})
save('cost-settings-after.json',after)
save('products-after.json',current)
save('labour-price-changes.json',changes)
receipt.update(status='PASS_ZERO_LABOUR_ALL_COMPONENTS',verified_utc=datetime.now(timezone.utc).isoformat(),
               after_version=after['version'],components_checked=len(current),
               nonzero_labour=0,manufacturing_costs_unchanged=True,
               pricing_modes=dict(Counter(p['costing']['pricing']['mode'] for p in current)))
save('labour-change-receipt.json',receipt)
print(json.dumps(receipt,indent=2))
