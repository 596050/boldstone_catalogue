"""Read-only v2.9.1 independent verification, without production mutations."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import hashlib
import json
import re
import sqlite3
import time
import urllib.request

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
ROOT = BASE.parent
APP = ROOT / 'catalogue-review'
HANDOFF = APP / 'reviews/filename-progress-20261026'
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(message)


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767' + path, timeout=30) as response:
        return json.load(response)


def snapshot(path):
    db = sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN')
        return {table: [dict(row) for row in db.execute('SELECT * FROM "' + table + '" ORDER BY rowid')]
                for table in ['reviews', 'events', 'operations', 'background_jobs', 'deletion_jobs', 'deletion_batches']}
    finally:
        db.close()


def unpack(row):
    row = dict(row)
    for name in ['data', 'original']:
        if isinstance(row.get(name), str):
            row[name] = json.loads(row[name])
    return row


def key(row):
    return row['kind'], row['product_id'], row['item_id']


pointer_path = BASE / 'current-master.json'
pointer_sha = sha(pointer_path)
pointer = read(pointer_path)
handoff_path = HANDOFF / 'HANDOFF.json'
check(sha(handoff_path) == 'f5421da1c401187e9c4cbeaef984616cd73c0501ee874355ef670d0f833f3c3f', 'Exact immutable final handoff')
handoff = read(handoff_path)
check(handoff['version'] == '2.9.1' and handoff['status'] == 'DEPLOYED_AND_VERIFIED', 'Final deployed release')
source_hashes = read(HERE / 'tested-source-before.json')
for path, digest in source_hashes.items():
    check(Path(path).is_relative_to(APP), 'App-scoped test source')
    check(sha(path) == digest, 'Tested source remained unchanged: ' + path)
for path, digest in handoff['changed_files'].items():
    deployed = APP / path
    check(source_hashes.get(str(deployed.resolve())) == digest, 'Handoff and independently tested source agree: ' + path)

python_log = (HERE / 'python-tests.txt').read_text()
javascript_log = (HERE / 'javascript-tests.txt').read_text()
sort_log = (HERE / 'sort-tests.txt').read_text()
check(re.search(r'Ran 200 tests in .*\n\nOK\s*$', python_log) is not None, '200 independent Python tests passed')
check('ℹ tests 25' in javascript_log and 'ℹ pass 25' in javascript_log and 'ℹ fail 0' in javascript_log, '25 independent JavaScript checks passed')
check('9 multi-sort behaviour checks passed' in sort_log, '9 independent sort checks passed')
check(handoff['validation']['python_tests'] == 200 and handoff['validation']['javascript_tests'] == 25, 'Exact test result agreement')
check(handoff['validation']['production_native_actions_for_progress'] == 0, 'Progress feature uses no production native actions')

protected = {str(BASE / pointer['register']): pointer['register_sha256'],
             str(BASE / pointer['workbook']): pointer['workbook_sha256'],
             str(BASE / pointer['preferred_review_workbook']): pointer['current_comprehensive_workbook']['sha256']}
for path, digest in protected.items():
    check(sha(path) == digest, 'Protected canonical bytes')

before = snapshot(HANDOFF / 'pre-deploy.sqlite3')
live = snapshot(RUNTIME / 'reviews.sqlite3')
check(len(before['reviews']) == 2440 and before['events'][-1]['id'] == 4945, 'Exact predeployment review backup')
check([row for row in live['events'] if row['id'] <= 4945] == before['events'], 'Existing audit history preserved exactly')
state = {key(row): unpack(row) for row in before['reviews']}
for event in [row for row in live['events'] if row['id'] > 4945]:
    prior = unpack(json.loads(event['before_json'])) if event['before_json'] else None
    after = unpack(json.loads(event['after_json']))
    if prior and key(prior) in state:
        check(prior == state[key(prior)], 'Later audited change follows preserved prior review')
    state[key(after)] = after
check(state == {key(row): unpack(row) for row in live['reviews']}, 'All current review values, originals and versions follow preserved history')
for table in ['operations', 'background_jobs', 'deletion_jobs', 'deletion_batches']:
    old = {row['id']: row for row in before[table]}
    current = {row['id']: row for row in live[table]}
    check(set(old) <= set(current), 'Existing ' + table + ' rows retained')
    for ident, row in old.items():
        check(current[ident] == row, 'Preserved queued/deletion record ' + table + '/' + ident)

health = get('/api/health')
bootstrap = get('/api/bootstrap')
jobs = get('/api/jobs')
register = read(BASE / pointer['register'])
check(health['version'] == '2.9.1' and health['products'] == 187, 'Live 2.9.1 with187 active options')
check(bootstrap['source']['register_sha256'] == pointer['register_sha256'], 'Live source register unchanged')
check({row['id'] for row in bootstrap['products']} == set(register['active_option_ids']), 'Exact187 active product IDs')
gallery = bootstrap['source']['gallery_database']
protected[gallery] = bootstrap['source']['gallery_sha256']
check(sha(gallery) == protected[gallery], 'Saved source gallery preserved')
check(jobs['reservation'].get('active') is True, 'Native filename writer still reserved')
check(read(RUNTIME / 'native-writer-reservation.json')['root'] == '/Users/tprice/BoldstoneMigration/path-renaming-20261026', 'Exact owning native filename task')
check(snapshot(RUNTIME / 'reviews.sqlite3') == live, 'Stable live database frame for activity comparison')

# Reconstruct original-file reservations independently of the app helper.
deletion_jobs = {row['id']: {**row, 'payload': json.loads(row['payload'])} for row in live['deletion_jobs']}
batches = {row['id']: json.loads(row['payload']) for row in live['deletion_batches']}
targets, keepers = {}, {}


def reserve(job, parent_id, status):
    fid, payload = job['file_id'], job['payload']
    targets[fid] = {'file_id': fid, 'job_id': parent_id, 'operation_id': job['id'],
                    'state': status, 'kind': 'delete', 'name': payload['file']['name']}
    keeper = payload.get('keeper_binding')
    if keeper and status not in ['deleted', 'already_absent']:
        keepers[keeper['id']] = {'file_id': keeper['id'], 'job_id': parent_id,
                                 'state': 'keeper_reserved', 'kind': 'keeper',
                                 'name': (payload.get('keeper') or {}).get('name', keeper['id'])}


for parent in live['background_jobs']:
    if parent['kind'] not in ['delete', 'delete_batch'] or parent['state'] not in ['queued', 'running', 'uncertain']:
        continue
    body = json.loads(parent['payload'])['body']
    ids = [body['operation_id']] if parent['kind'] == 'delete' else batches[body['batch_id']]['operation_ids']
    for ident in ids:
        job = deletion_jobs[ident]
        if job['state'] == 'prepared' and parent['state'] in ['queued', 'running']:
            reserve(job, parent['id'], parent['state'])
        elif job['state'] in ['executing', 'uncertain']:
            reserve(job, parent['id'], job['state'])
for job in deletion_jobs.values():
    if job['state'] in ['executing', 'uncertain', 'deleted', 'already_absent']:
        reserve(job, targets.get(job['file_id'], {}).get('job_id'), job['state'])
expected = {**keepers, **targets}
for fid, item in expected.items():
    check(jobs['deletion_activity'].get(fid) == item, 'Per-original activity agrees: ' + fid)
for alias, item in jobs['deletion_activity'].items():
    check(item['file_id'] in expected and item == expected[item['file_id']], 'Alias activity points only to an expected original')
check(jobs['active_count'] == sum(row['state'] in ['queued', 'running'] for row in live['background_jobs']), 'Background active count')


# Product routes did not change: bind the prior 187 endpoint readbacks rather
# than repeating that whole-library work for a progress-only release.
prior_path = HERE.parent / 'deletion-activity-app-reference-2026-10-26/independent-verification.json'
prior = read(prior_path)
check(prior['status'] == 'PASS_READ_ONLY_V2_9_0_DELETION_ACTIVITY_AND_SAVED_STATE', 'Prior independent product readback')
pages = prior['independent_live_product_endpoint_readbacks']
check({row['product_id'] for row in pages} == set(register['active_option_ids']), 'Prior exact187 API IDs')
old_server = HANDOFF / 'before/server.py'
check(sha(old_server) == prior['independently_tested_source_files'][str(APP / 'server.py')], 'Exact old server snapshot')
check(old_server.read_text().replace('2.9.0', '2.9.1') == (APP / 'server.py').read_text(), 'Product routes unchanged; server version change only')
for path, digest in prior['independently_tested_source_files'].items():
    path = Path(path)
    if path.parent == APP and path.suffix == '.py' and path.name not in ['background_jobs.py', 'server.py']:
        check(sha(path) == digest, 'Product/catalogue helper unchanged: ' + path.name)

progress = jobs['filename_job']
check(progress and progress['state'] == 'running', 'Live filename progress available')
root = Path(jobs['reservation']['root'])
if progress['pass_name'] == 'Original pass':
    current_pass = root
else:
    number = int(progress['pass_name'].split()[-1])
    choices = [p for p in root.glob('followup-*') if p.is_dir() and int(p.name.split('-')[-1]) == number]
    check(len(choices) == 1, 'Exact follow-up pass')
    current_pass = choices[0]
manifest_path = current_pass / 'manifest.json'
manifest = read(manifest_path)
batch = current_pass / 'bulk-operations' / str(progress['batch_number']).zfill(3)
intent = read(batch / 'intent.json')
check(intent['manifest_sha256'] == sha(manifest_path), 'Batch intent binds current manifest')
inventory_options = []
for name, receipt_name, hash_key in [('before.json', 'intent.json', 'before_sha256'),
                                     ('after.json', 'verified.json', 'after_sha256')]:
    path = batch / name
    if path.is_file() and (batch / receipt_name).is_file():
        value = read(path)
        if value['recorded_utc'] == progress['checked_at']:
            proof = read(batch / receipt_name)
            check(sha(path) == proof[hash_key], 'Progress inventory matches its journal receipt')
            inventory_options.append((path, value))
check(len(inventory_options) == 1, 'Exact progress inventory timestamp')
inventory_path, inventory = inventory_options[0]
check(all(inventory[scope]['pagination_exhausted'] for scope in ['wall', 'workshop']), 'Both native inventory scopes exhausted')
rows = inventory['wall']['entries'] + inventory['workshop']['entries']
by_id = {row['id']: row for row in rows}
by_parent = {}
for row in rows:
    if row['kind'] == 'file':
        by_parent.setdefault(row['parent_id'], {})[row['id']] = row
correct = total = deferred_folders = deferred_files = 0
immutable = ['id', 'parent_id', 'size', 'content_hash', 'client_modified',
             'has_explicit_shared_members', 'sharing_info_present', 'read_only',
             'parent_shared_folder_id', 'file_lock_present']
for group in manifest['groups']:
    parent, files = group['parent'], group['files']
    total += len(files)
    actual_folder = by_id.get(parent['id'])
    actual = by_parent.get(parent['id'], {})
    stable = bool(actual_folder and actual_folder['path'].casefold() == parent['path'].casefold()
                  and actual_folder['name'] == parent['name'] and set(actual) == {r['id'] for r in files})
    if stable:
        for old in files:
            new = actual[old['id']]
            allowed = {str(value).casefold() for value in [old['path'], old['new_path'], old.get('temporary_path')] if value}
            if any(old.get(key) != new.get(key) for key in immutable) or new['path'].casefold() not in allowed:
                stable = False
                break
    if not stable:
        deferred_folders += 1
        deferred_files += len(files)
        continue
    correct += sum(actual[row['id']]['name'] == row['new_name'] and
                   actual[row['id']]['path'].casefold() == row['new_path'].casefold() for row in files)
check(total == manifest['counts']['files'] == progress['total'], 'Exact original/follow-up file denominator')
check(correct == progress['correct'], 'Progress counts observed checked paths, not submitted moves')
check(deferred_folders == progress['deferred_folders'] and deferred_files == progress['deferred_files'], 'Changed-folder holds accurately retained')
check(progress['percent'] == round(100 * correct / total, 1), 'Exact displayed progress percentage')
check(progress['batch_files'] == len(intent['moves']), 'Exact pending batch size')
check(progress['planned_renames'] == manifest['counts']['renames'], 'Exact planned rename count')
submission_path = batch / 'submission.json'
submission = read(submission_path)
check(bool(submission.get('async_job_id')), 'Existing async batch submission')
check(progress['batch_started_at'] == submission['at'], 'Original batch start time')
started = datetime.fromisoformat(progress['batch_started_at'].replace('Z', '+00:00')).timestamp()
check(abs(progress['batch_elapsed_seconds'] - int(time.time() - started)) < 15, 'Elapsed time agrees with original submission')
progress_journals = {str(path): sha(path) for path in [manifest_path, batch / 'intent.json', inventory_path, submission_path]}

check(sha(pointer_path) == pointer_sha, 'Canonical publication remains held')
for path, digest in source_hashes.items():
    check(sha(path) == digest, 'No source changes during final readback')

report = {
    'status': 'PASS_READ_ONLY_V2_9_1_FILENAME_PROGRESS_AND_SAVED_STATE',
    'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
    'application_version': '2.9.1', 'handoff': str(handoff_path), 'handoff_sha256': sha(handoff_path),
    'independently_tested_source_files': source_hashes, 'protected_source_hashes': protected,
    'independent_python_tests_passed': 200, 'independent_javascript_checks_passed': 25,
    'independent_sort_checks_passed': 9, 'active_options': 187,
    'prior_independent_live_product_endpoint_readbacks': pages,
    'prior_product_api_evidence': {'path': str(prior_path), 'sha256': sha(prior_path), 'unchanged_route_and_product_helpers_verified': True},
    'filename_progress': progress, 'progress_journal_bindings': progress_journals,
    'baseline_pointer_sha256': pointer_sha,
    'predeployment_review_rows': 2440, 'predeployment_event_cutoff': 4945,
    'live_review_rows': len(live['reviews']), 'live_event_cutoff': live['events'][-1]['id'],
    'historical_reviews_original_values_versions_and_events_preserved': True,
    'existing_queued_and_deletion_rows_preserved': {name: len(before[name]) for name in ['operations', 'background_jobs', 'deletion_jobs', 'deletion_batches']},
    'original_file_activity_entries_verified': len(expected),
    'alias_expanded_activity_entries_verified': len(jobs['deletion_activity']),
    'activity_states': dict(Counter(item['state'] for item in jobs['deletion_activity'].values())),
    'native_writer_reservation': jobs['reservation'],
    'publication_remains_held_for_final_native_filename_overlay': True,
    'root_production_mutating_http_requests_or_native_calls': 0,
    'root_source_app_review_database_or_shared_publication_writes': 0,
}
(HERE / 'independent-verification.json').write_text(json.dumps(report, indent=2) + '\n')
(HERE / 'PUBLICATION_READY_QUEUED.json').write_text(json.dumps({
    'status': 'VERIFIED_APP_V2_9_1_QUEUED_FINAL_PATH_PUBLICATION_HELD',
    'verification': str(HERE / 'independent-verification.json'),
    'verification_sha256': sha(HERE / 'independent-verification.json'),
    'baseline_pointer_sha256': pointer_sha, 'supersedes_queued_app_reference': '2.9.0',
    'requires_final_native_filename_overlay': True,
    'root_source_app_review_and_native_writes': 0,
}, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items()
                  if k not in ['independently_tested_source_files', 'protected_source_hashes',
                               'prior_independent_live_product_endpoint_readbacks']}, indent=2))
