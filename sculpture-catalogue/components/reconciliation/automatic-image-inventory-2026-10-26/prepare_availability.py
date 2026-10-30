"""Prepare cumulative receipt history and independently observed native absence."""
from pathlib import Path
import hashlib
import json

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
p = read(B / 'current-master.json')
assert sha(B / 'current-master.json') == '9a54e024644dc45f22cd69ba7118cee765987a1c5a2c48bb8948be3ee729b726'
previous_path = B / p['current_native_availability']['path']
previous = read(previous_path)
queued_path = B / 'components/reconciliation/queued-native-availability-2026-10-26/queued-receipt-delta.json'
queued = read(queued_path)
verification = read(H / 'independent-verification.json')
native = read(H / 'current-native-overlay.json')
absence = read(H / 'native-absence-register.json')
lookups = {r['target']: r for r in read(H / 'independent-native-metadata.json')['metadata']}
g = read(B / p['register'])
rows = list(previous['rows'])
for r in queued['newer_receipts']:
    assert lookups[r['file_id']]['not_found']
    rows.append({'file_id': r['file_id'], 'status': 'DELETED_NATIVE_ABSENCE_VERIFIED', 'name': r['name'],
        'historical_path': r['path_at_deletion'], 'historical_image_url': r['source_snapshot_image_url'],
        'folder_id': r['source_snapshot_folder_id'], 'folder_url': r['source_snapshot_folder_url'],
        'revision_at_deletion': r['revision_at_deletion'], 'bytes_at_deletion': r['bytes_at_deletion'],
        'content_hash_at_deletion': r['content_hash_at_deletion'], 'operation_id': r['job_id'],
        'batch_id': r['batch_id'], 'user_confirmation_utc': r['confirmation_at'],
        'deletion_readback_utc': r['app_native_readback_utc'],
        'independent_native_readback': {'checked_utc': read(H / 'independent-native-metadata.json')['checked_utc'],
            'not_found': True},
        'source_master_example_option_ids': [i['product_id'] for i in r['source_master_reference_impacts'] if 'file_id' in i['roles']],
        'source_master_context_option_ids': [i['product_id'] for i in r['source_master_reference_impacts'] if 'context_file_id' in i['roles']],
        'replacement_primary_selected': False, 'historical_source_records_retained': True})
assert len(rows) == len({r['file_id'] for r in rows}) == 13
assert {r['file_id'] for r in rows} == {r['file_id'] for r in absence['confirmed_app_deletions']}
missing = {r['file_id'] for r in absence['rows']}
impacts = []
for o in g['options']:
    if o['product_id'] not in g['active_option_ids']:
        continue
    for field in ['file_id', 'context_file_id']:
        if o.get(field) in missing:
            impacts.append({'product_id': o['product_id'], 'name': o['name'], 'field': field, 'file_id': o[field]})
packet = {'schema': 'boldstone.native-availability/v3',
    'status': 'PREPARED_FIXED_SNAPSHOT_AND_THIRTEEN_CONFIRMED_DELETION_RECEIPTS',
    'baseline_pointer_sha256': sha(B / 'current-master.json'), 'baseline_register_sha256': p['register_sha256'],
    'review_event_cutoff': verification['review_event_cutoff'], 'last_confirmed_native_event': 1846,
    'native_snapshot': verification['input_snapshot'], 'rows': rows,
    'other_native_absence_rows': [r for r in absence['rows'] if not r['owner_deletion_receipt_present']],
    'source_reference_impacts': impacts,
    'counts': {'active_options_unchanged': 188, 'confirmed_deleted_native_files': 13,
        'baseline_current_wall_files': 6360, 'current_snapshot_wall_files': 6285,
        'baseline_files_native_not_found': 81, 'other_native_absences_without_app_deletion_receipts': 68,
        'new_current_native_files': 6, 'retained_file_ids_with_changed_contents': 2,
        'current_snapshot_folders_including_root': 443, 'current_snapshot_objects_including_root': 6728,
        'affected_source_master_examples': sum(r['field'] == 'file_id' for r in impacts),
        'affected_source_master_contexts': sum(r['field'] == 'context_file_id' for r in impacts)},
    'scope': 'Complete immutable generation 6 image inventory plus independent native ID and folder checks. Thirteen exact app-confirmed deletions remain distinct from 68 native NOT_FOUND observations without app deletion receipts. No source identity, specification or listing-primary import.',
    'source_evidence': {str(previous_path): sha(previous_path), str(queued_path): sha(queued_path),
        str(H / 'independent-verification.json'): sha(H / 'independent-verification.json'),
        str(H / 'current-native-overlay.json'): sha(H / 'current-native-overlay.json')},
    'native_mutations_by_this_phase': 0, 'active_review_db_writes': 0}
dump(H / 'availability-overlay.json', packet)
dump(H / 'publication-plan.json', {'status': 'PREPARED_AWAITING_APP_2_3_1_AND_DECO_PALM_RENAME_HANDOFFS',
    'baseline_pointer_sha256': packet['baseline_pointer_sha256'],
    'availability_overlay_sha256': sha(H / 'availability-overlay.json'),
    'shared_control_writes': 0, 'workbook_unchanged': True,
    'pending': ['Verify sealed 2.3.1 app change with exact In Situ folder association and saved override protection',
        'Verify completed Deco Palm and Spiral folder rename receipt and current paths before registering latest navigation']})
print(json.dumps({'status': packet['status'], 'confirmed_receipts': 13, 'other_native_absences': 68,
    'selected_source_impacts': impacts, 'shared_writes': 0}, indent=2))
