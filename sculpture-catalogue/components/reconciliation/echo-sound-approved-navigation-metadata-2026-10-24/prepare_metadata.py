"""Prepare current Echo navigation while retaining byte-identical catalogue/workbook data."""
import copy
import hashlib
import json
import os
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
D = ROOT / 'reports/dropbox-echo-sound-23-approved-moves-20261024T191800Z'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()
rel = lambda p: str(Path(p).relative_to(B))
def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
def block_hash(path):
    chunks = []
    with Path(path).open('rb') as f:
        while chunk := f.read(4 * 1024 * 1024):
            chunks.append(hashlib.sha256(chunk).digest())
    return hashlib.sha256(b''.join(chunks)).hexdigest()

assert not (H / 'publication-receipt.json').exists()
assert sha(B / 'current-master.json') == 'acc939a3ac1765da11db0ce73bcb8a437bdb35db60aa9deca1a2a9dad288b90b'
old = read(B / 'current-master.json')
g = read(B / old['register'])
oldh = (B / old['register']).parent
assert sha(B / old['register']) == old['register_sha256'] == 'd10946390d3858ce1f5c6a66caca988b9a61a1ce2ab1d1776d28bebeec4453a1'
assert sha(B / old['workbook']) == old['workbook_sha256'] == '4c1bb8cccbf1cc5111e747e3084052937346828b80c2f8de203450bfa43ccae6'
assert sha(D / 'execution-seal.json') == '87d07e437a6a39d8fe6fb4ee4c870edc8dcd07f9171a43cf986e4cd2d022e51b'
assert sha(D / 'current-reference-overlay.json') == 'f7065c400f4d5a29f31930e5c16b946ae1ef8aa7ef8db0aa03676894bf04b94d'
seal = read(D / 'execution-seal.json')
assert seal['status'] == 'NATIVE_EXECUTION_COMPLETE_VERIFIED' and seal['receipt_count'] == 33
inputs = {'pointer': B / 'current-master.json', 'register': B / old['register'], 'workbook': B / old['workbook'],
          'audit': Path(old['latest_image_coverage_audit']['path']),
          'native_map': B / old['current_native_reference_map']['path'], 'assets': oldh / 'current-assets.json',
          'report_verification': B / old['current_image_review_links']['verification'],
          'review_progress': B / 'components/reviews/specification_review_progress.json',
          'component_checkpoint': B / 'components/checkpoint.json', 'root_checkpoint': B / 'checkpoint.json',
          'execution_seal': D / 'execution-seal.json'}
for i, item in enumerate(seal['files']):
    path = D / item['path']
    assert sha(path) == item['sha256'] and path.stat().st_size == item['size'], path
    inputs['native_receipt_' + str(i)] = path
source_report = ROOT / 'reports/source-photo-finish-review-20261024-root'
source_seal = read(source_report / 'sealed-handoff.json')
for path, expected in source_seal['files'].items():
    assert sha(path) == expected
    inputs['source_review_' + Path(path).name] = Path(path)
inputs['source_review_seal'] = source_report / 'sealed-handoff.json'
water = B / 'components/parallel-reviews/water-feature-coverage-20261024-B'
assert sha(water / 'sealed-handoff.json') == '9aec4e5dbe77704454278999bc0ead40ad737e4be53f4ef9aaaa2b62a5f7debe'
inputs['water_review_seal'] = water / 'sealed-handoff.json'

(H / 'inputs').mkdir(exist_ok=True)
manifest = {}
for key, path in inputs.items():
    snap = H / 'inputs' / (key + '.before')
    if snap.exists():
        assert sha(snap) == sha(path), key
    else:
        snap.write_bytes(path.read_bytes())
    manifest[key] = {'path': str(path), 'snapshot': str(snap), 'sha256': sha(path)}
write(H / 'input-manifest.json', manifest)
for key in ['review_progress', 'component_checkpoint', 'root_checkpoint']:
    assert read(manifest[key]['path'])['current_master_catalogue'] == old

approval = read(D / 'owner-approval-source-evidence.json')
with Path(approval['source_file']).open('rb') as f:
    meta = json.loads(f.readline())
    assert meta['type'] == 'session_meta' and meta['payload']['id'] == approval['session_id']
    f.seek(approval['byte_offset'])
    line = f.readline()
