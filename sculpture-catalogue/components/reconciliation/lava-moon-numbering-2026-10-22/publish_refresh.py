"""Publish the verified Lava Moon names and current native references."""
import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
 p=Path(p);tmp=p.with_name(p.name+'.lava-tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');g=read(H/'canonical-master-register.json');reports=read(H/'link-report-verification.json');visual=read(H/'visual-verification.json')
assert v['status']=='PASS'and not v['issues']and visual['status']=='PASS'and reports['status']=='PASS_OWNER_CORRECTION_REPORTS'
assert sha(H/'master-workbook.pending')==v['workbook_sha256']and sha(H/'canonical-master-register.json')==v['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+visual['previews']:assert sha(x['path'])==x['sha256']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256']
ptr=read(BASE/'current-master.json');prior=copy.deepcopy(ptr);out=Path(reports['output_directory']);scope=copy.deepcopy(g['latest_lava_moon_numbering'])
scope.update(verification=rel(H/'saved-file-verification.json'),verification_sha256=sha(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'),workbook_sheet='Lava Moon Folders')
ptr.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_lava_moon_numbering=scope)
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification_sha256=scope['verification_sha256'],visual_verification_sha256=scope['visual_verification_sha256']);ptr['latest_image_coverage_audit']=coverage
ptr.setdefault('historical_path_refreshes',[]).append(copy.deepcopy(prior['latest_path_refresh']));ptr['latest_path_refresh']={'recorded_utc':now(),'scope':'Owner-confirmed Lava Moon numbering/current folders and detail001 actual parent','owner_overlay':m['owner_overlay'],'native_link_destinations_updated':v['native_targets_updated'],'new_candidate_links':12,'six_option_names_updated':True,'specification_changes':0,'new_canonical_options':0,'photo_role_changes':0,'new_white_candidate_PNGs':3,'verification':scope['verification'],'root_remote_writes':0}
ptr['current_path_scope']+='; owner-confirmed Lava Moon1Left/2Centre/3Right, six existing finish options and current flat White folders; detail001 actual parent rebased; three White PNG candidates qualified'
ptr.setdefault('historical_image_review_links',[]).append(copy.deepcopy(prior['current_image_review_links']));links=copy.deepcopy(prior['current_image_review_links'])
for k in ['all_links','individual_image_gaps','missing_in_situ_images','missing_series_images','existing_images_to_check','resolved_image_roles']:
 if k in links:links[k]=rel(out/Path(links[k]).name)
links.update(verification=rel(H/'link-report-verification.json'),verification_sha256=sha(H/'link-report-verification.json'),counts=reports['counts']);ptr['current_image_review_links']=links
missing=copy.deepcopy(ptr['current_missing_picture_lists'])
for k,x in list(missing.items()):
 if isinstance(x,str)and x.startswith('outputs/'):missing[k]=rel(out/Path(x).name)
ptr['current_missing_picture_lists']=missing
updates={}
for k in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[k]['path']);d=read(p);d.update(current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],updated_utc=now(),latest_lava_moon_numbering=copy.deepcopy(scope),latest_image_coverage_audit=copy.deepcopy(coverage),current_image_review_links=copy.deepcopy(links))
 if k=='component_checkpoint':d['current_master_validation']={'path':scope['verification'],'sha256':scope['verification_sha256']}
 updates[p]=d
write(H/'export-receipt.json',{'status':'PASS_READY_TO_PUBLISH','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':v['workbook_sha256'],'register':ptr['register'],'register_sha256':v['register_sha256'],'sheets':25,'native_hyperlinks':11327,'formulas':2754,'names_updated':6,'new_options':0,'photo_role_changes':0})
for x in m.values():assert sha(x['path'])==x['sha256']
target=BASE/ptr['workbook'];os.replace(H/'master-workbook.pending',target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)
assert read(BASE/'current-master.json')==ptr and sha(target)==ptr['workbook_sha256']
for p,d in updates.items():assert read(p)==d
for k,x in m.items():
 if k not in ['master_workbook','master_pointer','review_progress','component_checkpoint','root_checkpoint']:assert sha(x['path'])==x['sha256']
for k in ['latest_listing_resolution','latest_listing_reconciliation','latest_image_identity_resolution','latest_moon_and_shellwave_numbering','latest_gleneagles_numbering','latest_raked_spiral_paths','latest_fingerprint_numbered_reconciliation','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds','summary']:assert ptr.get(k)==prior.get(k),'Unrelated pointer field changed '+k
for k,x in prior['current_image_review_links'].items():
 if k.startswith('fingerprint_'):
  assert links[k]==x
  if not k.endswith('_sha256'):assert(BASE/x).is_file()
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':v['workbook_sha256'],'register':str(H/'canonical-master-register.json'),'register_sha256':v['register_sha256'],'audit_sha256':v['audit_sha256'],'verification':scope['verification'],'visual_verification':scope['visual_verification'],'checks':v['checks'],'old_sheets':24,'new_sheet':'Lava Moon Folders','six_option_names_updated':True,'three_component_names_updated':True,'new_candidate_links':12,'native_link_destinations_updated':v['native_targets_updated'],'specification_changes':0,'photo_role_changes':0,'new_canonical_options':0,'individual_gaps':26,'in_situ_gaps':61,'series_gaps':18,'lava_individual_gaps_retained':6,'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},'root_platform_or_Dropbox_writes':0}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_LAVA_NAMES_AND_LINK_REPORTS','publication_receipt':str(H/'publication-receipt.json'),'workbook_sha256':v['workbook_sha256'],'register_sha256':v['register_sha256']})
state=read(H/'WORK_STATE.json');state.update(status='COMPLETE_PUBLISHED_AND_READ_BACK',publication_receipt=rel(H/'publication-receipt.json'));write(H/'WORK_STATE.json',state)
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','current_master_pointer_sha256']}))
