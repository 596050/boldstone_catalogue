"""Publish the verified local master, current controls and linked review pass."""
import copy,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.photo-review-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
m=read(H/'input-manifest.json');check=read(H/'saved-file-verification.json');visual=read(H/'visual-verification.json');reports=read(H/'link-report-verification.json');g=read(H/'canonical-master-register.json');audit=read(H/'image-coverage-current.json')
assert check['status']==visual['status']=='PASS'and not check['issues']and reports['status']=='PASS_CURRENT_TERMINAL_REVIEW_REPORTS'
assert sha(H/'master-workbook.pending')==check['workbook_sha256']and sha(H/'canonical-master-register.json')==check['register_sha256']and sha(H/'image-coverage-current.json')==check['audit_sha256']
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
for x in reports['pages']+reports['csv_files']+reports['thumbnail_files']:assert sha(x['path'])==x['sha256']
for x in visual['previews']:assert sha(x['path'])==x['sha256']
assert read(m['squarespace_hold']['path'])['status']=='OWNER_HOLD_NO_SQUARESPACE_WRITES'
ptr=copy.deepcopy(read(BASE/'current-master.json'));oldptr=copy.deepcopy(ptr);out=Path(reports['output_directory'])
ptr.update(recorded_utc=now(),workbook_sha256=check['workbook_sha256'],register=rel(H/'canonical-master-register.json'),register_sha256=check['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'))
coverage=copy.deepcopy(g['latest_image_coverage_audit']);coverage.update(verification=rel(H/'saved-file-verification.json'),verification_sha256=sha(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),visual_verification_sha256=sha(H/'visual-verification.json'))
ptr['latest_image_coverage_audit']=coverage;ptr['historical_image_coverage_audits']=copy.deepcopy(g['historical_image_coverage_audits'])
ptr['latest_terminal_photo_review']={**copy.deepcopy(g['latest_terminal_photo_review']),'verification':coverage['verification'],'verification_sha256':coverage['verification_sha256'],'visual_verification':coverage['visual_verification'],'visual_verification_sha256':coverage['visual_verification_sha256'],'linked_reports':rel(out/'index.html')}
ptr['current_cup_colour_reference_paths']=copy.deepcopy(g['current_cup_colour_reference_paths'])
ptr['historical_terminal_photo_reviews']=copy.deepcopy(g['historical_terminal_photo_reviews'])
ptr.setdefault('historical_image_review_links',[]).append(copy.deepcopy(oldptr['current_image_review_links']))
ptr['current_image_review_links']={'all_links':rel(out/'index.html'),'individual_image_gaps':rel(out/'individual-images.html'),'missing_in_situ_images':rel(out/'in-situ-images.html'),'missing_series_images':rel(out/'series-images.html'),'existing_images_to_check':rel(out/'existing-images-to-check.html'),'resolved_image_roles':rel(out/'resolved-image-associations.html'),'verification':rel(H/'link-report-verification.json'),'verification_sha256':sha(H/'link-report-verification.json'),'counts':reports['counts']}
ptr['current_image_review_links']['latest_deep_comparisons']=rel(out/'deep-review-findings.html')
ptr['current_missing_picture_lists']={'required_find_or_verify':rel(out/'Missing_Pictures_Required_2026-10-21.csv'),'individual_image_gaps':rel(out/'Missing_Individual_Images_2026-10-21.csv'),'missing_in_situ':rel(out/'Missing_In_Situ_Images_2026-10-21.csv'),'missing_series':rel(out/'Missing_Series_Images_2026-10-21.csv'),'existing_image_checks':rel(out/'Existing_Images_to_Check_2026-10-21.csv'),'resolved_image_roles':rel(out/'Resolved_Image_Associations_2026-10-21.csv'),'optional_series_images':rel(out/'Optional_Series_Images_2026-10-21.csv'),'required_actions':117,'find_capture':111,'verify_existing':6,'individual_gaps':26,'in_situ_gaps':65,'series_gaps':20,'resolved_this_pass':25,'resolved_across_both_photo_passes':40,'optional':53}
next_actions=[
 'Frozen Fish Long: identify the exact 100 x 22 cm source file or photograph that measured build. The shared White solo source remains unbound to Long; existing owner/source question remains pending.',
 'Use the linked 26 individual-image/size actions: 20 group-only options, five detail-only options and one Long-size binding. The historical isolated White Cup Ring reference is already resolved.',
 'Resolve the six linked exact-image questions: Frozen Fish Two size, Riyadh Shellmoon handedness, Riyadh Plain Moon handedness, Shellwave tier assignment, and Acanthus Pewter/Sandstone full-member finish bindings. Each has current image/folder links and a specific comparison finding.',
 'Find or capture 65 exact-option wider in-situ scenes and 20 exact-option series images. White Brancusi 1 needs its kept relief intact; the altered solo garden illustration is excluded. Qualified studio, water-adapted and staged contexts remain labelled.',
 'Fingerprint component/finish folders are verified. The four separate options still need isolated individual views; source composition 2 contains both Left and Right.',
 'Cup Ring Pink/Brown processed references are now in separate owner-approved appearance folders. Clarify physical manufacture and intended sale finish before creating any coloured product option.',
 'Keep group-position candidates outside the unique identity count until supported. Physical measurements, stock, fixing hardware and exact current platform matches remain separate. Squarespace writes remain on owner hold.'
]
updates={};control_allowed={'current_master_catalogue','current_master_workbook','current_master_register','updated_utc','latest_image_coverage_audit','latest_terminal_photo_review','current_cup_colour_reference_paths','current_image_review_links','current_missing_picture_lists','platform_write_holds','current_master_validation','next_image_review_actions','prior_image_review_action_lists','current_component_photograph_gaps_scope','current_group_photo_review_policy','pending_cup_frozen_image_identity'}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[key]['path']);before=read(p);d=copy.deepcopy(before);d.update(current_master_catalogue=copy.deepcopy(ptr),current_master_workbook=ptr['workbook'],current_master_register=ptr['register'],updated_utc=now(),latest_image_coverage_audit=copy.deepcopy(coverage),latest_terminal_photo_review=copy.deepcopy(ptr['latest_terminal_photo_review']),current_cup_colour_reference_paths=copy.deepcopy(ptr['current_cup_colour_reference_paths']),current_image_review_links=copy.deepcopy(ptr['current_image_review_links']),current_missing_picture_lists=copy.deepcopy(ptr['current_missing_picture_lists']),platform_write_holds=copy.deepcopy(ptr['platform_write_holds']))
 if d.get('next_image_review_actions'):d.setdefault('prior_image_review_action_lists',[]).append({'source_snapshot':m[key]['snapshot'],'source_sha256':m[key]['sha256'],'actions':copy.deepcopy(d['next_image_review_actions'])})
 d['next_image_review_actions']=next_actions
 if'current_component_photograph_gaps'in d:d['current_component_photograph_gaps_scope']='Historical partial component review records preserved. Current184-option role statuses and precise remaining actions are maintained by latest_image_coverage_audit and current_missing_picture_lists.'
 if'current_group_photo_review_policy'in d:d['current_group_photo_review_policy']['current_audit']=coverage['audit']
 if'pending_cup_frozen_image_identity'in d:d['pending_cup_frozen_image_identity']['current_appearance_reference_paths']=copy.deepcopy(ptr['current_cup_colour_reference_paths'])
 if key=='component_checkpoint':d['current_master_validation']={'path':coverage['verification'],'sha256':coverage['verification_sha256']}
 for k in set(before)|set(d):
  if k not in control_allowed:assert before.get(k)==d.get(k),(key,k)
 updates[p]=d
