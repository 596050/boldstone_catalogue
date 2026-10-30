import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

OUT = Path(__file__).parent
CAT = OUT.parents[1] / 'sculpture-catalogue'
root = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Gleneagles Vine and Tendril'
baseline = json.loads((OUT / 'baseline-native-inventory.json').read_text())['listing']
assert not baseline['has_more'] and len(baseline['entries']) == 11
files = [x for x in baseline['entries'] if x['object_type'] == 'file']
sources = CAT / 'components/parallel-reviews/gleneagles-2026-10-18'
members = []
for number, slug, position, product_id in [
    (1, 'top-left-white', 'Top Left', 'BSI-53239DE28BCA'),
    (2, 'top-right-white', 'Top Right', 'BSI-49CB2EDD232C'),
    (3, 'bottom-left-white', 'Bottom Left', 'BSI-48D13D8D7E67'),
    (4, 'bottom-right-white', 'Bottom Right', 'BSI-8957C5C51828')]:
    path = sources / slug / 'identity-approval.json'
    approval = json.loads(path.read_text())
    assert approval['identity_confirmed'] and approval['reference_file_id'] == 'id:cnqzTNngPVsAAAAAAAylEg'
    members.append({'component_id': approval['component_id'], 'product_id': product_id,
        'approved_position': position, 'existing_approved_name': approval['canonical_name'],
        'proposed_new_number': number, 'number_is_existing_public_source_code': False,
        'owner_number_decision_pending': True,
        'proposed_numbered_folder': root + f'/Gleneagles Vine and Tendril {number} White',
        'positional_alternative_folder': root + '/Gleneagles Vine and Tendril ' + position + ' White',
        'owner_identity_receipt': str(path.resolve()),
        'owner_identity_receipt_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'reference_file_id': 'id:cnqzTNngPVsAAAAAAAylEg',
        'individual_photo_status': 'Group only'})

classification = []
for item in sorted(files, key=lambda x: x['name']):
    role = 'FOUR_PANEL_GROUP'
    if 'white-in-situ' in item['name']:
        role = 'FOUR_PANEL_IN_SITU_REFERENCE_SCENE_PROVENANCE_UNCONFIRMED'
    elif item['name'].endswith('white__004.jpg'):
        role = 'CROPPED_FOUR_PANEL_DETAIL_NOT_STANDALONE'
    elif item['name'].endswith('white__005.jpg'):
        role = 'FOUR_PANEL_WORKSHOP_REFERENCE'
    classification.append({'file_id': item['file_id'], 'name': item['name'], 'current_native_path': item['path'],
        'size': item['file']['size'], 'image_role': role,
        'depicted_component_IDs': [m['component_id'] for m in members],
        'standalone_component_photograph': False,
        'scope': 'Depicted pattern and position comparison, not proof of the same physical cast, material or scene provenance.'})

full_group = ' and '.join('Gleneagles Vine and Tendril ' + str(n) for n in range(1, 5))
renames = []
for ident, old, suffix in [('id:cnqzTNngPVsAAAAAAAyigA', 'Gleneagles Vine and Tendril White', ' White'),
                          ('id:cnqzTNngPVsAAAAAAAyigQ', 'Gleneagles Vine and Tendril White In Situ', ' White In Situ')]:
    renamed = full_group + suffix
    assert len(renamed.encode()) < 255
    renames.append({'folder_id': ident, 'old_path': root + '/' + old, 'proposed_current_path': root + '/' + renamed,
        'direct_file_count': sum(f['path'].rsplit('/', 1)[0].endswith('/' + old) for f in files)})

review = {'status': 'ALL_NINE_IMAGES_REVIEWED; PUBLIC_COMPONENT_NUMBERING_AWAITS_OWNER_DECISION',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'source_inventory': 'baseline-native-inventory.json', 'visual_board': 'all-nine-images.jpg',
    'cached_preview_hashes_and_original_ID_size_crosscheck': 'visual-review-manifest.json',
    'counts': {'existing_original_images': 9, 'existing_child_folders': 2, 'identified_catalogue_components': 4,
        'standalone_individual_images_verified': 0, 'new_original_downloads': 0, 'remote_mutations': 0},
    'members': members, 'image_classifications': classification,
    'question': 'Use new member numbers 1 Top Left, 2 Top Right, 3 Bottom Left, 4 Bottom Right, or retain approved positional names?',
    'question_reason': 'Previous owner approvals establish positional component names only. The numeric suffixes on internal catalogue IDs do not establish a public numbering convention.',
    'prepared_flat_numbered_plan': {'conditional_on_explicit_owner_number_answer': True,
        'create_component_folders': [m['proposed_numbered_folder'] for m in members],
        'rename_existing_group_folders': renames,
        'add_reference_documents': ['One Pair and Group References.html per component folder, linking existing shared four-panel images; no new individual-image claim.'],
        'existing_original_images_to_edit_crop_copy_delete': [], 'new_nesting_levels': 0,
        'expected_original_images_preserved': 9, 'expected_existing_parent_folder_IDs_preserved': 2,
        'four_existing_component_and_product_IDs_preserved': True},
    'not_executed': True, 'shared_master_writes': 0,
}
path = OUT / 'component-image-review-and-prepared-plan.json'
assert not path.exists()
path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'review': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'counts': review['counts'], 'pending_question': review['question']}))
