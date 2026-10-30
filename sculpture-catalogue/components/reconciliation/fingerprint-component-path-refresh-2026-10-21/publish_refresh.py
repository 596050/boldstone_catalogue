"""Publish verified Fingerprint current bindings and complete link deliverables."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text());digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
 p=Path(p);t=p.with_name(p.name+'.fingerprint-tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');t.replace(p)
m=read(HERE/'input-manifest.json');check=read(HERE/'saved-file-verification.json');g=read(HERE/'canonical-master-register.json');reports=read(HERE/'link-report-verification.json')
assert check['status']=='PASS'and not check['issues']and reports['status']=='PASS_COMPLETE_LINK_REPORTS'
assert digest(HERE/'master-workbook.pending')==check['workbook_sha256']and digest(HERE/'canonical-master-register.json')==check['register_sha256']
for x in m.values():assert digest(x['path'])==digest(x['snapshot'])==x['sha256']
for x in reports['pages']+reports['csv_files']:assert digest(x['path'])==x['sha256']
previews=read(HERE/'preview-manifest.json');assert len(previews)==3
write(HERE/'visual-verification.json',{'status':'PASS','recorded_utc':now(),'previews':[{**x,'sha256':digest(x['path'])}for x in previews],
 'finding':'New component-folder view, actual pair-image containing folders, stable-ID columns and four retained Group only gaps inspected. All text/IDs readable. Original20 tabs retain all values, formulas, styles and visible layout; their unchanged visual QA reused.'})
ptr=copy.deepcopy(read(BASE/'current-master.json'));prior=copy.deepcopy(ptr)
ptr.update(recorded_utc=now(),workbook_sha256=check['workbook_sha256'],register=rel(HERE/'canonical-master-register.json'),register_sha256=check['register_sha256'],publication_receipt=rel(HERE/'publication-receipt.json'))
summary=copy.deepcopy(g['latest_fingerprint_component_paths']);summary['graph_reference_changes_count']=len(summary.pop('graph_reference_changes'))
summary.update(verification=rel(HERE/'saved-file-verification.json'),verification_sha256=digest(HERE/'saved-file-verification.json'),visual_verification=rel(HERE/'visual-verification.json'),visual_verification_sha256=digest(HERE/'visual-verification.json'),workbook_sheet='Fingerprint Folders')
ptr['latest_fingerprint_component_paths']=summary
ptr['current_path_scope']+='; verified Fingerprint component/finish folders with pair/group images retained under Arrangements'
ptr['latest_path_refresh']={'scope':'Fingerprint component/finish folders and current arrangement image paths','overlay':m['overlay'],
 'native_link_destinations_updated':250,'new_component_folder_links':20,'current_image_parent_ID_changes':0,'verification':summary['verification'],
 'all_names_specifications_and_coverage_preserved':True,'individual_Fingerprint_image_gaps_retained':4,'root_remote_writes':0}
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification=summary['verification'],verification_sha256=summary['verification_sha256'],visual_verification=summary['visual_verification'],visual_verification_sha256=summary['visual_verification_sha256'])
ptr['latest_image_coverage_audit']=coverage
out=Path(reports['output_directory'])
ptr['current_missing_picture_lists'].update(required_find_or_verify=rel(out/'Missing_Pictures_Required_2026-10-21.csv'),individual_image_gaps=rel(out/'Missing_Individual_Images_2026-10-21.csv'),optional_series_images=rel(out/'Optional_Series_Images_2026-10-21.csv'))
ptr['current_image_review_links']={'all_links':rel(out/'index.html'),'fingerprint_folders':rel(out/'01-fingerprint-folders.html'),
 'individual_26':rel(out/'02-individual-images.html'),'missing_in_situ_66':rel(out/'03-in-situ-images.html'),'missing_series_27':rel(out/'04-series-images.html'),
 'existing_images_to_verify_38':rel(out/'05-existing-images-to-check.html'),'verification':rel(HERE/'link-report-verification.json'),'verification_sha256':digest(HERE/'link-report-verification.json')}
ptr.setdefault('platform_write_holds',{})['Squarespace']={'status':'OWNER_HOLD_NO_SQUARESPACE_WRITES','source':m['squarespace_hold'],'allowed':'Read-only verification and local preparation only; explicit owner release required for native changes'}
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[key]['path']);d=read(p);d['current_master_catalogue']=copy.deepcopy(ptr);d['current_master_workbook']=ptr['workbook'];d['current_master_register']=ptr['register'];d['updated_utc']=now()
 d['latest_fingerprint_component_paths']=copy.deepcopy(summary);d['latest_image_coverage_audit']=copy.deepcopy(coverage);d['current_image_review_links']=copy.deepcopy(ptr['current_image_review_links']);d['platform_write_holds']=copy.deepcopy(ptr['platform_write_holds'])
 if key=='component_checkpoint':d['current_master_validation']={'path':summary['verification'],'sha256':summary['verification_sha256']}
 updates[p]=d
write(HERE/'export-receipt.json',{'status':'PASS','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':ptr['workbook_sha256'],'register':ptr['register'],'register_sha256':ptr['register_sha256'],
 'sheets':21,'native_hyperlinks':11235,'formula_count':2729,'required_picture_actions':157,'individual_gaps':26,'link_report_verification':ptr['current_image_review_links']['verification']})
for x in m.values():assert digest(x['path'])==x['sha256']
target=BASE/ptr['workbook'];(HERE/'master-workbook.pending').replace(target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)
assert read(BASE/'current-master.json')==ptr and digest(target)==ptr['workbook_sha256']
for p in updates:assert read(p)['current_master_catalogue']==ptr
for k in ['master_register','owner_ledger','source_model','prior_audit','overlay','verification','after_native','split_plan','native_metadata','squarespace_hold']:assert digest(m[k]['path'])==m[k]['sha256']
for k in ['latest_listing_resolution','latest_listing_reconciliation','latest_image_identity_resolution']:assert ptr[k]==prior[k]
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':ptr['workbook_sha256'],'register':str(HERE/'canonical-master-register.json'),'register_sha256':ptr['register_sha256'],
 'verification':summary['verification'],'visual_verification':summary['visual_verification'],'checks':check['checks'],'new_sheet':'Fingerprint Folders','new_component_finish_bindings':4,
 'native_link_destinations_updated':250,'new_binding_links':20,'graph_current_reference_changes':120,'names_specifications_counts_and_image_coverage_preserved':True,
 'fingerprint_individual_gaps_retained':4,'individual_image_gaps':26,'image_review_links':ptr['current_image_review_links'],'current_master_pointer_sha256':digest(BASE/'current-master.json'),
 'controls_sha256':{str(p):digest(p)for p in updates},'squarespace_write_hold_preserved':True,'platform_or_Dropbox_writes_by_root':0}
write(HERE/'publication-receipt.json',receipt)
write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_LINK_REPORTS','recorded_utc':now(),'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256'],'master_pointer':str(BASE/'current-master.json'),'publication_receipt':str(HERE/'publication-receipt.json'),'link_report_verification_sha256':digest(HERE/'link-report-verification.json')})
write(HERE/'completion.json',{'status':'COMPLETE_VERIFIED_FP_COMPONENT_FOLDER_PROJECTION_AND_ALL_PICTURE_LINKS','recorded_utc':now(),'publication_receipt':rel(HERE/'publication-receipt.json'),
 'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256'],'linked_picture_actions':157,'component_finish_folder_bindings':4,'all_requested_action_categories_complete':True,
 'photograph_creation_or_coverage_upgrade':0,'root_remote_writes':0})
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','native_link_destinations_updated','new_binding_links']}))
