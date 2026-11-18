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
COPY={'BSI-BCAB636141CC': ('A single curve, held in relief.', 'Acanthus Frond (Left) carries a broad, sweeping curve across a compact square panel. Light follows the raised edge, giving this white botanical relief a quiet sense of movement.', 'A white square Acanthus Frond (Left) wall relief with a broad curved band sweeping from the left edge towards the lower right.'), 'BSI-3ABEAEE767E8': ('Botanical rhythm, drawn in relief.', 'Egyptian Palm I sets repeated sweeping curves across an upright panel. The smooth raised bands catch the light while the spaces between them create a changing pattern of shadows.', 'An upright white Egyptian Palm I wall relief with repeated broad curved bands rising from the lower left across the panel.'), 'BSI-98997871B7EC': ('A small landscape of moving lines.', 'Dune Ripple I turns the flowing lines of sand into a compact wall relief. Its vertical ribs bend gently across the white panel, bringing a rhythm of light and shadow to a home or garden.', 'A narrow upright white Dune Ripple I wall relief with a sequence of gently undulating vertical ribs.'), 'BSI-7B6291B7C7F9': ('Structure in the shadows.', 'Strata Relief sets intersecting ridges against a textured square surface. The raised lines divide the panel into irregular planes, giving light and shadow a different path across each part of the design.', 'A textured white square Strata Relief with intersecting raised ridges dividing the surface into irregular angular planes.'), 'BSI-F7ADC5AEE4E0': ('A flowing line, given depth.', 'Brancusi Meander II brings a sculpted wave to a tall, narrow panel. Its flowing central ridge creates a strong play of light and shadow. Display it alone or alongside Brancusi Meander I, which is sold separately.', 'A tall narrow white Brancusi Meander II wall relief with a flowing central raised wave and deep shadows along its curved sides.')}
records=[]
for p in snapshot['products']:
 pid=p['catalogue_id'];d=downloads[pid];m=mapping[pid]
 assert p['photo']['primary_eligible'] and not p['photo']['withheld_reasons']
 assert hashlib.sha256(Path(d['media_path']).read_bytes()).hexdigest()==d['sha256']
 opening,description,alt=COPY[pid]
 common=p['title']+'\n\n'+opening+'\n\n'+description
 common+='\n\nDimensions: '+p['fields']['Dimensions / depth']+'.\nMade from a gypsum-based material. Suitable for outdoor use and indoor display.'
 common+='\n\nOne individual sculpture. All designs can be customised, and new commissions can be developed with designer Sally Price.'
 links={platform:m['pinterest_link']+'?'+urlencode({'utm_source':platform,'utm_medium':'social','utm_campaign':'component_sculptures_20261118','utm_content':p['sku']}) for platform in ['facebook','instagram','linkedin']}
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
