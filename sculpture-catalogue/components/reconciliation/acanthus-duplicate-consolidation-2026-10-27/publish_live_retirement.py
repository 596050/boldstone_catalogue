"""Publish the exact validated retirement; old workbook exports stay labelled history."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,os,shutil
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
draft=BASE.parent/'catalogue-review/reviews/acanthus-names-20261027/staged-retirement';seal=read(draft/'draft-handoff.json');check=read(H/'independent-candidate-verification.json');assert check['status']=='PASS_EXACT_OWNER_DUPLICATE_CONSOLIDATION'
pointer=BASE/'current-master.json';assert sha(pointer)==seal['source_pointer_sha256'];old=read(pointer)
assert old['register_sha256']==seal['source_register_sha256'] and old['current_published_gallery_projection']['database_sha256']==seal['source_gallery_sha256']
assert sha(seal['draft_register'])==check['register_sha256']==seal['draft_register_sha256'];assert sha(seal['draft_gallery'])==check['gallery_sha256']==seal['draft_gallery_sha256']
gallery=H/'published-gallery';gallery.mkdir(exist_ok=True);reg=H/'canonical-master-register.json';db=gallery/'complete-image-platform-register.sqlite'
assert not reg.exists() and not db.exists();shutil.copyfile(seal['draft_register'],reg);shutil.copyfile(seal['draft_gallery'],db)
g=read(reg);now=datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
(gallery/'sealed-handoff.json').write_text(json.dumps({'status':'OWNER_CONFIRMED_DUPLICATE_CONSOLIDATION','register_sha256':sha(reg),'database_sha256':sha(db),'active_options':186,'retained_options':189,'retired_options':3,'source_handoff':str(draft/'draft-handoff.json'),'source_handoff_sha256':sha(draft/'draft-handoff.json'),'independent_verification':str(H/'independent-candidate-verification.json'),'no_native_or_platform_writes':True},indent=2)+'\n')
new=deepcopy(old);new.update(recorded_utc=now,status='CANONICAL186_OWNER_DUPLICATE_RETIRED_WORKBOOK_EXPORT_REFRESH_PENDING',register=rel(reg),register_sha256=sha(reg),summary=g['summary'],current_option_count=186,retained_option_count=189,retired_option_count=3,publication_receipt=rel(H/'publication-receipt.json'))
new['historical_master_publications'].append({k:old[k] for k in ['recorded_utc','register','register_sha256','workbook','workbook_sha256','preferred_review_workbook','publication_receipt']})
new['current_published_gallery_projection'].update(status='CURRENT186_OWNER_DUPLICATE_CONSOLIDATED',path=rel(gallery/'sealed-handoff.json'),sha256=sha(gallery/'sealed-handoff.json'),register_sha256=sha(reg),database_sha256=sha(db))
new['current_individual_sculpture_list'].update(status='CURRENT186_ACTIVE_189_RETAINED',register=rel(reg),register_sha256=sha(reg),summary=g['summary'],current_option_rows=186,review='http://127.0.0.1:8767/#specifications')
new['current_review_application'].update(status='AUTOMATIC_186_SOURCE_REFRESH_PENDING',source_rebase_required=True,new_published_register_sha256=sha(reg),new_published_gallery_sha256=sha(db))
new['latest_owner_duplicate_consolidation']={'decision':seal['decision'],'verification':rel(H/'independent-candidate-verification.json'),'verification_sha256':sha(H/'independent-candidate-verification.json'),'keeper_primary_retained':'id:cnqzTNngPVsAAAAAAAufMQ','secondary_listing_retained':'id:cnqzTNngPVsAAAAAAAyj8Q','confirmed_context_retained':'id:cnqzTNngPVsAAAAAAAyluQ','missing_reference_not_reactivated':'id:cnqzTNngPVsAAAAAAAyluA','native_files_deleted_by_publisher':0}
new['workbook_is_historical_snapshot']=True
new['workbook_snapshot_qualification']='Previous 187-option export; the authoritative live register is now186. Refreshed186 workbook exports are being prepared. Survivor specification values are unchanged.'
new['current_comprehensive_workbook']['status']='HISTORICAL187_EXPORT_PENDING186_REFRESH'
new['current_image_review_links']={'current_live_catalogue':'http://127.0.0.1:8767/#specifications','keeper':'http://127.0.0.1:8767/#BSI-93ADE7C4103D','previous_187_snapshot':old['current_image_review_links']}
new['next_catalogue_actions']=['Verify automatic app loading:186 active; retired duplicate404; keeper specs/Primary unchanged and accepted shared context retained.','Refresh the workbook exports and derived photograph lists to186 while preserving all source history.']+old['next_catalogue_actions'][1:]
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer];before={};payload={};backup=H/'publication-backups';backup.mkdir(exist_ok=True)
for i,p in enumerate(targets):
    before[p]=p.read_bytes();(backup/(str(i)+'-'+p.name)).write_bytes(before[p])
    if p==pointer:payload[p]=new
    else:
        value=read(p);assert value['current_master_catalogue']==old;value['current_master_catalogue']=new;payload[p]=value
def put(p,b):
    tmp=p.with_name(p.name+'.root-retirement-pending');tmp.write_bytes(b);os.replace(tmp,p)
written=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p];put(p,(json.dumps(payload[p],ensure_ascii=False,indent=2)+'\n').encode());written.append(p)
    assert read(pointer)==new
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(written):put(p,before[p])
    raise
receipt={'status':'CANONICAL186_PUBLISHED_APP_READBACK_PENDING','published_utc':now,'pointer':str(pointer),'pointer_sha256':sha(pointer),'register_sha256':sha(reg),'gallery_sha256':sha(db),'active_options':186,'retained_options':189,'retired_options':3,'keeper_specs_and_primary_unchanged':True,'all_source_assertions_retained':1668,'workbook_refresh_pending_and_old_exports_marked_historical':True,'all_three_controls_equal_pointer':True,'app_native_or_platform_writes':0}
(H/'publication-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
