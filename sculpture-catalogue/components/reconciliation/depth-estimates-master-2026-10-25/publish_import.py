"""Publish verified depth estimates and current projections with baseline guards."""
import copy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
H=Path(__file__).resolve().parent
B=H.parents[2]
OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel=lambda p:str(Path(p).relative_to(B))
def write(path,value):
    path=Path(path);temp=path.with_name(path.name+'.depth-tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)
assert not(H/'publication-receipt.json').exists()
m=read(H/'input-manifest.json');old=read(m['pointer']['snapshot']);g=read(H/'canonical-master-register.json');s=read(H/'import-summary.json')
v=read(H/'saved-workbook-verification.json');reports=read(H/'report-verification.json');actual=read(H/'actual-input-verification.json')
assert v['status']==actual['status'].split('_')[0]=='PASS' and not v['failures']
assert reports['status']=='PASS_CURRENT_DEPTH_ESTIMATE_REPORTS' and not reports['failures']
assert actual['all_original_actual_measurement_fields_preserved'] and actual['new_actual_measurements']==0
assert sha(actual['current_path'])==actual['current_sha256']
for key,name in [('workbook_sha256','master-workbook.pending'),('register_sha256','canonical-master-register.json'),('coverage_sha256','image-coverage-current.json')]:assert sha(H/name)==v[key],key
assert reports['register_sha256']==v['register_sha256']
for x in reports['pages']+reports['csv_files']+[reports['current_count_summary']]:assert sha(x['path'])==x['sha256'],x['path']
qa=read(H/'independent-qa-reference.json');assert sha(qa['path'])==qa['sha256'];q=read(qa['path']);assert q['status'].startswith('PASS')
assert q['workbook_sha256']==v['workbook_sha256'] and q['register_sha256']==v['register_sha256']
if qa.get('seal_path'):assert sha(qa['seal_path'])==qa['seal_sha256']
seal=read(qa['seal_path'])
for path,digest in seal['files'].items():assert sha(path)==digest,path
visual=read(H/'visual-verification.json')
assert visual['status']=='PASS_RENDERED_WORKING_DEPTHS_READABLE' and visual['workbook_sha256']==v['workbook_sha256']
for path,digest in visual['previews'].items():assert sha(path)==digest,path
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
p=copy.deepcopy(old)
p.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_MASTER188_FOURTEEN_OWNER_AUTHORIZED_DEPTH_ESTIMATES',
    register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],workbook_sha256=v['workbook_sha256'],
    publication_receipt=rel(H/'publication-receipt.json'),latest_owner_depth_estimate_import={**s,'status':'PUBLISHED14_OWNER_AUTHORIZED_DEPTH_ESTIMATES',
        'review':rel(OUT/'depth-estimates.html'),'independent_qa':qa},
    latest_workbook_validation={'saved_workbook':{'path':rel(H/'saved-workbook-verification.json'),'sha256':sha(H/'saved-workbook-verification.json')},'independent_depth_qa':qa,'rendered_previews':{'path':rel(H/'visual-verification.json'),'sha256':sha(H/'visual-verification.json')}})
p['current_working_depth_status']={'active_options_with_working_depth':188,'new_estimate_fields':14,'new_physical_measurements':0,
    'face_sizes_still_unconfirmed':s['unknown_face_sizes_retained'],'depth_definition':s['depth_definition'],'review':rel(OUT/'depth-estimates.html')}
p['current_individual_sculpture_list'].update(recorded_utc=p['recorded_utc'],register=p['register'],register_sha256=p['register_sha256'],
    workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],current_option_list=rel(OUT/'Current_Individual_Options_188.csv'),
    current_option_list_sha256=sha(OUT/'Current_Individual_Options_188.csv'),count_summary=rel(OUT/'current-count-summary.json'),
    count_summary_sha256=sha(OUT/'current-count-summary.json'))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),
    review=rel(OUT/'specifications-to-verify.html'),field_checklist=rel(OUT/'Specification_Verification_Checklist_1128_Fields.csv'),
    actual_physical_measurement_input=rel(OUT/'Physical_Verification_Input_188_Options.csv'),
    actual_input_verification=rel(H/'actual-input-verification.json'),actual_input_verification_sha256=sha(H/'actual-input-verification.json'),
    depth_estimate_fields_added=14,new_physical_measurements_added=0,new_physical_verifications=0,
    current_depth_estimates=rel(OUT/'depth-estimates.html'),current_depth_estimates_csv=rel(OUT/'Depth_Estimates_14.csv'),
    new_working_field_groups_added=0,commercial_values_changed_in_this_refresh=0)
