"""Publish verified references while preserving current prices, identities and fields."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.path-refresh-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists(),'Already published'
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');g=read(H/'canonical-master-register.json');reports=read(H/'link-report-verification.json');cl=read(H/'capture-and-specification-verification.json');visual=read(H/'visual-verification.json');bind=read(H/'native-bindings-verification.json');extra=read(H/'folder-refresh-report-verification.json');out=Path(reports['output_directory'])
assert v['status']==visual['status']==bind['status']=='PASS'and not v['issues']
assert sha(H/'master-workbook.pending')==v['workbook_sha256']==visual['workbook_sha256']==bind['workbook_sha256']
assert sha(H/'canonical-master-register.json')==v['register_sha256']==bind['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+cl['pages']+cl['csv_files']+visual['previews']+extra['pages']+extra['csv_files']:assert sha(x['path'])==x['sha256']
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
ptr=read(BASE/'current-master.json');prior=copy.deepcopy(ptr);scope=copy.deepcopy(g['latest_spice_frozen_path_refresh'])
validation={'verification':rel(H/'saved-file-verification.json'),'verification_sha256':sha(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'visual_verification_sha256':sha(H/'visual-verification.json'),'native_binding_verification':rel(H/'native-bindings-verification.json'),'native_binding_verification_sha256':sha(H/'native-bindings-verification.json')}
scope.update(validation);scope['walkthrough']=rel(out/'folder-changes.html');scope['walkthrough_sha256']=sha(out/'folder-changes.html');scope['folder_audit_rows']=53
ptr.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_spice_frozen_path_refresh=scope)
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(validation);ptr['latest_image_coverage_audit']=coverage
ptr.setdefault('historical_path_refreshes',[]).append(copy.deepcopy(prior['latest_path_refresh']));ptr['latest_path_refresh']={'recorded_utc':now(),'scope':'Spice Texture 1/2 actual component folders and Frozen Decowaves 1–2–1 three-panel arrangement folder','native_link_destinations_updated':v['native_targets_updated'],'new_native_links':8,'folder_reference_rows_added':4,'folder_renames':3,'new_folders':1,'moved_files':1,'new_canonical_options':0,'image_role_changes':0,'commercial_field_changes':0,'verification':validation['verification'],'root_remote_writes':0}
ptr['current_path_scope']+='; Spice Texture 1/2 actual containing folders and Frozen Decowaves three-panel group name verified across178native objects; all original file/folder IDs preserved, one new Spice2 folder ID recorded'
ptr.setdefault('historical_image_review_links',[]).append(copy.deepcopy(prior['current_image_review_links']));links=copy.deepcopy(prior['current_image_review_links'])
for k in ['all_links','individual_image_gaps','missing_in_situ_images','missing_series_images','existing_images_to_check','resolved_image_roles','specifications_to_verify','selling_details','combined_shoot_and_measure','separate_individual_photographs']:
 links[k]=rel(out/Path(links[k]).name);assert(BASE/links[k]).is_file()
links.update(verification=rel(H/'link-report-verification.json'),verification_sha256=sha(H/'link-report-verification.json'),counts=copy.deepcopy(reports['counts']),latest_folder_walkthrough=scope['walkthrough']);ptr['current_image_review_links']=links
missing=copy.deepcopy(prior['current_missing_picture_lists'])
for k,x in list(missing.items()):
 if isinstance(x,str)and x.startswith('outputs/'):
  missing[k]=rel(out/Path(x).name);assert(BASE/missing[k]).is_file()
missing.update(resolved_this_pass=0,new_image_roles_closed_this_refresh=0);ptr['current_missing_picture_lists']=missing
spec=copy.deepcopy(prior['current_specification_verification']);spec.update(path=rel(H/'capture-and-specification-verification.json'),sha256=sha(H/'capture-and-specification-verification.json'),review=links['specifications_to_verify'],field_checklist=rel(out/'Specification_Verification_Checklist_1116_Fields.csv'),selling_details=links['selling_details'],commercial_values_changed_in_this_refresh=0);ptr['current_specification_verification']=spec
commercial=copy.deepcopy(prior['latest_commercial_completion']);commercial.update(current_review=links['selling_details'],current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=rel(H/'publication-receipt.json'));ptr['latest_commercial_completion']=commercial
count=copy.deepcopy(prior['current_individual_sculpture_list']);count.update(recorded_utc=now(),register=ptr['register'],register_sha256=ptr['register_sha256'],workbook_sha256=ptr['workbook_sha256'],publication_receipt=ptr['publication_receipt'],current_option_list=rel(out/'Current_Individual_Options_186.csv'),current_option_list_sha256=sha(out/'Current_Individual_Options_186.csv'),count_summary=rel(out/'current-count-summary.json'),count_summary_sha256=sha(out/'current-count-summary.json'));ptr['current_individual_sculpture_list']=count
ptr.setdefault('historical_guided_image_reviews',[]).append(copy.deepcopy(prior['current_guided_image_review']));guided=copy.deepcopy(prior['current_guided_image_review']);guided.update(path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),review_list=links['individual_image_gaps']);ptr['current_guided_image_review']=guided
ptr.setdefault('completed_native_path_refresh_queue_snapshots',[]).append({'status':'COMPLETED_IN_CURRENT_PUBLICATION','prior_master_queue':copy.deepcopy(prior.get('queued_native_path_refreshes')),'later_completed_changes_queue':m['prior_pending_queue'],'completed_scope':scope})
ptr.pop('queued_native_path_refreshes',None)
later=[]
for family,filename,expected in [('Egyptian Two Palms','dropbox-egyptian-two-palms-flat-renames-2026-10-22','9deefa2dda417e3f984e7bc4d40bf1d0d324cb75d9b0242c32fa59e37956768b'),('Brancusi Gold Leaf','dropbox-brancusi-gold-leaf-flat-renames-2026-10-22','71316e7d16f6662098719b321d498221599155115ea007b2ee9a92fec1b6a83f')]:
 p0=BASE.parent/'reports'/filename/'current-reference-overlay.json'
 if p0.is_file():
  assert sha(p0)==expected;later.append({'family':family,'path':str(p0),'sha256':sha(p0),'root_native_verification_pending':True,'scope':'Later owner-approved group-folder renames; preserve identities, specifications and roles. Outside the requested Spice/Frozen master refresh.'})
if later:ptr['queued_native_path_refreshes']={'status':'SEPARATE_DIRECTORY_COMPLETED_SCOPES_NOT_PROJECTED_IN_THIS_TWO_CHANGE_REFRESH','changes':later}
ptr['next_catalogue_actions']=['Collect18 separate individual photographs; retain the13 declined crop proposals and one deferred Frozen Fish identity. All current Frozen Fish remain70x15cm.','Complete61 in situ and18 series image gaps using the linked77-option shoot/measure checklist.','Verify actual component dimensions, weight, material and fitted fixing; preserve all labelled working estimates and current commercial policies.','The two requested Spice Texture and Frozen Decowaves master changes are complete. Later separately completed folder changes are tracked outside this bounded refresh.','Verify current authenticated platform inventories and exact component matches before creating or updating individual buying listings.']
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[key]['path']);d=read(p);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],current_individual_catalogue_count=copy.deepcopy(count),latest_spice_frozen_path_refresh=copy.deepcopy(scope),latest_image_coverage_audit=copy.deepcopy(coverage),current_image_review_links=copy.deepcopy(links),current_missing_picture_lists=copy.deepcopy(missing),current_specification_verification=copy.deepcopy(spec),latest_commercial_completion=copy.deepcopy(commercial),current_guided_image_review=copy.deepcopy(guided),next_image_review_actions=copy.deepcopy(ptr['next_catalogue_actions']))
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[p]=d
for k in ['summary','current_listing_population','latest_listing_resolution','latest_listing_reconciliation','latest_fingerprint_working_specification_confirmation','latest_catalogue_followup','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','current_individual_photo_capture_policy']:assert ptr.get(k)==prior.get(k),k
write(H/'prepared-pointer.json',ptr)
if '--prepare-only'in sys.argv:print('PREPARED_NO_CURRENT_FILES_REPLACED');raise SystemExit(0)
for k,x in m.items():assert sha(x['path'])==x['sha256'],k
target=BASE/ptr['workbook'];os.replace(H/'master-workbook.pending',target)
for p,x in updates.items():write(p,x)
write(BASE/'current-master.json',ptr)
assert sha(target)==ptr['workbook_sha256']and sha(BASE/ptr['register'])==ptr['register_sha256']and read(BASE/'current-master.json')==ptr
for p,x in updates.items():assert read(p)==x and x['current_master_catalogue']==ptr
for k,x in m.items():
 if k not in ['master_pointer','master_workbook','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256'],k
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':ptr['workbook_sha256'],'register':str(BASE/ptr['register']),'register_sha256':ptr['register_sha256'],'audit':str(H/'image-coverage-current.json'),'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},'saved_file_checks':v['checks'],'fresh_native_binding_checks':bind['checks'],'affected_current_links_verified':bind['affected_current_native_links_checked'],'current_options':186,'working_component_identities':112,'working_field_groups':1116,'sheets':28,'formulas':3356,'native_hyperlinks':11901,'native_link_targets_updated':124,'new_folder_reference_links':8,'folder_audit_rows':53,'original_files_preserved':161,'original_folder_IDs_preserved_including_families':16,'new_folder_IDs':1,'moved_files':1,'folder_renames':3,'file_paths_updated':26,'commercial_specification_identity_and_image_role_changes':0,'current_individual_gaps':19,'in_situ_gaps':61,'series_gaps':18,'root_Dropbox_or_platform_writes':0}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_VERIFIED_SPICE_SPLIT_AND_FROZEN_DECOWAVES_FOLDER_REFERENCES','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256']});state=read(H/'WORK_STATE.json');state.update(status='COMPLETE_PUBLISHED_AND_READ_BACK',publication_receipt=rel(H/'publication-receipt.json'));write(H/'WORK_STATE.json',state)
write(H/'completed-two-change-queue.json',{'status':'BOTH_REQUESTED_MASTER_REFERENCE_CHANGES_COMPLETE','Spice_Texture':scope['source_overlays'][0],'Frozen_Decowaves':scope['source_overlays'][1],'publication_receipt':str(H/'publication-receipt.json'),'prior_queue_snapshot':m['prior_pending_queue']})
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256','native_link_targets_updated','current_options']}))
