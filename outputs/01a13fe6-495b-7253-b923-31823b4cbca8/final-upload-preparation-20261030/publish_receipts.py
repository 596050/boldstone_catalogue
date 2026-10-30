"""Publish narrow workbook/upload references only after Dropbox byte readback."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,zipfile,os
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt=read(OUT/'dropbox-receipt.json');verification=read(OUT/'verification.json');snapshot=read(OUT/'catalogue-snapshot.json');plan=read(OUT/'upload-plan.json')
assert receipt['status']=='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert sha(OUT/'catalogue_wall_sculptures.xlsx')==receipt['sha256_readback']==verification['sha256']
target=ROOT/'sculpture-catalogue/current-master.json';raw=target.read_bytes();pointer=json.loads(raw)
assert pointer['register_sha256']==snapshot['source']['register_sha256']
before_path=OUT/'current-master-before-workbook-pointer.json'
assert not before_path.exists();before_path.write_bytes(raw)
pointer['current_app_review_workbook']={
 'status':'PASS_CURRENT181_METADATA_MARKUP_AND_UPLOAD_PLAN_DROPBOX_BYTE_READBACK',
 'path':str(OUT/'catalogue_wall_sculptures.xlsx'),'sha256':verification['sha256'],
 'app_snapshot_utc':snapshot['created_utc'],'event_cutoff':snapshot['event_cutoff'],
 'active_options':181,'sheets':7,'unique_images':snapshot['summary']['unique_images'],'image_rows':snapshot['summary']['image_rows'],
 'specification_fields':1267,'specification_and_listing_copy_rows':1991,'manufacturing_cost_rows':181,
 'hyperlinks':verification['hyperlinks'],'source_register_sha256':snapshot['source']['register_sha256'],
 'source_gallery_sha256':snapshot['source']['gallery_sha256'],
 'verification':str(OUT/'verification.json'),'verification_sha256':sha(OUT/'verification.json'),
 'dropbox_receipt':str(OUT/'dropbox-receipt.json'),'dropbox_receipt_sha256':sha(OUT/'dropbox-receipt.json'),
 'dropbox':receipt['current'],
 'scope':'Current app specifications, descriptions and delivery policy; all retained image associations; selected-photo alt text and original dimensions; editable manufacturing costs and markup prices; product/variant/SKU upload plan. Workbook edits do not update the app.'}
pointer['current_upload_preparation']={'status':plan['status'],'path':str(OUT/'upload-plan.json'),
 'sha256':sha(OUT/'upload-plan.json'),'counts':plan['counts'],'snapshot_utc':snapshot['created_utc'],
 'review_page':str(OUT/'publication-review.html'),'validation':str(OUT/'final-upload-validation.json'),
 'platform_products_published':False,'image_media_uploaded_to_destination':False}
temporary=target.with_name(target.name+'.upload-preparation.tmp')
temporary.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n')
assert target.read_bytes()==raw, 'Another publisher changed the pointer'
os.replace(temporary,target)
assert read(target)['current_app_review_workbook']['sha256']==verification['sha256']
names=['catalogue_wall_sculptures.xlsx','UPLOAD_README.txt','upload-plan.json','all-components-upload-register.csv',
 'selected-image-upload-manifest.csv','retired-components-not-for-upload.csv','shopify-new-products-draft.csv',
 'shopify-existing-variant-price-updates.csv','publication-review.html','app-preparation-verification.json',
 'final-upload-validation.json','verification.json','dropbox-receipt.json']
manifest={name:{'sha256':sha(OUT/name),'bytes':(OUT/name).stat().st_size} for name in names}
(OUT/'package-manifest.json').write_text(json.dumps(manifest,indent=2))
package=OUT/'boldstone-wall-sculptures-upload-package.zip'
with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for name in names+['package-manifest.json']:z.write(OUT/name,name)
with zipfile.ZipFile(package) as z:
    assert z.testzip() is None
    for name,value in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==value['sha256']
(OUT/'publication-receipt.json').write_text(json.dumps({'status':'PASS','published_utc':datetime.now(timezone.utc).isoformat(),
 'pointer_before_sha256':hashlib.sha256(raw).hexdigest(),'pointer_after_sha256':sha(target),
 'package':str(package),'package_sha256':sha(package),'package_bytes':package.stat().st_size,
 'workbook_sha256':verification['sha256'],'dropbox_revision':receipt['current']['rev']},indent=2))
print(json.dumps({'status':'PASS','package':str(package),'bytes':package.stat().st_size,'dropbox_revision':receipt['current']['rev']}))
