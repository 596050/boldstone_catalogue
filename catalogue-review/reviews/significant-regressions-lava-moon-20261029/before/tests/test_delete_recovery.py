"""Deletion recovery against fake Dropbox only; never touches live originals."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import json
import threading
import time
import unittest

import test_background_jobs as fixtures
import test_deletions as native_fixtures
from background_jobs import BackgroundJobs
from delete_dropbox import execute, failure_details, read_failure, verify_absent
from deletion_reviews import DeletionReviews
from deletions import NativeUnavailable
from projection import Projection
from store import Conflict
from test_deletions import TARGET, KEEPER


class NativeRecoveryTests(unittest.TestCase):
    setUp = native_fixtures.NativeDeletionTests.setUp

    def test_timeout_before_commit_retains_safe_error_and_does_not_retry(self):
        calls = []
        def timeout(fid, parent_rev):
            calls.append((fid, parent_rev))
            raise TimeoutError('secret token and private response body')
        self.client.files_delete_v2 = timeout
        result = execute(self.client, self.reviewed, self.binding, native_fixtures.ROOT)
        self.assertEqual(result['state'], 'uncertain')
        self.assertTrue(result['presence_verified'])
        self.assertEqual(result['delete_error']['error_code'], 'TimeoutError')
        self.assertNotIn('secret', json.dumps(result))
        self.assertEqual(calls, [(TARGET, 'a1')])

    def test_timeout_after_commit_is_verified_deleted_without_retry(self):
        self.client.after_delete_error = True
        result = execute(self.client, self.reviewed, self.binding, native_fixtures.ROOT)
        self.assertEqual(result['state'], 'deleted')
        self.assertTrue(result['verified_absent'])
        self.assertEqual(result['delete_error']['error_code'], 'TimeoutError')
        self.assertEqual(self.client.calls, [(TARGET, 'a1')])

    def test_sdk_request_id_and_long_cooldown_survive_without_response_body(self):
        RateLimitError = type('RateLimitError', (Exception,), {
            'request_id': 'safe-request-123', 'backoff': 275, 'status_code': 429})
        result = read_failure(RateLimitError('secret body'))
        self.assertEqual(result['retry_after'], 275)
        self.assertEqual(result['request_id'], 'safe-request-123')
        self.assertEqual(result['http_status'], 429)
        self.assertNotIn('secret', json.dumps(result))
        for value in ('bad', float('inf'), float('nan'), -5):
            error = RateLimitError(); error.backoff = value; error.request_id = 'unsafe secret\nheader'
            details = failure_details(error)
            self.assertEqual(details['retry_after'], 0)
            self.assertNotIn('request_id', details)

    def test_status_check_requires_matching_identity_and_file_revision(self):
        for field, bad in [('id', KEEPER), ('rev', None)]:
            old = getattr(self.client.files[TARGET], field)
            setattr(self.client.files[TARGET], field, bad)
            result = verify_absent(self.client, TARGET)
            self.assertEqual(result['state'], 'uncertain')
            self.assertFalse(result['presence_verified'])
            setattr(self.client.files[TARGET], field, old)
        self.assertEqual(self.client.calls, [])


class RecoveryQueueTests(unittest.TestCase):
    setUp = fixtures.BackgroundJobTests.setUp
    tearDown = fixtures.BackgroundJobTests.tearDown
    enqueue = fixtures.BackgroundJobTests.enqueue
    batch = fixtures.BackgroundJobTests.batch
    plans = fixtures.BackgroundJobTests.plans
    confirmation = fixtures.BackgroundJobTests.confirmation

    def unknown_batch(self):
        job, body = self.enqueue()
        real = self.manager.runner
        def unknown(request):
            if request['action'] == 'execute':
                raise TimeoutError('lost original request')
            return real(request)
        self.manager.runner = unknown
        self.jobs.step()
        self.manager.runner = real
        self.assertEqual(self.jobs.get(job['id'])['state'], 'uncertain')
        return job, body

    def reviews(self):
        reviews = DeletionReviews(self.app)
        self.app.deletion_reviews = reviews
        return reviews

    def test_present_files_get_fresh_review_and_require_new_confirmation(self):
        job, _ = self.unknown_batch()
        original_ids = self.manager.batch(job['progress']['batch_id'])['payload']['operation_ids']
        original_results = [deepcopy(self.manager.job(oid)['result']) for oid in original_ids]
        checked = self.jobs.check(job['id'])
        self.assertEqual(checked['state'], 'needs_review')
        self.assertTrue(checked['can_review_remaining'])
        self.assertNotIn(TARGET, self.jobs.deletion_activity())
        self.assertIn(TARGET, Projection(self.cat, self.store.all()).edges['A'])
        self.assertEqual(self.client.calls, [])
        for oid, previous in zip(original_ids, original_results):
            self.assertEqual(self.manager.job(oid)['result']['attempt_result'], previous)
        self.client.files[TARGET].rev = 'new-reviewed-version'
        reviews = self.reviews()
        fresh = self.jobs.review_remaining(job['id'])
        self.assertEqual(self.jobs.review_remaining(job['id'])['id'], fresh['id'])
        reviews.step()
        batch = reviews.plan(fresh['id'])
        self.assertEqual(batch['files'][0]['revision'], 'new-reviewed-version')
        self.assertEqual(self.client.calls, [])
        # Preparing/reopening a review never starts deletion.
        self.assertFalse(self.jobs.step())
        body = {'batch_id': batch['batch_id'], 'confirm_files': batch['files'], 'confirmed': True}
        new = self.jobs.enqueue_deletion(body, True)
        self.assertEqual(self.jobs.enqueue_deletion(body, True)['id'], new['id'])
        self.jobs.step(); self.jobs.step()
        self.assertEqual(self.jobs.get(new['id'])['state'], 'completed')
        self.assertEqual(self.client.calls, [(TARGET, 'new-reviewed-version'), (KEEPER, 'a1')])
        self.assertEqual([self.manager.job(oid)['state'] for oid in original_ids], ['present', 'present'])
        earlier = self.jobs.get(job['id'])
        self.assertEqual(earlier['state'], 'completed')
        self.assertFalse(earlier['can_review_remaining'])
        self.assertTrue(all(r['state'] == 'deleted' and r.get('resolved_by_operation_id') for r in earlier['progress']['results']))
        self.assertTrue(all('file is present' not in r.get('message', '') for r in earlier['progress']['results']))

    def test_new_review_does_not_reuse_older_unconfirmed_metadata(self):
        old = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        job, _ = self.unknown_batch(); self.jobs.check(job['id'])
        self.client.files[TARGET].rev = 'new-revision'
        reviews = self.reviews(); fresh = self.jobs.review_remaining(job['id']); reviews.step()
        entry = next(e for e in reviews.get(fresh['id'], True)['entries'] if e['asset_id'] == TARGET)
        self.assertNotEqual(entry['operation_id'], old['operation_id'])
        self.assertEqual(entry['plan']['file']['revision'], 'new-revision')

    def test_later_receipt_resolves_only_its_exact_file_in_an_older_partial_job(self):
        job, _ = self.unknown_batch(); self.jobs.check(job['id'])
        self.reviews()
        plan = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        new = self.jobs.enqueue_deletion({'operation_id': plan['operation_id'], 'confirm_file_id': TARGET, 'confirmed': True})
        self.jobs.step()
        result = self.jobs.get(job['id'])
        self.assertEqual(result['state'], 'needs_review')
        self.assertEqual([r['state'] for r in result['progress']['results']], ['deleted', 'present'])
        self.assertEqual([e['asset_id'] for e in self.jobs.review_remaining(job['id'])['entries']], [KEEPER])
        self.assertEqual(self.client.calls, [(TARGET, 'a1')])

    def test_failed_check_isolated_from_other_members_and_keeps_its_reservation(self):
        job, _ = self.unknown_batch()
        self.client.gone.add(KEEPER)
        real = self.manager.runner
        def flaky(request):
            if request['action'] == 'check' and request['file_id'] == TARGET:
                raise TimeoutError('secret')
            return real(request)
        self.manager.runner = flaky
        result = self.jobs.check(job['id'])
        self.assertEqual(result['state'], 'uncertain')
        self.assertEqual([r['state'] for r in result['progress']['results']], ['uncertain', 'deleted'])
        self.assertIn(TARGET, self.jobs.deletion_activity())
        self.assertFalse(result['can_review_remaining'])
        self.assertEqual(self.client.calls, [])
        self.assertNotIn('secret', json.dumps(result))
        self.manager.runner = real
        self.assertEqual(self.jobs.check(job['id'])['state'], 'needs_review')

    def test_checking_older_partial_batch_preserves_later_confirmed_results(self):
        job, _ = self.unknown_batch()
        ids = self.manager.batch(job['progress']['batch_id'])['payload']['operation_ids']
        self.jobs.check_deletion(ids[0])
        plan = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        self.jobs.enqueue_deletion({'operation_id': plan['operation_id'], 'confirm_file_id': TARGET, 'confirmed': True})
        self.jobs.step(); self.client.gone.add(KEEPER)
        result = self.jobs.check(job['id'])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual([r['state'] for r in result['progress']['results']], ['deleted', 'deleted'])
        self.assertTrue(result['progress']['results'][0]['resolved_by_operation_id'])
        self.assertFalse(result['can_review_remaining'])

    def test_individual_history_check_updates_parent_heading_and_keeps_attempt_receipt(self):
        job, _ = self.unknown_batch()
        ids = self.manager.batch(job['progress']['batch_id'])['payload']['operation_ids']
        self.client.gone.update((TARGET, KEEPER))
        for oid in ids:
            self.jobs.check_deletion(oid)
        result = self.jobs.get(job['id'])
        self.assertEqual(result['state'], 'completed')
        self.assertEqual(result['message'], '')
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM background_jobs WHERE id=?', (job['id'],)).fetchone()[0], 'completed')
        self.assertEqual(self.client.calls, [])
        self.assertIn('delete_error', self.manager.job(ids[0])['result']['attempt_result'])

    def test_public_heading_recovers_stale_parent_but_never_overrides_running_job(self):
        job, _ = self.enqueue(); self.jobs.step()
        self.jobs.mark(job['id'], 'uncertain', {'message': 'Old interruption'})
        self.assertEqual(self.jobs.get(job['id'])['state'], 'completed')
        self.jobs.mark(job['id'], 'running', {})
        self.assertEqual(self.jobs.get(job['id'])['state'], 'running')

    def test_unknown_checks_cannot_release_files_or_issue_deletions_after_restart(self):
        job, _ = self.unknown_batch()
        replacement = BackgroundJobs(self.app)
        self.manager.runner = lambda _: (_ for _ in ()).throw(TimeoutError())
        result = replacement.check(job['id'])
        self.assertEqual(result['state'], 'uncertain')
        self.assertFalse(result['can_review_remaining'])
        self.assertIn(TARGET, replacement.deletion_activity())
        self.assertEqual(self.client.calls, [])

    def test_history_check_respects_writer_lease(self):
        job, _ = self.unknown_batch()
        oid = self.manager.batch(job['progress']['batch_id'])['payload']['operation_ids'][0]
        other = BackgroundJobs(self.app)
        with other.writer() as acquired:
            self.assertTrue(acquired)
            with self.assertRaisesRegex(Conflict, 'still active'):
                self.jobs.check_deletion(oid)
        self.assertEqual(self.manager.job(oid)['state'], 'uncertain')

    def test_long_read_cooldown_keeps_full_delay_and_does_not_sleep_writer(self):
        plan = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        self.manager.runner = lambda _: (_ for _ in ()).throw(NativeUnavailable('Rate limit', True, 275))
        with patch('deletions.time.sleep') as sleep:
            result = self.manager.execute({'operation_id': plan['operation_id'], 'confirm_file_id': TARGET, 'confirmed': True})
        self.assertEqual(result['state'], 'rejected')
        self.assertEqual(result['retry_after'], 275)
        self.assertFalse(result['delete_attempted'])
        sleep.assert_not_called()
        reviews = self.reviews()
        fresh = reviews.start_review({'request_id': 'cooldown-test-1234', 'entries': [{'asset_id': TARGET, 'reason': 'unwanted'}]})
        before = time.time(); reviews.inspect_one(fresh['id'], 0)
        row = reviews.row(fresh['id'])
        self.assertGreaterEqual(row['payload']['cooldown_until'], before + 275)
        self.assertGreaterEqual(row['payload']['entries'][0]['next_attempt_at'], before + 275)
        self.assertFalse(reviews.step())
        self.assertEqual(self.client.calls, [])


if __name__ == '__main__':
    unittest.main()
