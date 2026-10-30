"""Publish current Fingerprint evidence and clearly unresolved historical aliases."""
import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
 p=Path(p);tmp=p.with_name(p.name+'.fp-current-tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');g=read(H/'canonical-master-register.json');reports=read(H/'link-report-verification.json');visual=read(H/'visual-verification.json')
assert v['status']=='PASS'and not v['issues']and visual['status']=='PASS'and reports['status']=='PASS_CURRENT_FP_LINK_REPORTS'
assert read(H/'html-local-link-verification.json')['status']=='PASS'
assert sha(H/'master-workbook.pending')==v['workbook_sha256']and sha(H/'canonical-master-register.json')==v['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in reports['pages']+reports['csv_files']+reports['image_files']+visual['previews']:assert sha(x['path'])==x['sha256']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256']
proof=read(H/'standalone-original-native-verification.json');assert proof['status']=='PASS'and len(proof['originals'])==6
for x in proof['originals']:assert sha(x['local_path'])==x['sha256']
ptr=read(BASE/'current-master.json');prior=copy.deepcopy(ptr);out=Path(reports['output_directory']);scope=g['latest_fingerprint_numbered_reconciliation']
ptr.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'))
summary={k:copy.deepcopy(scope[k])for k in ['status','recorded_utc','placement_overlay','placement_verification','root_independent_native_readback','original_image_verification','numbered_folder_finish_count','current_numbered_design_labels','newly_uploaded_photos','new_canonical_components_or_options','legacy_specification_transfers','historical_canonical_individual_gaps_retained','current_native_tree','counts_scope']}
summary.update(current_inventory=rel(H/'numbered-folder-inventory.json'),current_inventory_sha256=sha(H/'numbered-folder-inventory.json'),legacy_crosswalk_review=rel(H/'legacy-crosswalk-review.json'),legacy_crosswalk_review_sha256=sha(H/'legacy-crosswalk-review.json'),standalone_native_original_proof=rel(H/'standalone-original-native-verification.json'),verification=rel(H/'saved-file-verification.json'),verification_sha256=sha(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'),workbook_sheets=['Fingerprint Current','Fingerprint Photos'])
ptr['latest_fingerprint_numbered_reconciliation']=summary
ptr['latest_fingerprint_component_paths']=copy.deepcopy(g['latest_fingerprint_component_paths'])
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification_sha256=summary['verification_sha256'],visual_verification_sha256=summary['visual_verification_sha256']);ptr['latest_image_coverage_audit']=coverage
ptr.setdefault('historical_path_refreshes',[]).append(copy.deepcopy(ptr['latest_path_refresh']))
ptr['latest_path_refresh']={'recorded_utc':now(),'scope':'Current flat Fingerprint numbered folders and matched original photograph placement; historical Left/Right aliases unresolved','placement_overlay':m['placement_overlay'],'current_folder_moves':14,'new_group_folders':6,'new_original_photos':26,'new_original_bytes':8888149,'native_link_destinations_updated':v['native_targets_updated'],'new_native_links':82,'new_canonical_components_or_options':0,'legacy_specification_transfers':0,'root_remote_writes':0,'verification':summary['verification']}
ptr['current_path_scope']+='; current flat Fingerprint numbered folders and26new arrangement photographs verified; historical Left/Right hierarchy superseded and retained as archived source; numbered design/version alias unresolved'
links=copy.deepcopy(ptr['current_image_review_links']);links.update(fingerprint_current=rel(out/'index.html'),fingerprint_all26_photographs=rel(out/'photographs.html'),fingerprint_legacy_alias_review=rel(out/'legacy-alias-review.html'),fingerprint_link_verification=rel(H/'link-report-verification.json'),fingerprint_link_verification_sha256=sha(H/'link-report-verification.json'));ptr['current_image_review_links']=links
updates={}
for k in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[k]['path']);d=read(p);d.update(current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],updated_utc=now(),latest_fingerprint_numbered_reconciliation=copy.deepcopy(summary),latest_fingerprint_component_paths=copy.deepcopy(ptr['latest_fingerprint_component_paths']),latest_image_coverage_audit=copy.deepcopy(coverage),current_image_review_links=copy.deepcopy(links))
 if k=='component_checkpoint':d['current_master_validation']={'path':summary['verification'],'sha256':summary['verification_sha256']}
 updates[p]=d
write(H/'export-receipt.json',{'status':'PASS_READY_TO_PUBLISH','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':v['workbook_sha256'],'register':ptr['register'],'register_sha256':v['register_sha256'],'sheets':24,'native_hyperlinks':11315,'formulas':2746,'current_numbered_folder_finish_records':6,'original_photographs_mapped':26,'legacy_aliases_promoted':0})
for x in m.values():assert sha(x['path'])==x['sha256']
target=BASE/ptr['workbook'];os.replace(H/'master-workbook.pending',target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)
assert read(BASE/'current-master.json')==ptr and sha(target)==ptr['workbook_sha256']
for p,d in updates.items():assert read(p)==d
for k,x in m.items():
 if k not in ['master_workbook','master_pointer','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256']
for k in ['latest_listing_resolution','latest_listing_reconciliation','latest_image_identity_resolution','latest_moon_and_shellwave_numbering','latest_gleneagles_numbering','latest_raked_spiral_paths','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','summary','current_missing_picture_lists']:
 assert ptr.get(k)==prior.get(k),'Unrelated pointer field changed '+k
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK_LEGACY_ALIAS_PENDING','recorded_utc':now(),'workbook':str(target),'workbook_sha256':v['workbook_sha256'],'register':str(H/'canonical-master-register.json'),'register_sha256':v['register_sha256'],'audit_sha256':v['audit_sha256'],'verification':summary['verification'],'visual_verification':summary['visual_verification'],'checks':v['checks'],'old_sheets':22,'new_sheets':['Fingerprint Current','Fingerprint Photos'],'current_numbered_folder_finish_records':6,'current_standalone_original_JPEGs':6,'matched_originals':26,'full_arrangement_originals':22,'detail_partial_originals':4,'native_link_destinations_updated':v['native_targets_updated'],'new_native_links':82,'canonical_options':184,'identified_component_identities':111,'new_canonical_options':0,'legacy_aliases_promoted':0,'legacy_specification_transfers':0,'historical_canonical_photo_counts_preserved':True,'root_platform_or_Dropbox_writes':0,'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},'current_fingerprint_review_links':{k:x for k,x in links.items()if k.startswith('fingerprint_')},'pending_owner_fact':'Are current2/3 revised versions of historical Left/Right, or separate designs?'}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_FP_EVIDENCE_LEGACY_ALIAS_PENDING','publication_receipt':str(H/'publication-receipt.json'),'master_pointer':str(BASE/'current-master.json'),'workbook_sha256':v['workbook_sha256'],'register_sha256':v['register_sha256']})
write(H/'completion.json',{'status':'VERIFIED_CURRENT_FOLDER_PHOTO_MAPPING_PUBLISHED','recorded_utc':now(),'publication_receipt':rel(H/'publication-receipt.json'),'legacy_alias_owner_fact_pending':True,'legacy_specification_transfer':0,'root_remote_writes':0})
state=read(H/'WORK_STATE.json');state.update(status='PUBLISHED_CURRENT_EVIDENCE_LEGACY_ALIAS_PENDING',publication_receipt=rel(H/'publication-receipt.json'));write(H/'WORK_STATE.json',state)
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256']}))
