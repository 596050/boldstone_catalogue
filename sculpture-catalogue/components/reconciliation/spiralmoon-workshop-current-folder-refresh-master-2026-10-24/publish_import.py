"""Publish the verified navigation-only candidate with exact baseline guards."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.spiralmoon-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
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
    candidate=dst+x[len(src):];f=Path(candidate.split('#')[0]);f=f if f.is_absolute()else B/f
    if f.is_file():return candidate
 return x
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion','current_local_draft_completion']:p[key]=reroute(p[key])
validation={}
for key,file in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:validation[key]=rel(H/file);validation[key+'_sha256']=sha(H/file)
p.update(recorded_utc=now(),status='CURRENT_MASTER188_OPTIONS_SPIRALMOON_WORKSHOP_VERIFIED_NO_ACTIVE_PHOTO_REQUESTS',workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_workbook_validation=validation,latest_spiralmoon_workshop_navigation_import={**summary,**validation},latest_active_photo_source_review=copy.deepcopy(g['latest_active_photo_source_review']),latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']})
assert len(g['active_option_ids'])==p['current_option_count']==188 and len(g['options'])==p['retained_option_count']==189
p['current_path_scope']+='; Two approved Spiralmoon workshop image moves imported, with new flat Workshop Views folder6VsQ. Primary011.JPG and existing context selections remain unchanged in In Situ. Physical-audit scope188/752, working specifications and photo holds retained.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links'].update(remaining_photograph_brief=rel(out/'remaining-photograph-requests.html'),remaining_photograph_brief_json=rel(out/'remaining-photograph-requests.json'),remaining_photograph_brief_json_sha256=sha(out/'remaining-photograph-requests.json'),verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=rep['counts'],latest_native_navigation=rel(out/'spiralmoon-folder-changes.html'),spiralmoon_all_current_images=rel(out/'all-current-spiralmoon-images.html'))
p['current_missing_picture_lists'].update(new_qualified_reference_exceptions_this_refresh=0,capture_tasks_closed_by_owner_reference_this_refresh=0,requirements_removed_by_owner_policy_this_refresh=0,resolved_this_pass=0,new_image_roles_closed_this_refresh=0,new_in_situ_roles_closed_this_refresh=0,new_individual_option_source_gaps=0)
p['current_guided_image_review'].update(path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),terminal_review_command_sha256=sha(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),terminal_runtime_verification=rel(H/'native-binding-verification.json'),terminal_runtime_verification_sha256=sha(H/'native-binding-verification.json'),component_confirmation_scope='Spiralmoon completed current navigation only; selected files/roles, all physical/commercial values, local drafts and exact owner policy scopes preserved.')
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),new_working_fields_added=0,new_comparator_estimates_added=0,new_standing_policy_fields_added=0,new_physical_measurements_added=0,new_physical_verifications=0,new_physical_field_groups_source_reviewed=0)
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_188.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']),status='COMPLETED_SPIRALMOON_WORKSHOP_NAVIGATION_IMPORTED_OTHER_PROPOSALS_RETAINED')
p['current_native_reference_map']={**old['current_native_reference_map'],'path':rel(H/'current-native-reference-map.json'),'sha256':sha(H/'current-native-reference-map.json'),'same_id_file_paths_refreshed':2,'actual_file_parent_changes':2,'actual_folder_parent_changes':0,'existing_folder_renames':0,'new_native_folders':1,'sealed_scope_originals_rehashed':82,'native_writes_by_master_import':0,'scope':'Scoped current-reference map plus sealed Spiralmoon family readback; not a whole-Dropbox inventory'}
p['latest_working_entry_owner_provenance']={**old['latest_working_entry_owner_provenance'],'path':rel(H/'working-entry-owner-provenance-sidecar.json'),'sha256':sha(H/'working-entry-owner-provenance-sidecar.json')}
p['next_catalogue_actions']=['Continue physical specifications one sculpture at a time with exact image and containing-folder links; retain accepted working estimates until actual measurements or maker inspection are supplied.','Review the separate current Squarespace authenticated-export packet without changing source history or the platform write hold; Shopify account identity remains owned by the other session.','Preserve22 context holds, Dune2Copper Series hold and deferred Frozen Fish identity. No active photograph prompts remain. Two approved Spiralmoon workshop moves are completed and imported.']
for key in ['summary','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_listing_population','platform_write_holds','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy','current_individual_photo_capture_policy','current_option_count','retained_option_count']:assert p[key]==old[key],key
updates={};fields=['current_option_count','retained_option_count','current_individual_photo_capture_policy','current_local_draft_completion','current_global_context_owner_hold','latest_spiralmoon_workshop_navigation_import','latest_working_entry_owner_provenance','latest_active_photo_source_review','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion','queued_followup_packets','next_catalogue_actions','latest_workbook_validation','current_native_reference_map']
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
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'binding_checks':n['checks'],'sheet_count':v['sheet_count'],'formula_count':v['formula_count'],'native_hyperlinks':v['native_hyperlinks'],**summary,'preceding_release':old['publication_receipt']};r['status']='PASS_PUBLISHED_AND_READ_BACK';r['import_prepared_utc']=summary['recorded_utc'];r['recorded_utc']=p['recorded_utc'];write(H/'publication-receipt.json',r)
write(out/'publication-state.json',{'status':'PUBLISHED_SPIRALMOON_CURRENT_FOLDER_REFRESH','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']})
write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED','publication_receipt':rel(H/'publication-receipt.json'),'active_options':188,'retained_options':189,'active_photo_requests':0})
print(json.dumps(r,indent=2))
