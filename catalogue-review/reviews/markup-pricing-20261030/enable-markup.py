"""Enable the requested shared 100% markup without replacing any existing cost or price input."""
from datetime import datetime, timezone
from pathlib import Path
from contextlib import closing
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json, sqlite3, sys, urllib.request
out=Path(__file__).resolve().parent
base='http://127.0.0.1:8767'
def get(path):
    with urllib.request.urlopen(base+path, timeout=60) as r: return json.load(r)
def save(name, value):
    (out/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def reviews_except_settings():
    dbpath=Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3')
    with closing(sqlite3.connect('file:'+str(dbpath)+'?mode=ro',uri=True)) as db:
        rows=db.execute("SELECT * FROM reviews WHERE kind != 'cost_settings' ORDER BY rowid").fetchall()
    return {'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=False).encode()).hexdigest()}
if '--apply' not in sys.argv: raise SystemExit('Use --apply to save the requested default.')
assert get('/api/health')['version']=='2.16.0'
before=get('/api/costs');save('costs-immediately-before-enable.json',before)
config=before['settings'].copy();config.update(default_pricing_mode='markup',default_markup_percent=100)
save('requested-shared-pricing.json',config)
unchanged_before=reviews_except_settings()
if config!=before['settings']:
    token=get('/api/bootstrap')['csrf_token']
    body={'kind':'cost_settings','product_id':'','item_id':'','version':before['version'],'data':config}
    req=urllib.request.Request(base+'/api/reviews',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Review-Token':token,'Origin':base},method='POST')
    with urllib.request.urlopen(req,timeout=60) as response: result=json.load(response)
    save('pricing-save-result.json',result)
after=get('/api/costs');save('costs-after.json',after)
assert after['settings']==config
assert {k:v for k,v in before['settings'].items() if k not in ('default_pricing_mode','default_markup_percent')}=={k:v for k,v in after['settings'].items() if k not in ('default_pricing_mode','default_markup_percent')}
unchanged_after=reviews_except_settings()
assert unchanged_before==unchanged_after, 'Another review changed concurrently; inspect before claiming preservation.'
specs=get('/api/specifications');save('specifications-after.json',specs)
original=json.loads((out/'specifications-before.json').read_text())
old={p['id']:p for p in original['products']}
results=[]
for p in specs['products']:
    c=p['costing'];pr=c['pricing'];prior=old[p['id']]
    price=next(f['value'] for f in p['fields'] if f['key']=='Price')
    expected=(Decimal(str(c['total_cost']))*2).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    assert c['status']=='calculated' and pr['mode']=='markup' and pr['markup_percent']==100,(p['id'],c)
    assert price==f'£{expected:,.2f}',(p['id'],price,expected)
    for key in ('listing_fields','notes','listing_decision','review_status','name','family'):
        assert p[key]==prior[key],(p['id'],key)
    assert [f for f in p['fields'] if f['key']!='Price']==[f for f in prior['fields'] if f['key']!='Price'],p['id']
    assert c['total_cost']==prior['costing']['total_cost'],p['id']
    results.append({'id':p['id'],'name':p['name'],'cost':c['total_cost'],'labour_cost':c['labour_cost'],'markup_percent':100,'price':price,'retained_fixed_price':pr['fixed_value']})
receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','count':len(results),'totals':specs['totals'],'settings_version':after['version'],'unchanged_reviews_before':unchanged_before,'unchanged_reviews_after':unchanged_after,'all_other_rates_specs_notes_listing_choices_preserved':True,'products':results}
save('live-pricing-verification.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k!='products'}))
print(json.dumps(next(x for x in results if x['id']=='BSI-2CA935C1A57A')))
