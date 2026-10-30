"""CAS-publish the verified combined update to the single current master."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.followup-tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
assert not(H/'publication-receipt.json').exists(),'Already published'
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');g=read(H/'canonical-master-register.json');reports=read(H/'link-report-verification.json');visual=read(H/'visual-verification.json');checklists=read(H/'capture-and-specification-verification.json');out=Path(reports['output_directory'])
ind=BASE/'components/parallel-reviews/selling-details-completion-2026-10-22/prepared-commercial-integration-verification.json'
if '--prepare-only'not in sys.argv:
 iv=read(ind);assert iv['status']=='PASS',iv
 assert iv['workbook_sha256']==v['workbook_sha256']and iv['register_sha256']==v['register_sha256']
assert v['status']==visual['status']=='PASS'and not v['issues']
assert sha(H/'master-workbook.pending')==v['workbook_sha256']==visual['workbook_sha256']
assert sha(H/'canonical-master-register.json')==v['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+visual['previews']+checklists['csv_files']+checklists['pages']:assert sha(x['path'])==x['sha256']
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
ptr=read(BASE/'current-master.json');prior=copy.deepcopy(ptr);scope=copy.deepcopy(g['latest_catalogue_followup']);commercial=copy.deepcopy(g['latest_commercial_completion'])
verification={'verification':rel(H/'saved-file-verification.json'),'verification_sha256':sha(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'visual_verification_sha256':sha(H/'visual-verification.json'),'independent_verification':rel(ind)}
if ind.is_file():verification['independent_verification_sha256']=sha(ind)
scope.update(verification);scope['cumulative_folder_updates_in_sheet']=49;scope['workbook_folder_sheet']='Moonphases and Dune';commercial.update(verification);commercial['workbook_sheet']='Selling Details';commercial['current_review']=rel(out/'selling-details.html');commercial['current_review_sha256']=sha(out/'selling-details.html')
ptr.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_catalogue_followup=scope,latest_commercial_completion=commercial,current_individual_photo_capture_policy=copy.deepcopy(g['current_individual_photo_capture_policy']))
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification);coverage['status']='CURRENT_THREE_OWNER_ACCEPTED_INDIVIDUAL_IMAGES_AND_FOLDER_REFRESH';ptr['latest_image_coverage_audit']=coverage
ptr.setdefault('historical_path_refreshes',[]).append(copy.deepcopy(prior['latest_path_refresh']));ptr['latest_path_refresh']={'recorded_utc':now(),'scope':'14 approved Moonspirals, Echo Sound and Decowaves folder changes projected with stable IDs;49 cumulative folder references in the current folder sheet','native_link_destinations_updated':v['native_targets_updated'],'new_native_links':398,'folder_reference_links_added':28,'selling_view_links_added':370,'new_canonical_options':0,'image_role_changes':3,'commercial_field_changes':370,'verification':verification['verification'],'root_remote_writes':0}
ptr['current_path_scope']+=';14 later Moonspirals/Echo Sound/Decowaves folder references verified against515objects with485files; three owner-accepted individual listing images use stable file and parent IDs'
ptr.setdefault('historical_image_review_links',[]).append(copy.deepcopy(prior['current_image_review_links']));links=copy.deepcopy(prior['current_image_review_links'])
for k in ['all_links','individual_image_gaps','missing_in_situ_images','missing_series_images','existing_images_to_check','resolved_image_roles']:
 links[k]=rel(out/Path(links[k]).name);assert(BASE/links[k]).is_file()
links.pop('separate_individual_photographs_21',None)
links.update(verification=rel(H/'link-report-verification.json'),verification_sha256=sha(H/'link-report-verification.json'),counts=copy.deepcopy(reports['counts']),specifications_to_verify=rel(out/'specifications-to-verify.html'),selling_details=rel(out/'selling-details.html'),combined_shoot_and_measure=rel(out/'Combined_Shoot_and_Measure_Checklist.csv'),separate_individual_photographs=rel(out/'Separate_Individual_Photographs_Required_18.csv'))
ptr['current_image_review_links']=links
missing=copy.deepcopy(prior['current_missing_picture_lists'])
for k,x in list(missing.items()):
 if isinstance(x,str)and x.startswith('outputs/'):
  missing[k]=rel(out/Path(x).name);assert(BASE/missing[k]).is_file()
missing.update(required_actions=98,find_capture=97,verify_existing=1,individual_gaps=19,in_situ_gaps=61,series_gaps=18,resolved_this_pass=3,current_resolved_actions=54,exact_crop_candidates=0,separate_individual_photos_required=18,historical_crop_candidates_declined_by_owner=13,new_image_roles_closed_this_refresh=3)
missing['historical_resolved_actions_scope']='53 belongs to the prior cumulative snapshot; current active-table resolved actions are54, cumulative including two archived actions56.'
ptr['current_missing_picture_lists']=missing
ptr['current_specification_verification']={'path':rel(H/'capture-and-specification-verification.json'),'sha256':sha(H/'capture-and-specification-verification.json'),'review':links['specifications_to_verify'],'field_checklist':rel(out/'Specification_Verification_Checklist_1116_Fields.csv'),'selling_details':links['selling_details'],'current_option_rows':186,'current_field_rows':1116,'new_physical_measurements_added':0,'source_price_check':rel(checklists['source_price_check']['path']),'commercial_values_changed_in_this_refresh':370,'working_estimated_prices':185,'specific_owner_commercial_exception':1}
count=copy.deepcopy(prior['current_individual_sculpture_list']);count.update(recorded_utc=now(),register=ptr['register'],register_sha256=ptr['register_sha256'],workbook_sha256=ptr['workbook_sha256'],publication_receipt=ptr['publication_receipt'],current_option_list=rel(out/'Current_Individual_Options_186.csv'),current_option_list_sha256=sha(out/'Current_Individual_Options_186.csv'),count_summary=rel(out/'current-count-summary.json'),count_summary_sha256=sha(out/'current-count-summary.json'));ptr['current_individual_sculpture_list']=count
ptr.setdefault('historical_guided_image_reviews',[]).append(copy.deepcopy(prior['current_guided_image_review']));guided={'status':'READY_FOR_REMAINING_SEPARATE_INDIVIDUAL_PHOTOGRAPH_COLLECTION','path':rel(H/'photo-review-queue.json'),'sha256':sha(H/'photo-review-queue.json'),'review_list':links['individual_image_gaps'],'current_individual_gaps':19,'separate_photographs_required':18,'deferred_legacy_identity':1,'exact_crops_declined':True,'owner_accepted_standalone_listing_images':3};ptr['current_guided_image_review']=guided
if 'queued_native_path_refreshes'in ptr:ptr.setdefault('completed_native_path_refresh_queue_snapshots',[]).append(ptr.pop('queued_native_path_refreshes'))
pending=BASE.parent/'reports/dropbox-decowaves-three-panel-rename-2026-10-22/approved-plan-and-baseline.json'
assert pending.is_file()
ptr['queued_native_path_refreshes']={'status':'OWNER_APPROVED_NATIVE_RENAME_NOT_YET_EXECUTED_AT_THIS_PUBLICATION','family':'Frozen Decowaves','path':str(pending),'sha256':sha(pending),'folder_id':'id:cnqzTNngPVsAAAAAAAyk5Q','current_folder_name':'Three Frozen Decowaves White','approved_new_name':'Frozen Decowaves 1 and Frozen Decowaves 2 White Three Panel Arrangements','scope':'Retain22files and the same folder ID; panel sequence1–2–1 with1rotated; no third component. Directory lane held until this publication readback.'}
ptr['next_catalogue_actions']=['Collect18 separate individual photographs using the linked examples. Keep the13 declined crop proposals open; no crops are authorized. One historical Frozen Fish identity remains deferred; all current Frozen Fish stay70x15cm.','Complete61 in situ and18 series image gaps, grouped in77 option-specific shoot/measure rows.','Record actual component dimensions, weighed mass, confirmed material and fitted rear hardware. Preserve labelled estimates and owner statements until physical verification.','Use current working individual price estimates, made-to-order policy and1–2-week lead times where unresolved. Preserve the specific MCP4Verdigris/Rust £175 and1-week policy; confirm actual order pricing, capacity and delivery separately.','Complete the already-approved single Frozen Decowaves three-panel arrangement folder rename after release of the native hold, then project its sealed overlay at the next safe refresh.']
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p0=Path(m[key]['path']);d=read(p0)
 d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],current_individual_catalogue_count=copy.deepcopy(count),latest_catalogue_followup=copy.deepcopy(scope),latest_commercial_completion=copy.deepcopy(commercial),current_individual_photo_capture_policy=copy.deepcopy(ptr['current_individual_photo_capture_policy']),latest_image_coverage_audit=copy.deepcopy(coverage),current_image_review_links=copy.deepcopy(links),current_missing_picture_lists=copy.deepcopy(missing),current_guided_image_review=copy.deepcopy(guided),current_specification_verification=copy.deepcopy(ptr['current_specification_verification']),next_image_review_actions=copy.deepcopy(ptr['next_catalogue_actions']))
 if key=='component_checkpoint':d['current_master_validation']={'path':verification['verification'],'sha256':verification['verification_sha256']}
 updates[p0]=d
for k in ['summary','latest_listing_resolution','latest_listing_reconciliation','latest_moon_and_shellwave_numbering','latest_lava_moon_numbering','latest_gleneagles_numbering','latest_raked_spiral_paths','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','current_listing_population','latest_moonphases_dune_ripple_refresh','latest_fingerprint_working_specification_confirmation']:assert ptr.get(k)==prior.get(k),k
write(H/'prepared-pointer.json',ptr)
if '--prepare-only'in sys.argv:
 print(json.dumps({'status':'PUBLICATION_PREPARED_NO_CURRENT_FILES_REPLACED','options':186,'individual_gaps':19,'commercial_changes':370}));raise SystemExit(0)
for k,x in m.items():assert sha(x['path'])==x['sha256'],k
target=BASE/ptr['workbook'];os.replace(H/'master-workbook.pending',target)
for p0,x in updates.items():write(p0,x)
write(BASE/'current-master.json',ptr)
assert sha(target)==ptr['workbook_sha256']and sha(BASE/ptr['register'])==ptr['register_sha256']and read(BASE/'current-master.json')==ptr
for p0,x in updates.items():assert read(p0)==x and x['current_master_catalogue']==ptr
for k,x in m.items():
 if k not in ['master_pointer','master_workbook','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256'],k
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':ptr['workbook_sha256'],'register':str(BASE/ptr['register']),'register_sha256':ptr['register_sha256'],'audit':str(H/'image-coverage-current.json'),'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p0):sha(p0)for p0 in updates},'checks':v['checks'],'independent_prepared_verification':str(ind),'independent_prepared_verification_sha256':sha(ind),'current_options':186,'working_component_identities':112,'working_field_groups':1116,'sheets':28,'formulas':3356,'native_hyperlinks':11893,'native_link_targets_updated':v['native_targets_updated'],'new_native_links':398,'folder_renames_this_refresh':14,'cumulative_folder_rows':49,'stable_native_objects_verified':515,'stable_native_file_IDs_and_sizes':485,'new_physical_verifications':0,'current_individual_gaps':19,'separate_individual_photos_required':18,'deferred_identity':1,'in_situ_gaps':61,'series_gaps':18,'required_picture_actions':98,'new_image_roles_closed':3,'cropped_images_created':0,'commercial_field_changes':370,'working_estimated_prices':185,'specific_owner_exception':1,'root_Dropbox_or_platform_writes':0}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_VERIFIED_OWNER_ACCEPTED_INDIVIDUAL_IMAGES_WORKING_PRICES_AND_CURRENT_FOLDER_REFERENCES','recorded_utc':now(),'publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256']})
state=read(H/'WORK_STATE.json');state.update(status='COMPLETE_PUBLISHED_AND_READ_BACK',publication_receipt=rel(H/'publication-receipt.json'),next='Remaining separate photographs and actual physical checks; approved Frozen Decowaves arrangement rename remains queued');write(H/'WORK_STATE.json',state)
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256','current_options','current_individual_gaps']}))
