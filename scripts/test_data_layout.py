"""Exercise data preservation and broken-migration detection on disposable files."""
import csv
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from check_data_layout import check


class DataLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.target = self.root / 'data/inputs/catalogue/source.csv'
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'name,value\nPanel,1\n')
        self.legacy = self.root / 'Old source/source.csv'
        self.legacy.parent.mkdir()
        self.legacy.symlink_to('../data/inputs/catalogue/source.csv')
        self.row = {'legacy_path': 'Old source/source.csv', 'path': 'data/inputs/catalogue/source.csv',
                    'bytes': str(self.target.stat().st_size),
                    'sha256': hashlib.sha256(self.target.read_bytes()).hexdigest()}
        self.write_manifest([self.row])

    def write_manifest(self, rows):
        with (self.root / 'data/file-manifest.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['legacy_path', 'path', 'bytes', 'sha256'])
            writer.writeheader()
            writer.writerows(rows)

    def test_nested_legacy_link_and_export_preserve_bytes(self):
        self.assertEqual(check(self.root), (1, []))
        export = self.root / 'data/exports/squarespace/source.csv'
        export.parent.mkdir(parents=True)
        self.target.rename(export)
        self.legacy.unlink()
        self.legacy.symlink_to('../data/exports/squarespace/source.csv')
        self.write_manifest([{**self.row, 'path': 'data/exports/squarespace/source.csv'}])
        self.assertEqual(check(self.root), (1, []))

    def test_changed_bytes_missing_alias_and_unlisted_files_are_detected(self):
        self.target.write_bytes(b'changed')
        self.assertTrue(check(self.root)[1])
        self.legacy.unlink()
        self.assertTrue(check(self.root)[1])
        (self.target.parent / 'unlisted.csv').write_text('new')
        self.assertTrue(any('file set' in error for error in check(self.root)[1]))

    def test_truncated_manifest_returns_an_error(self):
        for raw in ('', 'legacy_path,path,bytes,sha256\n',
                    'legacy_path,path,bytes,sha256\nOld source/source.csv\n',
                    'legacy_path,path,bytes,sha256\na,b,1,hash,extra\n'):
            with self.subTest(raw=raw):
                (self.root / 'data/file-manifest.csv').write_text(raw)
                self.assertTrue(check(self.root)[1])

    def test_duplicate_records_are_not_a_complete_verification(self):
        self.write_manifest([self.row, self.row])
        self.assertTrue(any('duplicate' in error for error in check(self.root)[1]))

    def test_absolute_and_parent_paths_are_rejected(self):
        for path in (str(self.target), 'data/inputs/../inputs/catalogue/source.csv'):
            with self.subTest(path=path):
                self.write_manifest([{**self.row, 'path': path}])
                self.assertTrue(any('relative' in error for error in check(self.root)[1]))

    def test_missing_manifest_reports_failure(self):
        (self.root / 'data/file-manifest.csv').unlink()
        self.assertTrue(check(self.root)[1])

    def test_broken_extra_data_links_are_not_omitted_from_verification(self):
        (self.target.parent / 'missing.csv').symlink_to('absent.csv')
        self.assertTrue(check(self.root)[1])

    def test_directory_links_cannot_hide_unlisted_canonical_data(self):
        hidden = self.root / 'other-data'
        hidden.mkdir()
        (hidden / 'unlisted.csv').write_text('unlisted')
        (self.target.parent / 'hidden-data').symlink_to(hidden, target_is_directory=True)
        self.assertTrue(check(self.root)[1])

    def test_same_size_target_replacement_during_hashing_is_not_certified(self):
        real_sha256 = hashlib.sha256
        replacement = self.root / 'replacement.csv'
        replacement.write_bytes(b'x' * self.target.stat().st_size)
        target = self.target

        class ReplacingDigest:
            def __init__(self):
                self.digest = real_sha256()

            def update(self, block):
                self.digest.update(block)
                replacement.replace(target)

            def hexdigest(self):
                return self.digest.hexdigest()

        with patch('check_data_layout.hashlib.sha256', side_effect=ReplacingDigest):
            self.assertTrue(check(self.root)[1])

    def test_legacy_link_retargeted_during_hashing_is_not_certified(self):
        real_sha256 = hashlib.sha256
        alternate = self.root / 'alternate.csv'
        alternate.write_bytes(self.target.read_bytes())
        legacy = self.legacy

        class RetargetingDigest:
            def __init__(self):
                self.digest = real_sha256()

            def update(self, block):
                self.digest.update(block)
                legacy.unlink()
                legacy.symlink_to('../alternate.csv')

            def hexdigest(self):
                return self.digest.hexdigest()

        with patch('check_data_layout.hashlib.sha256', side_effect=RetargetingDigest):
            self.assertTrue(check(self.root)[1])


if __name__ == '__main__':
    unittest.main()
