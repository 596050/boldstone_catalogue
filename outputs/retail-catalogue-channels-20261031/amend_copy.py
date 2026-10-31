from pathlib import Path
import json,urllib.request
OUT=Path(__file__).resolve().parent;BASE='http://127.0.0.1:8767'
read=lambda p:json.loads(p.read_text())
assert read(OUT/'app-copy-verification.json')['status']=='PASS_APP_READBACK'
plan=read(OUT/'website-copy-plan.json')
amend=read(OUT/'app-copy-amendments.json') if (OUT/'app-copy-amendments.json').exists() else []
receipts=read(OUT/'app-copy-receipts.json')+amend;expected={(x['catalogue_id'],x['field']):x['after']['data']['value'] for x in receipts}
def get(p):
 with urllib.request.urlopen(BASE+p,timeout=120) as r:return json.load(r)
boot=get('/api/bootstrap');now={p['id']:p for p in get('/api/specifications')['products']}
for p in plan['products']:
 pid=p['catalogue_id'];fs={f['key']:f for f in now[pid]['fields']+now[pid]['listing_fields']}
 for key,value in [('Description',p['website_description']),('Retail name',p['retail_name']),('Fixing',p['website_fixings'])]:
  f=fs[key]
  if f['value']==value:continue
  assert f['value']==expected[(pid,key)],('Concurrent edit',pid,key)
  data={'decision':'edit','value':value,'certainty':'confirmed','evidence':'Owner requested public copy without construction material references, 31 October 2026.','notes':'Design interpretation and customer wording; internal production and source values retained.'}
  req=urllib.request.Request(BASE+'/api/reviews',data=json.dumps({'kind':'field','product_id':pid,'item_id':key,'version':f['version'],'data':data}).encode(),headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token'],'Origin':BASE},method='POST')
  with urllib.request.urlopen(req,timeout=120) as r:result=json.load(r)
  amend.append({'catalogue_id':pid,'field':key,'before':f,'after':result});(OUT/'app-copy-amendments.json').write_text(json.dumps(amend,indent=2))
after=get('/api/specifications')
for x in after['products']:
 p=next(p for p in plan['products'] if p['catalogue_id']==x['id']);fs={f['key']:f for f in x['fields']+x['listing_fields']}
 assert fs['Description']['value']==p['website_description'] and fs['Fixing']['value']==p['website_fixings'] and fs['Retail name']['value']==p['retail_name']
(OUT/'app-copy-final-verification.json').write_text(json.dumps({'status':'PASS','products':181,'amended_fields':len(amend)},indent=2));print('PASS final copy readback',len(amend))
