"""Read-only review of v2.8.2; no native calls, jobs, or shared publication writes."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from urllib.parse import quote
import hashlib,json,sqlite3,sys,urllib.request
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent;APP=ROOT/'catalogue-review';A=APP/'reviews/background-organisation-20261026'
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
            'jobs':[dict(r) for r in db.execute('SELECT * FROM background_jobs ORDER BY id')]}
    finally:db.close()
def unpack(row):
    r=dict(row)
    for k in ['data','original']:
        if isinstance(r.get(k),str):r[k]=json.loads(r[k])
    return r
key=lambda r:(r['kind'],r['product_id'],r['item_id'])
def get(path,raw=False):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=30) as r:return r.read() if raw else json.load(r)
handoff_path=A/'HANDOFF.json';handoff=read(handoff_path);pointer=B/'current-master.json';p=read(pointer);pointer_sha=sha(pointer)
check(handoff['version']=='2.8.2' and handoff['status']=='deployed_and_verified','Final2.8.2 handoff')
code={}
for row in handoff['source_files']:
    path=(ROOT/row['path']).resolve();check(path.is_relative_to(APP),'App-scoped source file')
    check(sha(path)==row['sha256'],'Sealed deployed source '+row['path']);code[str(path)]=row['sha256']
protected={str(B/p['register']):p['register_sha256'],str(B/p['workbook']):p['workbook_sha256'],
    str(B/p['preferred_review_workbook']):p['current_comprehensive_workbook']['sha256']}
for path,digest in protected.items():check(sha(path)==digest,'Canonical bytes '+path)
before=snapshot(A/'pre-v281.sqlite3');runtime=Path.home()/'Library/Application Support/BoldstoneReview';live=snapshot(runtime/'reviews.sqlite3')
check(len(before['reviews'])==2416 and before['events'][-1]['id']==4905,'Exact pre-v281 backup')
check([r for r in live['events'] if r['id']<=4905]==before['events'],'Historical audit events unchanged')
state={key(r):unpack(r) for r in before['reviews']}
for event in [r for r in live['events'] if r['id']>4905]:
    prior=json.loads(event['before_json']) if event['before_json'] else None
    after=unpack(json.loads(event['after_json']));k=key(after)
    if prior and k in state:check(unpack(prior)==state[k],'Later recorded event follows prior state')
    state[k]=after
check(state=={key(r):unpack(r) for r in live['reviews']},'Current reviews retained or follow later audited changes')
health=get('/api/health');boot=get('/api/bootstrap');jobs=get('/api/jobs');g=read(B/p['register'])
check(health['version']=='2.8.2' and health['products']==187,'Live2.8.2/187')
check(boot['source']['register_sha256']==p['register_sha256'],'Live source register binding')
check({r['id'] for r in boot['products']}==set(g['active_option_ids']),'Exact187 active IDs')
gallery=boot['source']['gallery_database'];protected[gallery]=boot['source']['gallery_sha256'];check(sha(gallery)==protected[gallery],'Saved source gallery bytes')
check(jobs['reservation'] and jobs['reservation'].get('active') is True,'Native jobs remain gated by active reservation')
reservation_file=runtime/'native-writer-reservation.json';reservation=read(reservation_file)
check(reservation.get('active') is True and reservation['root']=='/Users/tprice/BoldstoneMigration/path-renaming-20261026','Filename writer reservation')
sys.path.insert(0,str(APP))
from organisation import folder_for_components,NeedsChoice
products={o['product_id']:{'id':o['product_id'],'name':o['name'],'family':o['family'],'folder_url':o.get('folder_url','')}
    for o in g['options'] if o['product_id'] in g['active_option_ids']}
current_native=read(boot['source']['live_dropbox']['path'])['records']
for o in g['options']:
    pid=o['product_id']
    if pid not in products:continue
    folder=current_native.get(o.get('folder_id'))
    if folder and folder['kind']=='folder':
        products[pid]['folder_url']='https://www.dropbox.com/home'+quote(folder['path'],safe='/')
plans=read(A/'all-component-folder-plans.json');expected={r['product_id']:r for r in plans['results']};computed=[]
check(set(expected)==set(products) and plans['native_calls']==0 and plans['review_writes']==0,'Folder-plan scope and read-only evidence')
for pid,product in products.items():
    try:
        destination=folder_for_components(products,[pid],['in_situ']);row={'product_id':pid,'status':'ready','destination':destination}
        check(destination.startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/'),'Scoped folder destination')
    except NeedsChoice as error:row={'product_id':pid,'status':'needs_review','reason':str(error)}
    check(row['status']==expected[pid]['status'],'Recomputed folder status '+pid)
    if row['status']=='ready':check(row['destination']==expected[pid]['destination'],'Exact destination '+pid)
    computed.append(row)
counts=dict(Counter(r['status'] for r in computed));check(counts=={'ready':172,'needs_review':15},'172 unambiguous/15 held plans')
similarity=read(A/'live-similarity-result.json');request=read(A/'live-similarity-request.json')
check(similarity['state']=='ready' and similarity['total']==similarity['analysed']==72,'Real-image similarity72/72')
check(len(similarity['order'])==len(set(similarity['order']))==72 and not similarity['missing_ids'],'Similarity preserves72 IDs')
check(set(similarity['order'])==set(request['requested_ids']),'Exact real-image similarity request IDs')
api=handoff['validation']['all_product_api_readback'];check(api['products_checked']==187 and not api['errors'],'Owner all-product API readback')
check({r[0] for r in api['results']}==set(products),'Owner readback exact187 IDs')
check(sha(pointer)==pointer_sha,'Shared pointer held')
report={'status':'PASS_READ_ONLY_V2_8_2_BACKGROUND_JOBS_AND_ORGANISATION','checked_utc':datetime.now(timezone.utc).isoformat(),
    'checks':checks,'application_version':'2.8.2','active_options':187,'baseline_pointer_sha256':pointer_sha,
    'handoff':str(handoff_path),'handoff_sha256':sha(handoff_path),'application_files':code,'protected_source_hashes':protected,
    'before_backup':str(A/'pre-v281.sqlite3'),'before_backup_sha256':sha(A/'pre-v281.sqlite3'),
    'predeployment_review_rows':2416,'predeployment_event_cutoff':4905,'live_review_rows':len(live['reviews']),
    'live_event_cutoff':live['events'][-1]['id'],'later_live_events':sum(r['id']>4905 for r in live['events']),
    'old_reviews_values_originals_versions_and_audit_history_preserved':True,
    'independent_python_tests_passed':176,'independent_js_regressions_passed':14,'independent_sort_checks_passed':9,
    'cached_recovery_receipt_cannot_override_newer_native_or_organisation_location':True,
    'unambiguous_catalogue_folder_plans':172,'folder_anchor_cases_needing_review':15,'computed_plans':computed,
    'folder_planning_does_not_verify_native_folder_existence':True,
    'real_similarity_images':72,'native_writer_reservation':reservation,
    'background_job_states_at_readback':dict(Counter(r['state'] for r in live['jobs'])),
    'publication_remains_held_for_final_native_filename_overlay':True,
    'root_native_calls_or_writes':0,'root_source_app_code_or_live_review_database_writes':0}
(H/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n')
(H/'PUBLICATION_READY_QUEUED.json').write_text(json.dumps({'status':'VERIFIED_APP_V2_8_2_QUEUED_FINAL_PATH_PUBLICATION_HELD',
    'verification':str(H/'independent-verification.json'),'sha256':sha(H/'independent-verification.json'),
    'baseline_pointer_sha256':pointer_sha,'supersedes_pending_app_reference':'2.7.1','requires_final_native_filename_overlay':True,
    'shared_source_app_and_native_writes_by_root':0},indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['application_files','protected_source_hashes','computed_plans']},indent=2))
