import concurrent.futures as cf
import hashlib
import json
from pathlib import Path
import urllib.request
from PIL import Image,ImageOps,ImageDraw

project=Path(__file__).resolve().parents[1]
evidence=project/'evidence'
private=evidence/'first_family_download_links.private.json'
private.chmod(0o600)
links=json.loads(private.read_text())
media=Path('/Users/tprice/Library/Application Support/BoldstoneCatalogue/media')
media.mkdir(parents=True,exist_ok=True);media.chmod(0o700)
cache=json.loads((evidence/'image_review_cache_index.json').read_text())
def content_hash(b):
    return hashlib.sha256(b''.join(hashlib.sha256(b[x:x+4194304]).digest() for x in range(0,len(b),4194304))).hexdigest()
def get(r):
    out={k:v for k,v in r.items() if k!='download_url'}
    try:
        old=cache.get(r['id'],{}).get('local_path')
        p=Path(old) if old and Path(old).is_file() and content_hash(Path(old).read_bytes())==r['content_hash'] else media/(r['id'][3:]+'.image')
        if not p.exists() or content_hash(p.read_bytes())!=r['content_hash']:
            with urllib.request.urlopen(r['download_url'],timeout=60) as response:p.write_bytes(response.read())
        b=p.read_bytes();assert content_hash(b)==r['content_hash'], 'Downloaded bytes do not match Dropbox receipt'
        with Image.open(p) as im:out.update(image_size=list(im.size),format=im.format)
        out.update(local_path=str(p),sha256=hashlib.sha256(b).hexdigest(),hash_verified=True)
    except Exception as exc:out['error']=str(exc)
    return out
with cf.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(get,links))
(evidence/'batch01_media.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
private.unlink()
valid=[r for r in results if r.get('hash_verified')]
canvas=Image.new('RGB',(1400,((len(valid)+3)//4)*300),'white');draw=ImageDraw.Draw(canvas)
for i,r in enumerate(valid):
    x=(i%4)*350;y=(i//4)*300
    with Image.open(r['local_path']) as im:
        small=ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'),(340,225));canvas.paste(small,(x+(350-small.width)//2,y))
    draw.multiline_text((x+5,y+228),f'{i+1}. {r["name"][-43:]}\n{r["path"].split("/")[-2]}\n{r["id"]}',fill='black',spacing=3)
canvas.save(project/'reviews'/'batch01_contact.jpg',quality=92)
print(json.dumps(dict(files=len(results),verified=len(valid),errors=[r for r in results if 'error' in r])))
