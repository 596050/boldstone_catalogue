import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.queued-import-tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');v=read(H/'saved-file-verification.json');native=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
assert v['status']==native['status']==vis['status']=='PASS'and not v['issues']and not native['issues']
for key,path in [('workbook_sha256',H/'master-workbook.pending'),('register_sha256',H/'canonical-master-register.json'),('audit_sha256',H/'image-coverage-current.json')]:assert v[key]==native[key]==vis[key]==sha(path),key
assert rep['register_sha256']==v['register_sha256']and rep['audit_sha256']==v['audit_sha256']
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256']
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
p=read(m['pointer']['snapshot']);old=copy.deepcopy(p);oldout='outputs/master-only-source-correction-2026-10-23';newout=rel(out)
def reroute(z):
 if isinstance(z,list):return[reroute(x)for x in z]
 if isinstance(z,dict):return{k:reroute(x)for k,x in z.items()}
 if isinstance(z,str)and z.startswith(oldout+'/'):return newout+z[len(oldout):]
 return z
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion']:p[key]=reroute(p[key])
validation={'verification':rel(H/'saved-file-verification.json'),'verification_sha256':sha(H/'saved-file-verification.json'),'native_binding_verification':rel(H/'native-binding-verification.json'),'native_binding_verification_sha256':sha(H/'native-binding-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'visual_verification_sha256':sha(H/'visual-verification.json')}
current={**g['latest_queued_master_import'],**validation,'review':rel(out/'imported-approvals.html'),'folder_changes':rel(out/'completed-changes.html')}
p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_queued_master_import=current,latest_context_folder_refresh=current,latest_draft_media_synchronization={**g['latest_draft_media_synchronization'],**validation},latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']},imported_owner_review_packets=copy.deepcopy(g['imported_owner_review_packets']))
p['current_path_scope']+='; completed Barbados/Sally workshop-name links imported for13 images with unchanged stable IDs/actual parents. Egyptian Palm3 garden context is second from left by owner-confirmed component identity; scene origin and physical specifications remain unverified.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
links=p['current_image_review_links'];links.update(verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=copy.deepcopy(rep['counts']),latest_component_confirmation=rel(out/'imported-approvals.html'),completed_folder_changes=rel(out/'completed-changes.html'))
p['current_missing_picture_lists'].update(required_actions=72,find_capture=71,verify_existing=1,individual_gaps=2,in_situ_gaps=52,series_gaps=18,resolved_this_pass=1,historical_resolved_actions=81,current_resolved_actions=82,new_in_situ_roles_closed_this_refresh=1,reopened_source_gaps=0,explicit_owner_image_role_approvals_added=0,historical_resolved_actions_scope='81 previously resolved action rows; one qualified garden-context association closes a find/capture action.82 currently resolved.')
p['current_guided_image_review'].update(path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),latest_component_confirmation=rel(out/'imported-approvals.html'),component_confirmation_scope='Egyptian Palm3 is second from left; explicit image-role approval not inferred')
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'))
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_188.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']),contains_partial_owner_held_native_work=True)
p['next_catalogue_actions']=['Use BOLDSTONE MASTER exclusively for current sculpture evidence and image reviews.','Import the newly completed Moon and Shellwave three pair-folder renames in the next bounded path refresh; stable IDs and actual parents are unchanged.','Keep Acanthus Sandstone individual-image and Sandstone/Pewter series-image gaps open until an exact current Master source is found or photographed.','Continue52 in situ and18 series gaps individually, retaining owner holds for Wall Circle and the two Dune Ripple patina cases.','Keep Frozen Fish legacy identity deferred; all current Frozen Fish remain70cm high by15cm wide.','Verify physical measurements/material/fitted fixing and unresolved exact platform configurations separately; accepted working estimates remain labelled.']
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for field in ['latest_queued_master_import','latest_context_folder_refresh','latest_draft_media_synchronization','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','latest_commercial_completion','current_guided_image_review','queued_followup_packets','next_catalogue_actions','current_dropbox_source_policy']:d[field]=copy.deepcopy(p[field])
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
for key in ['summary','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','source_platform_records_are_preserved_snapshots','current_listing_population','current_option_count']:assert p[key]==old[key],key
for key,x in links.items():
 if isinstance(x,str)and x.startswith('outputs/'):assert(B/x).is_file(),key
write(H/'prepared-pointer.json',p)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'independent_binding_checks':native['checks'],'sheet_count':28,'formula_count':3390,'native_hyperlinks':v['native_hyperlinks'],'current_options':188,'working_component_identities':112,'required_actions':72,'individual_action_entries':2,'technical_individual_gaps':11,'in_situ_gaps':52,'series_gaps':18,'qualified_in_situ_roles_closed':1,'component_identity_confirmations_imported':1,'explicit_owner_image_role_approvals_added':0,'workshop_image_paths_refreshed':13,'new_physical_verifications':0,'native_or_platform_writes':0,'source_scope':'BOLDSTONE MASTER only','preceding_release':old['publication_receipt']}
write(H/'publication-receipt.json',r);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_WORKSHOP_LINKS_AND_GARDEN_COMPONENT','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']});write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED','publication_receipt':rel(H/'publication-receipt.json'),'next_source_scope':'BOLDSTONE MASTER only'})
print(json.dumps(r,indent=2))
