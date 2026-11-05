"""Update the authorized existing workbook once, guarded by native revision."""
import fcntl,hashlib,json,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.files import WriteMode
read=lambda p:json.loads(p.read_text());sha=lambda b:hashlib.sha256(b).hexdigest()
body=(OUT/'catalogue_wall_sculptures.xlsx').read_bytes();ver=read(OUT/'verification.json');plan=read(OUT/'plan.json')
assert ver['status']=='PASS' and ver['sha256']==sha(body)
assert read(OUT/'independent-verification.json')['status']=='PASS'
old=read(OUT/'previous-dropbox-metadata.json');saved=read(OUT/'app-after.json')
assert old['id']=='id:cnqzTNngPVsAAAAAAA7JEQ'
assert old['path_display']=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/_Documents_Catalogue/catalogue_wall_sculptures.xlsx'
with urllib.request.urlopen('http://127.0.0.1:8767/api/specifications',timeout=120) as r:current=json.load(r)
def relevant(app):
 return {p['id']:{'fields':p['fields'],'listing_fields':p['listing_fields'],'costing':p['costing'],'photos':p['photos'],'listing_decision':p['listing_decision']} for p in app['products']}
assert relevant(current)==relevant(saved),'App changed; reconcile before upload'
receipt_path=OUT/'dropbox-receipt.json';assert not receipt_path.exists(),'Reconcile existing upload journal before retrying'
receipt=dict(status='PREPARED',started_utc=datetime.now(timezone.utc).isoformat(),previous=old,sha256=sha(body),scope=plan['scope'])
save=lambda:receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
info=lambda m:{k:str(getattr(m,k)) if k.endswith('modified') else getattr(m,k) for k in ['id','path_display','rev','size','content_hash','server_modified','client_modified']}
content_hash=sha(b''.join(hashlib.sha256(body[n:n+4194304]).digest() for n in range(0,len(body),4194304)))
with Path('/Users/tprice/Library/Application Support/BoldstoneReview/native-jobs/writer.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 with connection(ROOT) as (db,_):
  meta=db.files_get_metadata(old['id']);assert meta.rev==old['rev'] and meta.path_display==old['path_display']
  dm,r=db.files_download('rev:'+meta.rev)
  try:previous=r.content
  finally:r.close()
  assert dm.id==meta.id and previous==(OUT/'previous-catalogue.xlsx').read_bytes()
  receipt['status']='SUBMITTING_REVISION_UPDATE';save()
  try:
   result=db.files_upload(body,meta.path_display,mode=WriteMode.update(meta.rev),autorename=False,mute=True,strict_conflict=True)
   receipt.update(status='UPLOADED_READBACK_PENDING',upload_response=info(result));save()
  except Exception as e:receipt.update(status='RESPONSE_UNCONFIRMED',error_type=type(e).__name__);save()
  fresh=db.files_get_metadata(meta.id);assert fresh.id==meta.id and fresh.path_display==meta.path_display
  assert fresh.size==len(body) and fresh.content_hash==content_hash
  dm,r=db.files_download('rev:'+fresh.rev)
  try:readback=r.content
  finally:r.close()
  assert dm.id==meta.id and sha(readback)==sha(body)
  (OUT/'dropbox-readback.xlsx').write_bytes(readback)
  receipt.update(status='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK',current=info(fresh),sha256_readback=sha(readback),verified_utc=datetime.now(timezone.utc).isoformat());save()
 pointer_path=ROOT/'sculpture-catalogue/current-master.json';pointer=read(pointer_path);before=read(OUT/'source-pointer-before.json')
 assert pointer['current_app_review_workbook']==before['current_app_review_workbook']
 updated=dict(pointer['current_app_review_workbook'])
 updated.update(path=str(OUT/'catalogue_wall_sculptures.xlsx'),sha256=sha(body),dropbox=receipt['current'],dropbox_receipt=str(receipt_path),dropbox_receipt_sha256=sha(receipt_path.read_bytes()),verification=str(OUT/'verification.json'),verification_sha256=sha((OUT/'verification.json').read_bytes()),publication_photo_update_utc=receipt['verified_utc'],publication_photo_update_scope=plan['scope'],publication_photo_update_plan=str(OUT/'plan.json'),publication_photo_update_verified=str(OUT/'independent-verification.json'))
 pointer['current_app_review_workbook']=updated
 tmp=pointer_path.with_suffix('.publication-update.tmp');tmp.write_text(json.dumps(pointer,indent=2)+'\n');tmp.replace(pointer_path)
print(json.dumps(receipt,indent=2))
