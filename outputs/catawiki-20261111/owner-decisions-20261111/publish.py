"""Guarded update of the same Dropbox workbook and current-master pointer."""
from pathlib import Path
from datetime import datetime, timezone
import fcntl, hashlib, json, os, sqlite3, sys
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import WriteMode
read=lambda n:json.loads((OUT/n).read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
plan=read('plan.json');verification=read('verification.json')
body=(OUT/'catalogue_wall_sculptures.xlsx').read_bytes()
assert verification['status']=='PASS' and verification['readers_agree']
assert verification['core_prices_costs_labour_and_other_platforms_unchanged']
assert verification['sha256']==sha(body) and verification['all_other_parts_byte_identical']
before=read('source-pointer-before.json');old=read('previous-dropbox-metadata.json')
assert old['id']=='id:cnqzTNngPVsAAAAAAA7JEQ'
assert old['path_display']=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
receipt_path=OUT/'dropbox-receipt.json'
assert not receipt_path.exists(),'Reconcile any earlier attempt instead of retrying it'
pointer_path=ROOT/'sculpture-catalogue/current-master.json'
now=lambda:datetime.now(timezone.utc).isoformat()
receipt={'status':'PREPARED','started_utc':now(),'scope':plan['scope'],'counts':plan['counts'],
         'previous':old,'sha256':sha(body),'public_catawiki_submissions':0,
         'base_minimum_value_applied':False,'google_private_copy_refreshed':False}
save=lambda:receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
info=lambda m:{k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k)
               for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
content_hash=sha(b''.join(hashlib.sha256(body[n:n+4194304]).digest() for n in range(0,len(body),4194304)))
with (Path.home()/'Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    pointer=json.loads(pointer_path.read_text())
    assert pointer['current_app_review_workbook']==before['current_app_review_workbook'],'Master pointer changed'
    guard=read('app-source-guard.json')
    db=sqlite3.connect(Path(guard['database']).as_uri()+'?mode=ro',uri=True)
    current=db.execute('SELECT MAX(id),MAX(at) FROM events').fetchone();db.close()
    assert list(current)==guard['last_event'],'App changed; reconcile before publication'
    with connection(ROOT) as (client,_):
        meta=client.files_get_metadata(old['id'])
        assert meta.rev==old['rev'] and meta.path_display==old['path_display'],'Dropbox revision changed'
        dm,response=client.files_download('rev:'+meta.rev)
        try:source=response.content
        finally:response.close()
        assert dm.id==meta.id and source==(OUT/'previous-catalogue.xlsx').read_bytes()
        receipt['status']='SUBMITTING_REVISION_UPDATE';save()
        try:
            uploaded=client.files_upload(body,meta.path_display,mode=WriteMode.update(meta.rev),autorename=False,mute=True,strict_conflict=True)
            receipt.update(status='UPLOADED_READBACK_PENDING',upload_response=info(uploaded));save()
        except Exception as e:
            receipt.update(status='RESPONSE_UNCONFIRMED',error_type=type(e).__name__);save()
        fresh=client.files_get_metadata(meta.id)
        assert fresh.id==meta.id and fresh.path_display==meta.path_display
        assert fresh.size==len(body) and fresh.content_hash==content_hash
        dm,response=client.files_download('rev:'+fresh.rev)
        try:readback=response.content
        finally:response.close()
        assert dm.id==meta.id and sha(readback)==sha(body)
        (OUT/'dropbox-readback.xlsx').write_bytes(readback)
        receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK',current=info(fresh),
                       sha256_readback=sha(readback),verified_utc=now());save()
    current_pointer=json.loads(pointer_path.read_text())
    assert current_pointer['current_app_review_workbook']==before['current_app_review_workbook']
    updated=dict(current_pointer['current_app_review_workbook'])
    updated.update(path=str(OUT/'catalogue_wall_sculptures.xlsx'),sha256=sha(body),dropbox=receipt['current'],
                   dropbox_receipt=str(receipt_path),dropbox_receipt_sha256=sha(receipt_path.read_bytes()),
                   verification=str(OUT/'verification.json'),verification_sha256=sha((OUT/'verification.json').read_bytes()),
                   google_private_snapshot_requires_refresh=True)
    updated['catawiki_owner_decisions']={'verified_utc':receipt['verified_utc'],'scope':plan['scope'],
                                       'counts':plan['counts'],'plan':str(OUT/'plan.json'),
                                       'owner_decisions':str(OUT/'owner-decisions.json'),
                                       'catawiki_terms_accepted':False,'public_catawiki_submissions':0}
    current_pointer['current_app_review_workbook']=updated
    tmp=pointer_path.with_suffix('.catawiki-owner.tmp')
    tmp.write_text(json.dumps(current_pointer,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,pointer_path)
print(json.dumps({'status':receipt['status'],'revision':receipt['current']['rev'],'bytes':len(body),
                  'same_file_id':True,'counts':plan['counts'],'sha256':sha(body)},indent=2))
