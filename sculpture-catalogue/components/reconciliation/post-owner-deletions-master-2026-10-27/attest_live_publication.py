"""Attach verified app-loading evidence without changing catalogue data."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import os

live=read(H/'live-after-publication.json');assert live['status']=='PASS_AUTOMATIC_LIVE_SOURCE_RELOAD_WITH_NEWER_NATIVE_OVERLAY'
pointer=BASE/'current-master.json';old=read(pointer);receipt=read(H/'publication-receipt.json');assert sha(pointer)==receipt['pointer_sha256']
assert old['register_sha256']==live['register_sha256'] and old['current_published_gallery_projection']['database_sha256']==live['gallery_sha256']
new=deepcopy(old);new['status']='CURRENT_MASTER187_AND_AUTOMATIC_APP_SOURCE_RELOAD_VERIFIED'
app=new['current_review_application'];app.update(status='V2_13_PUBLISHED_SOURCE_LOADED_AND_VERIFIED',last_verified_utc=live['checked_utc'],source_register_sha256=live['register_sha256'],source_gallery_sha256=live['gallery_sha256'],verification=rel if False else str((H/'live-after-publication.json').relative_to(BASE)),verification_sha256=sha(H/'live-after-publication.json'),source_rebase_required=False,qualified_status='Published frozen catalogue loaded automatically; the app also applies a newer native overlay. Newer native changes are queued for a separate canonical import; no extra deletion or retirement is inferred.')
new['latest_app_native_overlay_observation']={'checked_utc':live['checked_utc'],'native_snapshot':live['live_native_snapshot'],'wall_images':live['live_wall_images'],'published_cut_wall_images':5474,'scope':'Observed later app inventory, not reconciled into this 14:57 publication cut. Differences are not additional verified-deletion claims.'}
new['queued_post_publication_imports']={'owning_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','items':['Acanthus Two Leaves White title approval and exact saved app field','Two Deco Palm family folder renames and 27 filenames, preserving stable IDs and bytes; receipt awaited','BSI-E7CDC2CFAC9D: photo transfer and missing old folder do not constitute approved identity consolidation or retirement'],'canonical_identity_consolidation_approval_recorded':False}
new['next_catalogue_actions'][0]='Import forthcoming Acanthus/Deco Palm receipts separately; automatic source reload for this publication is verified.'
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer];before={};payloads={}
for p in targets:
    before[p]=p.read_bytes()
    if p==pointer:payloads[p]=new
    else:
        value=read(p);assert value['current_master_catalogue']==old;value['current_master_catalogue']=new;payloads[p]=value
def put(p,b):
    temp=p.with_name(p.name+'.root-attestation-pending');temp.write_bytes(b);os.replace(temp,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p];put(p,(json.dumps(payloads[p],ensure_ascii=False,indent=2)+'\n').encode());done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt.update(status='PUBLISHED_SOURCE_AND_AUTOMATIC_APP_RELOAD_VERIFIED',initial_published_pointer_sha256=receipt['pointer_sha256'],pointer_sha256=sha(pointer),live_source_verification=str(H/'live-after-publication.json'),live_source_verification_sha256=sha(H/'live-after-publication.json'),data_source_hashes_unchanged_by_app_attestation=True);write(H/'publication-receipt.json',receipt)
ready=read(H/'SOURCE_READY_FOR_APP_REBASE.json');ready.update(status='PUBLISHED_AND_AUTOMATIC_APP_SOURCE_RELOAD_VERIFIED',pointer_sha256=sha(pointer),live_verification=str(H/'live-after-publication.json'));write(H/'SOURCE_READY_FOR_APP_REBASE.json',ready)
write(H/'CURRENT_STATUS.json',{'status':'PUBLISHED_188_DELETION_REFRESH_AND_LIVE_APP_VERIFIED','recorded_utc':datetime.now(timezone.utc).isoformat(),'publication_cut_utc':manifest['recorded_utc'],'active_options':187,'retained_options':189,'current_scoped_files_in_publication_cut':5670,'primary_references':185,'context_references':160,'context_holds':27,'open_primary_selections':1,'deferred_frozen_fish_binding':1,'open_series_replacements':3,'series_hold':1,'source_assertions_preserved':1668,'publication_checks':read(H/'independent-verification.json')['checks'],'independent_v2_13_tests':389,'app_source_loaded':True,'later_native_observation_wall_images':live['live_wall_images'],'upcoming_owner_session_changes_queued_separately':True,'app_native_or_platform_mutations_by_publisher':0})
print('PASS current pointer, three controls and automatic app loading; newer native changes remain separately queued')
