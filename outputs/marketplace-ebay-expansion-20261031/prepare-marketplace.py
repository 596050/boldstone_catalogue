"""Prepare the next 40 included wall sculptures for the authorised Marketplace upload."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor
import hashlib, json, io, re
from PIL import Image

OUT=Path(__file__).resolve().parent
PREV=OUT.parent/'website-marketplace-refresh-20261031'
plan=json.loads((PREV/'website-final-plan.json').read_text())
old=json.loads((PREV/'catalogue-snapshot.json').read_text())
fresh=json.loads((OUT/'catalogue-snapshot.json').read_text())
assert fresh['event_cutoff']==old['event_cutoff']==plan['event_cutoff']
assert fresh['products']==old['products']
done={r['catalogue_id'] for r in json.loads((PREV/'marketplace-first10.json').read_text())['records']}
done.update(r['catalogue_id'] for r in json.loads((OUT.parent/'marketplace-next30-20261031/publication-receipts.json').read_text()))
assert len(done)==40
done.add('BSI-B2D54C28FDA3')
class Plain(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,t):self.parts.append(t)
 def handle_endtag(self,t):
  if t in ['p','li']:self.parts.append('\n')
products=sorted([p for p in plan['products'] if p.get('public') and p['listing_decision']=='include' and p['catalogue_id'] not in done],key=lambda p:p['catalogue_name'].casefold())[:40]
records=[]
for n,p in enumerate(products,42):
 parser=Plain();parser.feed(p['published_description_html'])
 description='\n\n'.join(s.strip() for s in ''.join(parser.parts).splitlines() if s.strip())
 description+='\n\nWebsite price: £'+p['price']+'. Full details, photographs and online ordering: '+p['website_url']
 assert not re.search(r'\b(GFRC|Jesmonite|plaster|concrete|Royal Mail)\b',description,re.I)
 gallery=p['website_gallery'];assert gallery[0]['url']==p['primary_url']
 if len(gallery)<=10:chosen=gallery
 else:
  situ=[a for a in gallery if a['role']=='in_situ']; other=[a for a in gallery if a['role']!='in_situ']
  chosen=other[:10-min(2,len(situ))]+situ[:max(0,10-len(other[:10-min(2,len(situ))]))]
 records.append({'order':n,'catalogue_id':p['catalogue_id'],'catalogue_name':p['catalogue_name'],'title':p['retail_name']+' | Wall Sculpture','price':p['price'],'marketplace_price':int(Decimal(p['price']).quantize(Decimal('1'),rounding=ROUND_HALF_UP)),'currency':'GBP','description':description,'condition':'New','category':'Household','website_url':p['website_url'],'sku':p['sku'],'photos':chosen,'all_website_photos':len(gallery),'status':'prepared'})
assert len(records)==40 and len({r['catalogue_id'] for r in records})==40
assets={a['url']:a for r in records for a in r['photos']}
image_dir=OUT/'upload-images';image_dir.mkdir(exist_ok=True)
def fetch(item):
 url,a=item
 with urlopen(Request(url,headers={'User-Agent':'BoldstoneCatalogueVerification/1.0'}),timeout=60) as response:data=response.read()
 im=Image.open(io.BytesIO(data));im.verify()
 im=Image.open(io.BytesIO(data));ext={'JPEG':'jpg','PNG':'png','WEBP':'webp'}[im.format]
 target=image_dir/(hashlib.sha256(url.encode()).hexdigest()[:18]+'.'+ext);target.write_bytes(data)
 return url,{'local_path':str(target),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'width':im.width,'height':im.height}
with ThreadPoolExecutor(max_workers=4) as pool:downloaded=dict(pool.map(fetch,assets.items()))
for r in records:r['photos']=[{**a,**downloaded[a['url']]} for a in r['photos']]
result={'created_utc':datetime.now(timezone.utc).isoformat(),'source_cutoff':fresh['event_cutoff'],'ordering':'Next included public products, alphabetical by catalogue name, excluding prior forty publications and one blocked draft','price_policy':'Marketplace whole-pound display rounded to nearest pound as in prior batch; exact catalogue price disclosed in description and on website.','records':records}
(OUT/'manifest.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print(json.dumps({'records':len(records),'unique_upload_images':len(assets),'image_placements':sum(len(r['photos']) for r in records),'bytes':sum(a['bytes'] for a in downloaded.values()),'titles':[r['title'] for r in records]},indent=2))
