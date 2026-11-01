from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import json
OUT=Path(__file__).resolve().parent;BASE='http://127.0.0.1:8767'
def get(path):
 with urlopen(BASE+path,timeout=90) as r:return json.load(r)
boot=get('/api/bootstrap')
def post(path,data):
 with urlopen(Request(BASE+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token'],'Origin':BASE}),timeout=90) as r:return json.load(r)
pairs=[('BSI-67EA9E9D261A','id:cnqzTNngPVsAAAAAAA7JVg','White Lava Moonshell I square relief with a textured sweeping arc and a curled spiral on the right.'),('BSI-21E7F11ACAAA','id:cnqzTNngPVsAAAAAAA7JVw','White Lava Moonshell II square relief with a textured sweeping arc and a smooth crescent on the right.')]
snapshot=json.loads((OUT/'catalogue-snapshot.json').read_text());receipts=[]
for pid,aid,alt in pairs:
 c=get('/api/image-components?'+urlencode({'id':aid,'primary':1}));row=next(r for r in c['rows'] if r['product_id']==pid)
 assert row['shown'] and not row['excluded'] and row['image_version']==0
 h=next(r['image']['original']['dropbox_content_hash'] for r in snapshot['images'] if r['image']['id']==aid)
 assert h==c['content_hash']
 receipts.append(post('/api/reviews',{'kind':'asset','product_id':'','item_id':aid,'version':0,'expected_content_hash':h,'data':{'types':['product']}}))
 row.update(listing=True,primary=True)
 receipts.append(post('/api/image-components',{'asset_id':aid,'content_hash':h,'rows':[row]}))
 p=get('/api/products/'+pid);saved=next(r for r in p['reviews'] if r['kind']=='image' and r['item_id']==aid and r['product_id']==pid)
 data=saved['data'].copy();data.pop('reviewed_content_hash',None);data['alt']=alt
 receipts.append(post('/api/reviews',{'kind':'image','product_id':pid,'item_id':aid,'version':saved['version'],'expected_content_hash':h,'data':data}))
 verify=get('/api/component-overview/'+pid)
 assert verify['primary_id']==aid,verify.keys()
(OUT/'app-selection-receipts.json').write_text(json.dumps(receipts,indent=2))
print('PASS: replacement product images selected as Listing and Primary for both components.')
