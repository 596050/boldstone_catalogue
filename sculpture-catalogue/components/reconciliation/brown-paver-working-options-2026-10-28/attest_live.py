"""Read-only live application proof: working references never auto-select Primary."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import urllib.request,sqlite3,time,os
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=40) as r:return json.load(r)
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json');assert sha(pointer)==receipt['pointer_sha256']
for attempt in range(5):
    boot=get('/api/bootstrap')
    if boot['source']['register_sha256']==old['register_sha256']:break
    time.sleep(1)
health=get('/api/health')
assert boot['source']['register_sha256']==old['register_sha256']==sha(H/'canonical-master-register.json')
assert boot['source']['gallery_sha256']==receipt['gallery_sha256']
assert len(boot['products'])==187 and {p['id'] for p in boot['products']}==active
proof=[]
for o in read(H/'new-paver-options.json'):
    pid=o['product_id'];product=get('/api/products/'+pid);overview=get('/api/component-overview/'+pid)
    write(H/(pid+'-product-live.json'),product);write(H/(pid+'-overview-live.json'),overview)
    assert o['file_id'] in {x['id'] for x in product['images']},'Audited source image missing'
    assert overview['primary_id'] is None and overview['listing_ids']==[],'Source-only reference became a saved image approval'
    assert overview.get('source_reference_id')==o['file_id'],'Audited reference identity'
    assert overview['primary_listing']['status']=='missing','Missing saved Primary must remain visible'
    fields={r['key']:r for r in product['fields']}
    for key in ['Dimensions / depth','Weight','Material / finish']:
        assert fields[key]['value']==o['master_fields'][key]['display'],key+' working display did not project'
    assert 'keyhole' in fields['Fixing']['value'].lower() and 'french cleat' in fields['Fixing']['value'].lower(),'Offered fixing choices'
    assert fields['Price']['value']=='£225 — estimate' and fields['Availability']['value']=='made to order' and fields['Lead time']['value']=='1–2 weeks','Working selling proposals'
    assert 'hypothesis' in fields['Material / finish']['value'] and 'AC730' not in fields['Material / finish']['value'],'No material hypothesis upgrade'
    proof.append({'product_id':pid,'name':o['name'],'source_reference_id':overview['source_reference_id'],'primary_id':overview['primary_id'],'listing_ids':overview['listing_ids'],'primary_listing':overview['primary_listing'],'image_count':len(product['images']),'working_fields':{k:fields[k] for k in ['Dimensions / depth','Weight','Material / finish','Fixing','Price','Availability','Lead time']}})
saved=sqlite3.connect(Path(manifest['sources']['app_review_cut']['snapshot']).as_uri()+'?mode=ro',uri=True)
livepath=Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3');live=sqlite3.connect(livepath.as_uri()+'?mode=ro',uri=True)
for o in read(H/'new-paver-options.json'):
    assert live.execute('SELECT COUNT(*) FROM reviews WHERE product_id=?',(o['product_id'],)).fetchone()[0]==0,'Unexpected saved review on a new working option'
ecols=[r[1] for r in saved.execute('PRAGMA table_info(events)')];prefix=saved.execute('SELECT * FROM events ORDER BY rowid').fetchall()
assert live.execute('SELECT '+','.join('"'+c+'"' for c in ecols)+' FROM events ORDER BY rowid LIMIT ?',(len(prefix),)).fetchall()==prefix,'Review event prefix changed'
counts={t:live.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['reviews','events']};saved.close();live.close()
for w in receipt['workbooks']:assert sha(w['output'])==w['sha256']
result={'status':'PASS_TWO_WORKING_OPTIONS_REFERENCE_ONLY_LIVE_SOURCE','checked_utc':datetime.now(timezone.utc).isoformat(),'health':health,'register_sha256':old['register_sha256'],'gallery_sha256':receipt['gallery_sha256'],'active_options':187,'retained_records':191,'retired_records':4,'new_options':proof,'new_saved_review_rows':0,'new_listing_primary_or_advertising_approvals':0,'event_prefix_preserved':len(prefix),'later_runtime_counts':counts,'unrelated_pending_imports_applied':False,'root_review_native_platform_writes_or_restarts':0}
write(H/'live-after-publication.json',result)
new=deepcopy(old);new['status']='CURRENT187_BROWN_WORKING_OPTIONS_EXPORTS_AND_LIVE_SOURCE_VERIFIED'
new['current_review_application'].update(source_register_sha256=old['register_sha256'],source_gallery_sha256=receipt['gallery_sha256'],source_rebase_required=False,last_verified_utc=result['checked_utc'],version_observed_at_publication_readback=health['version'],latest_catalogue_role_verification=str((H/'live-after-publication.json').relative_to(BASE)),latest_catalogue_role_verification_sha256=sha(H/'live-after-publication.json'),qualified_status='187 active source options loaded automatically. Both Brown image references are present; saved Primary remains missing and Listing empty; zero reviews created for the new IDs. Source images and saved use choices remain separate. App code and native jobs remain with sibling.')
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer];before={p:p.read_bytes() for p in targets};payload={}
for p in targets:
    d=read(p)
    if p!=pointer:assert d['current_master_catalogue']==old;d['current_master_catalogue']=new
    else:d=new
    payload[p]=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    t=p.with_name(p.name+'.brown-live-attest-pending');t.write_bytes(data);os.replace(t,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p];put(p,payload[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt.update(status=new['status'],initial_published_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),live_verification=str(H/'live-after-publication.json'),live_verification_sha256=sha(H/'live-after-publication.json'))
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
handoff=read(H/'app-owner-handoff.json');handoff.update(status='CANONICAL187_SOURCE_PUBLISHED_AND_LIVE_REFERENCE_ROLES_VERIFIED',live_verification=str(H/'live-after-publication.json'),live_verification_sha256=sha(H/'live-after-publication.json'));write(H/'app-owner-handoff.json',handoff)
print(json.dumps({k:v for k,v in result.items() if k not in {'health','new_options'}},ensure_ascii=False))
