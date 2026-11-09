"""Offline artifact and workbook checks; no browser, account or network access."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
from zipfile import ZipFile

import build_pinterest_tracking as builder
from check_google_sheet_import import inspect
import check_google_sheet_import as preflight


class TrackingBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'prepared'
        self.config = {'tagId': '2612823030261', 'products': {
            f'SKU-{i}': {'id': f'variant-{i}', 'path': f'/buy/p/sculpture-{i}'}
            for i in range(176)}}

    def test_valid_build_binds_exact_prepared_bytes_to_receipt(self):
        result = builder.prepare(self.config, self.output)
        self.assertEqual(result['status'], 'PREPARED_ONLY')
        self.assertEqual(result['live_writes'], 0)
        for name, expected in result['sha256'].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(json.loads((self.output / 'tracking-build.json').read_text()), result)

    def test_existing_footer_or_receipt_blocks_every_new_artifact(self):
        for name in ('shopping-funnel-footer.html', 'tracking-build.json'):
            with self.subTest(name=name):
                output = self.root / name
                output.mkdir()
                (output / name).write_text('previous artifact')
                with self.assertRaises(FileExistsError):
                    builder.prepare(self.config, output)
                self.assertEqual([p.name for p in output.iterdir()], [name])
                self.assertEqual((output / name).read_text(), 'previous artifact')

    def test_failed_write_rolls_back_only_new_artifacts(self):
        with patch.object(builder.os, 'fsync', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                builder.prepare(self.config, self.output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_embedded_json_cannot_terminate_html_script(self):
        self.config['public_note'] = '</script><script>alert("test")</script>'
        builder.prepare(self.config, self.output)
        header = (self.output / 'pinterest-tag-header.html').read_text()
        self.assertEqual(header.count('</script>'), 1)
        self.assertNotIn('<script>alert', header)
        self.assertIn('JSON.parse(', header)

    def test_invalid_config_cannot_bypass_validation_under_python_optimization(self):
        self.config['tagId'] = 'invalid'
        path = self.root / 'config.json'
        path.write_text(json.dumps(self.config))
        result = subprocess.run([sys.executable, '-O', str(Path(builder.__file__)), str(path), str(self.output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_duplicate_ids_bad_paths_and_malformed_records_are_refused_before_writes(self):
        mutations = [lambda c: c['products']['SKU-1'].update(id='variant-0'),
                     lambda c: c['products']['SKU-1'].update(path='/buy/p/../other'),
                     lambda c: c['products']['SKU-1'].update(path='/buy/p/test?wrong=1'),
                     lambda c: c['products']['SKU-1'].update(path='/buy/p/%2e%2e/other'),
                     lambda c: c['products']['SKU-1'].update(id=[]),
                     lambda c: c['products'].update({'SKU-1': None})]
        for mutate in mutations:
            config = deepcopy(self.config)
            mutate(config)
            with self.subTest(config=config['products']['SKU-1']), self.assertRaises(ValueError):
                builder.prepare(config, self.output)
        self.assertFalse(self.output.exists())


MAIN = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
STRICT = 'http://purl.oclc.org/ooxml/spreadsheetml/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


class WorkbookPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'source.xlsx'

    def workbook(self, *, target='worksheets/current.xml', cells='', namespace=MAIN, missing=False):
        with ZipFile(self.path, 'w') as archive:
            archive.writestr('xl/workbook.xml', f'<workbook xmlns="{namespace}" xmlns:r="{REL}"><sheets><sheet name="Current" sheetId="1" r:id="sheet"/></sheets></workbook>')
            archive.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="sheet" Type="{REL}/worksheet" Target="{target}"/></Relationships>')
            if not missing:
                part = target.lstrip('/') if target.startswith('/') else 'xl/' + target
                archive.writestr(part, f'<worksheet xmlns="{namespace}"><sheetData><row r="1">{cells}</row></sheetData></worksheet>')

    def test_non_numbered_sheet_relationships_are_inspected(self):
        self.workbook(cells='<c r="A1" t="d"><v>2026-11-01T12:00:00Z</v></c><c r="B1"><f>1+1</f><v>2</v></c>')
        result = inspect(self.path)
        self.assertEqual(result['sheets'], 1)
        self.assertEqual(result['formulas'], 1)
        self.assertEqual(result['typed_date_cells'], 1)
        self.assertEqual(result['status'], 'HOLD_GOOGLE_IMPORT')

    def test_absolute_package_targets_and_strict_workbooks_are_supported(self):
        for namespace in (MAIN, STRICT):
            with self.subTest(namespace=namespace):
                self.workbook(target='/xl/worksheets/current.xml', namespace=namespace)
                result = inspect(self.path)
                self.assertEqual(result['sheets'], 1)
                self.assertEqual(result['status'], 'PASS_GOOGLE_IMPORT_PREFLIGHT')

    def test_non_workbook_zip_never_passes_a_zero_sheet_check(self):
        with ZipFile(self.path, 'w') as archive:
            archive.writestr('readme.txt', 'not a workbook')
        self.assertEqual(inspect(self.path)['status'], 'HOLD_GOOGLE_IMPORT')

    def test_missing_relationship_target_and_corrupt_workbook_are_held(self):
        self.workbook(missing=True)
        self.assertEqual(inspect(self.path)['status'], 'HOLD_GOOGLE_IMPORT')
        self.path.write_bytes(b'not a zip archive')
        self.assertEqual(inspect(self.path)['status'], 'HOLD_GOOGLE_IMPORT')

    def test_duplicate_zip_parts_and_escaping_relationships_are_held(self):
        self.workbook()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with ZipFile(self.path, 'a') as archive:
                archive.writestr('xl/workbook.xml', '<duplicate/>')
        self.assertEqual(inspect(self.path)['status'], 'HOLD_GOOGLE_IMPORT')
        self.workbook(target='../../outside.xml', missing=True)
        self.assertEqual(inspect(self.path)['status'], 'HOLD_GOOGLE_IMPORT')

    def test_hash_describes_the_inspected_snapshot_and_source_is_read_once(self):
        self.workbook(cells='<c r="A1" t="e"><v>#VALUE!</v></c>')
        raw = self.path.read_bytes()
        with patch.object(Path, 'read_bytes', return_value=raw) as read:
            result = inspect(self.path)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(result['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['formula_error_cells'], [{'part': 'xl/worksheets/current.xml', 'cell': 'A1'}])

    def test_report_cannot_overwrite_original_workbook_or_a_hardlink_to_it(self):
        self.workbook()
        raw = self.path.read_bytes()
        alias = self.root / 'source-alias.xlsx'
        alias.hardlink_to(self.path)
        for output in (self.path, alias):
            with self.subTest(output=output), self.assertRaises(SystemExit) as exit:
                preflight.main([str(self.path), '--report', str(output)])
            self.assertEqual(exit.exception.code, 2)
            self.assertEqual(self.path.read_bytes(), raw)

    def test_report_creates_its_parent_and_does_not_alter_source_bytes(self):
        self.workbook()
        raw = self.path.read_bytes()
        report = self.root / 'reports/preflight.json'
        self.assertEqual(preflight.main([str(self.path), '--report', str(report)]), 0)
        self.assertEqual(json.loads(report.read_text())['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.path.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
