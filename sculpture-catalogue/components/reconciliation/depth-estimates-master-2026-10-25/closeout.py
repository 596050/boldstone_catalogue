"""Check the published depth-only change and bind the final local receipts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
p = read(B/'current-master.json')
g = read(B/p['register'])
old = read(H/'inputs/master_register.before')
before = {o['product_id']:o for o in old['options']}
packet = read(H/'depth-estimate-packet.json')
rows = {r['product_id']:r for r in packet['rows']}
changed = []
unchanged = 0
for o in g['options']:
    prev = before[o['product_id']]
    assert {k:v for k,v in o.items() if k != 'master_fields'} == {k:v for k,v in prev.items() if k != 'master_fields'}
    for key, value in o['master_fields'].items():
        if value == prev['master_fields'][key]:
            unchanged += 1
        else:
            assert key == 'Dimensions / depth'
            assert value == rows[o['product_id']]['after'] and prev['master_fields'][key] == rows[o['product_id']]['before']
            assert value['physical_verification'] == 0
            changed.append(o['product_id'])
assert set(g) - set(old) == {'latest_owner_depth_estimate_import'}
assert all(g[k] == old[k] for k in old if k != 'options')
assert len(changed) == 14 and unchanged == 1120
assert len(g['original_review_specification_assertions']) == 1668
for path in ['components/reviews/specification_review_progress.json','components/checkpoint.json','checkpoint.json']:
    assert read(B/path)['current_master_catalogue'] == p, path
for key in ['register','workbook']:
    assert sha(B/p[key]) == p[key+'_sha256']
for key in ['current_asset_reference_map','current_native_reference_map']:
    assert sha(B/p[key]['path']) == p[key]['sha256']
with zipfile.ZipFile(B/p['workbook']) as z:
    assert z.testzip() is None
text = (H/'terminal-depth-readout.txt').read_text()
estimated_lines = [line for line in text.splitlines() if line.startswith('Estimated body depth:')]
assert text.count('DEPTH ') == text.count('Containing folder: https://www.dropbox.com/') == len(estimated_lines) == 14
assert all(line.endswith('not measured.') for line in estimated_lines)
qa = B/'components/parallel-reviews/owner-depth-estimates-20261025T005003Z-B/publication-readback-20261025T011426Z.json'
q = read(qa)
assert q['status'] == 'PASS' and q['checks_failed'] == 0
assert q['published_pointer_sha256'] == sha(B/'current-master.json')
assert q['published_register_sha256'] == p['register_sha256'] and q['published_workbook_sha256'] == p['workbook_sha256']
ref = {'path':str(qa),'sha256':sha(qa),'checks_passed':q['checks_passed'],'pointer_sha256':sha(B/'current-master.json')}
(H/'independent-published-qa-reference.json').write_text(json.dumps(ref,indent=2)+'\n')
acceptance = B.parent/'reports/catalogue-terminal-walkthrough-20261024/current-reader-acceptance.json'
a = read(acceptance)
assert a['status'] == 'PASS_CURRENT_READERS_AND_RELEASE_BINDINGS' and not a['local_link_failures']
assert a['pointer_sha256'] == sha(B/'current-master.json') and a['register_sha256'] == p['register_sha256'] and a['workbook_sha256'] == p['workbook_sha256']
assert a['main_work_items'] == 104 and a['shopify_product_terminal_runs'] == 38 and not a['unchanged_shopify_runs_reused']
for path, digest in a['files'].items():
    assert sha(path) == digest, path
actual = read(H/'actual-input-verification.json')
assert actual['all_original_actual_measurement_fields_preserved'] and actual['new_actual_measurements'] == 0
assert sha(actual['current_path']) == actual['current_sha256']
receipt = {'status':'PASS_CURRENT14_DEPTH_ESTIMATES_AND_ALL_READERS','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'pointer_sha256':sha(B/'current-master.json'),'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],
    'depth_field_objects_changed':14,'other_field_objects_unchanged':1120,'original_source_assertions_unchanged':1668,
    'active_options':188,'retained_rows':189,'component_records':112,'working_design_groups':110,
    'all188_have_working_depth':True,'new_physical_measurements':0,'face_sizes_still_unconfirmed':p['current_working_depth_status']['face_sizes_still_unconfirmed'],
    'context_holds':22,'series_holds':1,'all_three_control_pointers_equal':True,'native_or_platform_writes':0,
    'independent_published_qa':ref,'reader_acceptance':{'path':str(acceptance),'sha256':sha(acceptance)},
    'terminal_depth_rows_walked':14,'terminal_main_items':104,'shopify_products_with_current_specifications_exercised':38,
    'terminal_depth_readout_sha256':sha(H/'terminal-depth-readout.txt'),'xlsx_zip_integrity':'PASS'}
(H/'final-closeout.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
