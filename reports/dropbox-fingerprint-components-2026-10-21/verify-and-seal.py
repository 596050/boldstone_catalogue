import hashlib
import json
from collections import Counter
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
def native_url(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(fq(path), safe='/')
baseline = read('baseline-native.json')
post = read('after-native-readback.json')
after = post['listing']
plan = read('split-plan.json')
assert not baseline['has_more'] and not after['has_more']
before_id = {x['file_id']: x for x in baseline['entries']}
after_id = {x['file_id']: x for x in after['entries']}
after_path = {fq(x['path']): x for x in after['entries']}
family = post['family_metadata']['folder']
family_path, family_id = family['path_display'], family['id']
assert set(before_id) <= set(after_id)
assert len(before_id) == 83 and len(after_id) == 94

def parent_id(item, mapping):
    path = fq(item['path']).rsplit('/', 1)[0]
    if path == family_path:
        return family_id
    return mapping[path]['file_id']
before_path = {fq(x['path']): x for x in baseline['entries']}
objects = []
for ident, old in before_id.items():
    new = after_id[ident]
    assert old['object_type'] == new['object_type']
    expected = fq(old['path'])
    for move in plan['folder_moves']:
        if expected == move['source_path'] or expected.startswith(move['source_path'] + '/'):
            expected = move['destination_path'] + expected[len(move['source_path']):]
            break
    assert fq(new['path']) == expected, (ident, fq(new['path']), expected)
    if old['object_type'] == 'file':
        assert old['name'] == new['name']
        assert old['file']['size'] == new['file']['size']
        assert parent_id(old, before_path) == parent_id(new, after_path)
    objects.append({'file_id': ident, 'object_type': old['object_type'], 'old_name': old['name'],
        'current_name': new['name'], 'old_path': fq(old['path']), 'current_path': fq(new['path']),
        'old_parent_id': parent_id(old, before_path), 'current_parent_id': parent_id(new, after_path),
        'current_native_url': native_url(new['path'], new['object_type'] == 'folder'),
        'size': new.get('file', {}).get('size')})

for i, expected in enumerate(plan['create_folders'], 1):
    result = read(f'create-folder-{i:02}.json')['response']['folder']
    assert expected['path'] in after_path
    assert after_path[expected['path']]['file_id'] == result['file_id']
    assert fq(result.get('path_display') or result['path']) == expected['path']

done = read('move-completion.json')
assert done['status'] == 'completed' and done['result_type'] == 'move'
assert len(done['move_result']['entries']) == 5
for result, move in zip(done['move_result']['entries'], plan['folder_moves']):
    assert result['entry_status'] == 'success'
    assert result['object']['file_id'] == move['source_id']
    assert fq(result['object'].get('path_display') or result['object']['path']) == move['destination_path']

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')

created_docs = []
link_checks = []
for i, upload in enumerate(plan['reference_file_uploads'], 1):
    receipt = read(f'upload-{i:02}-completion.json')
    response = receipt['response']
    assert response['status'] == 'completed'
    new = after_path[upload['destination_path']]
    assert new['file_id'] == response['file']['file_id']
    assert new['file']['size'] == upload['size']
    data = Path(upload['source_file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == upload['sha256']
    assert b'Individual photograph: still needed.' in data
    parser = Links()
    parser.feed(data.decode())
    for link in parser.links:
        parsed = urlparse(link)
        assert parsed.scheme == 'https' and parsed.netloc == 'www.dropbox.com'
        mode, path = parsed.path[1:].split('/', 1)
        assert mode in ('home', 'preview')
        target = '/' + unquote(path)
        assert target in after_path
        link_checks.append({'reference_file_id': new['file_id'], 'url': link,
            'target_file_id': after_path[target]['file_id'], 'verified_by': 'Current native path and stable ID enumeration; no HTTP access audit'})
    created_docs.append({'file_id': new['file_id'], 'path': fq(new['path']), 'size': new['file']['size'], 'local_sha256': upload['sha256']})

before_links = read('baseline-metadata-and-links.json')
for item in post['direct_owned_links']:
    old = before_links[item['id']]['direct_owned_links']
    new = item['result']
    assert not old['has_more'] and not new['has_more']
    assert old['links'] == new['links'] == []

bindings = []
for source in plan['component_finish_bindings']:
    binding = dict(source)
    for role in ('component_folder', 'finish_folder', 'reference_document'):
        current = after_path[source[role + '_path']]
        binding[role + '_id'] = current['file_id']
        binding[role + '_url'] = native_url(current['path'], current['object_type'] == 'folder')
    binding['pair_references'] = [
        {'file_id': ident, 'current_path': fq(after_id[ident]['path']),
            'current_parent_id': parent_id(after_id[ident], after_path),
            'current_native_url': native_url(after_id[ident]['path']), 'image_role': 'Pair or pair context; not isolated individual image'}
        for ident in binding['pair_reference_file_ids']]
    bindings.append(binding)

verification = {
    'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'counts': {'original_files_preserved': 75, 'original_folder_ids_preserved': 8,
        'original_files_with_updated_paths': sum(x['object_type'] == 'file' and x['old_path'] != x['current_path'] for x in objects),
        'existing_folders_moved': 5, 'existing_folders_renamed': 3,
        'new_folders': 7, 'new_reference_documents': 4, 'current_files': 79, 'current_folders': 15,
        'reference_hrefs_bound_to_current_native_objects': len(link_checks), 'individual_image_gaps_retained': 4},
    'all_original_file_ids_names_sizes_and_parent_ids_preserved': True,
    'all_original_folder_ids_preserved': True,
    'all_expected_current_paths_match': True,
    'owned_direct_folder_links_unchanged': True,
    'sharing_scope': 'Five moved folder IDs had zero directly owned links before and after. No sharing mutations. This is not an audit of all descendant, inherited, external or HTTP access.',
    'verification_limits': 'Native enumeration and metadata/size comparisons; original photograph bytes were not newly downloaded or rehashed. Four generated source HTML files hashed locally; upload metadata sizes and native href targets verified, not an HTTP access test.',
    'pending_native_jobs': 0,
}
verification_path = OUT / 'verification.json'
assert not verification_path.exists()
verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
receipts = []
for path in sorted(OUT.glob('*.json')):
    receipts.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
overlay = {
    'status': 'COMPLETE_VERIFIED_FINGERPRINT_COMPONENT_FOLDER_SPLIT',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'scope': 'Fingerprint only; existing approved concentric Left/Right component identities and four White/Verdigris catalogue options',
    'authorization': plan['authorization'], 'family_id': family_id, 'family_path': family_path,
    'summary': verification['counts'],
    'prefix_maps': [{'file_id': x['source_id'], 'old_path': x['source_path'], 'current_path': x['destination_path'], 'role': x['role']} for x in plan['folder_moves']],
    'objects': objects,
    'created_folders': [{**x, 'file_id': after_path[x['path']]['file_id'], 'current_native_url': native_url(x['path'], True)} for x in plan['create_folders']],
    'created_reference_documents': created_docs,
    'component_finish_bindings': bindings,
    'reference_link_checks': link_checks,
    'catalogue_projection': [
        'Preserve all existing component/product IDs, accepted names and specifications.',
        'Expose the new component and finish folders separately from the actual parent folders of pair-reference image files.',
        'Keep the four individual photograph statuses Group only. Reference documents are not photographs.',
        'All pair or group photographs remain arrangement/series/context references. Do not introduce new product records from those photographs.',
        'Whole source composition number 2 contains both concentric components; individual member numbers remain null.',
        'No Dropbox deletion, image edit, duplicate photograph, new shared link or master workbook write by this lane.',
    ],
    'verification': verification, 'receipts': receipts, 'rollback': plan['rollback'],
}
target = OUT / 'fingerprint-component-split-current-overlay.json'
assert not target.exists()
target.write_text(json.dumps(overlay, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'overlay': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'verification': verification['status'], 'counts': verification['counts']}))
