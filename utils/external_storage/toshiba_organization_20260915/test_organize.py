import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('organize', Path(__file__).with_name('organize.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mount = Path(self.tmp.name).resolve()
        self.source = self.mount / 'marketmaker' / 'prices'
        self.source.mkdir(parents=True)
        (self.source / 'price ü.csv').write_bytes(b'Date,Close\n2026-09-15,123.4\n')
        (self.source / '.hidden').write_bytes(b'private source metadata')
        (self.source / 'empty').touch()
        (self.source / 'empty folder').mkdir()
        self.state = self.mount / 'state'
        self.action = {'source': 'marketmaker/prices', 'target': 'raw_price_data/iqfeed'}

    def test_complete_move_and_idempotent_resume(self):
        result = mod.move_one(self.action, self.state, self.mount)
        target = self.mount / self.action['target']
        self.assertEqual(result['status'], 'VERIFIED')
        self.assertFalse(self.source.exists())
        self.assertEqual((target / 'price ü.csv').read_bytes(), b'Date,Close\n2026-09-15,123.4\n')
        self.assertEqual(result['after']['counts'], {'file': 3, 'directory': 1, 'bytes': 51})
        self.assertEqual(mod.move_one(self.action, self.state, self.mount)['status'], 'VERIFIED')

    def test_destination_collision_does_not_overwrite(self):
        target = self.mount / self.action['target']
        target.mkdir(parents=True)
        (target / 'keep').write_text('keep')
        with self.assertRaises(FileExistsError):
            mod.move_one(self.action, self.state, self.mount)
        self.assertTrue(self.source.exists())
        self.assertEqual((target / 'keep').read_text(), 'keep')

    def test_live_reader_and_new_writer_block_before_rename(self):
        blocker = {'path': str(self.source / 'price ü.csv'), 'command': 'research', 'pid': 123}
        with self.assertRaisesRegex(RuntimeError, 'blocked'):
            mod.move_one(self.action, self.state, self.mount, blockers=[blocker])
        with self.assertRaisesRegex(RuntimeError, 'New active'):
            mod.move_one(self.action, self.state, self.mount, recheck=lambda: [blocker])
        self.assertTrue(self.source.exists())

    def test_crash_after_rename_can_be_reconciled(self):
        original = mod.inventory
        def interrupted(source, output, **kwargs):
            if 'AFTER' in output.name:
                raise RuntimeError('simulated power loss after rename')
            return original(source, output, **kwargs)
        with patch.object(mod, 'inventory', side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, 'power loss'):
                mod.move_one(self.action, self.state, self.mount)
        self.assertFalse(self.source.exists())
        self.assertEqual(mod.move_one(self.action, self.state, self.mount)['status'], 'VERIFIED')

    def test_namespace_change_retains_everything_and_blocks_cleanup(self):
        original = mod.no_replace_rename
        def changed(source, target):
            original(source, target)
            (target / 'new writer output').write_text('preserve this too')
        with patch.object(mod, 'no_replace_rename', side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, 'identity differs'):
                mod.move_one(self.action, self.state, self.mount)
        target = self.mount / self.action['target']
        self.assertTrue((target / 'price ü.csv').exists())
        self.assertTrue((target / 'new writer output').exists())

    def test_unsafe_paths_and_symlinks_rejected(self):
        for path in ['../escape', '/absolute']:
            with self.assertRaises(ValueError): mod.safe_path(path, self.mount)
        alias = self.mount / 'other_data'
        alias.symlink_to(self.mount / 'marketmaker', target_is_directory=True)
        with self.assertRaises(RuntimeError): mod.safe_path('other_data/prices', self.mount)


if __name__ == '__main__':
    unittest.main()
