"""Prepare ten catalogue-authoritative Marketplace records and upload images."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,io,re
from PIL import Image
OUT=Path(__file__).resolve().parent
plan=json.loads((OUT/'website-final-plan.json').read_text())
snap=json.loads((OUT/'catalogue-snapshot.json').read_text())
assert json.loads((OUT/'public-website-verification.json').read_text())['status']=='PASS_ALL_PUBLIC_PAGES'
class Plain(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,t):self.parts.append(t)
 def handle_endtag(self,t):
  if t in ['p','li']:self.parts.append('\n')
products=sorted([p for p in plan['products'] if p.get('public') and p['listing_decision']=='include'],key=lambda p:p['catalogue_name'].casefold())[:10]
records=[]
for n,p in enumerate(products,1):
 parser=Plain();parser.feed(p['published_description_html'])
 description='\n\n'.join(s.strip() for s in ''.join(parser.parts).splitlines() if s.strip())
 description+='\n\nFull details and more photographs: '+p['website_url']
 assert not re.search(r'\b(GFRC|Jesmonite|plaster|concrete|Royal Mail)\b',description,re.I)
 gallery=p['website_gallery'];assert gallery[0]['url']==p['primary_url']
 # Within Facebook's 10-photo cap, reserve two positions for selected in-situ photos.
 if len(gallery)<=10: chosen=gallery
 else:
  situ=[a for a in gallery if a['role']=='in_situ']
  other=[a for a in gallery if a['role']!='in_situ']
  chosen=other[:10-min(2,len(situ))]+situ[:max(0,10-len(other[:10-min(2,len(situ))]))]
 records.append({'order':n,'catalogue_id':p['catalogue_id'],'catalogue_name':p['catalogue_name'],'title':p['retail_name']+' | Wall Sculpture','price':p['price'],'currency':'GBP','description':description,'condition':'New','website_url':p['website_url'],'sku':p['sku'],'photos':chosen,'all_website_photos':len(gallery),'status':'prepared'})
assets={a['url']:a for r in records for a in r['photos']}
image_dir=OUT/'marketplace-images';image_dir.mkdir(exist_ok=True)
def fetch(item):
 url,a=item
 with urlopen(Request(url,headers={'User-Agent':'BoldstoneCatalogueVerification/1.0'}),timeout=60) as response:data=response.read()
 im=Image.open(io.BytesIO(data));im.verify()
 im=Image.open(io.BytesIO(data));ext={'JPEG':'jpg','PNG':'png','WEBP':'webp'}[im.format]
 target=image_dir/(hashlib.sha256(url.encode()).hexdigest()[:18]+'.'+ext);target.write_bytes(data)
 return url,{'local_path':str(target),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'width':im.width,'height':im.height}
with ThreadPoolExecutor(max_workers=4) as pool:downloaded=dict(pool.map(fetch,assets.items()))
for r in records:
 r['photos']=[{**a,**downloaded[a['url']]} for a in r['photos']]
result={'created_utc':datetime.now(timezone.utc).isoformat(),'source_cutoff':snap['event_cutoff'],'ordering':'Included public products, alphabetical by catalogue name','records':records}
(OUT/'marketplace-first10.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print(json.dumps([{'order':r['order'],'title':r['title'],'price':r['price'],'photos':len(r['photos'])} for r in records],indent=2))
