"""Verify current native content identity; download only missing selected originals."""
import hashlib,json,urllib.request
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from PIL import Image,ImageOps
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());assets=read(H/'current-assets.json');req=H/'temporary-download-requests.json';rows=read(req)['entries'];out=H/'originals';out.mkdir(exist_ok=True)
def hashes(data):
 h=hashlib.sha256()
 for i in range(0,len(data),4*1024*1024):h.update(hashlib.sha256(data[i:i+4*1024*1024]).digest())
 return hashlib.sha256(data).hexdigest(),h.hexdigest()
def one(x):
 fid=x['id'];a=assets[fid];p=next((Path(a[k])for k in ['full']if a.get(k)and Path(a[k]).is_file()),None);downloaded=False
 if p:
  data=p.read_bytes();whole,dbx=hashes(data)
  if dbx!=x['content_hash']:p=None
 if p is None:
  data=urllib.request.urlopen(x['download_url'],timeout=120).read();whole,dbx=hashes(data);assert dbx==x['content_hash'];p=out/(fid[3:]+Path(x['name']).suffix.lower());p.write_bytes(data);downloaded=True
 assert len(data)==x['size'] and dbx==x['content_hash']
 with Image.open(p)as im:size=ImageOps.exif_transpose(im).size
 a['full']=str(p.resolve());a['current_original_sha256']=whole;a['current_native_content_hash']=dbx;a['current_original_content_rehashed']=True
 return {'file_id':fid,'path':x['path'],'current_file_name':x['name'],'local_original':str(p.resolve()),'sha256':whole,'dropbox_content_hash':dbx,'bytes':len(data),'pixel_size':size,'downloaded_this_pass':downloaded}
try:
 with ThreadPoolExecutor(max_workers=4)as ex:results=list(ex.map(one,rows))
finally:req.unlink(missing_ok=True)
(H/'current-assets.json').write_text(json.dumps(assets,indent=2)+'\n');receipt={'status':'PASS_CURRENT_ORIGINAL_IDENTITY','recorded_utc':datetime.now(timezone.utc).isoformat(),'originals':results,'all_native_hashes_matched':True,'temporary_URLs_retained':False,'native_mutations':0};(H/'selected-original-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'sources':len(results),'downloaded':sum(x['downloaded_this_pass']for x in results),'native_hashes_verified':len(results)}))
