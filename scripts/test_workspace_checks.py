"""A green workspace check must cover the selected suites, not empty discovery."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_workspace


class WorkspaceCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in (
            'scripts/check_workspace.py', 'scripts/check_data_layout.py', 'scripts/test_data.py',
            'catalogue-review/tests/test_example.py', 'catalogue-review/tests/ui-example.cjs',
            'catalogue-review/tests/test_example.mjs', 'application/tests/test_example.py',
            'application/src/example.py', 'search-analytics-toolkit/tests/test_example.py',
            'search-analytics-toolkit/src/example.py', 'image-processing/test_example.py',
            'SquareSpace product upload/scripts/tests/test_example.py',
            'channel-update-playbook/automation/test_example.py',
            'channel-update-playbook/automation/test_pinterest_tag.cjs',
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# fixture\n')

    def test_selected_javascript_patterns_must_both_exist(self):
        for pattern in ('*.cjs', 'test_*.mjs'):
            with self.subTest(pattern=pattern):
                for path in (self.root / 'catalogue-review/tests').glob(pattern):
                    before = path.read_text()
                    path.unlink()
                    try:
                        with self.assertRaisesRegex(ValueError, 'No check files matched'):
                            check_workspace.build_checks(self.root, 'python', 'node')
                    finally:
                        path.write_text(before)

    def test_missing_and_empty_python_suites_fail_preflight(self):
        for relative in ('scripts/test_data.py', 'catalogue-review/tests/test_example.py',
                         'application/tests/test_example.py', 'search-analytics-toolkit/tests/test_example.py',
                         'image-processing/test_example.py',
                         'SquareSpace product upload/scripts/tests/test_example.py',
                         'channel-update-playbook/automation/test_example.py'):
            with self.subTest(relative=relative):
                path = self.root / relative
                path.unlink()
                try:
                    with self.assertRaisesRegex(ValueError, 'No check files matched'):
                        check_workspace.build_checks(self.root, 'python', 'node')
                    path.write_text('')
                    with self.assertRaisesRegex(ValueError, 'missing or empty'):
                        check_workspace.build_checks(self.root, 'python', 'node')
                finally:
                    path.write_text('# fixture\n')

    def test_pytest_is_bound_to_its_project_test_directory(self):
        checks = check_workspace.build_checks(self.root, 'python', 'node')
        for name, directory, command in checks:
            if name in ('auditor', 'search-toolkit'):
                self.assertEqual(command[-1], 'tests')
                self.assertTrue((directory / 'tests').is_dir())

    def test_blank_javascript_file_does_not_pass_as_a_file_level_node_test(self):
        (self.root / 'catalogue-review/tests/ui-example.cjs').write_text(' \n\t')
        with self.assertRaisesRegex(ValueError, 'missing or empty'):
            check_workspace.build_checks(self.root, 'python', 'node')

    def test_browser_is_optional_but_explicit_selection_requires_its_script(self):
        self.assertEqual(len(check_workspace.build_checks(self.root, 'python', 'node')), 12)
        with self.assertRaisesRegex(ValueError, 'missing or empty'):
            check_workspace.build_checks(self.root, 'python', 'node', browser=True)
        script = self.root / 'catalogue-review/tests/browser-offline-smoke.mjs'
        script.write_text('// fixture\n')
        with self.assertRaisesRegex(ValueError, 'missing or empty'):
            check_workspace.build_checks(self.root, 'python', 'node', browser=True)
        (script.parent / 'browser-cold-starts.mjs').write_text('// fixture\n')
        self.assertEqual(len(check_workspace.build_checks(self.root, 'python', 'node', browser=True)), 14)

    def run_discovery(self, body):
        directory = self.root / 'guarded-unit'
        directory.mkdir()
        (directory / 'test_guard.py').write_text(body)
        return subprocess.run([sys.executable, str(Path(check_workspace.__file__).resolve()),
                               '--unittest-suite', str(directory), 'test_*.py'],
                              capture_output=True, text=True)

    def test_unittest_file_with_no_cases_cannot_report_pass(self):
        result = self.run_discovery('# A truncated test file still exists.\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no unittest cases discovered', result.stderr)

    def test_guarded_unittest_executes_real_cases(self):
        result = self.run_discovery('import unittest\nclass Checks(unittest.TestCase):\n'
                                   '    def test_real(self): self.assertEqual(2 + 2, 4)\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Ran 1 test', result.stderr)


if __name__ == '__main__':
    unittest.main()
