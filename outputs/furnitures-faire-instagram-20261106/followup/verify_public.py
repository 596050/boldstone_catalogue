"""Independently read public product pages; never submit orders or mutations."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
import urllib.request, hashlib, json, re, html

OUT=Path(__file__).parent
PRIOR=OUT.parent
read=lambda p:json.loads(p.read_text())
plan=read(PRIOR/'furnitures-upload-plan.json')
targets={r['sku']:r for r in plan['records']}
bindings=read(PRIOR/'furnitures-native-bindings.json')
assert len(bindings)==len(targets)==176
assert len({b['native_id'] for b in bindings})==176

def verify(binding):
    target=targets[binding['sku']]
    receipt=dict(catalogue_id=binding['catalogue_id'],sku=binding['sku'],native_id=binding['native_id'],url=binding['public_url'],checked_utc=datetime.now(timezone.utc).isoformat())
    try:
        req=urllib.request.Request(binding['public_url'],headers={'User-Agent':'Boldstone catalogue verification/1.0'})
        with urllib.request.urlopen(req,timeout=30) as r:
            body=r.read();receipt.update(http_status=r.status,final_url=r.url)
        assert receipt['http_status']==200 and receipt['final_url']==binding['public_url']
        text=body.decode('utf-8')
        products=[]
        for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',text,re.S):
            data=json.loads(block)
            nodes=data if isinstance(data,list) else data.get('@graph',[data])
            products.extend(n for n in nodes if n.get('@type')=='Product')
        assert len(products)==1, 'Expected one public Product schema'
        p=products[0];offer=p['offers']
        assert p['name']==target['title'], 'Public title mismatch'
        assert p['sku']==binding['native_id'], 'Public native ID mismatch'
        assert Decimal(str(offer['price']))==Decimal(str(target['price_gbp'])), 'Public price mismatch'
        assert offer['priceCurrency']=='GBP' and offer['availability']=='https://schema.org/InStock'
        assert p['image']==target['image_urls'], 'Public full gallery mismatch'
        norm=lambda v:' '.join(html.unescape(v).split())
        assert norm(p['description'])==norm(target['description']), 'Public description mismatch'
        assert p['brand']['name']=='Boldstone Sculpture'
        receipt.update(status='PASS_PUBLIC_PRODUCT',price_gbp=float(offer['price']),currency='GBP',availability='InStock',image_count=len(p['image']),description_sha256=hashlib.sha256(p['description'].encode()).hexdigest(),response_sha256=hashlib.sha256(body).hexdigest())
    except Exception as e:
        receipt.update(status='NEEDS_ATTENTION',error_type=type(e).__name__,error=str(e))
    return receipt

rows=[]
def save():
    rows.sort(key=lambda r:r['sku'])
    errors=[r for r in rows if r['status']!='PASS_PUBLIC_PRODUCT']
    report=dict(status='PASS_ALL_176_PUBLIC_PRODUCTS' if len(rows)==176 and not errors else 'IN_PROGRESS_OR_NEEDS_ATTENTION',checked_utc=datetime.now(timezone.utc).isoformat(),scope='Public page and Product structured data: exact title, native ID, asking price, GBP, InStock, complete ordered selected gallery and full description. No checkout/payment tested.',products_checked=len(rows),products_passed=len(rows)-len(errors),errors=len(errors),images_verified=sum(r.get('image_count',0) for r in rows),records=rows)
    (OUT/'furnitures-public-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report
with ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(verify,b) for b in bindings]
    for f in as_completed(futures):
        rows.append(f.result());report=save()
        if len(rows)%25==0:print(json.dumps({k:report[k] for k in ['products_checked','products_passed','errors']}),flush=True)
print(json.dumps({k:v for k,v in save().items() if k!='records'}))
