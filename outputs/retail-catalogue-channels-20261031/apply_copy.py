"""Save owner-requested public copy and fixing wording through version-checked app API."""
from pathlib import Path
import json,urllib.request
OUT=Path(__file__).resolve().parent;BASE='http://127.0.0.1:8767'
read=lambda p:json.loads(p.read_text())
plan=read(OUT/'website-copy-plan.json');before=read(OUT/'catalogue-snapshot.json');old={p['id']:p for p in before['products']};first={p['catalogue_id']:p for p in read(OUT/'retail-plan.json')['products']}
def get(p):
 with urllib.request.urlopen(BASE+p,timeout=120) as r:return json.load(r)
boot=get('/api/bootstrap');assert boot['source']['register_sha256']==before['source']['register_sha256']
current={p['id']:p for p in get('/api/specifications')['products']}
path=OUT/'app-copy-receipts.json';receipts=read(path) if path.exists() else []
for index,p in enumerate(plan['products'],1):
 id=p['catalogue_id'];fields={f['key']:f for f in current[id]['fields']+current[id]['listing_fields']}
 oldfields={f['key']:f for f in old[id]['fields']+old[id]['listing_fields']}
 for key,value in [('Retail name',p['retail_name']),('Description',p['website_description']),('Fixing',p['website_fixings'])]:
  field=fields[key]
  if field['value']==value:continue
  expected=first[id]['retail_name'] if key=='Retail name' else oldfields[key]['value']
  assert field['value']==expected,('Concurrent edit',id,key)
  data={'decision':'edit','value':value,'certainty':'confirmed','evidence':'Owner instruction, 31 October 2026: descriptive design-led customer copy, suitable for outdoor use, keyhole fixings usually used with alternatives such as French cleats, no casting material or Royal Mail rates in public product copy.','notes':'Public wording; does not alter dimensions, weight, production cost inputs, prices, stock or component identity.'}
  req=urllib.request.Request(BASE+'/api/reviews',data=json.dumps({'kind':'field','product_id':id,'item_id':key,'version':field['version'],'data':data}).encode(),headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token'],'Origin':BASE},method='POST')
  with urllib.request.urlopen(req,timeout=120) as r: result=json.load(r)
  assert result['data']['value']==value
  receipts.append({'catalogue_id':id,'field':key,'before':field,'after':result})
  path.write_text(json.dumps(receipts,indent=2))
 if index%20==0:print(json.dumps({'products_saved':index,'total':181}),flush=True)
after={p['id']:p for p in get('/api/specifications')['products']}
for p in plan['products']:
 x=after[p['catalogue_id']];fs={f['key']:f for f in x['fields']+x['listing_fields']}
 assert fs['Retail name']['value']==p['retail_name'] and fs['Description']['value']==p['website_description'] and fs['Fixing']['value']==p['website_fixings']
 assert x['name']==p['catalogue_name']
(OUT/'app-copy-verification.json').write_text(json.dumps({'status':'PASS_APP_READBACK','products':181,'changed_fields':['Retail name (gold finish wording only)','Description','Fixing']},indent=2))
print('PASS_APP_COPY_READBACK')
