"""Publish this owner correction after native-file and visual readback."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.owner-update-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
m=read(H/'input-manifest.json');v=read(H/'saved-file-verification.json');vis=read(H/'visual-verification.json');reports=read(H/'link-report-verification.json');g=read(H/'canonical-master-register.json');audit=read(H/'image-coverage-current.json')
assert v['status']==vis['status']=='PASS'and not v['issues']and reports['status']=='PASS_OWNER_CORRECTION_REPORTS'
assert sha(H/'master-workbook.pending')==v['workbook_sha256']and sha(H/'canonical-master-register.json')==v['register_sha256']and sha(H/'image-coverage-current.json')==v['audit_sha256']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']+vis['previews']:assert sha(x['path'])==x['sha256'],x['path']
assert read(m['squarespace_hold']['path'])['status']=='OWNER_HOLD_NO_SQUARESPACE_WRITES'
old=read(BASE/'current-master.json');p=copy.deepcopy(old);out=Path(reports['output_directory'])
p.update(recorded_utc=now(),workbook_sha256=v['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),summary=copy.deepcopy(g['summary']))
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification_sha256=sha(H/'saved-file-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'))
p['latest_image_coverage_audit']=coverage;p['historical_image_coverage_audits']=copy.deepcopy(g['historical_image_coverage_audits']);p['historical_terminal_photo_reviews']=copy.deepcopy(g['historical_terminal_photo_reviews'])
p['latest_terminal_photo_review']={**copy.deepcopy(g['latest_terminal_photo_review']),'verification':coverage['verification'],'verification_sha256':coverage['verification_sha256'],'visual_verification':coverage['visual_verification'],'visual_verification_sha256':coverage['visual_verification_sha256'],'linked_reports':rel(out/'index.html')}
for k in ['wall_sculpture_customisation_policy','current_frozen_fish_size_policy','latest_owner_configuration_update']:p[k]=copy.deepcopy(g[k])
p['latest_corrections']='All current Frozen Fish faces set to70 H ×15 W cm; wall-sculpture customisation policy recorded. Prior corrections preserved in the register/history.'
p.setdefault('historical_image_review_links',[]).append(copy.deepcopy(old['current_image_review_links']))
p['current_image_review_links']={'all_links':rel(out/'index.html'),'individual_image_gaps':rel(out/'individual-images.html'),'missing_in_situ_images':rel(out/'in-situ-images.html'),'missing_series_images':rel(out/'series-images.html'),'existing_images_to_check':rel(out/'existing-images-to-check.html'),'resolved_image_roles':rel(out/'resolved-image-associations.html'),'verification':rel(H/'link-report-verification.json'),'verification_sha256':sha(H/'link-report-verification.json'),'counts':reports['counts']}
p['current_missing_picture_lists']={'required_find_or_verify':rel(out/'Missing_Pictures_Required_2026-10-21.csv'),'individual_image_gaps':rel(out/'Missing_Individual_Images_2026-10-21.csv'),'missing_in_situ':rel(out/'Missing_In_Situ_Images_2026-10-21.csv'),'missing_series':rel(out/'Missing_Series_Images_2026-10-21.csv'),'existing_image_checks':rel(out/'Existing_Images_to_Check_2026-10-21.csv'),'resolved_image_roles':rel(out/'Resolved_Image_Associations_2026-10-21.csv'),'optional_series_images':rel(out/'Optional_Series_Images_2026-10-21.csv'),'required_actions':116,'find_capture':110,'verify_existing':6,'individual_gaps':26,'in_situ_gaps':65,'series_gaps':20,'resolved_this_pass':1,'historical_resolved_actions':42,'optional':53,'gap_views_overlap_on_legacy_individual_identity':True}
walk=read(H/'walkthrough.pending.json');walk['current_master_sha256']=p['workbook_sha256'];walk['current_master_register']=p['register'];walk['latest_owner_configuration_update']=copy.deepcopy(g['latest_owner_configuration_update']);write(H/'walkthrough.pending.json',walk)
p['current_guided_image_review']={'path':rel(Path(m['guided_review']['path'])),'sha256':sha(H/'walkthrough.pending.json'),'current_step':2,'current_case':99,'current_name':'Riyadh — Shellmoon Panel','first_owner_answer_recorded':True}
next_actions=[
 'Walk through Riyadh Shellmoon next: compare the second-from-left pool spiral with the workshop primary; ask whether they are one design, an orientation/mirrored variant, or distinct designs.',
 'Resolve Riyadh Plain Moon handedness, Shellwave tier assignment and Acanthus Pewter/Sandstone full-member finish bindings using the linked images and folders.',
 'Legacy FFL1 now uses70 ×15cm. Confirm whether it is an FFS2 alias or a separate design before requesting separate images; do not request100 ×22cm as the current standard.',
 'Use the current26 individual gaps and110 find/capture actions. Existing-image checks include the legacy individual identity, so the role views overlap.',
 'All wall sculptures offer custom size, colour, texture, material, orientation and other variants. Keep listed/default configuration specifications separate from a chosen custom commission.',
 'Fingerprint split is retained; four individual finish/component photos still need complete isolated views. Cup Ring Pink/Brown image process and physical finish questions remain separate.',
 'Preserve all source claims and exact live platform verification boundaries. Squarespace writes remain on owner hold.'
]
updates={}
allowed={'current_master_catalogue','current_master_workbook','current_master_register','updated_utc','latest_image_coverage_audit','latest_terminal_photo_review','current_image_review_links','current_missing_picture_lists','current_master_validation','next_image_review_actions','prior_image_review_action_lists','wall_sculpture_customisation_policy','current_frozen_fish_size_policy','latest_owner_configuration_update','current_guided_image_review','pending_cup_frozen_image_identity','current_individual_catalogue_count','historical_individual_catalogue_count_snapshots'}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 path=Path(m[key]['path']);before=read(path);z=copy.deepcopy(before);z.update(current_master_catalogue=copy.deepcopy(p),current_master_workbook=p['workbook'],current_master_register=p['register'],updated_utc=now(),latest_image_coverage_audit=copy.deepcopy(coverage),latest_terminal_photo_review=copy.deepcopy(p['latest_terminal_photo_review']),current_image_review_links=copy.deepcopy(p['current_image_review_links']),current_missing_picture_lists=copy.deepcopy(p['current_missing_picture_lists']),wall_sculpture_customisation_policy=copy.deepcopy(p['wall_sculpture_customisation_policy']),current_frozen_fish_size_policy=copy.deepcopy(p['current_frozen_fish_size_policy']),latest_owner_configuration_update=copy.deepcopy(p['latest_owner_configuration_update']),current_guided_image_review=copy.deepcopy(p['current_guided_image_review']))
 if z.get('next_image_review_actions'):z.setdefault('prior_image_review_action_lists',[]).append({'source_snapshot':m[key]['snapshot'],'sha256':m[key]['sha256'],'actions':copy.deepcopy(z['next_image_review_actions'])})
 z['next_image_review_actions']=next_actions
 if'pending_cup_frozen_image_identity'in z:
  q=z['pending_cup_frozen_image_identity'];q['superseded_frozen_fish_long_status']=q.get('frozen_fish_long_status');q.update(status='CUP_PROCESS_AND_LEGACY_FFL_IDENTITY_PENDING;FROZEN_CURRENT_SIZE_OWNER_CONFIRMED',frozen_fish_long_status='CURRENT70x15;LEGACY_DESIGN_ALIAS_UNBOUND;NO100x22_PHOTO_REQUEST',owner_size_decision=copy.deepcopy(p['latest_owner_configuration_update']))
 if'current_individual_catalogue_count'in z:
  z.setdefault('historical_individual_catalogue_count_snapshots',[]).append(copy.deepcopy(z['current_individual_catalogue_count']))
  z['current_individual_catalogue_count']={'recorded_utc':now(),'status':'CURRENT_WORKING_RECORDS_WITH_LEGACY_IDENTITY_OPEN','register':p['register'],'register_sha256':p['register_sha256'],'workbook':p['workbook'],'workbook_sha256':p['workbook_sha256'],'publication_receipt':p['publication_receipt'],'summary':copy.deepcopy(g['summary']),'count_definition':g['count_definition'],'customisable_records':184,'unbounded_custom_requests_are_not_enumerated_records':True,'physical_stock_verified':False}
 if key=='component_checkpoint':z['current_master_validation']={'path':coverage['verification'],'sha256':coverage['verification_sha256']}
 for k in set(z)|set(before):
  if k not in allowed:assert z.get(k)==before.get(k),(key,k)
 updates[path]=z
for k in ['latest_listing_resolution','latest_listing_reconciliation','latest_fingerprint_component_paths','platform_write_holds','current_cup_colour_reference_paths']:assert p[k]==old[k],k
# Final guard before shared files change.
for x in m.values():assert sha(x['path'])==x['sha256'],x['path']
target=BASE/p['workbook'];(H/'master-workbook.pending').replace(target)
write(m['owner_ledger']['path'],read(H/'owner-ledger.pending.json'));write(m['guided_review']['path'],walk)
for path,z in updates.items():write(path,z)
write(BASE/'current-master.json',p)
assert sha(target)==p['workbook_sha256']and sha(BASE/p['register'])==p['register_sha256']and read(BASE/'current-master.json')==p
for path,z in updates.items():assert read(path)==z and read(path)['current_master_catalogue']==p
assert sha(m['guided_review']['path'])==p['current_guided_image_review']['sha256']
changed={'master_pointer','master_workbook','owner_ledger','guided_review','review_progress','component_checkpoint','root_checkpoint'}
for k,x in m.items():
 if k not in changed:assert sha(x['path'])==x['sha256'],k
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':sha(target),'register':str(BASE/p['register']),'register_sha256':p['register_sha256'],'checks':v['checks'],'frozen_records_standardized':6,'customisable_option_records':184,'source_assertions_preserved':True,'legacy_identity_not_merged':True,'resolved_current_photo_roles':1,'remaining_required_actions':116,'guided_next_case':99,'owner_answer_saved':True,'Squarespace_hold_preserved':True,'native_mutations':0,'controls_sha256':{str(path):sha(path)for path in updates},'master_pointer_sha256':sha(BASE/'current-master.json')}
write(H/'publication-receipt.json',receipt);write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_OWNER_CONFIGURATION_UPDATE','recorded_utc':now(),'workbook_sha256':p['workbook_sha256'],'register_sha256':p['register_sha256'],'publication_receipt':str(H/'publication-receipt.json')})
print(json.dumps(receipt))
