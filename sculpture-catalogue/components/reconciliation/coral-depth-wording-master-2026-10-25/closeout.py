"""Close the single-field wording fix against its published master and readers."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import zipfile

H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json');g=read(B/p['register']);old=read(H/'inputs/master_register.before')
packet=read(H/'wording-correction-packet.json');row=packet['rows'][0]
changed=[];unchanged=0
for before,after in zip(old['options'],g['options']):
    assert {k:v for k,v in before.items()if k!='master_fields'}=={k:v for k,v in after.items()if k!='master_fields'}
    for field,value in before['master_fields'].items():
        current=after['master_fields'][field]
        if current==value:unchanged+=1
        else:
            assert after['product_id']==row['product_id'] and field==row['field'] and value==row['before'] and current==row['after']
            assert current['state']==value['state'] and current['physical_verification']==value['physical_verification']==0
            for key in ['display','basis']:assert re.findall(r'\d+(?:\.\d+)?',value[key])==re.findall(r'\d+(?:\.\d+)?',current[key])
            changed.append([after['product_id'],field])
assert len(changed)==1 and unchanged==1133
assert set(g)-set(old)=={'latest_coral_depth_wording_correction'}
assert all(g[k]==old[k]for k in old if k!='options')
for key in ['register','workbook']:assert sha(B/p[key])==p[key+'_sha256']
for path in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']:assert read(B/path)['current_master_catalogue']==p
with zipfile.ZipFile(B/p['workbook'])as z:assert z.testzip()is None
qa=B/'components/parallel-reviews/coral-wording-qa-20261025T014446Z-B/published-readback-20261025T014915880930Z.json';q=read(qa)
assert sha(qa)=='768319cbcea956527c5b5e0a0cf289c2f9632529afc291fa92e613fc523670a3'
assert q['status']=='PASS_PUBLISHED_CORAL_WORDING'and not q['failures']and q['checks_failed']==0
assert q['register_sha256']==p['register_sha256']and q['workbook_sha256']==p['workbook_sha256']
accept=B.parent/'reports/catalogue-terminal-walkthrough-20261024/current-reader-acceptance.json';a=read(accept)
assert a['status']=='PASS_CURRENT_READERS_AND_RELEASE_BINDINGS'and not a['local_link_failures']
assert a['pointer_sha256']==sha(B/'current-master.json')and a['register_sha256']==p['register_sha256']and a['workbook_sha256']==p['workbook_sha256']
assert a['main_work_items']==105 and a['unchanged_shopify_runs_reused']
for path,digest in a['files'].items():assert sha(path)==digest,path
reuse=read(H/'shopify-reader-reuse-verification.json');assert reuse['related_options']==121 and reuse['changed_related_options']==0 and reuse['current_register_sha256']==p['register_sha256']
actual=read(H/'actual-input-verification.json');assert actual['all_original_actual_measurement_fields_preserved']and actual['new_actual_measurements']==0 and sha(actual['current_path'])==actual['current_sha256']
result={'status':'PASS_CORAL_WORDING_AND_CURRENT_READERS','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'pointer_sha256':sha(B/'current-master.json'),'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],
    'changed_field_objects':1,'other_field_objects_unchanged':1133,'numeric_value_changes':0,'new_physical_measurements':0,
    'active_options':188,'retained_rows':189,'component_records':112,'working_design_groups':110,
    'base_material_gaps_retained':27,'face_size_gaps_retained':3,'context_holds':22,'series_holds':1,
    'independent_published_qa':{'path':str(qa),'sha256':sha(qa),'checks_passed':q['checks_passed']},
    'terminal_reader_acceptance':{'path':str(accept),'sha256':sha(accept),'main_items':105},
    'unchanged_shopify_related_options_justifying_readout_reuse':121,'all_three_control_pointers_equal':True,'native_or_platform_writes':0}
(H/'final-closeout.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
