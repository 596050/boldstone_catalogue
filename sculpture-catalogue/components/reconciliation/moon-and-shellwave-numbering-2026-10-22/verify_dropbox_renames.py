import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

JOB = Path(__file__).parent
def read(name):
    return json.loads((JOB / name).read_text())
def fq(path):
    if path.startswith('ns:202238505//'):
        return '/' + path.split('//', 1)[1]
    return path
def native(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(path, safe='/')

plan = read('rename-plan.json')
before = read('dropbox-before-inventory.json')
after = read('dropbox-after-inventory.json')
assert hashlib.sha256((JOB / 'rename-plan.json').read_bytes()).hexdigest() == before['plan_sha256']
assert not before['has_more'] and not after['subtree']['has_more'] and not after['wall_root']['has_more']
old_root = before['family_metadata']['folder']
new_root = after['family_metadata']['folder']
assert old_root['id'] == new_root['id'] == plan['family']['folder_id']
assert old_root['name'] == plan['family']['old_name'] and new_root['name'] == plan['family']['new_name']
assert old_root['path_display'] == plan['family']['old_path'] and new_root['path_display'] == plan['family']['new_path']
assert old_root['folder_size'] == new_root['folder_size']
assert old_root['sharing_info'] == new_root['sharing_info']
old = {x['file_id']: x for x in before['entries']}
new = {x['file_id']: x for x in after['subtree']['entries']}
assert old.keys() == new.keys() and len(old) == 200
assert sum(x['object_type'] == 'file' for x in old.values()) == 188
assert sum(x['object_type'] == 'folder' for x in old.values()) == 12
old_by_path = {fq(x['path']): x for x in old.values()}
new_by_path = {fq(x['path']): x for x in new.values()}

def parent_id(item, paths, family_path):
    parent = fq(item['path']).rsplit('/', 1)[0]
    if parent == family_path:
        return plan['family']['folder_id']
    return paths[parent]['file_id']

objects = [{
    'file_id': plan['family']['folder_id'], 'object_type': 'folder',
    'old_name': old_root['name'], 'current_name': new_root['name'],
    'old_path': old_root['path_display'], 'current_path': new_root['path_display'],
    'current_native_url': native(new_root['path_display'], True),
    'old_parent_path': old_root['path_display'].rsplit('/', 1)[0],
    'current_parent_path': new_root['path_display'].rsplit('/', 1)[0],
}]
for ident, original in old.items():
    current = new[ident]
    original_path = fq(original['path'])
    expected = original_path
    for change in plan['child_folder_renames']:
        src = change['old_path']
        if expected == src or expected.startswith(src + '/'):
            expected = change['current_final_path'] + expected[len(src):]
            break
    else:
        assert expected.startswith(plan['family']['old_path'] + '/')
        expected = plan['family']['new_path'] + expected[len(plan['family']['old_path']):]
    assert current['object_type'] == original['object_type']
    assert fq(current['path']) == expected, (ident, fq(current['path']), expected)
    assert parent_id(original, old_by_path, plan['family']['old_path']) == parent_id(current, new_by_path, plan['family']['new_path'])
    if original['object_type'] == 'file':
        assert original['name'] == current['name']
        assert original['file']['size'] == current['file']['size']
    objects.append({'file_id': ident, 'object_type': original['object_type'],
        'old_name': original['name'], 'current_name': current['name'],
        'old_path': original_path, 'current_path': fq(current['path']),
        'current_native_url': native(fq(current['path']), current['object_type'] == 'folder'),
        'old_parent_id': parent_id(original, old_by_path, plan['family']['old_path']),
        'current_parent_id': parent_id(current, new_by_path, plan['family']['new_path']),
        'size': current.get('file', {}).get('size')})

for change in plan['child_folder_renames']:
    item = new[change['folder_id']]
    assert item['name'] == change['new_name']
for unchanged in plan['child_names_unchanged']:
    assert new[unchanged['folder_id']]['name'] == unchanged['name']

for name, expected in [('dropbox-child-move-completion.json', plan['child_folder_renames']),
                       ('dropbox-family-move-completion.json', [plan['family']])]:
    receipt = read(name)
    assert receipt['status'] == 'completed' and receipt['result_type'] == 'move'
    assert len(receipt['move_result']['entries']) == len(expected)
    for result, request in zip(receipt['move_result']['entries'], expected):
        assert result['entry_status'] == 'success'
        assert result['object']['file_id'] == request['folder_id']

wall = after['wall_root']['entries']
assert len([x for x in wall if x['file_id'] == plan['family']['folder_id'] and x['name'] == plan['family']['new_name']]) == 1
assert not any(x['name'].casefold() == plan['family']['old_name'].casefold() for x in wall)
fish_before = next(x for x in before['wall_root_relevant'] if x['name'] == 'Moon Fishwave')
fish_after = next(x for x in wall if x['file_id'] == fish_before['file_id'])
assert fish_before['name'] == fish_after['name'] and fish_before['path'] == fish_after['path']

verification = {
    'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'counts': {'original_files': 188, 'original_child_folders': 12, 'original_folders_including_family': 13,
        'stable_objects_preserved_including_family': 201, 'child_folders_renamed': 9, 'family_folders_renamed': 1,
        'child_folder_names_unchanged': 3, 'current_file_paths_updated': 188,
        'original_total_file_bytes': sum(x['file']['size'] for x in old.values() if x['object_type'] == 'file'),
        'files_renamed_copied_deleted': 0, 'folders_created_or_deleted': 0, 'pending_native_jobs': 0},
    'all_stable_IDs_types_file_basenames_sizes_and_scoped_parent_IDs_preserved': True,
    'all_expected_paths_match': True,
    'execution_order_verified': 'Nine children completed and all200 descendants verified before family rename submission.',
    'all_ten_entry_results_success': True,
    'family_sharing_metadata_preserved': True,
    'Moon_Fishwave_family_root_ID_name_path_unchanged_and_excluded_from_mutations': True,
    'limits': 'Native stable-ID inventory, names, byte sizes, parent IDs, API receipts and folder sharing metadata. No original-byte download/rehash, image-content reclassification, HTTP or all-shared-link audit.',
    'master_or_platform_writes_by_this_lane': 0,
}
vp = JOB / 'dropbox-verification.json'
assert not vp.exists()
vp.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')

