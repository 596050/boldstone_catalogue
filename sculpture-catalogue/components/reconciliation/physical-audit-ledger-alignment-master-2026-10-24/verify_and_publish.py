"""Verify and optionally publish a metadata-only physical-audit scope alignment."""
import copy,csv,hashlib,json,os,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rel=lambda p:str(Path(p).relative_to(B));now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,v):
 p=Path(p);tmp=p.with_name(p.name+'.metadata-tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');oldp=read(m['pointer']['snapshot']);oldg=read(m['master_register']['snapshot']);g=read(H/'canonical-master-register.json');old=read(m['legacy_ledger']['snapshot']);l=read(H/'physical-source-audit.json');r=read(H/'report-verification.json');checks={};OLD=Path(m['master_register']['path']).parent
checks['baseline_bytes']=all(sha(v['path'])==sha(v['snapshot'])==v['sha256']for v in m.values())
checks['legacy_records_exact']=l['options'][:187]==old['options']and l['field_rows'][:748]==old['field_rows']and l['recorded_source_reference_validation']==old['recorded_source_reference_validation']
checks['scope_188_752']=len(l['options'])==188 and len(l['field_rows'])==752 and {x['option_id']for x in l['options']}==set(g['active_option_ids'])
checks['source_assertions_684']=sum(x['source_assertions_count']for x in l['field_rows'])==sum(len(x['source_assertions'])for x in l['field_rows'])==684
checks['four_new_qualified_fields']=len(l['field_rows'][748:])==4 and all(x['option_id']=='BSI-C3AA3700F7DA'and x['source_assertions']==[]and x['source_assertions_count']==0 and x['verification_outcome']=='QUALIFIED_ESTIMATE_OR_COMPARATOR; NOT_PHYSICALLY_VERIFIED'for x in l['field_rows'][748:])
opts={o['product_id']:o for o in g['options']};checks['all_current_working_fields_exact']=all(x['current_working_detail']==opts[x['option_id']]['master_fields'][x['field']]['display']and x['recorded_state']==opts[x['option_id']]['master_fields'][x['field']]['state']and x['recorded_basis']==opts[x['option_id']]['master_fields'][x['field']]['basis']for x in l['field_rows'])
checks['physical_evidence_not_promoted']=all(not x['physically_verified']and not x['new_measurement_or_hardware_evidence']for x in l['field_rows'])and all(not x['complete_physical_verification']for x in l['options'])and l['summary']['new_physical_verifications']==0
checks['classification_totals']=l['summary']['verification_outcomes']==dict(Counter(x['verification_outcome']for x in l['field_rows']))and sum(l['summary']['verification_outcomes'].values())==752
checks['all_options_identical']=g['options']==oldg['options']and g['components']==oldg['components']
z=copy.deepcopy(g);z.pop('latest_physical_audit_scope_alignment');z['latest_physical_source_audit']=oldg['latest_physical_source_audit'];checks['canonical_only_audit_metadata']=z==oldg
for n in ['image-coverage-current.json','current-native-reference-map.json','current-assets.json','photo-review-queue.json','guided-owner-review-state.json','pending-followups.json','original-verification.json','photo-source-review.json','working-entry-owner-provenance-sidecar.json']:
 checks['unchanged_'+n]=sha(H/n)==sha(OLD/n)
