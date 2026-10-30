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


if __name__ == '__main__': unittest.main()
