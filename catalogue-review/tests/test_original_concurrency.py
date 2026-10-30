"""Slow original downloads use fakes; no native Dropbox access or credentials."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import subprocess
import sys
import threading
import unittest
import urllib.request

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from media import MediaCache
from server import Application, Handler
from store import Conflict
import test_review

TARGET = 'id:original'


class OriginalConcurrencyTests(unittest.TestCase):
    tearDown = test_review.ReviewTests.tearDown

    def setUp(self):
        test_review.ReviewTests.setUp(self)
        self.asset = self.cat.assets.pop('image')
        self.asset['id'] = TARGET
        self.cat.assets[TARGET] = self.asset
        for pid in self.cat.edges:
            self.cat.edges[pid][TARGET] = self.cat.edges[pid].pop('image')
            self.cat.products[pid].update(id=pid, primary_id=TARGET)
        self.cat.paths[TARGET] = self.cat.paths.pop('image')
        self.cat.project = self.root
        self.cat.source['dedupe'] = {}
        self.cat.duplicate_members = {TARGET: [TARGET]}
        self.info = MediaCache(self.root).inspect(self.image, hashes=True)
        self.asset['original'] = {'bytes': self.info['bytes'], 'dropbox_content_hash': self.info['dropbox_content_hash']}
        self.info.update(file_id=TARGET, path=str(self.image), checked_utc='2026-10-29T12:00:00Z')
        python = self.root / 'application/.venv/bin/python'
        python.parent.mkdir(parents=True)
        python.touch()
        self.app = Application.__new__(Application)
        self.app.store, self.app.catalogue = self.store, self.cat
        self.app.catalogue_lock = threading.RLock()
        self.app.original_lock = threading.Lock()
        self.app.refresh_source = lambda: False
        self.app.token = 'isolated-only'
        self.body = {'asset_id': TARGET, 'expected_content_hash': self.info['dropbox_content_hash']}

    def receipt(self, info=None):
        return SimpleNamespace(returncode=0, stdout=json.dumps(self.info if info is None else info))

    def server(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = self.app
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return 'http://127.0.0.1:' + str(server.server_port)

    def request(self, base, path, body=None, timeout=2):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(base + path, data=data, headers={
            'Content-Type': 'application/json', 'X-Review-Token': self.app.token})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def test_download_does_not_block_health_gallery_or_saved_reviews(self):
        base = self.server()
        entered, release = threading.Event(), threading.Event()
        def slow(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test download was not released')
            return self.receipt()
        with patch('server.subprocess.run', side_effect=slow), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.request, base, '/api/original', self.body, 8)
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.request(base, '/api/health', timeout=.5)['status'], 'ok')
                self.assertEqual(self.request(base, '/api/products/A', timeout=.5)['id'], 'A')
                saved = self.request(base, '/api/reviews', {
                    'kind': 'product', 'product_id': 'A', 'item_id': '', 'version': 0,
                    'data': {'decision': 'include', 'notes': 'Saved while downloading'}}, timeout=.5)
                self.assertEqual(saved['data']['notes'], 'Saved while downloading')
            finally:
                release.set()
                future.result(timeout=3)

    def test_newer_bytes_are_not_replaced_by_an_old_download(self):
        def replaced(*args, **kwargs):
            self.asset['original']['dropbox_content_hash'] = 'b' * 64
            return self.receipt()
        with patch('server.subprocess.run', side_effect=replaced), self.assertRaisesRegex(Conflict, 'changed'):
            self.app.original(self.body)
        self.assertNotIn('locally_verified', self.asset['original'])
        self.assertEqual(self.cat.paths[TARGET][1], 'cached source')

    def test_removal_during_download_returns_a_clear_conflict(self):
        def removed(*args, **kwargs):
            del self.cat.assets[TARGET]
            return self.receipt()
        with patch('server.subprocess.run', side_effect=removed), self.assertRaisesRegex(Conflict, 'removed|changed'):
            self.app.original(self.body)

    def test_completed_deletion_cannot_be_resurrected_by_download(self):
        def deleted(*args, **kwargs):
            self.app.projection = lambda: SimpleNamespace(cid=lambda aid: aid, deleted={TARGET})
            return self.receipt()
        with patch('server.subprocess.run', side_effect=deleted), self.assertRaisesRegex(Conflict, 'delet|removed'):
            self.app.original(self.body)
        self.assertNotIn('locally_verified', self.asset['original'])

    def test_a_deleted_original_is_rejected_before_any_download(self):
        self.app.projection = lambda: SimpleNamespace(cid=lambda aid: aid, deleted={TARGET})
        with patch('server.subprocess.run') as process, self.assertRaisesRegex(Conflict, 'delet'):
            self.app.original(self.body)
        process.assert_not_called()

    def test_changed_duplicate_representative_requires_reloading_the_group(self):
        def regrouped(*args, **kwargs):
            self.cat.assets['id:copy'] = deepcopy(self.asset)
            self.cat.assets['id:copy']['id'] = 'id:copy'
            self.cat.canonical_assets = {TARGET: 'id:copy', 'id:copy': 'id:copy'}
            self.cat.duplicate_members = {'id:copy': [TARGET, 'id:copy']}
            return self.receipt()
        with patch('server.subprocess.run', side_effect=regrouped), self.assertRaisesRegex(Conflict, 'group changed'):
            self.app.original(self.body)
        self.assertNotIn('locally_verified', self.asset['original'])

    def test_a_moved_unchanged_file_still_receives_its_original(self):
        def moved(*args, **kwargs):
            self.asset['name'] = 'panel__white-in-situ__001.png'
            return self.receipt()
        with patch('server.subprocess.run', side_effect=moved):
            result = self.app.original(self.body)
        self.assertEqual(result['asset']['name'], 'panel__white-in-situ__001.png')
        self.assertEqual(result['asset']['original']['dimensions'], [1, 1])

    def test_same_file_in_a_new_catalogue_receives_download_and_keeps_new_metadata(self):
        def refreshed(*args, **kwargs):
            self.app.catalogue = deepcopy(self.cat)
            self.app.catalogue.assets[TARGET]['name'] = 'Current catalogue name'
            return self.receipt()
        with patch('server.subprocess.run', side_effect=refreshed):
            result = self.app.original(self.body)
        self.assertEqual(result['asset']['name'], 'Current catalogue name')
        self.assertTrue(result['asset']['original']['locally_verified'])
        self.assertNotIn('locally_verified', self.asset['original'])

    def test_current_duplicate_mapping_does_not_apply_metadata_to_replaced_bytes(self):
        def changed_member(*args, **kwargs):
            self.cat.assets['id:copy'] = deepcopy(self.asset)
            self.cat.assets['id:copy']['original']['dropbox_content_hash'] = 'c' * 64
            self.cat.duplicate_members[TARGET].append('id:copy')
            return self.receipt()
        with patch('server.subprocess.run', side_effect=changed_member):
            self.app.original(self.body)
        self.assertNotIn('locally_verified', self.cat.assets['id:copy']['original'])

    def test_identical_dropbox_duplicate_receives_metadata_without_touching_platform_copy(self):
        for aid, source in [('id:copy', 'Dropbox'), ('platform', 'Shopify')]:
            self.cat.assets[aid] = deepcopy(self.asset)
            self.cat.assets[aid].update(id=aid, source=source)
            self.cat.duplicate_members[TARGET].append(aid)
        with patch('server.subprocess.run', return_value=self.receipt()):
            self.app.original(self.body)
        self.assertTrue(self.cat.assets['id:copy']['original']['locally_verified'])
        self.assertNotIn('locally_verified', self.cat.assets['platform']['original'])

    def test_displayed_hash_is_checked_before_starting_download(self):
        self.asset['original']['dropbox_content_hash'] = 'd' * 64
        with patch('server.subprocess.run') as process, self.assertRaisesRegex(Conflict, 'changed'):
            self.app.original(self.body)
        process.assert_not_called()

    def test_second_fetch_fails_fast_without_starting_another_download(self):
        entered, release = threading.Event(), threading.Event()
        def slow(*args, **kwargs):
            entered.set();release.wait(3)
            return self.receipt()
        with patch('server.subprocess.run', side_effect=slow) as process, ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(self.app.original, self.body)
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaisesRegex(Conflict, 'Another original'):
                    self.app.original(self.body)
                self.assertEqual(process.call_count, 1)
            finally:
                release.set();first.result(timeout=3)

    def test_timeout_releases_download_slot_for_deliberate_retry(self):
        with patch('server.subprocess.run', side_effect=subprocess.TimeoutExpired('fake', 100)), self.assertRaisesRegex(ValueError, 'timed out'):
            self.app.original(self.body)
        with patch('server.subprocess.run', return_value=self.receipt()):
            self.assertTrue(self.app.original(self.body)['asset']['original']['locally_verified'])

    def test_source_refresh_is_locked_before_and_after_network_work(self):
        checks = []
        def refresh():
            acquired = []
            def check():
                ok = self.app.catalogue_lock.acquire(timeout=.02)
                acquired.append(ok)
                if ok:self.app.catalogue_lock.release()
            thread = threading.Thread(target=check);thread.start();thread.join(1)
            checks.append(not acquired[0])
        self.app.refresh_source = refresh
        with patch('server.subprocess.run', return_value=self.receipt()):
            self.app.original(self.body)
        self.assertEqual(checks, [True, True])

    def test_unexpected_download_identity_does_not_mark_original_verified(self):
        info = {**self.info, 'file_id': 'id:other'}
        with patch('server.subprocess.run', return_value=self.receipt(info)), self.assertRaisesRegex(ValueError, 'verification|receipt'):
            self.app.original(self.body)
        self.assertNotIn('locally_verified', self.asset['original'])

    def test_invalid_receipts_leave_metadata_untouched_and_release_the_download_slot(self):
        for info in ([], {}, {**self.info, 'bytes': self.info['bytes'] + 1}, {**self.info, 'dropbox_content_hash': 'e' * 64}):
            with self.subTest(info=info):
                with patch('server.subprocess.run', return_value=self.receipt(info)), self.assertRaises(ValueError):
                    self.app.original(self.body)
                self.assertFalse(self.app.original_lock.locked())
                self.assertNotIn('locally_verified', self.asset['original'])


if __name__ == '__main__':
    unittest.main()
