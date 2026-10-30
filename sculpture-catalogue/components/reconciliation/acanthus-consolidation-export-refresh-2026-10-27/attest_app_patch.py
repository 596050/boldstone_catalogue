"""Independently bind the released app patch without touching app/native state."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import os,re,sqlite3,urllib.request

testdir=H/'app-v2.13.1-independent'
release=BASE.parent/'catalogue-review/reviews/delete-recovery-bugs-20261027'
proof=read(release/'verification.json');assert proof['state']=='PASS'
assert sha(release/'verification.json')==sha(testdir/'verification-input.json')
source_manifest=read(testdir/'source-manifest.json')
for row in source_manifest:
    assert sha(testdir/'source'/row['path'])==row['sha256']
    assert sha(BASE.parent/'catalogue-review'/row['path'])==row['sha256'],'Source changed during independent verification'
for name,digest in proof['files'].items():assert sha(testdir/'source'/name)==digest
py=(testdir/'python-tests.txt').read_text();js=(testdir/'javascript-tests.txt').read_text();sort=(testdir/'sort-tests.txt').read_text()
assert re.search(r'Ran 305 tests.*\n\nOK\s*$',py,re.S)
assert re.search(r'pass 91\b',js) and re.search(r'fail 0\b',js)
assert '9 multi-sort behaviour checks passed' in sort
get=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8767'+p,timeout=60))
health=get('/api/health');assert health['version']=='2.13.1' and health['products']==186
boot=get('/api/bootstrap')
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json')
assert sha(pointer)==receipt['pointer_sha256']
assert boot['source']['register_sha256']==old['register_sha256']==sha(H/'canonical-master-register.json')
assert boot['source']['gallery_sha256']==old['current_published_gallery_projection']['database_sha256']
assert {p['id'] for p in boot['products']}==active
# Compare the immutable event prefix and stable review keys against the
# owning session's before-restart backup. Later user edits may advance versions.
snapshot=sqlite3.connect((release/'reviews-before-restart.sqlite3').as_uri()+'?mode=ro',uri=True)
runtime=Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3')
current=sqlite3.connect(runtime.as_uri()+'?mode=ro',uri=True)
prefix=snapshot.execute('SELECT * FROM review_events ORDER BY rowid').fetchall() if snapshot.execute("SELECT 1 FROM sqlite_master WHERE name='review_events'").fetchone() else None
event_table='review_events' if prefix is not None else 'events'
if prefix is None:prefix=snapshot.execute('SELECT * FROM events ORDER BY rowid').fetchall()
oldcols=[r[1] for r in snapshot.execute('PRAGMA table_info('+event_table+')')]
current_prefix=current.execute('SELECT '+','.join('"'+c+'"' for c in oldcols)+' FROM '+event_table+' ORDER BY rowid LIMIT ?',(len(prefix),)).fetchall()
assert current_prefix==prefix,'Pre-restart event history changed'
oldreviews=snapshot.execute('SELECT kind,product_id,item_id,version,data FROM reviews').fetchall()
advanced=0
for kind,pid,iid,version,data in oldreviews:
    row=current.execute('SELECT version,data FROM reviews WHERE kind=? AND product_id=? AND item_id=?',(kind,pid,iid)).fetchone()
    assert row and row[0]>=version,'Saved review missing or regressed'
    if row[0]==version:assert row[1]==data,'Same-version review changed'
    else:advanced+=1
current_count=current.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
snapshot.close();current.close()
for workbook in receipt['workbooks']:assert sha(workbook['output'])==workbook['sha256']
qa={'status':'PASS_V2_13_1_SOURCE_HASHES_ISOLATED_TESTS_AND_LIVE_READBACK','checked_utc':datetime.now(timezone.utc).isoformat(),'owning_session_verification':str(release/'verification.json'),'owning_session_verification_sha256':sha(release/'verification.json'),'source_manifest_sha256':sha(testdir/'source-manifest.json'),'source_files':len(source_manifest),'python_tests':305,'javascript_tests':91,'sort_checks':9,'total_tests':405,'live_health':health,'register_sha256':old['register_sha256'],'gallery_sha256':boot['source']['gallery_sha256'],'pre_restart_saved_review_keys_preserved':len(oldreviews),'pre_restart_immutable_events_preserved':len(prefix),'later_review_versions_observed':advanced,'current_review_rows':current_count,'workbook_and_catalogue_bytes_unchanged':True,'native_or_live_app_writes_or_restarts_by_root':0,'app_pool_integration':'Not integrated; owning session reports three review workers and one native writer.'}
write(testdir/'independent-verification.json',qa)
new=deepcopy(old);app=new['current_review_application']
app['preceding_release_validation']=deepcopy(app.get('release_validation',{}))
app.update(status='PUBLISHED186_SOURCE_AND_APP2_13_1_VERIFIED',version='2.13.1',ui_revision='2.13.1',last_verified_utc=qa['checked_utc'],last_independently_verified_release='2.13.1',latest_independent_release_check=str((testdir/'independent-verification.json').relative_to(BASE)),latest_independent_release_check_sha256=sha(testdir/'independent-verification.json'),release_validation={'owning_session_verification':str(release/'verification.json'),'sha256':sha(release/'verification.json'),'independent_verification':str((testdir/'independent-verification.json').relative_to(BASE)),'independent_checks':405},latest_release_scope='Deletion-result checks, fresh review of confirmed-present files, isolated per-file errors and durable retry history. Canonical186 source, saved reviews and original files retained. App-pool distribution remains unintegrated.')
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer]
before={p:p.read_bytes() for p in targets};payloads={}
for p in targets:
    value=read(p)
    if p!=pointer:assert value['current_master_catalogue']==old;value['current_master_catalogue']=new
    else:value=new
    payloads[p]=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    temp=p.with_name(p.name+'.root-app2131-pending');temp.write_bytes(data);os.replace(temp,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p];put(p,payloads[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt.update(preceding_app_attested_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),latest_app_release='2.13.1',latest_app_release_verification=str(testdir/'independent-verification.json'),latest_app_release_verification_sha256=sha(testdir/'independent-verification.json'))
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({'status':qa['status'],'tests':405,'active_options':186,'pre_restart_review_keys_preserved':len(oldreviews),'immutable_events_preserved':len(prefix),'catalogue_and_workbook_bytes_unchanged':True}))
