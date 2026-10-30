"""Correct an inherited map description; preserve every published data artifact."""
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[3]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.map-summary-tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)

assert not (H / 'publication-receipt.json').exists()
pointer = B / 'current-master.json'
assert sha(pointer) == 'b101dd57eb7e768c69e9f1603f6069727463a67a4bb7a36b1040ecef2766399b'
old = read(pointer)
p = copy.deepcopy(old)
controls = [B / x for x in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
(H / 'inputs').mkdir(exist_ok=True)
manifest = {}
paths = {'pointer': pointer, 'register': B / old['register'], 'workbook': B / old['workbook'],
         'native_map': B / old['current_native_reference_map']['path'], 'asset_map': B / old['current_asset_reference_map']['path'],
         'audit': Path(old['latest_image_coverage_audit']['path']), **{f'control_{i}': x for i, x in enumerate(controls)}}
for key, path in paths.items():
    snapshot = H / 'inputs' / (key + '.before')
    snapshot.write_bytes(path.read_bytes())
    manifest[key] = {'path': str(path), 'snapshot': str(snapshot), 'sha256': sha(path)}
write(H / 'input-manifest.json', manifest)
prior = {k: v for k, v in old['current_native_reference_map'].items() if k not in ['path', 'sha256']}
p['current_native_reference_map'] = {
    'path': old['current_native_reference_map']['path'], 'sha256': old['current_native_reference_map']['sha256'],
    'scope': 'Cumulative current map with190 existing Echo Sound native objects newly represented, including180files/9childfolders/familyroot. The23 approved file moves are current. Prior4300 map objects retained.',
    'latest_scope': 'Echo Sound within BOLDSTONE MASTER/Products/01 Wall Sculptures',
    'fresh_metadata_objects_in_latest_scope': 190, 'complete_current_family_listings_in_latest_scope': 1,
    'same_id_file_paths_refreshed_in_latest_scope': 23, 'actual_file_parent_changes_in_latest_scope': 23,
    'actual_folder_parent_changes_in_latest_scope': 0, 'new_native_folders': 0, 'new_catalogue_options': 0,
    'global_all_source_original_bytes_rehashed': False,
    'Echo_originals_verified_by_native_lane': 180, 'Echo_local_originals_rehashed_by_importer': 23,
    'native_writes_by_master_import': 0, 'historical_scope_observation': prior,
}
p['recorded_utc'] = datetime.now(timezone.utc).isoformat()
p['publication_receipt'] = str((H / 'publication-receipt.json').relative_to(B))
p['latest_master_metadata_change'] = {'status': 'ECHO_NATIVE_MAP_SUMMARY_SCOPE_CORRECTED_ONLY',
    'path': p['publication_receipt'], 'preceding_publication_receipt': old['publication_receipt'],
    'catalogue_register_workbook_audit_and_native_asset_maps_unchanged': True}
allowed = {'current_native_reference_map', 'recorded_utc', 'publication_receipt', 'latest_master_metadata_change'}
assert {k: v for k, v in p.items() if k not in allowed} == {k: v for k, v in old.items() if k not in allowed}
updates = {}
for dest in controls:
    d = read(dest)
    assert d['current_master_catalogue'] == old
    d.update(updated_utc=p['recorded_utc'], current_master_catalogue=copy.deepcopy(p),
        current_native_reference_map=copy.deepcopy(p['current_native_reference_map']),
        latest_master_metadata_change=copy.deepcopy(p['latest_master_metadata_change']))
    updates[dest] = d
write(H / 'prepared-pointer.json', p)
for key, x in manifest.items():
    assert sha(x['path']) == x['sha256'], key
for dest, value in updates.items():
    write(dest, value)
write(pointer, p)
assert read(pointer) == p and all(read(x)['current_master_catalogue'] == p for x in controls)
for key in ['register', 'workbook', 'native_map', 'asset_map', 'audit']:
    assert sha(manifest[key]['path']) == manifest[key]['sha256']
receipt = {'status': 'PASS_PUBLISHED_AND_READ_BACK', 'publication_mode': 'MAP_SUMMARY_SCOPE_ADDENDUM_ONLY',
    'recorded_utc': p['recorded_utc'], 'preceding_publication_receipt': old['publication_receipt'],
    'preceding_pointer_sha256': manifest['pointer']['sha256'], 'current_master_pointer_sha256': sha(pointer),
    'register': str(B / p['register']), 'register_sha256': p['register_sha256'],
    'workbook': str(B / p['workbook']), 'workbook_sha256': p['workbook_sha256'],
    'audit_sha256': manifest['audit']['sha256'], 'controls_sha256': {str(x): sha(x) for x in controls},
    'all_five_data_artifacts_byte_identical': True, 'new_native_or_platform_writes': 0,
    'active_options': 188, 'retained_component_ids': 112, 'working_design_groups': 110}
write(H / 'publication-receipt.json', receipt)
write(H / 'post-publication-readback.json', {'status': 'PASS', 'pointer_and_three_controls_equal_candidate': True,
    'map_summary': p['current_native_reference_map'], 'all_five_data_artifacts_byte_identical': True,
    'current_pointer_sha256': sha(pointer)})
print(json.dumps(receipt))
