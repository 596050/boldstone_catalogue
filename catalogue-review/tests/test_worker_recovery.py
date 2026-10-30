"""Worker and HTTP failure regressions. No live Dropbox calls."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import test_background_jobs as fixtures
from dropbox_sync import DropboxSync
from server import Handler
from test_deletions import TARGET


def dead_thread(service):
    old = threading.Thread(target=lambda: None)
    old.start(); old.join()
    service.thread = old
    return old


def wait_until(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Worker did not reach expected state')


class NativeWorkerRecoveryTests(unittest.TestCase):
    setUp = fixtures.BackgroundJobTests.setUp

    def tearDown(self):
        self.jobs.stop()
        if self.jobs.thread:
            self.jobs.thread.join(5)
            self.assertFalse(self.jobs.thread.is_alive())
        fixtures.BackgroundJobTests.tearDown(self)

    def queued(self):
        plan = self.manager.prepare({'asset_id': TARGET, 'reason': 'unwanted'})
        return self.jobs.enqueue_deletion({'operation_id': plan['operation_id'],
                                          'confirm_file_id': TARGET, 'confirmed': True})

    def test_dead_worker_resumes_a_confirmed_queue_exactly_once(self):
        job = self.queued(); dead_thread(self.jobs)
        with ThreadPoolExecutor(max_workers=10) as readers:
            list(readers.map(lambda _: self.jobs.snapshot(), range(20)))
        wait_until(lambda: self.jobs.get(job['id'])['state'] == 'completed')
        self.assertEqual(self.client.calls, [(TARGET, 'a1')])
        self.assertEqual(self.jobs.worker_status()['restart_count'], 1)

    def test_revival_never_replays_an_interrupted_mutation(self):
        job = self.queued(); self.jobs.mark(job['id'], 'running', {})
        dead_thread(self.jobs); self.jobs.snapshot()
        wait_until(lambda: self.jobs.get(job['id'])['state'] == 'uncertain')
        self.assertEqual(self.client.calls, [])

    def test_stopped_service_cannot_start_a_queued_mutation(self):
        job = self.queued(); old = dead_thread(self.jobs)
        self.jobs.stop(); self.jobs.start()
        self.assertFalse(self.jobs.step())
        self.assertIs(self.jobs.thread, old)
        self.assertEqual(self.jobs.snapshot()['worker']['state'], 'stopped')
        self.assertEqual(self.jobs.get(job['id'])['state'], 'queued')
        self.assertEqual(self.client.calls, [])

    def test_local_outage_is_visible_and_clears_after_recovery(self):
        seen = []
        def wake(_):
            seen.append(self.jobs.snapshot()['worker'])
            if len(seen) == 2: self.jobs.stop()
        with patch.object(self.jobs, 'step', side_effect=[sqlite3.OperationalError('disk I/O error'), False]), \
             patch.object(self.jobs.wake, 'wait', side_effect=wake):
            self.jobs.loop()
        self.assertEqual(seen[0]['state'], 'retrying')
        self.assertIn('disk I/O error', seen[0]['error'])
        self.assertEqual(seen[1]['error'], '')
        self.assertEqual(self.client.calls, [])


class SyncWorkerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        python = self.root / 'application/.venv/bin/python'
        python.parent.mkdir(parents=True); python.touch()
        self.app = NS(store=NS(root=self.root), catalogue=NS(project=self.root, assets={}, source={}),
                      catalogue_lock=threading.RLock())
        self.sync = DropboxSync(self.app, interval=.01)

    def tearDown(self):
        self.sync.stop()
        if self.sync.thread:
            self.sync.thread.join(5)
            self.assertFalse(self.sync.thread.is_alive())
        self.temp.cleanup()

    def test_poll_and_check_now_restart_a_dead_thread_only_once(self):
        dead_thread(self.sync)
        entered, release = threading.Event(), threading.Event()
        def loop():
            entered.set(); release.wait(5)
        with patch.object(self.sync, 'loop', side_effect=loop) as run:
            try:
                with ThreadPoolExecutor(max_workers=10) as readers:
                    list(readers.map(lambda i: self.sync.request() if i % 2 else self.sync.snapshot(), range(20)))
                self.assertTrue(entered.wait(1))
                self.assertEqual(run.call_count, 1)
                self.assertTrue(self.sync.snapshot()['worker']['alive'])
            finally:
                self.sync.stop(); release.set()

    def test_stopped_refresh_cannot_be_restarted(self):
        old = dead_thread(self.sync); self.sync.stop()
        self.sync.start(); self.sync.request()
        self.assertIs(self.sync.thread, old)
        self.assertEqual(self.sync.snapshot()['worker']['state'], 'stopped')

    def test_disabled_refresh_does_not_start_a_worker(self):
        self.sync.status['enabled'] = False
        old = dead_thread(self.sync)
        self.sync.request(); self.sync.start()
        self.assertIs(self.sync.thread, old)
        self.assertFalse(self.sync.snapshot()['worker']['alive'])

    def test_cleanup_failure_keeps_retrying_without_losing_the_child(self):
        child = Mock(returncode=None)
        child.poll.return_value = None
        child.communicate.side_effect = subprocess.TimeoutExpired('fake', 300)
        child.kill.side_effect = OSError('temporary process cleanup failure')
        with patch('dropbox_sync.subprocess.Popen', return_value=child), \
             patch.object(self.sync.wake, 'wait', side_effect=lambda _: self.sync.stop_event.set()):
            self.sync.loop()
        self.assertIs(self.sync.process, child)
        self.assertEqual(self.sync.status['state'], 'error')
        self.assertIn('cleanup', self.sync.status['error'])

    def test_unreaped_child_prevents_launching_another_refresh(self):
        child = Mock(); child.poll.return_value = None
        child.kill.side_effect = OSError('cannot stop yet')
        self.sync.process = child
        with patch('dropbox_sync.subprocess.Popen') as spawn:
            with self.assertRaises(OSError): self.sync.check_once()
        spawn.assert_not_called()
        self.assertIs(self.sync.process, child)

    def test_cleanup_wait_is_bounded_and_process_is_released_after_reaping(self):
        child = Mock(); child.poll.return_value = None
        self.sync.process = child
        self.sync.cleanup_process()
        child.kill.assert_called_once()
        child.communicate.assert_called_once_with(timeout=5)
        self.assertIsNone(self.sync.process)

    def test_cleanup_timeout_retains_handle_until_later_success(self):
        child = Mock(); child.poll.return_value = None
        child.communicate.side_effect = [subprocess.TimeoutExpired('fake', 5), ('', '')]
        self.sync.process = child
        with self.assertRaises(subprocess.TimeoutExpired): self.sync.cleanup_process()
        self.assertIs(self.sync.process, child)
        self.sync.cleanup_process()
        self.assertIsNone(self.sync.process)
        self.assertTrue(all(c.kwargs == {'timeout': 5} for c in child.communicate.call_args_list))

    def test_child_exits_between_poll_and_kill_is_still_reaped(self):
        child = Mock(); child.poll.return_value = None
        child.kill.side_effect = ProcessLookupError('already gone')
        self.sync.process = child
        self.sync.cleanup_process()
        child.communicate.assert_called_once_with(timeout=5)
        self.assertIsNone(self.sync.process)

    def test_shutdown_survives_child_already_exiting(self):
        child = Mock(); child.poll.return_value = None
        child.terminate.side_effect = ProcessLookupError('already gone')
        self.sync.process = child
        self.sync.stop()
        self.assertTrue(self.sync.stop_event.is_set())

    def test_shutdown_during_spawn_still_stops_the_new_child(self):
        spawning, release, finishing = threading.Event(), threading.Event(), threading.Event()
        child = Mock(returncode=0); child.poll.return_value = None
        child.communicate.side_effect = lambda **_: (finishing.wait(5) and '{}', '')
        child.terminate.side_effect = finishing.set
        def spawn(*args, **kwargs):
            spawning.set(); release.wait(5); return child
        with patch('dropbox_sync.subprocess.Popen', side_effect=spawn), \
             patch('dropbox_sync.read_inventory', return_value={'generation': 7}), \
             patch.object(self.sync, 'install'):
            checker = threading.Thread(target=self.sync.check_once); checker.start()
            self.assertTrue(spawning.wait(1))
            stopper = threading.Thread(target=self.sync.stop); stopper.start()
            release.set(); stopper.join(2); finishing.set(); checker.join(2)
        self.assertFalse(stopper.is_alive()); self.assertFalse(checker.is_alive())
        child.terminate.assert_called_once()

    def test_successful_refresh_preserves_inventory_install_and_clears_child(self):
        child = Mock(returncode=0)
        child.communicate.return_value = ('{}', '')
        with patch('dropbox_sync.subprocess.Popen', return_value=child) as spawn, \
             patch('dropbox_sync.read_inventory', return_value={'generation': 7}), \
             patch.object(self.sync, 'install') as install:
            self.sync.check_once()
        spawn.assert_called_once(); install.assert_called_once_with({'generation': 7})
        self.assertIsNone(self.sync.process)

    def test_status_exposes_retry_deadline_without_bypassing_it(self):
        self.sync.retry_at = time.time() + 300
        self.sync.status.update(state='error', error='Dropbox requested a delay')
        status = self.sync.request()
        self.assertEqual(status['retry_at'], self.sync.retry_at)
        self.assertIsNone(self.sync.thread)


class HTTPLoggingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.app = NS(token='test-only', catalogue_lock=threading.RLock(),
                      catalogue=NS(products={}), jobs=NS(snapshot=Mock(return_value={'jobs': []})),
                      deletion_reviews=NS(start_review=Mock(return_value={'id': 'test-review', 'state': 'queued'})),
                      save=Mock(side_effect=sqlite3.OperationalError('disk I/O error')))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.app = self.app; self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)

    def request(self, path, body=None):
        request = urllib.request.Request('http://127.0.0.1:' + str(self.server.server_port) + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type': 'application/json', 'X-Review-Token': 'test-only'})
        try: response = urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as error: response = error
        with response:
            return response.status, json.load(response)

    def test_failed_access_log_does_not_lose_a_committed_review_response(self):
        with patch.object(BaseHTTPRequestHandler, 'log_message', side_effect=OSError('log unavailable')):
            status, body = self.request('/api/deletion-reviews', {'request_id': 'test-review'})
        self.assertEqual(status, 202)
        self.assertEqual(body['id'], 'test-review')
        self.app.deletion_reviews.start_review.assert_called_once()

    def test_failed_traceback_and_access_logs_still_return_json_error(self):
        with patch('traceback.print_exc', side_effect=OSError('log unavailable')), \
             patch.object(BaseHTTPRequestHandler, 'log_message', side_effect=OSError('log unavailable')):
            status, body = self.request('/api/reviews', {})
        self.assertEqual(status, 500); self.assertIn('error', body)
        self.assertNotIn('previous saved decisions are intact', body['error'])
        self.app.save.assert_called_once()

    def test_failed_status_read_returns_retryable_json_instead_of_closed_connection(self):
        self.app.jobs.snapshot.side_effect = sqlite3.OperationalError('disk I/O error')
        with patch('traceback.print_exc', side_effect=OSError('log unavailable')), \
             patch.object(BaseHTTPRequestHandler, 'log_message', side_effect=OSError('log unavailable')):
            status, body = self.request('/api/jobs')
        self.assertEqual(status, 503); self.assertTrue(body['retryable'])

    def test_one_argument_log_message_is_supported(self):
        handler = Handler.__new__(Handler)
        with patch.object(BaseHTTPRequestHandler, 'log_message') as log:
            handler.log_message('Message: %s', 'a diagnostic')
        log.assert_called_once()


if __name__ == '__main__':
    unittest.main()
