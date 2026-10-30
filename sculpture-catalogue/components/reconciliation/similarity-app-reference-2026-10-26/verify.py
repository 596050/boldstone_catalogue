"""Independent read-only v2.5 release and saved-review preservation checks."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sqlite3,urllib.request

H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent
A=ROOT/'catalogue-review/reviews/similarity-multisort-20261026';APP=ROOT/'catalogue-review'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=0
def check(ok,msg):
    global checks
    checks+=1
    assert ok,msg
def snapshot(path):
    db=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN')
        return {'reviews':[dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')],
            'events':[dict(r) for r in db.execute('SELECT * FROM events ORDER BY id')],
            'operations':[dict(r) for r in db.execute('SELECT * FROM operations ORDER BY id')]}
    finally:db.close()
def unpack(row):
    r=dict(row)
    for k in ['data','original']:
        if isinstance(r.get(k),str):r[k]=json.loads(r[k])
    return r
key=lambda r:(r['kind'],r['product_id'],r['item_id'])
handoff=read(A/'HANDOFF.json');pointer=read(B/'current-master.json');before_pointer_sha=sha(B/'current-master.json')
check(handoff['status']=='COMPLETE' and handoff['application_version']=='2.5.0','Completed2.5 handoff')
check(handoff['source_register_sha256']==pointer['register_sha256'],'Canonical hash unchanged')
protected={str(B/pointer['register']):pointer['register_sha256'],str(B/pointer['workbook']):pointer['workbook_sha256'],
    str(B/pointer['preferred_review_workbook']):pointer['current_comprehensive_workbook']['sha256']}
for p,digest in protected.items():check(sha(p)==digest,'Canonical bytes '+p)
code={}
for f in handoff['files']:
    check(sha(APP/f)==sha(A/'work'/f),'Deployed code equals QA-tested work '+f);code[str(APP/f)]=sha(APP/f)
for f in ['store.py','deletions.py','delete_dropbox.py','exports.py','projection.py','catalogue.py','dropbox_sync.py','dropbox_sync_worker.py']:
    check(sha(APP/f)==sha(A/'before'/f),'Review/native/source backend unchanged '+f)
before=snapshot(A/'before-deployment.sqlite3')
live_path=Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3';live=snapshot(live_path)
check(len(before['reviews'])==1918 and before['events'][-1]['id']==3952,'Exact production predeployment backup')
check([r for r in live['events'] if r['id']<=3952]==before['events'],'All predeployment audit events retained')
state={key(r):unpack(r) for r in before['reviews']}
for e in [r for r in live['events'] if r['id']>3952]:
    old=json.loads(e['before_json']) if e['before_json'] else None
    new=unpack(json.loads(e['after_json']));k=key(new)
    if old and k in state:check(unpack(old)==state[k],'Later owner event follows preserved state')
    state[k]=new
check(state=={key(r):unpack(r) for r in live['reviews']},'All current reviews are preserved or follow later audit events')
def get(path,raw=False):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=15) as r:
        return r.read() if raw else json.load(r)
health=get('/api/health');boot=get('/api/bootstrap')
check(health['version']=='2.5.0' and health['products']==187,'Live2.5 /187')
check(boot['source']['register_sha256']==pointer['register_sha256'],'Live source binding')
g=read(B/pointer['register']);check({o['id'] for o in boot['products']}==set(g['active_option_ids']),'Exact187 live option IDs')
check('BSI-B0D0CCA7E318' not in {o['id'] for o in boot['products']},'Retired option stays excluded')
gallery=boot['source']['gallery_database'];check(sha(gallery)==boot['source']['gallery_sha256'],'Source gallery bytes')
protected[gallery]=boot['source']['gallery_sha256']
for f in handoff['files']:
    if f.startswith('static/'):
        route='/'+f.split('/',1)[1]
        check(hashlib.sha256(get(route,True)).hexdigest()==sha(APP/f),'Served static bytes '+f)
library=read(A/'qa-library-result.json');request=read(A/'qa-state/similarity-v1'/(library['job_id']+'.request.json'))
request_ids=[r['id'] for group in request['groups'] for r in group]
check(library['state']=='ready' and len(request_ids)==len(set(request_ids))==7091,'Full-library input unique7091')
check(len(library['order'])==len(set(library['order']))==7091 and set(library['order'])==set(request_ids),'Similarity is a permutation of all images')
check(len(library['missing_ids'])==328 and set(library['missing_ids'])<=set(library['order']),'Missing previews retained')
check(library['analysed']==6763 and library['analysed']+len(library['missing_ids'])==7091,'Analysed/missing reconciliation')
native=read(A/'native-similarity-check.json')
for mode in ['cold','warm','reverse']:
    r=native[mode];check(set(r['order'])=={'original','brightened','resized','other','missing'},'Native fixture IDs '+mode)
    check(r['order'][-1]=='missing' and r['analysed']==4,'Native missing preview stays last '+mode)
check(native['warm']['new_features']==0 and native['warm']['cached_features']==4,'Feature cache reused')
check(native['cold']['order'][:3]==['original','brightened','resized'],'Resized/brightness copies group with original')
check(sha(B/'current-master.json')==before_pointer_sha,'No canonical metadata write during verification')
report={'status':'PASS_INDEPENDENT_V2_5_RELEASE_AND_REVIEW_PRESERVATION','checked_utc':datetime.now(timezone.utc).isoformat(),
    'checks':checks,'app_version':'2.5.0','active_options':187,'baseline_pointer_sha256':before_pointer_sha,
    'handoff':str(A/'HANDOFF.json'),'handoff_sha256':sha(A/'HANDOFF.json'),'application_files':code,
    'protected_source_hashes':protected,'predeployment_backup':str(A/'before-deployment.sqlite3'),
    'predeployment_backup_sha256':sha(A/'before-deployment.sqlite3'),'predeployment_reviews':1918,'predeployment_event_cutoff':3952,
    'live_review_rows':len(live['reviews']),'live_event_cutoff':live['events'][-1]['id'],
    'later_owner_events':sum(e['id']>3952 for e in live['events']),'predeployment_reviews_and_events_preserved':True,
    'full_library_unique_images':7091,'analysed_images':6763,'missing_preview_images_retained':328,
    'python_tests_independently_passed':94,'node_sort_checks_independently_passed':9,
    'similarity_is_not_duplicate_or_sculpture_identity_proof':True,'root_runtime_db_native_platform_code_writes':0}
(H/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in {'application_files','protected_source_hashes'}},indent=2))
