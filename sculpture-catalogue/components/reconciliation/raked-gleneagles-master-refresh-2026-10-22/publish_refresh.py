"""Publish the independently verified local master using immutable input guards."""
import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
 p=Path(p);tmp=p.with_name(p.name+'.raked-glen-tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');g=read(H/'canonical-master-register.json');reports=read(H/'link-report-verification.json');visual=read(H/'visual-verification.json')
assert v['status']=='PASS'and not v['issues']and visual['status']=='PASS'
assert sha(H/'master-workbook.pending')==v['workbook_sha256']and sha(H/'canonical-master-register.json')==v['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+visual['previews']:assert sha(x['path'])==x['sha256']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256']
ptr=read(BASE/'current-master.json');prior=copy.deepcopy(ptr);out=Path(reports['output_directory'])
ptr.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'))
ptr['latest_gleneagles_numbering']=copy.deepcopy(g['latest_gleneagles_numbering']);ptr['latest_raked_spiral_paths']=copy.deepcopy(g['latest_raked_spiral_paths'])
for key in ['latest_gleneagles_numbering','latest_raked_spiral_paths']:
 ptr[key].update(verification=rel(H/'saved-file-verification.json'),verification_sha256=sha(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'))
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification_sha256=sha(H/'saved-file-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'));ptr['latest_image_coverage_audit']=coverage
ptr.setdefault('historical_path_refreshes',[]).append(copy.deepcopy(prior['latest_path_refresh']))
ptr['latest_path_refresh']={'recorded_utc':now(),'scope':'Six Raked Spiral folder renames and Gleneagles numbered identities/flat component folders','source_overlays':[m['raked_overlay'],m['glen_overlay']],'current_state_addendum':m['glen_state_addendum'],'native_link_destinations_updated':v['native_targets_updated'],'new_component_folder_links':16,'verification':rel(H/'saved-file-verification.json'),'specification_changes':0,'photo_role_changes':0,'new_candidate_pngs':4,'root_remote_writes':0}
ptr['current_path_scope']+='; verified Raked Spiral group folder names and owner-approved Gleneagles1/2/3/4 identities with four flat component folders and qualified PNG candidates'
ptr.setdefault('historical_image_review_links',[]).append(copy.deepcopy(prior['current_image_review_links']))
links=copy.deepcopy(prior['current_image_review_links'])
for k,val in list(links.items()):
 if isinstance(val,str)and val.startswith('outputs/'):links[k]=rel(out/Path(val).name)
links.update(verification=rel(H/'link-report-verification.json'),verification_sha256=sha(H/'link-report-verification.json'),counts=reports['counts']);ptr['current_image_review_links']=links
missing=copy.deepcopy(ptr['current_missing_picture_lists'])
for k,val in list(missing.items()):
 if isinstance(val,str)and val.startswith('outputs/'):missing[k]=rel(out/Path(val).name)
missing.update(required_actions=105,find_capture=104,verify_existing=1,individual_gaps=26,in_situ_gaps=61,series_gaps=18)
ptr['current_missing_picture_lists']=missing
updates={}
for k in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[k]['path']);d=read(p);d.update(current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],updated_utc=now(),latest_gleneagles_numbering=copy.deepcopy(ptr['latest_gleneagles_numbering']),latest_raked_spiral_paths=copy.deepcopy(ptr['latest_raked_spiral_paths']),latest_image_coverage_audit=copy.deepcopy(coverage),current_image_review_links=copy.deepcopy(links))
 if k=='component_checkpoint':d['current_master_validation']={'path':rel(H/'saved-file-verification.json'),'sha256':sha(H/'saved-file-verification.json')}
 updates[p]=d
write(H/'export-receipt.json',{'status':'PASS_READY_TO_PUBLISH','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':v['workbook_sha256'],'register':ptr['register'],'register_sha256':v['register_sha256'],'sheets':22,'native_hyperlinks':11233,'formulas':2739,'required_picture_actions':105,'individual_gaps':26})
for x in m.values():assert sha(x['path'])==x['sha256']
target=BASE/ptr['workbook'];os.replace(H/'master-workbook.pending',target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)
assert read(BASE/'current-master.json')==ptr and sha(target)==ptr['workbook_sha256']
for p,d in updates.items():assert read(p)==d
for k,x in m.items():
 if k not in ['master_workbook','master_pointer','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256']
for k in ['latest_listing_resolution','latest_listing_reconciliation','latest_image_identity_resolution','latest_moon_and_shellwave_numbering','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds']:
 assert ptr.get(k)==prior.get(k),'Unrelated pointer field changed '+k
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':v['workbook_sha256'],'register':str(H/'canonical-master-register.json'),'register_sha256':v['register_sha256'],'audit_sha256':v['audit_sha256'],'verification':rel(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'checks':v['checks'],'old_sheets':21,'new_sheet':'Gleneagles Folders','gleneagles_names_updated':4,'gleneagles_candidate_pngs_linked':4,'individual_gaps_retained':26,'required_picture_actions':105,'native_link_destinations_updated':v['native_targets_updated'],'new_binding_links':16,'specification_changes':0,'new_catalogue_options':0,'root_platform_or_Dropbox_writes':0,'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},'current_image_review_links':links,'prior_inconsistent_picture_counter_metadata_corrected':{'find_capture':[prior['current_missing_picture_lists']['find_capture'],104],'in_situ_gaps':[prior['current_missing_picture_lists']['in_situ_gaps'],61],'series_gaps':[prior['current_missing_picture_lists']['series_gaps'],18]}}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_LINK_REPORTS','publication_receipt':str(H/'publication-receipt.json'),'master_pointer':str(BASE/'current-master.json'),'workbook_sha256':v['workbook_sha256'],'register_sha256':v['register_sha256']})
write(H/'completion.json',{'status':'COMPLETE_VERIFIED_RAKED_GLENEAGLES_REFRESH','recorded_utc':now(),'publication_receipt':rel(H/'publication-receipt.json'),'qualified_photo_coverage_unchanged':True,'root_remote_writes':0})
state=read(H/'WORK_STATE.json');state.update(status='COMPLETE_PUBLISHED_AND_READ_BACK',publication_receipt=rel(H/'publication-receipt.json'));write(H/'WORK_STATE.json',state)
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256']}))
