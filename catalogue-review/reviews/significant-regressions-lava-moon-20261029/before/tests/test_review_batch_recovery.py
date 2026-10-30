"""Saved read checks must survive overlapping reviews and failed local commits."""
from pathlib import Path
from unittest.mock import patch
import json
import sqlite3
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import test_background_jobs as fixtures
import test_deletion_reviews as review_fixtures
from test_deletions import TARGET, KEEPER
from deletion_reviews import DeletionReviews
from store import Conflict


class ReviewBatchRecoveryTests(unittest.TestCase):
    start = review_fixtures.ResilientReviewTests.start
    finish = review_fixtures.ResilientReviewTests.finish
    tearDown = review_fixtures.ResilientReviewTests.tearDown

    def setUp(self):
        fixtures.BackgroundJobTests.setUp(self)
        self.reviews = DeletionReviews(self.app)
        self.app.deletion_reviews = self.reviews

    def overlapping(self):
        first = self.start([TARGET], 'review-overlap-first')
        self.finish()
        second = self.start([TARGET, KEEPER], 'review-overlap-second')
        self.finish()
        return first, second

    def test_overlapping_unconfirmed_reviews_can_each_prepare_confirmation(self):
        first, second = self.overlapping()
        first_plan = self.reviews.plan(first['id'])
        first_job = self.manager.job(first_plan['operation_ids'][0])
        second_plan = self.reviews.plan(second['id'])
        self.assertEqual({f['id'] for f in second_plan['files']}, {TARGET, KEEPER})
        self.assertTrue(set(first_plan['operation_ids']).isdisjoint(second_plan['operation_ids']))
        self.assertEqual(self.manager.job(first_job['id']), first_job)
        self.assertEqual(self.manager.batch(first_plan['batch_id'])['state'], 'prepared')
        self.assertEqual(self.reviews.plan(second['id']), second_plan)
        copied = self.manager.job(second_plan['operation_ids'][0])
        for field in ('file', 'binding', 'context_hash', 'expires_at', 'reason'):
            self.assertEqual(copied['payload'][field], first_job['payload'][field])
        self.assertNotIn('queue_confirmed_at', copied['payload'])
        self.assertEqual(self.client.calls, [])

    def test_legacy_orphaned_batch_does_not_strand_saved_checks(self):
        review = self.start(); self.finish()
        ids = [e['operation_id'] for e in self.reviews.get(review['id'])['entries']]
        orphan = self.manager.prepare_batch({'operation_ids': ids})
        plan = self.reviews.plan(review['id'])
        self.assertEqual(len(plan['files']), 3)
        self.assertTrue(set(ids).isdisjoint(plan['operation_ids']))
        self.assertEqual(self.manager.batch(orphan['batch_id'])['state'], 'prepared')
        self.assertEqual(self.client.calls, [])

    def test_legacy_detached_batch_pointer_can_prepare_a_fresh_confirmation(self):
        review = self.start(); self.finish()
        old = self.reviews.plan(review['id'])
        # Simulate the old retry path failing after detach had already committed.
        row = self.reviews.row(review['id']); self.reviews.detach_batch(row)
        self.assertEqual(self.reviews.row(review['id'])['payload']['batch_id'], old['batch_id'])
        fresh = self.reviews.plan(review['id'])
        self.assertNotEqual(fresh['batch_id'], old['batch_id'])
        self.assertEqual(len(fresh['files']), 3)
        self.assertIn(old['batch_id'], self.reviews.row(review['id'])['payload']['previous_batches'])
        self.assertEqual(self.client.calls, [])

    def test_failed_confirmation_save_rolls_back_batch_and_member_bindings(self):
        review = self.start(); self.finish()
        before = self.reviews.row(review['id'])
        write = self.reviews.write
        def fail_final(row, *args, **kwargs):
            if row['payload'].get('batch_id'):
                raise sqlite3.OperationalError('Injected final confirmation write failure')
            return write(row, *args, **kwargs)
        with patch.object(self.reviews, 'write', side_effect=fail_final):
            with self.assertRaises(sqlite3.OperationalError): self.reviews.plan(review['id'])
        self.assertEqual(self.reviews.row(review['id']), before)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deletion_batches').fetchone()[0], 0)
        for e in before['payload']['entries']:
            self.assertNotIn('batch_id', self.manager.job(e['operation_id'])['payload'])
        self.assertEqual(len(self.reviews.plan(review['id'])['files']), 3)
        self.assertEqual(self.client.calls, [])

    def test_failed_retry_save_keeps_old_confirmation_intact(self):
        review = self.start(); self.finish()
        plan = self.reviews.plan(review['id'])
        before = self.reviews.row(review['id'])
        members = [self.manager.job(oid) for oid in plan['operation_ids']]
        with patch.object(self.reviews, 'write', side_effect=sqlite3.OperationalError('Injected retry write failure')):
            with self.assertRaises(sqlite3.OperationalError): self.reviews.retry(review['id'])
        self.assertEqual(self.reviews.row(review['id']), before)
        self.assertEqual(self.manager.batch(plan['batch_id'])['state'], 'prepared')
        self.assertEqual([self.manager.job(oid) for oid in plan['operation_ids']], members)
        self.assertEqual(self.reviews.plan(review['id']), plan)
        self.assertEqual(self.client.calls, [])

    def test_overlap_with_confirmed_job_skips_reserved_file_but_keeps_other(self):
        first, second = self.overlapping()
        plan = self.reviews.plan(first['id'])
        self.jobs.enqueue_deletion({'batch_id': plan['batch_id'], 'confirm_files': plan['files'], 'confirmed': True}, True)
        other = self.reviews.plan(second['id'])
        self.assertEqual([f['id'] for f in other['files']], [KEEPER])
        self.assertEqual(self.reviews.get(second['id'])['counts']['skipped'], 1)
        self.assertEqual(self.client.calls, [])

    def test_stale_shared_check_requires_new_read_instead_of_fresh_expiry(self):
        first, second = self.overlapping()
        plan = self.reviews.plan(first['id'])
        job = self.manager.job(plan['operation_ids'][0]); job['payload']['expires_at'] = 1
        with self.store.connect() as db:
            db.execute('UPDATE deletion_jobs SET payload=? WHERE id=?', (json.dumps(job['payload']), job['id']))
        other = self.reviews.plan(second['id'])
        self.assertEqual([f['id'] for f in other['files']], [KEEPER])
        self.assertEqual(self.reviews.get(second['id'])['counts']['failed'], 1)
        self.assertEqual(self.client.calls, [])

    def test_two_confirmed_overlapping_batches_delete_each_original_only_once(self):
        first, second = self.overlapping()
        first_plan = self.reviews.plan(first['id']); second_plan = self.reviews.plan(second['id'])
        queued = []
        for plan in (first_plan, second_plan):
            queued.append(self.jobs.enqueue_deletion({'batch_id': plan['batch_id'], 'confirm_files': plan['files'], 'confirmed': True}, True))
        self.assertEqual(len(queued[1]['skipped']), 1)
        self.jobs.step(); self.jobs.step()
        self.assertCountEqual(self.client.calls, [(TARGET, 'a1'), (KEEPER, 'a1')])
        self.assertTrue(all(self.jobs.get(j['id'])['state'] == 'completed' for j in queued))

    def test_copy_and_new_batch_roll_back_if_saved_review_write_fails(self):
        first, second = self.overlapping(); first_plan = self.reviews.plan(first['id'])
        with self.store.connect() as db:
            before = db.execute('SELECT COUNT(*) FROM deletion_jobs').fetchone()[0]
        saved = self.reviews.row(second['id'])
        with patch.object(self.reviews, 'write', side_effect=sqlite3.OperationalError('Injected copy commit failure')):
            with self.assertRaises(sqlite3.OperationalError): self.reviews.plan(second['id'])
        self.assertEqual(self.reviews.row(second['id']), saved)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deletion_jobs').fetchone()[0], before)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM deletion_batches').fetchone()[0], 1)
        self.assertEqual(self.reviews.plan(first['id']), first_plan)
        self.assertEqual(len(self.reviews.plan(second['id'])['files']), 2)
        self.assertEqual(self.client.calls, [])

    def test_all_invalid_checks_persist_failure_before_returning_error(self):
        review = self.start([TARGET]); self.finish()
        self.store.save('image', 'A', TARGET, {'decision': 'reviewed', 'uses': ['advertising']},
                        0, self.cat.source['register_sha256'], {})
        with self.assertRaisesRegex(Conflict, 'No checked files'): self.reviews.plan(review['id'])
        self.assertEqual(self.reviews.get(review['id'])['counts']['failed'], 1)
        self.reviews.retry(review['id']); self.finish()
        self.assertEqual(len(self.reviews.plan(review['id'])['files']), 1)
        self.assertEqual(self.client.calls, [])

    def test_cancelled_confirmation_is_not_copied_or_implicitly_renewed(self):
        first, second = self.overlapping(); plan = self.reviews.plan(first['id'])
        queued = self.jobs.enqueue_deletion({'batch_id': plan['batch_id'], 'confirm_files': plan['files'], 'confirmed': True}, True)
        self.jobs.cancel(queued['id'])
        other = self.reviews.plan(second['id'])
        self.assertEqual([f['id'] for f in other['files']], [KEEPER])
        self.assertEqual(self.reviews.get(second['id'])['counts']['failed'], 1)
        self.reviews.retry(second['id']); self.finish()
        fresh = self.reviews.plan(second['id'])
        self.assertEqual({f['id'] for f in fresh['files']}, {TARGET, KEEPER})
        self.assertTrue(all('queue_confirmed_at' not in self.manager.job(oid)['payload'] for oid in fresh['operation_ids']))
        self.assertEqual(self.client.calls, [])


if __name__ == '__main__': unittest.main()
