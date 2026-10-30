"""Publish only the verified path/name, working-approval and no-crop-policy refresh."""
import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.reference-refresh-tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');g=read(H/'canonical-master-register.json');reports=read(H/'link-report-verification.json');visual=read(H/'visual-verification.json');checklists=read(H/'capture-and-specification-verification.json');out=Path(reports['output_directory'])
ind=BASE/'components/parallel-reviews/selling-details-completion-2026-10-22/prepared-folder-merge-verification.json';iv=read(ind)
assert v['status']==visual['status']=='PASS'and not v['issues']and iv['status']=='PASS'
assert sha(H/'master-workbook.pending')==v['workbook_sha256']==visual['workbook_sha256']
assert sha(H/'canonical-master-register.json')==v['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+visual['previews']+checklists['csv_files']+checklists['pages']:assert sha(x['path'])==x['sha256']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256']
ptr=read(BASE/'current-master.json');prior=copy.deepcopy(ptr);scope=copy.deepcopy(g['latest_moonphases_dune_ripple_refresh'])
scope.update(verification=rel(H/'saved-file-verification.json'),verification_sha256=sha(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'),independent_verification=rel(ind),independent_verification_sha256=sha(ind),workbook_sheet='Moonphases and Dune')
ptr.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_moonphases_dune_ripple_refresh=scope,
 latest_fingerprint_working_specification_confirmation=copy.deepcopy(g['latest_fingerprint_working_specification_confirmation']),latest_fingerprint_product_finalization=copy.deepcopy(g['latest_fingerprint_product_finalization']),current_individual_photo_capture_policy=copy.deepcopy(g['current_individual_photo_capture_policy']))
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification_sha256=scope['verification_sha256'],visual_verification_sha256=scope['visual_verification_sha256']);ptr['latest_image_coverage_audit']=coverage
ptr.setdefault('historical_path_refreshes',[]).append(copy.deepcopy(prior['latest_path_refresh']));ptr['latest_path_refresh']={'recorded_utc':now(),'scope':'35 verified Moonphases,Dune Ripple and Deco Palm/Spiral folder changes;13 Dune display names and36 explicit Fingerprint working approvals; no-crops capture criterion','native_link_destinations_updated':v['native_targets_updated'],'new_native_links':68,'specification_display_changes':0,'new_canonical_options':0,'image_role_changes':0,'verification':scope['verification'],'root_remote_writes':0}
ptr['current_path_scope']+='; verified35 Moonphases/Dune Ripple/Deco Palm and Spiral folder changes, including flat custom40x50 folder; Dune Ripple1=Waves/2=Spiral, previous names retained as aliases'
ptr.setdefault('historical_image_review_links',[]).append(copy.deepcopy(prior['current_image_review_links']));links=copy.deepcopy(prior['current_image_review_links'])
for k in ['all_links','individual_image_gaps','missing_in_situ_images','missing_series_images','existing_images_to_check','resolved_image_roles']:
 links[k]=rel(out/Path(links[k]).name);assert(BASE/links[k]).is_file()
links.update(verification=rel(H/'link-report-verification.json'),verification_sha256=sha(H/'link-report-verification.json'),counts=copy.deepcopy(reports['counts']),specifications_to_verify=rel(out/'specifications-to-verify.html'),combined_shoot_and_measure=rel(out/'Combined_Shoot_and_Measure_Checklist.csv'),separate_individual_photographs_21=rel(out/'Separate_Individual_Photographs_Required_21.csv'))
ptr['current_image_review_links']=links
missing=copy.deepcopy(prior['current_missing_picture_lists'])
for k,x in list(missing.items()):
 if isinstance(x,str)and x.startswith('outputs/'):
  missing[k]=rel(out/Path(x).name);assert(BASE/missing[k]).is_file()
