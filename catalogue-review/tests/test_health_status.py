"""A busy catalogue must not make the launcher mistake its server for a stopped app."""
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler


class HealthStatusTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace(catalogue_lock=threading.RLock(),
                                   catalogue=SimpleNamespace(products={'A': {}, 'B': {}}))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.app = self.app
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}/api/health'

    def test_health_answers_while_another_thread_holds_catalogue_lock(self):
        with self.app.catalogue_lock:
            with urllib.request.urlopen(self.url, timeout=.5) as response:
                health = json.load(response)
        self.assertEqual(health['application'], 'boldstone-review')
        self.assertEqual(health['products'], 2)

    def test_health_still_enforces_local_host_header(self):
        request = urllib.request.Request(self.url, headers={'Host': 'unrelated.example'})
        with self.app.catalogue_lock:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(request, timeout=.5)
        self.assertEqual(caught.exception.code, 403)