p['current_image_review_links'].update(all_links=rel(OUT/'index.html'),specifications_to_verify=rel(OUT/'specifications-to-verify.html'),
    latest_depth_estimates=rel(OUT/'depth-estimates.html'),verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'))
p['current_image_review_links']['counts']['new_depth_estimate_fields']=14
p['current_guided_image_review'].update(terminal_review_command=rel(H/'walkthrough.py'),terminal_review_command_sha256=sha(H/'walkthrough.py'),
    depth_estimate_review=rel(OUT/'depth-estimates.html'),no_repeat_numeric_depth_approval_required=True)
p['current_authenticated_squarespace_inventory_observation'].update(register=p['register'],register_sha256=p['register_sha256'])
p['current_local_draft_completion']['latest_working_depth_refresh']=rel(OUT/'depth-estimates.html')
p['current_local_draft_completion']['new_native_drafts_or_variant_assignments']=0
p['current_published_gallery_projection']['status']='FROZEN_IMAGE_SOURCE_READER_BEFORE14_WORKING_DEPTH_UPDATES'
p['current_published_gallery_projection']['latest_current_option_projection']=rel(OUT/'index.html')
p['current_published_gallery_projection']['source_photographs_and_associations_unchanged']=True
p['next_catalogue_actions']=[
    'All188 active options now have a working depth.14 additions are explicitly labelled assistant estimates/ranges under the owner request; do not ask the owner to approve those numbers again.',
    'Azure and bordered Moonphase1/2 face dimensions remain unconfirmed. Actual measurements, materials, weight and fitted fixing retain their existing evidence states. Actual measurement input cells remain blank.',
    'Preserve22 held installation and1 held series requests. The four owner identity decisions remain closed; no new photo, SKU, variant, stock or physical verification is inferred.',
    'Preserve bounded source/configuration uncertainties and the Squarespace write hold. Local Shopify records remain the source authority; no account task or platform write is required.']
p['latest_master_metadata_change']={'status':'SUPERSEDED_BY_OWNER_REQUESTED14_DEPTH_ESTIMATES','preceding_receipt':old['publication_receipt']}
for key in ['summary','current_option_count','retained_option_count','current_global_context_owner_hold','current_frozen_fish_size_policy',
    'wall_sculpture_customisation_policy','platform_write_holds','current_asset_reference_map','current_native_reference_map',
    'physical_stock_quantity','all_actual_specifications_complete','current_working_design_group_projection']:
    assert p[key]==old[key],key
fields=['latest_owner_depth_estimate_import','current_working_depth_status','latest_workbook_validation','current_individual_sculpture_list',
    'current_specification_verification','current_image_review_links','current_guided_image_review','current_authenticated_squarespace_inventory_observation',
    'current_local_draft_completion','current_published_gallery_projection','next_catalogue_actions','latest_master_metadata_change']
updates={}
for label in ['review_progress','component_checkpoint','checkpoint']:
    path=Path(m[label]['path']);value=read(path);value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p),
        current_master_register=p['register'],current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
    for key in fields:value[key]=copy.deepcopy(p[key])
    updates[path]=value
write(H/'prepared-pointer.json',p)
if '--apply'not in sys.argv:print('PASS_PREPARED_DEPTH_PUBLICATION_GUARDS');raise SystemExit(0)
changed=[]
try:
    for key,x in m.items():assert sha(x['path'])==x['sha256'],key
    target=B/p['workbook'];temp=target.with_name(target.name+'.depth-tmp');shutil.copy2(H/'master-workbook.pending',temp);os.replace(temp,target);changed.append(('master_workbook',target))
    for path,value in updates.items():
        write(path,value);changed.append((next(k for k in ['review_progress','component_checkpoint','checkpoint']if m[k]['path']==str(path)),path))
    write(B/'current-master.json',p);changed.append(('pointer',B/'current-master.json'))
    assert read(B/'current-master.json')==p and sha(target)==p['workbook_sha256'] and sha(B/p['register'])==p['register_sha256']
    for path,value in updates.items():assert read(path)==value and value['current_master_catalogue']==p
    receipt={'status':'PASS14_DEPTH_ESTIMATES_PUBLISHED_AND_READ_BACK','recorded_utc':p['recorded_utc'],'current_master_pointer_sha256':sha(B/'current-master.json'),
        'preceding_pointer_sha256':m['pointer']['sha256'],'register':str(B/p['register']),'register_sha256':p['register_sha256'],
        'workbook':str(target),'workbook_sha256':p['workbook_sha256'],'controls_sha256':{str(path):sha(path)for path in updates},'independent_qa':qa,
        'depth_estimate_field_objects':14,'other_field_objects_unchanged':1120,'new_physical_measurements':0,
        'actual_input_fields_preserved':True,'active_options':188,'retained_rows':189,'component_records':112,'working_groups':110,
        'sheets':28,'formulas':3407,'native_hyperlinks':12206,'authored_cells':55,'calculated_cells':14,'planned_row_heights':27,'new_native_targets':0,'external_writes':0}
    write(H/'publication-receipt.json',receipt);print(json.dumps(receipt,indent=2))
except BaseException:
    for label,path in reversed(changed):temp=path.with_name(path.name+'.depth-rollback');shutil.copy2(m[label]['snapshot'],temp);os.replace(temp,path)
    raise
