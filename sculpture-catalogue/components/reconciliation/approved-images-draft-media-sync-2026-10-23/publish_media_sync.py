import json,hashlib,copy,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.media-sync-tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
assert not(H/'publication-receipt.json').exists();m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');native=read(H/'native-binding-verification.json');visual=read(H/'visual-verification.json');reports=read(H/'report-verification.json');g=read(H/'canonical-master-register.json');out=Path(reports['output_directory']);p=read(B/'current-master.json');old=copy.deepcopy(p);prior=(B/p['register']).parent
assert v['status']==native['status']==visual['status']=='PASS'and not v['issues']and not native['issues']
assert sha(H/'master-workbook.pending')==v['workbook_sha256']==native['workbook_sha256']==visual['workbook_sha256']
assert sha(H/'canonical-master-register.json')==v['register_sha256']==native['register_sha256']==visual['register_sha256']==reports['register_sha256']
assert sha(H/'image-coverage-current.json')==v['audit_sha256']==native['audit_sha256']==visual['audit_sha256']==reports['audit_sha256']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+visual['previews']:assert sha(x['path'])==x['sha256']
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
oldout=rel(Path(read(prior/'report-verification.json')['output_directory']));newout=rel(out)
def urls(z):
 if isinstance(z,list):return[urls(x)for x in z]
 if isinstance(z,dict):return{k:urls(v)for k,v in z.items()}
 if isinstance(z,str)and z.startswith(oldout+'/'):return newout+z[len(oldout):]
 return z
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','latest_commercial_completion','current_individual_sculpture_list']:p[key]=urls(p[key])
validation={'verification':rel(H/'saved-file-verification.json'),'verification_sha256':sha(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'visual_verification_sha256':sha(H/'visual-verification.json'),'native_binding_verification':rel(H/'native-binding-verification.json'),'native_binding_verification_sha256':sha(H/'native-binding-verification.json')}
p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_draft_media_synchronization={**g['latest_draft_media_synchronization'],**validation,'current_workbook_cells_synchronized':36})
p['latest_image_coverage_audit']={**copy.deepcopy(g['latest_image_coverage_audit']),**validation};p['latest_approved_images_folder_refresh'].update(validation);p['latest_approved_images_folder_refresh']['review']=rel(out/'completed-changes.html');p['latest_approved_images_folder_refresh']['accepted_references']=rel(out/'accepted-listing-references.html')
p['current_image_review_links'].update(verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'))
p['current_guided_image_review'].update(path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'))
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_188.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'))
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']),latest_draft_media_synchronization=copy.deepcopy(p['latest_draft_media_synchronization']),latest_image_coverage_audit=copy.deepcopy(p['latest_image_coverage_audit']),current_image_review_links=copy.deepcopy(p['current_image_review_links']),current_missing_picture_lists=copy.deepcopy(p['current_missing_picture_lists']),current_specification_verification=copy.deepcopy(p['current_specification_verification']),latest_commercial_completion=copy.deepcopy(p['latest_commercial_completion']),current_guided_image_review=copy.deepcopy(p['current_guided_image_review']))
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
for k in ['summary','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','current_individual_photo_capture_policy','source_platform_records_are_preserved_snapshots','current_listing_population','next_catalogue_actions']:assert p[k]==old[k],k
write(H/'prepared-pointer.json',p)
if '--prepare-only'in sys.argv:print('PREPARED_NO_CURRENT_FILES_REPLACED');raise SystemExit(0)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'independent_binding_checks':native['checks'],'sheet_count':28,'formula_count':3390,'native_hyperlinks':v['native_hyperlinks'],'media_option_records_synchronized':12,'media_cells_synchronized':36,'current_options':188,'working_component_identities':112,'required_actions':87,'individual_action_entries':6,'technical_individual_gaps':11,'in_situ_gaps':63,'series_gaps':18,'new_physical_verifications':0,'native_or_platform_writes_in_this_consistency_correction':0,'preceding_import_and_restore_receipt':str(prior/'publication-receipt.json'),'pending_followup_entries':len(read(H/'pending-followups.json')['entries'])};write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_MASTER_DRAFT_MEDIA_SYNCHRONIZED','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']});write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED_PHYSICAL_REVIEW_AWAITING_OWNER','publication_receipt':rel(H/'publication-receipt.json'),'next_question_option_id':'BSI-C41824131174','pending_followups':rel(H/'pending-followups.json')});print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256','media_option_records_synchronized','individual_action_entries']}))
