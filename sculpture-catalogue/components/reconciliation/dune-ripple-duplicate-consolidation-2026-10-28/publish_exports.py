"""Publish the verified exact Dune Ripple merge with guarded shared controls."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import os
pointer=BASE/'current-master.json';old=read(pointer)
assert sha(pointer)==manifest['baseline_pointer_sha256'],'Concurrent publication'
qa=read(H/'independent-verification.json');assert qa['status']=='PASS_INDEPENDENT_PUBLICATION_READBACK'
plans=read(H/'workbook-edit-plan.json')['plans'];core,unified=[Path(p['output']) for p in plans]
for p,r in zip(plans,qa['workbooks']):assert sha(p['output'])==r['sha256']
now=datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
register=H/'canonical-master-register.json';db=H/'gallery-projection/complete-image-platform-register.sqlite';seal=H/'gallery-projection/sealed-handoff.json';paths=read(H/'current-reader-paths.json')
new=deepcopy(old)
new.update(recorded_utc=now,status='CURRENT185_DUNE_RIPPLE_MERGE_PUBLISHED_APP_READBACK_PENDING',workbook=rel(core),workbook_sha256=sha(core),register=rel(register),register_sha256=sha(register),publication_receipt=rel(H/'publication-receipt.json'),summary=deepcopy(g['summary']),workbook_is_historical_snapshot=False)
new['preferred_review_workbook']=rel(unified);new['preferred_review_workbook_sha256']=sha(unified)
new['latest_corrections']+=' 28October owner-directed merge: keep BSI-9299D69FEF08 Dune Ripple2 Verdigris and Copper; retire BSI-4536FDCA0DA9 Verdigris as its alias.185 active189 retained4 retired. Keeper specifications and existing two Listing choices/Primary preserved. Two accepted-reference qualifications and qualified source/platform evidence retained. No unrelated pending imports.'
new['current_path_scope']='Native paths retain the separate '+manifest['native_inventory_cut_utc']+' inventory cutoff. This publication applies only the28October Dune Ripple2 duplicate merge and exact keeper review choices. Earlier image-use exclusions retain their policy cutoff '+manifest['retained_policy_cut_utc']+'. No new native census or file move is inferred.'
new['current_individual_sculpture_list'].update(recorded_utc=now,status='CURRENT185_ACTIVE_189_RETAINED_FOUR_RETIRED',register=rel(register),register_sha256=sha(register),workbook=rel(core),workbook_sha256=sha(core),publication_receipt=rel(H/'publication-receipt.json'),summary=deepcopy(g['summary']),current_option_rows=185,retained_option_rows=189,retired_option_rows=4,current_option_list=paths['current_option_list'],current_option_list_sha256=sha(BASE/paths['current_option_list']),count_summary=paths['count_summary'],count_summary_sha256=sha(BASE/paths['count_summary']),review=paths['specification_review'])
new['current_comprehensive_workbook'].update(status='CURRENT185_EXACT_OWNER_DUNE_RIPPLE_ALIAS_MERGE',path=rel(unified),sha256=sha(unified),active_options=185,retained_option_records=189,verification=rel(H/'independent-verification.json'),verification_sha256=sha(H/'independent-verification.json'),validation_checks_passed=qa['checks'],publication_cut_utc=manifest['recorded_utc'],native_inventory_cut_utc=manifest['native_inventory_cut_utc'],later_native_review=rel(H/'gallery-projection/family-images.html'))
new['current_published_gallery_projection']={'status':'CURRENT185_EXACT_OWNER_DUPLICATE_SOURCE_UNION','path':rel(seal),'sha256':sha(seal),'register_sha256':sha(register),'database_sha256':sha(db),'counts':read(seal)['counts'],'readers':{p.name:rel(p) for p in (H/'gallery-projection').glob('*.html')},'source_database':manifest['sources']['source_gallery'],'source_platform_associations_preserved':True,'association_union':rel(H/'association-union.json')}
new['current_image_review_links']={'index':rel(H/'gallery-projection/index.html'),'individual_options':rel(H/'gallery-projection/product-images.html'),'current_images_and_folders':rel(H/'gallery-projection/family-images.html'),'listing_use_exclusions':rel(H/'gallery-projection/listing-use-exclusions.html'),'photograph_requests':paths['photograph_review'],'working_specifications':paths['specification_review'],'current_live_catalogue':'http://127.0.0.1:8767/#specifications'}
new['current_missing_picture_lists'].update(status='FIVE_PRIMARY_CHOICES_IN_SCOPED185_SOURCE_AND_STANDING_HOLDS',coverage=paths['coverage'],active_individual_source_requests=5,individual_gaps=5,technical_individual_gaps=16,active_in_situ_source_requests=0,active_series_source_requests=0,owner_held_in_situ_cases=28,owner_held_series_cases=1,technical_individual_references=paths['technical_individual_references'],held_in_situ_cases_csv=paths['held_in_situ_cases_csv'],active_individual_requests_csv=paths['active_individual_requests_csv'],active_series_requests_csv=paths['active_series_requests_csv'],listing_use_exclusions_csv=paths['listing_use_exclusions_csv'],historical_previous_current={'pointer_snapshot':manifest['sources']['pointer']['snapshot'],'sha256':manifest['sources']['pointer']['sha256']})
new['current_individual_photo_capture_policy'].update(individual_gaps=5,current_primary_choice_review=paths['active_individual_requests_csv'])
new['current_working_specification_checklist']={'path':paths['field_checklist'],'sha256':sha(BASE/paths['field_checklist']),'active_options':185,'working_field_groups':1110,'physical_verification_complete':False,'review':paths['specification_review']}
new['latest_catalogue_retirement']=deepcopy(g['latest_catalogue_retirement']);new['latest_dune_ripple_duplicate_consolidation']=deepcopy(g['latest_dune_ripple_duplicate_consolidation'])
new['latest_export_refresh']={'status':'VERIFIED185_EXACT_OWNER_MERGE_EXPORTS','recorded_utc':now,'merge_cut_utc':manifest['recorded_utc'],'source_register_before_refresh':manifest['sources']['register'],'independent_verification':rel(H/'independent-verification.json'),'checks':qa['checks'],'retired_duplicate':'BSI-4536FDCA0DA9','keeper':'BSI-9299D69FEF08','native_or_platform_changes':0,'physical_or_commercial_field_changes':0,'unrelated_pending_imports_applied':False}
new['current_review_application'].update(new_published_register_sha256=sha(register),new_published_gallery_sha256=sha(db),source_rebase_required=True,qualified_status='Automatic source loading pending readback. App reviews and native jobs remain owned by sibling; root made no app review writes or restart.')
new['queued_post_publication_imports']['latest_scoped_merge_completed']={'receipt':rel(H/'publication-receipt.json'),'scope':'Only Dune Ripple2 duplicate merge. Existing unrelated queued choices and metadata corrections remain pending.'}
new['next_catalogue_actions']=['Keep unrelated Chiswick Primary and Acanthus metadata imports queued separately.','Cup Ring exact owner image decision remains pending with root.','Dune Ripple1 Verdigris/Rust exact Primary question remains pending; do not repeat it.','Dune Ripple2 keeper Primary is now preserved and its duplicate is retired.','Retain28 context cases and one prior series case on hold; gather physical evidence without removing estimate labels.']
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer]
before={p:p.read_bytes() for p in targets};payload={};backup=H/'publication-backups';backup.mkdir(exist_ok=True)
for i,p in enumerate(targets):
    (backup/(str(i)+'-'+p.name)).write_bytes(before[p]);d=read(p)
    if p!=pointer:assert d['current_master_catalogue']==old;d['current_master_catalogue']=new
    else:d=new
    payload[p]=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    t=p.with_name(p.name+'.dune-alias-pending');t.write_bytes(data);os.replace(t,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p],'Concurrent control write';put(p,payload[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt={'status':'CURRENT185_OWNER_MERGE_EXPORTS_PUBLISHED_APP_READBACK_PENDING','published_utc':now,'pointer':str(pointer),'pointer_sha256':sha(pointer),'register_sha256':sha(register),'gallery_sha256':sha(db),'keep':'BSI-9299D69FEF08','retire':'BSI-4536FDCA0DA9','active_options':185,'retained_options':189,'retired_options':4,'working_fields':1110,'source_assertions_preserved':1668,'keeper_specifications_unchanged':True,'keeper_saved_listing_choices':2,'primary_file_id':'id:cnqzTNngPVsAAAAAAAyegw','qualified_reference_edges_added':2,'qualified_platform_source_links_added':qa['qualified_platform_source_links_added'],'checks':qa['checks'],'native_inventory_cut_utc':manifest['native_inventory_cut_utc'],'merge_cut_utc':manifest['recorded_utc'],'workbooks':qa['workbooks'],'all_three_nested_controls_equal_pointer':True,'native_app_or_platform_writes':0,'unrelated_pending_imports_applied':False}
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k!='workbooks'},indent=2))
