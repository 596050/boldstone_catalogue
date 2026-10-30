import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

OUT = Path(__file__).parent
def read(name):
    return json.loads((OUT / name).read_text())
def fq(path):
    if path.startswith('ns:202238505//'):
        return '/' + path.split('//', 1)[1]
    return path
def native(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(fq(path), safe='/')

plan = read('execution-plan.json')
before = read('before-native-inventory.json')
after = read('after-native-readback.json')
owner = read('owner-decision.json')
assert owner['status'] == 'EXPLICIT_OWNER_APPROVED_NEW_COMPONENT_NUMBERING_AND_FLAT_FOLDER_EXECUTION'
assert [(x['proposed_new_number'], x['approved_position']) for x in owner['mappings']] == [(1, 'Top Left'), (2, 'Top Right'), (3, 'Bottom Left'), (4, 'Bottom Right')]
listing = next(x['data'] for x in after['receipts'] if x['kind'] == 'subtree')
assert not listing['has_more'] and not before['listing']['has_more']
old = {x['file_id']: x for x in before['listing']['entries']}
new = {x['file_id']: x for x in listing['entries']}
old_paths = {fq(x['path']): x for x in old.values()}
new_paths = {fq(x['path']): x for x in new.values()}
assert len(old) == 11 and len(new) == 19 and set(old) < set(new)
assert sum(x['object_type'] == 'file' for x in new.values()) == 13
assert sum(x['object_type'] == 'folder' for x in new.values()) == 6
root, family_id = plan['family']['path'], plan['family']['file_id']
def parent_id(item, paths):
    parent = fq(item['path']).rsplit('/', 1)[0]
    return family_id if parent == root else paths[parent]['file_id']

objects = []
for ident, original in old.items():
    current = new[ident]
    expected = fq(original['path'])
    for change in plan['folder_renames']:
        if expected == change['old_path'] or expected.startswith(change['old_path'] + '/'):
            expected = change['current_path'] + expected[len(change['old_path']):]
            break
    assert current['object_type'] == original['object_type']
    assert fq(current['path']) == expected
    assert parent_id(original, old_paths) == parent_id(current, new_paths)
    if current['object_type'] == 'file':
        assert original['name'] == current['name']
        assert original['file']['size'] == current['file']['size']
    objects.append({'file_id': ident, 'object_type': current['object_type'],
        'old_name': original['name'], 'current_name': current['name'],
        'old_path': fq(original['path']), 'current_path': fq(current['path']),
        'old_parent_id': parent_id(original, old_paths), 'current_parent_id': parent_id(current, new_paths),
        'current_native_url': native(current['path'], current['object_type'] == 'folder'),
        'size': current.get('file', {}).get('size')})

family_after = next(x['data']['folder'] for x in after['receipts'] if x['kind'] == 'family_metadata')
family_before = before['family_metadata']['folder']
for key in ('id', 'name', 'path_display', 'sharing_info'):
    assert family_before.get(key) == family_after.get(key)
assert family_after['id'] == family_id and family_after['path_display'] == root
for move in plan['folder_renames']:
    metadata = next(x['data']['folder'] for x in after['receipts'] if x['kind'] == 'group_folder_metadata' and x.get('id') == move['file_id'])
    original = next(x for x in before['folder_metadata_and_links'] if x['id'] == move['file_id'])
    assert metadata['id'] == move['file_id'] and metadata['path_display'] == move['current_path'] and metadata['name'] == move['current_name']
    assert metadata.get('sharing_info') == original['metadata']['folder'].get('sharing_info')
    assert metadata['folder_size'] == original['metadata']['folder']['folder_size']
    links = next(x['data'] for x in after['receipts'] if x['kind'] == 'direct_owned_links' and x.get('id') == move['file_id'])
    assert not links['has_more'] and not original['direct_owned_links']['has_more']
    assert original['direct_owned_links']['links'] == links['links'] == []

done = read('move-completion.json')
assert done['status'] == 'completed' and done['result_type'] == 'move' and len(done['move_result']['entries']) == 2
for result, move in zip(done['move_result']['entries'], plan['folder_renames']):
    assert result['entry_status'] == 'success' and result['object']['file_id'] == move['file_id']
    assert fq(result['object'].get('path_display') or result['object']['path']) == move['current_path']

created_folders = []
for i, request in enumerate(plan['create_folders'], 1):
    receipt = read(f'create-folder-{i:02}.json')
    result = receipt['response']['folder']
    current = new_paths[request['path']]
    assert current['file_id'] == result['file_id'] and current['object_type'] == 'folder'
    assert fq(current['path']).rsplit('/', 1)[0] == root
    created_folders.append({**request, 'file_id': current['file_id'], 'current_native_url': native(current['path'], True)})

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')

docs, hrefs = [], []
for i, upload in enumerate(plan['reference_file_uploads'], 1):
    receipt = read(f'upload-{i:02}-completion.json')
    result = receipt['response']
    assert result['status'] == 'completed'
    doc = new_paths[upload['destination_path']]
    assert result['file']['file_id'] == doc['file_id']
    assert doc['file']['size'] == upload['size']
    data = Path(upload['source_file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == upload['sha256']
    assert b'Individual photograph: still needed.' in data
    parser = Links()
    parser.feed(data.decode())
    assert len(parser.links) == 9
    target_ids = []
    for href in parser.links:
        url = urlparse(href)
        assert url.scheme == 'https' and url.netloc == 'www.dropbox.com' and url.path.startswith('/preview/')
        path = unquote(url.path[len('/preview'):])
        target = new_paths[path]
        assert target['file_id'] in old and target['object_type'] == 'file'
        target_ids.append(target['file_id'])
        hrefs.append({'reference_document_id': doc['file_id'], 'href': href, 'target_file_id': target['file_id'],
            'current_parent_id': parent_id(target, new_paths), 'verified_scope': 'Native stable ID and current path, not an HTTP access test'})
    assert set(target_ids) == {x['file_id'] for x in old.values() if x['object_type'] == 'file'}
    docs.append({'file_id': doc['file_id'], 'path': fq(doc['path']), 'current_parent_id': parent_id(doc, new_paths),
        'current_native_url': native(doc['path']), 'size': doc['file']['size'], 'local_sha256': upload['sha256'],
        'role': 'COMPONENT_GROUP_IMAGE_REFERENCE_DOCUMENT_NOT_AN_INDIVIDUAL_PHOTOGRAPH'})

bindings = []
for b in plan['component_finish_bindings']:
    current = dict(b)
    folder = new_paths[b['component_finish_folder_path']]
    doc = new_paths[b['reference_document_path']]
    current.update({'component_finish_folder_id': folder['file_id'], 'component_finish_folder_url': native(folder['path'], True),
        'reference_document_id': doc['file_id'], 'reference_document_url': native(doc['path']),
        'group_references': [{'file_id': ident, 'current_path': fq(new[ident]['path']),
            'current_parent_id': parent_id(new[ident], new_paths), 'current_native_url': native(new[ident]['path']),
            'image_role': 'FOUR_PANEL_GROUP_OR_CONTEXT_NOT_INDIVIDUAL'} for ident in b['group_reference_file_ids']]})
    assert current['component_finish_folder_id'] not in [x['current_parent_id'] for x in current['group_references']]
    assert current['individual_photo_status'] == 'Group only' and not current['new_individual_photo']
    bindings.append(current)

assert all(fq(x['path']).rsplit('/', 1)[0] == root for x in new.values() if x['object_type'] == 'folder')
original_bytes = sum(x['file']['size'] for x in old.values() if x['object_type'] == 'file')
new_bytes = sum(x['file']['size'] for x in new.values() if x['object_type'] == 'file')
assert original_bytes == 9809573 and new_bytes - original_bytes == sum(x['size'] for x in docs)
assert family_after['folder_size'] == new_bytes
counts = {'original_images_preserved': 9, 'original_folder_IDs_preserved_including_family': 3,
    'original_total_image_bytes': original_bytes, 'existing_group_folders_renamed': 2,
    'new_component_folders': 4, 'new_reference_documents': 4, 'current_files': 13, 'current_child_folders': 6,
    'current_stable_objects_including_family': 20, 'reference_hrefs_bound_to_current_native_images': len(hrefs),
    'standalone_individual_image_gaps_retained': 4, 'original_file_basename_changes': 0,
    'image_edits_crops_copies_deletions': 0, 'new_hierarchy_levels': 0, 'pending_native_jobs': 0}
verification = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'counts': counts,
    'all_original_IDs_file_names_sizes_types_and_parent_IDs_preserved': True,
    'all_expected_paths_match': True, 'flat_family_children_verified': True,
    'all_36_reference_hrefs_match_existing_native_images': True,
    'group_folder_sharing_metadata_and_direct_owned_links_preserved': True,
    'group_images_remain_separate_from_component_folders': True,
    'limits': 'Complete native enumeration, metadata, sizes, original parent IDs, terminal API receipts, local reference HTML hashes and target IDs verified. No new original-image or remote HTML byte rehash, HTTP or all descendant/inherited sharing audit.',
    'master_or_platform_writes_by_this_lane': 0}
p = OUT / 'verification.json'
assert not p.exists()
p.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
names = ['owner-decision.json', 'execution-plan.json', 'before-native-inventory.json', 'move-submission.json', 'move-completion.json', 'after-native-readback.json', 'verification.json']
names += [f'create-folder-{i:02}.json' for i in range(1, 5)]
names += [f'upload-{i:02}-{stage}.json' for i in range(1, 5) for stage in ['submission', 'completion']]
overlay = {'schema': 'boldstone.current_reference_overlay.gleneagles_numbered_flat_components.v1',
    'status': 'COMPLETE_VERIFIED_GLENEAGLES_OWNER_NUMBERING_AND_FLAT_COMPONENT_FOLDERS',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'owner_decision': owner,
    'family': plan['family'], 'summary': counts, 'prefix_maps': plan['folder_renames'],
    'objects': objects, 'created_folders': created_folders, 'created_reference_documents': docs,
    'component_finish_bindings': bindings, 'reference_link_checks': hrefs,
    'catalogue_projection': [
        'Root alone writes the master. Adopt the explicitly owner-approved component numbering and new component/White option display names from the bindings.',
        'Preserve all four existing component and product IDs, old positional names as aliases, accepted specifications, source snapshots and image roles.',
        'Expose component/finish folder IDs separately from the actual unchanged parent IDs of group-image files.',
        'All four individual-image statuses remain Group only. New HTML documents are not photographs.',
        'All nine original images remain shared four-panel group, detail, workshop or in situ references; no extra product or manufactured-design identity is inferred.',
        'Preserve flat direct-family naming with full component names repeated in group folder names; no Arrangements, component or finish nesting is introduced.',
    ], 'verification': verification,
    'receipts': [{'path': str((OUT / n).resolve()), 'sha256': hashlib.sha256((OUT / n).read_bytes()).hexdigest()} for n in names],
    'rollback': plan['rollback'], 'master_write_owner': plan['master_write_owner'], 'master_writes_by_this_lane': 0}
p = OUT / 'current-reference-overlay.json'
assert not p.exists()
p.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'overlay': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'verification': verification['status'], 'counts': counts}))
