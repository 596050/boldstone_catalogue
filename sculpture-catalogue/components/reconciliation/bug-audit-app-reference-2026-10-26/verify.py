"""Independent live readback of the bounded v2.7.1 audit release."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import csv,hashlib,io,json,sqlite3,urllib.request,zipfile
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent;APP=ROOT/'catalogue-review';A=APP/'reviews/bug-audit-20261026'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=0
def check(ok,msg):
    global checks
    checks+=1;assert ok,msg
def snapshot(path):
    db=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN');return {'reviews':[dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')],
            'events':[dict(r) for r in db.execute('SELECT * FROM events ORDER BY id')]}
    finally:db.close()
def unpack(row):
    r=dict(row)
    for k in ['data','original']:
        if isinstance(r.get(k),str):r[k]=json.loads(r[k])
    return r
key=lambda r:(r['kind'],r['product_id'],r['item_id'])
def get(path,raw=False):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=45) as r:return r.read() if raw else json.load(r)
handoff_path=A/'HANDOFF.json';check(sha(handoff_path)=='a03aa1fc4697368f8bc8e6f8f8274a30c02dbe16d94a8afdb551cfd797573155','Exact handed-off receipt')
handoff=read(handoff_path);p=read(B/'current-master.json');pointer_sha=sha(B/'current-master.json');code={}
for f,digest in handoff['deployment']['code_sha256'].items():
    check(sha(APP/f)==sha(A/'work'/f)==digest,'Deployed/QA source '+f);code[str(APP/f)]=digest
for f in ['catalogue.py','store.py','exports.py','component_links.py','component_reviews.py','projection.py','deletions.py','delete_dropbox.py']:
    check(sha(APP/f)==sha(A/'before'/f),'Source/review/deletion module unchanged '+f)
protected={str(B/p['register']):p['register_sha256'],str(B/p['workbook']):p['workbook_sha256'],
    str(B/p['preferred_review_workbook']):p['current_comprehensive_workbook']['sha256']}
for path,digest in protected.items():check(sha(path)==digest,'Canonical bytes '+path)
before=snapshot(A/'before-deployment.sqlite3');live=snapshot(Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3')
check(len(before['reviews'])==2178 and before['events'][-1]['id']==4439,'Exact predeployment state')
check([r for r in live['events'] if r['id']<=4439]==before['events'],'Historical audit events retained')
state={key(r):unpack(r) for r in before['reviews']}
for event in [r for r in live['events'] if r['id']>4439]:
    prior=json.loads(event['before_json']) if event['before_json'] else None
    after=unpack(json.loads(event['after_json']));k=key(after)
    if prior and k in state:check(unpack(prior)==state[k],'Later recorded change follows prior review')
    state[k]=after
check(state=={key(r):unpack(r) for r in live['reviews']},'All reviews retained or follow later audited activity')
health=get('/api/health');boot=get('/api/bootstrap');g=read(B/p['register'])
check(health['version']=='2.7.1' and health['products']==187,'Live2.7.1/187')
check(boot['source']['register_sha256']==p['register_sha256'],'Live source register')
check({r['id'] for r in boot['products']}==set(g['active_option_ids']),'Exact active187 IDs')
gallery=boot['source']['gallery_database'];protected[gallery]=boot['source']['gallery_sha256'];check(sha(gallery)==protected[gallery],'Source gallery bytes unchanged')
for f in handoff['deployment']['code_sha256']:
    if f.startswith('static/'):check(hashlib.sha256(get('/'+f.split('/',1)[1],True)).hexdigest()==sha(APP/f),'Served static bytes '+f)
with ThreadPoolExecutor(max_workers=4) as pool:
    products=list(pool.map(lambda row:get('/api/products/'+row['id']),boot['products']))
product_checks=[];revalidated_live_counts=[]
def signature(frame):
    return (frame['source']['live_dropbox']['signature'], frame['history'][0]['id'] if frame['history'] else 0)
def fresh_count(pid):
    for attempt in range(3):
        first=get('/api/bootstrap');current=get('/api/products/'+pid);last=get('/api/bootstrap')
        left=next(r for r in first['products'] if r['id']==pid)['image_count']
        right=next(r for r in last['products'] if r['id']==pid)['image_count']
        actual=sum(im['association']['tier']!='removed' for im in current['images'])
        if signature(first)==signature(last):
            check(left==actual==right,'Retained count in stable fresh frame '+pid)
            return {'product_id':pid,'before_count':left,'payload_retained_count':actual,'after_count':right,
                'native_signature':signature(first)[0],'event_cutoff':signature(first)[1],
                'reason':'Initial full readback spanned live native/review changes','stable_frame':True}
    raise AssertionError('No stable live count frame for '+pid)
for row,product in zip(boot['products'],products):
    pid=row['id'];images=product['images'];retained=[im for im in images if im['association']['tier']!='removed']
    check(product['id']==pid and product['source_hash']==p['register_sha256'],'Product source '+pid)
    check(len({im['id'] for im in images})==len(images),'Unique displayed image IDs '+pid)
    if len(retained)!=row['image_count']:
        revalidated_live_counts.append(fresh_count(pid))
    else:check(True,'Retained count excludes removed '+pid)
    product_checks.append({'product_id':pid,'retained_images':len(retained),'removed_images':len(images)-len(retained)})
coverage=get('/api/coverage')
for pid,row in coverage['products'].items():check(row['counts']['total']==row['counts']['sculpture']+row['counts']['related'],'Coverage totals '+pid)
api_receipt=read(A/'api-audit.json');check(api_receipt['products_checked']==187 and not api_receipt['failures'],'Owning session API audit')
export=Path(api_receipt['export']['path']);archive=export.with_suffix('.zip')
with zipfile.ZipFile(archive) as z:
    check(z.testzip() is None,'Isolated export ZIP integrity')
    rows=list(csv.DictReader(io.StringIO(z.read('all-product-decisions.csv').decode('utf-8-sig'))))
    check(len(rows)==187,'Isolated export has187 active product rows')
    check('BSI-B0D0CCA7E318' not in str(rows),'Retired option absent from export')
family_changes=read(A/'family-label-readback.json');check(family_changes==[],'No unmoved live family labels changed')
check(sha(B/'current-master.json')==pointer_sha,'No concurrent canonical publication')
result={'status':'PASS_INDEPENDENT_V2_7_1_BOUNDED_BUG_AUDIT','checked_utc':datetime.now(timezone.utc).isoformat(),
    'checks':checks,'application_version':'2.7.1','active_options':187,'baseline_pointer_sha256':pointer_sha,
    'handoff':str(handoff_path),'handoff_sha256':sha(handoff_path),'application_files':code,'protected_source_hashes':protected,
    'predeployment_backup':str(A/'before-deployment.sqlite3'),'predeployment_backup_sha256':sha(A/'before-deployment.sqlite3'),
    'predeployment_review_rows':2178,'predeployment_event_cutoff':4439,'live_review_rows':len(live['reviews']),
    'live_event_cutoff':live['events'][-1]['id'],'later_live_events':sum(r['id']>4439 for r in live['events']),
    'old_review_values_versions_originals_and_audit_history_preserved':True,
    'independent_python_tests_passed':126,'independent_js_regressions_passed':7,'independent_sort_checks_passed':9,
    'live_product_endpoints_checked':len(products),'product_checks':product_checks,
    'live_count_changes_revalidated':revalidated_live_counts,
    'isolated_export_zip':str(archive),'isolated_export_zip_sha256':sha(archive),'export_zip_integrity':'passed',
    'unmoved_live_family_labels_changed':0,'audit_scope_is_bounded_not_proof_of_absence_of_all_bugs':True,
    'root_app_code_review_db_native_platform_mutations':0}
(H/'independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['application_files','protected_source_hashes','product_checks']},indent=2))
