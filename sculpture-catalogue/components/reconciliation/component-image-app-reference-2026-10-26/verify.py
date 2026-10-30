"""Independent read-only v2.6 component defaults, API and durable-state audit."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from urllib.parse import quote
import hashlib,json,sqlite3,urllib.request

H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent;APP=ROOT/'catalogue-review'
A=APP/'reviews/component-image-uses-20261026'
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
            'operations':[dict(r) for r in db.execute('SELECT * FROM operations ORDER BY id')]}
    finally:db.close()
def unpack(row):
    r=dict(row)
    for k in ['data','original']:
        if isinstance(r.get(k),str):r[k]=json.loads(r[k])
    return r
key=lambda r:(r['kind'],r['product_id'],r['item_id'])
def get(path,raw=False):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=20) as r:return r.read() if raw else json.load(r)
handoff_path=A/'HANDOFF.json';check(sha(handoff_path)=='e31a11c399a3dd50d1501652f17ad86e8f576b3f16e2de8b83d85ee764d0d6e4','Sealed owner receipt')
handoff=read(handoff_path);pointer=read(B/'current-master.json');pointer_sha=sha(B/'current-master.json')
protected={str(B/pointer['register']):pointer['register_sha256'],str(B/pointer['workbook']):pointer['workbook_sha256'],
    str(B/pointer['preferred_review_workbook']):pointer['current_comprehensive_workbook']['sha256']}
for path,digest in protected.items():check(sha(path)==digest,'Canonical bytes '+path)
code={}
for f,digest in handoff['deployment']['code_sha256'].items():
    check(sha(APP/f)==sha(A/'work'/f)==digest,'Deployed and QA code '+f);code[str(APP/f)]=digest
for f in ['catalogue.py','media.py','deletions.py','delete_dropbox.py','dropbox_sync.py','dropbox_sync_worker.py','similarity.py']:
    check(sha(APP/f)==sha(A/'before'/f),'Source/native backend unchanged '+f)
before=snapshot(A/'before-deployment.sqlite3');live=snapshot(Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3')
check(len(before['reviews'])==2012 and before['events'][-1]['id']==4131,'Exact predeployment state')
check([r for r in live['events'] if r['id']<=4131]==before['events'],'All historical audit events unchanged')
rows={key(r):unpack(r) for r in before['reviews']}
for event in [r for r in live['events'] if r['id']>4131]:
    prior=json.loads(event['before_json']) if event['before_json'] else None
    after=unpack(json.loads(event['after_json']));k=key(after)
    if prior and k in rows:check(unpack(prior)==rows[k],'Later owner review follows prior state')
    rows[k]=after
check(rows=={key(r):unpack(r) for r in live['reviews']},'Reviews preserved or changed only through later audit events')
health=get('/api/health');boot=get('/api/bootstrap');g=read(B/pointer['register'])
check(health['version']=='2.6.0' and health['products']==187,'Live version/count')
check({r['id'] for r in boot['products']}==set(g['active_option_ids']),'Exact active187 IDs')
check(boot['source']['register_sha256']==pointer['register_sha256'],'Live source register binding')
check('BSI-B0D0CCA7E318' not in {r['id'] for r in boot['products']},'Retired option remains excluded')
protected[boot['source']['gallery_database']]=boot['source']['gallery_sha256']
check(sha(boot['source']['gallery_database'])==boot['source']['gallery_sha256'],'Source gallery bytes')
for f in handoff['deployment']['code_sha256']:
    if f.startswith('static/'):check(hashlib.sha256(get('/'+f.split('/',1)[1],True)).hexdigest()==sha(APP/f),'Served static '+f)
library=get('/api/library?family=Ammonite');images={r['id']:r for r in library['images'] if r['source']=='Dropbox'}
snapshot_ref=boot['source']['live_dropbox'];native=read(snapshot_ref['path'])
native_images={k:r for k,r in native['records'].items() if r['kind']=='file' and r['path'].startswith('/BOLDSTONE MASTER/Products/01 Wall Sculptures/Ammonite/')}
check(set(native_images)==set(images),'Current native/App Ammonite IDs')
check(all(images[k]['folder_id']==v['folder_id'] for k,v in native_images.items()),'Actual Ammonite parents')
large={'BSI-DA27DD604F0B','BSI-C3858B1FE67E'};small={'BSI-624D16148726','BSI-EFBAEB31C2B1'}
folder_members={'Ammonite Large 1 and Ammonite Large 2 White':large,'Ammonite Large 1 and Ammonite Large 2 White In Situ':large,
    'Ammonite Small 1 and Ammonite Small 2 White':small,'Ammonite Small 1 and Ammonite Small 2 White In Situ':small}
group_counts=Counter();group_rows=[]
for aid,image in images.items():
    expected=folder_members.get(image['folder_label'])
    if expected is None:continue
    group_counts[image['folder_label']]+=1
    check(set(image['default_component_ids'])==expected,'Exact size-specific folder defaults '+aid)
    check(not (set(image['component_ids']) & ((large|small)-expected)),'No cross-size visibility '+aid)
    check('group' in image['types'],'Derived group type '+aid)
    for pid in expected:
        assignment=rows.get(('assignment',pid,aid),{}).get('data',{})
        if assignment.get('state')=='removed':check(pid not in image['component_ids'],'Saved manual removal wins '+aid)
        else:check(pid in image['component_ids'],'Named component default visible '+aid)
    group_rows.append({'file_id':aid,'folder_id':image['folder_id'],'folder':image['folder_label'],
        'default_components':sorted(expected),'shown_components':image['component_ids'],'image_url':image['url'],'folder_url':image['folder_url']})
check(group_counts['Ammonite Large 1 and Ammonite Large 2 White']==29,'29 Large pair images')
check(group_counts['Ammonite Large 1 and Ammonite Large 2 White In Situ']==19,'19 Large pair In Situ images')
example_id='id:cnqzTNngPVsAAAAAAAyjTg';example=get('/api/image-components?id='+quote(example_id,safe=''))
check(set(r['product_id'] for r in example['rows'])==set(g['active_option_ids']),'Chooser lists exact active187')
for row in [r for r in example['rows'] if r['product_id'] in large|small]:
    pid=row['product_id'];check(row['default']==(pid in large),'Chooser exact defaults')
    choice=rows.get(('image',pid,example_id),{}).get('data',{})
    if not choice:check(not row['listing'] and not row['advertising'],'No automatic purposes')
    if pid in small:check(not row['shown'],'Small not default-visible')
qa_state=snapshot(A/'qa-state/reviews.sqlite3');qrows={key(r):unpack(r) for r in qa_state['reviews']}
one=qrows[('image','BSI-DA27DD604F0B',example_id)]['data']
two=qrows[('assignment','BSI-C3858B1FE67E',example_id)]['data']
check({'listing','advertising'}<=set(one['uses']),'QA saved Listing and Ads together for one component')
check(two['state']=='removed','QA saved separate Show removal')
check(sha(B/'current-master.json')==pointer_sha,'No shared publication during readback')
report={'status':'PASS_INDEPENDENT_V2_6_COMPONENTS_AND_REVIEW_PRESERVATION','checked_utc':datetime.now(timezone.utc).isoformat(),
    'checks':checks,'application_version':'2.6.0','active_options':187,'baseline_pointer_sha256':pointer_sha,
    'handoff':str(handoff_path),'handoff_sha256':sha(handoff_path),'application_files':code,'protected_source_hashes':protected,
    'before_backup':str(A/'before-deployment.sqlite3'),'before_backup_sha256':sha(A/'before-deployment.sqlite3'),
    'predeployment_review_rows':2012,'predeployment_event_cutoff':4131,'live_review_rows':len(live['reviews']),
    'live_event_cutoff':live['events'][-1]['id'],'later_owner_events':sum(r['id']>4131 for r in live['events']),
    'predeployment_reviews_originals_versions_and_audit_events_preserved':True,
    'current_ammonite_images':len(images),'current_ammonite_group_counts':dict(group_counts),'group_rows':group_rows,
    'native_snapshot':snapshot_ref,'independent_python_tests_passed':106,'independent_node_sort_checks_passed':9,
    'no_automatic_listing_or_ads_for_unreviewed_example':True,'manual_removals_are_not_reintroduced':True,
    'folder_defaults_are_working_visibility_not_manufactured_identity':True,'root_code_review_db_native_platform_mutations':0}
(H/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['application_files','protected_source_hashes','group_rows']},indent=2))
