"""Publish the owner global-context hold after exact saved-file and runtime checks."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.context-hold-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');rep=read(H/'report-verification.json');v=read(H/'saved-file-verification.json');n=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');out=Path(rep['output_directory']);event=read(H/'global-owner-context-hold.json')
assert v['status']==n['status']==vis['status']=='PASS'and not v['issues']and not n['issues']
for key,path in [('workbook_sha256',H/'master-workbook.pending'),('register_sha256',H/'canonical-master-register.json'),('audit_sha256',H/'image-coverage-current.json')]:assert v[key]==n[key]==vis[key]==sha(path),key
assert rep['register_sha256']==v['register_sha256']and rep['audit_sha256']==v['audit_sha256']
for item in rep['pages']+rep['csv_files']+rep['thumbnail_files']+vis['previews']:assert sha(item['path'])==item['sha256'],item['path']
for key,item in m.items():assert sha(item['path'])==sha(item['snapshot'])==item['sha256'],key
old=read(m['pointer']['snapshot']);p=copy.deepcopy(old);oldh=Path(m['master_register']['path']).parent;oldout=Path(read(m['source_report_verification']['snapshot'])['output_directory'])
def reroute(x):
 if isinstance(x,list):return[reroute(z)for z in x]
 if isinstance(x,dict):return{k:reroute(z)for k,z in x.items()}
 if isinstance(x,str):
  for src,dst in [(str(oldout),str(out)),(rel(oldout),rel(out)),(str(oldh),str(H)),(rel(oldh),rel(H))]:
   if x.startswith(src+'/'):
    candidate=dst+x[len(src):];file=candidate.split('#')[0];absolute=Path(file)if Path(file).is_absolute()else B/file
    if absolute.is_file():return candidate
 return x
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion']:p[key]=reroute(p[key])
validation={}
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:validation[key]=rel(H/name);validation[key+'_sha256']=sha(H/name)
p.update(recorded_utc=now(),status='CURRENT_MASTER_ALL_MISSING_CONTEXT_OWNER_HELD_SERIES_ACTIVE',workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_workbook_validation=validation,current_global_context_owner_hold=event,latest_global_context_hold_import={**g['latest_global_context_hold_import'],**validation},latest_active_photo_source_review=copy.deepcopy(g['latest_active_photo_source_review']),latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']})
p['current_path_scope']+='; Owner global hold changes prompting only: all22 missing context roles held;17 series remain active. No additional native paths or role bindings imported.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links'].update(remaining_photograph_brief=rel(out/'remaining-photograph-requests.html'),remaining_photograph_brief_json=rel(out/'remaining-photograph-requests.json'),remaining_photograph_brief_json_sha256=sha(out/'remaining-photograph-requests.json'),verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=copy.deepcopy(rep['counts']),current_photograph_walkthrough=rel(out/'photograph-review-walkthrough.html'),active_in_situ_requests=rel(out/'active-in-situ-photo-requests.html'),held_in_situ_requests=rel(out/'held-in-situ-cases.html'))
p['current_missing_picture_lists'].update(required_actions=40,in_situ_gaps=22,series_gaps=17,resolved_this_pass=0,new_image_roles_closed_this_refresh=0,new_in_situ_roles_closed_this_refresh=0,current_resolved_actions=112,historical_resolved_actions=112,active_in_situ_source_requests=0,owner_held_in_situ_cases=22,active_in_situ_requests_csv=rel(out/'Active_In_Situ_Photographs_Required_0.csv'),held_in_situ_cases_csv=rel(out/'Held_In_Situ_Cases_22.csv'),current_reviewed_option_records=17,historical_resolved_actions_scope='112 prior resolved actions retained. All22 unresolved context roles are now owner-held;17 series requests remain active. No image gap is closed.')
p['current_guided_image_review'].update(status='ALL_MISSING_CONTEXT_OWNER_HELD_17_SERIES_REQUESTS_ACTIVE',path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),terminal_review_command_sha256=sha(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),terminal_runtime_verification=rel(H/'native-binding-verification.json'),terminal_runtime_verification_sha256=sha(H/'native-binding-verification.json'),active_in_situ_source_requests=0,series_source_requests=17,held_in_situ_cases=22,global_context_prompts_suppressed=True,global_context_owner_hold=event,current_role='Series',source_question_coordination='A continues separate series-only reviews. B context questions are suppressed under the global owner hold. Physical measurement questions remain separate.',component_confirmation_scope='Global context-only hold imports no photographs or identity/specification changes.17 separate series requests remain active.')
p['current_guided_image_review']['deferred_option_ids']=sorted(set(p['current_guided_image_review']['deferred_option_ids'])|set(event['all_held_option_ids']))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),new_physical_measurements_added=0,new_physical_verifications=0)
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_187.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']),status='GLOBAL_CONTEXT_HOLD_IMPORTED_COMPLETED_NATIVE_NAVIGATION_AND_PRIOR_NATIVE_HOLD_QUEUED',per_item_MCP4_and_WideLip_holds_imported_as_history=True,global_context_hold_applied=True)
p['next_catalogue_actions']=['Import the separately completed Raked Spiral/Moonphase native navigation packet by stable IDs in the next bounded folder refresh; preserve its identity holds.','Continue17 separate series photograph requests, one option at a time. Pewter group/finish identification remains series-only.','Do not request missing in situ/display photographs until the owner resumes; retain all22 context gaps and their evidence.','Verify actual dimensions/depth, bare-panel weight, maker material and fitted fixing for187 active options; retain accepted estimates until object evidence is supplied.','Preserve002/003 canonical identity holds, the deferred Frozen Fish identity and70cm high×15cm wide current policy. One Leaf Sandstone stays retired.']
for key in ['summary','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_listing_population','current_option_count','platform_write_holds']:assert p[key]==old[key],key
updates={}
fields=['current_global_context_owner_hold','latest_global_context_hold_import','latest_active_photo_source_review','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion','queued_followup_packets','next_catalogue_actions','latest_workbook_validation']
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for field in fields:d[field]=copy.deepcopy(p[field])
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
for group in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_individual_sculpture_list']:
 for key,x in p[group].items():
  if group=='current_individual_sculpture_list'and key=='publication_receipt':assert x==rel(H/'publication-receipt.json');continue
  if isinstance(x,str)and x.startswith(('outputs/','components/')):assert(B/x.split('#')[0]).is_file(),(group,key,x)
write(H/'prepared-pointer.json',p)
if '--prepare'in sys.argv:print('ALL_GLOBAL_HOLD_PUBLICATION_GUARDS_PASS_PREPARED_ONLY');raise SystemExit(0)
for key,item in m.items():assert sha(item['path'])==item['sha256'],key
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'independent_binding_checks':n['checks'],'sheet_count':v['sheet_count'],'formula_count':v['formula_count'],'native_hyperlinks':v['native_hyperlinks'],'active_context':0,'held_context':22,'active_series':17,'current_options':187,'retained_options':188,'component_identities':112,'all_image_gaps_retained':True,'required_picture_actions':40,'image_roles_closed':0,'primary_images_changed':0,'specifications_changed':0,'new_physical_verifications':0,'native_or_platform_writes':0,'terminal_actual_rows':17,'terminal_script_sha256':sha(H/'guided_review.py'),'global_owner_policy_sha256':m['owner_policy']['sha256'],'per_item_owner_transcripts_preserved':4,'later_completed_native_navigation_queued':True,'preceding_release':old['publication_receipt']}
write(H/'publication-receipt.json',r);write(out/'publication-state.json',{'status':'PUBLISHED_GLOBAL_CONTEXT_OWNER_HOLD','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']});write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED','publication_receipt':rel(H/'publication-receipt.json'),'active_context':0,'held_context':22,'active_series':17});print(json.dumps(r,indent=2))
