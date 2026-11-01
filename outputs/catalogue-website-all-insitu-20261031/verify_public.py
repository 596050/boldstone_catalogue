"""Read every public product and the hosted image URLs independently of the import."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from decimal import Decimal
from html.parser import HTMLParser
from urllib.request import urlopen,Request
import json,time,re
OUT=Path(__file__).resolve().parent
plan=json.loads((OUT/'website-final-plan.json').read_text());products=[p for p in plan['products'] if p.get('public')]
class Page(HTMLParser):
 def __init__(self):super().__init__();self.meta={};self.images=[];self.gallery=[];self.alts=[];self.description=[];self.description_depth=0;self.description_images=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='meta':self.meta[a.get('property',a.get('name',''))]=a.get('content','')
  if tag=='div':
   if self.description_depth:self.description_depth+=1
   elif 'product-description' in a.get('class','').split():self.description_depth=1
  if tag=='img':
   url=(a.get('data-src') or a.get('src') or '').split('?')[0]
   self.images.append(url)
   if self.description_depth:self.description_images.append(url)
   if 'product-gallery-slides-item-image' in a.get('class','').split():
    self.gallery.append(url);self.alts.append(a.get('alt',''))
 def handle_endtag(self,tag):
  if tag=='div' and self.description_depth:self.description_depth-=1
 def handle_data(self,data):
  if self.description_depth:self.description.append(data)
def page(p):
 for attempt in range(3):
  try:
   with urlopen(Request(p['website_url'],headers={'User-Agent':'BoldstoneCatalogueVerification/1.0','Cache-Control':'no-cache'}),timeout=30) as r:text=r.read().decode()
   doc=Page();doc.feed(text);want=[a['url'].split('?')[0] for a in p['website_gallery']];found=doc.gallery
   assert Decimal(doc.meta['product:price:amount'])==Decimal(p['price']),('price',doc.meta.get('product:price:amount'),p['price'])
   assert doc.meta.get('og:title') in (p['retail_name'],p['retail_name']+' \u2014 boldstone'),('title',doc.meta.get('og:title'))
   assert want==found,('gallery order',len(want),len(found),len(set(want)-set(found)),len(set(found)-set(want)))
   assert found[0]==p['primary_url'].split('?')[0],('primary',found[0])
   assert not doc.description_images,('inline images remain',doc.description_images)
   description=' '.join(doc.description)
   assert not re.search(r'\b(GFRC|Jesmonite|plaster|concrete|moulding paste|Royal Mail|Tracked 48)\b',description+' '+' '.join(doc.alts),re.I),'restricted public copy'
   assert 'Suitable for outdoor use' in description and 'Keyhole' in description and 'French cleats' in description
   assert 'In a setting' not in description
   assert p['product_id'] in text
   return {'catalogue_id':p['catalogue_id'],'url':p['website_url'],'status':'PASS','price':p['price'],'in_situ_photos':len(p['website_in_situ']),'gallery_photos':len(want)}
  except Exception as e:
   if attempt<2:time.sleep(3*(attempt+1));continue
   return {'catalogue_id':p['catalogue_id'],'url':p['website_url'],'status':'FAIL','error':str(e)}
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for n,f in enumerate(as_completed(pool.submit(page,p) for p in products),1):
  results.append(f.result())
  if n%25==0:print(json.dumps({'public_pages_checked':n,'failed':sum(r['status']!='PASS' for r in results)}),flush=True)
result={'status':'PASS_ALL_PUBLIC_PAGES' if all(r['status']=='PASS' for r in results) else 'FAIL','verified_utc':datetime.now(timezone.utc).isoformat(),'pages':len(results),'gallery_placements':sum(r.get('gallery_photos',0) for r in results),'in_situ_placements':sum(r.get('in_situ_photos',0) for r in results),'results':results}
(OUT/'public-website-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='results'}))
