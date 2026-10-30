"""Check only the published Echo descriptor addendum and its unchanged data."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
H = BASE / 'components/reconciliation/echo-sound-approved-navigation-metadata-2026-10-24'
ADD = H / 'native-map-summary-addendum'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks = []
def check(name, condition):
    assert condition, name
    checks.append(name)

qa = read(HERE / 'candidate-readback.json')
seal = read(HERE / 'sealed-handoff.json')
check('Original 33-check independent QA and its seal retained', qa['status'] == 'PASS' and qa['checks_passed'] == qa['checks_total'] == 33 and all(sha(f['path']) == f['sha256'] for f in seal['files']))
check('Original frozen candidate retained', sha(H / 'candidate-freeze.json') == qa['candidate_freeze_sha256'] and all(sha(p) == s for p, s in qa['frozen_artifacts'].items()))
old = read(H / 'prepared-pointer.json')
p = read(BASE / 'current-master.json')
original_receipt = read(H / 'publication-receipt.json')
receipt = read(ADD / 'publication-receipt.json')
check('Original metadata publication receipt retained', original_receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK' and original_receipt['current_master_pointer_sha256'] == sha(H / 'prepared-pointer.json'))
check('Published receipt still links independent QA', original_receipt['independent_qa']['sha256'] == sha(HERE / 'candidate-readback.json') and original_receipt['independent_qa']['seal_sha256'] == sha(HERE / 'sealed-handoff.json'))
check('Addendum status and preceding identity match', receipt['status'] == 'PASS_PUBLISHED_AND_READ_BACK' and receipt['publication_mode'] == 'MAP_SUMMARY_SCOPE_ADDENDUM_ONLY' and receipt['preceding_pointer_sha256'] == sha(H / 'prepared-pointer.json'))
pointer_sha = sha(BASE / 'current-master.json')
check('Published pointer bytes match addendum', pointer_sha == receipt['current_master_pointer_sha256'] == sha(ADD / 'prepared-pointer.json') == '2373ed2edd5bd9f6ad2f6e3fa16196ac4bcf169f158a2739ad0ff53225b65404')
allowed = {'recorded_utc', 'publication_receipt', 'current_native_reference_map', 'latest_master_metadata_change'}
check('Exactly the four documented pointer fields differ', {k for k in set(p) | set(old) if p.get(k) != old.get(k)} == allowed)
descriptor = p['current_native_reference_map']
previous = old['current_native_reference_map']
check('Map path and data hash remain exact', all(descriptor[k] == previous[k] for k in ['path', 'sha256']))
check('Historical 94-object scope preserved explicitly', descriptor['historical_scope_observation'] == {k: v for k, v in previous.items() if k not in ['path', 'sha256']})
expected = {'fresh_metadata_objects_in_latest_scope': 190, 'complete_current_family_listings_in_latest_scope': 1,
    'same_id_file_paths_refreshed_in_latest_scope': 23, 'actual_file_parent_changes_in_latest_scope': 23,
    'actual_folder_parent_changes_in_latest_scope': 0, 'new_native_folders': 0, 'new_catalogue_options': 0,
    'Echo_originals_verified_by_native_lane': 180, 'Echo_local_originals_rehashed_by_importer': 23,
    'native_writes_by_master_import': 0, 'global_all_source_original_bytes_rehashed': False}
check('Current descriptor agrees with the sealed Echo scope', all(descriptor[k] == value for k, value in expected.items()) and descriptor['latest_scope'] == 'Echo Sound within BOLDSTONE MASTER/Products/01 Wall Sculptures')
inputs = read(H / 'input-manifest.json')
paths = {'register': Path(inputs['register']['path']), 'workbook': Path(inputs['workbook']['path']),
    'audit': Path(inputs['audit']['path']), 'native_map': H / 'current-native-reference-map.json', 'asset_map': H / 'current-assets.json'}
expected_hashes = {k: qa['candidate_' + k + '_sha256'] for k in paths}
check('All five data artifacts retain their approved bytes', all(sha(path) == expected_hashes[k] for k, path in paths.items()))
check('Current explicit asset map still matches its approved bytes', p['current_asset_reference_map'] == old['current_asset_reference_map'] and p['current_asset_reference_map']['sha256'] == sha(BASE / p['current_asset_reference_map']['path']))
check('Current native map pointer matches its approved bytes', descriptor['sha256'] == sha(BASE / descriptor['path']))
updates = read(H / 'prepared-control-paths.json')
for key, prepared in updates.items():
    live_path = Path(inputs[key]['path'])
    control = read(live_path)
    before_control = read(prepared)
    assert control['current_master_catalogue'] == p
    assert control['current_native_reference_map'] == descriptor
    assert control['latest_master_metadata_change'] == p['latest_master_metadata_change']
    assert sha(live_path) == receipt['controls_sha256'][str(live_path)]
    assert all(control.get(k) == v for k, v in before_control.items() if k not in {'updated_utc', 'current_master_catalogue', 'current_native_reference_map', 'latest_master_metadata_change'})
check('Three current controls synchronized with unrelated state retained', len(updates) == 3)
check('The original Echo scope and both galleries are retained', p['latest_echo_sound_approved_native_navigation'] == old['latest_echo_sound_approved_native_navigation'] and p['current_image_review_links'] == old['current_image_review_links'])
check('Summary-only change adds no native writes or new catalogue claims', receipt['new_native_or_platform_writes'] == 0 and (receipt['active_options'], receipt['retained_component_ids'], receipt['working_design_groups']) == (188, 112, 110))
check('Current pointer did not change during this readback', sha(BASE / 'current-master.json') == pointer_sha)
record = {'status': 'PASS', 'phase': 'PUBLISHED_SUMMARY_ADDENDUM_READBACK', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'current_pointer_sha256': pointer_sha, 'preceding_pointer_sha256': sha(H / 'prepared-pointer.json'),
    'candidate_qa_sha256': sha(HERE / 'candidate-readback.json'), 'candidate_qa_checks_retained': 33,
    'all_five_data_artifact_sha256': expected_hashes, 'data_artifacts': {k: str(v) for k, v in paths.items()},
    'current_native_descriptor': descriptor, 'new_live_calls': 0, 'original_binary_reads_or_rehashes_by_this_QA': 0,
    'shared_writes': 0, 'broad_native_QA_repeated': False}
out = HERE / 'published-summary-addendum-readback.json'
assert not out.exists()
out.write_text(json.dumps(record, indent=2) + '\n')
published_seal = {'status': 'SEALED_PUBLISHED_ECHO_METADATA_QA', 'files': [{'path': str(f), 'sha256': sha(f)} for f in [Path(__file__), out]]}
(HERE / 'sealed-published-handoff.json').write_text(json.dumps(published_seal, indent=2) + '\n')
print(json.dumps({'status': record['status'], 'checks_passed': len(checks), 'checks_total': len(checks),
    'output': str(out), 'sha256': sha(out), 'seal_sha256': sha(HERE / 'sealed-published-handoff.json'), 'pointer_sha256': pointer_sha}, indent=2))
