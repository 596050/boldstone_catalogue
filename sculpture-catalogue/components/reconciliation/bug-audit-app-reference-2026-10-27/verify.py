"""Read-only v2.9.2 independent verification, without production mutations."""
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
HANDOFF = APP / 'reviews/bug-audit-20261027'
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
check(sha(handoff_path) == 'f3eeda9f6a0d6880f93ad4f6b6db45a21222fb41c9003aff665d275105a149b4', 'Exact immutable final handoff')
handoff = read(handoff_path)
check(handoff['version'] == '2.9.2' and handoff['status'] == 'DEPLOYED_AND_VERIFIED', 'Final deployed release')
source_hashes = read(HERE / 'tested-source-before.json')
for path, digest in source_hashes.items():
    check(Path(path).is_relative_to(APP) or Path(path).parent == ROOT / 'image-processing', 'App or scoped rename source')
    check(sha(path) == digest, 'Tested source remained unchanged: ' + path)
for path, digest in handoff['changed_files'].items():
    deployed = ROOT / path
    check(source_hashes.get(str(deployed.resolve())) == digest, 'Handoff and independently tested source agree: ' + path)

python_log = (HERE / 'python-tests.txt').read_text()
javascript_log = (HERE / 'javascript-tests.txt').read_text()
sort_log = (HERE / 'sort-tests.txt').read_text()
check(re.search(r'Ran 212 tests in .*\n\nOK\s*$', python_log) is not None, '212 independent Python tests passed')
check('ℹ tests 28' in javascript_log and 'ℹ pass 28' in javascript_log and 'ℹ fail 0' in javascript_log, '28 independent JavaScript checks passed')
check('9 multi-sort behaviour checks passed' in sort_log, '9 independent sort checks passed')
check(handoff['validation']['python_tests'] == 212 and handoff['validation']['javascript_tests'] == 28, 'Exact test result agreement')
check(handoff['validation']['production_native_deletions_for_tests'] == 0 and handoff['validation']['repeated_rename_requests'] == 0, 'No destructive test calls or repeated renames')

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
# The old queued deletion was rejected safely after filenames changed. Preserve
# that legitimate transition while checking all other retained operation rows.
allowed_job = handoff['outstanding_user_job']
old_background = {r['id']: r for r in before['background_jobs']}
batch_id = json.loads(old_background[allowed_job['id']]['payload'])['body']['batch_id']
operational_changes = []
for table in ['operations', 'background_jobs', 'deletion_jobs', 'deletion_batches']:
    old = {row['id']: row for row in before[table]}
    current = {row['id']: row for row in live[table]}
    check(set(old) == set(current), 'Exact retained operational IDs: ' + table)
    for ident, row in old.items():
        after = current[ident]
        if after == row:
            check(True, 'Preserved operation row')
            continue
        changed = {k for k in row if row[k] != after[k]}
        result = json.loads(after['result'])
        if table == 'background_jobs':
            check(ident == allowed_job['id'] and row['state'] == 'queued' and after['state'] == 'needs_review', 'Only the stale queued job stopped for review')
            check(changed <= {'state', 'updated_at', 'result'}, 'Queued-job immutable payload retained')
            entries = result['results']
            check(len(entries) == 1 and entries[0]['file_id'] == allowed_job['file_id'] and entries[0]['delete_attempted'] is False, 'Queued job confirms no deletion attempted')
        elif table == 'deletion_jobs':
            check(row['file_id'] == allowed_job['file_id'] and row['state'] == 'prepared' and after['state'] == 'rejected', 'Exact old deletion review rejected')
            check(changed <= {'state', 'result'} and result['delete_attempted'] is False, 'Native guard prevented deletion')
        elif table == 'deletion_batches':
            check(ident == batch_id and row['state'] == 'prepared' and after['state'] == 'partial', 'Exact stale batch state recorded')
            check(changed <= {'state', 'result'}, 'Stale-batch immutable payload retained')
        else:
            raise AssertionError('Unexpected operation mutation')
        operational_changes.append({'table': table, 'id': ident, 'before': row['state'], 'after': after['state'], 'changed_fields': sorted(changed)})
check(len(operational_changes) == 3, 'Three recorded rows reflect the one rejected native request')

