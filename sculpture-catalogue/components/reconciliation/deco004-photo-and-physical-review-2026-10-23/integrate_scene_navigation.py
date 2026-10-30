"""Project sealed native navigation changes and one scoped owner deferral."""
import copy, hashlib, json, shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()
def write(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

assert not (H / 'scene-navigation-import.json').exists(), 'Already integrated'
m = read(H / 'input-manifest.json')
for key, item in m.items():
    assert sha(item['path']) == sha(item['snapshot']) == item['sha256'], key
packet = B.parent / 'reports/dropbox-deco-acanthus-flower-scene-folder-rename-2026-10-23'
deferral_path = B / 'components/parallel-reviews/terminal-guided-context-20261023T205215Z/owner-deferral.json'
for key, path in [('scene_overlay', packet/'current-reference-overlay.json'),
                  ('scene_seal', packet/'execution-seal.json'),
                  ('scene_originals', packet/'original-content-verification.json'),
                  ('owner_context_deferral', deferral_path)]:
    dest = H/'inputs'/(key+'.before')
    shutil.copy2(path, dest)
    m[key] = {'path':str(path), 'snapshot':str(dest), 'sha256':sha(path)}
write(H/'input-manifest.json', m)
overlay = read(m['scene_overlay']['snapshot'])
seal = read(m['scene_seal']['snapshot'])
assert overlay['status'] == seal['status'] == 'COMPLETE_VERIFIED'
for item in seal['native_receipts'] + seal['review_receipts']:
    assert sha(item['path']) == item['sha256'], item['path']
pid = 'id:cnqzTNngPVsAAAAAAAyh5w'
held = {'id:cnqzTNngPVsAAAAAAAyh6w', 'id:cnqzTNngPVsAAAAAAAyh6g'}
fid004 = 'id:cnqzTNngPVsAAAAAAAyluQ'
prefix, = overlay['prefix_maps']
assert prefix['file_id'] == pid and set(prefix['applicable_file_ids']) == held
assert overlay['summary']['actual_file_parent_changes'] == 0
assert overlay['summary']['new_ids'] == overlay['summary']['deleted_ids'] == 0
fresh = {}
for item in read(H/'fresh-scene-followup-metadata.json')['records']:
    result = item['result']
    assert not result.get('isError')
    content = result['structuredContent']
    fresh[item['id']] = content[content['metadata_type']]
native = read(H/'current-native-reference-map.json')
assets = read(H/'current-assets.json')
objects = {x['file_id']: x for x in overlay['objects']}
history = []
newly_represented = []
for ident in [pid] + sorted(held):
    item, metadata = objects[ident], fresh[ident]
    assert item['current_path'] == 'ns:202238505/' + metadata['path_display']
    assert item['current_name'] == metadata['name']
    assert item['old_parent_id'] == item['current_parent_id']
    prior = copy.deepcopy(native['current_objects'].get(ident))
    if prior is None:
        assert ident in held
        a = assets[ident]
        prior = {'file_id':ident, 'object_type':'file', 'name':a['name'],
                 'path':a['path'], 'display_path':a['display_path'],
                 'parent_id':a['folder_id'], 'size':a['bytes']}
        newly_represented.append(ident)
    assert prior['path'] == item['old_path']
    current = {**prior, 'name':metadata['name'], 'path':item['current_path'],
               'display_path':metadata['path_display'], 'parent_id':item['current_parent_id']}
    if ident in held:
        assert metadata['size'] == item['size'] == prior['size']
        current.update(rev=metadata['rev'], client_modified=metadata['client_modified'],
                       server_modified=metadata['server_modified'])
        a = assets[ident]
        a.setdefault('historical_same_id_navigation', []).append(copy.deepcopy(a))
        a.update(path=current['path'], display_path=current['display_path'],
                 folder_path='ns:202238505/' + prefix['current_path'],
                 image_url='https://www.dropbox.com/preview'+quote(current['display_path'],safe='/'),
                 folder_url=prefix['current_native_url'], modified_time=metadata['server_modified'],
                 rev=metadata['rev'])
    native['current_objects'][ident] = current
    for obj in [prior,current]:
        native['old_path_to_id'][obj['display_path'].casefold()] = ident
    history.append({'file_id':ident,'before':prior,'current':current})
assert native['current_objects'][fid004]['parent_id'] == 'id:cnqzTNngPVsAAAAAAA6VrQ'
assert native['current_objects'][fid004]['display_path'] == fresh[fid004]['path_display']
assert fresh[fid004]['rev'] == assets[fid004]['current_native_revision']
native['status'] = 'CURRENT_MAP_WITH_DECO004_PLACEMENT_AND_SCENE_NAVIGATION'
native.setdefault('verified_path_change_history',[]).append({
    'overlay':m['scene_overlay']['path'],'sha256':m['scene_overlay']['sha256'],
    'objects':history,'specific004_placement_overrides_old_folder_prefix':True,
    'canonical002003_identity_state':'ON_HOLD_PER_CURRENT_ROOT_INSTRUCTION'})
originals = read(H/'original-verification.json')
for item in seal['verified_originals']:
    data = Path(item['local_path']).read_bytes()
    content = hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest()
                                    for i in range(0,len(data),4194304))).hexdigest()
    assert sha(item['local_path']) == item['sha256'] and len(data) == item['size']
    assert content == item['content_hash']
    originals['files'].append({'file_id':item['file_id'],'local_original':item['local_path'],
        'sha256':item['sha256'],'bytes':len(data),'dropbox_content_hash':content})
