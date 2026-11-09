import gzip
import importlib.util
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('transfer_job', Path(__file__).with_name('transfer_job.py'))
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='storage-coverage-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        job.create_coverage_schema(self.db)

    def inventory(self, inode, size=4, mtime=123):
        return [(str(self.root / 'file'), SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600, st_size=size, st_mtime_ns=mtime, st_ino=inode))]

    def scan(self, rows, phase):
        with patch.object(job, 'inventory', return_value=iter(rows)):
            return job.census_into(self.db, [], self.root / (phase + '.gz'), phase)

    def test_unsigned_inode_round_trip_and_replacement_detection(self):
        inode = 2**64 - 1
        self.scan(self.inventory(inode), 'pre')
        self.assertEqual(self.db.execute('SELECT inode,typeof(inode) FROM entries').fetchone(), (str(inode), 'text'))
        self.scan(self.inventory(inode), 'post')
        with gzip.open(self.root / 'pre.gz', 'rt') as stream:
            self.assertEqual(json.loads(stream.readline())[-1], inode)
        with self.assertRaisesRegex(RuntimeError, 'Source changed'):
            self.scan(self.inventory(inode - 1), 'post')

    def test_empty_file_synthetic_ids_do_not_hide_size_or_time_changes(self):
        self.scan(self.inventory(2**64 - 100, size=0), 'pre')
        self.scan(self.inventory(2**64 - 110, size=0), 'post')
        self.assertIsNone(self.db.execute('SELECT inode FROM entries').fetchone()[0])
        for size, mtime in [(1, 123), (0, 124)]:
            with self.assertRaisesRegex(RuntimeError, 'Source changed'):
                self.scan(self.inventory(2**64 - 120, size=size, mtime=mtime), 'post')

    def test_missing_source_stays_unreconciled(self):
        self.scan(self.inventory(1), 'pre')
        self.scan([], 'post')
        self.assertEqual(self.db.execute('SELECT count(*) FROM entries WHERE post=0').fetchone()[0], 1)

    def test_resume_rejects_absent_mistagged_or_wrong_path_snapshots(self):
        receipt = {'plan_sha256': 'plan', 'repository_id': 'repo', 'snapshot_id': 'snapshot', 'paths': ['/source']}
        batch = {'group': 'group', 'paths': ['/source']}
        snapshot = {'paths': ['/source'], 'tags': [job.sb.COMPLETE, 'group:group']}
        job.validate_completed(receipt, batch, 'plan', 'repo', {'snapshot': snapshot})
        invalid = [{}, {'snapshot': {**snapshot, 'tags': [job.sb.PENDING]}},
                   {'snapshot': {**snapshot, 'paths': ['/wrong']}}]
        for listing in invalid:
            with self.assertRaises(RuntimeError):
                job.validate_completed(receipt, batch, 'plan', 'repo', listing)


if __name__ == '__main__':
    unittest.main()
