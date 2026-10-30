"""Atomically register the independently checked app-only fix."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import json
import os
import shutil

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(B))
arg = argparse.ArgumentParser()
arg.add_argument('--apply', action='store_true')
a = arg.parse_args()
pointer = B / 'current-master.json'
qa = read(H / 'independent-verification.json')
assert qa['status'] == 'PASS_INDEPENDENT_IMAGE_PURPOSE_ROUND_TRIP_FIX'
assert sha(pointer) == qa['baseline_pointer_sha256'] == 'd69cf087314d929a22174f189dcb52d04880aa23b7f73106fb9c19882875edd4'
assert not (H / 'publication-receipt.json').exists()
assert sha(qa['handoff_path']) == qa['handoff_sha256']
for f, digest in {**qa['all_application_code_hashes'], **qa['protected_source_hashes'], **qa['evidence']}.items():
    assert sha(f) == digest, f
old = read(pointer)
controls = [B / f for f in ['components/reviews/specification_review_progress.json', 'components/checkpoint.json', 'checkpoint.json']]
for f in controls:
    assert read(f)['current_master_catalogue'] == old
p = copy.deepcopy(old)
now = datetime.now(timezone.utc).isoformat()
p['recorded_utc'] = now
app = p['current_review_application']
app['preceding_validation_reference'] = {k: app[k] for k in ['version', 'verification', 'verification_sha256', 'last_verified_utc', 'ui_revision'] if k in app}
app.update(version='2.3.2', status='LOCAL_REVIEW_APP_IMAGE_PURPOSE_FIX_VERIFIED', last_verified_utc=now,
    verification=str(H / 'independent-verification.json'), verification_sha256=sha(H / 'independent-verification.json'),
    contract_sha256=sha(B.parent / 'catalogue-review/README.md'), ui_revision='independent-purpose-toggles-repeat-save-fixed',
    verification_scope='Independent isolated purpose-toggle audit, native-provenance recomputation and preserved production review history.',
    image_purpose_fix={'listing_on_off_repeatedly': True, 'listing_and_advertising_independent': True,
        'other_image_uses_preserved': True, 'server_recomputes_native_reviewed_content_hash': True,
        'strict_unknown_editable_fields_and_version_checks_retained': True,
        'isolated_browser_saves_verified': 5, 'qa_database_promoted': False,
        'owning_thread_handoff': qa['handoff_path'], 'owning_thread_handoff_sha256': qa['handoff_sha256']},
    saved_review_snapshot={'event_cutoff': qa['production_review_event_cutoff'],
        'review_rows': qa['production_review_rows_at_snapshot'], 'app_review_writes_by_catalogue_publisher': 0,
        'owner_may_continue_reviewing': True},
    newer_native_activity_pending_inventory_reconciliation=qa['later_owner_native_activity_not_imported_into_inventory'])
app['release_validation'].update(unit_tests=86, isolated_image_purpose_browser_saves=5)
p['latest_master_metadata_change'] = {'status': 'APP232_IMAGE_PURPOSE_FIX_REFERENCE_ONLY',
    'preceding_receipt': old['publication_receipt'], 'source_register_gallery_maps_and_workbook_bytes_unchanged': True,
    'native_inventory_cutoff_retained': True, 'general_review_choice_imports': 0,
    'publisher_native_mutations': 0, 'publisher_active_review_db_writes': 0}
p['publication_receipt'] = rel(H / 'publication-receipt.json')
allowed = {'recorded_utc', 'current_review_application', 'latest_master_metadata_change', 'publication_receipt'}
assert all(p[k] == old[k] for k in old if k not in allowed)
updates = {}
for f in controls:
    value = read(f)
    value.update(updated_utc=now, current_master_catalogue=copy.deepcopy(p),
        current_review_application=copy.deepcopy(app), latest_master_metadata_change=copy.deepcopy(p['latest_master_metadata_change']))
    updates[f] = value
def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.app232-publication-tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)
if not a.apply:
    print(json.dumps({'status': 'READY_APP232_METADATA_PUBLICATION', 'source_and_native_inventory_changes': 0}))
    raise SystemExit(0)
saved = H / 'publication-inputs'
saved.mkdir(exist_ok=True)
snapshots = {}
for f in [pointer, *controls]:
    target = saved / str(f.relative_to(B)).replace('/', '__')
    assert not target.exists()
    shutil.copy2(f, target)
    snapshots[f] = target
try:
    for f, source in snapshots.items():
        assert sha(f) == sha(source)
    for f, digest in qa['all_application_code_hashes'].items():
        assert sha(f) == digest
    for f, value in updates.items():
        write(f, value)
    write(pointer, p)
    assert read(pointer) == p and all(read(f)['current_master_catalogue'] == p for f in controls)
    assert all(sha(f) == s for f, s in qa['protected_source_hashes'].items())
    receipt = {'status': 'PASS_APP232_REFERENCE_PUBLISHED', 'recorded_utc': now,
        'pointer_sha256': sha(pointer), 'preceding_pointer_sha256': sha(snapshots[pointer]),
        'app_version': '2.3.2', 'review_snapshot_event_cutoff': qa['production_review_event_cutoff'],
        'review_snapshot_rows': qa['production_review_rows_at_snapshot'], 'qa_checks': qa['checks_passed'],
        'automated_tests': 86, 'isolated_browser_saves': 5, 'qa_database_promoted': False,
        'source_identity_specification_native_inventory_or_workbook_changes': 0,
        'app_review_db_writes': 0, 'native_calls': 0,
        'verification_sha256': sha(H / 'independent-verification.json'),
        'control_sha256': {str(f): sha(f) for f in controls}}
    write(H / 'publication-receipt.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'control_sha256'}, indent=2))
except BaseException:
    for f, source in snapshots.items():
        shutil.copy2(source, f)
    raise
