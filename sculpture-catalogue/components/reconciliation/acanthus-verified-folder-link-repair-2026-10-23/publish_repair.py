import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):
 p=Path(p);t=p.with_name(p.name+'.acanthus-links-tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(t,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');native=read(H/'native-binding-verification.json');vis=read(H/'visual-verification.json')
assert v['status']==native['status']==vis['status']=='PASS'and not v['issues']and not native['issues']
for key,path in [('workbook_sha256',H/'master-workbook.pending'),('register_sha256',H/'canonical-master-register.json'),('audit_sha256',H/'image-coverage-current.json')]:assert v[key]==native[key]==vis[key]==sha(path),key
assert v['register_sha256']==m['master_register']['sha256']and v['audit_sha256']==m['audit']['sha256']
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
for x in vis['previews']:assert sha(x['path'])==x['sha256']
p=read(m['pointer']['snapshot']);old=copy.deepcopy(p);validation={'verification':rel(H/'saved-file-verification.json'),'verification_sha256':sha(H/'saved-file-verification.json'),'native_binding_verification':rel(H/'native-binding-verification.json'),'native_binding_verification_sha256':sha(H/'native-binding-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'visual_verification_sha256':sha(H/'visual-verification.json')}
repair={'status':'VERIFIED_ACANTHUS_FOLDER_LINKS_REPAIRED','recorded_utc':now(),'scope':'22 native folder-link targets across five workbook tabs; all14 target folder IDs currently verified in BOLDSTONE MASTER.','changed_link_targets':22,'verified_native_folder_ids':14,'values_formulas_roles_specs_identity_changes':0,'source_packet':rel(Path(m['link_drift']['path'])),'source_packet_sha256':m['link_drift']['sha256'],**validation}
p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_acanthus_workbook_folder_link_repair=repair,latest_workbook_validation={**validation,'scope':'Saved workbook preservation and22 verified Acanthus link targets; no library-wide live-link audit claimed.'})
p['latest_image_coverage_audit'].update(validation)
p['current_individual_sculpture_list'].update(recorded_utc=now(),workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'])
p['queued_followup_packets'].update(path=rel(H/'pending-followups.json'),sha256=sha(H/'pending-followups.json'),entries=len(read(H/'pending-followups.json')['entries']))
p['current_path_scope']+=';22 remaining Acanthus workbook folder links repaired using14 verified current Master folder IDs, retaining all values, source identities and photo roles.'
p['next_catalogue_actions']=['Import four completed Moon and Shellwave folder-name changes covering73 image paths; preserve file/folder IDs and per-image1-2-1 or2-1-2 arrangement qualifications.','Find or photograph Acanthus One Leaf Left Sandstone individually, and Sandstone/Pewter series references, using BOLDSTONE MASTER exclusively.','Continue52 in situ and18 series gaps individually. Keep the pending Acanthus Two Leaves Bronze image decision separate.','Retain Wall Circle, two Dune Ripple patina and Frozen Fish legacy-identity deferrals; all current Frozen Fish remain70cm high by15cm wide.','Verify actual dimensions/depth, weighed mass, material and fitted fixing, keeping accepted estimates labelled; resolve exact Squarespace/Shopify configurations separately.']
for key in ['register','register_sha256','summary','current_missing_picture_lists','current_image_review_links','current_guided_image_review','current_specification_verification','current_dropbox_source_policy','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','platform_write_holds']:assert p[key]==old[key],key
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']),latest_acanthus_workbook_folder_link_repair=copy.deepcopy(repair),latest_workbook_validation=copy.deepcopy(p['latest_workbook_validation']),latest_image_coverage_audit=copy.deepcopy(p['latest_image_coverage_audit']),queued_followup_packets=copy.deepcopy(p['queued_followup_packets']),next_catalogue_actions=copy.deepcopy(p['next_catalogue_actions']))
 if key=='component_checkpoint':d['current_master_validation']={'path':validation['verification'],'sha256':validation['verification_sha256']}
 updates[dest]=d
write(H/'prepared-pointer.json',p)
for key,x in m.items():assert sha(x['path'])==x['sha256'],key
dest=B/p['workbook'];os.replace(H/'master-workbook.pending',dest)
for path,x in updates.items():write(path,x)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(dest)==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']and sha(m['audit']['path'])==m['audit']['sha256']
for path,d in updates.items():assert read(path)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(dest),'workbook_sha256':p['workbook_sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],'audit_sha256':v['audit_sha256'],'current_master_pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(path):sha(path)for path in updates},'saved_file_checks':v['checks'],'independent_binding_checks':native['checks'],'sheet_count':28,'formula_count':3390,'native_hyperlinks':v['native_hyperlinks'],'changed_link_targets':22,'verified_current_master_folder_ids':14,'all_values_formulas_styles_roles_specs_preserved':True,'current_options':188,'working_component_identities':112,'in_situ_gaps':52,'series_gaps':18,'required_actions':72,'native_or_platform_writes':0,'source_scope':'BOLDSTONE MASTER only','preceding_release':old['publication_receipt']};write(H/'publication-receipt.json',r);write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED_LINK_ONLY_REPAIR','publication_receipt':rel(H/'publication-receipt.json'),'next_folder_update':'Four completed Moon and Shellwave folder changes covering73 images'});print(json.dumps(r,indent=2))
