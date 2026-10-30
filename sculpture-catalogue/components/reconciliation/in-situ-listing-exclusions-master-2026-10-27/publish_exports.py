"""Publish the verified policy layer without writing app reviews or native files."""
from common import *
from copy import deepcopy
from datetime import datetime, timezone
import os

pointer=BASE/'current-master.json';old=read(pointer)
assert sha(pointer)==manifest['baseline_pointer_sha256'],'Concurrent catalogue publication'
qa=read(H/'independent-verification.json');assert qa['status']=='PASS_INDEPENDENT_PUBLICATION_READBACK'
plans=read(H/'workbook-edit-plan.json')['plans'];core,unified=[Path(p['output']) for p in plans]
for p,r in zip(plans,qa['workbooks']):assert sha(p['output'])==r['sha256']
assert old['register_sha256']==manifest['sources']['register']['sha256']
now=datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
register=H/'canonical-master-register.json';db=H/'gallery-projection/complete-image-platform-register.sqlite';seal=H/'gallery-projection/sealed-handoff.json'
paths=read(H/'current-reader-paths.json')
new=deepcopy(old)
new.update(recorded_utc=now,status='CURRENT186_IN_SITU_LISTING_EXCLUSIONS_PUBLISHED_APP_READBACK_PENDING',workbook=rel(core),workbook_sha256=sha(core),register=rel(register),register_sha256=sha(register),publication_receipt=rel(H/'publication-receipt.json'),summary=deepcopy(g['summary']),workbook_is_historical_snapshot=False)
new['preferred_review_workbook']=rel(unified);new['preferred_review_workbook_sha256']=sha(unified)
new['latest_corrections']+=' Completed owner In situ image policy:91 Listing uses removed from68 images across30 active options. Four affected Primaries cleared; no replacements guessed. Originals, shared types, other purposes, context/series roles, component associations and all specifications retained.'
new['current_path_scope']='Native image paths retain the separately dated '+manifest['native_inventory_cut_utc']+' census cut:5,041 Wall Sculptures and196 retained Workshop files. Image-use exclusions reflect the completed '+manifest['policy_cut_utc']+' app review cut. No new native census or deletion is inferred by this publication.'
new['current_individual_sculpture_list'].update(recorded_utc=now,status='CURRENT186_ACTIVE_189_RETAINED_THREE_RETIRED',register=rel(register),register_sha256=sha(register),workbook=rel(core),workbook_sha256=sha(core),publication_receipt=rel(H/'publication-receipt.json'),summary=deepcopy(g['summary']),current_option_list=paths['current_option_list'],current_option_list_sha256=sha(BASE/paths['current_option_list']),count_summary=paths['count_summary'],count_summary_sha256=sha(BASE/paths['count_summary']),review=paths['specification_review'])
new['current_comprehensive_workbook'].update(status='CURRENT186_IN_SITU_LISTING_EXCLUSIONS',path=rel(unified),sha256=sha(unified),verification=rel(H/'independent-verification.json'),verification_sha256=sha(H/'independent-verification.json'),validation_checks_passed=qa['checks'],publication_cut_utc=manifest['recorded_utc'],native_inventory_cut_utc=manifest['native_inventory_cut_utc'],image_use_policy_cut_utc=manifest['policy_cut_utc'],later_native_review=rel(H/'gallery-projection/family-images.html'))
new['current_published_gallery_projection']={'status':'CURRENT186_PRESERVED_SOURCE_WITH_EXACT_LISTING_EXCLUSIONS','path':rel(seal),'sha256':sha(seal),'register_sha256':sha(register),'database_sha256':sha(db),'counts':read(seal)['counts'],'readers':{p.name:rel(p) for p in (H/'gallery-projection').glob('*.html')},'source_database':manifest['sources']['source_gallery'],'source_platform_associations_preserved':True,'current_listing_exclusions':91}
new['current_image_review_links']={'index':rel(H/'gallery-projection/index.html'),'individual_options':rel(H/'gallery-projection/product-images.html'),'current_images_and_folders':rel(H/'gallery-projection/family-images.html'),'listing_use_exclusions':rel(H/'gallery-projection/listing-use-exclusions.html'),'photograph_requests':paths['photograph_review'],'working_specifications':paths['specification_review'],'current_live_catalogue':'http://127.0.0.1:8767/#specifications'}
new['current_missing_picture_lists'].update(status='SIX_PRIMARY_CHOICES_ZERO_UNHELD_SERIES_REPLACEMENTS_AND_STANDING_HOLDS',coverage=paths['coverage'],active_individual_source_requests=6,individual_gaps=6,technical_individual_gaps=17,active_in_situ_source_requests=0,active_series_source_requests=0,owner_held_in_situ_cases=28,owner_held_series_cases=1,technical_individual_references=paths['technical_individual_references'],held_in_situ_cases_csv=paths['held_in_situ_cases_csv'],active_individual_requests_csv=paths['active_individual_requests_csv'],active_series_requests_csv=paths['active_series_requests_csv'],listing_use_exclusions_csv=paths['listing_use_exclusions_csv'],historical_previous_current={'pointer_snapshot':manifest['sources']['pointer']['snapshot'],'sha256':manifest['sources']['pointer']['sha256']})
new['current_individual_photo_capture_policy'].update(individual_gaps=6,current_primary_choice_review=paths['active_individual_requests_csv'])
new['current_working_specification_checklist']={'path':paths['field_checklist'],'sha256':sha(BASE/paths['field_checklist']),'active_options':186,'working_field_groups':1116,'physical_verification_complete':False,'review':paths['specification_review']}
new['latest_in_situ_listing_policy_import']=deepcopy(g['latest_in_situ_listing_policy_import'])
new['latest_export_refresh']={'status':'VERIFIED186_POLICY_EXCLUSION_EXPORTS','recorded_utc':now,'image_use_policy_cut_utc':manifest['policy_cut_utc'],'native_inventory_cut_utc':manifest['native_inventory_cut_utc'],'source_register_before_refresh':manifest['sources']['register'],'independent_verification':rel(H/'independent-verification.json'),'checks':qa['checks'],'listing_use_exclusions':91,'newly_cleared_primaries':4,'newly_verified_native_deletions':0,'physical_commercial_and_platform_changes':0}
new['current_review_application'].update(new_published_register_sha256=sha(register),new_published_gallery_sha256=sha(db),source_rebase_required=True,qualified_status='Automatic source loading awaits independent readback. Root did not write app reviews or restart the app.')
new['queued_post_publication_imports']={'owning_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','completed_in_this_publication':['91 In situ Listing-use removals and four cleared Primary choices, exact version-checked completion receipt imported'],'items':['Keep any later native or saved-review activity separately dated; do not infer new replacements.']}
new['next_catalogue_actions']=['Choose permitted replacement Primaries for Chiswick Moon, Cup Ring CRS2 White, Deco Dune Ripple Wave Verdigris and Icarus; no guesses applied.','Two earlier Dune Ripple Primary choices remain open; do not repeat the pending Dune Ripple1 question.','Keep28 context cases and one prior series case on hold.','Retain estimates while gathering actual dimensions, weight, material and fitted-fixing evidence.']
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer]
backup=H/'publication-backups';backup.mkdir(exist_ok=True)
before={p:p.read_bytes() for p in targets};payload={}
for i,p in enumerate(targets):
    (backup/(str(i)+'-'+p.name)).write_bytes(before[p]);d=read(p)
    if p!=pointer:assert d['current_master_catalogue']==old;d['current_master_catalogue']=new
    else:d=new
    payload[p]=(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    t=p.with_name(p.name+'.policy-export-pending');t.write_bytes(data);os.replace(t,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p],'Concurrent control modification'
        put(p,payload[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt={'status':'CURRENT186_POLICY_EXPORTS_PUBLISHED_APP_READBACK_PENDING','published_utc':now,'pointer':str(pointer),'pointer_sha256':sha(pointer),'register_sha256':sha(register),'gallery_sha256':sha(db),'active_options':186,'retained_options':189,'retired_options':3,'source_assertions_preserved':1668,'physical_commercial_and_platform_changes':0,'listing_use_exclusions':91,'excluded_unique_images':68,'affected_active_options':30,'cleared_primary_choices':4,'open_primary_choices':6,'checks':qa['checks'],'native_inventory_cut_utc':manifest['native_inventory_cut_utc'],'image_use_policy_cut_utc':manifest['policy_cut_utc'],'workbooks':qa['workbooks'],'all_three_nested_controls_equal_pointer':True,'native_app_or_platform_writes':0}
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k!='workbooks'},indent=2))
