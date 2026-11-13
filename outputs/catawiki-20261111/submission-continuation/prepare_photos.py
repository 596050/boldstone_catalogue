"""Download a bounded set of catalogue-bound originals for the native lot editor."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
pid=sys.argv[1] if len(sys.argv)>1 else 'BSI-C02D6DF365D3'
r=next(r for r in json.loads((OUT.parent/'product-review.json').read_text())['products'] if r['product_id']==pid)
chosen=[im for im in r['photo_candidates'] if not im['in_situ']]
if len(sys.argv)>2 and sys.argv[2]=='camera_candidates':
 chosen=[im for im in chosen if im['name'].lower().endswith(('.jpg','.jpeg'))][:5]
folder=OUT/'photos'/r['product_id'];folder.mkdir(parents=True,exist_ok=True)
receipt=[]
with connection(ROOT) as (client,_):
 for im in sorted(chosen,key=lambda x: x['name'].lower().endswith('.png')):
  m=client.files_get_metadata(im['image_id'])
  assert m.path_display.casefold().startswith('/boldstone master/products/01 wall sculptures/')
  assert m.size<15*1024*1024
  result,response=client.files_download('rev:'+m.rev)
  try:body=response.content
  finally:response.close()
  assert result.id==im['image_id'] and len(body)==m.size
  digest=hashlib.sha256(b''.join(hashlib.sha256(body[n:n+4194304]).digest() for n in range(0,len(body),4194304))).hexdigest()
  assert digest==m.content_hash
  p=folder/m.name;p.write_bytes(body)
  receipt.append({'id':m.id,'revision':m.rev,'path':str(p),'dropbox_path':m.path_display,'size':m.size,'sha256':hashlib.sha256(body).hexdigest(),'dropbox_hash_verified':True})
(OUT/(pid+'-photo-receipt.json')).write_text(json.dumps({'checked_utc':datetime.now(timezone.utc).isoformat(),'images':receipt},indent=2))
print(json.dumps(receipt,indent=2))
