import copy
import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import Hold, atomic_json, digest
from upload_bridge import UploadClient, UploadQueue, UploadServer, VERSION, build_helper


class UploadQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.media = self.directory / 'original.png'
        self.media.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
        self.clock = [1000]
        self.queue = UploadQueue(self.directory, now=lambda: self.clock[0])
        self.job = {'id': 'fixture-job', 'profile_id': 'boldstone_facebook', 'media_path': str(self.media),
                    'media_sha256': digest(self.media.read_bytes()), 'media_type': 'image/png',
                    'business_id': '123', 'asset_id': '456'}
        self.binding = {'window_id': 12, 'tab_id': 13, 'owner': 'fixture-owner',
                        'url': 'https://business.facebook.com/latest/composer/?business_id=123&asset_id=456'}
        self.trigger = [{'selector': '[role=button]', 'name': 'Add photo/video'}]
        self.guards = [{'purpose': 'account', 'locator': [{'selector': '#actor'}], 'contains': 'Fixture'}]

    def submit(self):
        return self.queue.submit(self.job, self.binding, self.trigger, self.guards)

    def success(self, claim):
        return {'ok': True, 'request_id': claim['request_id'], 'sha256': self.job['media_sha256'],
                'phase': 'FILE_EVENTS_DISPATCHED', 'method': 'chrome-main-world-file-input',
                'size': self.media.stat().st_size, 'name': self.media.name}

    def test_request_once_and_claim_once(self):
        value = self.submit()
        self.assertEqual(self.submit(), value)
        claim = self.queue.claim(value['request_id'])
        self.assertNotIn('media_path', claim)
        with self.assertRaisesRegex(Hold, 'UPLOAD_NOT_CLAIMABLE'):
            self.queue.claim(value['request_id'])
        self.assertEqual(self.queue.media(value['request_id'], claim['lease'])[0], self.media.read_bytes())

    def test_changed_scope_and_wrong_meta_account_hold(self):
        self.submit()
        self.trigger[0]['name'] = 'Post'
        with self.assertRaisesRegex(Hold, 'UPLOAD_REQUEST_CHANGED'):
            self.submit()
        self.binding['url'] = self.binding['url'].replace('asset_id=456', 'asset_id=999')
        with self.assertRaisesRegex(Hold, 'WRONG_META_ACCOUNT'):
            self.submit()

    def test_only_proven_unstarted_missing_control_can_be_requeued(self):
        claim = self.queue.claim(self.submit()['request_id'])
        result = {'ok': False, 'request_id': claim['request_id'], 'sha256': claim['sha256'],
                  'phase': 'NOT_STARTED', 'code': 'UPLOAD_CONTROL_MISSING'}
        self.queue.complete(claim['request_id'], claim['lease'], result)
        retry = self.submit()
        self.assertEqual(retry['status'], 'PENDING')
        self.assertEqual(retry['previous_attempts'][0]['result'], result)
        second = self.queue.claim(retry['request_id'])
        self.assertNotEqual(second['lease'], claim['lease'])
        self.queue.complete(second['request_id'], second['lease'], {
            **result, 'code': 'FILE_INPUT_NOT_CREATED'})
        self.trigger[0]['name'] = 'Upload from computer'
        self.assertEqual(self.submit()['status'], 'PENDING')
        self.guards[0]['contains'] = 'Another account'
        with self.assertRaisesRegex(Hold, 'UPLOAD_REQUEST_CHANGED'):
            self.submit()

    def test_account_guard_and_destination_required(self):
        self.guards = []
        with self.assertRaisesRegex(Hold, 'UPLOAD_ACCOUNT_GUARD_MISSING'):
            self.submit()
        self.binding['url'] = 'https://example.com/'
        with self.assertRaisesRegex(Hold, 'WRONG_DESTINATION'):
            self.submit()

    def test_pre_injection_foreground_pause_can_resume_but_unknown_injection_cannot(self):
        claim=self.queue.claim(self.submit()['request_id'])
        result={'ok':False,'request_id':claim['request_id'],'sha256':claim['sha256'],
                'phase':'NOT_STARTED','code':'HELPER_ERROR','detail':'FOREGROUND_TAB_PAUSED'}
        self.queue.complete(claim['request_id'],claim['lease'],result)
        retry=self.submit()
        self.assertEqual(retry['status'],'PENDING')
        self.assertEqual(retry['previous_attempts'][0]['result'],result)
        second=self.queue.claim(retry['request_id'])
        self.queue.complete(second['request_id'],second['lease'],dict(result,phase='OUTCOME_UNKNOWN'))
        self.assertEqual(self.submit()['status'],'OUTCOME_UNKNOWN')

    def test_media_lease_and_hash_are_checked_at_read_time(self):
        claim = self.queue.claim(self.submit()['request_id'])
        with self.assertRaisesRegex(Hold, 'UPLOAD_LEASE_INVALID'):
            self.queue.media(claim['request_id'], 'wrong')
        self.media.write_bytes(b'tampered')
        with self.assertRaisesRegex(Hold, 'MEDIA_HASH_CHANGED'):
            self.queue.media(claim['request_id'], claim['lease'])

    def test_lost_lease_survives_restart_and_late_ack_reconciles(self):
        claim = self.queue.claim(self.submit()['request_id'])
        self.clock[0] += 46
        restarted = UploadQueue(self.directory, now=lambda: self.clock[0])
        self.assertIsNone(restarted.next())
        self.assertEqual(restarted.load(claim['request_id'])['status'], 'OUTCOME_UNKNOWN')
        result = self.success(claim)
        self.assertEqual(restarted.complete(claim['request_id'], claim['lease'], result)['status'], 'DONE')
        self.assertEqual(restarted.complete(claim['request_id'], claim['lease'], result)['status'], 'DONE')
        self.assertIsNone(restarted.next())
        with self.assertRaisesRegex(Hold, 'UPLOAD_RECEIPT_CHANGED'):
            restarted.complete(claim['request_id'], claim['lease'], {**result, 'extra': 'changed'})

    def test_uncertain_events_never_become_retryable(self):
        claim = self.queue.claim(self.submit()['request_id'])
        result = {'ok': False, 'request_id': claim['request_id'], 'sha256': claim['sha256'],
                  'phase': 'FILE_ASSIGNMENT_ATTEMPTED', 'code': 'fixture failure'}
        self.assertEqual(self.queue.complete(claim['request_id'], claim['lease'], result)['status'], 'OUTCOME_UNKNOWN')
        self.assertIsNone(self.queue.next())
        with self.assertRaisesRegex(Hold, 'UPLOAD_NOT_CLAIMABLE'):
            self.queue.claim(claim['request_id'])

    def test_bad_receipt_does_not_mark_done(self):
        claim = self.queue.claim(self.submit()['request_id'])
        result = self.success(claim)
        for change in [{'sha256': '0' * 64}, {'phase': 'HASH_VERIFIED'}, {'size': 0}, {'name': 'other.png'}]:
            with self.assertRaisesRegex(Hold, 'UPLOAD_RECEIPT_INVALID'):
                self.queue.complete(claim['request_id'], claim['lease'], {**result, **change})
        self.assertEqual(self.queue.load(claim['request_id'])['status'], 'RUNNING')

    def test_shutdown_cancels_unclaimed_work_and_never_requeues_a_running_lease(self):
        value=self.submit(); self.queue.cancel(value['request_id'])
        self.assertIsNone(self.queue.next())
        self.assertEqual(self.queue.load(value['request_id'])['status'],'CANCELLED')
        self.submit(); claim=self.queue.claim(value['request_id']); self.queue.cancel(value['request_id'])
        self.assertIsNone(self.queue.next())
        self.assertEqual(self.submit()['status'],'OUTCOME_UNKNOWN')
        self.assertEqual(self.queue.complete(claim['request_id'],claim['lease'],self.success(claim))['status'],'DONE')

    def test_expired_pending_needs_explicit_preparation_before_requeue(self):
        request_id = self.submit()['request_id']
        self.clock[0] += 181
        self.assertIsNone(self.queue.next())
        self.assertEqual(self.queue.load(request_id)['status'], 'EXPIRED')
        self.assertEqual(self.submit()['status'], 'PENDING')


class UploadHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.config = {'version': VERSION, 'extension_id': 'a' * 32, 'token': 'b' * 64, 'port': 8768}
        self.server = UploadServer(self.directory, config=self.config, port=0).start()
        self.addCleanup(self.server.close)
        self.base = 'http://127.0.0.1:' + str(self.server.port)

    def request(self, path, data=None, headers=None, method=None):
        actual = {'Authorization': 'Bearer ' + self.config['token']}
        if data is not None:
            actual['Content-Type'] = 'application/json'
        actual.update(headers or {})
        request = urllib.request.Request(self.base + path, data=None if data is None else json.dumps(data).encode(), headers=actual, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return response.status, response.headers, json.loads(raw) if raw else None

    def test_auth_host_and_origin_are_restricted(self):
        for headers in [{'Authorization': ''}, {'Authorization': 'Bearer wrong'}, {'Origin': 'https://business.facebook.com'}, {'Host': 'localhost:' + str(self.server.port)}]:
            status, _, _ = self.request('/health', headers=headers)
            self.assertEqual(status, 403)
        status, headers, body = self.request('/health', headers={'Origin': self.server.origin})
        self.assertEqual(status, 200)
        self.assertEqual(headers['Access-Control-Allow-Origin'], self.server.origin)
        self.assertFalse(body['publish_actions'])
        self.assertEqual(body['bind'], '127.0.0.1')

    def test_no_enqueue_publish_or_arbitrary_path_api(self):
        for path in ['/enqueue', '/publish', '/media/../../secret', '/media/%2e%2e%2fsecret']:
            status, _, _ = self.request(path, data={'path': '/etc/passwd', 'version': VERSION})
            self.assertEqual(status, 404)
        status, _, body = self.request('/media/../../secret')
        self.assertEqual(status, 409)
        self.assertEqual(body['code'], 'UPLOAD_REQUEST_ID_INVALID')

    def test_preflight_and_hello_identity(self):
        status, _, _ = self.request('/health', method='OPTIONS', headers={'Origin': 'https://evil.example'})
        self.assertEqual(status, 403)
        status, headers, _ = self.request('/health', method='OPTIONS', headers={'Origin': self.server.origin})
        self.assertEqual(status, 204)
        self.assertIn('Authorization', headers['Access-Control-Allow-Headers'])
        status, _, _ = self.request('/hello', data={'version': VERSION, 'extension_id': 'c' * 32})
        self.assertEqual(status, 409)
        status, _, _ = self.request('/hello', data={'version': VERSION, 'extension_id': self.config['extension_id']})
        self.assertEqual(status, 200)
        status, _, body = self.request('/health')
        self.assertEqual(body['helper']['extension_id'], self.config['extension_id'])
        self.assertNotIn('token', json.dumps(body))

    def test_http_cannot_claim_missing_or_invalid_request(self):
        for request_id in ['bad', 'f' * 32]:
            status, _, _ = self.request('/claim/' + request_id, data={'version': VERSION})
            self.assertEqual(status, 409)

    def test_client_reuses_only_authenticated_matching_server(self):
        atomic_json(self.directory/'upload-helper.json',{**self.config,'port':self.server.port})
        client=UploadClient(self.directory)
        self.assertEqual(client.ensure_server()['extension_id'],self.config['extension_id'])
        client.close()
        self.assertEqual(client.health()['version'],VERSION)
        atomic_json(self.directory/'upload-helper.json',{**self.config,'port':self.server.port,'token':'c'*64})
        with self.assertRaisesRegex(Hold,'authenticated local bridge'):
            UploadClient(self.directory).ensure_server()


class HelperBuildTests(unittest.TestCase):
    def test_bundle_is_stable_private_and_has_only_reviewed_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            first=build_helper(directory); second=build_helper(directory)
            self.assertEqual(first['extension_id'],second['extension_id'])
            bundle=Path(first['bundle'])
            manifest=json.loads((bundle/'manifest.json').read_text())
            self.assertEqual(set(manifest['permissions']),{'scripting','alarms','storage'})
            self.assertEqual(set(manifest['host_permissions']),{'https://business.facebook.com/*','https://www.linkedin.com/*','http://127.0.0.1/*'})
            config=Path(directory)/'upload-helper.json'
            self.assertEqual(config.stat().st_mode & 0o777,0o600)
            self.assertNotIn(json.loads(config.read_text())['token'],json.dumps(first))
            self.assertFalse(first['installed'])


if __name__ == '__main__':
    unittest.main()
