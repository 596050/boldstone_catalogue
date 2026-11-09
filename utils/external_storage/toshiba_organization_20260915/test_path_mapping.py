import importlib.util
import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('isolated_data_paths', REPO / 'utils/data_paths.py')
paths = importlib.util.module_from_spec(spec)
# Isolate the import-time physical mount check; all exercised functions are the
# actual source definitions. These tests must also run while storage is paused.
tree = ast.parse((REPO / 'utils/data_paths.py').read_text())
tree.body = [node for node in tree.body if not (isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'CONFIGURED_DATA_ROOT' for t in node.targets))]
exec(compile(tree, str(REPO / 'utils/data_paths.py'), 'exec'), paths.__dict__)


class PathMappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mount = Path(self.tmp.name).resolve() / 'volume'
        self.mount.mkdir()
        self.config = {
            'schema': paths.CONFIG_SCHEMA,
            'data_root': str(self.mount / 'raw_price_data'),
            'external_storage': {'mount_point': str(self.mount), 'volume_uuid': 'test-volume'},
            'physical_locations': {'data/research': 'other_data/research',
                                   'data/research/testing_stages/source_updates': 'raw_price_data/price_views/source_updates'},
            'path_relocations': {'marketmaker/data/research': 'other_data/research',
                                 'marketmaker/iqfeed_archive': 'raw_price_data/iqfeed_archive'},
            'roots': {'research': 'data/research'}, 'datasets': {},
            'source_locations': {'updates': {'root': 'research', 'relative': 'testing_stages/source_updates'}},
            'path_policy': {'allow_absolute_paths': True, 'allow_environment_override': False, 'allow_symlinks': False},
        }

    def test_nested_mapping_and_unmodified_frozen_price_layout(self):
        expected = {
            'data/ibkr/iqfeed_192_daily/AAPL.txt': 'raw_price_data/ibkr/iqfeed_192_daily/AAPL.txt',
            'data/research/artifacts/source.bin': 'other_data/research/artifacts/source.bin',
            'data/research/testing_stages/source_updates/run/prices.csv': 'raw_price_data/price_views/source_updates/run/prices.csv',
        }
        for logical, relative in expected.items():
            self.assertEqual(paths._mapped_physical_path(self.config, Path(logical)), self.mount / relative)
        self.assertEqual(paths._source_location_path(self.config, 'updates'), self.mount / 'raw_price_data/price_views/source_updates')

    def test_historical_receipt_translation_and_shadow_rejection(self):
        target = self.mount / 'raw_price_data/iqfeed_archive/minute/source.csv'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'exact source bytes')
        old = self.mount / 'marketmaker/iqfeed_archive/minute/source.csv'
        with patch.object(paths, 'load_data_paths', return_value=self.config):
            self.assertEqual(paths.resolve_relocated_path(old, require_exists=True), target)
            old.parent.mkdir(parents=True); old.write_bytes(b'unexpected shadow')
            with self.assertRaisesRegex(paths.DataPathError, 'recreated'):
                paths.resolve_relocated_path(old)

    def test_invalid_mapping_and_historical_escape_fail_closed(self):
        bad = dict(self.config, physical_locations={'data/research': '../escape'})
        with self.assertRaises(paths.DataPathConfigError): paths._validate_config(bad, verify_storage=False)
        with patch.object(paths, 'load_data_paths', return_value=self.config):
            with self.assertRaises(paths.DataPathConfigError): paths.resolve_relocated_path(self.mount / '../escape')
            with self.assertRaises(paths.DataPathConfigError): paths.resolve_data_path('../escape')
            with self.assertRaises(paths.DataPathConfigError):
                with paths.local_job_lock(self.mount / 'other_data/research/../../../escape.lock'): pass

    def test_maintenance_blocks_even_previously_verified_storage(self):
        with patch.object(paths, '_verified_storage', {'cached': True}):
            with self.assertRaisesRegex(paths.ExternalDataVolumeError, 'in progress'):
                paths._validate_external_storage({'organization': {'state': 'MIGRATING'}})

    def test_registry_refresh_and_mapped_locks(self):
        config_file = Path(self.tmp.name) / 'data_paths.json'
        config_file.write_text(json.dumps(self.config))
        with patch.object(paths, 'CONFIG_PATH', config_file):
            first = paths.load_data_paths(force_reload=True, verify_storage=False)
            self.assertEqual(first['physical_locations']['data/research'], 'other_data/research')
            altered = dict(self.config, physical_locations={'data/research': 'other_data/research-new'})
            config_file.write_text(json.dumps(altered))
            second = paths.load_data_paths(verify_storage=False)
            self.assertEqual(second['physical_locations']['data/research'], 'other_data/research-new')
        lock = self.mount / 'other_data/research/worker.lock'
        with patch.object(paths, 'load_data_paths', return_value=self.config):
            with paths.local_job_lock(lock): self.assertTrue(lock.exists())
            self.assertFalse(lock.exists())


if __name__ == '__main__': unittest.main()
