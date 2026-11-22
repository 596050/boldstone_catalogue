"""Review only cover images already rendered by the public owned reel grid."""
import json,sys,urllib.request
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image,ImageOps,ImageDraw
OUT=Path(__file__).parent;ROOT=OUT.parents[1];sys.path.insert(0,str(ROOT/'social-publisher'))
from common import atomic_json,digest,utc
source=OUT/'facebook-reels-current-snapshot.json';snap=json.loads(source.read_text());images=[i for i in snap['images'] if i['width']>=250 and i['height']>=250 and 'aria-label="Reel tile preview"' in i['parent']];links=[x['href'].split('?')[0] for x in snap['links'] if '/reel/' in x['href'] and not x['href'].split('?')[0].endswith('/reel/')];links=list(dict.fromkeys(links));assert len(images)==len(links)==10
sheet=Image.new('RGB',(1500,640),'white');draw=ImageDraw.Draw(sheet);records=[]
for n,(im,u) in enumerate(zip(images,links)):
 assert (urlparse(im['src']).hostname or '').endswith('.fbcdn.net')
 req=urllib.request.Request(im['src'],headers={'User-Agent':'Mozilla/5.0','Referer':snap['url']})
 with urllib.request.urlopen(req,timeout=30) as r:raw=r.read(10_000_001)
 assert len(raw)<10_000_001
 path=OUT/'history-media'/('facebook-reel-cover-'+u.rstrip('/').rsplit('/',1)[1]+'.jpg');path.write_bytes(raw)
 with Image.open(path) as pic:pic.verify()
 pic=ImageOps.contain(Image.open(path).convert('RGB'),(295,280));x=(n%5)*300;y=(n//5)*320;sheet.paste(pic,(x,y));draw.text((x,y+282),str(n)+' '+u.rsplit('/',1)[-1],fill='black')
 records.append({'index':n,'reel_url':u,'cover_path':str(path.resolve()),'cover_sha256':digest(raw),'source_grid_path':str(source.resolve()),'source_grid_sha256':digest(source.read_bytes())})
sheet.save(OUT/'facebook-reel-cover-review.jpg');atomic_json(OUT/'facebook-reel-cover-review-index.json',records);print(len(records))
