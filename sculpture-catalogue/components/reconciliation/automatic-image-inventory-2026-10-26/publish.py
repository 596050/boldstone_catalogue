"""Register verified live navigation and app capabilities without source rebasing."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import os
import shutil
import urllib.request

H = Path(__file__).resolve().parent
P = H / 'post-folder-followup'
B = H.parents[2]
APP = B.parent / 'catalogue-review'
OUT = B / 'outputs/folder-tags-and-current-native-2026-10-26'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
arg = argparse.ArgumentParser()
arg.add_argument('--apply', action='store_true')
a = arg.parse_args()
pointer = B / 'current-master.json'
assert sha(pointer) == '9a54e024644dc45f22cd69ba7118cee765987a1c5a2c48bb8948be3ee729b726'
assert not (P / 'publication-receipt.json').exists()
old = read(pointer)
qa_path = P / 'independent-verification.json'
qa = read(qa_path)
assert qa['status'] == 'PASS_INDEPENDENT_FOLDER_TAGS_RENAMES_AND_NATIVE_FOLLOWUP'
assert qa['renamed_folders'] == 18 and qa['retained_deco_file_ids_hashes_sizes_names'] == 629
assert qa['source_field_or_identity_imports'] == 0 and qa['active_review_db_writes_by_root'] == 0
for f, digest in qa['all_application_code_hashes'].items():
    assert sha(f) == digest, f
handoff = Path(qa['handoff_path'])
assert sha(handoff) == qa['handoff_sha256']
q = read(handoff)
for f, digest in q['evidence_sha256'].items():
    assert sha(handoff.parent / f) == digest, f
snapshot = qa['input_snapshot']
assert sha(snapshot['snapshot_path']) == snapshot['snapshot_sha256']
readers = read(P / 'reader-verification.json')
assert readers['current_images'] == 6284 and readers['absence_cards'] == 82
assert readers['active_option_cards'] == 188 and readers['new_upload_cards'] == 6
for f, digest in readers['outputs'].items():
    assert sha(f) == digest, f
availability_path = P / 'availability-overlay.json'
availability_doc = read(availability_path)
assert availability_doc['baseline_pointer_sha256'] == sha(pointer)
assert len(availability_doc['rows']) == 13 and len(availability_doc['other_native_absence_rows']) == 69
assert availability_doc['counts']['current_snapshot_wall_files'] == 6284
for f, digest in availability_doc['source_evidence'].items():
    assert sha(f) == digest, f
terminal = read(P / 'terminal-verification.json')
assert terminal['status'] == 'PASS_CURRENT_TERMINAL_READBACK'
assert terminal['script_sha256'] == sha(H / 'walkthrough.py')
protected = {}
for k in ['register', 'workbook']:
    f = B / old[k]
    assert sha(f) == old[k + '_sha256']
    protected[str(f)] = sha(f)
for k in ['current_asset_reference_map', 'current_native_reference_map']:
    f = B / old[k]['path']
    assert sha(f) == old[k]['sha256']
    protected[str(f)] = sha(f)
f = B / old['preferred_review_workbook']
assert sha(f) == old['current_comprehensive_workbook']['sha256']
protected[str(f)] = sha(f)
base_qa = read(H / 'independent-verification.json')
for f, digest in base_qa['protected_source_hashes'].items():
    if f != 'sculpture-catalogue/current-master.json':
        assert sha(B.parent / f) == digest
        protected[str(B.parent / f)] = digest
with urllib.request.urlopen('http://127.0.0.1:8767/api/health', timeout=10) as r:
    health = json.load(r)
assert health['version'] == '2.3.1' and health['products'] == 188
controls = [B / f for f in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
for f in controls:
    assert read(f)['current_master_catalogue'] == old
now = datetime.now(timezone.utc).isoformat()
availability = {'status': 'CURRENT_NATIVE_SNAPSHOT_WITH_SEPARATE_CONFIRMED_RECEIPT_HISTORY',
    'path': rel(availability_path), 'sha256': sha(availability_path),
    'review': rel(OUT / 'index.html'), 'all_options_review': rel(OUT / 'all-options.html'),
    'absent_reference_review': rel(OUT / 'absent-images.html'),
    'current_native_files': rel(OUT / 'Current_Wall_Images_6284.csv'),
    'native_absence_history': rel(OUT / 'Native_Image_Absences_82.csv'),
    'review_event_cutoff': qa['review_event_cutoff'], 'last_confirmed_native_event': 1846,
    'counts': availability_doc['counts'], 'native_snapshot': snapshot,
    'historical_ids_records_and_source_photo_proof_retained': True,
    'replacement_primary_selections_by_publication': 0, 'physical_verifications': 0,
    'scope': availability_doc['scope'], 'preceding_availability': old['current_native_availability']}
native_map = {'status': 'VERIFIED_COMPLETE_NATIVE_IMAGE_SNAPSHOT',
    'path': rel(P / 'current-native-overlay.json'), 'sha256': sha(P / 'current-native-overlay.json'),
    'source_snapshot': snapshot, 'counts': read(P / 'current-native-overlay.json')['counts'],
    'current_navigation_uses_stable_file_and_folder_ids': True,
    'base_source_maps_are_retained_history': True}
p = copy.deepcopy(old)
p.update(recorded_utc=now, status='CURRENT_MASTER188_WITH_LIVE_IMAGE_NAVIGATION_AND_FOLDER_TAGS',
    current_native_availability=availability, current_live_native_inventory=native_map,
    current_effective_native_inventory={**availability_doc['counts'], 'scope': availability_doc['scope'], 'source_snapshot': snapshot},
    publication_receipt=rel(P / 'publication-receipt.json'))
for k in ['current_asset_reference_map', 'current_native_reference_map']:
    p[k]['native_availability_overlay'] = {'path': availability['path'], 'sha256': availability['sha256']}
    p[k]['current_live_navigation'] = copy.deepcopy(native_map)
    p[k]['underlying_map_is_a_retained_snapshot'] = True
p['current_published_gallery_projection'].update(
    status='RETAINED_SOURCE_GALLERY_WITH_CURRENT_NATIVE_OVERLAY',
    native_availability_overlay={'path': availability['path'], 'sha256': availability['sha256']},
    current_live_native_inventory=copy.deepcopy(native_map),
    native_file_count_scope='Source gallery counts remain historical. The current native overlay resolves IDs, paths, availability and newly uploaded images at its explicit snapshot cutoff.')
p['current_complete_gallery_mapping']['native_availability_overlay'] = copy.deepcopy(availability)
p['current_complete_gallery_mapping']['current_live_native_inventory'] = copy.deepcopy(native_map)
p['current_comprehensive_workbook']['native_availability_is_an_earlier_snapshot'] = True
p['current_comprehensive_workbook']['later_verified_native_navigation'] = copy.deepcopy(native_map)
p['current_comprehensive_workbook']['later_native_review'] = availability['review']
links = p['current_image_review_links']
links.update(all_links=availability['all_options_review'], all_individual_option_galleries=availability['all_options_review'],
    complete_current_wall_images=availability['current_native_files'], current_native_availability=availability['review'],
    current_saved_app_specification_review=availability['all_options_review'],
    current_native_absences=availability['absent_reference_review'],
    latest_native_navigation=rel(OUT / 'deco-renamed-folders.html'),
    new_native_uploads=rel(OUT / 'New_Acanthus_Uploads_6.csv'))
p['current_guided_image_review'].update(
    terminal_review_command=rel(H / 'walkthrough.py'), terminal_review_command_sha256=sha(H / 'walkthrough.py'),
    terminal_runtime_verification=rel(P / 'terminal-verification.json'),
    terminal_runtime_verification_sha256=sha(P / 'terminal-verification.json'),
    native_availability_overlay=copy.deepcopy(availability),
    newly_absent_recorded_context_reference_options=['BSI-3C849B547D50'],
    native_refresh_does_not_reopen_owner_held_photograph_requests=True)
p['current_saved_specification_review'].update(last_independently_preserved_through_event=qa['review_event_cutoff'],
    current_navigation_review=availability['all_options_review'])
app = p['current_review_application']
app['preceding_validation_reference'] = {k: app[k] for k in ['version', 'verification', 'verification_sha256', 'last_verified_utc', 'ui_revision'] if k in app}
app.update(status='LOCAL_REVIEW_APP_AUTOMATIC_IMAGES_AND_FOLDER_TYPES_VERIFIED', version='2.3.1',
    last_verified_utc=now, verification=str(qa_path), verification_sha256=sha(qa_path),
    contract_sha256=sha(APP / 'README.md'), ui_revision='automatic-images-stable-folder-association-and-in-situ-defaults',
    verification_scope='Independent original-byte/native-ID checks, complete snapshot reconciliation, source-folder tags,18 folder renames and preserved owner history.',
    saved_review_snapshot={'event_cutoff': qa['review_event_cutoff'], 'review_rows': qa['saved_review_rows'],
        'app_review_writes_by_catalogue_publisher': 0, 'owner_may_continue_reviewing': True},
    automatic_image_refresh={'enabled': True, 'interval_seconds': 60, 'root_path': '/BOLDSTONE MASTER/Products/01 Wall Sculptures',
        'native_source': copy.deepcopy(native_map), 'new_images_start_unreviewed': True,
        'stable_folder_id_associations_survive_renames': True, 'source_catalogue_and_review_state_remain_separate': True,
        'native_writes_by_refresh_worker': 0, 'last_complete_inventory_retained_on_failure': True},
    folder_types={'in_situ_from_current_folder_label': True, 'explicit_saved_types_and_removals_win': True,
        'exact_unambiguous_sibling_folder_association': True, 'identity_finish_installation_or_listing_approval_inferred': False,
        'verified_target_product': 'BSI-BCAB636141CC', 'verified_target_images': 3},
    authorized_deco_folder_renames={'folders': 18, 'stable_descendant_ids': 647,
        'file_ids_hashes_sizes_and_names_preserved': 629, 'native_revision_metadata_advanced': 629,
        'receipt': str(handoff.parent / 'deco-move-result.json'),
        'receipt_sha256': sha(handoff.parent / 'deco-move-result.json'),
        'review': rel(OUT / 'deco-renamed-folders.html'),
        'executing_thread': '01a13fe6-495b-7253-b923-31823b4cbca8'})
app['release_validation'].update(unit_tests=84, refresh_controller_tests=6)
app['reviewed_native_file_deletion']['known_reconciled_receipt_scope'] = {
    'native_files': 13, 'review_event_cutoff': qa['review_event_cutoff'], 'last_confirmed_native_event': 1846,
    'availability_overlay': availability['path'], 'other_native_not_found_without_app_receipt': 69,
    'scope': '13 exact app deletion receipts; other native absence observations remain separate. Publisher performed no native mutation.'}
p['latest_master_metadata_change'] = {'status': 'CURRENT_NATIVE_OVERLAY_AUTOMATIC_IMAGES_FOLDER_TAGS_AND_VERIFIED_RENAMES',
    'preceding_receipt': old['publication_receipt'], 'source_register_core_workbook_maps_gallery_and_preferred_workbook_bytes_unchanged': True,
    'general_review_choice_imports': 0, 'publisher_native_mutations': 0, 'publisher_active_review_db_writes': 0}
allowed = {'recorded_utc', 'status', 'current_native_availability', 'current_live_native_inventory',
    'current_effective_native_inventory', 'publication_receipt', 'current_asset_reference_map', 'current_native_reference_map',
    'current_published_gallery_projection', 'current_complete_gallery_mapping', 'current_comprehensive_workbook',
    'current_image_review_links', 'current_guided_image_review', 'current_saved_specification_review',
    'current_review_application', 'latest_master_metadata_change'}
assert all(p[k] == old[k] for k in old if k not in allowed)
assert p['all_actual_specifications_complete'] is False
updates = {}
for f in controls:
    d = read(f)
    d.update(updated_utc=now, current_master_catalogue=copy.deepcopy(p))
    for k in allowed - {'recorded_utc', 'status', 'publication_receipt'}:
        if k in p:
            d[k] = copy.deepcopy(p[k])
    updates[f] = d
def write(path, data):
    path = Path(path)
    temp = path.with_name(path.name + '.live-image-publication-tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)
if not a.apply:
    print(json.dumps({'status': 'READY_SCOPED_METADATA_PUBLICATION', 'app_version': '2.3.1', 'images_at_cutoff': 6284,
        'renamed_folders': 18, 'new_native_uploads': 6, 'source_bytes_preserved': True}))
    raise SystemExit(0)
snap = P / 'publication-inputs'
snap.mkdir(exist_ok=True)
snapshots = {}
for f in [pointer, *controls]:
    dest = snap / str(f.relative_to(B)).replace('/', '__')
    assert not dest.exists()
    shutil.copy2(f, dest)
    snapshots[f] = dest
try:
    for f, original in snapshots.items():
        assert sha(f) == sha(original)
    for f, digest in protected.items():
        assert sha(f) == digest
    for f, digest in qa['all_application_code_hashes'].items():
        assert sha(f) == digest
    for f, value in updates.items():
        write(f, value)
    write(pointer, p)
    assert read(pointer) == p and all(read(f)['current_master_catalogue'] == p for f in controls)
    assert all(sha(f) == digest for f, digest in protected.items())
    receipt = {'status': 'PASS_CURRENT_NATIVE_NAVIGATION_APP231_AND_FOLDER_RENAMES_REGISTERED',
        'recorded_utc': now, 'pointer_sha256': sha(pointer), 'preceding_pointer_sha256': sha(snapshots[pointer]),
        'availability_overlay_sha256': sha(availability_path), 'native_map_sha256': native_map['sha256'],
        'native_snapshot': snapshot, 'app_version': '2.3.1', 'active_options': 188,
        'review_event_cutoff': qa['review_event_cutoff'], 'saved_review_rows': qa['saved_review_rows'],
        'current_images_at_fixed_cutoff': 6284, 'new_uploads': 6, 'renamed_folders': 18,
        'confirmed_app_deletion_receipts': 13, 'other_native_absences_without_app_deletion_receipt': 69,
        'publisher_native_mutations': 0, 'publisher_active_review_db_writes': 0,
        'canonical_identity_specification_or_primary_imports': 0,
        'source_and_workbook_files_unchanged': protected, 'app_verification_sha256': sha(qa_path),
        'controls_sha256': {str(f): sha(f) for f in controls}}
    write(P / 'publication-receipt.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ['source_and_workbook_files_unchanged', 'controls_sha256']}, indent=2))
except BaseException:
    for f, original in snapshots.items():
        shutil.copy2(original, f)
    raise
