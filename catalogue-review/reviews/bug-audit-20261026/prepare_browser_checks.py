from pathlib import Path
import urllib.request,json
BASE=Path(__file__).resolve().parent
URL='http://127.0.0.1:8768'
def get(path):
    with urllib.request.urlopen(URL+path,timeout=30) as r:return json.load(r)
boot=get('/api/bootstrap');token=boot['csrf_token']
def post(path,body):
    request=urllib.request.Request(URL+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Review-Token':token})
    with urllib.request.urlopen(request,timeout=30) as r:return json.load(r)
pid='BSI-C02D6DF365D3';p=get('/api/products/'+pid)
images=[i for i in p['images'] if i['source']=='Dropbox' and i['association']['tier']!='removed']
assert len(images)>=3
first,second,removed=images[:3]
for asset in [first,removed]:
    old=next((r for r in p['reviews'] if r['kind']=='image' and r['product_id']==pid and r['item_id']==asset['id']),{'version':0,'data':{}})
    values={**old['data'],'decision':'reviewed','uses':['listing','advertising'],'primary':asset==first}
    post('/api/reviews',{'kind':'image','product_id':pid,'item_id':asset['id'],'version':old['version'],'member_versions':old.get('member_versions'),'data':values})
assignment=next((r for r in boot['assignments'] if r['product_id']==pid and r['item_id']==removed['id']),{'version':0})
post('/api/assignments',{'asset_ids':[removed['id']],'from_product_id':pid,'to_product_id':'','mode':'remove','versions':{pid:{removed['id']:assignment['version']}}})
updated=get('/api/products/'+pid)
retained=[x for x in updated['images'] if x['association']['tier']!='removed']
lookup={(r['kind'],r['product_id'],r['item_id']):r for r in updated['reviews']}
expected_listing=sum(lookup.get(('image',pid,x['id']),{}).get('data',{}).get('decision')=='reviewed' and 'listing' in lookup.get(('image',pid,x['id']),{}).get('data',{}).get('uses',[]) for x in retained)
fixture={'pid':pid,'name':p['name'],'first':first['id'],'first_name':first['name'],'second':second['id'],'removed':removed['id'],'expected_retained':len(retained),'expected_listing':expected_listing,'production_mutations':0}
(BASE/'browser-fixture.json').write_text(json.dumps(fixture,indent=2))
print(json.dumps(fixture,indent=2))
