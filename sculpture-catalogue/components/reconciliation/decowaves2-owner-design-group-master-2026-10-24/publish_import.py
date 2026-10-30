"""Publish the separately confirmed Number2 edge and110 working design groups."""
import copy,hashlib,json,os,sys
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.owner-design-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');rep=read(H/'report-verification.json');v=read(H/'saved-file-verification.json');n=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json');summary=read(H/'import-summary.json');out=Path(rep['output_directory']);old=read(m['pointer']['snapshot']);p=copy.deepcopy(old);oldh=Path(m['master_register']['path']).parent;oldout=Path(read(m['source_report_verification']['snapshot'])['output_directory'])
assert v['status']==n['status']==vis['status']=='PASS'and not v['issues']and not n['issues']
for key,file in [('workbook_sha256','master-workbook.pending'),('register_sha256','canonical-master-register.json'),('audit_sha256','image-coverage-current.json')]:assert v[key]==n[key]==vis[key]==sha(H/file),key
assert rep['register_sha256']==v['register_sha256']and rep['audit_sha256']==v['audit_sha256']
for x in rep['pages']+rep['csv_files']+rep['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256'],x['path']
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
qa=read(H/'independent-qa-reference.json');assert sha(qa['path'])==qa['sha256'];q=read(qa['path']);assert q['status']=='PASS'
assert q['candidate_register_sha256']==v['register_sha256']and q['candidate_workbook_sha256']==v['workbook_sha256']
assert q['checks_passed']==q['checks_total']
for path,digest in q.get('frozen_artifacts',q.get('reviewed_frozen_artifacts',{})).items():assert sha(path)==digest,path
assert q.get('frozen_artifacts',q.get('reviewed_frozen_artifacts',{}))
assert sha(qa['seal_path'])==qa['seal_sha256']
def reroute(x):
 if isinstance(x,list):return[reroute(z)for z in x]
 if isinstance(x,dict):return{k:reroute(z)for k,z in x.items()}
 if isinstance(x,str):
  for src,dst in [(str(oldout),str(out)),(rel(oldout),rel(out)),(str(oldh),str(H)),(rel(oldh),rel(H))]:
   if x.startswith(src+'/'):
    target=dst+x[len(src):];f=Path(target.split('#')[0]);f=f if f.is_absolute()else B/f
    if f.is_file():return target
 return x
