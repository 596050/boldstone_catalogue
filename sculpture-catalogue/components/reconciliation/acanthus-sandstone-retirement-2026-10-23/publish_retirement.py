import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.retirement-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists();m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');v=read(H/'saved-file-verification.json');native=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');report=read(H/'report-verification.json');out=Path(report['output_directory']);counts=a['counts']
assert v['status']==native['status']==vis['status']=='PASS'and not v['issues']and not native['issues']
for key,path in [('workbook_sha256',H/'master-workbook.pending'),('register_sha256',H/'canonical-master-register.json'),('audit_sha256',H/'image-coverage-current.json')]:assert v[key]==native[key]==vis[key]==sha(path),key
assert report['register_sha256']==v['register_sha256']and report['audit_sha256']==v['audit_sha256']
for x in report['pages']+report['csv_files']+report['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256']
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
p=read(m['pointer']['snapshot']);old=copy.deepcopy(p);oldout=str(Path(m['master_register']['path']).parent.relative_to(B)).replace('components/reconciliation/','outputs/');newout=rel(out)
def reroute(z):
 if isinstance(z,list):return[reroute(x)for x in z]
 if isinstance(z,dict):return{k:reroute(x)for k,x in z.items()}
 if isinstance(z,str)and z.startswith(oldout+'/'):
  z=newout+z[len(oldout):]
  for x,y in [('Current_Individual_Options_188','Current_Individual_Options_187'),('Physical_Verification_Input_188','Physical_Verification_Input_187'),('Specification_Verification_Checklist_1128','Specification_Verification_Checklist_1122'),('Separate_Individual_Photographs_Required_1','Separate_Individual_Photographs_Required_0')]:z=z.replace(x,y)
 return z
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion']:p[key]=reroute(p[key])
validation={}
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:validation[key]=rel(H/name);validation[key+'_sha256']=sha(H/name)
retirement={**g['latest_catalogue_retirement'],**validation,'history_review':rel(out/'retired-options.html'),'full_history':rel(H/'retired-option-history.json'),'active_option_count_after':187,'retained_option_rows':188,'retired_photo_tasks':3,'new_photograph_or_physical_verifications':0}
p.update(recorded_utc=now(),summary=copy.deepcopy(g['summary']),current_option_count=187,retained_option_count=188,retired_option_count=1,workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_catalogue_retirement=retirement,option_lifecycle_policy=g['option_lifecycle_policy'],latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']},latest_workbook_validation=validation)
p['current_path_scope']+='; owner-retired Acanthus One Leaf Left Sandstone retained as history only, with its3 active photo requests removed. No native identifiers or paths changed by retirement.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']));links=p['current_image_review_links'];links.update(verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=copy.deepcopy(report['counts']),retired_options=rel(out/'retired-options.html'))
p['current_missing_picture_lists'].update(required_actions=67,find_capture=66,verify_existing=1,individual_gaps=1,technical_individual_gaps=10,separate_individual_photographs_required=0,in_situ_gaps=49,series_gaps=17,resolved_this_pass=0,historical_resolved_actions=84,current_resolved_actions=84,new_in_situ_roles_closed_this_refresh=0,explicit_owner_image_role_approvals_added=0,retired_actions=3,historical_resolved_actions_scope='84 existing resolved actions retained. Three Sandstone tasks retired by owner; no photographs found or verified by this correction.')
p['current_guided_image_review'].update(status='PEWTER_SERIES_EXACT_SOURCE_PENDING; FROZEN_LEGACY_IDENTITY_DEFERRED',path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),current_option_id='BSI-3635E3DC3434',current_role='Series',current_individual_gaps=1,separate_photographs_required=0,individual_capture_reviews=0,technical_individual_gaps=10,sandstone_retired=True)
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),current_option_rows=187,current_field_rows=1122,retained_historical_field_rows=1128,working_estimated_prices=186,current_physical_question_option_id=None,physical_question_status='Retired Sandstone requires no measurement; current active-option checklist retained.')
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],summary=copy.deepcopy(g['summary']),customisable_records=187,retained_option_rows=188,retired_option_rows=1,count_definition=g['count_definition'],current_option_list_sha256=sha(out/'Current_Individual_Options_187.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['current_listing_population'].update(catalogue_options=187,working_field_groups=1122,local_draft_scopes=103,nonwall_individual_drafts=100,current_resolution_population_entries=109,retired_local_draft_rows=1,retained_historical_draft_scopes=104)
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'],current_active_option_rows=187,retired_option_rows=1)
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']))
p['next_catalogue_actions']=['Acanthus One Leaf Left — Sandstone is retired: do not request photographs, measurements, price, availability or native offer creation. Keep its source history.','Obtain the exact One Leaf Pewter series-image filename or Master file link; its current folder readback does not contain a group image.','Refresh the remaining verified Moon and Shellwave/workshop folder references by stable native IDs, retaining owner holds.','Continue49 in situ and17 series gaps individually within BOLDSTONE MASTER.','Verify outstanding physical specifications for187 active options, retaining accepted source qualifications.','Keep Frozen Fish legacy identity deferred; all current Frozen Fish stay70cm high ×15cm wide.']
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for field in ['summary','current_option_count','retained_option_count','retired_option_count','latest_catalogue_retirement','option_lifecycle_policy','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','latest_commercial_completion','current_guided_image_review','current_listing_population','queued_followup_packets','next_catalogue_actions','latest_workbook_validation']:d[field]=copy.deepcopy(p[field])
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
for key in ['wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','source_platform_records_are_preserved_snapshots']:assert p[key]==old[key],key
for key,x in links.items():
 if isinstance(x,str)and x.startswith('outputs/'):assert(B/x).is_file(),key
write(H/'prepared-pointer.json',p)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'independent_lifecycle_checks':native['checks'],'active_options':187,'retained_history_option_rows':188,'working_component_identities':112,'required_actions':67,'in_situ_gaps':49,'series_gaps':17,'deferred_individual_identity_entries':1,'retired_photo_actions':3,'new_photographs_verified':0,'new_physical_verifications':0,'native_or_platform_writes':0,'preceding_release':old['publication_receipt']}
write(H/'publication-receipt.json',r);write(out/'publication-state.json',{'status':'PUBLISHED_OWNER_RETIREMENT','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json')});print(json.dumps(r,indent=2))
