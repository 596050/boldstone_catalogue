"""Bind the final188-option working catalogue, listing package and reader checks."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import zipfile

H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json');g=read(B/p['register']);old=read(H/'inputs/master_register.before')
expected={(r['product_id'],r['field']):r for r in read(H/'specification-completion-packet.json')['changes']};changed=[];unchanged=0
for before,after in zip(old['options'],g['options']):
    assert {k:v for k,v in before.items()if k!='master_fields'}=={k:v for k,v in after.items()if k!='master_fields'}
    for field,value in before['master_fields'].items():
        current=after['master_fields'][field];key=(after['product_id'],field)
        if current==value:unchanged+=1
        else:
            assert key in expected and value==expected[key]['before']and current==expected[key]['after']
            assert current['physical_verification']==value['physical_verification']==0
            if field=='Dimensions / depth':assert current['depth_estimate']==value['depth_estimate']
            changed.append(key)
assert len(changed)==30 and unchanged==1104
assert set(g)-set(old)=={'latest_working_specification_completion','current_listing_treatment_plan'}
assert all(g[k]==old[k]for k in old if k!='options')
assert len(g['active_option_ids'])==188 and len(g['options'])==189 and len(g['original_review_specification_assertions'])==1668
for key in ['register','workbook']:assert sha(B/p[key])==p[key+'_sha256']
for key in ['current_asset_reference_map','current_native_reference_map']:assert sha(B/p[key]['path'])==p[key]['sha256']
controls={}
for path in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']:
    assert read(B/path)['current_master_catalogue']==p;controls[path]=sha(B/path)
package=read(H/'listing-package-reference.json');assert sha(package['path'])==package['sha256'];seal=read(package['path'])
for item in seal['files']:assert sha(item['path'])==item['sha256'],item['path']
plan=read(g['current_listing_treatment_plan']['register']);options={o['product_id']:o for o in g['options']}
assert len(plan['options'])==188
for row in plan['options']:assert row['accepted_working_fields']==options[row['product_id']]['master_fields']and not row['native_execution_allowed']
for book in [B/p['workbook'],Path(package['workbook']['path'])]:
    with zipfile.ZipFile(book)as z:assert z.testzip()is None
qa=B/'components/parallel-reviews/matched-listing-publication-qa-20261025-B/published-readback.json';q=read(qa)
assert q['status'].startswith('PASS')
accept=B.parent/'reports/catalogue-terminal-walkthrough-20261024/current-reader-acceptance.json';a=read(accept)
assert a['status']=='PASS_CURRENT_READERS_AND_RELEASE_BINDINGS'and not a['local_link_failures']
assert a['pointer_sha256']==sha(B/'current-master.json')and a['register_sha256']==p['register_sha256']and a['workbook_sha256']==p['workbook_sha256']
assert a['main_work_items']==107 and not a['unchanged_shopify_runs_reused']and a['shopify_product_terminal_runs']==38
for path,digest in a['files'].items():assert sha(path)==digest,path
actual=read(H/'actual-input-verification.json');assert actual['all_original_actual_measurement_fields_preserved']and actual['new_actual_measurements']==0 and sha(actual['current_path'])==actual['current_sha256']
text=(H/'terminal-proposals-readout.txt').read_text();assert text.count('PROPOSAL ')==text.count('Containing folder: https://www.dropbox.com/')==30
result={'status':'PASS_CURRENT188_WORKING_CATALOGUE_AND_LISTING_EXPORTS','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'pointer_sha256':sha(B/'current-master.json'),'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],'controls_sha256':controls,
    'active_options':188,'retained_rows':189,'component_records':112,'working_design_groups':110,'working_fields':1128,
    'working_material_proposals_added':27,'working_face_size_estimates_added':3,'other_retained_field_objects_unchanged':1104,'new_physical_measurements':0,
    'all_six_working_fields_recorded':True,'actual_specifications_complete':False,'source_assertions_unchanged':1668,'native_or_platform_writes':0,
    'listing_treatments':188,'existing_individual_records':47,'qualified_working_pattern_mappings':4,'proposed_new_or_additional_options':135,'explicit_native_binding_exceptions':2,
    'context_holds':22,'series_holds':1,'listing_package':package,'independent_published_readback':{'path':str(qa),'sha256':sha(qa)},
    'terminal_reader_acceptance':{'path':str(accept),'sha256':sha(accept)},'terminal_proposal_rows_walked':30,
    'listing_workbook_sha256':package['workbook']['sha256'],'catalogue_csv_sha256':package['catalogue_csv']['sha256']}
(H/'final-closeout.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k not in ['listing_package','controls_sha256']},indent=2))
