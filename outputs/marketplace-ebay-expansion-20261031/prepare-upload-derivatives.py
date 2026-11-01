from pathlib import Path
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import json,hashlib,io
p=Path(__file__).resolve().parent;m=json.loads((p/'manifest.json').read_text());folder=p/'upload-1500w';folder.mkdir(exist_ok=True)
assets={a['url']:a for r in m['records'][6:] for a in r['photos']}
def get(it):
 url,a=it;u=url+('&' if '?' in url else '?')+'format=1500w'
 with urlopen(Request(u,headers={'User-Agent':'BoldstoneCatalogueUpload/1.0'}),timeout=45) as q:data=q.read()
 im=Image.open(io.BytesIO(data));im.verify();im=Image.open(io.BytesIO(data));ext={'JPEG':'jpg','PNG':'png','WEBP':'webp'}[im.format];dest=folder/(hashlib.sha256(u.encode()).hexdigest()[:18]+'.'+ext);dest.write_bytes(data)
 return url,{'local_path':str(dest),'upload_source_url':u,'upload_sha256':hashlib.sha256(data).hexdigest(),'upload_bytes':len(data),'upload_dimensions':[im.width,im.height]}
with ThreadPoolExecutor(max_workers=4) as pool:done=dict(pool.map(get,assets.items()))
for r in m['records'][6:]:
 for a in r['photos']:a.update(done[a['url']])
(p/'manifest-upload.json').write_text(json.dumps(m,indent=2,ensure_ascii=False));print('Prepared',len(done),'CDN upload derivatives, bytes',sum(a['upload_bytes'] for a in done.values()))
