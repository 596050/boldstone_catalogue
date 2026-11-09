"""Revision-guard the existing Dropbox Google-native backup and read it back."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import hashlib
import json
import sys

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import WriteMode
load=lambda p:json.loads(Path(p).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
verified=load(OUT/'google-refresh-verification.json')
assert verified['status']=='PASS_GOOGLE_NATIVE_MASTER_FULL_EXPORT_READBACK'
assert verified['new_dated_evidence_cells_verified']==1061 and len({v['sheet'] for v in verified['native_visual_records']})==12
body=(OUT/'google-master-after.xlsx').read_bytes()
assert sha(body)==verified['native_export_sha256']
previous=load(OUT/'source-pointer-before.json')['current_app_review_workbook']['google_native_master_current']
old=previous['native_backup'];assert old['id']=='id:cnqzTNngPVsAAAAAAA7Jew'
expected_path='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures_google_sheets_backup.xlsx'
assert old['path_display']==expected_path
receipt_path=OUT/'google-backup-dropbox-receipt.json'
assert not receipt_path.exists(),'Reconcile an existing attempt before another upload'
receipt=dict(status='PREPARED',started_utc=datetime.now(timezone.utc).isoformat(),previous=old,
    source_google_url=verified['native_url'],sha256=sha(body),scope='Refresh only the existing private Google-native export backup after complete value, timestamp, formula, table and native visual readback. Main catalogue, feed and sharing unchanged.')
save=lambda:receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
info=lambda m:{k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
provider_hash=sha(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304)))
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with connection(ROOT) as (db,_):
        meta=db.files_get_metadata(old['id'])
        assert meta.rev==old['rev'] and meta.path_display==expected_path,'Remote Google backup changed; reconcile first'
        receipt['status']='SUBMITTING_REVISION_UPDATE';save()
        try:
            m=db.files_upload(body,expected_path,mode=WriteMode.update(meta.rev),autorename=False,mute=True,strict_conflict=True)
            receipt.update(status='UPLOADED_READBACK_PENDING',upload_response=info(m));save()
        except Exception as e:
            receipt.update(status='RESPONSE_UNCONFIRMED',error_type=type(e).__name__);save()
        current=db.files_get_metadata(meta.id)
        assert current.id==meta.id and current.path_display==expected_path
        assert current.size==len(body) and current.content_hash==provider_hash
        dm,response=db.files_download('rev:'+current.rev)
        try:readback=response.content
        finally:response.close()
        assert dm.id==current.id and readback==body
        receipt.update(status='PASS_EXISTING_GOOGLE_BACKUP_REVISION_AND_BYTE_READBACK',current=info(current),
                       sha256_readback=sha(readback),verified_utc=datetime.now(timezone.utc).isoformat());save()
        (OUT/'google-backup-dropbox-readback.xlsx').write_bytes(readback)
print(json.dumps(dict(status=receipt['status'],revision=receipt['current']['rev'],bytes=len(body),sha256=sha(body))))
