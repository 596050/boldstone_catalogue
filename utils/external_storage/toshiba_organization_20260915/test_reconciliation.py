import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import organize
import reconcile
import registry


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.here = base / 'records'; self.here.mkdir()
        self.mount = base / 'volume'; self.mount.mkdir()
        source = self.mount / 'marketmaker/data/prices'
        source.mkdir(parents=True)
        (source / 'source.csv').write_bytes(b'time,price\n1,5\n')
        (source / 'empty').mkdir()
        (self.mount / 'marketmaker_v2').mkdir()
        (self.mount / 'other_data').mkdir()
        st = (source / 'source.csv').stat()
        census = self.here / 'census_repaired'; census.mkdir()
        with gzip.open(census / 'FILES.jsonl.gz', 'wt') as out:
            out.write(json.dumps({'path': 'marketmaker/data/prices/source.csv', 'bytes': st.st_size,
                                  'mtime_ns': st.st_mtime_ns, 'inode': st.st_ino}) + '\n')
        with gzip.open(census / 'DIRECTORIES.jsonl.gz', 'wt') as out:
            for name in ['marketmaker', 'marketmaker/data', 'marketmaker/data/prices', 'marketmaker/data/prices/empty', 'marketmaker_v2']:
                out.write(json.dumps({'path': name}) + '\n')
        action = {'source': 'marketmaker/data/prices', 'target': 'raw_price_data/prices', 'category': 'test'}
        (self.here / 'PLAN.json').write_text(json.dumps({'actions': [action]}))
        state = self.here / 'execution'; state.mkdir()
        organize.move_one(action, state, mount=self.mount)
        for module in [reconcile, registry]:
            for attr, value in [('HERE', self.here), ('MOUNT', self.mount)]:
                patcher = patch.object(module, attr, value)
                patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(reconcile, 'validate_volume')
        patcher.start(); self.addCleanup(patcher.stop)

    def test_exact_accounting_then_only_empty_marketmaker_removed(self):
        reconcile.audit()
        reconcile.cleanup()
        self.assertFalse((self.mount / 'marketmaker').exists())
        self.assertTrue((self.mount / 'marketmaker_v2').is_dir())
        self.assertEqual((self.mount / 'raw_price_data/prices/source.csv').read_bytes(), b'time,price\n1,5\n')

    def test_missing_destination_file_blocks_cleanup(self):
        (self.mount / 'raw_price_data/prices/source.csv').unlink()
        with self.assertRaises(SystemExit): reconcile.audit()
        with self.assertRaises(RuntimeError): reconcile.cleanup()
        self.assertTrue((self.mount / 'marketmaker').exists())

    def test_new_hidden_file_prevents_root_removal(self):
        reconcile.audit()
        (self.mount / 'marketmaker/.new-writer').write_bytes(b'retain')
        with self.assertRaises(OSError): reconcile.cleanup()
        self.assertEqual((self.mount / 'marketmaker/.new-writer').read_bytes(), b'retain')

    def test_missing_original_empty_directory_blocks_cleanup(self):
        (self.mount / 'raw_price_data/prices/empty').rmdir()
        with self.assertRaises(SystemExit): reconcile.audit()
        with self.assertRaises(RuntimeError): reconcile.cleanup()


if __name__ == '__main__': unittest.main()
