"""Publish the verified current media projection and source-scope corrections."""
import copy, hashlib, json
from pathlib import Path
from datetime import datetime, timezone
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):
 p=Path(p);t=p.with_name(p.name+'.media-tmp');t.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');t.replace(p)
m=read(HERE/'input-manifest.json');check=read(HERE/'saved-file-verification.json');g=read(HERE/'canonical-master-register.json')
assert check['status']=='PASS'and not check['issues']
assert digest(HERE/'master-workbook.pending')==check['workbook_sha256']
assert digest(HERE/'canonical-master-register.json')==check['register_sha256']
for x in m.values():assert digest(x['path'])==digest(x['snapshot'])==x['sha256']
previews=read(HERE/'preview-manifest.json');assert len(previews)==14
write(HERE/'visual-verification.json',{'status':'PASS','recorded_utc':now(),
 'previews':[{**x,'sha256':digest(x['path'])}for x in previews],
 'finding':'Changed primary examples, Cup image quality/provenance, resolved action, conditional Wall Circle rows/summary, Fingerprint composition scope/source links, component view and draft media inspected. Text and IDs readable. Unchanged tabs retain prior visual QA.'})
prior=read(BASE/'current-master.json');ptr=copy.deepcopy(prior)
ptr.update(recorded_utc=now(),workbook_sha256=check['workbook_sha256'],register=rel(HERE/'canonical-master-register.json'),register_sha256=check['register_sha256'],publication_receipt=rel(HERE/'publication-receipt.json'))
coverage=copy.deepcopy(g['latest_image_coverage_audit'])
coverage.update(verification=rel(HERE/'saved-file-verification.json'),verification_sha256=digest(HERE/'saved-file-verification.json'),
 visual_verification=rel(HERE/'visual-verification.json'),visual_verification_sha256=digest(HERE/'visual-verification.json'))
ptr['historical_image_coverage_audits']=[copy.deepcopy(prior['latest_image_coverage_audit'])]
ptr['latest_image_coverage_audit']=coverage
summary=copy.deepcopy(g['latest_image_identity_resolution'])
summary.update(verification=coverage['verification'],verification_sha256=coverage['verification_sha256'],visual_verification=coverage['visual_verification'])
ptr['latest_image_identity_resolution']=summary
ptr['component_organisation_policy']=copy.deepcopy(g['component_organisation_policy'])
ptr['current_missing_picture_lists']={
 'required_find_or_verify':rel(HERE/'Missing_Pictures_Required_2026-10-21.csv'),
 'individual_image_gaps':rel(HERE/'Missing_Individual_Images_2026-10-21.csv'),
 'optional_series_images':rel(HERE/'Optional_Series_Images_2026-10-21.csv'),
 'required_actions':157,'find_capture':119,'verify_existing':38,'individual_gaps':26,'optional':53}
ptr['latest_path_refresh']['image_questions']='Current Cup primary superseded by the complete historical isolated archive image (tg4A); its453px edited-source qualification retained. Processed coloured-reference finish/provenance and exact Frozen Fish Long100x22 image remain unresolved.'
ptr['latest_cup_frozen_manual_paths']['current_image_supersession']={'source':rel(HERE/'image-coverage-current.json'),'primary_file_id':summary['cup_primary']['file_id'],'primary_folder_id':summary['cup_primary']['folder_id'],'historical_path_only_paired_primary_superseded':True}
fp_scope='Numbers1/2 are whole source inspiration compositions. Both accepted standard Left/Right members are within composition2. Earlier positional1/2 recovery question withdrawn; no individual numbering or rename inferred.'
ptr['latest_four_family_matching']['status']='VERIFIED_CURRENT_PATHS; FINGERPRINT_NUMBERING_SOURCE_SCOPE_SUPERSEDED'
ptr['latest_four_family_matching']['numbering_status']=fp_scope
ptr['latest_four_family_matching']['numbering_source_addendum']=m['fingerprint_addendum']
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 p=Path(m[key]['path']);d=read(p)
 d['current_master_catalogue']=copy.deepcopy(ptr);d['current_master_workbook']=ptr['workbook'];d['current_master_register']=ptr['register'];d['updated_utc']=now()
 d['latest_image_coverage_audit']=copy.deepcopy(coverage);d['latest_image_identity_resolution']=copy.deepcopy(summary)
 d['latest_four_family_matching']=copy.deepcopy(ptr['latest_four_family_matching']);d['component_organisation_policy']=copy.deepcopy(g['component_organisation_policy'])
 d['historical_Fingerprint_numeric_assignment_question']=copy.deepcopy(d.get('pending_Fingerprint_numeric_assignment'))
 d['pending_Fingerprint_numeric_assignment']={'status':'WITHDRAWN_SOURCE_SCOPE_CORRECTION','scope':fp_scope,'source_addendum':m['fingerprint_addendum'],
  'individual_member_number':None,'requires_owner_positional_assignment':False,'names_and_component_IDs_preserved':True}
 d['pending_cup_frozen_image_identity']={'status':'HISTORICAL_RING_ISOLATED_IMAGE_RESOLVED; PNG_PROCESS_AND_EXACT_FFL_IMAGE_UNRESOLVED',
  'cup_primary_file_id':summary['cup_primary']['file_id'],'cup_primary_folder_id':summary['cup_primary']['folder_id'],
  'qualification':summary['cup_qualification'],'processed_reference_provenance':summary['processed_reference_provenance'],
  'frozen_fish_long_status':summary['frozen_fish_long']['status'],'coverage_available':158,'individual_gaps':26,'source_addendum':m['cup_addendum']}
 if key=='component_checkpoint':d['current_master_validation']={'path':coverage['verification'],'sha256':coverage['verification_sha256']}
 updates[p]=d
