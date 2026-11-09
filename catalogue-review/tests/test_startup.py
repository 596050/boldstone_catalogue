"""Start the complete application against a private, synthetic publication."""
from http.server import ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import unittest
from unittest.mock import patch
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Application, Handler
from store import ReviewStore
import test_catalogue_metadata
from us_delivery import TariffUnavailable


class StartupTests(unittest.TestCase):
    def test_start_read_save_and_restart_with_private_runtime_and_no_shipping_snapshot(self):
        fixture = test_catalogue_metadata.RetainedMetadataTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        register = fixture.base / 'register.json'
        register.write_text(json.dumps({'components': [], 'active_option_ids': ['A']}))
        pointer_path = fixture.base / 'current-master.json'
        pointer = json.loads(pointer_path.read_text())
        pointer['register_sha256'] = hashlib.sha256(register.read_bytes()).hexdigest()
        pointer_path.write_text(json.dumps(pointer))
        with sqlite3.connect(fixture.database) as db:
            db.execute('INSERT INTO products VALUES(?,?,?,?)', ('A', 'Panel', 'Panels', json.dumps({
                'master_fields': {'Weight': {'display': '6 kg'},
                                  'Dimensions / depth': {'display': '50 x 30 x 6 cm'}},
                'selling_details': {}})))
        runtime = fixture.root / 'private-runtime'
        app = Application(fixture.project, runtime, auto_sync=False)
        self.addCleanup(app.similarity.executor.shutdown)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = app
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def request(path, body=None):
            data = None if body is None else json.dumps(body).encode()
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path, data=data,
                headers={'Content-Type': 'application/json', 'X-Review-Token': app.token})
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.load(response)

        self.assertEqual(request('/api/health')['application'], 'boldstone-review')
        with patch('us_delivery.tariff', side_effect=TariffUnavailable('No verified saved tariff')):
            self.assertEqual(request('/api/bootstrap')['products'][0]['id'], 'A')
            specs = request('/api/specifications')['products']
            self.assertEqual(specs[0]['us_shipping']['status'], 'rate_unavailable')
        saved = request('/api/reviews', {'kind': 'product', 'product_id': 'A', 'version': 0,
                                        'data': {'decision': 'include'}})
        self.assertEqual(saved['version'], 1)
        self.assertEqual(ReviewStore(runtime).get('product', 'A')['data']['decision'], 'include')
        reopened = Application(fixture.project, runtime, auto_sync=False)
        self.addCleanup(reopened.similarity.executor.shutdown)
        self.assertEqual(reopened.store.get('product', 'A')['version'], 1)
        self.assertEqual(reopened.token, app.token)
        self.assertFalse((fixture.project / 'reviews.sqlite3').exists())
