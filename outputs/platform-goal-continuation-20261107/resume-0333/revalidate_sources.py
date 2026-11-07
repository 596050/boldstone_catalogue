import hashlib,json,re,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
OLD=OUT.parent/'resume-0220'
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx
pointer=json.loads((ROOT/'sculpture-catalogue/current-master.json').read_text())['current_app_review_workbook']
assert hashlib.sha256(Path(pointer['path']).read_bytes()).hexdigest()==pointer['sha256']
book=Xlsx(pointer['path']);sheet='Wall Sculptures'
headers={book.value(sheet,a):re.sub(r'\d','',a) for a in book.cells[sheet] if re.fullmatch(r'[A-Z]+7',a)}
rows={book.value(sheet,'AQ'+str(n)):n for n in range(8,189)}
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:app=json.load(response)
(OUT/'app-specifications.json').write_text(json.dumps(app,ensure_ascii=False)+'\n')
products={p['id']:p for p in app['products']}
queue=json.loads((OLD/'ebay-remaining-metadata-queue.json').read_text())
for p in queue:
    row=rows[p['sku']]
    get=lambda key:book.value(sheet,headers[key]+str(row))
    assert get('Product ID')==p['catalogue_id'] and get('ebay_catalogue_title')==p['title']
    desc=get('ebay_description').replace('Within 10 working days.','Within 3 working days.')
    desc=re.sub(r'Dispatch time: Within 10 working days','Dispatch time: Within 3 working days',desc)
    assert desc==p['description'],p['sku']
    for field,key in [('ebay_price_gbp','price_gbp'),('ebay_width_cm','width_cm'),('ebay_height_cm','height_cm'),('ebay_depth_cm','depth_cm')]:
        assert get(field)==p[key],(p['sku'],field)
    product=products[p['catalogue_id']]
    ids=[product['photos']['primary_listing']['image_id']]
    for kind in ['listing','in_situ']:
        for image in product['photos'].get(kind,{}).get('images',[]):
            if image['id'] not in ids:ids.append(image['id'])
    assert ids[:24]==p['desired_gallery_ids'],('Photo selection changed',p['sku'])
frozen=json.loads((OLD/'workbook/app-specifications.json').read_text())
fields=['retail_name','fields','listing_fields','costing','photos','listing_decision']
relevant=lambda data:{p['id']:{key:p[key] for key in fields} for p in data['products']}
assert relevant(frozen)==relevant(app),'App product contents changed; reconcile before edits'
receipt=dict(status='PASS_CURRENT_TARGETS_AND_APP_CONTENTS_UNCHANGED',checked_utc=datetime.now(timezone.utc).isoformat(),
             queued_targets_verified=len(queue),app_records_verified=len(products),source_workbook_sha256=pointer['sha256'],
             source_app_revision=app['revision'],frozen_app_revision=frozen['revision'],
             revision_change_explained='Native observation workbook updates changed the overall source revision. All 181 relevant app records and all 52 eBay target packets compare exactly.',
             mutations=0)
(OUT/'source-revalidation.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
