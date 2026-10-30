"""Publish verified empty-folder-history workbook and refresh its canonical controls."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.display-import-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');v=read(H/'saved-file-verification.json');native=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');rep=read(H/'report-verification.json');out=Path(rep['output_directory']);counts=a['counts']
assert v['status']==native['status']==vis['status']=='PASS'and not v['issues']and not native['issues']
for k,p in [('workbook_sha256',H/'master-workbook.pending'),('register_sha256',H/'canonical-master-register.json'),('audit_sha256',H/'image-coverage-current.json')]:assert v[k]==native[k]==vis[k]==sha(p),k
assert rep['register_sha256']==v['register_sha256']and rep['audit_sha256']==v['audit_sha256']
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256']
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
p=read(m['pointer']['snapshot']);old=copy.deepcopy(p);oldout='outputs/four-qualified-display-references-2026-10-23';newout=rel(out)
def reroute(z):
 if isinstance(z,list):return[reroute(x)for x in z]
 if isinstance(z,dict):return{k:reroute(x)for k,x in z.items()}
 if isinstance(z,str)and z.startswith(oldout+'/'):return newout+z[len(oldout):]
 return z
for k in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion']:p[k]=reroute(p[k])
validation={}
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:validation[key]=rel(H/name);validation[key+'_sha256']=sha(H/name)
current={**g['latest_empty_folder_history_import'],**validation,'review':rel(out/'completed-changes.html'),'folder_history':rel(H/'removed-empty-folder-history.json'),'folder_history_sha256':sha(H/'removed-empty-folder-history.json')}
p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_empty_folder_history_import=current,latest_context_folder_refresh=current,latest_draft_media_synchronization={**g['latest_draft_media_synchronization'],**validation},latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']},latest_workbook_validation=copy.deepcopy(validation),imported_reviewer_selection_authorities=copy.deepcopy(g['imported_reviewer_selection_authorities']))
p['current_path_scope']+='; Nine owner-removed empty folder IDs recorded in history and excluded from current folder positions. Two obsolete Dune Ripple folder links now navigate to the surviving family. Photograph records and all option/specification decisions are unchanged.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links'].update(verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=copy.deepcopy(rep['counts']),latest_context_bindings=rel(out/'imported-approvals.html'),current_context_qualifications=rel(out/'current-context-references.html'),specification_evidence_review=rel(out/'specification-evidence-review.html'),completed_folder_changes=rel(out/'completed-changes.html'))
p['current_missing_picture_lists'].update(required_actions=62,find_capture=61,verify_existing=1,individual_gaps=1,in_situ_gaps=44,series_gaps=17,resolved_this_pass=0,historical_resolved_actions=90,current_resolved_actions=90,new_in_situ_roles_closed_this_refresh=0,reopened_source_gaps=0,explicit_owner_image_role_approvals_added=0,reviewer_verified_display_bindings=0,historical_resolved_actions_scope='All90 previously resolved actions retained. Nine empty-folder histories do not close any photograph action.')
p['current_missing_picture_lists'].update(current_action_rows=209,technical_individual_reference_gaps=10,separate_individual_photos_required=0,separate_individual_photographs_required=0,new_image_roles_closed_this_refresh=0)
p['current_guided_image_review'].update(path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),latest_context_bindings=rel(out/'imported-approvals.html'),component_confirmation_scope='Current qualified photograph decisions retained unchanged during the nine-empty-folder history refresh.',active_owner_question=None)
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),source_evidence_review=rel(out/'specification-evidence-review.html'),source_evidence_ledger=rel(H/'specification-evidence-review.json'),source_evidence_ledger_sha256=sha(H/'specification-evidence-review.json'))
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_187.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']),status='ONLY_OWNER_HELD_NATIVE_PACKET_REMAINS')
p['current_native_reference_map']={'path':rel(H/'current-native-reference-map.json'),'sha256':sha(H/'current-native-reference-map.json'),'fresh_surviving_family_parents_verified':6,'current_direct_children_checked':87,'owner_removed_empty_folders_recorded':9,'formerly_current_empty_entries_removed':5,'prior_native_reference_history_retained':True}
p['current_folder_removal_history']={'path':rel(H/'removed-empty-folder-history.json'),'sha256':sha(H/'removed-empty-folder-history.json'),'review':rel(out/'completed-changes.html'),'csv':rel(out/'Removed_Empty_Folders_9.csv'),'empty_folder_ids_recorded':9,'deleted_photographs':0,'image_roles_closed':0}
p['next_catalogue_actions']=['Import verified qualified in-situ source matches from the active review lane, starting with the Rust and Verdigris replacement; keep historical unresolved IDs.','Continue44 current in-situ gaps and17 series gaps within BOLDSTONE MASTER; retain owner-held scopes. The completed17-series review found no new supported series binding.','Locate the exact Acanthus One Leaf Left — Pewter series photograph; solo/detail and Two Leaves references do not close it. Sandstone remains retired.','Keep Wall Circle, Dune patina and Chiswick source holds; retain the deferred Frozen Fish legacy identity and70 ×15cm current faces.','Verify actual measurements, weight, material and fitted fixing for187 active options, retaining estimate labels until verified.']
updates={}
fields=['latest_empty_folder_history_import','current_folder_removal_history','latest_context_folder_refresh','latest_draft_media_synchronization','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','latest_commercial_completion','current_guided_image_review','queued_followup_packets','next_catalogue_actions','current_dropbox_source_policy','latest_workbook_validation','current_native_reference_map','imported_reviewer_selection_authorities']
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for field in fields:d[field]=copy.deepcopy(p[field])
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
for key in ['summary','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','source_platform_records_are_preserved_snapshots','current_listing_population','current_option_count','latest_owner_leaf_curve_context_import','latest_four_qualified_display_import','latest_verified_native_folder_import']:assert p[key]==old[key],key
for key,x in p['current_image_review_links'].items():
 if isinstance(x,str)and x.startswith('outputs/'):assert(B/x).is_file(),key
write(H/'prepared-pointer.json',p)
if '--prepare'in sys.argv:print('ALL_PUBLICATION_GUARDS_PASS_PREPARED_ONLY');raise SystemExit(0)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'independent_binding_checks':native['checks'],'sheet_count':28,'formula_count':3390,'native_hyperlinks':v['native_hyperlinks'],'current_options':187,'retained_option_rows':188,'working_component_identities':112,'required_actions':62,'individual_action_entries':1,'technical_individual_gaps':10,'in_situ_gaps':44,'series_gaps':17,'qualified_in_situ_roles_closed':0,'explicit_owner_image_role_approvals_added':0,'reviewer_verified_display_bindings':0,'current_file_paths_refreshed':0,'actual_file_parent_id_changes':0,'fresh_surviving_parent_metadata_objects':6,'fresh_direct_children_checked':87,'empty_folder_history_entries_added':9,'obsolete_current_folder_links_replaced':2,'current_map_empty_entries_removed':5,'whole_source_images_modified':0,'new_physical_verifications':0,'native_or_platform_writes':0,'source_scope':'BOLDSTONE MASTER only','preceding_release':old['publication_receipt']}
write(H/'publication-receipt.json',r);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_EMPTY_FOLDER_HISTORY','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']});write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED','publication_receipt':rel(H/'publication-receipt.json'),'next_source_scope':'BOLDSTONE MASTER only'})
print(json.dumps(r,indent=2))
