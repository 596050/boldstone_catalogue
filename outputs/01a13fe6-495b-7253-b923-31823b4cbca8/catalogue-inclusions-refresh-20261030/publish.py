"""Publish only the verified refreshed-workbook reference."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sqlite3,urllib.request

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt=read(OUT/'dropbox-receipt.json');verification=read(OUT/'verification.json');snapshot=read(OUT/'catalogue-snapshot.json')
assert receipt['status']=='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert sha(OUT/'catalogue_wall_sculptures.xlsx')==verification['sha256']==receipt['sha256_readback']
assert read(OUT/'preservation-verification.json')['status']=='PASS'
target=ROOT/'sculpture-catalogue/current-master.json';raw=target.read_bytes();pointer=json.loads(raw)
baseline=read(OUT/'source-pointer-before.json')
assert pointer['register_sha256']==snapshot['source']['register_sha256']
assert pointer['current_app_review_workbook']==baseline['current_app_review_workbook'],'Another workbook publisher changed the reference'
entry=dict(pointer['current_app_review_workbook'])
entry.update(status='PASS_CURRENT181_INCLUSION_REFRESH_DROPBOX_BYTE_READBACK',
             path=str(OUT/'catalogue_wall_sculptures.xlsx'),sha256=verification['sha256'],
             app_snapshot_utc=snapshot['created_utc'],event_cutoff=snapshot['event_cutoff'],
             listing_decisions={'include':178,'pending':0,'exclude':3},
             verification=str(OUT/'verification.json'),verification_sha256=sha(OUT/'verification.json'),
             preservation_verification=str(OUT/'preservation-verification.json'),
             dropbox_receipt=str(OUT/'dropbox-receipt.json'),dropbox_receipt_sha256=sha(OUT/'dropbox-receipt.json'),
             dropbox=receipt['current'],workbook_upload_plan=str(OUT/'upload-plan.json'))
pointer['current_app_review_workbook']=entry
temporary=target.with_name(target.name+'.workbook-refresh.tmp')
temporary.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+'\n')
assert target.read_bytes()==raw,'Another publisher changed the pointer'
os.replace(temporary,target)
saved=read(target)
assert saved['current_app_review_workbook']==entry
assert {k:v for k,v in saved.items() if k!='current_app_review_workbook'}=={k:v for k,v in json.loads(raw).items() if k!='current_app_review_workbook'}
runtime=Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3')
with sqlite3.connect('file:'+str(runtime)+'?mode=ro',uri=True) as db:
    latest=db.execute('SELECT MAX(id) FROM events').fetchone()[0]
health=json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=30))
assert health['status']=='ok' and health['products']==181
result={'status':'PASS','published_utc':datetime.now(timezone.utc).isoformat(),'dropbox_revision':receipt['current']['rev'],
        'workbook_sha256':verification['sha256'],'pointer_sha256':sha(target),'snapshot_event_cutoff':snapshot['event_cutoff'],
        'latest_app_event':latest,'current_at_final_check':latest==snapshot['event_cutoff'],'live_app':health,
        'only_workbook_pointer_changed':True,'platform_writes':False}
(OUT/'publication-receipt.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
