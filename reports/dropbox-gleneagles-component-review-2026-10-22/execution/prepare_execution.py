import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

OUT = Path(__file__).parent
prepared_path = OUT.parent / 'component-image-review-and-prepared-plan.json'
assert hashlib.sha256(prepared_path.read_bytes()).hexdigest() == 'ca7f47830b719d4ce66f245d0293ec95014f2b311f83e074ec7d0df5bce3d116'
prepared = json.loads(prepared_path.read_text())
baseline = json.loads((OUT / 'before-native-inventory.json').read_text())
prior = json.loads((OUT.parent / 'baseline-native-inventory.json').read_text())['listing']
old = {x['file_id']: x for x in prior['entries']}
fresh = {x['file_id']: x for x in baseline['listing']['entries']}
assert not baseline['listing']['has_more'] and old.keys() == fresh.keys()
for ident, original in old.items():
    assert original['path'] == fresh[ident]['path'] and original['name'] == fresh[ident]['name'] and original['object_type'] == fresh[ident]['object_type']
    if original['object_type'] == 'file':
        assert original['file']['size'] == fresh[ident]['file']['size']
root = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Gleneagles Vine and Tendril'
assert baseline['family_metadata']['folder']['id'] == 'id:cnqzTNngPVsAAAAAAAydJQ'
assert baseline['family_metadata']['folder']['path_display'] == root

owner_decision = {'status': 'EXPLICIT_OWNER_APPROVED_NEW_COMPONENT_NUMBERING_AND_FLAT_FOLDER_EXECUTION',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'owner_response': 'do it',
    'immediately_preceding_proposal': '1 = Top Left; 2 = Top Right; 3 = Bottom Left; 4 = Bottom Right. Then create four component folders directly under the family and rename the two group folders using the full-name convention; preserve all nine existing images.',
    'numbering_is_new_owner_convention': True, 'view': 'Front view of existing four-panel reference id:cnqzTNngPVsAAAAAAAylEg',
    'mappings': [{k: m[k] for k in ['component_id', 'product_id', 'approved_position', 'proposed_new_number']} for m in prepared['members']],
    'historical_position_names_retained_as_aliases': True,
    'new_component_or_product_IDs': 0,
    'approved_specification_value_changes': 0,
    'individual_photographs_created_or_reclassified': 0}
assert not (OUT / 'owner-decision.json').exists()
(OUT / 'owner-decision.json').write_text(json.dumps(owner_decision, ensure_ascii=False, indent=2) + '\n')

renames = []
for change in prepared['prepared_flat_numbered_plan']['rename_existing_group_folders']:
    original = fresh[change['folder_id']]
    assert original['path'] == 'ns:202238505/' + change['old_path']
    target = change['proposed_current_path']
    assert not any(x['path'].casefold() == ('ns:202238505/' + target).casefold() for x in fresh.values())
    assert len(target.rsplit('/', 1)[1].encode()) < 255
    renames.append({'file_id': change['folder_id'], 'old_path': change['old_path'], 'current_path': target,
        'old_name': change['old_path'].rsplit('/', 1)[1], 'current_name': target.rsplit('/', 1)[1],
        'expected_file_count': change['direct_file_count']})

def current_path(item):
    path = '/' + item['path'].split('//', 1)[1]
    for change in renames:
        if path == change['old_path'] or path.startswith(change['old_path'] + '/'):
            return change['current_path'] + path[len(change['old_path']):]
    return path