g = read(H/'canonical-master-register.json')
a = read(H/'image-coverage-current.json')
reviews = read(H/'photo-review-queue.json')
state = read(H/'guided-owner-review-state.json')
pending = read(H/'pending-followups.json')
def refresh_current_refs(value):
    if isinstance(value,dict):
        if value.get('file_id') in held:
            item=assets[value['file_id']]
            for key in ['path','image_url','folder_url','folder_id','name']:
                if key in value:value[key]=item[key]
            return
        for key,child in value.items():
            if not key.startswith(('historical','previous','source_assertions')):refresh_current_refs(child)
    elif isinstance(value,list):
        for child in value:refresh_current_refs(child)
affected_current=[]
for option in g['options']:
    if option.get('context_file_id') in held:
        item=assets[option['context_file_id']]
        option.setdefault('historical_deco_scene_navigation_references',[]).append({
            'context_image_url':option['context_image_url'],'context_folder_url':option['context_folder_url'],
            'current_photo_task_review':copy.deepcopy(option.get('current_photo_task_review')),
            'current_candidate_binding_review':copy.deepcopy(option.get('current_candidate_binding_review'))})
        option.update(context_image_url=item['image_url'],context_folder_url=item['folder_url'])
        for key in ['current_photo_task_review','current_candidate_binding_review']:
            if key in option:refresh_current_refs(option[key])
        affected_current.append(option['product_id'])
    assert option.get('file_id') not in held and option.get('series_file_id') not in held
for coverage in a['coverage']:
    if coverage['option_id'] in affected_current:
        coverage.setdefault('historical_deco_scene_navigation_references',[]).append(copy.deepcopy(coverage['in_situ']))
        for key in ['in_situ','terminal_task_review','candidate_binding_review']:
            if key in coverage:refresh_current_refs(coverage[key])
for task in a['missing_pictures']:
    if task['reference'].get('file_id') in held:
        task.setdefault('historical_reference_paths',[]).append(copy.deepcopy(task['reference']))
        refresh_current_refs(task['reference'])
for task in reviews:
    if task.get('source_reference',{}).get('file_id') in held:
        task.setdefault('historical_reference_paths',[]).append(copy.deepcopy(task['source_reference']))
        refresh_current_refs(task['source_reference'])
summary = {'status':'IMPORTED_NAVIGATION_ONLY_IDENTITIES_HELD','recorded_utc':now(),
    'source_overlay':m['scene_overlay']['path'],'source_overlay_sha256':m['scene_overlay']['sha256'],
    'folder_id':pid,'folder_name':prefix['current_name'],'folder_url':prefix['current_native_url'],
    'same_id_folder_names_refreshed':1,'same_id_file_paths_refreshed':2,'actual_file_parent_changes':0,
    'existing_native_ids_newly_represented_in_scoped_map':newly_represented,
    'held_scene_file_ids':sorted(held),'identity_state':'ON_HOLD_PER_CURRENT_ROOT_INSTRUCTION',
    'existing_context_options_refreshed':affected_current,
    'new_photo_roles':0,'specifications_changed':0,'native_writes':0}
g['latest_deco_scene_navigation_refresh'] = summary
pending['entries'] = [x for x in pending['entries'] if x.get('kind') != 'LATER_SCENE_IDENTIFICATION_AND_UNAPPLIED_RENAME_PROPOSAL']
pending.setdefault('imported_packet_history',[]).append({
    'kind':'COMPLETED_SCENE_RENAME_NAVIGATION_ONLY','path':m['scene_overlay']['path'],
    'sha256':m['scene_overlay']['sha256'],'applied_to_current_frozen_release':True,
    'current_002_003_identity_hold_preserved':True,'native_rename_already_completed':True})
