from pathlib import Path
import json,urllib.request,zipfile,csv,io
BASE=Path(__file__).resolve().parent;URL='http://127.0.0.1:8768'
def get(path):
    with urllib.request.urlopen(URL+path,timeout=60) as r:return json.load(r)
boot=get('/api/bootstrap');token=boot.pop('csrf_token')
failures=[];count=0;listing=0;removed=0
for p in boot['products']:
    payload=get('/api/products/'+p['id']);count+=1
    ids=[i['id'] for i in payload['images']]
    if len(ids)!=len(set(ids)):failures.append({'product':p['id'],'error':'duplicate display IDs'})
    retained=[i for i in payload['images'] if i['association']['tier']!='removed']
    if p['image_count']!=len(retained):failures.append({'product':p['id'],'error':'bootstrap retained count mismatch'})
    removed+=len(ids)-len(retained)
coverage=get('/api/coverage')
for p in coverage['products'].values():
    if p['counts']['total']!=p['counts']['sculpture']+p['counts']['related']:failures.append({'product':p['id'],'error':'coverage totals mismatch'})
library=get('/api/library')
choices=[x for x in library['images'] if not x['component_ids']]
candidates=[x for x in choices if x['product_ids']]
request=urllib.request.Request(URL+'/api/export',data=json.dumps({'include_media':False}).encode(),headers={'Content-Type':'application/json','X-Review-Token':token})
with urllib.request.urlopen(request,timeout=90) as r:export=json.load(r)
path=Path(export['path']);archive=path.with_suffix('.zip')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    product_rows=list(csv.DictReader(io.StringIO(z.read('all-product-decisions.csv').decode('utf-8-sig'))))
    assert len(product_rows)==len(boot['products'])
receipt={'products_checked':count,'images_in_library':len(library['images']),'no_component_chosen':len(choices),'related_only_missed_by_old_filter':len(candidates),'removed_associations_in_test_fixture':removed,'failures':failures,'export':export,'zip_integrity':'passed','production_writes':0}
(BASE/'api-audit.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
assert not failures
