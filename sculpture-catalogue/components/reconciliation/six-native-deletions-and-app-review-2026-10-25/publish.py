"""Atomically register v4 availability and saved app review evidence only."""
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
B = H.parents[2]
APP = B.parent / 'catalogue-review'
OUT = B / 'outputs/six-native-deletions-and-app-review-2026-10-25'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
arg = argparse.ArgumentParser()
arg.add_argument('--inputs', required=True, type=Path)
arg.add_argument('--apply', action='store_true')
a = arg.parse_args()
inputs = read(a.inputs)
pointer = B / 'current-master.json'
assert sha(pointer) == '8840bcc0389a0a37d85278b41f966a5d909cd59879ee3d77ca29278ab3bb76bb'
old = read(pointer)
assert not (H / 'publication-receipt.json').exists()
overlay = read(H / 'availability-overlay.json')
assert sha(H / 'availability-overlay.json') == '174cdf148b1483216aa5cceec69d708d96679dc95926aed068096dcf4a9d3e37'
assert overlay['baseline_pointer_sha256'] == sha(pointer)
assert overlay['review_event_cutoff'] == 347 and overlay['last_confirmed_native_event'] == 342
assert old['register_sha256'] == overlay['baseline_register_sha256']
for key in ['workbook', 'workbook_validation', 'workbook_handoff']:
    assert sha(inputs[key]['path']) == inputs[key]['sha256'], key
validation = read(inputs['workbook_validation']['path'])
assert validation['status'] == 'PASS_V4_SIX_FILE_NATIVE_AVAILABILITY_WORKBOOK'
assert validation['source_workbook_sha256'] == old['current_comprehensive_workbook']['sha256']
assert validation['overlay_sha256'] == sha(H / 'availability-overlay.json')
assert validation['source_or_specification_cell_changes'] == 0
assert not validation['existing_hyperlink_changes'] and not validation['errors']
workbook = Path(inputs['workbook']['path'])
assert sha(workbook) == validation['output_workbook_sha256']
assert workbook.name == 'Boldstone_Wall_Sculptures_Unified_2026-10-25_v4.xlsx'
handoff = Path(inputs['workbook_handoff']['path'])
app_qa_path = H / 'app-independent-validation.json'
app_qa = read(app_qa_path)
assert app_qa['status'] == 'PASS_INDEPENDENT_ALL188_APP_FIELDS_AND_EXPORT'
assert app_qa['products'] == 188 and app_qa['specification_fields'] == 1316
assert app_qa['event_cutoff'] == 1830 and app_qa['new_physical_measurements'] == 0
for name, digest in app_qa['all_application_code_hashes'].items():
    assert sha(name) == digest, name
app_handoff = APP / 'reviews/specification-completion-20261025/sealed-handoff.json'
assert sha(app_handoff) == app_qa['handoff_sha256']
q = read(app_handoff)
for row in q['artifacts'] + q['application_code']:
    assert sha(row['path']) == row['sha256'], row['path']
readers = read(H / 'reader-verification.json')
assert readers['status'] == 'PASS_NATIVE_AVAILABILITY_READERS'
assert readers['deleted_native_ids'] == 6 and readers['effective_baseline_files'] == 6354
for name, digest in readers['outputs'].items():
    assert sha(name) == digest, name
with urllib.request.urlopen('http://127.0.0.1:8767/api/health', timeout=10) as response:
    health = json.load(response)
assert health['version'] == '2.2' and health['products'] == 188
protected = {}
for key in ['register', 'workbook']:
    f = B / old[key]
    assert sha(f) == old[key + '_sha256']
    protected[str(f)] = sha(f)
for key in ['current_asset_reference_map', 'current_native_reference_map']:
    f = B / old[key]['path']
    assert sha(f) == old[key]['sha256']
    protected[str(f)] = sha(f)
