"""Refresh all public native bindings, stopping if the site rate-limits reads."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,re,time

ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from check_wescover_public_presence import fetch
source=json.loads((ROOT/'outputs/platform-live-completion-20261104/wescover-public-verification.json').read_text())
targets=source['records']
assert len(targets)==len({r['sku'] for r in targets})==len({r['native_item_id'] for r in targets})==176
rows=[]
def save():
    good=[r for r in rows if r.get('identity_matches') and r.get('positive_available_offer')]
    summary=dict(status='PASS_ALL_176_PUBLIC_PRODUCTS' if len(good)==176 else 'PARTIAL_OR_NEEDS_ATTENTION',checked_utc=datetime.now(timezone.utc).isoformat(),expected=176,checked=len(rows),public_matches=len(good),native_mutations=0,scope='Unauthenticated public Product schema: stable native ID, exact seller SKU in description, Boldstone brand and positive available USD offer. Checkout, complete gallery and full description/pricing alignment are not certified.',records=rows)
    (OUT/'wescover-current-public-verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary
for b in targets:
    result=fetch(b['url']);p=next((p for p in result.get('structured_data',[]) if isinstance(p,dict) and p.get('@type')=='Product'),None)
    r=dict(sku=b['sku'],native_item_id=b['native_item_id'],url=b['url'],checked_utc=result['checked_utc'],http=result.get('http_status'))
    if p:
        o=p.get('offers',{})
        r.update(identity_matches=p.get('sku')==b['native_item_id'] and bool(re.search(r'\('+re.escape(b['sku'])+r'\)',p.get('description',''))) and p.get('brand',{}).get('name')=='Boldstone',price=o.get('price'),currency=o.get('priceCurrency'),availability=o.get('availability'),positive_available_offer=isinstance(o.get('price'),(int,float)) and o['price']>0 and o.get('priceCurrency')=='USD' and o.get('availability')=='https://schema.org/InStock')
    else:r['read_status']=result.get('status','NO_PRODUCT_SCHEMA')
    rows.append(r);s=save()
    if len(rows)%12==0 or r.get('http')==429:print(json.dumps({k:v for k,v in s.items() if k not in ['records','scope']}),flush=True)
    if r.get('http')==429:break
    time.sleep(.65)
print(json.dumps({k:v for k,v in save().items() if k!='records'}),flush=True)
