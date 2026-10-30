#!/usr/bin/env python3
"""Isolated data draft for the canonical publisher; changes no live controls."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json
import sqlite3

H = Path(__file__).resolve().parent
P = H.parents[2]
B = P/'sculpture-catalogue'
D = H/'staged-retirement'
D.mkdir(exist_ok=True)
OLD = 'BSI-E7CDC2CFAC9D'
KEEP = 'BSI-93ADE7C4103D'
NAME = 'Acanthus Two Leaves White'
load = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name, value):
    (D/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

pointer = load(B/'current-master.json')
source = B/pointer['register']
assert sha(source) == pointer['register_sha256']
before = load(source)
assert OLD in before['active_option_ids'] and KEEP in before['active_option_ids']
g = copy.deepcopy(before)
options = {o['product_id']: o for o in g['options']}
old, keep = options[OLD], options[KEEP]
decision = {**load(H/'owner-duplicate-decision.json'),
    'decision_id': 'ACANTHUS-DECO-TWO-LEAVES-WHITE-DUPLICATE-20261027',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'RETIRED_DUPLICATE_RETAINED_IN_HISTORY',
    'option_id': OLD, 'replacement_option_id': KEEP,
    'instruction_path': str(H/'owner-duplicate-decision.json'),
    'instruction_sha256': sha(H/'owner-duplicate-decision.json')}
old.update(catalogue_status='Retired', active_catalogue_option=False,
    counted_as_individual_option=False, count_class='Retired duplicate - historical identity retained',
    catalogue_retirement=decision, current_offer_active=False,
    historical_selling_details_only=True, current_availability='Retired duplicate of '+NAME,
    current_measurement_required=False, replacement_option_id=KEEP)
old['photo_coverage'].update(individual='Retired / not applicable', in_situ='Retired / not applicable', series='Retired / not applicable')
old.setdefault('current_photo_task_review', {}).update(state='OWNER_RETIRED_DUPLICATE', retirement=decision,
    next_action='Use the surviving Acanthus Two Leaves White entry; no duplicate photo task.')
old['current_listing_resolution'] = {**old.get('current_listing_resolution', {}), 'catalogue_active': False,
    'status': 'RETIRED_DUPLICATE_NO_CURRENT_OFFER_OR_DRAFT_CREATION', 'replacement_option_id': KEEP}
keep['name'] = NAME
keep['retained_names'] = list(dict.fromkeys([*keep.get('retained_names', []), 'Acanthus Two Leaves', old['name'], 'Deco Two Leaves - White']))
keep.setdefault('owner_confirmed_duplicate_aliases', []).append(decision)
g['active_option_ids'].remove(OLD)
g['retired_option_ids'].append(OLD)
g['catalogue_retirements'].append(decision)
g['latest_catalogue_retirement'] = decision
g['count_definition'] = '186 active individually offered options; 189 retained history records including three retired options. No physical stock or mould count inferred.'
for component in g['components']:
    if OLD in component.get('option_ids', []):
        component['historical_option_members_before_duplicate_retirement'] = {k: copy.deepcopy(component.get(k)) for k in ['option_ids','option_names','option_count']}
        component['option_ids'] = [v for v in component['option_ids'] if v != OLD]
        component['option_names'] = [options[v]['name'] for v in component['option_ids']]
        component['option_count'] = len(component['option_ids'])
        component.setdefault('retired_option_ids', []).append(OLD)
        component['owner_confirmed_option_alias'] = decision
    elif KEEP in component.get('option_ids', []):
        component['option_names'] = [options[v]['name'] for v in component['option_ids']]
for group in g['current_working_design_group_projection']['groups']:
    if OLD in group.get('active_option_ids', []):
        group['historical_active_option_ids_before_duplicate_retirement'] = group['active_option_ids'][:]
        group['active_option_ids'].remove(OLD)
g['current_working_design_group_projection']['active_individual_finish_option_count'] = 186
g['summary'].update(individual_options_on_identified_components=179,
    individual_named_working_options=186, individual_options_with_dropbox_reference=185,
    current_option_records=186, current_field_groups=1116, options_with_six_working_fields=186,
    retained_option_records=189, retired_option_records=3, retained_working_field_groups=1134)
g['aliases'].append({'alias_id': decision['decision_id'], 'source': old['name'],
    'targets': [KEEP], 'target_option_ids': [KEEP], 'relationship': 'Owner-confirmed duplicate catalogue option',
    'reason': decision['owner_quote'], 'evidence': str(H/'owner-duplicate-decision.json'),
    'individual_count_increment': 0, 'scope': 'The exact White option only; other finishes and platform sale identities are not inferred.'})
assert len(g['active_option_ids']) == 186 and len(g['retired_option_ids']) == 3
for original in before['options']:
    if original['product_id'] not in [OLD, KEEP]:
        assert original == options[original['product_id']]
for key in ['specifications','master_fields','selling_details','current_primary_selection']:
    assert keep.get(key) == next(o for o in before['options'] if o['product_id'] == KEEP).get(key)
assert g['original_review_specification_assertions'] == before['original_review_specification_assertions']
save('canonical-master-register.draft.json', g)

gallery = (B/pointer['current_published_gallery_projection']['path']).parent/'complete-image-platform-register.sqlite'
database = D/'complete-image-platform-register.draft.sqlite'
assert not database.exists()
with sqlite3.connect('file:'+str(gallery)+'?mode=ro', uri=True) as original:
    with sqlite3.connect(database) as target:
        original.backup(target)
inventory = load(Path.home()/'Library/Application Support/BoldstoneReview/dropbox-sync/inventory.json')
rename_ids = {m['id'] for m in load(H/'native-plan.json')['moves'] if m['kind']=='file'}
admitted_ids = rename_ids | {'id:cnqzTNngPVsAAAAAAAyj8Q'}
transferred = []
with sqlite3.connect(database) as db:
    for pid in [OLD, KEEP]:
        db.execute('UPDATE products SET name=?,record_json=? WHERE product_id=?',
            (options[pid]['name'], json.dumps(options[pid],ensure_ascii=False), pid))
    for aid, _, fid, use, status, raw in db.execute('SELECT * FROM associations WHERE product_id=?', (OLD,)).fetchall():
        if fid not in admitted_ids or fid not in inventory['records']:
            continue
        # Keep the surviving primary. The moved original already has explicit
        # listing/advertising approval in the live app review store.
        if use == 'selected_primary_reference':
            continue
        value = json.loads(raw)
        new_id = hashlib.sha256((aid+'|'+decision['decision_id']+'|'+KEEP).encode()).hexdigest()[:24]
        value.update(association_id=new_id, product_id=KEEP,
            duplicate_consolidation={'original_association_id':aid,'retired_product_id':OLD,'decision':decision})
        native = inventory['records'][fid]
        from urllib.parse import quote
        value['image_url'] = 'https://www.dropbox.com/preview'+quote(native['path'],safe='/')
        value['folder_url'] = 'https://www.dropbox.com/home'+quote(str(Path(native['path']).parent),safe='/')
        value['folder_id'] = native.get('folder_id',value.get('folder_id'))
        db.execute('INSERT INTO associations VALUES (?,?,?,?,?,?)',
            (new_id, KEEP, fid, use, status, json.dumps(value,ensure_ascii=False)))
        transferred.append({'old_association_id':aid,'new_association_id':new_id,'file_id':fid,'use':use,'status':status})
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert any(r['file_id']=='id:cnqzTNngPVsAAAAAAAyluQ' and r['use']=='selected_context_reference' for r in transferred)
save('draft-handoff.json', {'status':'ISOLATED_DRAFT_NOT_PUBLISHED','source_pointer_sha256':sha(B/'current-master.json'),
    'source_register':str(source),'source_register_sha256':sha(source),'source_gallery':str(gallery),'source_gallery_sha256':sha(gallery),
    'draft_register':str(D/'canonical-master-register.draft.json'),'draft_register_sha256':sha(D/'canonical-master-register.draft.json'),
    'draft_gallery':str(database),'draft_gallery_sha256':sha(database),'decision':decision,
    'active_options':186,'other_option_objects_unchanged':187,'survivor_specs_price_primary_unchanged':True,
    'associations':transferred,'remaining_publisher_work':'Reconcile treatment/output/control metadata and publish under source checks; this draft does not alter live controls, platform records, native files or app reviews.'})
print(json.dumps({'status':'ISOLATED_DRAFT_NOT_PUBLISHED','active_options':186,'transferred_associations':len(transferred)}))
