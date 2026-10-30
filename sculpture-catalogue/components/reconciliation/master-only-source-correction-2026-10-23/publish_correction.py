"""Publish one corrected workbook and current controls with compare-and-swap guards."""
import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.master-only-tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');v=read(H/'saved-file-verification.json');n=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');rep=read(H/'report-verification.json');out=Path(rep['output_directory'])
assert v['status']==n['status']==vis['status']=='PASS'and not v['issues']and not n['issues']
for key,path in [('workbook_sha256',H/'master-workbook.pending'),('register_sha256',H/'canonical-master-register.json'),('audit_sha256',H/'image-coverage-current.json')]:assert v[key]==n[key]==vis[key]==sha(path),key
assert rep['register_sha256']==v['register_sha256']and rep['audit_sha256']==v['audit_sha256']
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256']
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
p=read(m['pointer']['snapshot']);prior=copy.deepcopy(p);oldout='outputs/in-situ-folder-refresh-and-context-review-2026-10-23';newout=rel(out)
def reroute(z):
 if isinstance(z,list):return[reroute(x)for x in z]
 if isinstance(z,dict):return{k:reroute(x)for k,x in z.items()}
 if isinstance(z,str)and z.startswith(oldout+'/'):return newout+z[len(oldout):]
 return z
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion']:p[key]=reroute(p[key])
validation={'verification':rel(H/'saved-file-verification.json'),'verification_sha256':sha(H/'saved-file-verification.json'),'native_binding_verification':rel(H/'native-binding-verification.json'),'native_binding_verification_sha256':sha(H/'native-binding-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'visual_verification_sha256':sha(H/'visual-verification.json')}
p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),summary=copy.deepcopy(g['summary']),current_dropbox_source_policy=copy.deepcopy(g['current_dropbox_source_policy']),latest_master_only_source_correction={**g['latest_master_only_source_correction'],**validation,'review':rel(out/'source-scope-correction.html')},latest_context_folder_refresh={**g['latest_context_folder_refresh'],**validation},latest_draft_media_synchronization={**g['latest_draft_media_synchronization'],**validation},latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']})
p['current_path_scope']+='; latest owner restriction: current source evidence exclusively BOLDSTONE MASTER. Former Sandstone detail/workshop references are unavailable in the checked Master folder; their fallback links are excluded and two series-photo gaps reopened.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(prior['current_image_review_links']))
links=p['current_image_review_links'];links.update(verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=copy.deepcopy(rep['counts']),master_only_source_correction=rel(out/'source-scope-correction.html'))
missing=p['current_missing_picture_lists'];missing.update(required_actions=73,find_capture=72,verify_existing=1,individual_gaps=2,in_situ_gaps=53,series_gaps=18,resolved_this_pass=0,historical_resolved_actions=83,current_resolved_actions=81,new_in_situ_roles_closed_this_refresh=0,reopened_source_gaps=2,historical_resolved_actions_scope='83 previously resolved action rows; two reopened because a current Master series image is unavailable.81 remain resolved.')
p['current_guided_image_review'].update(status='MASTER_ONLY_ACANTHUS_IMAGE_REQUIRED',path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),guided_review_page=rel(out/'source-scope-correction.html'),backup_image_choice_superseded=True,source_root='/BOLDSTONE MASTER',deferred_families=['Wall Circle'],deferred_option_ids=['BSI-9299D69FEF08','BSI-AF88EAA8EBC0'])
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'))
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],summary=copy.deepcopy(g['summary']),current_option_list_sha256=sha(out/'Current_Individual_Options_188.csv'),count_summary_sha256=sha(out/'current-count-summary.json'))
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']),contains_partial_owner_held_native_work=True)
p['next_catalogue_actions']=['Use BOLDSTONE MASTER exclusively for current sculpture image searches, references and reviews.','Find or take the exact Acanthus One Leaf Left Sandstone individual image in Master; the previous fallback-image choice is superseded.','Find current Master series images for Acanthus One Leaf Left Sandstone and Pewter; existing owner-confirmed identities remain recorded.','Continue53 in situ and18 series gaps while retaining owner deferrals for Wall Circle and the two Dune Ripple patina cases.','Keep Frozen Fish legacy identity deferred and all current Frozen Fish70cm high by15cm wide.','Verify actual object-specific measurements, material and fitted fixing separately; accepted estimates remain labelled.']
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for field in ['latest_context_folder_refresh','latest_draft_media_synchronization','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','latest_commercial_completion','current_guided_image_review','queued_followup_packets','next_catalogue_actions','current_dropbox_source_policy','latest_master_only_source_correction']:d[field]=copy.deepcopy(p[field])
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
for key in ['wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','source_platform_records_are_preserved_snapshots','current_listing_population','current_option_count']:assert p[key]==prior[key],key
for key,x in links.items():
 if isinstance(x,str)and x.startswith('outputs/'):assert(B/x).is_file(),key
write(H/'prepared-pointer.json',p)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
dest=B/p['workbook'];os.replace(H/'master-workbook.pending',dest)
for path,d in updates.items():write(path,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(dest)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for path,d in updates.items():assert read(path)==d and d['current_master_catalogue']==p
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(dest),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(path):sha(path)for path in updates},'saved_file_checks':v['checks'],'independent_binding_checks':n['checks'],'sheet_count':28,'formula_count':3390,'native_hyperlinks':v['native_hyperlinks'],'current_options':188,'working_component_identities':112,'required_actions':73,'individual_action_entries':2,'technical_individual_gaps':11,'in_situ_gaps':53,'series_gaps':18,'reopened_series_source_gaps':2,'new_physical_verifications':0,'native_or_platform_writes':0,'source_scope':'BOLDSTONE MASTER only','preceding_release':prior['publication_receipt']}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_MASTER_ONLY_SOURCE_SCOPE','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']});write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED_MASTER_ONLY','publication_receipt':rel(H/'publication-receipt.json'),'former_backup_image_question':'SUPERSEDED'})
print(json.dumps(receipt,indent=2))
