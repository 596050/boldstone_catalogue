"""Check the final reference-map schema and the narrowly allowed catalogue edits."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
N = B.parent / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks = 0
failures = []
def check(ok, name):
    global checks
    checks += 1
    if not ok:
        failures.append(name)

original = read(H/'inputs/master_register.before')
candidate = read(H/'canonical-master-register.json')
before = read(H/'inputs/navigation-candidate-before-gallery-metadata.json')
check(candidate['options'] == before['options'], 'All189 option objects equal independently checked navigation candidate')
check(candidate['summary'] == original['summary'], 'Original option/component/group counts')
check(candidate['original_review_specification_assertions'] == original['original_review_specification_assertions'], 'All original source assertions')
allowed = {
    'BSI-D5A939264C82': {'file_id','image_url','current_link_basis','current_primary_navigation','context_image_url','context_folder_url'},
    'BSI-65520F070145': {'file_id','image_url','current_link_basis','current_primary_navigation'},
    'BSI-C02D6DF365D3': {'context_image_url','context_folder_url'},
    'BSI-EBD43DF0704F': {'current_context_navigation'},
}
option_changes = []
for old, new in zip(original['options'], candidate['options']):
    check(old['product_id'] == new['product_id'], 'Original row position '+old['product_id'])
    diff = {k for k in set(old)|set(new) if old.get(k) != new.get(k)}
    check(diff <= allowed.get(old['product_id'], set()), 'Allowed option navigation scope '+old['product_id'])
    for k in ['master_fields','specifications','selling_details','name','canonical_component_id','photo_coverage']:
        check(old[k] == new[k], 'Preserved '+k+' '+old['product_id'])
    if diff:
        option_changes.append({'option_id':old['product_id'], 'changed_keys':sorted(diff)})
check(len(candidate['options']) == 189 and len(candidate['active_option_ids']) == 188, '188 active/189 retained')
audit = read(H/'image-coverage-current.json')
check(audit['counts'] == read(H/'inputs/coverage.before')['counts'], 'All dated coverage counters and owner deferrals retained')
check(audit['current_complete_gallery_mapping'] == candidate['current_complete_gallery_mapping'], 'Register and audit complete-gallery evidence agree')

fresh = read(N/'complete-current-native-object-map.json')
native_before = read(H/'inputs/native_map.before')
native = read(H/'current-native-reference-map.json')
objects = native['current_objects']
check(set(objects) == set(native_before['current_objects']) | set(fresh), 'Cumulative native stable-ID union')
check(len(objects) == 7061 and len(fresh) == 6802, '7061 cumulative/6802 current native objects')
for key, value in native_before.items():
    if key not in ['status','current_objects','old_path_to_id']:
        check(native.get(key) == value, 'Retained historical wrapper '+key)
for path, fid in native_before['old_path_to_id'].items():
    check(native['old_path_to_id'].get(path) == fid, 'Retained historical path '+path)
for fid, old in native_before['current_objects'].items():
    for key, value in old.items():
        if key not in fresh.get(fid, {}) and key not in ['current_wall_snapshot_present','current_wall_snapshot_verified_utc','absence_does_not_establish_deletion_or_global_unavailability']:
            check(objects[fid].get(key) == value, 'Retained native history '+fid+' '+key)
for fid, item in fresh.items():
    for key, value in item.items():
        check(objects[fid].get(key) == value, 'Current native field '+fid+' '+key)

assets_old = read(H/'inputs/asset_map.before')
assets = read(H/'current-assets.json')
files = {fid:item for fid,item in fresh.items() if item.get('object_type') == 'file'}
evidence = {row['file_id']:row for row in read(N/'current-6360-visual-source-evidence.json')}
check(len(files) == 6360 and len(assets) == 6690, '6360 current/6690 cumulative assets')
check(set(assets) == set(assets_old)|set(files), 'All6656 old asset IDs retained plus34 newly represented IDs')
for fid, item in files.items():
    for key in ['name','path','display_path','folder_id','image_url','folder_url']:
        check(assets[fid][key] == item[key], 'Current asset field '+fid+' '+key)
    check(assets[fid]['folder_path'] == 'ns:202238505/'+item['folder_path'], 'Current containing folder '+fid)
    check(assets[fid]['source_content_hash'] == evidence[fid]['native_content_hash'], 'Current native content hash '+fid)
    check(assets[fid]['current_visual_source_binding'] == evidence[fid], 'Visual source binding '+fid)
    if assets_old.get(fid, {}).get('source_content_hash'):
        check(assets_old[fid]['source_content_hash'] == assets[fid]['source_content_hash'], 'Retained encoded old hash '+fid)
for fid in set(assets_old)-set(files):
    for key,value in assets_old[fid].items():
        if key not in ['current_wall_snapshot_present','current_wall_snapshot_absence_scope','absence_does_not_establish_deletion_or_global_unavailability']:
            check(assets[fid].get(key) == value, 'Retained out-of-scope asset history '+fid+' '+key)

for name, record in read(H/'input-manifest.json').items():
    check(sha(record['path']) == sha(record['snapshot']) == record['sha256'], 'Live baseline guard '+name)
result = {'status':'FAIL' if failures else 'PASS', 'recorded_utc':datetime.now(timezone.utc).isoformat(),
    'checks_passed':checks-len(failures), 'checks_total':checks, 'failures':failures[:50],
    'register_sha256':sha(H/'canonical-master-register.json'), 'audit_sha256':sha(H/'image-coverage-current.json'),
    'workbook_sha256':sha(H/'master-workbook.pending'), 'asset_map_sha256':sha(H/'current-assets.json'),
    'native_map_sha256':sha(H/'current-native-reference-map.json'), 'native_wrapper_schema_verified':True,
    'cumulative_native_objects':7061, 'cumulative_assets':6690, 'current_wall_files':6360,
    'option_navigation_changes':option_changes, 'physical_commercial_or_identity_changes':0,
    'canonical_or_external_writes':0}
(H/'final-data-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if failures:
    raise SystemExit(1)
