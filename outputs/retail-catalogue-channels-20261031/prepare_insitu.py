"""Verify and stage only the exact associated in-situ originals for website upload."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from contextlib import ExitStack
import json,hashlib,sys,threading,os,time
ROOT=Path('/Users/tprice/Documents/boldstone'); OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from image_delivery_worker import connection
from fetch_original import check_metadata
from delete_dropbox import failure_details
plan=json.loads((OUT/'website-plan.json').read_text())
rows={r['image_id']:r for p in plan['products'] if p.get('public') for r in p['in_situ']}
folder=OUT/'staged-in-situ';folder.mkdir(exist_ok=True)
manifest=OUT/'staged-in-situ.json'
results=json.loads(manifest.read_text()) if manifest.exists() else {}
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
   m,resp=local.client.files_download(r['image_id'])
   try:b=resp.content
   finally:resp.close()
   check_metadata(m,r['image_id'],r['content_hash'],int(r['bytes']),local.root)
   assert dbhash(b)==m.content_hash and len(b)==m.size
   name='boldstone-situ-'+r['content_hash'][:16]+Path(m.name).suffix.lower()
   path=folder/name;path.write_bytes(b)
   return r['image_id'],dict(file=str(path),filename=name,bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),content_hash=m.content_hash,original_name=m.name,path=m.path_display,revision=m.rev,status='verified_original')
  except Exception as e:
   info=failure_details(e)
   if attempt<2 and info['error_code'] in {'ReadTimeout','ConnectTimeout','ConnectionError','Timeout','InternalServerError','RateLimitError'}:time.sleep(min(30,max(1,info.get('retry_after',0),2**attempt)));continue
   return r['image_id'],dict(status='error',error=info)
try:
 with ThreadPoolExecutor(max_workers=3) as pool:
  fs=[pool.submit(task,r) for aid,r in rows.items() if aid not in results or results[aid].get('status')!='verified_original']
  for i,f in enumerate(as_completed(fs),1):
   aid,value=f.result();results[aid]=value
   tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(results,indent=2));tmp.replace(manifest)
   if i%20==0 or i==len(fs):print(json.dumps({'verified':sum(r.get('status')=='verified_original' for r in results.values()),'total':len(rows),'errors':sum(r.get('status')=='error' for r in results.values())}),flush=True)
finally:
 for stack in stacks:stack.close()