missing.update(exact_crop_candidates=0,separate_individual_photos_required=21,historical_crop_candidates_declined_by_owner=13,new_image_roles_closed_this_refresh=0)
ptr['current_missing_picture_lists']=missing
ptr['current_specification_verification']={'path':rel(H/'capture-and-specification-verification.json'),'sha256':sha(H/'capture-and-specification-verification.json'),'review':links['specifications_to_verify'],'field_checklist':rel(out/'Specification_Verification_Checklist_1116_Fields.csv'),'current_option_rows':186,'current_field_rows':1116,'new_physical_measurements_added':0,'source_price_check':rel(H/'current-price-source-text-check.json'),'commercial_values_changed_in_this_refresh':0}
count=copy.deepcopy(prior['current_individual_sculpture_list']);count.update(recorded_utc=now(),register=ptr['register'],register_sha256=ptr['register_sha256'],workbook_sha256=ptr['workbook_sha256'],publication_receipt=ptr['publication_receipt'],current_option_list=rel(out/'Current_Individual_Options_186.csv'),current_option_list_sha256=sha(out/'Current_Individual_Options_186.csv'),count_summary=rel(out/'current-count-summary.json'),count_summary_sha256=sha(out/'current-count-summary.json'));ptr['current_individual_sculpture_list']=count
ptr.setdefault('historical_guided_image_reviews',[]).append(copy.deepcopy(prior['current_guided_image_review']));guided={'status':'READY_FOR_SEPARATE_INDIVIDUAL_PHOTOGRAPH_COLLECTION','path':rel(H/'photo-review-queue.json'),'sha256':sha(H/'photo-review-queue.json'),'review_list':links['individual_image_gaps'],'current_individual_gaps':22,'separate_photographs_required':21,'deferred_legacy_identity':1,'exact_crops_declined':True};ptr['current_guided_image_review']=guided
if 'queued_native_path_refreshes'in ptr:ptr.setdefault('completed_native_path_refresh_queue_snapshots',[]).append(ptr.pop('queued_native_path_refreshes'))
moon=BASE.parent/'reports/dropbox-moonspirals-flat-renames-2026-10-22/current-reference-overlay.json'
if moon.is_file():ptr['queued_native_path_refreshes']={'status':'NEXT_AFTER_FROZEN_PUBLICATION','family':'Moonspirals','path':str(moon),'sha256':sha(moon),'scope':'Four later owner-approved group-folder renames, no new components/specification changes; not projected in this frozen release.'}
ptr['next_catalogue_actions']=['Collect21 separate individual photographs; keep group references and do not create crops. One additional historical Frozen Fish identity remains deferred; current faces stay70x15cm.','Complete61in situ and18series image gaps using the linked per-option capture checklist.','Record actual dimensions, weighed mass, confirmed material and fitted rear fixing where needed; keep existing owner-stated values and estimates qualified.','Integrate the separately prepared owner-authorized selling-details packet only after source/price checks; no new commercial values are written in this release.','Apply the later four-folder Moonspirals overlay at the next safe master refresh.']
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[key]['path']);d=read(p)
 d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],current_individual_catalogue_count=copy.deepcopy(count),latest_moonphases_dune_ripple_refresh=copy.deepcopy(scope),latest_fingerprint_working_specification_confirmation=copy.deepcopy(ptr['latest_fingerprint_working_specification_confirmation']),latest_fingerprint_product_finalization=copy.deepcopy(ptr['latest_fingerprint_product_finalization']),current_individual_photo_capture_policy=copy.deepcopy(ptr['current_individual_photo_capture_policy']),latest_image_coverage_audit=copy.deepcopy(coverage),current_image_review_links=copy.deepcopy(links),current_missing_picture_lists=copy.deepcopy(missing),current_guided_image_review=copy.deepcopy(guided),current_specification_verification=copy.deepcopy(ptr['current_specification_verification']),next_image_review_actions=copy.deepcopy(ptr['next_catalogue_actions']))
 if key=='component_checkpoint':d['current_master_validation']={'path':scope['verification'],'sha256':scope['verification_sha256']}
 updates[p]=d
for k in ['summary','latest_listing_resolution','latest_listing_reconciliation','latest_moon_and_shellwave_numbering','latest_lava_moon_numbering','latest_gleneagles_numbering','latest_raked_spiral_paths','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','current_listing_population']:assert ptr.get(k)==prior.get(k),k
for x in m.values():assert sha(x['path'])==x['sha256']
write(H/'prepared-pointer.json',ptr)
target=BASE/ptr['workbook'];os.replace(H/'master-workbook.pending',target)
for p,x in updates.items():write(p,x)
write(BASE/'current-master.json',ptr)
assert sha(target)==ptr['workbook_sha256']and sha(BASE/ptr['register'])==ptr['register_sha256']and read(BASE/'current-master.json')==ptr
for p,x in updates.items():assert read(p)==x and x['current_master_catalogue']==ptr
for k,x in m.items():
 if k not in ['master_pointer','master_workbook','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256']
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':ptr['workbook_sha256'],'register':str(BASE/ptr['register']),'register_sha256':ptr['register_sha256'],'audit':str(H/'image-coverage-current.json'),'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},'checks':v['checks'],'independent_prepared_verification':str(ind),'independent_prepared_verification_sha256':sha(ind),'current_options':186,'working_component_identities':112,'working_field_groups':1116,'sheets':27,'formulas':2794,'native_hyperlinks':11495,'native_link_targets_updated':v['native_targets_updated'],'new_binding_links':68,'folder_renames':35,'stable_native_objects_verified':1435,'stable_native_file_IDs_and_sizes':1370,'dune_option_display_names_updated':13,'explicit_Fingerprint_working_approvals':36,'specification_display_changes':0,'new_physical_verifications':0,'current_individual_gaps':22,'separate_individual_photos_required':21,'deferred_identity':1,'in_situ_gaps':61,'series_gaps':18,'required_picture_actions':101,'new_image_roles_closed':0,'cropped_images_created':0,'commercial_field_changes':0,'root_Dropbox_or_platform_writes':0}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_VERIFIED_CURRENT_FOLDER_NAMES_WORKING_APPROVAL_AND_NO_CROP_CHECKLISTS','recorded_utc':now(),'publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256']})
state=read(H/'WORK_STATE.json');state.update(status='COMPLETE_PUBLISHED_AND_READ_BACK',publication_receipt=rel(H/'publication-receipt.json'),next='Later Moonspirals path projection, new image candidates and owner-authorized selling-details packet');write(H/'WORK_STATE.json',state)
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256','folder_renames','current_options']}))
