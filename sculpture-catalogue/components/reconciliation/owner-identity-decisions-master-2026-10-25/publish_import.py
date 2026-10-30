"""Publish the four exact owner answers after saved-workbook and independent QA."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

H = Path(__file__).resolve().parent
B = H.parents[2]
OUT = B/'outputs'/H.name
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
def write(path,value):
    path = Path(path)
    temp = path.with_name(path.name+'.owner-identity-tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(temp,path)

assert not (H/'publication-receipt.json').exists()
m = read(H/'input-manifest.json')
old = read(m['pointer']['snapshot'])
g = read(H/'canonical-master-register.json')
audit = read(H/'image-coverage-current.json')
s = read(H/'import-summary.json')
v = read(H/'saved-workbook-verification.json')
r = read(H/'report-verification.json')
assert v['status'] == 'PASS' and not v['failures']
assert r['status'] == 'PASS_CURRENT_OWNER_DECISION_REPORTS' and not r['failures']
assert len(s['decisions']) == 4 and s['remaining_owner_decision_ids'] == []
for key,name in [('workbook_sha256','master-workbook.pending'),('register_sha256','canonical-master-register.json'),('audit_sha256','image-coverage-current.json')]:
    assert v[key] == sha(H/name),key
assert r['register_sha256'] == v['register_sha256'] and r['audit_sha256'] == v['audit_sha256']
for x in r['pages']+r['csv_files']+[r['current_count_summary']]:
    assert sha(x['path']) == x['sha256']
for x in s['decisions']:
    assert sha(x['seal']) == x['seal_sha256'] and sha(x['answer_path']) == x['answer_sha256']
qa = read(H/'independent-qa-reference.json')
assert sha(qa['path']) == qa['sha256']
assert sha(qa['seal_path']) == qa['seal_sha256']
q = read(qa['path'])
assert q['status'].startswith('PASS')
assert q['workbook_sha256'] == v['workbook_sha256'] and q['register_sha256'] == v['register_sha256']
for key,x in m.items():
    assert sha(x['path']) == sha(x['snapshot']) == x['sha256'],key

p = copy.deepcopy(old)
p.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT_MASTER188_FOUR_OWNER_IDENTITY_DECISIONS_IMPORTED',
    register=rel(H/'canonical-master-register.json'),register_sha256=v['register_sha256'],workbook_sha256=v['workbook_sha256'],
    publication_receipt=rel(H/'publication-receipt.json'),summary=copy.deepcopy(g['summary']),
    latest_owner_identity_decision_import={**s,'status':'PUBLISHED_OWNER_ANSWERS_AND_READ_BACK',
        'independent_qa':qa,'verification':rel(H/'saved-workbook-verification.json'),
        'verification_sha256':sha(H/'saved-workbook-verification.json')},
    latest_workbook_validation={'saved_workbook':{'path':rel(H/'saved-workbook-verification.json'),'sha256':sha(H/'saved-workbook-verification.json')},
        'independent_owner_import':qa})
p['latest_image_coverage_audit'] = {**old['latest_image_coverage_audit'],'path':str(H/'image-coverage-current.json'),
    'audit':rel(H/'image-coverage-current.json'),'audit_sha256':v['audit_sha256'],'counts':audit['counts'],
    'status':'OWNER_DESIGN_IDENTITY_RESOLVED_SHARED_REFERENCE_QUALIFIED_CONTEXT_AND_SERIES_HOLDS_UNCHANGED'}
p['current_working_design_group_projection'] = {**old['current_working_design_group_projection'],
    'path':rel(H/'working-design-group-projection.json'),'sha256':sha(H/'working-design-group-projection.json'),
    'owner_equivalence_edges':3,'review':rel(OUT/'owner-identity-decisions.html'),
    'groups_csv':rel(OUT/'Current_Working_Design_Groups_110.csv'),
    'legacy_FFL1_now_joins_existing_FFS2_group':True,'group_count_delta':0,
    'scope':'112 previously identified component records remain110 working groups. FFL1 was previously outside that identified list and now refers to existing FFS2;188 option records are retained.'}
p['current_individual_sculpture_list'].update(recorded_utc=p['recorded_utc'],register=p['register'],
    register_sha256=p['register_sha256'],workbook_sha256=p['workbook_sha256'],publication_receipt=p['publication_receipt'],
    current_option_list=rel(OUT/'Current_Individual_Options_188.csv'),current_option_list_sha256=sha(OUT/'Current_Individual_Options_188.csv'),
    count_summary=rel(OUT/'current-count-summary.json'),count_summary_sha256=sha(OUT/'current-count-summary.json'))
links = p['current_image_review_links']
links.update(all_links=rel(OUT/'index.html'),individual_image_gaps=rel(OUT/'individual-images.html'),
    missing_in_situ_images=rel(OUT/'in-situ-images.html'),missing_series_images=rel(OUT/'series-images.html'),
    specifications_to_verify=rel(OUT/'specifications-to-verify.html'),
    remaining_photograph_brief=rel(OUT/'remaining-photograph-requests.html'),
    latest_owner_identity_decisions=rel(OUT/'owner-identity-decisions.html'),
    verification=rel(H/'report-verification.json'),verification_sha256=sha(H/'report-verification.json'))
links['counts'].update(individual_gaps=0,existing_image_checks=0,required_actions=23,resolved_actions=114,
    owner_identity_decisions_imported=4,unresolved_owner_identity_questions_in_resumed_batch=0,
    shared_design_references_not_separate_selected_primaries=1)
p['current_guided_image_review'].update(deferred_legacy_identity=0,deferred_individual_identity_cases=0,current_individual_gaps=0,
    active_owner_question=None,owner_identity_questions_in_resumed_batch_remaining=0,
    source_question_coordination='The four resumed identity decisions are answered and imported. Preserve22 context and1 series deferrals. Actual physical questions remain separate.',
    terminal_review_command=rel(H/'walkthrough.py'),terminal_review_command_sha256=sha(H/'walkthrough.py'),
    latest_owner_identity_decisions=rel(OUT/'owner-identity-decisions.html'))
p['current_specification_verification'].update(path=rel(H/'report-verification.json'),sha256=sha(H/'report-verification.json'),
    review=rel(OUT/'specifications-to-verify.html'),field_checklist=rel(OUT/'Specification_Verification_Checklist_1128_Fields.csv'),
    identity_wording_field_objects_updated=3,new_physical_measurements_added=0,new_physical_verifications=0,
    commercial_values_changed_in_this_refresh=0)
p['current_authenticated_squarespace_inventory_observation'].update(register=p['register'],register_sha256=p['register_sha256'])
p['current_local_draft_completion']['latest_owner_identity_note'] = rel(OUT/'owner-identity-decisions.html')
p['current_local_draft_completion']['no_new_native_drafts_or_variant_assignments'] = True
p['current_source_association_scope']['legacy_FFL1_identity_answer_status'] = 'OWNER_CONFIRMED_SAME_RELIEF_DESIGN_NOT_A_NEW_EXACT_SOURCE_OFFER_MATCH'
p['current_source_association_scope']['latest_owner_resolution_review'] = rel(OUT/'owner-identity-decisions.html')
p['current_published_gallery_projection']['status'] = 'FROZEN_GALLERY_SOURCE_EVIDENCE_BEFORE_LATEST_OWNER_IDENTITY_DECISIONS'
p['current_published_gallery_projection']['latest_owner_option_projection'] = rel(OUT/'index.html')
p['current_published_gallery_projection']['source_photo_proof_unchanged'] = True
def refresh_paths(value):
    if isinstance(value,dict):
        return {k:refresh_paths(v) for k,v in value.items()}
    if isinstance(value,list):
        return [refresh_paths(v) for v in value]
    if isinstance(value,str) and value.endswith(('.html','.csv')):
        match = OUT/Path(value).name
        if match.is_file():
            return rel(match)
    return value
p['current_missing_picture_lists'] = refresh_paths(p['current_missing_picture_lists'])
p['current_missing_picture_lists'].update(required_actions=23,verify_existing=0,individual_gaps=0,legacy_binding_deferred=False,
    gap_views_overlap_on_legacy_individual_identity=False,current_resolved_actions=114,
    current_owner_resolution_scope='FFL1 relief identity resolved.22 context and1 series cases remain held; no separate legacy primary selected. Technical source-photo limitations remain qualified.')
p['next_catalogue_actions'] = [
    'All four resumed owner identity questions are answered. Preserve the exact name/relief scope; no forced native swatch alias or exact platform variant assignment.',
    'Retain22 held installation and1 held series requirements. FFL1 has a qualified shared-design reference; no separate primary or historical cast photograph is certified.',
    'Continue source/configuration verification separately from names:29 Squarespace/3 Shopify exact-photo uncertainties,4 uncertain native roles,65 component-source gaps and625 family-scope files remain qualified.',
    'Verify actual dimensions/depth, bare-panel weight, material and fitted fixing. All working numerical values, estimate labels and commercial policies remain unchanged.',
    'Keep the Squarespace write hold. No platform, stock, native file or folder write is authorized or performed by these identity answers.']
p['latest_master_metadata_change'] = {'status':'SUPERSEDED_BY_FOUR_EXACT_OWNER_IDENTITY_DECISIONS','preceding_receipt':old['publication_receipt']}
for key in ['current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_global_context_owner_hold','platform_write_holds',
    'current_option_count','retained_option_count','physical_stock_quantity','whole_library_unique_design_total','all_actual_specifications_complete',
    'current_asset_reference_map','current_native_reference_map','current_individual_photo_capture_policy']:
    assert p[key] == old[key],key
updates = {}
fields = ['summary','latest_owner_identity_decision_import','latest_workbook_validation','latest_image_coverage_audit',
    'current_working_design_group_projection','current_individual_sculpture_list','current_image_review_links','current_guided_image_review',
    'current_specification_verification','current_authenticated_squarespace_inventory_observation','current_local_draft_completion',
    'current_source_association_scope','current_published_gallery_projection','current_missing_picture_lists','next_catalogue_actions','latest_master_metadata_change']
for label in ['review_progress','component_checkpoint','checkpoint']:
    dest = Path(m[label]['path'])
    value = read(dest)
    value.update(updated_utc=p['recorded_utc'],current_master_catalogue=copy.deepcopy(p),current_master_register=p['register'],
        current_master_workbook=p['workbook'],current_individual_catalogue_count=copy.deepcopy(p['current_individual_sculpture_list']))
    for key in fields:
        value[key] = copy.deepcopy(p[key])
    updates[dest] = value
write(H/'prepared-pointer.json',p)
if '--apply' not in sys.argv:
    print('PASS_ALL_PUBLICATION_GUARDS_PREPARED_ONLY')
    raise SystemExit(0)
changed = []
try:
    for label,x in m.items():
        assert sha(x['path']) == x['sha256'],label
    target = B/p['workbook']
    temp = target.with_name(target.name+'.owner-identity-tmp')
    shutil.copy2(H/'master-workbook.pending',temp)
    os.replace(temp,target)
    changed.append(('master_workbook',target))
    for dest,value in updates.items():
        write(dest,value)
        label = next(k for k in ['review_progress','component_checkpoint','checkpoint'] if m[k]['path'] == str(dest))
        changed.append((label,dest))
    write(B/'current-master.json',p)
    changed.append(('pointer',B/'current-master.json'))
    assert read(B/'current-master.json') == p
    assert sha(target) == p['workbook_sha256'] and sha(B/p['register']) == p['register_sha256']
    for dest,value in updates.items():
        assert read(dest) == value and value['current_master_catalogue'] == p
    receipt = {'status':'PASS_FOUR_OWNER_IDENTITY_DECISIONS_PUBLISHED_AND_READ_BACK','recorded_utc':p['recorded_utc'],
        'current_master_pointer_sha256':sha(B/'current-master.json'),'preceding_pointer_sha256':m['pointer']['sha256'],
        'register':str(B/p['register']),'register_sha256':p['register_sha256'],'workbook':str(target),'workbook_sha256':p['workbook_sha256'],
        'audit_sha256':v['audit_sha256'],'controls_sha256':{str(x):sha(x) for x in updates},'independent_qa':qa,
        'owner_decisions':[x['decision_id'] for x in s['decisions']],'active_options':188,'retained_options':189,
        'component_records':112,'working_design_groups':110,'field_identity_wording_updates':3,'other_working_field_objects_unchanged':1131,
        'new_physical_or_commercial_numeric_values':0,'new_selected_primary_images':0,'context_holds':22,'series_holds':1,
        'sheets':28,'formulas':3407,'native_hyperlinks':12206,'authored_cell_changes':v['planned_value_changes'],'new_native_link_targets':0,'external_writes':0}
    write(H/'publication-receipt.json',receipt)
    write(OUT/'publication-state.json',{'status':'PUBLISHED_AND_READ_BACK','receipt':str(H/'publication-receipt.json'),
        'receipt_sha256':sha(H/'publication-receipt.json'),'current_master_pointer_sha256':sha(B/'current-master.json')})
    print(json.dumps(receipt,indent=2))
except BaseException:
    for label,dest in reversed(changed):
        temp = dest.with_name(dest.name+'.owner-identity-rollback')
        shutil.copy2(m[label]['snapshot'],temp)
        os.replace(temp,dest)
    raise
