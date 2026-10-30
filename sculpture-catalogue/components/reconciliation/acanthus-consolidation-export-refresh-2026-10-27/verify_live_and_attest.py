"""Verify automatic source loading; record later native scope separately."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import urllib.request,urllib.error,os

get=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8767'+p,timeout=60))
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json')
assert sha(pointer)==receipt['pointer_sha256']
boot=get('/api/bootstrap');health=get('/api/health');source=boot['source']
assert source['register_sha256']==old['register_sha256']==sha(H/'canonical-master-register.json')
assert source['gallery_sha256']==old['current_published_gallery_projection']['database_sha256']==sha(H/'gallery-projection/complete-image-platform-register.sqlite')
products={p['id']:p for p in boot['products']};assert set(products)==active and len(products)==186
for r in read(H/'white-title-audit-input.json')['corrected']:assert products[r['id']]['name']==r['name'],r['id']
try:get('/api/products/BSI-E7CDC2CFAC9D')
except urllib.error.HTTPError as error:assert error.code==404
else:raise AssertionError('Retired duplicate is still active')
keeper=get('/api/products/BSI-93ADE7C4103D');photo=get('/api/component-overview/BSI-93ADE7C4103D')
assert keeper['source_hash']==old['register_sha256'] and keeper['name']=='Acanthus Two Leaves White'
assert photo['primary_id']=='id:cnqzTNngPVsAAAAAAAufMQ'
assert 'id:cnqzTNngPVsAAAAAAAyj8Q' in photo['listing_ids']
assert 'id:cnqzTNngPVsAAAAAAAyluQ' in photo['in_situ_ids']
assert 'id:cnqzTNngPVsAAAAAAAyluA' not in {a['id'] for a in photo['images']}
before=read(BASE.parent/'catalogue-review/reviews/acanthus-names-20261027/BSI-93ADE7C4103D-pre-consolidation.json')
before_reviews={(r['kind'],r['item_id']):r['data'] for r in before['reviews']}
after_reviews={(r['kind'],r['item_id']):r['data'] for r in keeper['reviews']}
assert all(after_reviews[k]==v for k,v in before_reviews.items())
live=source.get('live_dropbox',{});current=read(live['path'])
candidate='id:cnqzTNngPVsAAAAAAAuQDA';candidate_current=candidate in current.get('records',{})
assert candidate_current,'The previously offered Primary candidate has disappeared; update the question before continuing'
for w in receipt['workbooks']:assert sha(w['output'])==w['sha256'],'Saved workbook changed after verification'
result={'status':'PASS186_AUTOMATIC_APP_SOURCE_RELOAD','checked_utc':datetime.now(timezone.utc).isoformat(),'health':health,'register_sha256':source['register_sha256'],'gallery_sha256':source['gallery_sha256'],'active_options':186,'saved_names_verified':18,'retired_duplicate_404':True,'keeper_primary_and_all_prior_reviews_unchanged':True,'moved_listing_and_qualified_shared_context_present':True,'unavailable_image_not_resurrected':True,'dune_primary_candidate_current':candidate_current,'published_cut_utc':manifest['recorded_utc'],'published_wall_files':sum(r['scope']=='Wall Sculptures' for r in overlay),'published_retained_workshop_files':sum(r['scope']=='Retained Workshop' for r in overlay),'later_live_native_snapshot':live,'later_native_differences_are_not_additional_deletion_claims':True,'root_native_app_review_writes_or_restarts':0,'saved_final_workbook_renders':6}
write(H/'live-after-publication.json',result)
new=deepcopy(old);new['status']='CURRENT186_EXPORTS_AND_AUTOMATIC_APP_SOURCE_RELOAD_VERIFIED'
new['current_review_application'].update(status='PUBLISHED186_SOURCE_AUTOMATICALLY_LOADED_AND_VERIFIED',last_verified_utc=result['checked_utc'],source_register_sha256=source['register_sha256'],source_gallery_sha256=source['gallery_sha256'],verification=str((H/'live-after-publication.json').relative_to(BASE)),verification_sha256=sha(H/'live-after-publication.json'),source_rebase_required=False,qualified_status='The published186 catalogue and18 saved titles loaded automatically. Saved reviews and Primary choices are preserved. The app also has a newer native census; later removals are not retroactively assigned to this export cut.')
new['latest_app_native_overlay_observation']={'checked_utc':result['checked_utc'],'native_snapshot':live,'published_cut_wall_images':result['published_wall_files'],'scope':'Later live inventory observation. Do not mix these counts with the immutable export cut or infer deletion causes without receipts.'}
new['queued_post_publication_imports']['items'].append('Reconcile later native census generation'+str(live.get('generation'))+' at a separately frozen cut; differences from the published5289 Wall files are observations, not unverified deletion approvals.')
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer];before_bytes={p:p.read_bytes() for p in targets};payloads={}
for p in targets:
    a=read(p)
    if p!=pointer:assert a['current_master_catalogue']==old;a['current_master_catalogue']=new
    else:a=new
    payloads[p]=(json.dumps(a,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    q=p.with_name(p.name+'.root186-attestation-pending');q.write_bytes(data);os.replace(q,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before_bytes[p];put(p,payloads[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before_bytes[p])
    raise
receipt.update(status='CURRENT186_EXPORTS_AND_LIVE_SOURCE_VERIFIED',initial_published_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),live_verification=str(H/'live-after-publication.json'),live_verification_sha256=sha(H/'live-after-publication.json'))
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({'status':receipt['status'],'active_options':186,'saved_titles_verified':18,'source_register_sha256':source['register_sha256'],'pointer_sha256':sha(pointer),'later_native_generation':live.get('generation'),'dune_candidate_current':candidate_current}))
