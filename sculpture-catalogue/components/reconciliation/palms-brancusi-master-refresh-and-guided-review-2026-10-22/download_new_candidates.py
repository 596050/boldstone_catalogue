"""Download only newly discovered candidate originals and verify their byte identity."""
import hashlib,json,urllib.request,struct
from pathlib import Path
H=Path(__file__).resolve().parent;config=H/'new-picture-download-links.private.json';d=json.loads(config.read_text());out=H/'new-picture-originals';out.mkdir(exist_ok=True);rows=[]
try:
 for x in d['entries']:
  with urllib.request.urlopen(x['download_url'],timeout=45)as r:data=r.read()
  assert len(data)==x.get('size',0)and data.startswith(b'\x89PNG\r\n\x1a\n')
  ch=hashlib.sha256(b''.join(hashlib.sha256(data[j:j+4194304]).digest()for j in range(0,len(data),4194304))).hexdigest();assert ch==x['content_hash']
  p=out/(x['id'].split(':',1)[1]+'.png');p.write_bytes(data);rows.append({k:x.get(k)for k in ['id','name','path','path_display','size','content_hash']})
  rows[-1].update(local_path=str(p),sha256=hashlib.sha256(data).hexdigest(),width_height=list(struct.unpack('>II',data[16:24])))
finally:config.unlink(missing_ok=True)
(H/'new-picture-original-verification.json').write_text(json.dumps({'status':'PASS','originals':rows,'pixels_edited':False,'photographic_origin_verified':False,'catalogue_roles_changed':False},indent=2)+'\n');print(json.dumps({'status':'PASS','originals':len(rows),'no_image_edits':True}))
