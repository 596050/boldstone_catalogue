"""Real HTTP/save/readback checks; native Dropbox is a disposable simulator."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
import urllib.error
import urllib.request
from urllib.parse import quote

import test_background_jobs
from test_deletions import TARGET, KEEPER
from server import Handler
from store import ReviewStore


class PrimaryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_background_jobs.BackgroundJobTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.organisation_fixture()
        self.app = self.fixture.app
        self.store = self.fixture.store
        self.app.token = 'isolated-primary-workflow-token'
        self.app.refresh_source = lambda: False
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.app = self.app
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, body=None):
        request = urllib.request.Request(self.base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'Origin': self.base,
                     'X-Review-Token': self.app.token})
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def read(self, aid=TARGET, primary=True):
        status, result = self.request('/api/image-components?id=' + quote(aid) + ('&primary=1' if primary else ''))
        self.assertEqual(status, 200, result)
        return result

    def row(self, pid='L1', aid=TARGET, primary=True):
        return next(r for r in self.read(aid, primary)['rows'] if r['product_id'] == pid)

    def write(self, rows, aid=TARGET, content_hash=None):
        return self.request('/api/image-components', {'asset_id': aid,
            'content_hash': self.read(aid)['content_hash'] if content_hash is None else content_hash,
            'rows': rows})

    def assert_no_native_work(self):
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM background_jobs').fetchone()[0], 0)
        self.assertEqual(self.fixture.native.moves, [])
        self.assertEqual(self.fixture.native.creates, [])

    def test_primary_round_trip_and_durable_reload_without_file_move(self):
        row = self.row()
        self.assertIs(row['primary'], False)
        row.update(primary=True, listing=True, advertising=True)
        status, saved = self.write([row])
        self.assertEqual(status, 200, saved)
        self.assertFalse(saved['organisation_changed'])
        self.assertTrue(self.row()['primary'])
        reloaded = ReviewStore(self.store.root).get('image', 'L1', TARGET)['data']
        self.assertTrue(reloaded['primary'])
        self.assertEqual(set(reloaded['uses']), {'listing', 'advertising'})
        self.assertFalse(self.row('L2')['primary'])
        self.assert_no_native_work()

    def test_same_photo_can_be_primary_for_two_components_independently(self):
        rows = [self.row(pid) for pid in ('L1', 'L2')]
        for row in rows:
            row.update(primary=True, listing=True)
        self.assertEqual(self.write(rows)[0], 200)
        row = self.row('L1')
        row.update(primary=False, listing=False, advertising=True)
        self.assertEqual(self.write([row])[0], 200)
        self.assertFalse(self.row('L1')['primary'])
        self.assertTrue(self.row('L1')['advertising'])
        self.assertTrue(self.row('L2')['primary'])
        self.assert_no_native_work()

    def test_primary_replacement_keeps_previous_listing_ads_and_caption(self):
        cat = self.app.catalogue
        cat.assets[KEEPER] = {**deepcopy(cat.assets[TARGET]), 'id': KEEPER}
        cat.edges['L1'][KEEPER] = {'tier': 'folder'}
        self.store.save('image', 'L1', KEEPER,
            {'decision': 'reviewed', 'uses': ['listing', 'advertising'], 'primary': True, 'caption': 'Retain caption'},
            0, cat.source['register_sha256'], {})
        row = self.row()
        row.update(listing=True, primary=True)
        self.assertEqual(self.write([row])[0], 200)
        old = self.store.get('image', 'L1', KEEPER)['data']
        self.assertFalse(old['primary'])
        self.assertEqual(old['caption'], 'Retain caption')
        self.assertEqual(set(old['uses']), {'listing', 'advertising'})
        self.assertTrue(self.row()['primary'])
        self.assert_no_native_work()

    def test_old_open_tabs_preserve_primary_on_ads_and_clear_it_on_listing_off(self):
        row = self.row()
        row.update(listing=True, primary=True)
        self.assertEqual(self.write([row])[0], 200)
        legacy = self.row(primary=False)
        self.assertNotIn('primary', legacy)
        legacy['advertising'] = True
        self.assertEqual(self.write([legacy])[0], 200)
        self.assertTrue(self.row()['primary'])
        legacy = self.row(primary=False)
        legacy['listing'] = False
        self.assertEqual(self.write([legacy])[0], 200)
        self.assertFalse(self.row()['primary'])
        self.assertTrue(self.row()['advertising'])
        self.assert_no_native_work()

    def test_concurrent_tabs_cannot_overwrite_primary_or_other_uses(self):
        one, two = self.row(), self.row()
        one.update(listing=True, primary=True)
        two.update(advertising=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda row: self.write([row]), [one, two]))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        actual = self.row()
        self.assertIn((actual['listing'], actual['primary'], actual['advertising']),
                      [(True, True, False), (False, False, True)])
        self.assertEqual(self.store.get('image', 'L1', TARGET)['version'], 1)
        self.assert_no_native_work()

    def test_changed_bytes_reject_multi_component_save_atomically(self):
        rows = [self.row(pid) for pid in ('L1', 'L2')]
        for row in rows:
            row.update(listing=True, primary=True)
        before = self.store.all()
        status, _ = self.write(rows, content_hash='outdated')
        self.assertEqual(status, 409)
        self.assertEqual(before, self.store.all())
        self.assert_no_native_work()

    def test_primary_on_new_component_queues_only_association_work(self):
        row = self.row('S1')
        self.assertFalse(row['shown'])
        row.update(shown=True, listing=True, primary=True)
        status, saved = self.write([row])
        self.assertEqual(status, 200, saved)
        self.assertTrue(saved['organisation_changed'])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM background_jobs').fetchone()[0], 1)
        row = self.row('S1')
        row['advertising'] = True
        self.assertEqual(self.write([row])[0], 200)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM background_jobs').fetchone()[0], 1)
        self.assertEqual(self.fixture.native.moves, [])

    def test_invalid_primary_and_unknown_component_leave_no_partial_save(self):
        valid, invalid = self.row('L1'), self.row('L2')
        valid.update(listing=True, primary=True)
        invalid.update(primary=True, listing=False)
        before = self.store.all()
        self.assertEqual(self.write([valid, invalid])[0], 400)
        invalid.update(product_id='retired-component', listing=True)
        self.assertEqual(self.write([valid, invalid])[0], 400)
        self.assertEqual(self.store.all(), before)
        self.assert_no_native_work()
