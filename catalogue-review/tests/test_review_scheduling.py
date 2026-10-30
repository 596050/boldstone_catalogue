"""Observable queue behaviour using fake originals, never live Dropbox."""
from pathlib import Path
from unittest.mock import patch
import json
import sys
import threading
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import test_deletion_reviews as fixtures
from test_deletions import TARGET, KEEPER
from deletion_reviews import DeletionReviews
from deletions import NativeUnavailable


class ReviewSchedulingTests(unittest.TestCase):
    setUp = fixtures.ResilientReviewTests.setUp
    tearDown = fixtures.ResilientReviewTests.tearDown
    start = fixtures.ResilientReviewTests.start

    def throttle_first(self, delay=60):
        job = self.start([TARGET])
        original = self.manager.runner
        with patch.object(self.manager, 'runner', side_effect=NativeUnavailable('Dropbox asked us to wait', True, delay)):
            self.reviews.inspect_one(job['id'], 0)
        self.manager.runner = original
        return job

    def test_another_review_cannot_bypass_dropbox_wait(self):
        with patch('deletion_reviews.time.time', return_value=1000):
            first = self.throttle_first()
            second = self.start([KEEPER], 'another-review-123456')
            with patch.object(self.manager, 'runner', wraps=self.manager.runner) as reads:
                self.assertFalse(self.reviews.step())
                self.reviews.inspect_one(second['id'], 0)
            self.assertEqual(reads.call_count, 0)
            self.assertEqual(self.reviews.get(first['id'])['counts']['pending'], 1)
            self.assertEqual(self.reviews.get(second['id'])['entries'][0]['attempts'], 0)

    def test_cancel_and_restart_do_not_clear_app_wait(self):
        with patch('deletion_reviews.time.time', return_value=1000):
            first = self.throttle_first(275)
            self.reviews.cancel(first['id'])
            second = self.start([KEEPER], 'restart-review-123456')
            restarted = DeletionReviews(self.app)
            with patch.object(self.manager, 'runner', wraps=self.manager.runner) as reads:
                self.assertFalse(restarted.step())
                restarted.retry(first['id'])
                self.assertFalse(restarted.step())
            self.assertEqual(reads.call_count, 0)
            self.assertEqual(restarted.get(second['id'])['retry_at'], 1275)
        with patch('deletion_reviews.time.time', return_value=1276):
            self.assertTrue(restarted.step())
            self.assertTrue(restarted.step())
        self.assertEqual(restarted.get(first['id'])['counts']['ready'], 1)
        self.assertEqual(restarted.get(second['id'])['counts']['ready'], 1)
        self.assertEqual(self.client.calls, [])

    def test_existing_review_wait_survives_upgrade(self):
        job = self.start([TARGET])
        row = self.reviews.row(job['id'])
        row['payload']['cooldown_until'] = 1300
        self.reviews.write(row)
        with patch('deletion_reviews.time.time', return_value=1000):
            restarted = DeletionReviews(self.app)
            another = self.start([KEEPER], 'upgraded-review-123456')
            self.assertEqual(restarted.get(another['id'])['retry_at'], 1300)
            with patch.object(self.manager, 'runner') as reads:
                self.assertFalse(restarted.step())
            reads.assert_not_called()

    def test_concurrent_rate_limits_keep_the_longest_wait(self):
        job = self.start([TARGET, KEEPER])
        barrier = threading.Barrier(2)
        def limited(request):
            barrier.wait(timeout=2)
            raise NativeUnavailable('Wait before retrying', True, 275 if request['binding']['id'] == TARGET else 20)
        with patch('deletion_reviews.time.time', return_value=1000):
            with patch.object(self.manager, 'runner', side_effect=limited):
                self.reviews.step()
            another = self.start([self.third], 'concurrent-wait-123456')
            self.assertEqual(self.reviews.get(job['id'])['retry_at'], 1275)
            self.assertEqual(self.reviews.get(another['id'])['retry_at'], 1275)
        with patch('deletion_reviews.time.time', return_value=1021):
            with patch.object(self.manager, 'runner') as reads:
                self.assertFalse(self.reviews.step())
            reads.assert_not_called()

    def test_wait_status_distinguishes_retry_and_provider_pause(self):
        with patch('deletion_reviews.time.time', return_value=1000):
            job = self.throttle_first()
            status = self.reviews.get(job['id'])
            self.assertEqual(status['retry_at'], 1060)
            self.assertEqual(status['wait_reason'], 'dropbox_cooldown')
            self.reviews.cancel(job['id'])
            self.assertIsNone(self.reviews.get(job['id'])['retry_at'])
        with patch('deletion_reviews.time.time', return_value=1061):
            self.reviews.retry(job['id'])
            with patch.object(self.manager, 'runner', side_effect=TimeoutError('Read failed')):
                self.reviews.inspect_one(job['id'], 0)
            status = self.reviews.get(job['id'])
            self.assertEqual(status['retry_at'], 1063)
            self.assertEqual(status['wait_reason'], 'read_retry')

    def test_invalid_wait_values_do_not_make_the_queue_unfinishable(self):
        for index, delay in enumerate((float('nan'), float('inf'), 'not-a-number', -50)):
            job = self.start([TARGET], 'invalid-wait-review-' + str(index))
            with patch('deletion_reviews.time.time', return_value=1000):
                with patch.object(self.manager, 'runner', side_effect=NativeUnavailable('Temporary failure', True, delay)):
                    self.reviews.inspect_one(job['id'], 0)
                status = self.reviews.get(job['id'])
                self.assertEqual(status['retry_at'], 1002)
                self.assertEqual(status['wait_reason'], 'read_retry')
                json.dumps(status, allow_nan=False)

    def test_resume_does_not_reset_an_inflight_attempt(self):
        job = self.start([TARGET])
        original = self.manager.runner
        entered, release = threading.Event(), threading.Event()
        def delayed(request):
            entered.set()
            self.assertTrue(release.wait(3))
            return original(request)
        with patch.object(self.manager, 'runner', side_effect=delayed) as reads:
            worker = threading.Thread(target=self.reviews.step)
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.reviews.cancel(job['id'])
                resumed = self.reviews.retry(job['id'])
                self.assertEqual(resumed['entries'][0]['state'], 'checking')
                self.assertEqual(resumed['entries'][0]['attempts'], 1)
            finally:
                release.set()
                worker.join(4)
            self.assertFalse(worker.is_alive())
            self.assertEqual(reads.call_count, 1)
        self.assertEqual(self.reviews.get(job['id'])['counts']['ready'], 1)
        self.assertEqual(self.client.calls, [])

    def test_server_stop_finishes_inflight_read_but_leaves_queued_reads_for_restart(self):
        job = self.start()
        self.reviews.workers = 1
        original = self.manager.runner
        reads = []
        def finish_then_stop(request):
            reads.append(request['binding']['id'])
            result = original(request)
            self.reviews.stop()
            return result
        with patch.object(self.manager, 'runner', side_effect=finish_then_stop):
            self.reviews.step()
        self.assertEqual(reads, [TARGET])
        self.assertEqual(self.reviews.get(job['id'])['counts']['ready'], 1)
        self.assertEqual(self.reviews.get(job['id'])['counts']['pending'], 2)
        self.assertFalse(self.reviews.step())
        restarted = DeletionReviews(self.app)
        with patch.object(self.manager, 'runner', wraps=original) as reads:
            restarted.step()
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(restarted.get(job['id'])['counts']['ready'], 3)
        self.assertEqual(self.client.calls, [])


if __name__ == '__main__':
    unittest.main()