with Path(m['current_csv']['snapshot']).open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
lookup={(x['option_id'],x['field']):x for x in l['field_rows']};checks['csv_working_details_exact']=len(rows)==752 and len(lookup)==752 and all(row['working_detail']==lookup[(row['option_id'],row['field'])]['current_working_detail']for row in rows)
with Path(m['physical_input']['snapshot']).open(encoding='utf-8-sig',newline='')as f:inputs=list(csv.DictReader(f))
actual=['actual_width_cm','actual_height_cm','actual_maximum_depth_cm','bare_panel_measured_weight_kg','maker_material_recipe','fitted_fixing_type','fitted_fixing_count','measurement_date','measurement_method','object_or_batch_reference','supporting_evidence_reference']
checks['measurement_inputs_empty']=len(inputs)==188 and all(not x.get(k)for x in inputs for k in actual)
checks['report_bound']=r['register_sha256']==sha(H/'canonical-master-register.json')and all(sha(x['path'])==x['sha256']for x in r['pages']+r['csv_files']+r['thumbnail_files'])
checks['unchanged_workbook_exact_bytes']=sha(m['workbook']['path'])==oldp['workbook_sha256']==m['workbook']['sha256']
assert all(checks.values()),{k:v for k,v in checks.items()if not v}
v={'status':'PASS_METADATA_ONLY_NO_WORKBOOK_AUTHORING','recorded_utc':now(),'checks':checks,'register_sha256':sha(H/'canonical-master-register.json'),'workbook_sha256':oldp['workbook_sha256'],'ledger_sha256':sha(H/'physical-source-audit.json'),'workbook_byte_identical':True,'new_physical_verifications':0,'new_independent_source_assertions':0};write(H/'metadata-verification.json',v)
p=copy.deepcopy(oldp);p.update(recorded_utc=now(),status='CURRENT_MASTER188_OPTIONS_PHYSICAL_AUDIT_LEDGER_ALIGNED_NO_ACTIVE_PHOTO_REQUESTS',register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],publication_receipt=rel(H/'publication-receipt.json'),latest_physical_source_audit=copy.deepcopy(g['latest_physical_source_audit']),latest_physical_audit_scope_alignment=copy.deepcopy(g['latest_physical_audit_scope_alignment']),latest_metadata_validation={'path':rel(H/'metadata-verification.json'),'sha256':sha(H/'metadata-verification.json'),'workbook_bytes_changed':False,'prior_workbook_native_validation_retained':True})
p['latest_physical_source_audit'].update(ledger=rel(H/'physical-source-audit.json'),review=rel(B/'outputs'/H.name/'physical-ledger-alignment.html'))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),physical_source_evidence_ledger=rel(H/'physical-source-audit.json'),physical_source_evidence_ledger_sha256=v['ledger_sha256'],physical_options_source_audited=188,physical_field_groups_source_audited=752,new_physical_field_groups_source_reviewed=4,new_independent_physical_source_assertions=0,new_physical_verifications=0,new_physical_measurements_added=0,physical_source_scope_alignment_review=rel(B/'outputs'/H.name/'physical-ledger-alignment.html'))
p['current_image_review_links'].update(verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'))
p['current_individual_sculpture_list'].update(register=p['register'],register_sha256=p['register_sha256'],publication_receipt=p['publication_receipt'])
for k in ['workbook','workbook_sha256','summary','current_option_count','retained_option_count','current_individual_photo_capture_policy','current_guided_image_review','current_local_draft_completion','current_missing_picture_lists','platform_write_holds','current_frozen_fish_size_policy','wall_sculpture_customisation_policy']:assert p[k]==oldp[k],k
updates={}
for key in ['review_progress','component_checkpoint','root_checkpoint']:
 dest=Path(m[key]['path']);d=read(dest);d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
 for k in ['latest_physical_source_audit','latest_physical_audit_scope_alignment','latest_metadata_validation','current_specification_verification','current_image_review_links','current_individual_sculpture_list']:d[k]=copy.deepcopy(p[k])
 updates[dest]=d
write(H/'prepared-pointer.json',p)
if '--apply'not in sys.argv:print(json.dumps({'status':'PREPARED_METADATA_ONLY_ALL_CHECKS_PASS','checks':len(checks),'register_sha256':v['register_sha256'],'ledger_sha256':v['ledger_sha256'],'workbook_unchanged':True}));raise SystemExit
ind=read(H/'independent-readback.json');assert ind['status']=='PASS'and sha(ind['path'])==ind['sha256']
for x in m.values():assert sha(x['path'])==x['sha256']
for dest,d in updates.items():write(dest,d)
write(B/'current-master.json',p)
assert read(B/'current-master.json')==p and sha(B/p['register'])==p['register_sha256']and sha(B/p['workbook'])==p['workbook_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
receipt={'status':'PASS_METADATA_ONLY_PUBLISHED_AND_READ_BACK','recorded_utc':now(),'register':p['register'],'register_sha256':p['register_sha256'],'workbook':p['workbook'],'workbook_sha256':p['workbook_sha256'],'ledger_sha256':v['ledger_sha256'],'pointer_sha256':sha(B/'current-master.json'),'controls_sha256':{str(dest):sha(dest)for dest in updates},'checks':len(checks),'active_options':188,'physical_field_groups':752,'retained_source_assertions':684,'added_qualified_comparator_groups':4,'new_independent_source_assertions':0,'new_physical_verifications':0,'workbook_authoring':False,'native_or_platform_writes':0,'preceding_release':oldp['publication_receipt']};write(H/'publication-receipt.json',receipt);write(H/'WORK_STATE.json',{'status':'PUBLISHED_VERIFIED_METADATA_ONLY','publication_receipt':rel(H/'publication-receipt.json')});print(json.dumps(receipt,indent=2))
