"""Publish the bounded candidate only after saved-file, source and visual checks."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.riyadh-policy-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');rep=read(H/'report-verification.json');v=read(H/'saved-file-verification.json');n=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');summary=read(H/'import-summary.json');out=Path(rep['output_directory']);old=read(m['pointer']['snapshot']);p=copy.deepcopy(old);oldh=Path(m['master_register']['path']).parent;oldout=Path(read(m['source_report_verification']['snapshot'])['output_directory'])
assert v['status']==n['status']==vis['status']=='PASS'and not v['issues']and not n['issues']
for key,file in [('workbook_sha256','master-workbook.pending'),('register_sha256','canonical-master-register.json'),('audit_sha256','image-coverage-current.json')]:assert v[key]==n[key]==vis[key]==sha(H/file),key
assert rep['register_sha256']==v['register_sha256']and rep['audit_sha256']==v['audit_sha256']
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256'],x['path']
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
def reroute(x):
 if isinstance(x,list):return[reroute(z)for z in x]
 if isinstance(x,dict):return{k:reroute(z)for k,z in x.items()}
 if isinstance(x,str):
  for src,dst in [(str(oldout),str(out)),(rel(oldout),rel(out)),(str(oldh),str(H)),(rel(oldh),rel(H))]:
   if x.startswith(src+'/'):
    candidate=(dst+x[len(src):]).replace('Active_Series_Photographs_Required_12.csv','Active_Series_Photographs_Required_0.csv');f=Path(candidate.split('#')[0]);f=f if f.is_absolute()else B/f
    if f.is_file():return candidate
 return x
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion']:p[key]=reroute(p[key])
validation={}
for key,file in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:validation[key]=rel(H/file);validation[key+'_sha256']=sha(H/file)
p.update(recorded_utc=now(),status='CURRENT_MASTER188_OPTIONS_BATTERSEA2_CURRENT_NAVIGATION_VERIFIED',workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_workbook_validation=validation,retained_option_count=189,current_option_count=188,latest_battersea2_native_navigation_import={**summary,**validation},latest_active_photo_source_review=copy.deepcopy(g['latest_active_photo_source_review']),latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']})
assert p['current_option_count']==len(g['active_option_ids'])==188 and p['retained_option_count']==len(g['options'])==189 and len(g['retired_option_ids'])==1
p['current_path_scope']+='; Battersea2 seven existing photographs have current paths and actual parent IDs from sealed completed filing. PrimaryylqA remains in productfolderyjEg; contextud0g retains selection/role with newactualparent6VsA. No identities, photo policies, working specifications, prices or availability changed.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links'].update(remaining_photograph_brief=rel(out/'remaining-photograph-requests.html'),remaining_photograph_brief_json=rel(out/'remaining-photograph-requests.json'),remaining_photograph_brief_json_sha256=sha(out/'remaining-photograph-requests.json'),verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=rep['counts'],latest_series_policies=rel(out/'series-policy-decisions.html'),latest_native_navigation=rel(out/'battersea-folder-changes.html'),riyadh_all_current_images=rel(out/'riyadh-all-images.html'))
p['current_missing_picture_lists'].update(required_actions=25,series_gaps=1,optional_series_requirements=70,active_series_source_requests=0,current_reviewed_option_records=1,active_individual_source_requests=1,active_series_requests_csv=rel(out/'Active_Series_Photographs_Required_0.csv'),requirements_removed_by_owner_policy_this_refresh=0,resolved_this_pass=0,new_image_roles_closed_this_refresh=0,new_in_situ_roles_closed_this_refresh=0,new_individual_option_source_gaps=0,historical_resolved_actions_scope='112 earlier resolved actions retained. Battersea2 current file locations refreshed without additional photographs or policy changes. No active Series-photo requirements; one individual water-build source request remains active;22 context and one Series request held. Frozen Fish legacy identity deferred.')
p['current_guided_image_review'].update(status='ONE_INDIVIDUAL_ZERO_SERIES_ACTIVE_CONTEXT_HELD',path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),terminal_review_command_sha256=sha(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),terminal_runtime_verification=rel(H/'native-binding-verification.json'),terminal_runtime_verification_sha256=sha(H/'native-binding-verification.json'),series_source_requests=0,active_individual_source_requests=1,owner_optional_series_option_ids=sorted({o['product_id']for o in g['options']if o.get('current_series_optionality_policy')}),source_question_coordination='Preserve22 context holds, Dune2Copper Series hold and Frozen Fish identity deferral. Later owner answers remain separate packets.',component_confirmation_scope='Current Battersea2 paths/actual parent only. Existing image selections, role meanings, photo policies and physical/commercial values retained.')
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),new_working_fields_added=0,new_comparator_estimates_added=0,new_standing_policy_fields_added=0,new_physical_measurements_added=0,new_physical_verifications=0,new_physical_field_groups_source_reviewed=0)
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_188.csv'),count_summary_sha256=sha(out/'current-count-summary.json'),retained_option_rows=189)
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'],new_water_panel_price_estimates=0)
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']),status='SEALED_BATTERSEA2_NAVIGATION_IMPORTED_OTHER_PROPOSALS_RETAINED')
p['current_native_reference_map']={**old['current_native_reference_map'],'path':rel(H/'current-native-reference-map.json'),'sha256':sha(H/'current-native-reference-map.json'),'same_id_file_paths_refreshed':7,'actual_file_parent_changes':7,'actual_folder_parent_changes':0,'existing_folder_renames':0,'new_native_folders':1,'sealed_scope_originals_rehashed':77,'native_writes_by_master_import':0,'scope':'Scoped current-reference map plus sealed Battersea family readback; not a whole-Dropbox inventory'}
p['current_native_reference_map'].pop('native_changes_this_refresh',None)
p['latest_working_entry_owner_provenance']={**old['latest_working_entry_owner_provenance'],'path':rel(H/'working-entry-owner-provenance-sidecar.json'),'sha256':sha(H/'working-entry-owner-provenance-sidecar.json')}
p['next_catalogue_actions']=['Obtain a complete individual photograph of Moon and Shellwave2 White Water Feature. No active Series-photo requirements remain after the exact owner preferences; unverified group photographs remain unverified.','Preserve22 context holds, Dune2Copper Series hold and the deferred Frozen Fish identity. Current Frozen Fish dimensions remain70×15cm.','Verify actual dimensions/depth, bare-panel weight, maker material and fitted fixing with the188-option checklist. Accepted estimates, the specific Moon Crater4 commercial exception and other working prices/availability remain labelled.']
for key in ['summary','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_listing_population','platform_write_holds','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy']:assert p[key]==old[key],key
updates={};fields=['current_option_count','retained_option_count','current_global_context_owner_hold','latest_battersea2_native_navigation_import','latest_working_entry_owner_provenance','latest_active_photo_source_review','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion','queued_followup_packets','next_catalogue_actions','latest_workbook_validation','current_native_reference_map']
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
if '--prepare'in sys.argv:print('ALL_PUBLICATION_GUARDS_PASS_PREPARED_ONLY');raise SystemExit(0)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p and d['retained_option_count']==189
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'binding_checks':n['checks'],'sheet_count':v['sheet_count'],'formula_count':v['formula_count'],'native_hyperlinks':v['native_hyperlinks'],**summary,'preceding_release':old['publication_receipt']}
r['status']='PASS_PUBLISHED_AND_READ_BACK';r['recorded_utc']=now();write(H/'publication-receipt.json',r)
write(out/'publication-state.json',{'status':'PUBLISHED_BATTERSEA2_CURRENT_FOLDER_REFRESH','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']})
write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED','publication_receipt':rel(H/'publication-receipt.json'),'active_options':188,'retained_options':189,'active_series':0})
print(json.dumps(r,indent=2))
