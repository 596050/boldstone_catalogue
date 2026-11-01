"""Download only missing website assets through the existing Dropbox connection."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from contextlib import ExitStack
from io import BytesIO
import json,hashlib,sys,threading,time
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from image_delivery_worker import connection
from fetch_original import check_metadata
from delete_dropbox import failure_details
from dropbox.files import PathOrLink,ThumbnailSize,ThumbnailMode
from PIL import Image
plan=json.loads((OUT/'website-plan.json').read_text());rows=[r for r in plan['assets'] if 'website_url' not in r]
folder=OUT/'staged-in-situ';folder.mkdir(exist_ok=True)
manifest=OUT/'staged-in-situ.json';results=json.loads(manifest.read_text()) if manifest.exists() else {}
local=threading.local();stacks=[];lock=threading.Lock()
def dbhash(b):
 h=hashlib.sha256()
 for start in range(0,len(b),4*1024*1024):h.update(hashlib.sha256(b[start:start+4*1024*1024]).digest())
 return h.hexdigest()
def task(r):
 if not hasattr(local,'client'):
  stack=ExitStack();local.client,local.root=stack.enter_context(connection(ROOT))
  with lock:stacks.append(stack)
 for attempt in range(3):
  try:
   oversized=True
   if oversized:
    result,resp=local.client.files_get_thumbnail_v2(PathOrLink.path(r['image_id']),size=ThumbnailSize.w2048h1536,mode=ThumbnailMode.bestfit);m=result.file_metadata
   else:m,resp=local.client.files_download(r['image_id'])
   try:b=resp.content
   finally:resp.close()
   check_metadata(m,r['image_id'],r['content_hash'],int(r['bytes']),local.root)
   if not oversized:assert dbhash(b)==m.content_hash and len(b)==m.size
   with Image.open(BytesIO(b)) as im:dimensions=list(im.size);im.verify()
   suffix='.jpg' if oversized else Path(m.name).suffix.lower()
   name='boldstone-situ-'+r['content_hash'][:16]+('-web' if oversized else '')+suffix
   path=folder/name;path.write_bytes(b)
   return r['content_hash'],dict(file=str(path),filename=name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),content_hash=m.content_hash,image_id=m.id,original_name=m.name,path=m.path_display,revision=m.rev,dimensions=dimensions,representation='Dropbox 2048-pixel preview' if oversized else 'Verified original',status='verified')
  except Exception as e:
   info=failure_details(e)
   if attempt<2 and info['error_code'] in {'ReadTimeout','ConnectTimeout','ConnectionError','Timeout','InternalServerError','RateLimitError'}:time.sleep(min(30,max(1,info.get('retry_after',0),2**attempt)));continue
   return r['content_hash'],dict(status='error',error=info)
try:
 with ThreadPoolExecutor(max_workers=3) as pool:
  tasks=[pool.submit(task,r) for r in rows if results.get(r['content_hash'],{}).get('status')!='verified']
  for n,f in enumerate(as_completed(tasks),1):
   h,value=f.result();results[h]=value
   tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(results,indent=2));tmp.replace(manifest)
   if n%25==0 or n==len(tasks):print(json.dumps({'verified':sum(r.get('status')=='verified' for r in results.values()),'total':len(rows),'errors':sum(r.get('status')=='error' for r in results.values())}),flush=True)
finally:
 for stack in stacks:stack.close()
