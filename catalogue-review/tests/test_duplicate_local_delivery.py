"""Verified duplicate bytes retain a local display path without inventing native metadata."""
from contextlib import contextmanager
import hashlib
from http.server import ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from media import enrich
from server import Application, Handler
from store import ReviewStore


class DuplicateLocalDeliveryTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'retained.png'
        Image.new('RGB', (13, 11), 'white').save(self.image)
        self.data = self.image.read_bytes()
        self.native_hash = hashlib.sha256(hashlib.sha256(self.data).digest()).hexdigest()

    def prepare(self, recorded_bytes=None):
        cat = SimpleNamespace(assets={
            'id:source': {'source': 'Dropbox', 'role': 'individual',
                'inventory_status': 'CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED',
                'original': {'dropbox_content_hash': self.native_hash, 'bytes': recorded_bytes}},
            'sq:copy': {'source': 'Squarespace', 'role': 'individual',
                'inventory_status': 'retained', 'original': {}},
        }, paths={'sq:copy': (self.image, 'cached source')}, source={})
        enrich(cat, self.root)
        app = Application.__new__(Application)
        app.catalogue = cat
        app.catalogue_lock = threading.RLock()
        app.store = ReviewStore(self.root / 'state')
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = app
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return app, f'http://127.0.0.1:{server.server_port}/api/image?id=id%3Asource'

    def test_verified_copy_supplies_display_size_without_becoming_native_metadata(self):
        app, url = self.prepare()
        original = app.catalogue.assets['id:source']['original']
        self.assertIsNone(original['bytes'])
        self.assertEqual(original['verified_local_bytes'], len(self.data))
        spec = app.image_spec('id:source')
        self.assertFalse(spec['native'])
        self.assertTrue(spec['full_verified'])
        self.assertEqual(spec['bytes'], len(self.data))
        # No native image service is present: this must use the retained copy.
        with urllib.request.urlopen(url, timeout=2) as response:
            self.assertEqual(response.headers['Content-Type'], 'image/png')
            self.assertEqual(response.read(), self.data)

    def test_duplicate_size_cannot_replace_conflicting_recorded_native_metadata(self):
        recorded_bytes = len(self.data) + 1
        app, url = self.prepare(recorded_bytes)
        original = app.catalogue.assets['id:source']['original']
        self.assertEqual(original['verified_local_bytes'], len(self.data))
        self.assertEqual(original['bytes'], recorded_bytes)
        self.assertEqual(app.image_spec('id:source')['bytes'], recorded_bytes)

        @contextmanager
        def actual_original(spec, action):
            yield {'mime': 'image/png', 'bytes': len(self.data)}, BytesIO(self.data)

        app.images = SimpleNamespace(worker=actual_original)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(url, timeout=2)
        self.assertEqual(caught.exception.code, 503)
        self.assertIn('original size changed', json.load(caught.exception)['error'])
        self.assertEqual(original['bytes'], recorded_bytes)
