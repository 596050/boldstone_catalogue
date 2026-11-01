"""Replace the explicitly requested workbook using a revision-checked update."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl, hashlib, json, sys, urllib.request
PROJECT=Path('/Users/tprice/Documents/boldstone'); OUT=Path(__file__).resolve().parent
RUNTIME=Path('/Users/tprice/Library/Application Support/BoldstoneReview')
sys.path.insert(0,str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import FileMetadata, WriteMode

DEST='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
FILE_ID='id:cnqzTNngPVsAAAAAAA7JEQ'
EXPECTED_REV=json.loads((OUT/'previous-dropbox-metadata.json').read_text())['rev']
read=lambda p:json.loads(Path(p).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
def content_hash(b):
    return sha(b''.join(hashlib.sha256(b[i:i+4194304]).digest() for i in range(0,len(b),4194304)))
def info(m):
    return {k:str(getattr(m,k)) if k in ('server_modified','client_modified') else getattr(m,k)
            for k in ('id','name','path_display','rev','size','content_hash','server_modified','client_modified')}
def save(receipt):
    (OUT/'dropbox-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

if '--apply' not in sys.argv:raise SystemExit('Use --apply to replace the requested existing workbook.')
assert not (OUT/'dropbox-receipt.json').exists(), 'Read the existing receipt before any retry.'
v=read(OUT/'verification.json');body=(OUT/'catalogue_wall_sculptures.xlsx').read_bytes()
assert v['status']=='PASS' and sha(body)==v['sha256']
expected_hash=content_hash(body)
receipt={'status':'PREPARED','requested_path':DEST,'local_sha256':sha(body),'expected_content_hash':expected_hash,
    'snapshot_utc':v['app_snapshot_utc'],'products':v['summary']['products'],'started_utc':datetime.now(timezone.utc).isoformat()}
with (RUNTIME/'native-jobs/writer.lock').open('a') as writer:
    fcntl.flock(writer,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with connection(PROJECT) as (client, root):
        assert DEST.startswith(root+'/')
        old=client.files_get_metadata(FILE_ID)
        assert isinstance(old,FileMetadata) and old.path_display==DEST and old.rev==EXPECTED_REV
        old_meta,download=client.files_download('rev:'+old.rev)
        try:previous=download.content
        finally:download.close()
        assert old_meta.id==FILE_ID and old_meta.rev==EXPECTED_REV
        assert previous==(OUT/'previous-catalogue.xlsx').read_bytes(), 'Dropbox workbook changed or local template differs.'
        (OUT/'previous-dropbox-catalogue.xlsx').write_bytes(previous)
        receipt.update(previous=info(old),previous_sha256=sha(previous),status='SUBMITTING_REVISION_UPDATE')
        save(receipt)
        try:
            result=client.files_upload(body,DEST,mode=WriteMode.update(old.rev),autorename=False,mute=True,strict_conflict=True)
            receipt.update(upload_response=info(result),status='UPLOADED_READBACK_PENDING')
            save(receipt)
        except Exception as exc:
            receipt.update(status='UPLOAD_RESPONSE_UNCONFIRMED',error_type=type(exc).__name__)
            save(receipt)
            # Read back; never submit the update again after an ambiguous response.
        current=client.files_get_metadata(FILE_ID)
        assert current.id==FILE_ID and current.path_display==DEST and current.content_hash==expected_hash and current.size==len(body)
        meta,response=client.files_download('rev:'+current.rev)
        try:downloaded=response.content
        finally:response.close()
        assert meta.id==FILE_ID and meta.rev==current.rev and sha(downloaded)==sha(body)
        (OUT/'dropbox-readback.xlsx').write_bytes(downloaded)
        receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK',current=info(current),
            bytes_readback=len(downloaded),sha256_readback=sha(downloaded),same_file_id=True,
            verified_utc=datetime.now(timezone.utc).isoformat())
        save(receipt)
print(json.dumps(receipt,indent=2))
