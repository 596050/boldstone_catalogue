"""Prepare five authorised posts for each of the three existing social accounts."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
import concurrent.futures
import hashlib
import json
import re
import urllib.request

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
snapshot = json.loads((OUT / 'catalogue-snapshot.json').read_text())
downloads = {r['catalogue_id']:r for r in json.loads((OUT / 'original-download-receipts.json').read_text())}
mapping = json.loads((ROOT / 'outputs/channel-completion-20261108/master-platform-values.json').read_text())
copy = {
 'BSI-C02D6DF365D3': (
  'A botanical form, shaped by light.',
  'Acanthus Bloom gathers broad curves into a crisp square relief. The white surface keeps the focus on the raised outline and soft shadows, bringing a botanical detail to an interior or garden wall.',
  'A white square Acanthus Bloom wall relief with a tall leaf-like central outline and smaller curved forms, mounted on a pale wall.'),
 'BSI-EC5966EA0C7A': (
  'A palm drawn in light and shadow.',
  'Deco Palm I pairs a fan of curved ridges with a simple rectangular panel. Directional light gives its white contours a strong, changing rhythm.',
  'A white Deco Palm I wall relief with curved ribs fanning across a rectangular panel, photographed on a pale blue-grey wall with strong shadows.'),
 'BSI-0D2FEACDB98D': (
  'Nature leaves its own repeating lines.',
  'Fingerprint Rings I follows flowing, closely spaced ridges across a white square panel. The shallow relief changes with the light, bringing each contour into focus in turn.',
  'A square white Fingerprint Rings I relief with closely spaced curved ridges flowing diagonally across its surface.'),
 'BSI-992BA62AA818': (
  'A small shoal beneath a sweeping moon.',
  'Moon Fish Wave I sets a sequence of raised fish-like forms between broad curved bands. In White, the movement comes from the relief itself and the shadows it casts.',
  'A white Moon Fish Wave I wall panel with small raised fish-like shapes between broad sweeping curved bands.'),
 'BSI-93FC0B4F78DA': (
  'A quiet spiral for a changing light.',
  'Lunar Phase III brings a curling raised form into a textured square panel. Its broad outer curve and compact spiral create a small focal point that changes as light moves across the wall.',
  'A textured white square Lunar Phase III relief with a raised central spiral and a broad curved sweep around its lower and left sides.')}
companions = {
 'BSI-EC5966EA0C7A':'Coordinates with Deco Palm II and Deco Timeless Spiral. Each sculpture is sold separately.',
 'BSI-0D2FEACDB98D':'Coordinates with Fingerprint Rings II and III. Each sculpture is sold separately.',
 'BSI-992BA62AA818':'Coordinates with Moon Fish Wave II. Each sculpture is sold separately.',
 'BSI-93FC0B4F78DA':'Coordinates with Lunar Phase I, II and IV. Each sculpture is sold separately.'}
records = []
for p in snapshot['products']:
    pid = p['catalogue_id']; d = downloads[pid]; m = mapping[pid]
    assert p['photo']['primary_eligible'] and not p['photo']['withheld_reasons']
    assert not p['surface_effect']
    assert hashlib.sha256(Path(d['media_path']).read_bytes()).hexdigest() == d['sha256']
    opening, description, alt = copy[pid]
    common = p['title'] + '\n\n' + opening + '\n\n' + description
    common += '\n\nDimensions: ' + p['fields']['Dimensions / depth'] + '.\nMaterial: Made from a gypsum-based material.\nSuitable for outdoor use and indoor display.'
    if pid in companions: common += '\n\n' + companions[pid]
    if p['fields']['Availability'] == 'Made to order':
        common += '\n\nMade to order. Dispatch within 10 working days; delivery time is additional.'
    common += '\n\nAll designs can be customised, and completely new commissions can be developed with designer Sally Price.'
    links = {platform:m['pinterest_link']+'?'+urlencode({'utm_source':platform, 'utm_medium':'social',
             'utm_campaign':'component_sculptures_20261114','utm_content':p['sku']})
             for platform in ['linkedin','facebook','instagram']}
    captions = {
       'instagram':common+'\n\nTap the product tag to view this sculpture. Browse the collection through the link in our bio.\n\n#Boldstone #SallyPrice #WallSculpture #ReliefSculpture #GardenArt',
       'facebook':common+'\n\nView this sculpture: '+links['facebook'],
       'linkedin':common+'\n\nFor homes, gardens and design projects. View this sculpture: '+links['linkedin']+'\n\n#WallSculpture #Boldstone #SallyPrice #InteriorDesign #GardenDesign'}
    assert len(captions['instagram']) < 2200
    assert len(captions['linkedin']) < 3000
    records.append({**d,'sku':p['sku'],'price_gbp':p['price_gbp'],
         'website_url':m['pinterest_link'],'commerce_variant_id':m['pinterest_id'],
         'alt_text':alt,'captions':captions,'tracked_urls':links,
         'status':'PREPARED_NOT_PUBLISHED'})
(OUT/'posts.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')

def verify(p):
    req=urllib.request.Request(p['website_url'],headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=45) as response:
        body=response.read().decode(); status=response.status; final_url=response.url
    (OUT/(p['catalogue_id']+'-product.html')).write_text(body)
    scripts=re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',body,re.S|re.I)
    products=[]
    def visit(x):
        if isinstance(x,list):
            for y in x:visit(y)
        elif isinstance(x,dict):
            if x.get('@type')=='Product':products.append(x)
            for k in ['@graph','mainEntity']:visit(x.get(k))
    for script in scripts:
        try:visit(json.loads(script))
        except json.JSONDecodeError:pass
    assert status==200 and products,(p['title'],status,'No Product data')
    product=products[0]; offers=product['offers'];offers=offers if isinstance(offers,list) else [offers]
    offer=next((x for x in offers if x.get('price') is not None),offers[0])
    assert float(offer['price'])==p['price_gbp'],(p['title'],offer)
    assert offer.get('priceCurrency')=='GBP'
    assert p['title'] in product['name'],(p['title'],product['name'])
    return {'catalogue_id':p['catalogue_id'],'title':product['name'],'status':status,'url':final_url,
            'price_gbp':float(offer['price']),'availability':offer.get('availability'),
            'html_sha256':hashlib.sha256(body.encode()).hexdigest(),'verified_utc':datetime.now(timezone.utc).isoformat()}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    verified=list(pool.map(verify,records))
(OUT/'website-verification.json').write_text(json.dumps(verified,ensure_ascii=False,indent=2)+'\n')
for p in records:print(p['title'],p['price_gbp'],{k:len(v) for k,v in p['captions'].items()})
print('Verified product pages:',len(verified))
