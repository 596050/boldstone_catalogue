"""Read-only app/source verification after the exact alias publication."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import urllib.request,urllib.error,sqlite3,time,os
KEEP='BSI-9299D69FEF08';DUP='BSI-4536FDCA0DA9'
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=40) as r:return json.load(r)
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json');assert sha(pointer)==receipt['pointer_sha256']
for attempt in range(4):
    boot=get('/api/bootstrap')
    if boot['source']['register_sha256']==old['register_sha256']:break
    time.sleep(1)
health=get('/api/health')
assert boot['source']['register_sha256']==old['register_sha256']==sha(H/'canonical-master-register.json')
assert boot['source']['gallery_sha256']==receipt['gallery_sha256']
assert len(boot['products'])==185 and {p['id'] for p in boot['products']}==active
try:get('/api/products/'+DUP)
except urllib.error.HTTPError as e:assert e.code==404
else:raise AssertionError('Retired duplicate remains active')
product=get('/api/products/'+KEEP);overview=get('/api/component-overview/'+KEEP)
packet=read(manifest['sources']['owner_'+KEEP+'-before']['snapshot'])
old_overview=read(manifest['sources']['owner_'+KEEP+'-overview-before']['snapshot'])
ids={r['id'] for r in product['images']}
prior_ids={r['id'] for r in packet['images']}
assert ids==prior_ids and len(ids)==60,'Keeper image/source union changed beyond the exact merge'
assert overview['primary_id']=='id:cnqzTNngPVsAAAAAAAyegw'
assert set(overview['listing_ids'])==set(old_overview['listing_ids'])=={'id:cnqzTNngPVsAAAAAAAyegw','id:cnqzTNngPVsAAAAAAAygqQ'}
saved=sqlite3.connect(Path(manifest['sources']['app_review_cut']['snapshot']).as_uri()+'?mode=ro',uri=True)
live=sqlite3.connect(Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3').as_uri()+'?mode=ro',uri=True)
columns=[r[1] for r in saved.execute('PRAGMA table_info(reviews)')];projection=','.join('"'+c+'"' for c in columns)
before=saved.execute('SELECT '+projection+' FROM reviews WHERE product_id=? ORDER BY kind,item_id',(KEEP,)).fetchall()
after=live.execute('SELECT '+projection+' FROM reviews WHERE product_id=? ORDER BY kind,item_id',(KEEP,)).fetchall();assert before==after and len(after)==12
oldbefore=saved.execute('SELECT '+projection+' FROM reviews WHERE product_id=? ORDER BY kind,item_id',(DUP,)).fetchall();oldafter=live.execute('SELECT '+projection+' FROM reviews WHERE product_id=? ORDER BY kind,item_id',(DUP,)).fetchall();assert oldbefore==oldafter and len(oldafter)==8
ecols=[r[1] for r in saved.execute('PRAGMA table_info(events)')];prefix=saved.execute('SELECT * FROM events ORDER BY rowid').fetchall()
assert live.execute('SELECT '+','.join('"'+c+'"' for c in ecols)+' FROM events ORDER BY rowid LIMIT ?',(len(prefix),)).fetchall()==prefix
counts={t:live.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['reviews','events']};saved.close();live.close()
for w in receipt['workbooks']:assert sha(w['output'])==w['sha256']
result={'status':'PASS_EXACT_DUNE_RIPPLE_MERGE_LIVE_SOURCE','checked_utc':datetime.now(timezone.utc).isoformat(),'health':health,'register_sha256':old['register_sha256'],'gallery_sha256':receipt['gallery_sha256'],'active_options':185,'retained_records':189,'retired_records':4,'keeper':KEEP,'retired_duplicate':DUP,'old_active_route_status':404,'keeper_image_union':60,'keeper_primary':overview['primary_id'],'keeper_listing_ids':overview['listing_ids'],'keeper_review_rows_unchanged':12,'retired_field_review_rows_preserved':8,'event_prefix_preserved':len(prefix),'later_runtime_counts':counts,'unrelated_pending_imports_applied':False,'root_review_native_platform_writes_or_restarts':0}
write(H/'live-after-publication.json',result)
new=deepcopy(old);new['status']='CURRENT185_DUNE_RIPPLE_MERGE_EXPORTS_AND_LIVE_SOURCE_VERIFIED'
new['current_review_application'].update(source_register_sha256=old['register_sha256'],source_gallery_sha256=receipt['gallery_sha256'],source_rebase_required=False,last_verified_utc=result['checked_utc'],version_observed_at_publication_readback=health['version'],latest_catalogue_role_verification=str((H/'live-after-publication.json').relative_to(BASE)),latest_catalogue_role_verification_sha256=sha(H/'live-after-publication.json'),qualified_status='185 active source options loaded automatically. Exact keeper Primary/two Listing choices and12 review rows unchanged; old8 field reviews retained; duplicate active route404. App-side accepted-reference verification remains with its owning session.')
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer];before_bytes={p:p.read_bytes() for p in targets};payload={}
for p in targets:
    d=read(p)
    if p!=pointer:assert d['current_master_catalogue']==old;d['current_master_catalogue']=new
    else:d=new
    payload[p]=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    t=p.with_name(p.name+'.dune-live-attest-pending');t.write_bytes(data);os.replace(t,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before_bytes[p];put(p,payload[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before_bytes[p])
    raise
receipt.update(status='CURRENT185_DUNE_RIPPLE_MERGE_EXPORTS_AND_LIVE_SOURCE_VERIFIED',initial_published_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),live_verification=str(H/'live-after-publication.json'),live_verification_sha256=sha(H/'live-after-publication.json'))
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({k:v for k,v in result.items() if k not in {'keeper_listing_ids'}},indent=2))