def native(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(path, safe='/')

creates, uploads, bindings = [], [], []
files = sorted((x for x in fresh.values() if x['object_type'] == 'file'), key=lambda x: x['name'])
for member in prepared['members']:
    folder_path = member['proposed_numbered_folder']
    assert not any(x['path'].casefold() == ('ns:202238505/' + folder_path).casefold() for x in fresh.values())
    number = member['proposed_new_number']
    title = f'Gleneagles Vine and Tendril {number} White'
    creates.append({'path': folder_path, 'component_id': member['component_id'], 'product_id': member['product_id'], 'number': number, 'position': member['approved_position']})
    rows = []
    for item in files:
        role = next(x['image_role'] for x in prepared['image_classifications'] if x['file_id'] == item['file_id'])
        label = {'FOUR_PANEL_GROUP': 'Four-panel group',
            'CROPPED_FOUR_PANEL_DETAIL_NOT_STANDALONE': 'Group detail with cropped edges',
            'FOUR_PANEL_WORKSHOP_REFERENCE': 'Four-panel workshop reference',
            'FOUR_PANEL_IN_SITU_REFERENCE_SCENE_PROVENANCE_UNCONFIRMED': 'Four-panel in situ reference; scene provenance unconfirmed'}[role]
        rows.append('<tr><td><a href="' + html.escape(native(current_path(item)), quote=True) + '">' + html.escape(item['name']) + '</a></td><td>' + html.escape(label) + '</td></tr>')
    body = '<!doctype html>\n<html lang="en"><meta charset="utf-8"><title>' + html.escape(title) + '</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;line-height:1.5}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}table{border-collapse:collapse;width:100%}</style><h1>' + html.escape(title) + '</h1><p>Component ' + str(number) + ' is the ' + html.escape(member['approved_position'].lower()) + ' panel in the front-view reference. Numbering follows the owner\'s approved convention.</p><p><strong>Individual photograph: still needed.</strong> The links below show the four-panel group or its context; they are reference images for this component.</p><table><thead><tr><th>Photograph</th><th>Reference role</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table><p>Existing catalogue component: ' + html.escape(member['component_id']) + '. Existing White option: ' + html.escape(member['product_id']) + '.</p><p>The viewer\'s existing Dropbox access is required. No new shared links were created.</p></html>\n'
    local = OUT / 'reference-files' / (member['component_id'] + '-White.html')
    local.parent.mkdir(exist_ok=True)
    assert not local.exists()
    local.write_text(body)
    destination = folder_path + '/Group Image References.html'
    uploads.append({'source_file': str(local.resolve()), 'destination_path': destination,
        'sha256': hashlib.sha256(local.read_bytes()).hexdigest(), 'size': local.stat().st_size})
    bindings.append({'component_id': member['component_id'], 'product_id': member['product_id'],
        'new_component_name': f'Gleneagles Vine and Tendril {number}',
        'new_option_name': f'Gleneagles Vine and Tendril {number} — White',
        'old_approved_option_name': member['existing_approved_name'],
        'component_number': number, 'approved_position': member['approved_position'],
        'finish': 'White', 'component_finish_folder_path': folder_path,
        'reference_document_path': destination, 'group_reference_file_ids': [x['file_id'] for x in files],
        'individual_photo_status': 'Group only', 'new_individual_photo': False,
        'primary_group_reference_file_id': member['reference_file_id']})

plan = {'status': 'AUTHORIZED_EXACT_GLENEA G LES_FLAT_COMPONENT_EXECUTION'.replace('GLENEA G LES', 'GLENEAGLES'),
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'authorization': owner_decision, 'family': {'file_id': 'id:cnqzTNngPVsAAAAAAAydJQ', 'path': root},
    'autorename': False, 'create_folders': creates, 'folder_renames': renames,
    'reference_file_uploads': uploads, 'component_finish_bindings': bindings,
    'original_image_edits_crops_copies_deletions': [], 'delete_items': [],
    'expected': {'original_images_preserved': 9, 'original_child_folder_IDs_preserved': 2,
        'original_family_folder_ID_preserved': True, 'new_component_folders': 4,
        'existing_group_folders_renamed': 2, 'new_reference_documents': 4,
        'new_nested_levels': 0, 'standalone_individual_image_gaps_retained': 4},
    'rollback': 'Rename the two existing group folder IDs back to the recorded old paths. Removing the four new reference documents and then-empty component folders requires separate explicit deletion confirmation.',
    'master_write_owner': '01a144ab-1a7c-7223-a403-73a4d53d70ff'}
p = OUT / 'execution-plan.json'
assert not p.exists()
p.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'plan': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'expected': plan['expected']}))
