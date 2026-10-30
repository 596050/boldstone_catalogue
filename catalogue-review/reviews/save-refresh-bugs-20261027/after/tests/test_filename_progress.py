from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import os
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from filename_progress import FilenameProgress


class FilenameProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.root = Path(self.temp.name)
        self.runtime = self.root / 'runtime'; self.job = self.root / 'rename'
        self.batch = self.job / 'bulk-operations/001'; self.batch.mkdir(parents=True); self.runtime.mkdir()
        self.folder = {'id': 'folder', 'kind': 'folder', 'path': '/Wall/A/A White', 'name': 'A White'}
        self.rows = [{'id': str(i), 'kind': 'file', 'parent_id': 'folder', 'path': f'/Wall/A/A White/old{i}.jpg',
                      'name': f'old{i}.jpg', 'size': i+1, 'content_hash': 'hash'+str(i)} for i in range(3)]
        self.rows[0].update(path='/Wall/A/A White/new0.jpg', name='new0.jpg')
        self.manifest = {'created_at': '2026-10-26T20:00:00+00:00', 'counts': {'files': 3, 'renames': 2},
                         'groups': [{'parent': self.folder, 'files': [{**r, 'new_name': f'new{i}.jpg',
                                  'new_path': f'/Wall/A/A White/new{i}.jpg'} for i, r in enumerate(self.rows)]}]}
        self.put(self.job/'manifest.json', self.manifest)
        self.reservation = {'active': True, 'label': 'Dropbox filename renaming', 'root': str(self.job),
                            'updated_at': '2026-10-26T20:00:00+00:00'}
        self.put(self.runtime/'native-writer-reservation.json', self.reservation)
        self.put(self.batch/'before.json', self.inventory(self.rows))
        self.intent = {'at': '2026-10-26T20:01:00+00:00', 'manifest_sha256': self.sha(self.job/'manifest.json'),
                       'before_sha256': self.sha(self.batch/'before.json'), 'moves': [{'id': '1'}, {'id': '2'}]}
        self.put(self.batch/'intent.json', self.intent)
        self.put(self.batch/'submission.json', {'at': '2026-10-26T20:01:00+00:00', 'async_job_id': 'private-job-id'})
        self.progress = FilenameProgress(self.runtime)

    def tearDown(self): self.temp.cleanup()
    def put(self, p, v): p.write_text(json.dumps(v))
    def sha(self, p): return hashlib.sha256(p.read_bytes()).hexdigest()
    def inventory(self, rows):
        return {'recorded_utc': '2026-10-26T20:01:00+00:00',
                'wall': {'entries': [self.folder, *rows], 'pagination_exhausted': True},
                'workshop': {'entries': [], 'pagination_exhausted': True}}

    def test_submitted_batch_does_not_increase_verified_progress(self):
        v = self.progress.read(); self.assertEqual((v['correct'], v['total'], v['batch_files']), (1, 3, 2))
        self.assertEqual(v['percent'], 33.3); self.assertEqual(v['batch_state'], 'processing')
        self.assertNotIn('private-job-id', json.dumps(v))
        self.assertEqual(len(list(self.batch.iterdir())), 3)  # no receipts or mutation from the reader

    def test_only_verified_after_snapshot_advances_count(self):
        rows = [{**r, 'name': f'new{i}.jpg', 'path': f'/Wall/A/A White/new{i}.jpg'} for i, r in enumerate(self.rows)]
        self.put(self.batch/'after.json', self.inventory(rows))
        self.assertEqual(self.progress.read()['correct'], 1)
        self.put(self.batch/'verified.json', {'manifest_sha256': self.intent['manifest_sha256'], 'after_sha256': self.sha(self.batch/'after.json')})
        v = self.progress.read(); self.assertEqual(v['correct'], 3)
        self.assertEqual(v['batch_state'], 'verified'); self.assertEqual(v['state'], 'running')

    def test_terminal_receipt_is_still_being_verified(self):
        self.put(self.batch/'terminal.json', {'results': [{'state': 'success'}]*2})
        v = self.progress.read(); self.assertEqual(v['stage'], 'Checking the completed batch')
        self.assertEqual(v['correct'], 1)

    def test_changed_membership_is_deferred_not_marked_complete(self):
        self.put(self.batch/'before.json', self.inventory(self.rows[:2]))
        self.intent['before_sha256'] = self.sha(self.batch/'before.json'); self.put(self.batch/'intent.json', self.intent)
        v = self.progress.read(); self.assertEqual(v['correct'], 0)
        self.assertEqual(v['deferred_folders'], 1); self.assertEqual(v['deferred_files'], 3)

    def test_corrupt_receipt_returns_unavailable_without_clearing_reservation(self):
        self.intent['before_sha256'] = 'bad'; self.put(self.batch/'intent.json', self.intent)
        self.assertEqual(self.progress.read()['state'], 'unavailable')
        self.assertTrue(json.loads((self.runtime/'native-writer-reservation.json').read_text())['active'])

    def test_incomplete_census_is_not_counted(self):
        v = self.inventory(self.rows); v['wall']['pagination_exhausted'] = False
        self.put(self.batch/'before.json', v); self.intent['before_sha256'] = self.sha(self.batch/'before.json')
        self.put(self.batch/'intent.json', self.intent)
        self.assertEqual(self.progress.read()['state'], 'unavailable')

    def test_wrong_manifest_binding_is_rejected(self):
        self.intent['manifest_sha256'] = 'other'; self.put(self.batch/'intent.json', self.intent)
        self.assertEqual(self.progress.read()['state'], 'unavailable')

    def test_followup_has_its_own_denominator(self):
        follow = self.job/'followup-01'; follow.mkdir()
        m = deepcopy(self.manifest); m['counts'] = {'files': 1, 'renames': 0}; m['groups'][0]['files'] = m['groups'][0]['files'][:1]
        self.put(follow/'manifest.json', m)
        v = self.progress.read(); self.assertEqual(v['pass_name'], 'Follow-up 1')
        self.assertEqual((v['correct'], v['total']), (1, 1)); self.assertEqual(v['state'], 'running')

    def test_final_verified_names_are_not_completed_until_queue_released(self):
        self.put(self.job/'verification.json', {'status': 'PASS', 'current_files': 2, 'at': '2026-10-26T21:00:00+00:00'})
        self.put(self.job/'completion.json', {'at': '2026-10-26T21:00:01+00:00'})
        self.assertEqual(self.progress.read()['state'], 'running')
        self.reservation['active'] = False; self.put(self.runtime/'native-writer-reservation.json', self.reservation)
        v = self.progress.read(); self.assertEqual(v['state'], 'completed')
        self.assertEqual((v['correct'], v['total'], v['percent']), (2, 2, 100))

    def test_stopped_worker_and_heartbeat_age_are_explicit(self):
        log = self.job/'completion-driver.log'; log.write_text('Pending')
        os.utime(log, (1000, 1000))
        v = self.progress.read(clock=1200); self.assertTrue(v['heartbeat_stale'])
        self.assertEqual(v['heartbeat_age_seconds'], 200)
        self.put(self.job/'completion-error.json', {'at': '2026-10-26T21:00:00+00:00'})
        v = self.progress.read(); self.assertEqual(v['state'], 'needs_review'); self.assertFalse(v['heartbeat_stale'])

    def test_missing_or_unrelated_reservation_has_no_filename_job(self):
        (self.runtime/'native-writer-reservation.json').unlink(); self.assertIsNone(self.progress.read())
        self.put(self.runtime/'native-writer-reservation.json', {'label': 'Other writer'})
        self.assertIsNone(self.progress.read())

    def test_cached_large_inventory_not_reread_on_heartbeat_updates(self):
        self.progress.read()
        original = Path.read_bytes
        def guarded(path):
            if path.name in ('manifest.json', 'before.json'): self.fail('Unchanged large evidence was re-read')
            return original(path)
        with patch.object(Path, 'read_bytes', guarded):
            (self.job/'completion-driver.log').write_text('New heartbeat')
            self.assertEqual(self.progress.read()['correct'], 1)

    def test_failed_final_checks_remain_separate_from_filename_percentage(self):
        self.put(self.job/'verification.json', {'status': 'FAIL', 'at': '2026-10-26T21:00:00+00:00',
            'errors': [{'check': 'original_shared_link_retained'}] * 6})
        value = self.progress.read()
        self.assertEqual(value['state'], 'needs_review'); self.assertEqual(value['final_checks'], 'failed')
        self.assertEqual(value['verification_errors'], [{'check': 'original_shared_link_retained', 'count': 6}])

    def test_recovered_verification_supersedes_preserved_failure_only_with_hash_binding(self):
        self.put(self.job/'verification.json', {'status': 'FAIL', 'at': '2026-10-26T21:00:00+00:00'})
        self.put(self.job/'completion-error.json', {'at': '2026-10-26T21:00:00+00:00'})
        directory = self.job/'verification-attempts/new'; directory.mkdir(parents=True)
        proof = directory/'verification.json'
        self.put(proof, {'status': 'PASS', 'at': '2026-10-27T11:00:00+00:00', 'current_files': 3})
        pointer = {'path': str(proof), 'sha256': self.sha(proof)}
        self.put(self.job/'verification-current.json', pointer)
        self.put(self.job/'completion.json', {'at': '2026-10-27T11:01:00+00:00',
            'verification': str(proof), 'verification_sha256': self.sha(proof)})
        self.reservation.update(active=False, updated_at='2026-10-27T11:01:01+00:00')
        self.put(self.runtime/'native-writer-reservation.json', self.reservation)
        value = self.progress.read()
        self.assertEqual(value['state'], 'completed'); self.assertEqual(value['final_checks'], 'passed')
        self.assertEqual(json.loads((self.job/'verification.json').read_text())['status'], 'FAIL')
        pointer['sha256'] = 'bad'; self.put(self.job/'verification-current.json', pointer)
        self.assertEqual(self.progress.read()['state'], 'unavailable')

    def test_fresh_recheck_does_not_report_old_failure_as_current(self):
        self.put(self.job/'verification.json', {'status': 'FAIL', 'at': '2026-10-26T21:00:00+00:00'})
        self.put(self.job/'completion-error.json', {'at': '2026-10-26T21:00:00+00:00'})
        self.reservation['updated_at'] = '2026-10-27T11:00:00+00:00'
        self.put(self.runtime/'native-writer-reservation.json', self.reservation)
        self.assertEqual(self.progress.read()['state'], 'running')
        self.assertEqual(self.progress.read()['final_checks'], 'pending')


if __name__ == '__main__': unittest.main()
