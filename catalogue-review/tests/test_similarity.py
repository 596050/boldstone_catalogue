from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
import json
import tempfile
import unittest

from similarity import Similarity
from projection import Projection


class SimilarityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.photo = self.root / 'photo.png'
        self.photo.write_bytes(b'preview')
        self.cat = SimpleNamespace(assets={'A': {'original': {'dropbox_content_hash': 'one'}}, 'B': {}},
                                   paths={'A': (self.photo, 'preview')}, preview_paths={}, edges={}, products={})
        self.view = Projection(self.cat, [])
        with patch('similarity.ThreadPoolExecutor') as pool:
            self.pool = pool.return_value
            self.service = Similarity(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_repeated_request_reuses_job_but_new_bytes_and_content_hash_invalidate(self):
        body = {'groups': [['A', 'B']]}
        first = self.service.start(body, self.view)
        self.assertEqual(first, self.service.start(body, self.view))
        self.assertEqual(self.pool.submit.call_count, 1)
        self.cat.assets['A']['original']['dropbox_content_hash'] = 'changed'
        second = self.service.start(body, self.view)
        self.assertNotEqual(first['job_id'], second['job_id'])
        self.photo.write_bytes(b'new preview bytes')
        third = self.service.start(body, self.view)
        self.assertNotEqual(second['job_id'], third['job_id'])

    def test_missing_preview_stays_in_job_and_client_paths_are_never_used(self):
        self.service.start({'groups': [['A', 'B']], 'path': '/etc/passwd'}, self.view)
        request = self.pool.submit.call_args.args[2]
        self.assertEqual(request['groups'][0][0]['path'], str(self.photo))
        self.assertIsNone(request['groups'][0][1]['path'])

    def test_invalid_duplicate_and_deleted_images_rejected(self):
        for body in ({'groups': []}, {'groups': [[]]}, {'groups': [['A'], ['A']]},
                     {'groups': [['unknown']]}, {'groups': [[None]]}, {'groups': [['A']], 'reverse': 'yes'}):
            with self.assertRaises(ValueError): self.service.start(body, self.view)
        self.view.deleted['A'] = {}
        with self.assertRaises(ValueError): self.service.start({'groups': [['A']]}, self.view)

    def test_corrupt_cached_result_cannot_drop_images(self):
        job = self.service.start({'groups': [['A', 'B']]}, self.view)
        request = self.pool.submit.call_args.args[2]
        (self.service.root / (job['job_id'] + '.result.json')).write_text(json.dumps({'order': ['A']}))
        with patch('similarity.subprocess.run', side_effect=OSError('Worker temporarily unavailable')):
            self.service._run(job['job_id'], request)
        self.assertEqual(self.service.status(job['job_id'])['state'], 'error')
        self.assertEqual(set(self.cat.assets), {'A', 'B'})

    def test_reuse_valid_complete_order_and_leave_source_untouched(self):
        job = self.service.start({'groups': [['A', 'B']]}, self.view)
        request = self.pool.submit.call_args.args[2]
        result = {'order': ['A', 'B'], 'missing_ids': ['B'], 'total': 2, 'analysed': 1}
        (self.service.root / (job['job_id'] + '.result.json')).write_text(json.dumps(result))
        self.service._run(job['job_id'], request)
        self.assertEqual(self.service.status(job['job_id'])['state'], 'ready')
        self.assertEqual(self.photo.read_bytes(), b'preview')

    def test_damaged_cached_results_are_rebuilt_instead_of_poisoning_retries(self):
        valid = {'order': ['A', 'B'], 'missing_ids': ['B'], 'total': 2, 'analysed': 1}
        damaged = ['{"order":', 'null', '[]', json.dumps({'order': ['A', 'B']}),
                   json.dumps({**valid, 'missing_ids': ['unknown']}),
                   json.dumps({**valid, 'analysed': 2}),
                   json.dumps({**valid, 'total': True}),
                   json.dumps({**valid, 'order': ['B', 'A']})]
        self.service.binary.write_bytes(b'fake worker - subprocess mocked')
        for content in damaged:
            with self.subTest(content=content):
                self.service.jobs.clear()
                job = self.service.start({'groups': [['A', 'B']]}, self.view)
                request = self.pool.submit.call_args.args[2]
                result = self.service.root / (job['job_id'] + '.result.json')
                result.write_text(content)
                def worker(*args, **kwargs):
                    result.write_text(json.dumps(valid))
                with patch('similarity.subprocess.run', side_effect=worker) as run:
                    self.service._run(job['job_id'], request)
                self.assertEqual(self.service.status(job['job_id'])['state'], 'ready')
                run.assert_called_once()
                self.assertEqual(json.loads(result.read_text()), valid)
        self.assertEqual(self.photo.read_bytes(), b'preview')

    def test_cached_order_cannot_cross_groups_from_earlier_sort_rules(self):
        job = self.service.start({'groups': [['A'], ['B']]}, self.view)
        request = self.pool.submit.call_args.args[2]
        result = self.service.root / (job['job_id'] + '.result.json')
        result.write_text(json.dumps({'order': ['B', 'A'], 'missing_ids': [], 'total': 2, 'analysed': 2}))
        self.service.binary.write_bytes(b'fake worker - subprocess mocked')
        correct = {'order': ['A', 'B'], 'missing_ids': [], 'total': 2, 'analysed': 2}
        with patch('similarity.subprocess.run', side_effect=lambda *a, **k: result.write_text(json.dumps(correct))) as run:
            self.service._run(job['job_id'], request)
        run.assert_called_once()
        self.assertEqual(self.service.status(job['job_id'])['order'], ['A', 'B'])

    def test_bad_worker_output_is_discarded_and_a_later_retry_can_succeed(self):
        job = self.service.start({'groups': [['A', 'B']]}, self.view)
        request = self.pool.submit.call_args.args[2]
        result = self.service.root / (job['job_id'] + '.result.json')
        self.service.binary.write_bytes(b'fake worker - subprocess mocked')
        with patch('similarity.subprocess.run', side_effect=lambda *a, **k: result.write_text('{')) as run:
            self.service._run(job['job_id'], request)
        run.assert_called_once()
        self.assertEqual(self.service.status(job['job_id'])['state'], 'error')
        self.assertFalse(result.exists())
        retried = self.service.start({'groups': [['A', 'B']]}, self.view)
        self.assertEqual(retried['state'], 'queued')
        correct = {'order': ['A', 'B'], 'missing_ids': ['B'], 'total': 2, 'analysed': 1}
        with patch('similarity.subprocess.run', side_effect=lambda *a, **k: result.write_text(json.dumps(correct))):
            self.service._run(job['job_id'], self.pool.submit.call_args.args[2])
        self.assertEqual(self.service.status(job['job_id'])['state'], 'ready')

    def test_bad_progress_does_not_break_status_or_replace_job_identity(self):
        job = self.service.start({'groups': [['A', 'B']]}, self.view)
        self.service.jobs[job['job_id']]['state'] = 'running'
        progress = self.service.root / (job['job_id'] + '.status.json')
        for content in ['null', '[]', '{', '{"phase":"ordering","completed":99,"total":99}']:
            with self.subTest(content=content):
                progress.write_text(content)
                status = self.service.status(job['job_id'])
                self.assertEqual(status['state'], 'running')
                self.assertEqual(status['total'], 2)
                self.assertNotIn('phase', status)
        progress.write_text(json.dumps({'phase': 'analysing', 'completed': 1, 'total': 2,
                                        'state': 'ready', 'job_id': 'wrong'}))
        status = self.service.status(job['job_id'])
        self.assertEqual(status['state'], 'running')
        self.assertEqual(status['job_id'], job['job_id'])
        self.assertEqual(status['completed'], 1)

    def test_valid_order_cannot_replace_job_identity_with_cached_metadata(self):
        job = self.service.start({'groups': [['A', 'B']]}, self.view)
        request = self.pool.submit.call_args.args[2]
        result = self.service.root / (job['job_id'] + '.result.json')
        result.write_text(json.dumps({'order': ['A', 'B'], 'missing_ids': ['B'], 'total': 2, 'analysed': 1,
                                      'job_id': 'another-job', 'error': 'stale failure'}))
        with patch('similarity.subprocess.run') as run:
            self.service._run(job['job_id'], request)
        run.assert_not_called()
        status = self.service.status(job['job_id'])
        self.assertEqual(status['job_id'], job['job_id'])
        self.assertEqual(status['state'], 'ready')
        self.assertNotIn('error', status)

    def test_retry_clears_old_progress_before_launching_worker(self):
        job = self.service.start({'groups': [['A', 'B']]}, self.view)
        request = self.pool.submit.call_args.args[2]
        result = self.service.root / (job['job_id'] + '.result.json')
        progress = self.service.root / (job['job_id'] + '.status.json')
        progress.write_text(json.dumps({'phase': 'ordering', 'completed': 2, 'total': 2}))
        self.service.binary.write_bytes(b'fake worker - subprocess mocked')
        def worker(*args, **kwargs):
            self.assertNotIn('phase', self.service.status(job['job_id']))
            result.write_text(json.dumps({'order': ['A', 'B'], 'missing_ids': ['B'], 'total': 2, 'analysed': 1}))
        with patch('similarity.subprocess.run', side_effect=worker):
            self.service._run(job['job_id'], request)
        self.assertEqual(self.service.status(job['job_id'])['state'], 'ready')


if __name__ == '__main__': unittest.main()
