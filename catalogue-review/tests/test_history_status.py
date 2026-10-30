"""History and cancellation regressions; native calls use in-memory fakes."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import json
import sys
import threading
import unittest
import urllib.request
from unittest.mock import Mock

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import test_background_jobs as fixtures
from deletion_reviews import DeletionReviews
from server import Handler
from test_deletions import TARGET


class HistoryStatusTests(unittest.TestCase):
    setUp = fixtures.BackgroundJobTests.setUp
    tearDown = fixtures.BackgroundJobTests.tearDown

    def test_history_endpoint_reads_receipts_without_rebuilding_or_publishing_catalogue(self):
        p = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        real = self.manager.runner
        self.manager.runner = Mock(side_effect=TimeoutError('Isolated unknown result'))
        self.manager.execute({'operation_id': p['operation_id'], 'confirm_file_id': TARGET, 'confirmed': True})
        self.manager.runner = real
        self.app.refresh_source = Mock(side_effect=AssertionError('History must not project the catalogue'))
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = self.app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with urllib.request.urlopen(base + '/api/deletions/history', timeout=2) as response:
                self.assertEqual(response.status, 200)
                rows = json.load(response)
            self.assertEqual(rows[0]['state'], 'uncertain')
            self.jobs.check_deletion(p['operation_id'])
            with urllib.request.urlopen(base + '/api/deletions/history', timeout=2) as response:
                rows = json.load(response)
            self.assertEqual(rows[0]['state'], 'present')
            self.assertTrue(rows[0]['result']['presence_verified'])
            self.assertEqual(rows[0]['file_id'], TARGET)
            self.assertEqual(self.client.calls, [])
            self.app.refresh_source.assert_not_called()
            with urllib.request.urlopen(base + '/api/health', timeout=2) as response:
                version = json.load(response)['version']
                self.assertIn('BoldstoneReview/' + version, response.headers['Server'])
        finally:
            server.shutdown(); server.server_close(); thread.join(2)

    def test_cancelled_confirmation_stays_cancelled_and_fresh_review_requires_new_confirmation(self):
        self.app.deletion_reviews = reviews = DeletionReviews(self.app)
        p = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        body = {'operation_id': p['operation_id'], 'confirm_file_id': TARGET, 'confirmed': True}
        old = self.jobs.enqueue_deletion(body)
        self.jobs.cancel(old['id'])
        self.assertEqual(self.jobs.enqueue_deletion(body)['state'], 'cancelled')
        self.jobs.step()
        self.assertEqual(self.client.calls, [])
        review = self.jobs.review_remaining(old['id'])
        self.assertEqual(self.jobs.review_remaining(old['id'])['id'], review['id'])
        reviews.step()
        plan = reviews.plan(review['id'])
        self.assertNotEqual(plan['operation_ids'], [p['operation_id']])
        self.jobs.step()
        self.assertEqual(self.client.calls, [])
        fresh_body = {'batch_id': plan['batch_id'], 'confirm_files': plan['files'], 'confirmed': True}
        fresh = self.jobs.enqueue_deletion(fresh_body, True)
        self.jobs.step()
        self.assertEqual(self.jobs.get(fresh['id'])['state'], 'completed')
        self.assertEqual(self.jobs.enqueue_deletion(fresh_body, True)['state'], 'completed')
        self.jobs.step()
        self.assertEqual(self.client.calls, [(TARGET, 'a1')])


if __name__ == '__main__':
    unittest.main()
