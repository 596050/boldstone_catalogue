"""Publish the verified Coral wording correction with exact baseline guards."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.coral-tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');old=read(m['pointer']['snapshot']);g=read(H/'canonical-master-register.json');s=read(H/'import-summary.json')
v=read(H/'saved-workbook-verification.json');reports=read(H/'report-verification.json');actual=read(H/'actual-input-verification.json');visual=read(H/'visual-verification.json')
assert v['status']=='PASS' and not v['failures'] and v['wording_field_objects']==1 and v['other_field_objects_unchanged']==1133
assert reports['status']=='PASS_CURRENT_CORAL_WORDING_REPORTS' and not reports['failures']
assert actual['all_original_actual_measurement_fields_preserved'] and actual['new_actual_measurements']==0
assert sha(actual['current_path'])==actual['current_sha256']
for key,name in [('workbook_sha256','master-workbook.pending'),('register_sha256','canonical-master-register.json'),('coverage_sha256','image-coverage-current.json')]:assert sha(H/name)==v[key],key
assert reports['register_sha256']==v['register_sha256'] and visual['workbook_sha256']==v['workbook_sha256']
assert visual['status']=='PASS_RENDERED_CORAL_WORDING_READABLE'
for path,digest in visual['previews'].items():assert sha(path)==digest
for x in reports['pages']+reports['csv_files']+[reports['current_count_summary']]:assert sha(x['path'])==x['sha256'],x['path']
qa=read(H/'independent-qa-reference.json');assert sha(qa['path'])==qa['sha256'];q=read(qa['path']);assert q['status'].startswith('PASS')
assert q['register_sha256']==v['register_sha256'] and q['workbook_sha256']==v['workbook_sha256']
if qa.get('seal_path'):
    assert sha(qa['seal_path'])==qa['seal_sha256']
    for path,digest in read(qa['seal_path'])['files'].items():assert sha(path)==digest,path
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
p=copy.deepcopy(old);now=datetime.now(timezone.utc).isoformat()
p.update(recorded_utc=now,status='CURRENT_MASTER188_CORAL_ACCEPTANCE_WORDING_ALIGNED',register=rel(H/'canonical-master-register.json'),
    register_sha256=v['register_sha256'],workbook_sha256=v['workbook_sha256'],publication_receipt=rel(H/'publication-receipt.json'),
    latest_coral_depth_wording_correction={**s,'status':'PUBLISHED_CORAL_WORDING_ONLY','review':rel(OUT/'coral-depth-wording.html'),'independent_qa':qa},
    latest_workbook_validation={'saved_workbook':{'path':rel(H/'saved-workbook-verification.json'),'sha256':sha(H/'saved-workbook-verification.json')},
        'independent_wording_qa':qa,'rendered_previews':{'path':rel(H/'visual-verification.json'),'sha256':sha(H/'visual-verification.json')}})
p['current_individual_sculpture_list'].update(recorded_utc=now,register=p['register'],register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],
    publication_receipt=p['publication_receipt'],current_option_list=rel(OUT/'Current_Individual_Options_188.csv'),current_option_list_sha256=sha(OUT/'Current_Individual_Options_188.csv'),
    count_summary=rel(OUT/'current-count-summary.json'),count_summary_sha256=sha(OUT/'current-count-summary.json'))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),
    review=rel(OUT/'specifications-to-verify.html'),field_checklist=rel(OUT/'Specification_Verification_Checklist_1128_Fields.csv'),
    actual_physical_measurement_input=rel(OUT/'Physical_Verification_Input_188_Options.csv'),actual_input_verification=rel(H/'actual-input-verification.json'),
    actual_input_verification_sha256=sha(H/'actual-input-verification.json'),current_depth_estimates=rel(OUT/'depth-estimates.html'),
    current_depth_estimates_csv=rel(OUT/'Depth_Estimates_14.csv'),coral_wording_fields_corrected=1,numeric_values_changed_in_latest_refresh=0,
    full188_independent_audit=s['audit'],remaining_face_and_base_material_checks=rel(OUT/'specification-audit.html'))
p['current_image_review_links'].update(all_links=rel(OUT/'index.html'),specifications_to_verify=rel(OUT/'specifications-to-verify.html'),
    latest_coral_wording=rel(OUT/'coral-depth-wording.html'),latest_full_specification_audit=rel(OUT/'specification-audit.html'),
    latest_depth_estimates=rel(OUT/'depth-estimates.html'),verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'))
p['current_working_depth_status']['review']=rel(OUT/'depth-estimates.html')
p['current_guided_image_review'].update(terminal_review_command=rel(H/'walkthrough.py'),terminal_review_command_sha256=sha(H/'walkthrough.py'),
    depth_estimate_review=rel(OUT/'depth-estimates.html'),coral_wording_review=rel(OUT/'coral-depth-wording.html'))
p['current_authenticated_squarespace_inventory_observation'].update(register=p['register'],register_sha256=p['register_sha256'])
p['current_local_draft_completion']['latest_working_note_correction']=rel(OUT/'coral-depth-wording.html')
p['current_published_gallery_projection'].update(status='FROZEN_IMAGE_SOURCE_READER_BEFORE_CORAL_WORDING_ALIGNMENT',latest_current_option_projection=rel(OUT/'index.html'))
p['next_catalogue_actions']=[
    'Coral Spiral acceptance wording is aligned. Its55×55cm face and working depth6cm/range5–7 remain unchanged; no numeric reapproval or physical verification is inferred.',
    'Continue the27 linked base-material checks and3 unknown face-size checks in '+rel(OUT/'specification-audit.html')+'. Keep estimates and actual measurement inputs distinct.',
    'Preserve22 held installation and1 held series requests, all source/variant qualifications, current Frozen Fish70×15cm policy and customisation choices.',
    'Preserve the Squarespace write hold. No new platform draft, exact variant assignment or physical stock claim is authorized by this clerical correction.']
p['latest_master_metadata_change']={'status':'CORAL_ACCEPTANCE_WORDING_ALIGNED','preceding_receipt':old['publication_receipt'],'numeric_or_physical_changes':0}
allowed={'recorded_utc','status','register','register_sha256','workbook_sha256','publication_receipt','latest_coral_depth_wording_correction','latest_workbook_validation',
    'current_individual_sculpture_list','current_specification_verification','current_image_review_links','current_working_depth_status','current_guided_image_review',
    'current_authenticated_squarespace_inventory_observation','current_local_draft_completion','current_published_gallery_projection','next_catalogue_actions','latest_master_metadata_change'}
assert all(p[k]==old[k]for k in old if k not in allowed)
updates={}
for label in ['review_progress','component_checkpoint','checkpoint']:
    path=Path(m[label]['path']);value=read(path);value.update(updated_utc=now,current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],
        current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
    for key in allowed-{'recorded_utc','status','register','register_sha256','workbook_sha256','publication_receipt'}:value[key]=copy.deepcopy(p[key])
    updates[path]=value
write(H/'prepared-pointer.json',p)
if '--apply'not in sys.argv:print('PASS_PREPARED_CORAL_WORDING_PUBLICATION_GUARDS');raise SystemExit(0)
changed=[]
try:
    for key,x in m.items():assert sha(x['path'])==x['sha256'],key
    target=B/p['workbook'];temp=target.with_name(target.name+'.coral-tmp');shutil.copy2(H/'master-workbook.pending',temp);os.replace(temp,target);changed.append(('master_workbook',target))
    for path,value in updates.items():
        write(path,value);changed.append((next(k for k in ['review_progress','component_checkpoint','checkpoint']if m[k]['path']==str(path)),path))
    write(B/'current-master.json',p);changed.append(('pointer',B/'current-master.json'))
    assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256'] and sha(B/p['register'])==p['register_sha256']
    for path,value in updates.items():assert read(path)==value and value['current_master_catalogue']==p
    receipt={'status':'PASS_ONE_CORAL_WORDING_CORRECTION_PUBLISHED_AND_READ_BACK','recorded_utc':now,'current_master_pointer_sha256':sha(B/'current-master.json'),
        'preceding_pointer_sha256':m['pointer']['sha256'],'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],
        'controls_sha256':{str(path):sha(path)for path in updates},'independent_qa':qa,'wording_field_objects':1,'other_field_objects_unchanged':1133,
        'numeric_values_changed':0,'new_physical_measurements':0,'active_options':188,'retained_rows':189,'component_records':112,'working_groups':110,
        'authored_cells':3,'calculated_cells':1,'planned_row_heights':1,'new_native_targets':0,'external_writes':0}
    write(H/'publication-receipt.json',receipt);print(json.dumps(receipt,indent=2))
except BaseException:
    for label,path in reversed(changed):shutil.copy2(m[label]['snapshot'],path)
    raise
