"""Restore an empty showroom from current catalogue records and selected photos."""
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
OUT=Path(__file__).parent;ROOT=OUT.parents[1]
sys.path[:0]=[str(ROOT/'catalogue-review'),str(ROOT/'catalogue-review/scripts')]
from channel_content import values,complete_description,marketplace_title,appearance
from delete_dropbox import connection
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=60) as r:return json.load(r)
spec=get('/api/specifications');coverage=get('/api/coverage')['products']
master=json.loads((OUT/'master-platform-values.json').read_text())
published={p['id'] for p in json.loads((OUT.parent/'product-social-approval-20261108/pinterest-public-audit.json').read_text())['products']}
products=[p for p in spec['products'] if master[p['id']].get('pinterest_id') in published]
assert len(products)==176
def fetch(p):
    detail=get('/api/products/'+p['id']);ids=set(coverage[p['id']]['listing']['image_ids']+coverage[p['id']]['in_situ']['image_ids'])
    photos={i['id']:i for i in detail['images'] if i['id'] in ids}
    assert set(photos)==ids,(p['id'],ids-set(photos))
    return photos
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:sets=list(pool.map(fetch,products))
images={}
for photos in sets:
    for iid,image in photos.items():
        if iid in images:assert images[iid]['original'].get('dropbox_content_hash')==image['original'].get('dropbox_content_hash')
        images[iid]=image
(OUT/'current-selected-photo-metadata.json').write_text(json.dumps(images,ensure_ascii=False)+'\n')
public=json.loads((ROOT/'outputs/faire-gumtree-20261104/current-public-images.json').read_text())
urls={};need=[]
for iid,image in images.items():
    expected=image.get('original',{}).get('dropbox_content_hash');old=public.get(iid)
    if old and expected and old.get('dropbox_content_hash')==expected:urls[iid]=old['url']
    else:need.append((iid,expected))
temporary=[]
with connection(ROOT) as (db,_):
    for iid,expected in need:
        native=db.files_get_temporary_link(iid)
        assert native.metadata.id==iid and expected and native.metadata.content_hash==expected
        urls[iid]=native.link
        temporary.append(dict(id=iid,hash=expected,created_utc=datetime.now(timezone.utc).isoformat()))
headers=['SKU Number','Style ID','Option Code','Size','Name','Description','Option Name','Wholesale (GBP)','Retail (GBP)','Type','Category','Season','Delivery Date','HS Code','Country of Origin','Minimum Quantity','Inventory Count','Image URL','Vendor']
records=[];rows=[]
for p in products:
    m=master[p['id']];v=values(p);photo=coverage[p['id']];primary=photo['primary_listing']['image_id']
    ids=list(dict.fromkeys([primary]+photo['listing']['image_ids']+photo['in_situ']['image_ids']))
    assert primary in photo['listing']['image_ids'] and all(i in urls for i in ids)
    sku=v['Seller SKU'];assert sku==m['SKU']==m['brandboom_sku']
    wholesale=m['brandboom_wholesale_gbp'];assert isinstance(wholesale,(int,float)) and wholesale>0
    description=complete_description(p,sku,dispatch_days=10)
    title=marketplace_title(p,limit=120)
    row=[sku,sku,'STANDARD','One sculpture',title,description,appearance(p),wholesale,m.get('brandboom_native_retail_gbp') or None,'Home Decor','Wall Sculpture','Year-round',None,None,None,1,None,','.join(urls[i] for i in ids),'Boldstone']
    assert len(row)==len(headers);rows.append(row)
    records.append(dict(catalogue_id=p['id'],sku=sku,title=title,image_ids=ids,image_count=len(ids),wholesale_gbp=wholesale))
assert len({r['sku'] for r in records})==176
now=get('/api/specifications')
for before,after in zip(spec['products'],now['products']):
    assert before['id']==after['id'] and values(before)==values(after) and before['listing_decision']==after['listing_decision'],'Catalogue changed during preparation'
plan=dict(prepared_utc=datetime.now(timezone.utc).isoformat(),showroom_id='111089',expected_existing_products=0,records=records,headers=headers,rows=rows,temporary_image_sources=temporary,app_revision=spec['revision'],pricing_basis='Restore the existing master brandboom_wholesale_gbp values. No new retail-price proposal applied.',stock_basis='No numerical stock quantity inferred; inventory omitted.',image_basis='Complete current Listing and In situ selections; permanent URLs used only when the stored Dropbox content hash matches, otherwise fresh short-lived Dropbox links with ID/hash verification.')
(OUT/'brandboom-restore-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'products':len(records),'distinct_images':len(images),'image_placements':sum(r['image_count'] for r in records),'fresh_temporary_links':len(temporary),'existing_products':0}))
