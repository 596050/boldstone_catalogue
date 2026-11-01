"""Stage only gallery additions, reusing verified web copies when available."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from contextlib import ExitStack
from io import BytesIO
from urllib.request import Request,urlopen
import hashlib,json,sys,threading,time
from PIL import Image
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
OLD=OUT.parent/'retail-catalogue-channels-20261031'
sys.path.insert(0,str(ROOT/'catalogue-review'))
from image_delivery_worker import connection
from fetch_original import check_metadata
from dropbox.files import PathOrLink,ThumbnailSize,ThumbnailMode
read=lambda p:json.loads(p.read_text())
plan=read(OUT/'all-image-plan.json');current=read(OUT/'staged-in-situ.json')
oldstage={v['content_hash']:v for v in read(OLD/'staged-in-situ.json').values()}
hosted={a['filename']:a['src'].split('?')[0] for a in read(OLD/'native-insitu-assets.json')+read(OUT/'hosted-assets.json')}
assets={}
for p in plan['products']:
 if not p['public']:continue
 existing={a['content_hash'] for a in p['existing']}
 p['additions']=[a for a in p['gallery'] if a['content_hash'] not in existing]
 p['removals']=[a for a in p['existing'] if a['content_hash'] not in {g['content_hash'] for g in p['gallery']}]
 for a in p['additions']:assets.setdefault(a['content_hash'],a)
folder=OUT/'gallery-additions';folder.mkdir(exist_ok=True)
manifest=OUT/'gallery-addition-assets.json';results=read(manifest) if manifest.exists() else {}
local=threading.local();stacks=[];lock=threading.Lock()
def work(a):
 h=a['content_hash'];known=current.get(h) or oldstage.get(h)
 if known and Path(known['file']).exists():
  return h,dict(known,status='verified',source='Previously verified Dropbox representation')
 for attempt in range(3):
  try:
   if known and known['filename'] in hosted:
    url=hosted[known['filename']]+'?format=2500w'
    with urlopen(Request(url,headers={'User-Agent':'BoldstoneCatalogueRefresh/1.0'}),timeout=35) as r:b=r.read()
    source=url
   else:
    if not hasattr(local,'client'):
     stack=ExitStack();local.client,root=stack.enter_context(connection(ROOT))
     with lock:stacks.append(stack)
    result,response=local.client.files_get_thumbnail_v2(PathOrLink.path(a['image_id']),size=ThumbnailSize.w2048h1536,mode=ThumbnailMode.bestfit)
    try:b=response.content
    finally:response.close()
    check_metadata(result.file_metadata,a['image_id'],h,a['bytes'],'/BOLDSTONE MASTER')
    source='Verified Dropbox 2048-pixel preview'
   with Image.open(BytesIO(b)) as im:
    dims=list(im.size);ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[im.format];im.verify()
   name='boldstone-gallery-'+h[:16]+ext;file=folder/name;file.write_bytes(b)
   return h,{'status':'verified','file':str(file),'filename':name,'content_hash':h,'image_id':a['image_id'],'source':source,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'dimensions':dims}
  except Exception as e:
   if attempt<2:time.sleep(attempt+1);continue
   return h,{'status':'error','image_id':a['image_id'],'error':str(e)}
try:
 with ThreadPoolExecutor(max_workers=4) as pool:
  for n,f in enumerate(as_completed(pool.submit(work,a) for h,a in assets.items() if results.get(h,{}).get('status')!='verified'),1):
   h,r=f.result();results[h]=r
   tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(results,indent=2));tmp.replace(manifest)
   if n%25==0:print(json.dumps({'staged':len(results),'total':len(assets),'errors':sum(x['status']!='verified' for x in results.values())}),flush=True)
finally:
 for stack in stacks:stack.close()
assert all(results.get(h,{}).get('status')=='verified' for h in assets),[r for r in results.values() if r['status']!='verified']
for p in plan['products']:
 for a in p.get('additions',[]):a.update(file=results[a['content_hash']]['file'],filename=results[a['content_hash']]['filename'])
(OUT/'all-image-execution-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2))
print(json.dumps({'status':'PASS','unique_additions':len(assets),'placements':sum(len(p.get('additions',[])) for p in plan['products']),'removals':sum(len(p.get('removals',[])) for p in plan['products']),'public':sum(p['public'] for p in plan['products'])}))
