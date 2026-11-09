"""Bad browser/session inputs must produce errors without changing saved reviews."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Application, Handler
import test_review


class RequestValidationTests(unittest.TestCase):
    tearDown = test_review.ReviewTests.tearDown

    def setUp(self):
        test_review.ReviewTests.setUp(self)
        self.app = Application.__new__(Application)
        self.app.catalogue = self.cat
        self.app.store = self.store
        self.app.catalogue_lock = threading.RLock()
        self.app.refresh_source = lambda: False
        self.app.token = 'isolated-session-token'

    def test_invalid_duplicate_versions_cannot_save_or_raise_internal_error(self):
        body = {'kind': 'image', 'product_id': 'A', 'item_id': 'image', 'version': 0,
                'data': {'decision': 'reviewed', 'uses': ['listing']}}
        for versions in [[], ['image'], 'image', 1]:
            with self.subTest(versions=versions), self.assertRaises(ValueError):
                self.app.save({**body, 'member_versions': versions})
        self.assertEqual(self.store.history(), [])
        versions = {'image': 0}
        saved = self.app.save({**body, 'member_versions': versions})
        self.assertEqual(saved['version'], 1)
        self.assertEqual(versions, {'image': 0})

    def test_invalid_nested_assignment_versions_cannot_move_images(self):
        body = {'from_product_id': 'A', 'to_product_id': 'B', 'mode': 'move',
                'asset_ids': ['image']}
        for versions in [[], ['image'], 'image', None, 1]:
            with self.subTest(versions=versions), self.assertRaises(ValueError):
                self.app.assign({**body, 'versions': {'A': versions, 'B': {'image': 0}}})
        self.assertEqual(self.store.history(), [])

    def test_invalid_session_and_request_lengths_return_errors_and_keep_server_available(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = self.app
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=2)
        self.addCleanup(connection.close)
        connection.request('POST', '/api/reviews', '{}', headers={
            'Content-Type': 'application/json', 'X-Review-Token': '\xe9'})
        response = connection.getresponse()
        self.assertEqual(response.status, 403)
        self.assertIn('error', json.loads(response.read()))
        for length in ['abc', '0', '-1', '512000']:
            connection.request('POST', '/api/reviews', '{}', headers={
                'Content-Type': 'application/json', 'X-Review-Token': self.app.token,
                'Content-Length': length})
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn('error', json.loads(response.read()))
        connection.request('GET', '/api/health')
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read())['status'], 'ok')
        self.assertEqual(self.store.history(), [])

    def test_slow_request_body_does_not_freeze_other_reads_or_saves(self):
        self.cat.products['A']['id'] = 'A'
        accepted = threading.Event()

        class ObservedHandler(Handler):
            def headers_ok(handler, write=False):
                result = super().headers_ok(write)
                if write and result:
                    accepted.set()
                return result

        server = ThreadingHTTPServer(('127.0.0.1', 0), ObservedHandler)
        server.app = self.app
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        stalled = socket.create_connection(('127.0.0.1', server.server_port), timeout=2)
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=.5)
        self.addCleanup(connection.close)
        try:
            stalled.sendall((f'POST /api/reviews HTTP/1.1\r\nHost: 127.0.0.1:{server.server_port}\r\n'
                f'X-Review-Token: {self.app.token}\r\nContent-Type: application/json\r\n'
                'Content-Length: 100\r\n\r\n{').encode())
            self.assertTrue(accepted.wait(1))
            connection.request('GET', '/api/health')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['status'], 'ok')
            connection.request('POST', '/api/reviews', json.dumps({
                'kind': 'product', 'product_id': 'A', 'version': 0,
                'data': {'decision': 'include', 'notes': 'Saved during a slow request'}}), headers={
                'Content-Type': 'application/json', 'X-Review-Token': self.app.token})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(json.loads(response.read())['version'], 1)
        finally:
            stalled.close()

    def test_incomplete_request_times_out_without_changing_saved_reviews(self):
        class FastTimeoutHandler(Handler):
            request_body_timeout = .05

        server = ThreadingHTTPServer(('127.0.0.1', 0), FastTimeoutHandler)
        server.app = self.app
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=1)
        self.addCleanup(connection.close)
        connection.request('POST', '/api/reviews', '{', headers={
            'Content-Type': 'application/json', 'X-Review-Token': self.app.token,
            'Content-Length': '100'})
        response = connection.getresponse()
        self.assertEqual(response.status, 408)
        self.assertIn('did not finish', json.loads(response.read())['error'])
        self.assertEqual(self.store.history(), [])


if __name__ == '__main__':
    unittest.main()
