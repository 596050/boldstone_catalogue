"""Version-checked completion of blank listing descriptions; preserve all populated specs."""
from pathlib import Path
from datetime import datetime,timezone
import json,sys,urllib.request
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parent.parent))
from costing import DEFAULTS
BASE='http://127.0.0.1:8767'
def get(path):return json.load(urllib.request.urlopen(BASE+path,timeout=90))
boot=get('/api/bootstrap')
def post(body):
 req=urllib.request.Request(BASE+'/api/reviews',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token']})
 return json.load(urllib.request.urlopen(req,timeout=90))
def clean(s):return s.replace('—','-').replace('–','-').strip().rstrip('.')
def description(p):
 f={f['key']:f['value'] for f in p['fields']+p['listing_fields']}
 name=clean(p['name']);material=clean(f['Material / finish']);size=clean(f['Dimensions / depth']);weight=clean(f['Weight']);fix=clean(f['Fixing']);lead=clean(f['Lead time'])
 unit='sculptural basin' if 'basin' in name.lower() else 'sculptural water-feature panel' if 'water feature' in name.lower() else 'individual relief sculpture'
 text=f'{name} is an {unit} in the {clean(p["family"])} collection. {material[0].upper()+material[1:]}. Dimensions: {size}. Weight: {weight}. {fix[0].upper()+fix[1:]}. Made to order, with a production lead time of {lead}.'
 if 'water feature' in name.lower() or 'fountain block' in size.lower():text+=' The sculpture is priced separately from pumps, plumbing and installation.'
 return text.replace('an sculptural','a sculptural')
if '--apply' not in sys.argv:raise SystemExit('Pass --apply to save the requested completion.')
rates=get('/api/costs');rate_saved=None
if rates['version']==0:
 rate_saved=post({'kind':'cost_settings','product_id':'','item_id':'','version':0,'data':DEFAULTS})
specs=get('/api/specifications');saved=[];skipped=[]
for n,p in enumerate(specs['products'],1):
 field=next(f for f in p['listing_fields'] if f['key']=='Description')
 if field['value'] or field['decision']=='exclude':skipped.append(p['id']);continue
 value=description(p)
 r=post({'kind':'field','product_id':p['id'],'item_id':'Description','version':field['version'],'data':{'decision':'edit','value':value,'certainty':'source_claim','evidence':'Compiled from the current app specifications and owner production policy, 2026-10-30. Does not add measurements or change material, sale price, image approval or identity.','notes':'Customer copy completed at owner request; original field qualifications remain in the specification records.'}})
 assert r['data']['value']==value
 saved.append({'id':p['id'],'name':p['name'],'value':value,'version':r['version']})
 if n%30==0: print(f'{n}/{len(specs["products"])} checked; {len(saved)} descriptions saved',flush=True)
after=get('/api/specifications')
assert after['totals']['products']==181
assert all(f['value'] and '—' not in f['value'] for p in after['products'] for f in p['fields']+p['listing_fields'])
assert all(p['costing']['status']=='calculated' for p in after['products'])
original={p['id']:{f['key']:f['value'] for f in p['fields']} for p in specs['products']}
assert original=={p['id']:{f['key']:f['value'] for f in p['fields']} for p in after['products']}
receipt={'at':datetime.now(timezone.utc).isoformat(),'descriptions_saved':saved,'skipped_nonblank':skipped,'core_fields_preserved':True,'products_with_costs':181,'settings_version':get('/api/costs')['version']}
(OUT/'completion-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
(OUT/'specifications-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2))
print(json.dumps({'saved':len(saved),'skipped':len(skipped),'complete_specs':181,'costs':181,'core_fields_preserved':True}))