f = B / old['preferred_review_workbook']
assert sha(f) == old['current_comprehensive_workbook']['sha256']
protected[str(f)] = sha(f)
protected[overlay['gallery_database']] = overlay['gallery_database_sha256']
controls = [B / x for x in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
for f in controls:
    assert read(f)['current_master_catalogue'] == old, str(f)
now = datetime.now(timezone.utc).isoformat()
availability = {'status': 'SIX_OWNER_CONFIRMED_NATIVE_DELETIONS_RECONCILED',
    'path': rel(H / 'availability-overlay.json'), 'sha256': sha(H / 'availability-overlay.json'),
    'review': rel(OUT / 'index.html'), 'all_options_review': rel(OUT / 'all-options.html'),
    'current_native_files': rel(OUT / 'Current_Native_Files_6354.csv'),
    'deleted_native_history': rel(OUT / 'Confirmed_Native_Deletions_6.csv'),
    'review_event_cutoff': 347, 'last_confirmed_native_event': 342, 'counts': overlay['counts'],
    'baseline_register_sha256': old['register_sha256'],
    'historical_ids_records_and_source_photo_proof_retained': True,
    'replacement_primary_selections': 0, 'physical_verifications': 0, 'scope': overlay['scope'],
    'preceding_five_id_scope_overlay': old['current_native_availability']}
p = copy.deepcopy(old)
p.update(recorded_utc=now, status='CURRENT_MASTER188_WITH_SIX_FILE_AVAILABILITY_AND_SAVED_APP_REVIEW',
    current_native_availability=availability,
    current_effective_native_inventory={**overlay['counts'], 'scope': overlay['scope']},
    publication_receipt=rel(H / 'publication-receipt.json'))
for key in ['current_asset_reference_map', 'current_native_reference_map']:
    p[key]['native_availability_overlay'] = {'path': availability['path'], 'sha256': availability['sha256']}
    p[key]['underlying_map_is_a_retained_snapshot'] = True
p['current_published_gallery_projection'].update(
    status='RETAINED_SOURCE_GALLERY_WITH_VERIFIED_NATIVE_AVAILABILITY_OVERLAY',
    native_availability_overlay={'path': availability['path'], 'sha256': availability['sha256']},
    native_file_count_scope='Gallery counts retain the original snapshot. The bounded availability overlay subtracts six verified native deletions. Saved app decisions remain a separate overlay.')
p['current_complete_gallery_mapping']['native_availability_overlay'] = copy.deepcopy(availability)
oldbook = copy.deepcopy(old['current_comprehensive_workbook'])
book = copy.deepcopy(oldbook)
book.update(status='CONSOLIDATED_SOURCE_WORKBOOK_WITH_SIX_FILE_NATIVE_AVAILABILITY',
    path=rel(workbook), sha256=sha(workbook), sheets=validation['output_sheet_count'],
    native_hyperlinks=validation['output_hyperlinks'], source_seal=rel(handoff), source_seal_sha256=sha(handoff),
    native_availability_overlay={'path': availability['path'], 'sha256': availability['sha256']},
    native_availability_review_event_cutoff=347, last_confirmed_native_event=342,
    preceding_workbook=oldbook, current_native_availability_source_scope=overlay['scope'],
    saved_app_field_review_imports=0)
book['counts'].update(current_wall_files=6354, confirmed_deleted_files_retained_as_history=6, source_snapshot_wall_files=6360)
p['current_comprehensive_workbook'] = book
p['preferred_review_workbook'] = rel(workbook)
links = p['current_image_review_links']
links.update(all_links=availability['all_options_review'], current_native_availability=availability['review'],
    all_individual_option_galleries=availability['all_options_review'], complete_current_wall_images=availability['current_native_files'],
    all_catalogue_and_source_inventories_workbook=str(workbook), single_wall_sculptures_sheet_workbook=str(workbook),
    current_saved_app_specification_review=str(APP / 'reviews/specification-completion-20261025/all-sculptures.html'))
p['current_guided_image_review'].update(terminal_review_command=rel(H / 'walkthrough.py'),
    terminal_review_command_sha256=sha(H / 'walkthrough.py'),
    terminal_runtime_verification=rel(H / 'terminal-verification.json'),
    terminal_runtime_verification_sha256=sha(H / 'terminal-verification.json'),
    native_availability_overlay=copy.deepcopy(availability))
review = {'status': 'ALL188_APP_SPECIFICATION_REVIEWS_SAVED_SEPARATELY',
    'recorded_utc': q['sealed_utc'], 'event_cutoff': 1830, 'products': 188,
    'specification_fields': 1316, 'punctuation_only_names': 167,
    'report': str(APP / 'reviews/specification-completion-20261025/all-sculptures.html'),
    'report_sha256': readers['app_review_report_sha256'],
    'values_readback': str(APP / 'reviews/specification-completion-20261025/all-188-readback.json'),
    'values_readback_sha256': sha(APP / 'reviews/specification-completion-20261025/all-188-readback.json'),
    'handoff': str(app_handoff), 'handoff_sha256': sha(app_handoff),
    'independent_verification': rel(app_qa_path), 'independent_verification_sha256': sha(app_qa_path),
    'export': q['export'], 'presentation': q['listing_presentation'],
    'certainty_source_qualifications_and_evidence_retained_separately': True,
    'new_physical_measurements': 0, 'canonical_field_imports': 0, 'platform_writes': 0,
    'listing_readiness_not_established_by_populated_fields': True}
p['current_saved_specification_review'] = review
app = p['current_review_application']
app['preceding_validation_reference'] = {k: app[k] for k in ['version', 'last_verified_utc', 'verification', 'verification_sha256', 'ui_revision'] if k in app}
app.update(status='LOCAL_REVIEW_APP_V22_ALL188_SAVED_FIELDS_VERIFIED', last_verified_utc=now,
    version='2.2', ui_revision='clean-listing-values-separate-evidence-20261025',
    verification=str(app_qa_path), verification_sha256=sha(app_qa_path), contract_sha256=sha(APP / 'README.md'),
    verification_scope='All188 saved field values and export; prior review history, native jobs and sources preserved.',
    latest_saved_specification_review=copy.deepcopy(review),
    source_coverage_is_a_retained_baseline_snapshot=True)
app['release_validation']['unit_tests'] = q['backend_tests_passed']
app['reviewed_native_file_deletion']['known_reconciled_receipt_scope'] = {
    'native_files': 6, 'review_event_cutoff': 347, 'last_confirmed_native_event': 342,
    'availability_overlay': availability['path'],
    'scope': 'Six exact app deletion receipts only; no additional native mutation by the catalogue publisher.'}
p['latest_master_metadata_change'] = {'status': 'V4_SIX_FILE_AVAILABILITY_AND_APP_REVIEW_REFERENCES',
    'preceding_receipt': old['publication_receipt'], 'source_register_core_workbook_maps_and_gallery_bytes_unchanged': True,
    'general_review_choice_imports': 0, 'publisher_native_mutations': 0}
allowed = {'recorded_utc', 'status', 'current_native_availability', 'current_effective_native_inventory', 'publication_receipt',
    'current_asset_reference_map', 'current_native_reference_map', 'current_published_gallery_projection',
    'current_complete_gallery_mapping', 'current_comprehensive_workbook', 'preferred_review_workbook',
    'current_image_review_links', 'current_guided_image_review', 'current_review_application',
    'latest_master_metadata_change', 'current_saved_specification_review'}
assert all(p[k] == old[k] for k in old if k not in allowed)
assert p['all_actual_specifications_complete'] is False
updates = {}
for f in controls:
    value = read(f)
    value.update(updated_utc=now, current_master_catalogue=copy.deepcopy(p))
    for key in allowed - {'recorded_utc', 'status', 'publication_receipt'}:
        if key in p:
            value[key] = copy.deepcopy(p[key])
    updates[f] = value

def write(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.six-file-publication-tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)

if not a.apply:
    print(json.dumps({'status': 'READY_FOR_ATOMIC_LOCAL_PUBLICATION', 'workbook': str(workbook), 'app_fields': 1316, 'confirmed_deletions': 6, 'source_bytes_unchanged': True}))
    raise SystemExit(0)
snap = H / 'publication-inputs'
snap.mkdir(exist_ok=True)
snapshots = {}
for f in [pointer, *controls]:
    dest = snap / str(f.relative_to(B)).replace('/', '__')
    assert not dest.exists()
    shutil.copy2(f, dest)
    snapshots[f] = dest
try:
    for f, snapshot in snapshots.items():
        assert sha(f) == sha(snapshot)
    for f, digest in protected.items():
        assert sha(f) == digest, f
    for f, digest in app_qa['all_application_code_hashes'].items():
        assert sha(f) == digest, f
    for f, value in updates.items():
        write(f, value)
    write(pointer, p)
    assert read(pointer) == p
    for f in controls:
        assert read(f)['current_master_catalogue'] == p
    assert all(sha(f) == digest for f, digest in protected.items())
    receipt = {'status': 'PASS_V4_SIX_FILE_AVAILABILITY_AND_APP_REVIEW_REFERENCES_PUBLISHED',
        'recorded_utc': now, 'pointer_sha256': sha(pointer), 'preceding_pointer_sha256': sha(snapshots[pointer]),
        'overlay_sha256': availability['sha256'], 'review_event_cutoff': 347, 'last_confirmed_native_event': 342,
        'app_review_event_cutoff_separate': 1830, 'source_register_sha256': p['register_sha256'],
        'core_workbook_sha256': p['workbook_sha256'], 'preferred_workbook_path': str(workbook),
        'preferred_workbook_sha256': sha(workbook), 'deleted_native_files': 6, 'affected_master_examples': 1,
        'active_options': 188, 'saved_app_specification_fields': 1316,
        'replacement_primaries_selected_by_publication': 0, 'general_review_choices_imported': 0,
        'publisher_native_mutations': 0, 'publisher_active_review_db_writes': 0,
        'protected_source_files_unchanged': protected, 'controls_sha256': {str(f): sha(f) for f in controls},
        'app_verification_sha256': sha(app_qa_path), 'workbook_validation_sha256': sha(inputs['workbook_validation']['path'])}
    write(H / 'publication-receipt.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ['protected_source_files_unchanged', 'controls_sha256']}, ensure_ascii=False, indent=2))
except BaseException:
    for f, snapshot in snapshots.items():
        shutil.copy2(snapshot, f)
    raise
