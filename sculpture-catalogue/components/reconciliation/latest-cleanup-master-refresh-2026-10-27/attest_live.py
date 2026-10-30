"""Verify the frozen publication and observe newer app choices separately."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import os,sqlite3,urllib.request,urllib.error

get=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8767'+p,timeout=60))
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json')
assert sha(pointer)==receipt['pointer_sha256']
boot=get('/api/bootstrap');health=get('/api/health')
assert len(boot['products'])==186 and {p['id'] for p in boot['products']}==active
assert boot['source']['register_sha256']==old['register_sha256']==sha(H/'canonical-master-register.json')
assert boot['source']['gallery_sha256']==old['current_published_gallery_projection']['database_sha256']
assert old['preferred_review_workbook']==old['current_comprehensive_workbook']['path']
assert old['preferred_review_workbook_sha256']==old['current_comprehensive_workbook']['sha256']
try:get('/api/products/BSI-E7CDC2CFAC9D')
except urllib.error.HTTPError as error:assert error.code==404
else:raise AssertionError('Retired duplicate returned as active')
observed=[]
for c in read(H/'register-preparation.json')['primary_changes']:
    o=get('/api/products/'+c['product_id']);v=get('/api/component-overview/'+c['product_id'])
    assert o['source_hash']==old['register_sha256']
    assert any(im['id']==c['file_id'] for im in o['images'])
    observed.append({'product_id':c['product_id'],'published_primary':c['file_id'],'current_app_primary':v.get('primary_id')})
for pid in ['BSI-CAB0D722062D','BSI-EC5966EA0C7A','BSI-F61AE4921B6B','BSI-09C1A55D460D','BSI-8DDEA2FEC9DA','BSI-6F3C6CD908A0','BSI-DB7FBD3E1323']:
    o=get('/api/products/'+pid);expected=options[pid]['current_series_reference']['file_id']
    assert o['photo_coverage']['series'].startswith('Available')
    assert any(im['id']==expected for im in o['images'])
request_states=[]
for pid in ['BSI-09C1A55D460D','BSI-9299D69FEF08']:
    v=get('/api/component-overview/'+pid)
    request_states.append({'product_id':pid,'published_primary':options[pid].get('file_id'),'current_app_primary':v.get('primary_id'),'current_app_status':v.get('primary_listing')})
saved=sqlite3.connect(Path(manifest['sources']['app_review_cut']['snapshot']).as_uri()+'?mode=ro',uri=True)
runtime=Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3')
current=sqlite3.connect(runtime.as_uri()+'?mode=ro',uri=True)
columns=[r[1] for r in saved.execute('PRAGMA table_info(events)')]
prefix=saved.execute('SELECT * FROM events ORDER BY rowid').fetchall()
assert current.execute('SELECT '+','.join('"'+c+'"' for c in columns)+' FROM events ORDER BY rowid LIMIT ?',(len(prefix),)).fetchall()==prefix
counts={t:current.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['reviews','events']}
saved.close();current.close()
for w in receipt['workbooks']:assert sha(w['output'])==w['sha256']
result={'status':'PASS_LATEST_FROZEN_PUBLICATION_AND_LIVE_SOURCE','checked_utc':datetime.now(timezone.utc).isoformat(),'publication_cut_utc':manifest['recorded_utc'],'health':health,'register_sha256':old['register_sha256'],'gallery_sha256':boot['source']['gallery_sha256'],'active_options':186,'published_primary_references':183,'published_context_holds':28,'published_primary_choices_open':2,'published_unheld_series_requests':0,'saved_primary_readbacks':observed,'primary_request_live_observations':request_states,'series_roles_rechecked':7,'captured_event_prefix_preserved':len(prefix),'later_runtime_counts':counts,'later_native_overlay':boot['source'].get('live_dropbox'),'later_changes_not_assigned_to_this_frozen_cut':True,'preferred_review_workbook_matches_current_export':True,'native_or_app_review_writes_or_restarts_by_root':0}
write(H/'live-after-publication.json',result)
new=deepcopy(old);new['status']='CURRENT186_LATEST_CLEANUP_AND_LIVE_SOURCE_VERIFIED'
app=new['current_review_application'];app.update(source_register_sha256=old['register_sha256'],source_gallery_sha256=boot['source']['gallery_sha256'],source_rebase_required=False,last_verified_utc=result['checked_utc'],version_observed_at_publication_readback=health['version'],latest_catalogue_role_verification=str((H/'live-after-publication.json').relative_to(BASE)),latest_catalogue_role_verification_sha256=sha(H/'live-after-publication.json'),qualified_status='Frozen19:03UTC catalogue source loaded automatically. Saved app choices may be newer and remain separately observable. Root did not write app reviews or restart the app.')
owner=BASE.parent/'catalogue-review/reviews/component-review-state-bugs-20261027/verification.json'
if owner.exists():app['latest_owning_session_release_observation']={'path':str(owner),'sha256':sha(owner),'version':read(owner).get('version'),'validation_scope':'Owning-session verification; the last independent full-code check remains separately recorded.'}
new['latest_app_native_overlay_observation']={'checked_utc':result['checked_utc'],'native_snapshot':result['later_native_overlay'],'scope':'Later live observation; do not infer deletion causes or merge it into the19:03UTC file cut.'}
new['latest_post_cut_primary_observations']=request_states
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer]
before={p:p.read_bytes() for p in targets};payloads={}
for p in targets:
    value=read(p)
    if p!=pointer:assert value['current_master_catalogue']==old;value['current_master_catalogue']=new
    else:value=new
    payloads[p]=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    tmp=p.with_name(p.name+'.root-latest-attest-pending');tmp.write_bytes(data);os.replace(tmp,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p];put(p,payloads[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt.update(status='LATEST_CLEANUP_EXPORTS_AND_LIVE_SOURCE_VERIFIED',initial_published_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),live_verification=str(H/'live-after-publication.json'),live_verification_sha256=sha(H/'live-after-publication.json'))
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({'status':receipt['status'],'cut':manifest['recorded_utc'],'active_options':186,'app_version_observed':health['version'],'open_choices_at_cut':2,'current_app_choices':request_states,'captured_events_preserved':len(prefix)}))
