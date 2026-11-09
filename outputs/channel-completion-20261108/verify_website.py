"""Public title/price/stock and unchanged carousel URL verification after import."""
import concurrent.futures
import csv
from datetime import datetime, timezone
import html
import json
import re
import urllib.request
from pathlib import Path
OUT=Path(__file__).parent
audit=json.loads((OUT.parent/'product-social-approval-20261108/pinterest-public-audit.json').read_text())
before={r['Variant ID [Non Editable]']:r for r in csv.DictReader((OUT/'squarespace-before.csv').open(encoding='utf-8-sig',newline=''))}
def check(p):
    result={'id':p['id'],'title':p['title'],'link':p['link']}
    try:
        req=urllib.request.Request(p['link'],headers={'User-Agent':'BoldstoneCatalogueAudit/1.0'})
        with urllib.request.urlopen(req,timeout=35) as r:source=r.read(6_000_000).decode();result['http']=r.status
        schemas=[]
        for raw in re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>',source,re.S|re.I):
            try:
                parsed=json.loads(raw);schemas.extend(parsed if isinstance(parsed,list) else [parsed])
            except ValueError:pass
        product=next((x for x in schemas if x.get('@type')=='Product'),None)
        if not product:
            product=next((x for y in schemas for x in y.get('@graph',[]) if x.get('@type')=='Product'),{})
        name=re.sub(r'\s+[—–-]\s+boldstone$','',html.unescape(product.get('name','')),flags=re.I)
        result['observed_title']=name;result['title_matches']=name==p['title']
        offers=product.get('offers',[]);offers=offers if isinstance(offers,list) else [offers]
        result['offers']=[{k:o.get(k) for k in ['price','priceCurrency','availability','sku']} for o in offers]
        amount,currency=p['feed_price'].split()
        result['price_matches']=any(float(str(o.get('price',-1)))==float(amount) and o.get('priceCurrency')==currency for o in offers)
        result['stock_matches']=any('InStock' in str(o.get('availability')) for o in offers)
        result['gallery_links_present']=all(u.split('?')[0].replace('http://','https://') in source.replace('http://','https://') for u in before[p['id']]['Hosted Image URLs'].split() if u.startswith('http'))
    except Exception as e:result['error']=type(e).__name__+': '+str(e)
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:products=list(pool.map(check,audit['products']))
summary={'checked_utc':datetime.now(timezone.utc).isoformat(),'products':len(products),'errors':sum('error'in p for p in products),'titles_matching':sum(p.get('title_matches',False) for p in products),'prices_matching':sum(p.get('price_matches',False) for p in products),'stock_matching':sum(p.get('stock_matches',False) for p in products)}
(OUT/'website-public-after.json').write_text(json.dumps({'summary':summary,'products':products},indent=2)+'\n')
print(json.dumps(summary))
