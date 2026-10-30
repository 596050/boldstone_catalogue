"""Publish one verified guided image match and advance the owner queue."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.guided-review-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');vis=read(H/'visual-verification.json');r=read(H/'link-report-verification.json');g=read(H/'canonical-master-register.json')
assert v['status']==vis['status']=='PASS'and not v['issues']and r['status']=='PASS_OWNER_CORRECTION_REPORTS'
assert sha(H/'master-workbook.pending')==v['workbook_sha256']and sha(H/'canonical-master-register.json')==v['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
for x in vis['previews']+r['pages']+r['csv_files']+r['thumbnail_files']:assert sha(x['path'])==x['sha256'],x['path']
assert read(m['squarespace_hold']['path'])['status']=='OWNER_HOLD_NO_SQUARESPACE_WRITES'
old=read(BASE/'current-master.json');p=copy.deepcopy(old);out=Path(r['output_directory']);p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'))
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification_sha256=sha(H/'saved-file-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'))
p['latest_image_coverage_audit']=coverage;p['historical_image_coverage_audits']=copy.deepcopy(g['historical_image_coverage_audits']);p['historical_terminal_photo_reviews']=copy.deepcopy(g['historical_terminal_photo_reviews'])
p['latest_terminal_photo_review']={**copy.deepcopy(g['latest_terminal_photo_review']),'verification':coverage['verification'],'verification_sha256':coverage['verification_sha256'],'visual_verification':coverage['visual_verification'],'visual_verification_sha256':coverage['visual_verification_sha256'],'linked_reports':rel(out/'index.html')}
p['latest_owner_guided_design_review']=copy.deepcopy(g['latest_owner_guided_design_review'])
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links']={'all_links':rel(out/'index.html'),'individual_image_gaps':rel(out/'individual-images.html'),'missing_in_situ_images':rel(out/'in-situ-images.html'),'missing_series_images':rel(out/'series-images.html'),'existing_images_to_check':rel(out/'existing-images-to-check.html'),'resolved_image_roles':rel(out/'resolved-image-associations.html'),'verification':rel(H/'link-report-verification.json'),'verification_sha256':sha(H/'link-report-verification.json'),'counts':r['counts']}
p['current_missing_picture_lists']={**p['current_missing_picture_lists'],'required_find_or_verify':rel(out/'Missing_Pictures_Required_2026-10-22.csv'),'individual_image_gaps':rel(out/'Missing_Individual_Images_2026-10-22.csv'),'missing_in_situ':rel(out/'Missing_In_Situ_Images_2026-10-22.csv'),'missing_series':rel(out/'Missing_Series_Images_2026-10-22.csv'),'existing_image_checks':rel(out/'Existing_Images_to_Check_2026-10-22.csv'),'resolved_image_roles':rel(out/'Resolved_Image_Associations_2026-10-22.csv'),'optional_series_images':rel(out/'Optional_Series_Images_2026-10-22.csv'),'required_actions':115,'verify_existing':5,'historical_resolved_actions':43,'resolved_this_pass':1}
walk=read(H/'walkthrough.pending.json');walk.update(current_master_sha256=p['workbook_sha256'],current_master_register=p['register']);write(H/'walkthrough.pending.json',walk)
p['current_guided_image_review']={'path':rel(Path(m['guided_review']['path'])),'sha256':sha(H/'walkthrough.pending.json'),'current_step':3,'current_case':100,'current_name':'Riyadh — Plain Moon Panel','owner_answers_recorded':len(walk['owner_answers'])}
next_actions=[
 'Guided next step: compare the FOURTH-FROM-LEFT plain curved pool panel with the workshop Plain Moon reference. Ask whether it is the same design with a possible mirrored/rotated presentation.',
 'Confirm Shellwave tier assignment, Acanthus Pewter/Sandstone full-member finish positions, and legacy FFL1 versus FFS2 design/alias identity using the linked references.',
 'Use115 current required actions:110 find/capture actions and5 existing-image/identity checks. The legacy FFL1 identity appears in both individual-gap and image-check views.',
 'All current Frozen Fish default to70 H ×15 W cm. All wall sculptures offer custom size, colour, texture, material, orientation and other variations; chosen custom specifications remain separate from the listed default.',
 'Retain the verified Fingerprint split and four isolated-photo gaps. Cup Pink/Brown provenance and physical finish questions remain open. Squarespace writes remain on owner hold.'
]
updates={};allowed={'current_master_catalogue','current_master_workbook','current_master_register','updated_utc','latest_image_coverage_audit','latest_terminal_photo_review','latest_owner_guided_design_review','current_image_review_links','current_missing_picture_lists','current_guided_image_review','current_master_validation','next_image_review_actions','prior_image_review_action_lists','current_individual_catalogue_count','historical_individual_catalogue_count_snapshots'}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 path=Path(m[key]['path']);before=read(path);z=copy.deepcopy(before);z.update(current_master_catalogue=copy.deepcopy(p),current_master_workbook=p['workbook'],current_master_register=p['register'],updated_utc=now(),latest_image_coverage_audit=copy.deepcopy(coverage),latest_terminal_photo_review=copy.deepcopy(p['latest_terminal_photo_review']),latest_owner_guided_design_review=copy.deepcopy(p['latest_owner_guided_design_review']),current_image_review_links=copy.deepcopy(p['current_image_review_links']),current_missing_picture_lists=copy.deepcopy(p['current_missing_picture_lists']),current_guided_image_review=copy.deepcopy(p['current_guided_image_review']))
 z.setdefault('prior_image_review_action_lists',[]).append({'source_snapshot':m[key]['snapshot'],'sha256':m[key]['sha256'],'actions':copy.deepcopy(z.get('next_image_review_actions',[]))});z['next_image_review_actions']=next_actions
 if key=='component_checkpoint':z['current_master_validation']={'path':coverage['verification'],'sha256':coverage['verification_sha256']}
 if'current_individual_catalogue_count'in z:
  z.setdefault('historical_individual_catalogue_count_snapshots',[]).append(copy.deepcopy(z['current_individual_catalogue_count']))
  z['current_individual_catalogue_count'].update(recorded_utc=now(),register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'])
 for k in set(z)|set(before):
  if k not in allowed:assert z.get(k)==before.get(k),(key,k)
 updates[path]=z
for k in ['summary','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','latest_owner_configuration_update','latest_listing_resolution','latest_listing_reconciliation','latest_fingerprint_component_paths','platform_write_holds']:assert p[k]==old[k],k
for x in m.values():assert sha(x['path'])==x['sha256'],x['path']
target=BASE/p['workbook'];(H/'master-workbook.pending').replace(target);write(m['owner_ledger']['path'],read(H/'owner-ledger.pending.json'));write(m['guided_review']['path'],walk)
for path,z in updates.items():write(path,z)
write(BASE/'current-master.json',p)
assert sha(target)==p['workbook_sha256']and sha(BASE/p['register'])==p['register_sha256']and read(BASE/'current-master.json')==p
for path,z in updates.items():assert read(path)==z and read(path)['current_master_catalogue']==p
assert sha(m['guided_review']['path'])==p['current_guided_image_review']['sha256']
changed={'master_workbook','master_pointer','owner_ledger','guided_review','review_progress','component_checkpoint','root_checkpoint'}
for k,x in m.items():
 if k not in changed:assert sha(x['path'])==x['sha256'],k
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256'],'checks':v['checks'],'same_design_confirmed':True,'position':'SECOND FROM LEFT','specification_changes':0,'new_options':0,'remaining_required_actions':115,'existing_image_checks':5,'guided_next_step':3,'guided_next_case':100,'Squarespace_hold_preserved':True,'native_mutations':0,'master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(path):sha(path)for path in updates}}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_GUIDED_IMAGE_REVIEW','recorded_utc':now(),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256'],'publication_receipt':str(H/'publication-receipt.json')})
print(json.dumps(receipt))