write(HERE/'export-receipt.json',{'status':'PASS','recorded_utc':now(),'workbook':ptr['workbook'],'workbook_sha256':ptr['workbook_sha256'],
 'register':ptr['register'],'register_sha256':ptr['register_sha256'],'native_hyperlinks':check['native_hyperlinks'],'formulas':check['formula_count'],
 'accepted_specifications_changed':0,'individual_available':158,'individual_gaps':26,'required_actions':157,'verification':coverage['verification']})
for x in m.values():assert digest(x['path'])==x['sha256']
target=BASE/ptr['workbook'];(HERE/'master-workbook.pending').replace(target)
for p,d in updates.items():write(p,d)
write(BASE/'current-master.json',ptr)
assert read(BASE/'current-master.json')==ptr and digest(target)==ptr['workbook_sha256']
for p in updates:assert read(p)['current_master_catalogue']==ptr and read(p)['pending_Fingerprint_numeric_assignment']['requires_owner_positional_assignment']is False
for key in ['master_register','owner_ledger','source_model','prior_audit','cup_seal','cup_addendum','fingerprint_addendum','fingerprint_bindings','fingerprint_downloads','component_organisation_audit','native_metadata']:
 assert digest(m[key]['path'])==m[key]['sha256']
assert ptr['latest_listing_resolution']==prior['latest_listing_resolution']and ptr['latest_listing_reconciliation']==prior['latest_listing_reconciliation']
receipt={'status':'PASS_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'workbook':str(target),'workbook_sha256':digest(target),
 'register':str(HERE/'canonical-master-register.json'),'register_sha256':ptr['register_sha256'],'audit':rel(HERE/'image-coverage-current.json'),
 'audit_sha256':check['audit_sha256'],'verification':coverage['verification'],'visual_verification':coverage['visual_verification'],'checks':check['checks'],
 'counts':coverage['counts'],'all184_names_1104_fields_and_A106_source_review_preserved':True,
 'current_primary':'Cup Ring historical complete isolated edited453px archive reference; no exact current cast certification',
 'fingerprint':'Source composition numbers recorded separately; positional numbering question withdrawn',
 'component_first_policy_adopted':True,'current_master_pointer_sha256':digest(BASE/'current-master.json'),
 'controls_sha256':{str(p):digest(p)for p in updates},'platform_or_dropbox_writes':0,'physical_claims_upgraded':0}
write(HERE/'publication-receipt.json',receipt)
write(HERE/'completion.json',{'status':'COMPLETE_BOUNDED_IMAGE_COVERAGE_AND_IDENTITY_ADDENDUM','recorded_utc':now(),
 'publication_receipt':rel(HERE/'publication-receipt.json'),'workbook_sha256':ptr['workbook_sha256'],'register_sha256':ptr['register_sha256'],
 'individual_complete':158,'individual_gaps':26,'required_actions':157,'exact_FFL_size_image_unresolved':True,'four_Wall_Circle_matches_conditional':True,
 'no_repeat_FP_positional_numbering_question':True,'new_native_or_remote_writes':0})
print(json.dumps({k:receipt[k]for k in ['status','workbook_sha256','register_sha256','checks','component_first_policy_adopted']}))
