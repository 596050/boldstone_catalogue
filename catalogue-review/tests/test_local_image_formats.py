"""Browser-compatible retained originals keep their bytes and verified identity."""
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
from server import Application, Handler
from store import ReviewStore


class LocalImageFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'retained.image'
        self.asset = {'source': 'Squarespace', 'original': {}}
        self.app = Application.__new__(Application)
        self.app.store = ReviewStore(self.root / 'private-runtime')
        self.app.catalogue_lock = threading.RLock()
        self.app.catalogue = SimpleNamespace(assets={'sq:local': self.asset},
                                            paths={'sq:local': (self.path, 'cached source')})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.app = self.app
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}/api/image?id=sq%3Alocal'

    def prepare(self, format):
        from PIL import Image
        output = BytesIO()
        Image.new('RGB', (13, 11), 'white').save(output, format=format)
        data = output.getvalue()
        self.path.write_bytes(data)
        self.asset['original'] = {'locally_verified': True, 'bytes': len(data),
                                  'sha256': hashlib.sha256(data).hexdigest()}
        return data

    def test_retained_bitmap_and_avif_are_served_without_thumbnail_substitution(self):
        for format, mime in (('BMP', 'image/bmp'), ('AVIF', 'image/avif')):
            with self.subTest(format=format):
                data = self.prepare(format)
                with urllib.request.urlopen(self.url, timeout=2) as response:
                    self.assertEqual(response.headers['Content-Type'], mime)
                    self.assertEqual(response.read(), data)

    def test_changed_verified_payload_is_withheld(self):
        for same_size in (False, True):
            with self.subTest(same_size=same_size):
                data = self.prepare('PNG')
                self.path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]) if same_size else data + b'replaced')
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(self.url, timeout=2)
                self.assertEqual(caught.exception.code, 409)
                self.assertIn('bytes changed', json.load(caught.exception)['error'])

    def test_dropbox_hash_still_protects_bytes_when_no_sha256_was_retained(self):
        data = self.prepare('PNG')
        self.asset['original'].pop('sha256')
        self.asset['original']['dropbox_content_hash'] = hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()
        self.path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url, timeout=2)
        self.assertEqual(caught.exception.code, 409)

    def test_previews_do_not_claim_or_require_original_hash_identity(self):
        data = self.prepare('JPEG')
        self.app.catalogue.paths['sq:local'] = (self.path, 'cached preview')
        self.asset['original'].update(sha256='a' * 64, locally_verified=False)
        with urllib.request.urlopen(self.url, timeout=2) as response:
            self.assertEqual(response.read(), data)
