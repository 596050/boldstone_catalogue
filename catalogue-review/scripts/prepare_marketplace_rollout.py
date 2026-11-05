"""Prepare narrowly scoped channel updates; does not publish or accept fees."""
import hashlib
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from channel_content import values, complete_description, marketplace_title, appearance, product_type

D = lambda x: Decimal(str(x))
ceil = lambda x: float(D(x).quantize(D('.01'), rounding=ROUND_CEILING))

def main(out):
    out.mkdir(parents=True, exist_ok=True)
    app = json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/specifications'))
    old = json.loads((ROOT/'outputs/faire-gumtree-20261104/faire-upload.json').read_text())
    plan = json.loads((ROOT/'outputs/platform-profit-pricing-stacking-20261104/profit-pricing-plan.json').read_text())
    prices = {r['catalogue_id']: r for r in plan['records']}
    images = json.loads((ROOT/'outputs/faire-gumtree-20261104/current-public-images.json').read_text())
    products = {p['id']:p for p in app['products']}
    drafts = {r['sku']:r for r in json.loads((ROOT/'outputs/catalogue-marketplace-publication-20261101/chairish-current/draft-receipts.json').read_text())}
    xml = urllib.request.urlopen('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml').read()
    tree=ET.fromstring(xml)
    rates={e.attrib['currency']:D(e.attrib['rate']) for e in tree.iter() if 'currency' in e.attrib}
    rate_date=next(e.attrib['time'] for e in tree.iter() if 'time' in e.attrib)
    fx=rates['USD']/rates['GBP']
    (out/'ecb-reference.xml').write_bytes(xml)
    # The published alias map is authoritative for exact content hashes.
    faire_rows=[]; bonanza_rows=[]; gumtree=[]; chairish=[]; changed=[]
    for binding in old['records']:
        p=products[binding['catalogue_id']]; f=values(p); price=prices[p['id']]
        assert p['listing_decision']=='include' and f['Seller SKU']==binding['sku']
        assert D(p['costing']['pricing']['marked_up_price'])==D(price['baseline_price_gbp']), (p['id'],'price changed; refresh pricing model')
        assert D(p['costing']['manufacturing_cost'])==D(price['cost_gbp'])
        primary=p['photos']['primary_listing']['image_id']
        ordered=list(dict.fromkeys([primary]+[i['id'] for i in p['photos']['listing']['images']]+[i['id'] for i in p['photos']['in_situ']['images']]))
        missing=[i for i in ordered if i not in images]
        assert not missing, (p['id'],'current selected images missing published URLs',missing)
        for im in p['photos']['listing']['images']+p['photos']['in_situ']['images']:
            h=im.get('original',{}).get('dropbox_content_hash')
            assert not h or h==images[im['id']]['dropbox_content_hash']
        urls=[images[i]['url'] for i in ordered]
        if ordered!=binding['image_ids']: changed.append(p['id'])
        description=complete_description(p,f['Seller SKU'],dispatch_days=10)
        title=marketplace_title(p,limit=80)
        faire_rows.append([f['Seller SKU'],marketplace_title(p,limit=100),product_type(p),description,'GBP',price['faire']['asking'],price['faire']['retail_reference'],1,1,'Physically available in the UK','Within 10 working days; delivery transit time additional',' '.join(urls),binding['website_url'],'Boldstone',appearance(p),f['Dimensions / depth'],f['Weight']])
        gt_desc=re.sub(r'^Availability:.*$','Availability: Finished sculpture physically available in the UK; inspection and collection by arrangement.',description,flags=re.M)
        gt_desc=re.sub(r'^Dispatch time:.*$','Dispatch time: If Gumtree Delivery is offered and selected, the item will be packaged and sent within seven calendar days of payment. For separately arranged delivery, agree the dispatch date before purchase. Carrier transit time is additional.',gt_desc,flags=re.M)
        gt_desc=re.sub(r'^Delivery:.*$','Delivery: Inspection and collection are available by arrangement. If Gumtree Delivery is selected, its checkout charge applies. Otherwise agree any delivery service, charge and timing before purchase.',gt_desc,flags=re.M)
        gt_desc+='\nCollection: Court Essington, Midford Road, Midford, Bath BA2 7BX, by arrangement.'
        gumtree.append(dict(catalogue_id=p['id'],sku=f['Seller SKU'],title=marketplace_title(p,limit=100),description=gt_desc,price_gbp=price['baseline_price_gbp'],seller_type='Business',collection_location='Court Essington, Midford Road, Midford, Bath BA2 7BX',image_ids=ordered,image_urls=urls,stock_confirmed_by_owner=True,native_status='NOT_PUBLISHED'))
        # USD price protects current retail receipt under explicitly provisional ceilings.
        # No advertising upgrade is enabled. Shipping/packing require an order quote.
        retained=1-(D('.11')+D('.05'))*D('1.20')
        target=D(price['baseline_price_gbp'])*fx/D('.97')
        usd=ceil((target+D('.25')*D('1.20')+D('.60')+D('.36'))/retained)
        assert (D(usd)*retained-D('1.26'))*D('.97')/fx>=D(price['baseline_price_gbp'])
        # Pick the primary, then in-situ, then other listing images within CSV's four-photo limit.
        four=list(dict.fromkeys([primary]+[i['id'] for i in p['photos']['in_situ']['images']]+ordered))[:4]
        bonanza_rows.append([f['Seller SKU'],title,usd,description,553,1,*([images[i]['url'] for i in four]+['']*4)[:4],'[[Condition:New]][[Brand:Boldstone]]','Wall Sculptures','TRUE'])
        chairish.append(dict(catalogue_id=p['id'],sku=f['Seller SKU'],native_id=drafts[f['Seller SKU']]['id'],url=drafts[f['Seller SKU']]['url'],asking_usd=price['chairish']['asking_usd'],auction_reserve_usd=price['chairish']['auction_reserve_usd'],native_status='PRICE_NOT_YET_UPDATED'))
    assert len(faire_rows)==len(bonanza_rows)==len(gumtree)==len(chairish)==176
    assert len({r[0] for r in bonanza_rows})==len({r[1] for r in bonanza_rows})==176
    ready=json.loads((ROOT/'outputs/platform-profit-pricing-20261104/gumtree-ready.json').read_text())
    service=ready['service_ad']; service['collection_location']='Court Essington, Midford Road, Midford, Bath BA2 7BX'
    service['description']+='\nConsultations and collection by arrangement at Court Essington, Midford Road, Midford, Bath BA2 7BX.'
    def write(name,data): (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    write('app-current.json',app)
    write('faire-update.json',dict(headers=old['headers'],rows=faire_rows,status='PREPARED; FAIRE_BUILD_PENDING; GENUINE_RETAIL_ALIGNMENT_REQUIRED'))
    write('bonanza-import.json',dict(headers=['id','title','price','description','category','quantity','image1','image2','image3','image4','trait','booth_category','force_update'],rows=bonanza_rows,currency='USD',ecb_date=rate_date,usd_per_gbp=str(fx),fee_assumptions=dict(base_commission=.11,payment_processing_reserve=.05,fee_tax_reserve=.20,fx_reserve=.03,fixed_transaction_usd=.25,processing_fixed_reserve_usd=.60,one_year_listing_reserve_usd=.36),scope='176 product drafts only; shipping quoted separately; no free-shipping promise; no edition cap',limitations='Monthly fees beyond one year and setup fee are business overheads, not per-sale protection. Processing and tax reserves are provisional; verify payout provider before activation.'))
    write('gumtree-ready.json',dict(records=gumtree,service_ad=service,products=176,service_adverts=1,terms_confirmation_pending=True,native_published=0))
    write('chairish-price-updates.json',dict(records=chairish,native_updated=0))
    write('verification.json',dict(status='PASS',app_revision=app['revision'],publication_products=176,changed_photo_selections_since_original_packet=changed,images=sum(len(r['image_ids']) for r in gumtree),unique_images=len({i for r in gumtree for i in r['image_ids']}),native_price_writes=0,native_publications=0,prepared_at=datetime.now(timezone.utc).isoformat()))
    body=['<!doctype html><meta charset="utf-8"><title>Gumtree adverts for review</title><style>body{font:16px/1.5 system-ui;max-width:1100px;margin:40px auto;padding:20px}article{border-top:1px solid #ccc;padding:20px 0}img{height:160px;width:160px;object-fit:contain}pre{white-space:pre-wrap;font:inherit}</style><h1>176 Gumtree products and one service advert</h1><p>Prepared for Court Essington, Midford Road, Midford, Bath BA2 7BX. Not published.</p>']
    for r in gumtree+[service]:
        body.append('<article><h2>'+html.escape(r['title'])+'</h2><p>'+html.escape(r['sku'])+(' · £%.2f'%r['price_gbp'] if 'price_gbp' in r else ' · Quote per commission')+'</p>'+''.join('<img loading="lazy" src="'+html.escape(u,quote=True)+'">' for u in r['image_urls'][:20])+'<pre>'+html.escape(r['description'])+'</pre></article>')
    (out/'gumtree-review.html').write_text(''.join(body))
    print(json.dumps(dict(products=176,changed_photo_records=len(changed),app_revision=app['revision'])))

if __name__=='__main__': main(Path(sys.argv[1]).resolve())