for k in ['summary','latest_listing_resolution','latest_listing_reconciliation','latest_fingerprint_component_paths','platform_write_holds']:assert ptr[k]==oldptr[k],k
write(H/'export-receipt.json',{'status':'PASS','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':ptr['workbook_sha256'],'register':ptr['register'],'register_sha256':ptr['register_sha256'],'sheets':21,'native_hyperlinks':check['native_hyperlinks'],'formula_count':2729,'reviewed_picture_actions':32,'resolved_image_roles':25,'remaining_required_actions':117,'individual_gaps':26,'source_qualified_not_physical_certification':True})
# Final compare-and-swap guard for all shared inputs immediately before publication.
for x in m.values():assert sha(x['path'])==x['sha256'],x['path']
target=BASE/ptr['workbook'];(H/'master-workbook.pending').replace(target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)
assert sha(target)==check['workbook_sha256']and read(BASE/'current-master.json')==ptr
for p,d in updates.items():assert read(p)==d and read(p)['current_master_catalogue']==ptr
changed_sources={'master_workbook','master_pointer','review_progress','component_checkpoint','root_checkpoint'}
for key,x in m.items():
 if key not in changed_sources:assert sha(x['path'])==x['sha256'],key
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':sha(target),'register':str(H/'canonical-master-register.json'),'register_sha256':sha(H/'canonical-master-register.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'saved_file_verification':coverage['verification'],'checks':check['checks'],'reviewed_prior_actions':32,'resolved_visual_image_roles':25,'required_picture_actions_remaining':117,'individual_image_or_size_gaps':26,'in_situ_capture_gaps':65,'series_capture_gaps':20,'existing_image_binding_checks':6,'accepted_names_and_1104_specifications_preserved':True,'fingerprint_split_and_four_individual_gaps_retained':True,'Cup_Pink_Brown_current_ID_paths_preserved':2,'Cup_physical_finish_options_added':0,'old_review_report_directory_preserved':True,'current_review':ptr['current_image_review_links'],'current_master_pointer_sha256':sha(BASE/'current-master.json'),'controls_sha256':{str(p):sha(p)for p in updates},'Squarespace_owner_hold_preserved':True,'root_Dropbox_or_platform_mutations':0,'image_role_completion_is_not_physical_verification':True}
write(H/'publication-receipt.json',receipt)
write(out/'publication-state.json',{'status':'PUBLISHED_CURRENT_TERMINAL_REVIEW','recorded_utc':now(),'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256'],'master_pointer':str(BASE/'current-master.json'),'publication_receipt':str(H/'publication-receipt.json'),'link_report_verification_sha256':sha(H/'link-report-verification.json')})
write(H/'completion.json',{'status':'COMPLETE_DEEP_CANDIDATE_REVIEW_PASS_WITH_REMAINING_PHOTO_AND_BINDING_WORK','recorded_utc':now(),'publication_receipt':rel(H/'publication-receipt.json'),'reviewed':32,'resolved_visual_associations':25,'remaining_required_actions':117,'remaining_work_is_not_marked_complete':True,'root_native_mutations':0})
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','reviewed_prior_actions','resolved_visual_image_roles','required_picture_actions_remaining']}))
