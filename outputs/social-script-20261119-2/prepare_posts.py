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
COPY={'BSI-5020FF47923F': ('A palm drawn in three long curves.', 'Egyptian Palm IV extends a botanical motif into a tall, narrow relief. Three sweeping raised bands rise across the panel, letting light trace their edges and the shadows between them.', 'A tall narrow white Egyptian Palm IV relief with three long raised bands curving towards the upper edge.'), 'BSI-53239DE28BCA': ('A small panel with a vineyard story.', 'Gleneagles Vine I brings a cluster of grapes and finely detailed leaves to a square relief. A broad curved division gives the composition space, balancing the small botanical details with a simple sculptural shape.', 'A square Gleneagles Vine I relief with a cluster of raised grapes, three detailed vine leaves and a broad curved division.'), 'BSI-8AC0376F7DEF': ('A shoal moving through moonlit curves.', 'Moon Fish Wave II sets small raised fish between broad curved forms and a curled spiral. Its textured surface and changes in depth turn the square panel into a quiet pattern of light, movement and shadow.', 'A white square Moon Fish Wave II relief with small raised fish between broad curves and a spiral in the lower left corner.'), 'BSI-41E5370B1314': ('A spiral that fills its frame.', 'Lunar Phase II carries one generous raised spiral across a textured square panel. The curve winds into a small centre, with a broad outer arc giving the relief a sense of slow, continuous movement.', 'A textured square Lunar Phase II relief with a broad raised spiral winding into a small curled centre.'), 'BSI-2AFD94C9F459': ('A rhythm of ridges for changing light.', 'Raked Spiral II follows broad, rippling ridges across a textured square panel. The lines gather and open as they turn, giving the surface a soft sense of movement and a changing pattern of shadows.', 'A white square Raked Spiral II relief with broad parallel rippling ridges and a rough textured surface.')}
records=[]
for p in snapshot['products']:
 pid=p['catalogue_id'];d=downloads[pid];m=mapping[pid]
 assert p['photo']['primary_eligible'] and not p['photo']['withheld_reasons']
 assert hashlib.sha256(Path(d['media_path']).read_bytes()).hexdigest()==d['sha256']
 opening,description,alt=COPY[pid]
 common=p['title']+'\n\n'+opening+'\n\n'+description
 common+='\n\nDimensions: '+p['fields']['Dimensions / depth'].split('; four-panel arrangement')[0]+'.\nMade from a gypsum-based material. Suitable for outdoor use and indoor display.'
 common+='\n\nOne individual sculpture. All designs can be customised, and new commissions can be developed with designer Sally Price.'
 links={platform:m['pinterest_link']+'?'+urlencode({'utm_source':platform,'utm_medium':'social','utm_campaign':'component_sculptures_20261119_2','utm_content':p['sku']}) for platform in ['facebook','instagram','linkedin']}
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
