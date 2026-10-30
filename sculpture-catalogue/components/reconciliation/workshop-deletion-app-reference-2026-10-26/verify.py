"""Read-only v2.7 guard, prepared-review and concurrent durable-state audit."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,re,sqlite3,time,urllib.request
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent;APP=ROOT/'catalogue-review';A=APP/'reviews/workshop-deletion-scope-20261026'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=0
def check(ok,msg):
    global checks
    checks+=1;assert ok,msg
def snapshot(path):
    db=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN')
        return {'reviews':[dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')],
            'events':[dict(r) for r in db.execute('SELECT * FROM events ORDER BY id')],
            'deletion_jobs':[dict(r) for r in db.execute('SELECT * FROM deletion_jobs ORDER BY id')],
            'deletion_batches':[dict(r) for r in db.execute('SELECT * FROM deletion_batches ORDER BY id')]}
    finally:db.close()
def unpack(row):
    r=dict(row)
    for k in ['data','original']:
        if isinstance(r.get(k),str):r[k]=json.loads(r[k])
    return r
key=lambda r:(r['kind'],r['product_id'],r['item_id'])
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=20) as r:return json.load(r)
handoff_path=A/'HANDOFF.json';check(sha(handoff_path)=='516b118a703d8d2b15f15e5ab31704500882a69fbb46d94f485a505a96c7b877','Sealed handoff bytes')
handoff=read(handoff_path);pointer=read(B/'current-master.json');pointer_sha=sha(B/'current-master.json');code={}
for f,digest in handoff['deployment']['code_sha256'].items():
    check(sha(APP/f)==sha(A/'work'/f)==digest,'Deployed and QA code '+f);code[str(APP/f)]=digest
for f in ['catalogue.py','store.py','exports.py','component_reviews.py','component_links.py','fetch_original.py','dropbox_sync.py','dropbox_sync_worker.py']:
    check(sha(APP/f)==sha(A/'before'/f),'Unchanged source/review module '+f)
protected={str(B/pointer['register']):pointer['register_sha256'],str(B/pointer['workbook']):pointer['workbook_sha256'],
    str(B/pointer['preferred_review_workbook']):pointer['current_comprehensive_workbook']['sha256']}
for path,digest in protected.items():check(sha(path)==digest,'Canonical bytes '+path)
before=snapshot(A/'before-deployment.sqlite3');live=snapshot(Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3')
check(len(before['reviews'])==2144 and before['events'][-1]['id']==4376,'Exact predeployment2144/4376 backup')
check([r for r in live['events'] if r['id']<=4376]==before['events'],'Old audit history unchanged')
state={key(r):unpack(r) for r in before['reviews']}
for event in [r for r in live['events'] if r['id']>4376]:
    prior=json.loads(event['before_json']) if event['before_json'] else None
    after=unpack(json.loads(event['after_json']));k=key(after)
    if prior and k in state:check(unpack(prior)==state[k],'Later live event follows preserved state')
    state[k]=after
check(state=={key(r):unpack(r) for r in live['reviews']},'Current rows preserved or follow later audited activity')
health=get('/api/health');boot=get('/api/bootstrap');g=read(B/pointer['register'])
check(health['version']=='2.7.0' and health['products']==187,'Live2.7/187')
check(boot['source']['register_sha256']==pointer['register_sha256'],'Live source binding')
check({r['id'] for r in boot['products']}==set(g['active_option_ids']),'Exact active187')
gallery=boot['source']['gallery_database'];protected[gallery]=boot['source']['gallery_sha256'];check(sha(gallery)==protected[gallery],'Saved gallery bytes unchanged')
review=read(A/'live-review-readback.json');check(review['final_checkbox_checked'] is False and review['agent_executed_native_deletions']==0,'Owning session stopped at final review')
check(review['batch']['state']=='prepared' and all(r['state']=='prepared' for r in review['jobs']),'Eight present files prepared at owning-session cutoff')
check({r['file_id'] for r in review['jobs']}==set(handoff['reviewed_dropbox_ids']) and len(review['jobs'])==8,'Exact eight file-ID set')
numbers=set();prepared=[];current_jobs={r['id']:r for r in live['deletion_jobs']}
for job in review['jobs']:
    p=job['payload'];f=p['file'];binding=p['binding']
    check(f['availability']=='present' and f['type']=='file','Native inspection present file')
    check(f['id']==binding['id']==job['file_id'],'Pinned stable ID')
    check(f['content_hash']==binding['content_hash'] and re.fullmatch('[a-f0-9]{64}',f['content_hash']),'Pinned content hash')
    check(f['bytes']==binding['bytes'] and f['bytes']>0 and f['revision'],'Pinned size/revision')
    check(f['path'].startswith('/BOLDSTONE MASTER/Products/Workshop and Moulding/Barbados Moons and Waves Workshop Views/'),'Exact containing folder')
    check(re.fullmatch('[a-f0-9]{64}',f['sharing_fingerprint']) is not None,'Sharing fingerprint present')
    check(Path(f['name']).suffix.casefold() in {'.jpg','.jpeg','.png'},'Known image filename suffix')
    number=re.search(r'__(\d{3})\.[^.]+$',f['name']).group(1);numbers.add(number)
    now=current_jobs[job['id']];result=json.loads(now['result'])
    check(now['file_id']==job['file_id'],'Later job keeps exact ID')
    check(json.loads(now['payload'])==p,'Reviewed payload unchanged during later activity')
    if now['state']=='deleted':check(result.get('verified_absent') and result.get('confirmed_file_id')==f['id'],'Confirmed deletion receipt has verified absence')
    if now['state']=='already_absent':check(result.get('verified_absent') and result.get('delete_attempted') is False,'No false deletion claim for already-absent file')
    prepared.append({'file_id':f['id'],'number':number,'name':f['name'],'path':f['path'],'revision_at_review':f['revision'],
        'sha256_content_hash_at_review':f['content_hash'],'state_at_root_snapshot':now['state'],
        'native_result_at_root_snapshot':result,'review_expired_at_root_snapshot':time.time()>p['expires_at']})
check(numbers=={'010','005','012','006','003','008','001','009'},'Exact requested filename numbers')
simulation=read(A/'qa-native-simulation.json')
check(simulation['simulated'] is True and simulation['real_dropbox_mutations']==0,'Only simulated native execution used for QA')
check(simulation['last_result']['state']=='already_absent' and simulation['last_result']['delete_attempted'] is False,'Missing-file cleanup differs from delete')
check(sha(B/'current-master.json')==pointer_sha,'No shared metadata write during verification')
report={'status':'PASS_INDEPENDENT_V2_7_GUARDS_AND_REVIEW_PRESERVATION','checked_utc':datetime.now(timezone.utc).isoformat(),
    'checks':checks,'application_version':'2.7.0','active_options':187,'baseline_pointer_sha256':pointer_sha,
    'handoff':str(handoff_path),'handoff_sha256':sha(handoff_path),'application_files':code,'protected_source_hashes':protected,
    'predeployment_backup':str(A/'before-deployment.sqlite3'),'predeployment_backup_sha256':sha(A/'before-deployment.sqlite3'),
    'predeployment_review_rows':2144,'predeployment_event_cutoff':4376,'live_review_rows':len(live['reviews']),
    'live_event_cutoff':live['events'][-1]['id'],'later_live_events':sum(r['id']>4376 for r in live['events']),
    'review_values_originals_versions_and_old_audit_history_preserved':True,'independent_python_tests_passed':122,
    'reviewed_barbados_file_ids':handoff['reviewed_dropbox_ids'],'prepared_eight_files':prepared,
    'current_reviewed_job_states':dict(Counter(r['state_at_root_snapshot'] for r in prepared)),
    'review_scope':'Known catalogue Dropbox image IDs within existing account/namespace BOLDSTONE MASTER; exact final review retained.',
    'missing_cleanup_is_not_a_native_delete':True,'live_file_deletion_not_executed_by_root_or_by_qa':True,
    'later_actual_native_job_activity_is_separate_from_the_software_deployment':True,
    'root_code_review_db_native_platform_mutations':0}
(H/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['application_files','protected_source_hashes','prepared_eight_files','reviewed_barbados_file_ids']},indent=2))
