"""Read back current source loading and the completed image-use exclusions."""
from common import *
from copy import deepcopy
from datetime import datetime, timezone
import os,sqlite3,urllib.request,time

def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=45) as response:return json.load(response)
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json')
assert sha(pointer)==receipt['pointer_sha256']
for attempt in range(4):
    boot=get('/api/bootstrap')
    if boot['source']['register_sha256']==old['register_sha256']:break
    time.sleep(1)
health=get('/api/health')
assert len(boot['products'])==186 and {p['id'] for p in boot['products']}==active
assert boot['source']['register_sha256']==old['register_sha256']==sha(H/'canonical-master-register.json')
assert boot['source']['gallery_sha256']==receipt['gallery_sha256']
library=get('/api/library');images={r['id']:r for r in library['images']};reviews={(r['kind'],r['product_id'],r['item_id']):r for r in library['reviews']}
effective_types=lambda fid:reviews.get(('asset','',fid),{}).get('data',{}).get('types',images.get(fid,{}).get('types',[]))
remaining=[(r['product_id'],r['item_id']) for r in library['reviews'] if r['kind']=='image' and r['product_id'] in active and 'listing' in r['data'].get('uses',[]) and 'in_situ' in effective_types(r['item_id'])]
assert not remaining,'A later saved Listing selection conflicts with the completed In situ policy'
exclusions=read(H/'listing-use-exclusions.json')
for row in exclusions:
    r=reviews[('image',row['product_id'],row['file_id'])]
    assert r['version']>=row['review_version'] and 'listing' not in r['data'].get('uses',[]) and not r['data'].get('primary')
    assert effective_types(row['file_id'])==row['effective_image_types']
request_states=[];later_choices=[]
for o in g['options']:
    if o['product_id'] not in active or o.get('file_id') or not o.get('historical_primary_reference'):continue
    v=get('/api/component-overview/'+o['product_id'])
    fid=v.get('primary_id')
    if fid:
        r=reviews[('image',o['product_id'],fid)]
        assert r['data'].get('decision')=='reviewed' and r['data'].get('primary') is True and 'listing' in r['data'].get('uses',[])
        assert 'in_situ' not in effective_types(fid)
        assert r['updated_at']>manifest['policy_cut_utc'],'Earlier saved Primary was missed by the scoped input capture'
        later_choices.append({'product_id':o['product_id'],'name':o['name'],'file_id':fid,'review_version':r['version'],'review_updated_at':r['updated_at'],'decision_source_register_sha256':r['source_hash'],'review_data':r['data'],'image_url':images[fid]['url'],'folder_url':images[fid]['folder_url'],'folder_id':images[fid]['folder_id'],'scope':'Explicit later saved Primary choice. Queued separately; frozen policy workbook cut remains unchanged.'})
    else:assert v.get('primary_listing',{}).get('status')=='missing'
    request_states.append({'product_id':o['product_id'],'name':o['name'],'published_primary':None,'current_app_primary':fid,'current_app_status':v.get('primary_listing')})
assert len(request_states)==6
saved=sqlite3.connect(Path(manifest['sources']['app_review_cut']['snapshot']).as_uri()+'?mode=ro',uri=True)
current=sqlite3.connect(Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3').as_uri()+'?mode=ro',uri=True)
columns=[r[1] for r in saved.execute('PRAGMA table_info(events)')]
prefix=saved.execute('SELECT * FROM events ORDER BY rowid').fetchall()
assert current.execute('SELECT '+','.join('"'+c+'"' for c in columns)+' FROM events ORDER BY rowid LIMIT ?',(len(prefix),)).fetchall()==prefix
counts={t:current.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['reviews','events']}
saved.close();current.close()
for r in receipt['workbooks']:assert sha(r['output'])==r['sha256']
result={'status':'PASS_EXCLUSION_PUBLICATION_AND_LIVE_SOURCE','checked_utc':datetime.now(timezone.utc).isoformat(),'health':health,'register_sha256':old['register_sha256'],'gallery_sha256':receipt['gallery_sha256'],'active_options':186,'primary_references_at_cut':179,'listing_exclusions_verified':91,'unique_images':68,'affected_active_options':30,'remaining_in_situ_listing_choices':remaining,'six_primary_request_readbacks':request_states,'later_saved_primary_choices':later_choices,'current_open_choices_among_the_six_published_requests':sum(not x['current_app_primary'] for x in request_states),'captured_event_prefix_preserved':len(prefix),'runtime_review_counts':counts,'native_inventory_cut_utc':manifest['native_inventory_cut_utc'],'policy_cut_utc':manifest['policy_cut_utc'],'later_live_native_observation':boot['source'].get('live_dropbox'),'publisher_native_app_or_platform_writes_or_restarts':0}
write(H/'live-after-publication.json',result)
new=deepcopy(old);new['status']='CURRENT186_IN_SITU_LISTING_EXCLUSIONS_LIVE_SOURCE_VERIFIED'
new['current_review_application'].update(source_register_sha256=old['register_sha256'],source_gallery_sha256=receipt['gallery_sha256'],source_rebase_required=False,last_verified_utc=result['checked_utc'],version_observed_at_publication_readback=health['version'],latest_catalogue_role_verification=str((H/'live-after-publication.json').relative_to(BASE)),latest_catalogue_role_verification_sha256=sha(H/'live-after-publication.json'),qualified_status='New source loaded automatically.91 exclusions independently verified. Six requests belong to the frozen policy cut; later saved choices are recorded separately. Root did not write app reviews or restart the app.')
new['latest_post_cut_primary_observations']=request_states
if later_choices:
    write(H/'later-saved-primary-choices.json',later_choices)
    new['queued_post_publication_imports']['later_saved_primary_choices']={'path':str((H/'later-saved-primary-choices.json').relative_to(BASE)),'sha256':sha(H/'later-saved-primary-choices.json'),'count':len(later_choices),'scope':'No repeat owner question needed for these exact saved choices; import in the next separately dated master revision.'}
new['latest_app_native_overlay_observation']={'checked_utc':result['checked_utc'],'native_snapshot':result['later_live_native_observation'],'scope':'Later live observation only. Native file changes are not merged into the retained19:03UTC inventory.'}
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer]
before={p:p.read_bytes() for p in targets};payloads={}
for p in targets:
    d=read(p)
    if p!=pointer:assert d['current_master_catalogue']==old;d['current_master_catalogue']=new
    else:d=new
    payloads[p]=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    tmp=p.with_name(p.name+'.policy-attest-pending');tmp.write_bytes(data);os.replace(tmp,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p];put(p,payloads[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt.update(status='IN_SITU_LISTING_EXCLUSIONS_EXPORTS_AND_LIVE_SOURCE_VERIFIED',initial_published_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),live_verification=str(H/'live-after-publication.json'),live_verification_sha256=sha(H/'live-after-publication.json'))
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({'status':receipt['status'],'active_options':186,'app_version':health['version'],'verified_exclusions':91,'open_primary_choices_at_policy_cut':len(request_states),'later_explicit_primary_choices':len(later_choices),'current_open_choices_among_six':result['current_open_choices_among_the_six_published_requests'],'captured_events_preserved':len(prefix)}))
