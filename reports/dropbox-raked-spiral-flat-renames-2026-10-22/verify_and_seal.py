import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

OUT = Path(__file__).parent
def read(name):
    return json.loads((OUT / name).read_text())
def fq(path):
    if path.startswith('ns:202238505//'):
        return '/' + path.split('//', 1)[1]
    return path
def native(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(path, safe='/')

plan = read('rename-plan.json')
before = read('before-native-inventory.json')
after = read('after-native-readback.json')
listing = next(x['data'] for x in after['receipts'] if x['type'] == 'subtree')
assert not before['listing']['has_more'] and not listing['has_more']
old = {x['file_id']: x for x in before['listing']['entries']}
new = {x['file_id']: x for x in listing['entries']}
assert old.keys() == new.keys() and len(old) == 137
assert sum(x['object_type'] == 'file' for x in new.values()) == 127
assert sum(x['object_type'] == 'folder' for x in new.values()) == 10
by_old_path = {fq(x['path']): x for x in old.values()}
by_new_path = {fq(x['path']): x for x in new.values()}
family_id, root = plan['family']['file_id'], plan['family']['path']
def parent_id(item, paths):
    parent = fq(item['path']).rsplit('/', 1)[0]
    if parent == root:
        return family_id
    return paths[parent]['file_id']

objects = []
for ident, prior in old.items():
    current = new[ident]
    expected = fq(prior['path'])
    for change in plan['folder_renames']:
        if expected == change['old_path'] or expected.startswith(change['old_path'] + '/'):
            expected = change['current_path'] + expected[len(change['old_path']):]
            break
    assert fq(current['path']) == expected, (ident, fq(current['path']), expected)
    assert prior['object_type'] == current['object_type']
    assert parent_id(prior, by_old_path) == parent_id(current, by_new_path)
    if prior['object_type'] == 'file':
        assert prior['name'] == current['name']
        assert prior['file']['size'] == current['file']['size']
    objects.append({'file_id': ident, 'object_type': current['object_type'],
        'old_name': prior['name'], 'current_name': current['name'],
        'old_path': fq(prior['path']), 'current_path': fq(current['path']),
        'old_parent_id': parent_id(prior, by_old_path), 'current_parent_id': parent_id(current, by_new_path),
        'size': current.get('file', {}).get('size'),
        'current_native_url': native(fq(current['path']), current['object_type'] == 'folder')})

old_family = next(x['data']['folder'] for x in before['metadata_and_links'] if x['type'] == 'family_metadata')
new_family = next(x['data']['folder'] for x in after['receipts'] if x['type'] == 'family_metadata')
for key in ('id', 'name', 'path_display', 'sharing_info', 'folder_size'):
    assert old_family.get(key) == new_family.get(key), key
assert new_family['id'] == family_id and new_family['path_display'] == root
for f in plan['folder_renames']:
    metadata = next(x['data']['folder'] for x in after['receipts'] if x['type'] == 'folder_metadata' and x.get('id') == f['file_id'])
    prior_metadata = next(x['data']['folder'] for x in before['metadata_and_links'] if x['type'] == 'renamed_folder_metadata' and x.get('id') == f['file_id'])
    assert metadata['id'] == f['file_id'] and metadata['name'] == f['current_name'] and metadata['path_display'] == f['current_path']
    assert metadata.get('sharing_info') == prior_metadata.get('sharing_info')
    assert metadata.get('folder_size') == prior_metadata.get('folder_size')
    before_links = next(x['data'] for x in before['metadata_and_links'] if x['type'] == 'direct_owned_links' and x.get('id') == f['file_id'])
    after_links = next(x['data'] for x in after['receipts'] if x['type'] == 'direct_owned_links' and x.get('id') == f['file_id'])
    assert not before_links['has_more'] and not after_links['has_more']
    assert before_links['links'] == after_links['links'] == []
done = read('move-completion.json')
assert done['status'] == 'completed' and done['result_type'] == 'move'
assert len(done['move_result']['entries']) == 6
for e, request in zip(done['move_result']['entries'], plan['folder_renames']):
    assert e['entry_status'] == 'success' and e['object']['file_id'] == request['file_id']
    assert fq(e['object'].get('path_display') or e['object']['path']) == request['current_path']
changed_folders = [o for o in objects if o['object_type'] == 'folder' and o['old_name'] != o['current_name']]
assert len(changed_folders) == 6
unchanged_folders = [o for o in objects if o['object_type'] == 'folder' and o['old_path'] == o['current_path']]
assert len(unchanged_folders) == 4
assert all(fq(f['path']).rsplit('/', 1)[0] == root for f in new.values() if f['object_type'] == 'folder')
counts = {'original_files_preserved': 127, 'original_child_folder_IDs_preserved': 10,
    'original_stable_objects_including_family_preserved': 138,
    'folders_renamed': 6, 'individual_component_folders_unchanged': 4,
    'file_paths_updated': sum(o['object_type'] == 'file' and o['old_path'] != o['current_path'] for o in objects),
    'original_total_file_bytes': sum(x['file']['size'] for x in old.values() if x['object_type'] == 'file'),
    'new_folders_files_copies_deletions': 0, 'file_basename_changes': 0, 'pending_native_jobs': 0}
assert counts['file_paths_updated'] == 109
verification = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'counts': counts,
    'all_original_IDs_file_names_sizes_types_and_parent_IDs_preserved': True,
    'all_expected_current_paths_match': True,
    'family_and_four_individual_component_folders_unchanged': True,
    'flat_family_hierarchy_preserved': True,
    'six_folder_sharing_metadata_and_zero_direct_owned_links_unchanged': True,
    'limits': 'Native metadata/complete subtree enumeration and six terminal API entry receipts checked. No original-byte download/rehash, HTTP access or all descendant/inherited sharing audit.',
    'master_and_platform_writes_by_this_lane': 0}
vp = OUT / 'verification.json'
assert not vp.exists()
vp.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
receipt_names = ['rename-plan.json', 'before-native-inventory.json', 'move-submission.json', 'move-completion.json', 'after-native-readback.json', 'verification.json']
overlay = {'schema': 'boldstone.current_reference_overlay.raked_spiral_flat_renames.v1',
    'status': 'COMPLETE_VERIFIED_SIX_RAKED_SPIRAL_FLAT_FOLDER_RENAMES',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'owner_authorization': plan['owner_authorization'], 'family': plan['family'],
    'summary': counts, 'prefix_maps': plan['folder_renames'], 'objects': objects,
    'catalogue_projection': ['Update current references by stable file IDs and actual unchanged parent IDs.',
        'Preserve all existing accepted component and option names, numbers, specifications, source snapshots and media roles.',
        'The directory convention repeats full component names in group folders directly under family; introduce no extra component/finish/Arrangements nesting.',
        'No new individual photos, products, finishes, source bindings, mould, stock or physical measurement claims.'],
    'verification': verification,
    'receipts': [{'path': str((OUT / n).resolve()), 'sha256': hashlib.sha256((OUT / n).read_bytes()).hexdigest()} for n in receipt_names],
    'rollback': plan['rollback'], 'master_write_owner': plan['master_write_owner'], 'master_writes_by_this_lane': 0}
p = OUT / 'current-reference-overlay.json'
assert not p.exists()
p.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'overlay': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'verification': verification['status'], 'counts': counts}))
