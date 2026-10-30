from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone
import hashlib, json, sqlite3, urllib.request, sys
from concurrent.futures import ThreadPoolExecutor
app=Path('/Users/tprice/Documents/boldstone/catalogue-review');sys.path.insert(0,str(app))
from catalogue import Catalogue
evidence=app/'reviews/all-specifications-20261027'; runtime=Path.home()/'Library/Application Support/BoldstoneReview'
def get(route):
 with urllib.request.urlopen('http://127.0.0.1:8767/api/'+route,timeout=30) as r:return json.load(r)
start=get('specifications');boot=get('bootstrap')
with patch('catalogue.enrich'):
 cat=Catalogue(app.parent,runtime)
with sqlite3.connect('file:'+str(runtime/'reviews.sqlite3')+'?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 rows={(r['kind'],r['product_id'],r['item_id']):dict(r) for r in db.execute("SELECT * FROM reviews WHERE kind IN ('field','product')")}
checks=0
assert start['source_hash']==cat.source['register_sha256'];checks+=1
ids={p['id'] for p in start['products']};assert len(ids)==len(start['products']);checks+=1
assert ids==set(cat.products)=={p['id'] for p in boot['products']};checks+=1
assert not ids.intersection(cat.retired_product_ids);checks+=1
edited=omitted=0;updated_folders=[]
for p in start['products']:
 src=cat.products[p['id']];fields=p['fields']+p['listing_fields'];expected={f['key']:f for f in src['fields']}
 assert {f['key'] for f in fields}==set(expected);checks+=1
 for f in fields:
  source=expected[f['key']];r=rows.get(('field',p['id'],f['key']),{});choice=json.loads(r.get('data','{}'));decision=choice.get('decision','pending')
  v=None if decision=='exclude' else (choice.get('value','') if decision=='edit' else source['value']).replace('\u2014','-')
  assert f['value']==v and f['source_value']==source['value'] and f['version']==r.get('version',0),(p['id'],f['key']);checks+=1
  assert '\u2014' not in (f['value'] or '');checks+=1
  edited+=decision=='edit';omitted+=decision=='exclude'
 assert p['family']==src['family'];checks+=1
 if p['folder_url']!=src['folder_url']:updated_folders.append(p)
# Native inventory overlays replace historical folder paths. Compare these to the actual component page.
with ThreadPoolExecutor(max_workers=4) as pool:
 for p,live in zip(updated_folders,pool.map(lambda p:get('products/'+p['id']),updated_folders)):
  assert p['folder_url']==live['folder_url'],p['id'];checks+=1
end=get('specifications');assert start['revision']==end['revision'];checks+=1
assets={}
for name in ('app.js','specifications.js','image-tools.js','sync-tools.js','jobs.js','index.html','style.css'):
 local=(app/'static'/name).read_bytes()
 with urllib.request.urlopen('http://127.0.0.1:8767/'+name,timeout=10) as r:served=r.read()
 assert served==local,name;checks+=1;assets[name]=hashlib.sha256(served).hexdigest()
record={'at':datetime.now(timezone.utc).isoformat(),'status':'PASS','checks':checks,'health':get('health'),'totals':start['totals'],'families':len(start['families']),'all_fields_including_listing_copy':sum(len(p['fields'])+len(p['listing_fields']) for p in start['products']),'saved_edits_verified':edited,'saved_omissions_verified':omitted,'source_hash':start['source_hash'],'revision':start['revision'],'active_ids_exact':True,'retired_ids_absent':True,'native_updated_folder_links_verified':len(updated_folders),'specification_source_and_review_rows_read_only':True,'native_mutations_performed':False,'served_static_sha256':assets}
(evidence/'live-readback.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
