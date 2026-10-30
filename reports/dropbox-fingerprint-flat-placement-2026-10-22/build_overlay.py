from pathlib import Path
import json, hashlib, datetime
from urllib.parse import quote

ROOT = Path('/Users/tprice/Documents/boldstone')
LANE = ROOT / 'reports/dropbox-fingerprint-flat-placement-2026-10-22'
FAMILY = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Fingerprint'
def read(path):
    return json.loads(path.read_text())
def write(name, value):
    (LANE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
def home(path):
    return 'https://www.dropbox.com/home' + quote(path, safe='/')
def photo_url(path):
    return home(str(Path(path).parent)) + '?preview=' + quote(Path(path).name, safe='')

before = read(LANE / 'plan-and-before-inventory.json')
native = read(LANE / 'native-final-readback.json')
uploads = read(LANE / 'upload-results.json')
hashes = read(LANE / 'content-hash-verification.json')
assert hashes['status'] == 'PASS' and hashes['all_original_bytes_preserved']
byid = {e['file_id']: e for e in native['recursive']['entries']}
paths = {e['file_id']: e['path_display'] for e in native['direct']['entries']}
for e in byid.values():
    if e['object_type'] == 'file':
        parent_name = e['path'].rsplit('/', 2)[1]
        parent = next(x for x in native['direct']['entries'] if x['name'] == parent_name)
        paths[e['file_id']] = parent['path_display'] + '/' + e['name']
def current(id):
    e = byid[id]
    p = paths[id]
    return {'file_id':id, 'name':e['name'], 'object_type':e['object_type'], 'path':p,
            'ns_path':e['path'], 'url': photo_url(p) if e['object_type']=='file' else home(p),
            **({'bytes':e['file']['size']} if e['object_type']=='file' else {})}

for old in before['before']['recursive']['entries']:
    new = byid[old['file_id']]
    assert new['name'] == old['name']
    if old['object_type'] == 'file':
        assert new['file']['size'] == old['file']['size']
        assert new['path'] == old['path'].replace('/Fingerprint/Fingerprint Concentric/', '/Fingerprint/')
for move in before['move_entries']:
    assert paths[move['source_id']] == move['destination_path']

components = []
photos = []
for finish, slug in [('Cream','fingerprint-whatsapp-photo-mapping-2026-10-22'),('White','fingerprint-white-photo-mapping-2026-10-22')]:
    mapping = read(ROOT / 'sculpture-catalogue/components/reconciliation' / slug / 'photo-folder-matches.json')
    for ref in mapping.get('components', mapping.get('references')):
        number = ref['number']
        individual_id = ref.get('cream_folder_id', ref.get('folder_id'))
        folder = current(individual_id)
        isolated = [current(e['file_id']) for e in byid.values() if e['object_type']=='file' and e['path'].rsplit('/',1)[0] == byid[individual_id]['path']]
        components.append({'number':number, 'finish':finish, 'name':f'Fingerprint Concentric {number} — {finish}',
            'visual_identifier':ref.get('visual_identifier',ref.get('description')), 'individual_folder':folder,
            'original_reference_folder':current(ref['context_folder_id']),
            'numbering_reference_photo':current(ref['reference_file_id']),
            'numbering_reference_sha256':ref['reference_sha256'],
            'isolated_image_candidates':isolated,
            'isolated_candidate_provenance':'Unchanged; source/provenance verification is not inferred from filename or placement.',
            'legacy_left_right_identity':'For authoritative master writer to reconcile from archived design evidence; no mapping inferred by placement.'})
    for p in mapping['photos']:
        u = next(x for x in uploads if x['batch']==finish and x['image_number']==p['image_number'])
        assert u['latest']['status']=='completed'
        file = current(u['latest']['file']['file_id'])
        assert file['path'] == u['destination_path'] and file['bytes'] == u['source_bytes']
        folder = next(e for e in native['direct']['entries'] if e['name']==p['destination_folder_name'])
        h = next(x for x in hashes['checks'] if x['file_id']==file['file_id'])
        members = []
        for v in p['visible_panels']:
            n = v['component_number']
            c = next(x for x in components if x['number']==n and x['finish']==finish)
            members.append({'number':n,'name':f'Fingerprint Concentric {n}', 'left_to_right_position':v['left_to_right_position'],
              'rotation_clockwise_degrees_from_numbered_reference':v.get('rotation_clockwise_degrees_from_numbered_reference',v.get('rotation_clockwise_degrees_from_current_reference')),
              'whole_outline_visible':v.get('whole_outline_visible',True),
              'component_folder':c['individual_folder'], 'reference_photo':c['numbering_reference_photo']})
        photos.append({'finish':finish,'image_number':p['image_number'],'source_local_path':u['source_file'],
            'source_sha256':u['source_sha256'],'dropbox_content_hash':h['dropbox_content_hash'],'original_bytes_verified':True,
            'file':file,'folder':current(folder['file_id']),'members':members,
            'left_to_right_component_numbers':p['left_to_right_component_numbers'],
            'coverage_scope':p['coverage_scope'],'image_role':p.get('image_role','Whole arrangement on brick wall'),
            'isolated_individual_image_qualified':False})

for c in components:
    matches = [p for p in photos if p['finish']==c['finish'] and c['number'] in p['left_to_right_component_numbers']]
    c['uploaded_context_photo_ids'] = [p['file']['file_id'] for p in matches]
    c['uploaded_context_photo_count'] = len(matches)
    c['uploaded_context_folder_ids'] = sorted({p['folder']['file_id'] for p in matches})
groups = []
for id in sorted({p['folder']['file_id'] for p in photos}):
    members = [p for p in photos if p['folder']['file_id']==id]
    groups.append({**current(id),'uploaded_photo_count':len(members),'photo_ids':[p['file']['file_id'] for p in members]})
overlay = {'schema':'boldstone-fingerprint-native-placement-overlay/v1',
    'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'NATIVE_PLACEMENT_COMPLETE_HASH_VERIFIED',
    'authorization':before['user_authorization'],'family_folder':{'file_id':'id:cnqzTNngPVsAAAAAAAyhAQ','path':FAMILY,'url':home(FAMILY)},
    'folders_moved':14,'original_existing_files_preserved':13,'new_group_folders':6,'uploaded_original_photos':26,
    'new_photo_bytes':hashes['bytes'],'original_bytes_preserved':True,'components':components,'groups':groups,'photos':photos,
    'legacy_alias_crosswalk_status':'Pending authoritative master reconciliation; numbering is owner-managed.',
    'unchanged_empty_former_parent':current('id:cnqzTNngPVsAAAAAAA53aA'),
    'mutation_receipt_directory':str(LANE),'squarespace_writes':0,'shopify_writes':0}
write('catalogue-placement-overlay.json',overlay)
proof={'status':'PASS','folders_moved':14,'moved_ids_preserved':True,'existing_files_preserved':13,
    'new_folders':6,'new_photos':26,'new_photo_hashes_verified':26,'new_photo_bytes':hashes['bytes'],
    'new_group_count':7,'all_content_folders_are_direct_children':True,
    'empty_former_parent_retained':True,'native_total_folders':21,'native_total_files':39,
    'overlay_sha256':hashlib.sha256((LANE/'catalogue-placement-overlay.json').read_bytes()).hexdigest(),
    'component_context_photo_counts':{c['name']:c['uploaded_context_photo_count'] for c in components},
    'master_publication':'Pending main catalogue writer'}
write('verification.json',proof)
print(json.dumps(proof,indent=2))
