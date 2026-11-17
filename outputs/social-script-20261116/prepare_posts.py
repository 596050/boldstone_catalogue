"""Freeze this authorized new batch with original bytes and verified site URLs."""
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
 'BSI-9C7406B46836':('Leaf and moon, drawn in relief.','Acanthus Moon brings tall leaf-like curves together with sweeping arcs in a rectangular panel. The white surface lets the raised edges and their shadows carry the design.','A rectangular white Acanthus Moon wall relief with tall leaf-like forms and curved bands sweeping in from each side.'),
 'BSI-EFBAEB31C2B1':('A small spiral with a generous presence.','Ammonite Petite II sets a textured curling form against a rectangular panel. A smooth outer sweep frames the spiral, giving the relief a changing rhythm as light moves across it.','A pale white rectangular Ammonite Petite II wall relief with a textured curling spiral and a broad smooth sweep around its outer edge.'),
 'BSI-9278986A1A89':('A curve held between light and shadow.','Bone Spiral I brings a broad, smooth curved band into a compact wall panel. The recessed centre and raised outer edge create a simple sculptural play of depth and light.','A pale white Bone Spiral I wall relief with a broad curved band and a recessed circular form near the right edge.'),
 'BSI-CAB0D722062D':('The rhythm of a palm, in clean lines.','Deco Palm II pairs a series of slender raised arcs with a central upright form. Its white surface catches the surrounding light, bringing crisp shadows and a flowing botanical rhythm to the wall.','A white Deco Palm II relief photographed in cool light, with raised curved ribs and a central upright form casting strong shadows.'),
 'BSI-818D745F1357':('A quiet shift across a square.','Lunar Phase IV places a broad raised form within a textured square panel. A deep curved division and a sloping edge give the piece a calm presence that changes with the light.','A textured white square Lunar Phase IV relief with a broad raised wedge-like form and a deep curved division along its left side.')
}
records=[]
for p in snapshot['products']:
 pid=p['catalogue_id'];d=downloads[pid];m=mapping[pid]
 assert p['photo']['primary_eligible'] and not p['photo']['withheld_reasons']
 assert not p['surface_effect']
 assert hashlib.sha256(Path(d['media_path']).read_bytes()).hexdigest()==d['sha256']
 opening,description,alt=COPY[pid]
 common=p['title']+'\n\n'+opening+'\n\n'+description
 common+='\n\nDimensions: '+p['fields']['Dimensions / depth']+'.\nMaterial: Made from a gypsum-based material.\nSuitable for outdoor use and indoor display.'
 if p['fields']['Availability']=='Made to order':common+='\n\nMade to order. Dispatch within 10 working days; delivery time is additional.'
 common+='\n\nAll designs can be customised, and completely new commissions can be developed with designer Sally Price.'
 links={platform:m['pinterest_link']+'?'+urlencode({'utm_source':platform,'utm_medium':'social','utm_campaign':'component_sculptures_20261116','utm_content':p['sku']}) for platform in ['facebook','instagram','linkedin']}
 captions={'facebook':common+'\n\nView this sculpture: '+links['facebook'],
           'instagram':common+'\n\nExplore the collection through the link in our bio.\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture #GardenArt',
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
 assert status==200 and products,(p['title'],'No official product data')
 product=products[0];offers=product['offers'];offers=offers if isinstance(offers,list) else [offers]
 offer=next(x for x in offers if x.get('price') is not None)
 assert offer['priceCurrency']=='GBP' and float(offer['price'])==p['price_gbp'],(p['title'],offer)
 assert p['title'] in product['name'],(p['title'],product['name'])
 return {'catalogue_id':p['catalogue_id'],'url':url,'title':product['name'],'price_gbp':float(offer['price']),'status':status,'verified_utc':datetime.now(timezone.utc).isoformat(),'html_sha256':hashlib.sha256(body.encode()).hexdigest()}
with ThreadPoolExecutor(max_workers=5) as pool:verified=list(pool.map(verify,records))
(OUT/'website-verification.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n')
(OUT/'posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'prepared':len(records),'titles':[r['title'] for r in records],'official_product_pages_verified':len(verified)},ensure_ascii=False))
