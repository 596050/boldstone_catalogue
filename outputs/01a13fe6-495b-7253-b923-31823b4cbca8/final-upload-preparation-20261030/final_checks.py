from pathlib import Path
from collections import defaultdict
import csv,hashlib,html,json,urllib.request
OUT=Path(__file__).resolve().parent
plan=json.loads((OUT/'upload-plan.json').read_text());snapshot=json.loads((OUT/'catalogue-snapshot.json').read_text())
products={p['product_id']:p for p in plan['products']}
media=list(csv.DictReader((OUT/'selected-image-upload-manifest.csv').open(encoding='utf-8-sig')))
draft=list(csv.DictReader((OUT/'shopify-new-products-draft.csv').open(encoding='utf-8-sig')))
updates=list(csv.DictReader((OUT/'shopify-existing-variant-price-updates.csv').open(encoding='utf-8-sig')))
native=list(csv.DictReader(Path('/Users/tprice/Downloads/products_export_1 (1).csv').open(encoding='utf-8-sig')))
native_sku={r['Variant SKU']:r for r in native if r['Variant SKU']}
new_skus={p['sku'] for p in products.values() if p['sku_status']=='Proposed new unique SKU'}
assert not new_skus.intersection(native_sku)
assert not {r['Handle'] for r in draft}.intersection(r['Handle'] for r in native)
for row in draft:
    p=next(p for p in products.values() if p['sku']==row['Variant SKU'])
    assert p['listing_decision']=='include'
    assert float(row['Variant Price'])==p['price_gbp']
    assert row['Status'] in ('draft','') and row['Published'] in ('FALSE','')
    assert 'Image Src' not in row
for row in updates:
    src=native_sku[row['Variant SKU']]
    assert row['Handle']==src['Handle']
    for i in range(1,4):assert row[f'Option{i} Value']==src[f'Option{i} Value']
    p=next(p for p in products.values() if p['sku']==row['Variant SKU'])
    assert float(row['Variant Price'])==p['price_gbp']
assert len({(r['Handle'],r['Option1 Value']) for r in draft})==len(draft)
assert len({r['Variant SKU'] for r in draft+updates})==len(draft+updates)
for row in media:
    assert row['alt'].strip() and int(row['original_width'])>0 and int(row['original_height'])>0
    assert row['source']=='Dropbox' and row['image_id'].startswith('id:') and len(row['content_hash'])==64
    assert not row['public_import_url']
    p=products[row['product_id']];assert row['sku']==p['sku'] and row['shopify_handle']==p['shopify_handle']
    if row['primary']=='True':assert int(row['position'])==1

# Read the running application, not just the offline projection.
library=json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/library',timeout=90))
if isinstance(library,dict):
    entries=library.get('images') or library.get('assets')
    assert entries is not None,list(library)
else:entries=library
live={a['id']:a for a in entries}
for row in media:
    original=live[row['image_id']]['original']
    assert original['dimensions']==[int(row['original_width']),int(row['original_height'])]
    assert original['dropbox_content_hash']==row['content_hash']

selected=json.loads((OUT/'selected-images.json').read_text());numbers={x['image']['id']:x['number'] for x in selected}
def esc(x):return html.escape(str(x or ''),quote=True)
cards=[]
for p in products.values():
    if not p['publication_review']:continue
    photos=[]
    for row in media:
        if row['product_id']==p['product_id'] and row['publication_review']:
            photos.append('<figure><img src="http://127.0.0.1:8767/api/image?id='+esc(row['image_id'])+'&amp;size=thumb" alt="'+esc(row['alt'])+'"><figcaption>'+esc(row['publication_review'])+'<br><a href="'+esc(row['source_url'])+'">Dropbox image</a> | <a href="'+esc(row['folder_url'])+'">Folder</a></figcaption></figure>')
    cards.append('<section><h2>'+esc(p['name'])+'</h2><p><a href="'+esc(p['app_url'])+'">Open component in app</a> | <a href="'+esc(p['folder_url'])+'">Dropbox folder</a></p><ul>'+''.join('<li>'+esc(x)+'</li>' for x in p['publication_review'])+'</ul><div class="photos">'+''.join(photos)+'</div></section>')
(OUT/'publication-review.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>BOLDSTONE - remaining publication choices</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;background:#f7f6ef;color:#263c32}section{background:white;padding:24px;margin:24px 0;border:1px solid #bdc8b6;border-radius:12px}.photos{display:flex;gap:20px;flex-wrap:wrap}figure{max-width:300px;margin:0}img{max-width:100%;height:240px;object-fit:contain}a{color:#3c6847}h1{font-family:Georgia}</style><h1>Remaining publication choices</h1><p>All selected images now have alt text and original dimensions. These existing decisions and photo questions remain separate. No selections were changed by preparation.</p>'+''.join(cards)+'</html>')
report={'status':'PASS','native_new_draft_products':len({r['Handle'] for r in draft}),
 'native_new_draft_variants':len(draft),'native_existing_price_updates':len(updates),
 'source_options_preserved_in_existing_csv':True,'new_handles_do_not_collide_with_local_export':True,
 'proposed_skus_do_not_collide_with_local_export':True,'images_have_alt_and_dimensions':True,
 'live_app_original_dimensions_and_hashes_verified':len({r['image_id'] for r in media}),
 'publication_review_components':len(cards),'no_platform_mutations':True}
(OUT/'final-upload-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
