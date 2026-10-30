"""Publish the validated scoped workbook and read back every canonical control."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.border-import-tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');v=read(H/'saved-file-verification.json');n=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
assert v['status']==n['status']==vis['status']=='PASS'and not v['issues']and not n['issues']
for k,path in [('workbook_sha256',H/'master-workbook.pending'),('register_sha256',H/'canonical-master-register.json'),('audit_sha256',H/'image-coverage-current.json')]:assert v[k]==n[k]==vis[k]==sha(path),k
assert rep['register_sha256']==v['register_sha256']and rep['audit_sha256']==v['audit_sha256']
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256'],x['path']
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
old=read(m['pointer']['snapshot']);p=copy.deepcopy(old);oldh=Path(m['master_register']['path']).parent;oldout=Path(read(m['source_report_verification']['snapshot'])['output_directory'])
def reroute(x):
 if isinstance(x,list):return[reroute(y)for y in x]
 if isinstance(x,dict):return{k:reroute(y)for k,y in x.items()}
 if isinstance(x,str):
  for src,dest in [(str(oldout),str(out)),(rel(oldout),rel(out)),(str(oldh),str(H)),(rel(oldh),rel(H))]:
   if x.startswith(src+'/'):return dest+x[len(src):]
 return x
for k in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion']:p[k]=reroute(p[k])
validation={}
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:validation[key]=rel(H/name);validation[key+'_sha256']=sha(H/name)
summary={**g['latest_bordered_moonphase_reference_import'],**validation,'review':rel(out/'bordered-moonphase-changes.html'),'path_history':rel(H/'path-change-history.json'),'path_history_sha256':sha(H/'path-change-history.json')}
p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_bordered_moonphase_reference_import=summary,latest_context_folder_refresh={**g['latest_combined_reference_refresh'],**validation},latest_combined_reference_refresh={**g['latest_combined_reference_refresh'],**validation},latest_additional_display_import=copy.deepcopy(g['latest_additional_display_import']),latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']},latest_workbook_validation=validation,latest_draft_media_synchronization={**g['latest_draft_media_synchronization'],**validation},imported_reviewer_selection_authorities=copy.deepcopy(g['imported_reviewer_selection_authorities']))
p['current_path_scope']+='; Completed bordered Moonphase pair-folder rename and original008 individual-folder move projected by stable IDs. Original008 is additional only. Whole001 pair also supplies two qualified brick-wall display references with origin and physical specifications unverified.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links'].update(remaining_photograph_brief=rel(out/'remaining-photograph-requests.html'),verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=copy.deepcopy(rep['counts']),completed_bordered_moonphase_changes=rel(out/'bordered-moonphase-changes.html'),latest_context_bindings=rel(out/'imported-approvals.html'),current_context_qualifications=rel(out/'current-context-references.html'),active_in_situ_requests=rel(out/'active-in-situ-photo-requests.html'))
p['current_missing_picture_lists'].update(required_actions=40,find_capture=39,verify_existing=1,in_situ_gaps=22,series_gaps=17,resolved_this_pass=4,historical_resolved_actions=108,current_resolved_actions=112,new_image_roles_closed_this_refresh=4,new_in_situ_roles_closed_this_refresh=4,reviewer_verified_display_bindings=4,explicit_owner_image_role_approvals_added=0,active_in_situ_source_requests=14,owner_held_in_situ_cases=8,current_reviewed_option_records=4,historical_resolved_actions_scope='108 prior resolved actions retained. Four qualified whole-source display bindings close four current context tasks. Seventeen series requests and eight held context cases retain their qualifications.')
p['current_guided_image_review'].update(path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),component_confirmation_scope='Four qualified display bindings added, including two bordered Moonphase panels, a workshop/tabletop panel and a garden-ground panel. Existing primaries, all physical fields,17 series requests and8 held context cases preserved.',active_in_situ_source_requests=14,series_source_requests=17,held_in_situ_cases=8)
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),source_evidence_ledger=rel(H/'specification-evidence-review.json'),source_evidence_ledger_sha256=sha(H/'specification-evidence-review.json'))
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_187.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']),status='VERIFIED_DECO_FOLLOWUP_QUEUED_AND_OWNER_HELD_NATIVE_PACKET_RETAINED')
p['current_native_reference_map']={'path':rel(H/'current-native-reference-map.json'),'sha256':sha(H/'current-native-reference-map.json'),'fresh_object_scope':15,'complete_current_parent_lists':2,'same_id_file_path_changes':8,'actual_file_parent_changes':1,'prior_native_reference_history_retained':True,'owner_removed_empty_folder_history_preserved':True}
p['next_catalogue_actions']=['Import the separately queued completed Deco004 same-ID folder/file change; preserve002/003 identity holds.','Continue14 active context-source requests and17 series-source requests in BOLDSTONE MASTER; preserve8 held context cases.','Prioritise the exact Acanthus One Leaf Left — Pewter display and series source. Existing solo/detail and Two Leaves images do not close those requests.','Import independently verified new photograph packets when sealed; do not infer individual approval, authentic installation or physical specifications.','Verify actual measurements, weight, material and fitted fixing for187 active options, retaining accepted estimates until measured.','Retain the deferred Frozen Fish legacy identity; all current faces remain70 ×15cm. Sandstone One Leaf remains retired.']
fields=['latest_combined_reference_refresh','latest_additional_display_import','latest_bordered_moonphase_reference_import','latest_context_folder_refresh','latest_draft_media_synchronization','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','latest_commercial_completion','current_guided_image_review','queued_followup_packets','next_catalogue_actions','current_dropbox_source_policy','latest_workbook_validation','current_native_reference_map','imported_reviewer_selection_authorities'];updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for field in fields:d[field]=copy.deepcopy(p[field])
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
for key in ['summary','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','source_platform_records_are_preserved_snapshots','current_listing_population','current_option_count','latest_owner_leaf_curve_context_import','latest_four_qualified_display_import','latest_empty_folder_history_import','current_folder_removal_history']:assert p[key]==old[key],key
for group in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_individual_sculpture_list']:
 for key,x in p[group].items():
  if group=='current_individual_sculpture_list'and key=='publication_receipt':
   assert x==rel(H/'publication-receipt.json')
   continue
  if isinstance(x,str)and x.startswith(('outputs/','components/')):assert(B/x.split('#')[0]).is_file(),(group,key,x)
write(H/'prepared-pointer.json',p)
if '--prepare'in sys.argv:print('ALL_PUBLICATION_GUARDS_PASS_PREPARED_ONLY');raise SystemExit(0)
for k,x in m.items():assert sha(x['path'])==x['sha256'],k
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'independent_binding_checks':n['checks'],'sheet_count':28,'formula_count':3390,'native_hyperlinks':v['native_hyperlinks'],'current_options':187,'retained_option_rows':188,'working_component_identities':112,'required_actions':40,'in_situ_gaps':22,'active_in_situ_source_requests':14,'held_in_situ_cases':8,'series_gaps':17,'qualified_display_roles_closed':4,'primary_images_replaced':0,'additional_individual_reference':1,'current_file_paths_refreshed':8,'actual_file_parent_id_changes':1,'new_physical_verifications':0,'whole_source_images_modified':0,'native_or_platform_writes':0,'source_scope':'BOLDSTONE MASTER only','preceding_release':old['publication_receipt']}
write(H/'publication-receipt.json',r);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_BORDERED_MOONPHASE_REFERENCES','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']});write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED','publication_receipt':rel(H/'publication-receipt.json'),'next_source_scope':'BOLDSTONE MASTER only'});print(json.dumps(r,indent=2))
