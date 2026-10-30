"""Publish verified186 exports and reference projection with guarded rollback."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import os,sqlite3

pointer=BASE/'current-master.json';old=read(pointer)
assert sha(pointer)==manifest['publication_parent_pointer_sha256'],'Another publication changed the pointer'
qa=read(H/'independent-verification.json');assert qa['status']=='PASS_INDEPENDENT_PUBLICATION_READBACK'
plans=read(H/'workbook-edit-plan.json')['plans'];core,unified=[Path(p['output']) for p in plans]
for p,r in zip(plans,qa['workbooks']):assert sha(p['output'])==r['sha256']
assert old['register_sha256']==manifest['sources']['register']['sha256']
assert len(active)==186 and len(g['options'])==189 and len(g['retired_option_ids'])==3
now=datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
register=H/'canonical-master-register.json';db=H/'gallery-projection/complete-image-platform-register.sqlite';seal=H/'gallery-projection/sealed-handoff.json'
paths=read(H/'current-reader-paths.json');report=read(H/'register-preparation.json');counts=read(OUT/'current-count-summary.json')
new=deepcopy(old)
new.update(recorded_utc=now,status='CURRENT186_EXPORTS_AND_NATIVE_NAVIGATION_PUBLISHED_APP_READBACK_PENDING',workbook=rel(core),workbook_sha256=sha(core),register=rel(register),register_sha256=sha(register),publication_receipt=rel(H/'publication-receipt.json'),summary=deepcopy(g['summary']),workbook_is_historical_snapshot=False)
new.pop('workbook_snapshot_qualification',None)
new['latest_corrections']+=' Owner-confirmed Deco Two Leaves White duplicate consolidated into Acanthus Two Leaves White. 18 saved White title edits imported with prior names retained. Two saved Primary changes and the captured native navigation refresh imported. No physical or commercial values changed.'
wall=sum(r['scope']=='Wall Sculptures' for r in overlay)
new['current_path_scope']=f"Scoped census/review cut {manifest['recorded_utc']}: {wall:,} Wall Sculptures files plus {len(overlay)-wall:,} retained Workshop files. 185 further verified deletions, one scoped native NOT_FOUND image and one added file reconcile to the preceding publication. Later native activity remains separately dated."
new['link_scope']='Current references use stable file IDs and actual parent-folder IDs from the captured census. Historical source sheets and unavailable references retain their dates, source claims and IDs.'
new['current_individual_sculpture_list'].update(recorded_utc=now,status='CURRENT186_ACTIVE_189_RETAINED_THREE_RETIRED',register=rel(register),register_sha256=sha(register),workbook=rel(core),workbook_sha256=sha(core),publication_receipt=rel(H/'publication-receipt.json'),summary=deepcopy(g['summary']),current_option_rows=186,retained_option_rows=189,retired_option_rows=3,current_option_list=paths['current_option_list'],current_option_list_sha256=sha(BASE/paths['current_option_list']),count_summary=paths['count_summary'],count_summary_sha256=sha(BASE/paths['count_summary']),review=paths['specification_review'],component_count_scope='111 currently active identified component IDs. 112 component rows retained as history. Whole-library unique design and physical mould counts are unverified.')
new['current_comprehensive_workbook'].update(status='CURRENT186_COMPLETE_SAVED_SOURCE_EXPORT',path=rel(unified),sha256=sha(unified),active_options=186,retained_option_records=189,verification=rel(H/'independent-verification.json'),verification_sha256=sha(H/'independent-verification.json'),current_scoped_files=len(files),current_wall_images=wall,retained_workshop_images=len(files)-wall,publication_cut_utc=manifest['recorded_utc'],validation_checks_passed=qa['checks'],later_verified_native_navigation=rel(H/'register-preparation.json'),later_native_review=rel(H/'gallery-projection/family-images.html'))
new['current_published_gallery_projection']={'status':'CURRENT186_SOURCE_HISTORY_AND_CAPTURED_NATIVE_NAVIGATION','path':rel(seal),'sha256':sha(seal),'register_sha256':sha(register),'database_sha256':sha(db),'counts':read(seal)['counts'],'readers':{p.name:rel(p) for p in (H/'gallery-projection').glob('*.html')},'source_database':manifest['sources']['source_gallery'],'source_platform_associations_preserved':True}
new['current_image_review_links']={'index':rel(H/'gallery-projection/index.html'),'individual_options':rel(H/'gallery-projection/product-images.html'),'current_images_and_folders':rel(H/'gallery-projection/family-images.html'),'photograph_requests':paths['photograph_review'],'working_specifications':paths['specification_review'],'current_live_catalogue':'http://127.0.0.1:8767/#specifications'}
previous_missing=deepcopy(old['current_missing_picture_lists']);missing=deepcopy(previous_missing)
missing.update(status='ONE_PRIMARY_SIX_SERIES_REPLACEMENTS_AND_STANDING_HOLDS',coverage=paths['coverage'],active_individual_source_requests=1,active_in_situ_source_requests=0,active_series_source_requests=6,owner_held_in_situ_cases=27,owner_held_series_cases=1,technical_individual_references=paths['technical_individual_references'],held_in_situ_cases_csv=paths['held_in_situ_cases_csv'],active_individual_requests_csv=paths['active_individual_requests_csv'],active_series_requests_csv=paths['active_series_requests_csv'],historical_previous_current=previous_missing)
new['current_missing_picture_lists']=missing
new['current_working_specification_checklist']={'path':paths['field_checklist'],'sha256':sha(BASE/paths['field_checklist']),'active_options':186,'working_field_groups':1116,'physical_verification_complete':False,'review':paths['specification_review']}
new['latest_verified_native_filename_import']=deepcopy(g['latest_verified_native_filename_import'])
new['latest_white_title_review_import']=deepcopy(g['latest_white_title_review_import'])
new['latest_export_refresh']={'status':'VERIFIED186_EXPORTS','recorded_utc':now,'capture_cut':manifest['recorded_utc'],'source_register_before_refresh':manifest['sources']['register'],'independent_verification':rel(H/'independent-verification.json'),'checks':qa['checks'],'newly_verified_deletions_since_previous_export':185,'scoped_absence_without_deletion_cause':['id:cnqzTNngPVsAAAAAAAyluA'],'new_file_ids':manifest['new_files_after_filename_pass'],'physical_commercial_and_platform_changes':0,'saved_names_imported':18,'saved_primary_changes':report['primary_changes']}
app=new['current_review_application'];app.update(new_published_register_sha256=sha(register),new_published_gallery_sha256=sha(db),source_rebase_required=True,qualified_status='Automatic source loading is pending readback. Saved reviews remain owned by the review application; root did not write its database or restart it.')
new['queued_post_publication_imports']={'owning_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','completed_in_this_publication':['Acanthus duplicate retirement and exact title','Two folder and27 filename renames through verified stable IDs','18 saved White title edits'],'items':['Later84-file deletion batch completion: the final stable ID id:cnqzTNngPVsAAAAAAAuhQA was verified absent after this15:55 census cut. Keep this dated proof separate until the next inventory import.'],'later_batch_evidence':'../catalogue-review/reviews/white-title-and-job-audit-20261027/job-final.json','canonical_identity_consolidation_approval_recorded':True}
new['next_catalogue_actions']=['Select the surviving full-view Primary for Dune Ripple1 Verdigris and Rust; exact candidate already presented in the root thread.','Find qualified series replacements for the three Dune Ripple options, Palm Form One White, Palm Form Two White and Timeless Spiral White.','Keep27 context requirements and the Copper series case held.','Verify actual dimensions/depth, weight, material and fitted hardware without erasing accepted estimates.','Import later native cleanup receipts at a separately frozen census cut.']
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer]
backup=H/'publication-backups';backup.mkdir(exist_ok=True)
before={p:p.read_bytes() for p in targets};payloads={}
for i,p in enumerate(targets):
    (backup/(str(i)+'-'+p.name)).write_bytes(before[p])
    value=read(p)
    if p!=pointer:
        assert value['current_master_catalogue']==old,'Control differs from the publication parent'
        value['current_master_catalogue']=new
    else:value=new
    payloads[p]=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    temp=p.with_name(p.name+'.root186-export-pending');temp.write_bytes(data);os.replace(temp,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p],'Concurrent control modification'
        put(p,payloads[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt={'status':'CURRENT186_EXPORTS_PUBLISHED_APP_READBACK_PENDING','published_utc':now,'pointer':str(pointer),'pointer_sha256':sha(pointer),'register_sha256':sha(register),'gallery_sha256':sha(db),'active_options':186,'retained_options':189,'retired_options':3,'source_assertions_preserved':1668,'physical_commercial_and_platform_changes':0,'saved_name_edits':18,'primary_changes':2,'checks':qa['checks'],'current_snapshot_files':len(files),'snapshot_cut':manifest['recorded_utc'],'workbooks':qa['workbooks'],'all_three_controls_equal_pointer':True,'native_app_or_platform_writes':0}
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k!='workbooks'},indent=2))
