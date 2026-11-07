"""Search retained family images for missing Saatchi originals; read headers only."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.request import urlopen
import sys,json

ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'catalogue-review/scripts')]
from check_saatchi_original_headers import check
from prepare_saatchi_catalogue import native_artwork_bindings

read=lambda p:json.loads(p.read_text())
save=lambda n,d:(OUT/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
source=read(OUT/'app-source.json')
scope=set(read(ROOT/'outputs/platform-live-completion-20261104/scope.json')['publication_skus'])
bindings=native_artwork_bindings(ROOT/'outputs/catalogue-marketplace-publication-20261101/saatchi-current/primary-draft-receipts.json')
products={}
for p in source['products']:
    fields={f['key']:f['value'] for f in p['fields']+p['listing_fields']}
    sku=fields['Seller SKU']
    if sku in scope and sku not in bindings:products[p['id']]=p
assert len(scope)==176 and len(bindings)==112 and len(products)==64
with urlopen('http://127.0.0.1:8767/api/library',timeout=120) as r:library=json.load(r)
images={i['id']:i for i in library['images']}
save('search-source.json',dict(app_revision=source['revision'],library_images=len(images),native_bindings=len(bindings),missing_products=len(products),families=sorted({p['family'] for p in products.values()}),checked_utc=datetime.now(timezone.utc).isoformat()))
checks={}
for p in [ROOT/'outputs/platform-completion-20261105/saatchi-additional-original-headers.json',ROOT/'outputs/platform-live-completion-20261104/saatchi-original-headers.json']:
    for r in read(p):checks[(r['photo_id'],r['expected_content_hash'])]=r
candidates=[]
for photo in read(ROOT/'outputs/platform-completion-20261105/saatchi-unselected-original-candidates.json')['records']:
    if photo['product_id'] not in products or photo['image_id'] not in images:continue
    current=images[photo['image_id']]
    if photo['original']['dropbox_content_hash']!=current.get('original',{}).get('dropbox_content_hash'):continue
    candidates.append(dict(product_id=photo['product_id'],sku=next(f['value'] for f in products[photo['product_id']]['listing_fields']+products[photo['product_id']]['fields'] if f['key']=='Seller SKU'),title=products[photo['product_id']]['retail_name'],image=current,association_basis='Earlier family search, refreshed against current retained library; visual product/finish review still required'))
# Include newly retained photographs associated with an exact missing component.
seen={(c['product_id'],c['image']['id']) for c in candidates}
for image in images.values():
    if not image.get('original',{}).get('dropbox_content_hash'):continue
    owners=set(image.get('component_ids',[]))|set(image.get('default_component_ids',[]))|set(image.get('product_ids',[]))
    for pid in owners&products.keys():
        if (pid,image['id']) in seen:continue
        seen.add((pid,image['id']))
        p=products[pid]
        candidates.append(dict(product_id=pid,sku=next(f['value'] for f in p['fields']+p['listing_fields'] if f['key']=='Seller SKU'),title=p['retail_name'],image=image,association_basis='Current retained library association; visual product/finish review still required'))
save('saatchi-candidate-associations.json',candidates)
new={c['image']['id']:c['image'] for c in candidates if (c['image']['id'],c['image']['original']['dropbox_content_hash']) not in checks}
save('saatchi-header-targets.json',list(new.values()))
results=[]
print(json.dumps(dict(candidate_associations=len(candidates),candidate_products=len({c['product_id'] for c in candidates}),new_distinct_originals=len(new))),flush=True)
with ThreadPoolExecutor(max_workers=2) as pool:
    futures={pool.submit(check,photo):photo['id'] for photo in new.values()}
    for f in as_completed(futures):
        results.append(f.result());save('saatchi-new-original-headers.json',results)
        if len(results)%10==0 or len(results)==len(new):print(json.dumps(dict(headers_checked=len(results),of=len(new),qualifying=sum(r.get('landscape_uploader_dimensions',False) or r.get('portrait_published_guidance_dimensions',False) for r in results))),flush=True)
for r in results:checks[(r['photo_id'],r['expected_content_hash'])]=r
qualified=[]
for c in candidates:
    i=c['image'];h=checks.get((i['id'],i['original']['dropbox_content_hash']))
    if h and (h.get('landscape_uploader_dimensions') or h.get('portrait_published_guidance_dimensions')):qualified.append({**c,'header':h})
save('saatchi-qualifying-photo-review.json',qualified)
summary=dict(checked_utc=datetime.now(timezone.utc).isoformat(),missing_products=64,candidate_associations=len(candidates),new_originals_header_checked=len(results),qualifying_associations=len(qualified),products_with_pixel_candidates=len({c['product_id'] for c in qualified}),full_originals_retained=0,native_mutations=0,scope='Original pixel dimensions only. Visual identity, full-product coverage and native acceptance remain required.')
save('saatchi-photo-search-summary.json',summary);print(json.dumps(summary),flush=True)
