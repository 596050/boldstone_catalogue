"""Revision-guarded update of the existing catalogue; reconcile, never retry blindly."""
from datetime import datetime, timezone
from pathlib import Path
import fcntl, hashlib, json, os, sys
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent/'requirements-workbook'
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import WriteMode
read=lambda p:json.loads(Path(p).read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
receiptfile=OUT/'dropbox-receipt.json'
assert not receiptfile.exists(),'Inspect existing receipt before retrying.'
v=read(OUT/'verification.json');body=(OUT/'catalogue_wall_sculptures.xlsx').read_bytes()
assert v['status']=='PASS' and v['sha256']==sha(body)
old=read(OUT/'previous-dropbox-metadata.json');dest=old['path_display'];expected_hash=sha(b''.join(hashlib.sha256(body[i:i+4194304]).digest() for i in range(0,len(body),4194304)))
info=lambda m:{k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ('id','name','path_display','rev','size','content_hash','server_modified','client_modified')}
scope=('Dispatch exceptions updated for all 181 components: three working days for applicable eBay Simple Delivery, Chairish parcel orders and Saatchi Art collection; ten working days elsewhere. Other workbook records preserved; same file ID.' if OUT.name=='dispatch-workbook' else 'Current descriptions and dispatch policy, plus channel details and US delivery estimates for all 181 components; same workbook file ID.')
receipt={'status':'PREPARED','started_utc':datetime.now(timezone.utc).isoformat(),'previous':old,'local_sha256':sha(body),'products':181,'scope':scope}
save=lambda:receiptfile.write_text(json.dumps(receipt,indent=2)+'\n')
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with connection(ROOT) as (client,root):
        m=client.files_get_metadata(old['id'])
        assert m.rev==old['rev'] and m.path_display==dest
        meta,response=client.files_download('rev:'+m.rev)
        try:before=response.content
        finally:response.close()
        assert meta.id==m.id and before==(OUT/'previous-catalogue.xlsx').read_bytes()
        receipt['status']='SUBMITTING_REVISION_UPDATE';save()
        try:
            result=client.files_upload(body,dest,mode=WriteMode.update(m.rev),autorename=False,mute=True,strict_conflict=True)
            receipt.update(status='UPLOADED_READBACK_PENDING',upload_response=info(result));save()
        except Exception as exc:
            receipt.update(status='RESPONSE_UNCONFIRMED',error_type=type(exc).__name__);save()
        current=client.files_get_metadata(m.id)
        assert current.path_display==dest and current.content_hash==expected_hash and current.size==len(body)
        meta,response=client.files_download('rev:'+current.rev)
        try:downloaded=response.content
        finally:response.close()
        assert meta.id==m.id and sha(downloaded)==sha(body)
        (OUT/'dropbox-readback.xlsx').write_bytes(downloaded)
        receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK',current=info(current),sha256_readback=sha(downloaded),verified_utc=datetime.now(timezone.utc).isoformat());save()
pointerpath=ROOT/'sculpture-catalogue/current-master.json';raw=pointerpath.read_bytes();pointer=json.loads(raw)
prior=read(OUT/'source-pointer-before.json')['current_app_review_workbook'];assert pointer['current_app_review_workbook']==prior
updated=dict(prior);updated.update(path=str(OUT/'catalogue_wall_sculptures.xlsx'),sha256=sha(body),dropbox=receipt['current'],dropbox_receipt=str(receiptfile),dropbox_receipt_sha256=sha(receiptfile.read_bytes()),verification=str(OUT/'verification.json'),verification_sha256=sha((OUT/'verification.json').read_bytes()),channel_requirements_update_utc=receipt['verified_utc'],channel_requirements_scope=receipt['scope'])
pointer['current_app_review_workbook']=updated;tmp=pointerpath.with_name('.current-master.channel-workbook.tmp');tmp.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n');assert pointerpath.read_bytes()==raw;os.replace(tmp,pointerpath)
print(json.dumps({'status':receipt['status'],'products':181,'same_file_id':True,'revision':receipt['current']['rev'],'sha256':sha(body)}))
