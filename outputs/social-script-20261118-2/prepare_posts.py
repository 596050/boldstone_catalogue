"""Prepare five new posts from checked catalogue records and original photos."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
import hashlib
import json
import re
import urllib.request

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
snapshot=json.loads((OUT/'catalogue-snapshot.json').read_text())
downloads={r['catalogue_id']:r for r in json.loads((OUT/'original-download-receipts.json').read_text())}
mapping=json.loads((ROOT/'outputs/channel-completion-20261108/master-platform-values.json').read_text())
COPY={'BSI-F61AE4921B6B': ('A spiral with room to breathe.', 'Deco Timeless Spiral lets one broad curve travel across a gently textured panel. The smooth raised form winds into a small coil, with the white finish drawing light along its edges.', 'A white rectangular Deco Timeless Spiral relief with a broad smooth raised spiral curling into a small centre.'), 'BSI-8BB94D9D6C27': ('A pattern that draws you closer.', 'Fingerprint Rings II carries a sequence of curved ridges across a square panel. The lines gather towards one edge like an enlarged fingerprint, turning a familiar trace into a pattern of light and shadow. It can be paired with Fingerprint Rings III, which is sold separately.', 'A white square Fingerprint Rings II relief with concentric curved ridges gathering towards the right edge.'), 'BSI-6581D83760F1': ('Botanical lines, held in relief.', 'Leaf Silhouette gives long, tapered leaf forms a strong sculptural outline. Raised edges and fine surface texture bring the white panel into focus as the light moves across it.', 'A white square Leaf Silhouette relief with long tapered raised leaf forms and lightly textured surfaces.'), 'BSI-8CC6C8AABCB7': ('A wave held in a vertical line.', 'Frozen Deco Wave I sets broad, flowing curves along a tall, narrow panel. Strong raised edges cast changing shadows, giving this white relief a sense of movement. It can be displayed with Frozen Deco Wave II, which is sold separately.', 'A tall narrow white Frozen Deco Wave I relief with two broad curved raised waves and deep shadows along their edges.'), 'BSI-8C0D9152DF73': ('A moonlike curve, close to hand.', 'Lunar Phase I carries a broad spiral across a textured square panel. The curve rises from its rough surface and gathers into a small curled centre, with the white finish keeping the changing light and shadow in view.', 'A textured white square Lunar Phase I relief with a broad raised spiral curling into a small central coil.')}
records=[]
for p in snapshot['products']:
 pid=p['catalogue_id'];d=downloads[pid];m=mapping[pid]
 assert p['photo']['primary_eligible'] and not p['photo']['withheld_reasons']
 assert hashlib.sha256(Path(d['media_path']).read_bytes()).hexdigest()==d['sha256']
 opening,description,alt=COPY[pid]
 common=p['title']+'\n\n'+opening+'\n\n'+description
 common+='\n\nDimensions: '+p['fields']['Dimensions / depth']+'.\nMade from a gypsum-based material. Suitable for outdoor use and indoor display.'
 common+='\n\nOne individual sculpture. All designs can be customised, and new commissions can be developed with designer Sally Price.'
 links={platform:m['pinterest_link']+'?'+urlencode({'utm_source':platform,'utm_medium':'social','utm_campaign':'component_sculptures_20261118_2','utm_content':p['sku']}) for platform in ['facebook','instagram','linkedin']}
 captions={'facebook':common+'\n\nShop this sculpture through the product tag or visit: '+links['facebook'],
           'instagram':common+'\n\nTap the product tag to shop this sculpture.\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture #GardenArt',
           'linkedin':common+'\n\nFor homes, gardens and design projects. View this sculpture: '+links['linkedin']+'\n\n#WallSculpture #Boldstone #SallyPrice #InteriorDesign #GardenDesign'}
 assert len(captions['instagram'])<2200 and len(captions['linkedin'])<3000
 records.append({**d,'sku':p['sku'],'price_gbp':p['price_gbp'],'website_url':m['pinterest_link'],'commerce_variant_id':m['pinterest_id'],'alt_text':alt,'captions':captions,'tracked_urls':links,'status':'PREPARED_NOT_PUBLISHED'})

def verify(p):
 request=urllib.request.Request(p['website_url'],headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(request,timeout=40) as r:
  body=r.read().decode();status=r.status;url=r.url
 (OUT/(p['catalogue_id']+'-product.html')).write_text(body)
 products=[]
 def visit(obj):
  if isinstance(obj,list):
   for child in obj:visit(child)
  elif isinstance(obj,dict):
   if obj.get('@type')=='Product':products.append(obj)
   for key in ['@graph','mainEntity']:visit(obj.get(key))
 for script in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',body,re.S|re.I):
  try:visit(json.loads(script))
  except json.JSONDecodeError:pass
 assert status==200 and products
 product=products[0];offers=product['offers'];offers=offers if isinstance(offers,list) else [offers]
 offer=next(x for x in offers if x.get('price') is not None)
 assert offer['priceCurrency']=='GBP' and float(offer['price'])==p['price_gbp'],(p['title'],offer)
 assert p['title'] in product['name'],(p['title'],product['name'])
 return {'catalogue_id':p['catalogue_id'],'url':url,'title':product['name'],'price_gbp':float(offer['price']),'status':status,'verified_utc':datetime.now(timezone.utc).isoformat(),'html_sha256':hashlib.sha256(body.encode()).hexdigest()}
with ThreadPoolExecutor(max_workers=5) as pool:verified=list(pool.map(verify,records))
(OUT/'website-verification.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n')
matches={r['catalogue_id']:r for r in json.loads((OUT/'commerce-matches.json').read_text())}
for r in records:
 match=matches[r['catalogue_id']]
 r.update(native_commerce_title=match['name'],native_commerce_price_text=match['price_text'])
(OUT/'posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'prepared':len(records),'titles':[r['title'] for r in records],'official_product_pages_verified':len(verified)},ensure_ascii=False))
