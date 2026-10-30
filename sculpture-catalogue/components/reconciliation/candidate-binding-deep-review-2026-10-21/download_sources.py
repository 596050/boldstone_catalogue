"""Download unique archive image bytes once; verify Dropbox block hashes."""
import collections,concurrent.futures,hashlib,json,urllib.request,argparse
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
(HERE/'archive-images').mkdir(exist_ok=True)
read=lambda p:json.loads(Path(p).read_text())
ap=argparse.ArgumentParser();ap.add_argument('--name',default='archive');args=ap.parse_args();pattern='download-*.json'if args.name=='archive'else args.name+'-download-*.json'
records=[x for p in sorted((HERE/'temporary').glob(pattern))for x in read(p)]
groups=collections.defaultdict(list)
for x in records:groups[x.get('content_hash')or x['id']].append(x)
def dbhash(data):
 a=hashlib.sha256()
 for i in range(0,len(data),4*1024*1024):a.update(hashlib.sha256(data[i:i+4*1024*1024]).digest())
 return a.hexdigest()
def fetch(group):
 rows=sorted(group,key=lambda x:('/90 Unclassified Documents/'in x.get('path',''),len(x.get('path',''))));x=rows[0]
 out=HERE/'archive-images'/(x['id'][3:]+Path(x['name']).suffix.lower())
 try:
  with urllib.request.urlopen(x['download_url'],timeout=45)as response:raw=response.read()
  assert len(raw)==x['size']and dbhash(raw)==x['content_hash']
  out.write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
  return[{'file_id':z['id'],'name':z['name'],'path':z['path'],'size':z['size'],'native_content_hash':z['content_hash'],'sha256':sha,'local_path':str(out),
   'downloaded_source_id':x['id'],'native_bytes_downloaded_for_this_ID':z['id']==x['id'],'shared_native_hash_verified':True}for z in rows]
 except Exception as exc:return{'failed_source_id':x['id'],'error_type':type(exc).__name__,'group_ids':[z['id']for z in rows]}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
 for result in pool.map(fetch,groups.values()):results.append(result)
failures=[x for x in results if isinstance(x,dict)];images=[z for x in results if isinstance(x,list)for z in x]
output={'status':'PASS'if not failures else'PARTIAL','recorded_utc':datetime.now(timezone.utc).isoformat(),'native_image_references':len(records),'unique_native_content_hashes':len(groups),
 'unique_files_downloaded':len([x for x in results if isinstance(x,list)]),'images':images,'failures':failures,'temporary_links_retained':False,'remote_mutations':0}
(HERE/(args.name+'-download-receipt.json')).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
for p in(HERE/'temporary').glob(pattern):p.unlink()
print(json.dumps({k:output[k]for k in ['status','native_image_references','unique_native_content_hashes','unique_files_downloaded','failures']}))
