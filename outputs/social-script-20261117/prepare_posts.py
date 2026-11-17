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
COPY={
 'BSI-93ADE7C4103D':('A sweep of light across a square.','Acanthus Twin Leaves brings broad, rising curves to a compact square panel. Its white surface catches the light along the raised edges, letting the shadows become part of the design.','A white square Acanthus Twin Leaves wall relief with broad raised curves sweeping upward from the lower edge.'),
 'BSI-70BDE00F2855':('An ancient mark, given depth.','Ancient Spiral follows a curling line across a textured square panel. The raised spiral draws the eye inward, while the white finish brings each ridge and recess into view.','A textured white square Ancient Spiral wall relief with a raised curling spiral and rounded bands.'),
 'BSI-8CD6A48141ED':('A long line of movement.','Deco Dune Wave sets flowing vertical ribs across a tall, narrow panel. The repeating curves catch the changing light, bringing a gentle rhythm to an interior or garden wall.','A tall, narrow white Deco Dune Wave relief with a series of smooth, flowing vertical ribs.'),
 'BSI-F8398FA248EE':('The shape of an echo.','Echo Rhythm II carries a sequence of curved ridges across a textured square. The repeating relief creates a rhythm of light and shadow. It can be displayed alone or alongside Echo Rhythm I, which is sold separately.','A textured white square Echo Rhythm II wall relief with repeated raised arcs spreading from the left edge.'),
 'BSI-FE10273D3655':('Movement held still.','Frozen Fish Relief arranges a sequence of small raised forms along a slender vertical panel. Each projection catches the light, creating a playful, measured rhythm from top to bottom.','A narrow, vertical white Frozen Fish Relief panel with a repeated sequence of projecting fish-like forms.')
}
records=[]
for p in snapshot['products']:
 pid=p['catalogue_id'];d=downloads[pid];m=mapping[pid]
 assert p['photo']['primary_eligible'] and not p['photo']['withheld_reasons']
 assert hashlib.sha256(Path(d['media_path']).read_bytes()).hexdigest()==d['sha256']
 opening,description,alt=COPY[pid]
 common=p['title']+'\n\n'+opening+'\n\n'+description
 common+='\n\nDimensions: '+p['fields']['Dimensions / depth']+'.\nMade from a gypsum-based material. Suitable for outdoor use and indoor display.'
 common+='\n\nOne individual sculpture. All designs can be customised, and new commissions can be developed with designer Sally Price.'
 links={platform:m['pinterest_link']+'?'+urlencode({'utm_source':platform,'utm_medium':'social','utm_campaign':'component_sculptures_20261117','utm_content':p['sku']}) for platform in ['facebook','instagram','linkedin']}
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
(OUT/'posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'prepared':len(records),'titles':[r['title'] for r in records],'official_product_pages_verified':len(verified)},ensure_ascii=False))