assert len(line) == approval['line_bytes'] and hashlib.sha256(line).hexdigest() == approval['line_sha256']
event = json.loads(line)
assert event['type'] == 'response_item' and event['payload']['role'] == 'user' and event['timestamp'] == approval['response_item_timestamp']
text = '\n'.join(x.get('text', '') for x in event['payload']['content'])
assert text.startswith('Do it:') and '17 wider' in text and '93 photographs' in text and '180 images' in text

overlay = read(D / 'current-reference-overlay.json')
assert overlay['status'] == 'COMPLETE_VERIFIED' and not overlay['prefix_maps']
moved = [x for x in overlay['objects'] if x['old_path'] != x['current_path']]
assert len(moved) == len(overlay['specific_file_maps']) == 23
ids = {x['file_id'] for x in moved}
fresh = read(D / 'twenty-three-fresh-postmove-originals.json')
assert {x['id'] for x in fresh} == ids
for x in fresh:
    assert sha(x['local_path']) == x['sha256']
    assert block_hash(x['local_path']) == x['dropbox_content_hash'] == x['content_hash']
    assert Path(x['local_path']).stat().st_size == x['size']
fresh_by_id = {x['id']: x for x in fresh}
links = read(D / 'all-current-echo-sound-image-folder-links.json')
assert len(links) == len({x['file_id'] for x in links}) == 180
assert sum(x['size'] for x in links) == 1092139502
counts = Counter(x['folder_id'] for x in links)
assert counts['id:cnqzTNngPVsAAAAAAAyicA'] == 93 and counts['id:cnqzTNngPVsAAAAAAAykBg'] == 25 and len(counts) == 9
assert {x['file_id'] for x in links if x['moved_this_batch']} == ids

tokens = ids | {x['current_name'] for x in moved}
gtext = (B / old['register']).read_text()
assert not any(t in gtext for t in tokens)
workbook_hits = []
with zipfile.ZipFile(B / old['workbook']) as z:
    for name in z.namelist():
        if name.endswith(('.xml', '.rels')):
            value = z.read(name).decode()
            workbook_hits += [(name, t) for t in tokens if t in value]
assert not workbook_hits, workbook_hits
reports = read(manifest['report_verification']['path'])
report_hits = []
for x in reports['pages'] + reports['csv_files']:
    assert sha(x['path']) == x['sha256']
    value = Path(x['path']).read_text()
    report_hits += [(x['path'], t) for t in tokens if t in value]
assert not report_hits, report_hits

assets_before = read(manifest['assets']['path'])
assets = copy.deepcopy(assets_before)
native_before = read(manifest['native_map']['path'])
native = copy.deepcopy(native_before)
assert not (ids & set(native['current_objects']))
changed_assets = []
for x in links:
    before = assets[x['file_id']]
    expected = {k: x[k] for k in ['folder_id', 'folder_url', 'image_url']}
    different = any(before[k] != v for k, v in expected.items())
    assert different == x['moved_this_batch']
    if not different:
        continue
    y = next(v for v in moved if v['file_id'] == x['file_id'])
    assert before['folder_id'] == y['old_parent_id'] and before['name'] == y['current_name'] == y['old_name']
    after = copy.deepcopy(before)
    after.update(expected)
    after.update(path=y['current_ns_path'], display_path=y['current_path'],
                 folder_path=y['current_ns_path'].rsplit('/', 1)[0], full=fresh_by_id[x['file_id']]['local_path'])
    after['current_original_evidence'] = {'sha256': x['sha256'], 'dropbox_content_hash': x['dropbox_content_hash'],
        'verified_utc': overlay['recorded_utc'], 'evidence': str(D / 'twenty-three-fresh-postmove-originals.json')}
    assets[x['file_id']] = after
    changed_assets.append({'file_id': x['file_id'], 'before': before, 'after': after})