health = get('/api/health')
bootstrap = get('/api/bootstrap')
jobs = get('/api/jobs')
register = read(BASE / pointer['register'])
check(health['version'] == '2.9.2' and health['products'] == 187, 'Live 2.9.2 with187 active options')
check(bootstrap['source']['register_sha256'] == pointer['register_sha256'], 'Live source register unchanged')
check({row['id'] for row in bootstrap['products']} == set(register['active_option_ids']), 'Exact187 active product IDs')
gallery = bootstrap['source']['gallery_database']
protected[gallery] = bootstrap['source']['gallery_sha256']
check(sha(gallery) == protected[gallery], 'Saved source gallery preserved')
check(not jobs['reservation'], 'Filename reservation released')
check(read(RUNTIME / 'native-writer-reservation.json')['active'] is False, 'Exact native reservation is inactive')
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
previous_progress = read(HERE.parent / 'filename-progress-app-reference-2026-10-26/independent-verification.json')
check(sha(old_server) == previous_progress['independently_tested_source_files'][str(APP / 'server.py')], 'Exact old server snapshot')
check(old_server.read_text().replace('2.9.1', '2.9.2') == (APP / 'server.py').read_text(), 'Product routes unchanged; server version change only')
for path, digest in prior['independently_tested_source_files'].items():
    path = Path(path)
    if path.parent == APP and path.suffix == '.py' and path.name not in ['background_jobs.py', 'server.py']:
        check(sha(path) == digest, 'Product/catalogue helper unchanged: ' + path.name)

progress = jobs['filename_job']
check(progress['state'] == 'completed' and progress['percent'] == 100, 'Live progress reports completed filename work')
completion_path = Path('/Users/tprice/BoldstoneMigration/path-renaming-20261026/completion.json')
completion = read(completion_path)
verified_path = Path(completion['verification'])
verified = read(verified_path)
check(completion['state'] == 'completed' and verified['status'] == 'PASS' and not verified['errors'], 'Completed native verification without errors')
check(sha(verified_path) == completion['verification_sha256'], 'Exact completion verification binding')
check(progress['correct'] == progress['total'] == verified['current_files'] == 5994, 'Completed count agrees with final native readback')
check(verified['preserved_scoped_shared_links'] == 996 and verified['external_user_deletions'] == 211, 'Exact sharing and user-deletion receipt counts')
progress_journals = {str(completion_path): sha(completion_path), str(verified_path): sha(verified_path)}
check(bootstrap['dropbox_sync']['state'] == 'ready' and bootstrap['dropbox_sync']['images'] == 5798, 'Current Wall image inventory ready')
check(sha(pointer_path) == pointer_sha, 'Canonical publication remains held')
for path, digest in source_hashes.items():
    check(sha(path) == digest, 'No source changes during final readback')

report = {
    'status': 'PASS_READ_ONLY_V2_9_2_FINALIZATION_AND_SAVED_STATE',
    'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
    'application_version': '2.9.2', 'handoff': str(handoff_path), 'handoff_sha256': sha(handoff_path),
    'independently_tested_source_files': source_hashes, 'protected_source_hashes': protected,
    'independent_python_tests_passed': 212, 'independent_javascript_checks_passed': 28,
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
    'completed_native_overlay_ready_for_master_reconciliation': True,
    'legitimate_postdeployment_rejected_job_transitions': operational_changes,
    'root_production_mutating_http_requests_or_native_calls': 0,
    'root_source_app_review_database_or_shared_publication_writes': 0,
}
(HERE / 'independent-verification.json').write_text(json.dumps(report, indent=2) + '\n')
(HERE / 'PUBLICATION_READY_QUEUED.json').write_text(json.dumps({
    'status': 'VERIFIED_APP_V2_9_2_READY_FOR_MASTER_RECONCILIATION',
    'verification': str(HERE / 'independent-verification.json'),
    'verification_sha256': sha(HERE / 'independent-verification.json'),
    'baseline_pointer_sha256': pointer_sha, 'supersedes_queued_app_reference': '2.9.1',
    'verified_native_filename_overlay_available': True,
    'root_source_app_review_and_native_writes': 0,
}, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items()
                  if k not in ['independently_tested_source_files', 'protected_source_hashes',
                               'prior_independent_live_product_endpoint_readbacks']}, indent=2))