folder_rows = []
for folder in sorted((x for x in new.values() if x['object_type'] == 'folder'), key=lambda x: x['name']):
    path = fq(folder['path'])
    folder_rows.append({'folder_id': folder['file_id'], 'name': folder['name'], 'current_path': path,
        'current_native_url': native(path, True), 'direct_file_count': sum(
            x['object_type'] == 'file' and fq(x['path']).rsplit('/', 1)[0] == path for x in new.values())})
receipt_names = ['rename-plan.json', 'dropbox-before-inventory.json', 'dropbox-child-move-submission.json',
    'dropbox-child-move-completion.json', 'dropbox-child-stage-readback.json',
    'dropbox-family-move-submission.json', 'dropbox-family-move-completion.json',
    'dropbox-after-inventory.json', 'dropbox-verification.json']
overlay = {'schema': 'boldstone.current_reference_overlay.moon_and_shellwave.v1',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'COMPLETE_VERIFIED_MOON_AND_SHELLWAVE_FAMILY_AND_COMPONENT_RENAMES',
    'owner_instruction': plan['source_user_instruction'],
    'family': {**plan['family'], 'current_name': new_root['name'], 'current_path': new_root['path_display'], 'current_native_url': native(new_root['path_display'], True)},
    'component_mapping': plan['component_mapping'],
    'prefix_maps': [{'file_id': x['folder_id'], 'old_path': x['old_path'], 'current_path': x['current_final_path']} for x in plan['child_folder_renames']] + [
        {'file_id': plan['family']['folder_id'], 'old_path': plan['family']['old_path'], 'current_path': plan['family']['new_path']}],
    'prefix_map_application': 'Apply longest matching old prefix first; child-specific maps precede family fallback.',
    'objects': objects, 'current_child_folders': folder_rows,
    'verification': verification,
    'receipts': [{'path': str((JOB / n).resolve()), 'sha256': hashlib.sha256((JOB / n).read_bytes()).hexdigest()} for n in receipt_names],
    'catalogue_projection': [
        'Root alone edits master. Preserve existing component and option IDs, all accepted specifications and source histories.',
        'BC-MSW-SPIRAL becomes Moon and Shellwave1; BC-MSW-MOON becomes Moon and Shellwave2 under explicit owner numbering.',
        'Historical MSW2 spiral and MSW1/MSW3 moon codes remain source aliases and are not overwritten.',
        'Project current references by stable ID and actual current parent. Pair/group, scene and water-feature evidence retains its original role.',
        'No new mould, cast, stock, finish, product, image coverage or provenance claim is created by folder naming.',
        'Distinct Moon Fishwave is outside scope and unchanged by these operations.',
    ],
    'rollback': 'Rename family ID back to the recorded old path first, then rename the nine child IDs back to their recorded old paths. No deletion or recreation is needed.',
    'master_write_owner': '01a144ab-1a7c-7223-a403-73a4d53d70ff',
    'master_writes_by_this_lane': 0,
}
target = JOB / 'dropbox-current-reference-overlay.json'
assert not target.exists()
target.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': verification['status'], 'overlay': str(target.resolve()),
    'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'counts': verification['counts'], 'folders': folder_rows}, ensure_ascii=False))