assert len(changed_assets) == 23 and set(assets) == set(assets_before)
assert all(assets[i] == value for i, value in assets_before.items() if i not in ids)
new_native_ids = []
for x in overlay['objects']:
    assert x['file_id'] not in native['current_objects']
    native['current_objects'][x['file_id']] = {'file_id': x['file_id'], 'object_type': x['object_type'],
        'display_path': x['current_path'], 'path': x['current_ns_path'], 'name': x['current_name'],
        'parent_id': x['current_parent_id'], 'size': x['size'], 'observed_utc': overlay['recorded_utc'],
        'evidence': str(D / 'current-reference-overlay.json'), 'evidence_sha256': sha(D / 'current-reference-overlay.json')}
    native['old_path_to_id'][x['old_path']] = x['file_id']
    new_native_ids.append(x['file_id'])
root = overlay['preserved_scope_roots'][0]
assert root['id'] not in native['current_objects']
native['current_objects'][root['id']] = {'file_id': root['id'], 'object_type': 'folder', 'name': root['name'],
    'display_path': root['path_display'], 'path': 'ns:202238505/' + root['path_display'],
    'parent_id': None, 'size': 0, 'observed_utc': overlay['recorded_utc'], 'evidence': str(D / 'current-reference-overlay.json')}
new_native_ids.append(root['id'])
assert all(native['current_objects'][i] == value for i, value in native_before['current_objects'].items())
native['status'] = 'CURRENT_REFERENCE_MAP_WITH_VERIFIED_ECHO_23_APPROVED_MOVES'
native.setdefault('verified_path_change_history', []).append({'path': str(D / 'current-reference-overlay.json'),
    'sha256': sha(D / 'current-reference-overlay.json'), 'scope': '23 Echo file parents changed;190 existing native objects newly represented in this scoped map; no new sculptures.'})
write(H / 'current-assets.json', assets)
write(H / 'current-native-reference-map.json', native)
write(H / 'asset-change-history.json', changed_assets)

summary = {'status': 'METADATA_ONLY_ECHO_NAVIGATION_READY', 'approved_native_file_moves_imported': 23,
    'newly_represented_existing_native_objects': len(new_native_ids), 'changed_asset_navigation_records': 23,
    'family_originals': 180, 'family_bytes': 1092139502, 'family_folders': 9, 'White': 93, 'InSitu': 25,
    'catalogue_register_workbook_audit_unchanged': True, 'workbook_token_hits': 0, 'prior_current_report_token_hits': 0,
    'new_original_binary_downloads_by_importer': 0, 'local_originals_rehashed_by_importer': 23,
    'new_specifications': 0, 'new_physical_verifications': 0, 'new_platform_pairs': 0,
    'native_or_platform_writes_by_importer': 0, 'active_options': 188, 'retained_component_ids': 112, 'working_design_groups': 110}
write(H / 'import-summary.json', summary)
p = copy.deepcopy(old)
p.update(recorded_utc=now(), publication_receipt=rel(H / 'publication-receipt.json'),
         status='CURRENT_MASTER_WITH_VERIFIED_ECHO_NAVIGATION_METADATA')
p['current_native_reference_map'] = {**old['current_native_reference_map'], 'path': rel(H / 'current-native-reference-map.json'),
    'sha256': sha(H / 'current-native-reference-map.json')}
p['current_asset_reference_map'] = {'path': rel(H / 'current-assets.json'), 'sha256': sha(H / 'current-assets.json'),
    'scope': 'Authoritative current asset navigation;23 Echo file parents refreshed. All catalogue-selected images, roles and field objects retained.'}
decision = {**summary, 'status': 'APPROVED_23_ECHO_MOVES_VERIFIED_AND_IMPORTED',
    'overlay': str(D / 'current-reference-overlay.json'), 'overlay_sha256': sha(D / 'current-reference-overlay.json'),
    'execution_seal': str(D / 'execution-seal.json'), 'execution_seal_sha256': sha(D / 'execution-seal.json'),
    'owner_approval_evidence': str(D / 'owner-approval-source-evidence.json'), 'owner_approval_sha256': sha(D / 'owner-approval-source-evidence.json'),
    'moved_image_review': str(D / 'moved-23-current-image-folder-links.html'),
    'all_current_images': str(D / 'all-current-echo-sound-image-folder-links.html')}