for key in ['current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion','current_local_draft_completion']:p[key]=reroute(p[key])
validation={}
for key,file in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:validation[key]=rel(H/file);validation[key+'_sha256']=sha(H/file)
p.update(recorded_utc=now(),status='CURRENT_MASTER188_OPTIONS_OWNER_DECOWAVES2_DESIGN_EQUIVALENCE_AND110_WORKING_GROUPS_VERIFIED',workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),summary=copy.deepcopy(g['summary']),latest_workbook_validation=validation,latest_decowaves2_owner_design_equivalence_import={**summary,**validation,'independent_qa':qa},latest_active_photo_source_review=copy.deepcopy(g['latest_active_photo_source_review']),latest_image_coverage_audit={**g['latest_image_coverage_audit'],**validation,'audit_sha256':v['audit_sha256']})
p['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'),sha256=sha(H/'photo-source-review.json'))
p['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=rel(H/'image-coverage-current.json'),status='SOURCE_PHOTO_COVERAGE_RETAINED_DURING_OWNER_NUMBER2_DESIGN_GROUP_IMPORT')
assert len(g['active_option_ids'])==p['current_option_count']==188 and len(g['options'])==p['retained_option_count']==189
p['current_path_scope']+='; Separate owner-confirmed Decowaves2/Frozen Decowaves2 relationship recovered once from duplicate wYes replies. Allnames/source/DropboxIDs retained;112 component ID rows project to110 working groups. No native folder or file changes.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links'].update(remaining_photograph_brief=rel(out/'remaining-photograph-requests.html'),remaining_photograph_brief_json=rel(out/'remaining-photograph-requests.json'),remaining_photograph_brief_json_sha256=sha(out/'remaining-photograph-requests.json'),verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'),counts=rep['counts'],owner_design_relationship=rel(out/'decowaves2-owner-design-equivalence.html'),working_design_groups=rel(out/'Current_Working_Design_Groups_110.csv'))
p['current_guided_image_review'].update(path=rel(H/'photo-review-queue.json'),sha256=sha(H/'photo-review-queue.json'),terminal_review_command=rel(H/'guided_review.py'),terminal_review_command_sha256=sha(H/'guided_review.py'),owner_progress_path=rel(H/'guided-owner-review-state.json'),owner_progress_snapshot_sha256=sha(H/'guided-owner-review-state.json'),terminal_runtime_verification=rel(H/'native-binding-verification.json'),terminal_runtime_verification_sha256=sha(H/'native-binding-verification.json'))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),new_working_fields_added=0,new_comparator_estimates_added=0,new_standing_policy_fields_added=0,new_physical_measurements_added=0,new_physical_verifications=0,new_physical_field_groups_source_reviewed=0)
p['current_individual_sculpture_list'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list_sha256=sha(out/'Current_Individual_Options_188.csv'),count_summary_sha256=sha(out/'current-count-summary.json'),retained_component_id_records=112,grouped_working_design_identities=110,component_count_scope='112 retained component ID rows project to110 working groups after separate number1 and number2 owner answers; not physical stock or a certified whole-library unique total.')
p['latest_commercial_completion'].update(current_review_sha256=sha(out/'selling-details.html'),current_reference_refresh=p['publication_receipt'])
p['current_native_reference_map']={**old['current_native_reference_map'],'path':rel(H/'current-native-reference-map.json'),'sha256':sha(H/'current-native-reference-map.json')}
p['latest_working_entry_owner_provenance']={**old['latest_working_entry_owner_provenance'],'path':rel(H/'working-entry-owner-provenance-sidecar.json'),'sha256':sha(H/'working-entry-owner-provenance-sidecar.json')}
p['current_authenticated_squarespace_inventory_observation'].update(register=p['register'],register_sha256=p['register_sha256'],review=rel(out/'captured-platform-source-observations.html'))
p['current_primary_navigation_health']['review']=rel(out/'current-primary-navigation-health.html');p['current_primary_navigation_health']['csv']=rel(out/'Current_Primary_Navigation_48.csv')
p['current_working_design_group_projection']={'path':rel(H/'working-design-group-projection.json'),'sha256':sha(H/'working-design-group-projection.json'),'retained_component_identity_record_count':112,'grouped_working_design_identity_count':110,'active_finish_option_count':188,'retained_option_count':189,'owner_equivalence_edges':2,'whole_library_unique_design_count':None,'review':rel(out/'decowaves2-owner-design-equivalence.html'),'groups_csv':rel(out/'Current_Working_Design_Groups_110.csv')}
p['latest_physical_checklist_label_alignment']={'path':rel(H/'physical-checklist-label-alignment.json'),'sha256':sha(H/'physical-checklist-label-alignment.json'),'existing_options':188,'existing_field_groups':752,'existing_water_comparator_only_fields':4,'new_measurements_or_verifications':0}
p['next_catalogue_actions']=['Both Decowaves/Frozen Decowaves number1 and number2 owner answers are now recorded separately. Preserve each individual finish option and its own fields; no mould, cast, stock or exact platform-configuration identity was inferred.','The recovery continuation session owns the outstanding Acanthus One Leaf Left Pewter physical-details question; avoid duplicate prompts. Continue independent source reconciliation with accepted estimates and source field objects retained.','Preserve two unresolved Wall Circle primary-reference warnings,22 missing-context holds, one Dune2Copper Series hold and deferred Frozen Fish identity. Shopify account access and the exact three-file Moonspiral move proposal remain owned by their existing sessions.']
for key in ['current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_listing_population','platform_write_holds','current_structure_discovery_scope','current_wall_sculpture_inclusion_policy','current_individual_photo_capture_policy','current_option_count','retained_option_count','current_global_context_owner_hold']:assert p[key]==old[key],key
updates={};fields=['summary','current_working_design_group_projection','latest_decowaves2_owner_design_equivalence_import','current_primary_navigation_health','current_authenticated_squarespace_inventory_observation','current_option_count','retained_option_count','current_individual_photo_capture_policy','current_local_draft_completion','current_global_context_owner_hold','latest_working_entry_owner_provenance','latest_active_photo_source_review','latest_image_coverage_audit','current_image_review_links','current_missing_picture_lists','current_specification_verification','current_guided_image_review','current_individual_sculpture_list','latest_commercial_completion','queued_followup_packets','next_catalogue_actions','latest_workbook_validation','current_native_reference_map']
fields.append('latest_physical_checklist_label_alignment')
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for field in fields:d[field]=copy.deepcopy(p[field])
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
write(H/'prepared-pointer.json',p)
if '--prepare'in sys.argv:print('ALL_PUBLICATION_GUARDS_PASS_PREPARED_ONLY');raise SystemExit(0)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
target=B/p['workbook'];os.replace(H/'master-workbook.pending',target)
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={**summary,'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':p['recorded_utc'],'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'saved_file_checks':v['checks'],'binding_checks':n['checks'],'sheet_count':v['sheet_count'],'formula_count':v['formula_count'],'native_hyperlinks':v['native_hyperlinks'],'independent_qa':qa,'preceding_release':old['publication_receipt']};write(H/'publication-receipt.json',r)
write(out/'publication-state.json',{'status':'PUBLISHED_OWNER_NUMBER2_DESIGN_EQUIVALENCE','publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256']});write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED','publication_receipt':rel(H/'publication-receipt.json'),'active_options':188,'retained_component_ids':112,'working_design_groups':110})
print(json.dumps(r,indent=2))
