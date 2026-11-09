"""Update only the existing authorised Dropbox master after exact preservation checks."""
import fcntl
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import WriteMode
load=lambda p:json.loads(Path(p).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
body=(OUT/'catalogue_wall_sculptures.xlsx').read_bytes()
verified=load(OUT/'verification.json');independent=load(OUT/'independent-verification.json')
assert verified['status']==independent['status']=='PASS'
assert verified['sha256']==independent['sha256']==sha(body)
assert verified['all_existing_formulas_preserved']==32776 and verified['all_other_parts_byte_identical']
assert verified['core_costs_prices_and_zero_labour_preserved'] and independent['readers_agree']
plan=load(OUT/'plan.json')
assert independent['independently_verified_cells']==len(plan['patches'])
old=load(OUT/'previous-dropbox-metadata.json')
assert old['id']=='id:cnqzTNngPVsAAAAAAA7JEQ'
assert old['path_display']=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as r:app=json.load(r)
relevant=lambda s:{p['id']:{k:p[k] for k in ['fields','listing_fields','costing','photos','listing_decision']} for p in s['products']}
assert relevant(app)==relevant(load(OUT/'app-specifications.json')),'App changed; reconcile source facts before release'
pointer_path=ROOT/'sculpture-catalogue/current-master.json'
before=load(OUT/'source-pointer-before.json')
assert load(pointer_path)['current_app_review_workbook']==before['current_app_review_workbook']
receipt_path=OUT/'dropbox-receipt.json'
assert not receipt_path.exists(),'Reconcile an existing attempt; never blindly re-upload'
now=lambda:datetime.now(timezone.utc).isoformat()
receipt=dict(status='PREPARED',started_utc=now(),previous=old,sha256=sha(body),scope=plan['scope'],
             counts=plan['counts'],google_private_sheet_status='Existing 7 November snapshot remains unchanged; private social/audit fields not projected',
             pinterest_public_feed_status='Existing public retail feed refreshed: only 21 additional-image cells changed; all 176 rows and 46 fields publicly read back. Prices, IDs and privacy unchanged. Ingestion remains disabled pending merchant approval.')
save=lambda:receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
info=lambda m:{k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
content_hash=sha(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304)))
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with connection(ROOT) as (db,_):
        meta=db.files_get_metadata(old['id'])
        assert meta.rev==old['rev'] and meta.path_display==old['path_display'],'Dropbox master changed'
        dm,response=db.files_download('rev:'+meta.rev)
        try:source=response.content
        finally:response.close()
        assert dm.id==meta.id and source==(OUT/'previous-catalogue.xlsx').read_bytes()
        receipt['status']='SUBMITTING_REVISION_UPDATE';save()
        try:
            m=db.files_upload(body,meta.path_display,mode=WriteMode.update(meta.rev),autorename=False,mute=True,strict_conflict=True)
            receipt.update(status='UPLOADED_READBACK_PENDING',upload_response=info(m));save()
        except Exception as e:
            receipt.update(status='RESPONSE_UNCONFIRMED',error_type=type(e).__name__);save()
        fresh=db.files_get_metadata(meta.id)
        assert fresh.id==meta.id and fresh.path_display==meta.path_display
        assert fresh.size==len(body) and fresh.content_hash==content_hash
        dm,response=db.files_download('rev:'+fresh.rev)
        try:readback=response.content
        finally:response.close()
        assert dm.id==meta.id and sha(readback)==sha(body)
        (OUT/'dropbox-readback.xlsx').write_bytes(readback)
        receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK',current=info(fresh),sha256_readback=sha(readback),verified_utc=now());save()
    pointer=load(pointer_path)
    assert pointer['current_app_review_workbook']==before['current_app_review_workbook']
    updated=dict(pointer['current_app_review_workbook'])
    updated.update(path=str(OUT/'catalogue_wall_sculptures.xlsx'),sha256=sha(body),dropbox=receipt['current'],
                   dropbox_receipt=str(receipt_path),dropbox_receipt_sha256=sha(receipt_path.read_bytes()),
                   verification=str(OUT/'verification.json'),verification_sha256=sha((OUT/'verification.json').read_bytes()))
    updated['photo_and_brandboom_followup_20261108']=dict(verified_utc=receipt['verified_utc'],scope=plan['scope'],
        plan=str(OUT/'plan.json'),independent_verification=str(OUT/'independent-verification.json'),counts=plan['counts'],
        pinterest_profile_shop_url='https://boldstonesculpture.com',pinterest_merchant_approved=False,
        primary_original_dimensions_confirmed=96,qualifying_selected_photo_alternatives_products=28,brandboom_duplicate_photo_associations_corrected=1,
        manufacturer_brand='Boldstone',manufacturer_brand_status='Brand review pending',manufacturer_logo_corrected=True,
        manufacturer_products_published=0,google_private_snapshot_requires_refresh=True,
        google_approved_products=325,google_wall_sculptures_refreshed=176,brandboom_restored_products=176,
        brandboom_owner_preview_products=50)
    pointer['current_app_review_workbook']=updated
    temp=pointer_path.with_suffix('.social-merchant.tmp')
    temp.write_text(json.dumps(pointer,indent=2)+'\n');temp.replace(pointer_path)
print(json.dumps(dict(status=receipt['status'],revision=receipt['current']['rev'],bytes=receipt['current']['size'],counts=plan['counts'],sha256=sha(body)),indent=2))