p['latest_echo_sound_approved_native_navigation'] = decision
p['current_image_review_links'].update(echo_sound_approved_moves=decision['moved_image_review'], echo_sound_all_current_images=decision['all_current_images'])
p['latest_read_only_source_photo_review'] = {'path': str(source_report / 'review.json'), 'sha256': sha(source_report / 'review.json'),
    'review': str(source_report / 'index.html'), 'sealed_handoff': str(source_report / 'sealed-handoff.json'),
    'sealed_handoff_sha256': sha(source_report / 'sealed-handoff.json'), 'cases': 2, 'new_platform_pairs_or_physical_verifications': 0}
p['latest_scoped_water_feature_coverage'] = {'review': str(water / 'review.html'), 'sealed_handoff': str(water / 'sealed-handoff.json'),
    'sealed_handoff_sha256': sha(water / 'sealed-handoff.json'), 'scope': 'Read-only19 existing option records/114 qualified fields; no whole-library completion assertion.'}
p['latest_master_metadata_change'] = {'status': 'ECHO_CURRENT_NAVIGATION_IMPORTED_METADATA_ONLY', 'path': rel(H / 'publication-receipt.json'),
    'catalogue_register_workbook_and_audit_unchanged': True, 'previous_receipt': old['publication_receipt']}
p['next_catalogue_actions'][0] = 'The approved23 Echo photograph moves are imported:93White/25InSitu; all180 originals and all selected component identities/roles/specifications retained. Chiswick015 remains pending in the directory session.'
for key in ['register', 'register_sha256', 'workbook', 'workbook_sha256', 'latest_image_coverage_audit', 'summary', 'current_option_count', 'retained_option_count', 'current_global_context_owner_hold', 'platform_write_holds']:
    assert p[key] == old[key], key
write(H / 'prepared-pointer.json', p)
updates = {}
for key in ['review_progress', 'component_checkpoint', 'root_checkpoint']:
    d = read(manifest[key]['snapshot'])
    d.update(updated_utc=p['recorded_utc'], current_master_catalogue=copy.deepcopy(p),
        current_native_reference_map=copy.deepcopy(p['current_native_reference_map']), current_asset_reference_map=copy.deepcopy(p['current_asset_reference_map']),
        latest_echo_sound_approved_native_navigation=copy.deepcopy(decision), latest_master_metadata_change=copy.deepcopy(p['latest_master_metadata_change']),
        latest_read_only_source_photo_review=copy.deepcopy(p['latest_read_only_source_photo_review']),
        latest_scoped_water_feature_coverage=copy.deepcopy(p['latest_scoped_water_feature_coverage']),
        current_image_review_links=copy.deepcopy(p['current_image_review_links']), next_catalogue_actions=copy.deepcopy(p['next_catalogue_actions']))
    target = H / ('prepared-' + key + '.json')
    write(target, d)
    updates[key] = str(target)
write(H / 'prepared-control-paths.json', updates)
assert all(sha(x['path']) == x['sha256'] for x in manifest.values())
verification = {**summary, 'status': 'PASS', 'recorded_utc': now(), 'owner_record_verified': True,
    'sealed_native_receipts_verified': 33, 'native_190_existing_objects_added': len(new_native_ids),
    'all_prior_native_objects_and_unmoved_assets_unchanged': True, 'prepared_controls': 3,
    'register_sha256': old['register_sha256'], 'workbook_sha256': old['workbook_sha256'], 'audit_sha256': manifest['audit']['sha256']}
write(H / 'candidate-verification.json', verification)
freeze_paths = [Path(__file__), H / 'input-manifest.json', H / 'current-assets.json', H / 'current-native-reference-map.json',
    H / 'asset-change-history.json', H / 'import-summary.json', H / 'prepared-pointer.json', H / 'prepared-control-paths.json',
    H / 'candidate-verification.json', *map(Path, updates.values())]
write(H / 'candidate-freeze.json', {'status': 'FROZEN_ECHO_METADATA_ONLY_CANDIDATE', 'recorded_utc': now(),
    'candidate_register_sha256': old['register_sha256'], 'candidate_workbook_sha256': old['workbook_sha256'],
    'candidate_audit_sha256': manifest['audit']['sha256'], 'frozen_artifacts': {str(x): sha(x) for x in freeze_paths}})
print(json.dumps({**verification, 'freeze_sha256': sha(H / 'candidate-freeze.json')}))
