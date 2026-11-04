"""Read public product JSON and compare exact mapped catalogue records."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,NS,R

class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_starttag(self,tag,attrs):
        if tag=='br':self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('li','p','div','h1','h2'):self.parts.append('\n')
def plain(s):
    p=Text();p.feed(s or '');return ''.join(p.parts)
def normal_url(u):
    u=urlsplit(u);return (u.netloc.casefold(),u.path.replace('/content/v1/','/content/'))

def main(out):
    out.mkdir(exist_ok=True)
    baseline=out.parent
    app=json.loads((baseline/'app.json').read_text());snap=json.loads((baseline/'catalogue-snapshot.json').read_text())
    products={p['id']:p for p in app['products']};projected={p['id']:p for p in snap['products']}
    pointer=json.loads((baseline/'source.json').read_text());assert hashlib.sha256(Path(pointer['path']).read_bytes()).hexdigest()==pointer['sha256']
    book=Xlsx(pointer['path']);path=book.paths['Wall Sculptures']
    rels={r.get('Id'):r.get('Target') for r in ET.fromstring(book.parts['xl/worksheets/_rels/'+path.rsplit('/',1)[-1]+'.rels'])}
    links={r.get('ref'):rels.get(r.get('{'+R+'}id')) for r in ET.fromstring(book.parts[path]).findall('s:hyperlinks/s:hyperlink',NS)}
    bindings=[]
    for row in range(8,189):
        pid=book.value('Wall Sculptures','AA'+str(row));url=links.get('AW'+str(row));public=book.value('Upload Plan','F'+str(row))=='Public'
        if not url:continue
        assert urlsplit(url).hostname=='boldstonesculpture.com'
        bindings.append({'id':pid,'row':row,'url':url,'expected_public':public,
            'native_id':book.value('Upload Plan','G'+str(row)),'variant_id':book.value('Upload Plan','H'+str(row))})
    # Native image URLs are resolved only through retained exact ID/hash upload
    # mappings. Unknown URLs remain explicitly unresolved.
    image_bindings={}
    for name in ['catalogue-website-all-insitu-20261031','moonshell-lava-channel-refresh-20261031']:
        plan=json.loads((ROOT/'outputs'/name/'website-final-plan.json').read_text())
        for p in plan['products']:
            for im in p.get('website_gallery',[]):
                key=normal_url(im['url']);value=(im['id'],im['content_hash'])
                assert key not in image_bindings or image_bindings[key]==value
                image_bindings[key]=value
    def fetch(b):
        result=dict(b,checked_utc=datetime.now(timezone.utc).isoformat())
        try:
            url=b['url']+'?format=json'
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Boldstone read-only catalogue audit)','Accept':'application/json'})
            with urllib.request.urlopen(request,timeout=40) as response:
                d=json.load(response)
            item=d.get('item')
            if not item:return {**result,'status':'NO_PRODUCT_ITEM'}
            return {**result,'status':'READ_PUBLIC_PRODUCT','item':{k:item.get(k) for k in ['id','title','excerpt','workflowState','fullUrl','assetUrl','variants','items']}}
        except urllib.error.HTTPError as e:return {**result,'status':'HTTP_ERROR','http_status':e.code}
        except Exception as e:return {**result,'status':'READ_FAILED','error':type(e).__name__+': '+str(e)}
    if '--reuse-readbacks' in sys.argv:
        results=json.loads((out/'public-product-readbacks.json').read_text())
        assert {(r['id'],r['url'],r['native_id'],r['variant_id']) for r in results}=={(r['id'],r['url'],r['native_id'],r['variant_id']) for r in bindings}
    else:
        results=[]
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures=[pool.submit(fetch,b) for b in bindings]
            for f in as_completed(futures):
                results.append(f.result())
                if len(results)%30==0:print('Read',len(results),'of',len(bindings),'public product URLs',flush=True)
        (out/'public-product-readbacks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    issues=[];checks=[]
    for result in sorted(results,key=lambda r:r['row']):
        p=products[result['id']];pid=p['id'];fields={f['key']:f['value'] for f in p['fields']+p['listing_fields']}
        if result['status']!='READ_PUBLIC_PRODUCT':
            if result['expected_public']:issues.append({'id':pid,'name':p['name'],'issue':'PUBLIC_PRODUCT_NOT_READ','result':result})
            continue
        item=result['item'];native=item['id'];variants=item.get('variants') or []
        matched=[v for v in variants if v['id']==result['variant_id']]
        if native!=result['native_id'] or len(matched)!=1:
            issues.append({'id':pid,'name':p['name'],'url':result['url'],'issue':'NATIVE_ID_MISMATCH','expected':result['native_id'],'actual':native});continue
        v=matched[0];text=plain(item['excerpt']);expected_title=fields['Retail name']
        effective_price=v['salePriceMoney'] if v.get('onSale') else v['priceMoney']
        price=Decimal(effective_price['value'])
        c={'id':pid,'name':p['name'],'url':result['url'],'public':result['expected_public'],'native_id_verified':True,
            'title':item['title'],'expected_title':expected_title,'price_gbp':str(price),'expected_price_gbp':p['costing']['pricing']['marked_up_price'],
            'sku':v.get('sku'),'expected_sku':fields['Seller SKU'],'packed_kg_estimate':p['us_shipping']['packed_kg'],
            'website_weight_lb':v.get('weight'),'website_dimensions':{key:v.get(key) for key in ('len','width','height')},
            'photo_count':len(item.get('items') or [])}
        def issue(kind,**kwargs):issues.append({'id':pid,'name':p['name'],'url':result['url'],'issue':kind,**kwargs})
        if item['title']!=expected_title:issue('TITLE_DIFFERS',observed=item['title'],expected=expected_title)
        if effective_price['currency']!='GBP' or abs(price-Decimal(str(c['expected_price_gbp'])))>Decimal('.005'):issue('PRICE_DIFFERS',observed=effective_price,expected=c['expected_price_gbp'])
        if v.get('sku')!=fields['Seller SKU']:issue('SKU_DIFFERS',observed=v.get('sku'),expected=fields['Seller SKU'])
        if all(not v.get(key) for key in ('len','width','height')):issue('PACKED_DIMENSIONS_ZERO',observed=c['website_dimensions'],expected_estimate_cm=p['us_shipping']['packed_cm'])
        expected_lb=Decimal(str(p['us_shipping']['packed_kg']))/Decimal('0.45359237')
        if abs(Decimal(str(v.get('weight',0)))-expected_lb)>Decimal('.015'):issue('PACKED_WEIGHT_DIFFERS',observed_lb=v.get('weight'),expected_estimate_lb=float(expected_lb))
        model=re.search(r'(?m)^Model:\s*(.*)$',text)
        if model and model.group(1).strip()!=fields['Retail name']+' ('+fields['Seller SKU']+')':issue('DESCRIPTION_MODEL_DIFFERS',observed=model.group(1).strip(),expected=fields['Retail name']+' ('+fields['Seller SKU']+')')
        actual_labels=dict(re.findall(r'(?m)^([^\n:]{1,35}):\s*([^\n]+)$',text))
        expected_labels=dict(re.findall(r'(?m)^([^\n:]{1,35}):\s*([^\n]+)$',fields['Description']))
        for label in ['Brand','Product type','Quantity supplied','Material','Surface effect','Dimensions','Weight','Use','Fixings','Availability','Custom design','Dispatch time','Delivery','Companion pieces','Colour / appearance']:
            if actual_labels.get(label)!=expected_labels.get(label):issue('DESCRIPTION_FIELD_DIFFERS',field=label,observed=actual_labels.get(label),expected=expected_labels.get(label))
        selected_ids=list(dict.fromkeys(([projected[pid]['photos']['primary_id']] if projected[pid]['photos']['primary_id'] else [])+projected[pid]['photos']['listing_ids']+projected[pid]['photos']['in_situ_ids']))
        observed=[];unmapped=[]
        for photo in item.get('items') or []:
            key=normal_url(photo.get('assetUrl') or '')
            if key in image_bindings:observed.append(image_bindings[key][0])
            else:unmapped.append(photo.get('assetUrl'))
        c['unmapped_photo_urls']=unmapped;c['mapped_photo_ids']=observed
        # Only complete exact URL bindings support a definitive gallery claim.
        if not unmapped:
            if set(observed)!=set(selected_ids):issue('GALLERY_SELECTION_DIFFERS',extra_ids=sorted(set(observed)-set(selected_ids)),missing_ids=sorted(set(selected_ids)-set(observed)))
            if selected_ids and observed and observed[0]!=selected_ids[0]:issue('PRIMARY_DIFFERS',observed=observed[0],expected=selected_ids[0])
        else:issue('GALLERY_MAPPING_INCOMPLETE',unmapped_count=len(unmapped))
        checks.append(c)
    from collections import Counter
    report={'checked_utc':max(r['checked_utc'] for r in results),'analysed_utc':datetime.now(timezone.utc).isoformat(),'source_app_snapshot':snap['created_utc'],
        'requested_urls':len(bindings),'public_products_checked':sum(c['public'] for c in checks),'hidden_products_read':sum(not c['public'] for c in checks),
        'response_counts':dict(Counter(r['status']+(' '+str(r.get('http_status')) if r.get('http_status') else '') for r in results)),
        'issue_counts':dict(Counter(i['issue'] for i in issues)),'checks':checks,'issues':issues,
        'scope':'Read-only public JSON and exact stored product/variant/image mappings. No checkout, platform account, product save or image download.'}
    (out/'website-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('issues','checks')},indent=2))

if __name__=='__main__':main(Path(sys.argv[1]).resolve())
