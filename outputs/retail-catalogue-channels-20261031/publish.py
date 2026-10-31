"""Publish only the verified current-workbook pointer, preserving other session work."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sqlite3,urllib.request
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(OUT/'dropbox-receipt.json');v=read(OUT/'workbook-verification.json');s=read(OUT/'current-catalogue-snapshot.json')
assert r['status']=='PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
assert sha(OUT/'catalogue_wall_sculptures.xlsx')==v['sha256']==r['sha256_readback']
assert read(OUT/'preservation-verification.json')['status']=='PASS'
assert read(OUT/'website-copy-verification.json')['status']=='PASS_EXACT_NATIVE_EXPORT_READBACK'
with sqlite3.connect('file:/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3?mode=ro',uri=True) as db:latest=db.execute('select max(id) from events').fetchone()[0]
assert latest==s['event_cutoff']
health=json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=30));assert health['status']=='ok' and health['products']==181
p=ROOT/'sculpture-catalogue/current-master.json';raw=p.read_bytes();current=json.loads(raw);old=read(OUT/'source-pointer-before.json');key='current_app_review_workbook'
assert current['register_sha256']==s['source']['register_sha256']
assert current[key]==old[key],'Another session changed the workbook pointer'
entry=dict(current[key]);entry.update(status='PASS_CURRENT_APP_REFRESH_DROPBOX_BYTE_READBACK',path=str(OUT/'catalogue_wall_sculptures.xlsx'),sha256=v['sha256'],app_snapshot_utc=s['created_utc'],event_cutoff=s['event_cutoff'],verification=str(OUT/'workbook-verification.json'),verification_sha256=sha(OUT/'workbook-verification.json'),preservation_verification=str(OUT/'preservation-verification.json'),dropbox_receipt=str(OUT/'dropbox-receipt.json'),dropbox_receipt_sha256=sha(OUT/'dropbox-receipt.json'),dropbox=r['current'],workbook_upload_plan=str(OUT/'website-final-plan.json'),squarespace_readiness=str(OUT/'website-photo-readiness.json'),website_verification=str(OUT/'website-copy-verification.json'))
current[key]=entry;temporary=p.with_name(p.name+'.retail-copy.tmp');temporary.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n');assert p.read_bytes()==raw;os.replace(temporary,p);assert read(p)==current
assert {k:v for k,v in current.items() if k!=key}=={k:v for k,v in json.loads(raw).items() if k!=key}
result={'status':'PASS','published_utc':datetime.now(timezone.utc).isoformat(),'dropbox_revision':r['current']['rev'],'workbook_sha256':v['sha256'],'app_event_cutoff':latest,'app_records':181,'website_records_updated':178,'only_workbook_pointer_changed':True}
(OUT/'publication-receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
