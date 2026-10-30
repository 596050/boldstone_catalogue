"""Independently bind the released app patch without touching app/native state."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import os,re,sqlite3,urllib.request

get=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8767'+p,timeout=60))
health=get('/api/health');assert health['products']==186
boot=get('/api/bootstrap')
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json')
assert sha(pointer)==receipt['pointer_sha256']
assert boot['source']['register_sha256']==old['register_sha256']==sha(H/'canonical-master-register.json')
assert boot['source']['gallery_sha256']==old['current_published_gallery_projection']['database_sha256']
assert {p['id'] for p in boot['products']}==active
for pid in g['latest_qualified_series_review']['positions']:
    product=get('/api/products/'+pid)
    assert product['source_hash']==old['register_sha256']
    assert product['photo_coverage']['series']=='Available — qualified group display reference'
    assert any(im['id']==next(o for o in g['options'] if o['product_id']==pid)['current_series_reference']['file_id'] for im in product['images'])

for workbook in receipt['workbooks']:assert sha(workbook['output'])==workbook['sha256']
qa={'status':'PASS_DUNE_SERIES_LIVE_SOURCE_READBACK','checked_utc':datetime.now(timezone.utc).isoformat(),'health':health,'register_sha256':old['register_sha256'],'gallery_sha256':boot['source']['gallery_sha256'],'active_options':186,'series_roles_verified':3,'open_series_requests':0,'dune_primary_still_unbound':get('/api/component-overview/BSI-09C1A55D460D')['primary_id'] is None,'physical_commercial_platform_or_primary_changes':0,'root_native_or_app_writes_or_restarts':0}
assert qa['dune_primary_still_unbound'],'A later saved Primary choice requires a separate scoped import'
write(H/'live-after-publication.json',qa)
new=deepcopy(old);new['status']='CURRENT186_DUNE_SERIES_COVERAGE_AND_LIVE_SOURCE_VERIFIED';app=new['current_review_application']
app.update(source_register_sha256=old['register_sha256'],source_gallery_sha256=boot['source']['gallery_sha256'],source_rebase_required=False,last_verified_utc=qa['checked_utc'],latest_catalogue_role_verification=str((H/'live-after-publication.json').relative_to(BASE)),latest_catalogue_role_verification_sha256=sha(H/'live-after-publication.json'),version_observed_at_catalogue_role_readback=health['version'])
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
receipt.update(status='DUNE_SERIES_ROLES_AND_LIVE_SOURCE_VERIFIED',initial_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),live_verification=str(H/'live-after-publication.json'),live_verification_sha256=sha(H/'live-after-publication.json'))
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps(qa))
