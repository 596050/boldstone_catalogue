"""Independently read public galleries and verify the narrowly appended photos."""
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote
import concurrent.futures, csv, json, urllib.request
OUT=Path(__file__).parent
load=lambda n:json.loads((OUT/n).read_text())
plan=load('website-photo-append-plan.json')
master=load('master-platform-values.json')
native={r['SKU']:r for r in csv.DictReader((OUT/'squarespace-after.csv').open(encoding='utf-8-sig',newline=''))}
class Page(HTMLParser):
    def __init__(self):super().__init__();self.images=[];self.product=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get('data-controller')=='ProductDetail':self.product=json.loads(a['data-context'])['product']
        if tag=='img' and 'product-gallery-slides-item-image' in a.get('class','').split():
            self.images.append(dict(url=a.get('data-image') or a.get('data-src'),alt=a.get('alt'),dimensions=a.get('data-image-dimensions')))
def canon(u):return unquote(urlparse(u).netloc+urlparse(u).path.replace('/content/v1/','/content/'))
def check(pair):
    i,p=pair;url=master[p['catalogue_id']]['pinterest_link']
    body=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BoldstoneCatalogueAudit/1.0'}),timeout=45).read().decode()
    page=Page();page.feed(body);assert page.product
    before=native[p['sku']];old_urls=before['Hosted Image URLs'].split()
    assert page.product['id']==before['Product ID [Non Editable]']
    assert page.product['title']==before['Title']
    assert float(page.product['price']['value'])==float(before['Price'])
    urls=[z['url'] for z in page.images]
    assert len(urls)==len(set(map(canon,urls)))
    assert [canon(u) for u in urls[:len(old_urls)]]==[canon(u) for u in old_urls]
    is_saved=(OUT/('website-photo-'+str(i+1).zfill(2)+'-save-clicked.json')).exists()
    if is_saved:
        assert len(urls)==len(old_urls)+1
        assert p['new_photo']['dropbox_content_hash'][:16] in urls[-1]
        assert page.images[-1]['alt']==p['new_photo']['alt_text']
    else:assert len(urls)==len(old_urls),(p['sku'],'Ambiguous native result; reconcile before retry')
    return dict(catalogue_id=p['catalogue_id'],sku=p['sku'],url=url,status='PASS_PUBLIC_APPEND_READBACK' if is_saved else 'UNCHANGED_PENDING_NATIVE_SAVE',old_count=len(old_urls),current_count=len(urls),primary_unchanged=canon(urls[0])==canon(old_urls[0]),existing_order_unchanged=True,price_unchanged=True,title_unchanged=True,product_id_unchanged=True,images=page.images,source_image_id=p['new_photo']['id'],source_hash=p['new_photo']['dropbox_content_hash'])
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(check,enumerate(plan['products'])))
receipt=dict(checked_at=datetime.now(timezone.utc).isoformat(),products=rows,verified_appends=sum(r['status']=='PASS_PUBLIC_APPEND_READBACK' for r in rows),pending=sum(r['status']!='PASS_PUBLIC_APPEND_READBACK' for r in rows),duplicates=0,unrelated_product_changes=0)
(OUT/'website-photo-public-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='products'}))
