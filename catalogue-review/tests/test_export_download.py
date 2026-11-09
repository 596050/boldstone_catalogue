"""Large review bundles download without materializing or blocking the catalogue."""
import hashlib
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler


class ExportDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / 'exports/20261109T100000Z-0123abcd.zip'
        self.archive.parent.mkdir()
        self.data = b'PK' + bytes(range(256)) * (4 * 1024)
        self.archive.write_bytes(self.data)
        self.app = SimpleNamespace(store=SimpleNamespace(root=self.root), catalogue_lock=threading.RLock())
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.app = self.app
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f'http://127.0.0.1:{self.server.server_port}/api/exports/'

    def test_archive_download_is_not_blocked_by_catalogue_work(self):
        with self.app.catalogue_lock:
            with urllib.request.urlopen(self.base + self.archive.name, timeout=.5) as response:
                self.assertEqual(response.headers['Content-Type'], 'application/zip')
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(response.read(), self.data)

    def test_archive_is_streamed_without_read_bytes(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Do not buffer an archive')):
            with urllib.request.urlopen(self.base + self.archive.name, timeout=2) as response:
                self.assertEqual(hashlib.sha256(response.read()).digest(), hashlib.sha256(self.data).digest())

    def test_missing_and_invalid_archives_return_not_found(self):
        for name in ('not-an-export.zip', '20261109T100000Z-ffffffff.zip'):
            with self.subTest(name=name), self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(self.base + name, timeout=2)
            self.assertEqual(caught.exception.code, 404)
