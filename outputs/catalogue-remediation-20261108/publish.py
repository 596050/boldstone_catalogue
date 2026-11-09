"""Revision-guarded update of the existing authorized Dropbox master, with byte readback."""
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
sha=lambda data:hashlib.sha256(data).hexdigest()
body=(OUT/'catalogue_wall_sculptures.xlsx').read_bytes()
verification=load(OUT/'verification.json');independent=load(OUT/'independent-verification.json')
assert verification['status']==independent['status']=='PASS'
assert verification['sha256']==independent['sha256']==sha(body)
assert load(OUT/'sensitivity-verification.json')['status']=='PASS'
plan=load(OUT/'plan.json')
assert independent['independently_verified_cells']==len(plan['patches'])
old=load(OUT/'previous-dropbox-metadata.json')
assert old['id']=='id:cnqzTNngPVsAAAAAAA7JEQ'
assert old['path_display']=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as response:
    app=json.load(response)
relevant=lambda snapshot:{p['id']:{k:p[k] for k in ['fields','listing_fields','costing','photos','listing_decision']} for p in snapshot['products']}
assert relevant(app)==relevant(load(OUT/'app-specifications.json')),'App changed: reconcile before publishing'
pointer_path=ROOT/'sculpture-catalogue/current-master.json'
before=load(OUT/'source-pointer-before.json')
assert load(pointer_path)['current_app_review_workbook']==before['current_app_review_workbook']
receipt_path=OUT/'dropbox-receipt.json'
assert not receipt_path.exists(),'Existing attempt must be reconciled before retrying'
now=lambda:datetime.now(timezone.utc).isoformat()
receipt=dict(status='PREPARED',started_utc=now(),previous=old,sha256=sha(body),scope=plan['scope'],google_sheet_status='7 November snapshot remains unchanged; new private remediation columns require native refresh',pinterest_public_feed_status='Unchanged: no new product identifiers or public prices assigned')
save=lambda:receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
info=lambda m:{k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
content_hash=sha(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304)))
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with connection(ROOT) as (db,_):
        meta=db.files_get_metadata(old['id'])
        assert meta.rev==old['rev'] and meta.path_display==old['path_display'],'Dropbox source changed; do not overwrite'
        source_meta,response=db.files_download('rev:'+meta.rev)
        try:source=response.content
        finally:response.close()
        assert source_meta.id==meta.id and source==(OUT/'previous-catalogue.xlsx').read_bytes()
        receipt['status']='SUBMITTING_REVISION_UPDATE';save()
        try:
            uploaded=db.files_upload(body,meta.path_display,mode=WriteMode.update(meta.rev),autorename=False,mute=True,strict_conflict=True)
            receipt.update(status='UPLOADED_READBACK_PENDING',upload_response=info(uploaded));save()
        except Exception as error:
            # A lost response never causes a blind second upload.
            receipt.update(status='RESPONSE_UNCONFIRMED',error_type=type(error).__name__);save()
        fresh=db.files_get_metadata(meta.id)
        assert fresh.id==meta.id and fresh.path_display==meta.path_display
        assert fresh.size==len(body) and fresh.content_hash==content_hash
        read_meta,response=db.files_download('rev:'+fresh.rev)
        try:readback=response.content
        finally:response.close()
        assert read_meta.id==meta.id and sha(readback)==sha(body)
        (OUT/'dropbox-readback.xlsx').write_bytes(readback)
        receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK',current=info(fresh),sha256_readback=sha(readback),verified_utc=now());save()
    pointer=load(pointer_path)
    assert pointer['current_app_review_workbook']==before['current_app_review_workbook']
    updated=dict(pointer['current_app_review_workbook'])
    updated.update(path=str(OUT/'catalogue_wall_sculptures.xlsx'),sha256=sha(body),dropbox=receipt['current'],dropbox_receipt=str(receipt_path),dropbox_receipt_sha256=sha(receipt_path.read_bytes()),verification=str(OUT/'verification.json'),verification_sha256=sha((OUT/'verification.json').read_bytes()))
    updated['channel_remediation_20261108']=dict(verified_utc=receipt['verified_utc'],scope=plan['scope'],plan=str(OUT/'plan.json'),independent_verification=str(OUT/'independent-verification.json'),google_private_snapshot_requires_refresh=True,gtins_assigned=0,brandboom_preview_id='681160',brandboom_preview_members=50,instagram_posts_published=0,pinterest_appeals_used=0)
    pointer['current_app_review_workbook']=updated
    temporary=pointer_path.with_suffix('.remediation.tmp')
    temporary.write_text(json.dumps(pointer,indent=2)+'\n');temporary.replace(pointer_path)
print(json.dumps(receipt,indent=2))
