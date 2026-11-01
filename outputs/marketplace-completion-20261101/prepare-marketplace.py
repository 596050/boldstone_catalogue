from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
from html.parser import HTMLParser
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor,as_completed
from PIL import Image
import hashlib,json,io,re,time
OUT=Path(__file__).resolve().parent
PREV=OUT.parent/'website-marketplace-refresh-20261031'
plan=json.loads((PREV/'website-final-plan.json').read_text())
old=json.loads((PREV/'catalogue-snapshot.json').read_text())
fresh=json.loads((OUT/'catalogue-snapshot.json').read_text())
assert fresh['event_cutoff']==old['event_cutoff']==plan['event_cutoff']
assert fresh['products']==old['products'] and fresh['images']==old['images']
prior=[]
for f in [PREV/'marketplace-receipts.json',OUT.parent/'marketplace-next30-20261031/publication-receipts.json',OUT.parent/'marketplace-ebay-expansion-20261031/publication-receipts.json']:
 prior.extend(json.loads(f.read_text()))
done={x['catalogue_id'] for x in prior};assert len(done)==len(prior)==80
blocked='BSI-B2D54C28FDA3'
class Plain(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,t):self.parts.append(t)
 def handle_endtag(self,t):
  if t in ['p','li']:self.parts.append('\n')
products=sorted([p for p in plan['products'] if p.get('public') and p['listing_decision']=='include' and p['catalogue_id'] not in done],key=lambda p:p['catalogue_name'].casefold())
assert len(products)==96
records=[];held=[];n=82
for p in products:
 parser=Plain();parser.feed(p['published_description_html'])
 description='\n\n'.join(s.strip() for s in ''.join(parser.parts).splitlines() if s.strip())
 description+='\n\nWebsite price: £'+p['price']+'. Full details, photographs and online ordering: '+p['website_url']
 assert not re.search(r'\b(GFRC|Jesmonite|plaster|concrete|Royal Mail)\b',description,re.I)
 gallery=p['website_gallery'];assert gallery and gallery[0]['url']==p['primary_url']
 if len(gallery)<=10: chosen=gallery
 else:
  situ=[a for a in gallery if a['role']=='in_situ'];other=[a for a in gallery if a['role']!='in_situ']
  chosen=other[:10-min(2,len(situ))]+situ[:max(0,10-len(other[:10-min(2,len(situ))]))]
 r={'order':41 if p['catalogue_id']==blocked else n,'catalogue_id':p['catalogue_id'],'catalogue_name':p['catalogue_name'],'title':p['retail_name']+' | Wall Sculpture','price':p['price'],'marketplace_price':int(Decimal(p['price']).quantize(Decimal('1'),rounding=ROUND_HALF_UP)),'currency':'GBP','description':description,'condition':'New','category':'Household','website_url':p['website_url'],'sku':p['sku'],'photos':chosen,'all_website_photos':len(gallery),'status':'prepared'}
 if p['catalogue_id']==blocked:held.append(r)
 else:records.append(r);n+=1
assert len(records)==95 and len(held)==1
assets={a['url']:a for r in records+held for a in r['photos']};folder=OUT/'upload-1500w';folder.mkdir(exist_ok=True)
base={'created_utc':datetime.now(timezone.utc).isoformat(),'source_cutoff':fresh['event_cutoff'],'prior_publications':len(done),'price_policy':'Whole-pound display; exact catalogue price in description','records':records,'existing_draft':held}
(OUT/'manifest-prepared.json').write_text(json.dumps(base,ensure_ascii=False,indent=2))
def get(it):
 url,a=it;u=url+('&' if '?' in url else '?')+'format=1500w'
 error=None
 for attempt in range(3):
  try:
   with urlopen(Request(u,headers={'User-Agent':'BoldstoneCatalogueUpload/1.0'}),timeout=45) as q:data=q.read()
   im=Image.open(io.BytesIO(data));im.verify();im=Image.open(io.BytesIO(data));ext={'JPEG':'jpg','PNG':'png','WEBP':'webp'}[im.format];dest=folder/(hashlib.sha256(u.encode()).hexdigest()[:18]+'.'+ext);dest.write_bytes(data)
   return url,{'local_path':str(dest),'upload_source_url':u,'upload_sha256':hashlib.sha256(data).hexdigest(),'upload_bytes':len(data),'upload_dimensions':[im.width,im.height]}
  except Exception as e:error=e;time.sleep(attempt+1)
 raise error
with ThreadPoolExecutor(max_workers=4) as pool:
 done_assets={}
 for result in as_completed([pool.submit(get,x) for x in assets.items()]):
  url,meta=result.result();done_assets[url]=meta
  if len(done_assets)%100==0:print('Downloaded',len(done_assets),'of',len(assets),flush=True)
for r in records+held:r['photos']=[{**a,**done_assets[a['url']]} for a in r['photos']]
(OUT/'manifest.json').write_text(json.dumps(base,ensure_ascii=False,indent=2))
print(json.dumps({'ready_new_listings':len(records),'existing_drafts':len(held),'unique_images':len(assets),'bytes':sum(a['upload_bytes'] for a in done_assets.values())}))
