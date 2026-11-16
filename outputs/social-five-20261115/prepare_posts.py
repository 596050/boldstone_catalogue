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
copy = {'BSI-ADD5F3BEFCF5': ('Circles that invite a closer look.', 'Ancient Cup Ring builds a simple circular motif into a textured square relief. Raised rings and a recessed centre catch the light, recalling the cup-and-ring marks found in ancient rock art.', 'A textured white square Ancient Cup Ring wall relief with raised concentric rings around a recessed central cup.'), 'BSI-87B48040E454': ('A slender panel with a flowing rhythm.', 'Two small spirals interrupt long, curving ribs in Deco Dune Spiral. Its narrow proportions bring movement and shadow to an entrance, a garden wall or a quiet interior.', 'A tall narrow white Deco Dune Spiral wall relief with flowing vertical ribs and two small curled spirals.'), 'BSI-F13E2BF8C6C8': ('A palm reduced to flowing lines.', 'Egyptian Palm II turns a stylised botanical motif into broad, sweeping curves. The raised white contours create a bold play of light and shadow across a tall rectangular panel.', 'A white rectangular Egyptian Palm II wall relief with broad curved bands sweeping upwards, photographed on a pale wall with strong side shadows.'), 'BSI-E21193597976': ('The movement of a fan, held in relief.', 'Folded Fan brings two sweeps of curved ridges together in a white rectangular panel. Fine edges and deeper folds draw the eye through the surface, changing as the light moves.', 'A white rectangular Folded Fan wall relief with two intersecting sweeps of curved ribs, photographed on a pale wall.'), 'BSI-FBD125528AEC': ('A quiet circle with a changing edge.', 'Lunar Ring sets a broad circular form inside a square relief. An offset curved band catches light along one edge, giving a simple shape a calm sculptural presence.', 'A white square Lunar Ring relief with a broad circular centre and an offset curved band along its left and upper edges.')}
companions = {'BSI-E21193597976': 'Coordinates with Cultivation Folds Relief, Fold and Unfold IV and Folded Swan Wing. Each sculpture is sold separately.'}
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
             'utm_campaign':'component_sculptures_20261115','utm_content':p['sku']})
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