pending['status'] = 'COMPLETED_DECO_NAVIGATION_IMPORTED_MASTER_IDENTITY_HOLDS_RETAINED'
pending['held_scene_identity_reviews'] = {'file_ids':sorted(held),'state':summary['identity_state'],
    'native_folder_navigation_current':True,'photo_roles_or_canonical_identities_imported':False}

d = read(m['owner_context_deferral']['snapshot'])
assert d['option_id'] == 'BSI-9B2B466B38BE' and d['owner_text'] == 'ignore it for the time being'
events = []
for line in Path(d['source']['transcript']).open():
    if d['source']['timestamp'] in line:
        z=json.loads(line)
        if z.get('payload',{}).get('id')==d['source']['message_id']: events.append(z)
assert len(events)==1 and events[0]['payload']['role']=='user'
assert d['owner_text'] in [x.get('text') for x in events[0]['payload']['content']]
oid=d['option_id']; note='Owner deferred this context photograph on 23 October 2026: "ignore it for the time being". Gap remains open until owner resumes.'
event={**d,'canonical_applied':True,'applied_utc':now(),'source_receipt':m['owner_context_deferral']['path'],'source_sha256':m['owner_context_deferral']['sha256']}
o=next(x for x in g['options']if x['product_id']==oid)
o['current_context_owner_deferral']=event
c=next(x for x in a['coverage']if x['option_id']==oid)
c['in_situ']['owner_deferral']=event
c['owner_review']=(c.get('owner_review','')+'\n'+note).strip()
for task in a['missing_pictures']:
    if task['option_id']==oid and task['role']=='In situ':
        task['owner_response']=note;task['owner_deferral']=event
for task in reviews:
    if task['option_id']==oid and task['role']=='In situ':
        task['owner_deferral']=event;task['next_action']='Hold this context request until the owner resumes.'
assert oid in state['queues']['in_situ']
state['queues']['in_situ'].remove(oid)
state.setdefault('owner_held_context_reviews',[]).append(event)
state['latest_completed_scope'].update(active_in_situ_reviewed=13,held_unchanged=8,new_context_deferrals=1,held_context_cases=9,series_reviewed=17)
state['updated_utc']=now()
state['working_specification_question']='One Leaf Left Pewter actual measurements, bare-panel weight, maker material and fitted fixing requested separately; accepted estimates retained.'
g['latest_owner_context_deferral_import']=event
g['latest_active_photo_source_review'].update(active_context_requests=13,series_requests=17,held_context_cases=9,original_roles_reviewed=31,active_roles=30)
photo=read(H/'photo-source-review.json')
deferred=[x for x in photo['requests']if x['option_id']==oid and x['role']=='Display/context']
assert len(deferred)==1
deferred[0].update(review_state='OWNER_DEFERRED_GAP_RETAINED',owner_deferral=event)
photo['requests']=[x for x in photo['requests']if x not in deferred]
photo['held_requests']=deferred
photo.update(status='31_ROLES_REVIEWED_30_ACTIVE_AFTER_SCOPED_OWNER_DEFERRAL',role_counts={'Display/context':13,'Series':17},original_roles_reviewed=31,held_context_cases=9)
source=read(H/'source-evidence-verification.json')
source.update(scene_navigation_sealed_native_receipts=len(seal['native_receipts']),scene_navigation_sealed_review_receipts=len(seal['review_receipts']),fresh_scene_metadata_objects=4,whole_original_rehashed=3,owner_deferral_transcript_verified=True)
for name,value in [('canonical-master-register.json',g),('image-coverage-current.json',a),
                   ('current-native-reference-map.json',native),('current-assets.json',assets),
                   ('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),
                   ('pending-followups.json',pending),('scene-navigation-import.json',summary),
                   ('scene-navigation-history.json',history),('owner-context-deferral-import.json',event),
                   ('photo-source-review.json',photo),('source-evidence-verification.json',source),
                   ('original-verification.json',originals)]:write(H/name,value)
evidence=read(H/'evidence-manifest.json')
for name in ['fresh-scene-followup-metadata.json','scene-navigation-import.json','scene-navigation-history.json',
             'owner-context-deferral-import.json','photo-source-review.json','source-evidence-verification.json','original-verification.json']:
    evidence[str(H/name)]={'sha256':sha(H/name)}
write(H/'evidence-manifest.json',evidence)
print(json.dumps({'status':'PASS','scene_file_paths_refreshed':2,'004_placement_retained':True,'identity_holds_retained':2,'active_context_requests':13,'held_context_cases':9,'series_requests':17,'physical_changes':0}))
