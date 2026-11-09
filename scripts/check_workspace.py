#!/usr/bin/env python3
"""Run the active applications' offline checks and retain readable test logs."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def executable(value, label):
    found = shutil.which(value)
    if not found:
        raise ValueError(f'{label} was not found: {value}. Install it or pass an explicit executable path.')
    # Preserve venv symlinks: resolving them changes Python's environment.
    return str(Path(found).absolute())


def require_file(path):
    path = Path(path)
    if not path.is_file() or not path.read_bytes().strip():
        raise ValueError(f'Required check file is missing or empty: {path}')
    return str(path)


def require_suite(directory, pattern):
    directory = Path(directory)
    files = sorted(path for path in directory.glob(pattern) if path.is_file())
    if not files:
        raise ValueError(f'No check files matched {directory / pattern}; verification cannot pass an empty suite.')
    return [require_file(path) for path in files]


def run_unittest_suite(directory, pattern):
    """Unittest otherwise exits successfully when discovery finds zero cases."""
    import unittest

    try:
        require_suite(directory, pattern)
        suite = unittest.TestLoader().discover(directory, pattern=pattern)
    except (ValueError, ImportError, OSError) as exc:
        print(f'FAIL unittest discovery: {exc}', file=sys.stderr)
        return 1
    if suite.countTestCases() == 0:
        print(f'FAIL: no unittest cases discovered in {directory} ({pattern}).', file=sys.stderr)
        return 1
    return 0 if unittest.TextTestRunner().run(suite).wasSuccessful() else 1


def build_checks(root, python, node, *, browser=False):
    """Resolve the exact intended suites before launching any checks."""
    root = Path(root)
    runner = require_file(root / 'scripts/check_workspace.py')

    def unit(name, relative, pattern='test_*.py'):
        directory = root / relative
        require_suite(directory, pattern)
        return name, root, [python, runner, '--unittest-suite', str(directory), pattern]

    javascript = [*require_suite(root / 'catalogue-review/tests', '*.cjs'),
                  *require_suite(root / 'catalogue-review/tests', 'test_*.mjs')]
    for relative in ('application/tests', 'search-analytics-toolkit/tests', 'image-processing'):
        require_suite(root / relative, 'test_*.py')
    for relative in ('application/src', 'search-analytics-toolkit/src'):
        require_suite(root / relative, '**/*.py')
    checks = [
        ('data-layout', root, [python, require_file(root / 'scripts/check_data_layout.py')]),
        unit('data-regressions', 'scripts'),
        unit('review-python', 'catalogue-review/tests'),
        ('review-javascript', root, [node, '--test', *javascript]),
        ('auditor', root / 'application', [python, '-m', 'pytest', '-o', 'addopts=', '-q', 'tests']),
        ('auditor-lint', root / 'application', [python, '-m', 'ruff', 'check', 'src', 'tests']),
        ('search-toolkit', root / 'search-analytics-toolkit', [python, '-m', 'pytest', '-o', 'addopts=', '-q', 'tests']),
        ('search-toolkit-lint', root / 'search-analytics-toolkit', [python, '-m', 'ruff', 'check', 'src', 'tests']),
        ('image-processing', root, [python, '-m', 'pytest', '-q', 'image-processing']),
        unit('content-pipeline', 'SquareSpace product upload/scripts/tests'),
        unit('channel-preparation', 'channel-update-playbook/automation'),
        ('channel-tracking', root, [node, require_file(root / 'channel-update-playbook/automation/test_pinterest_tag.cjs')]),
    ]
    if browser:
        checks.append(('browser-smoke', root, [node, require_file(root / 'catalogue-review/tests/browser-offline-smoke.mjs')]))
        checks.append(('browser-cold-starts', root, [node, require_file(root / 'catalogue-review/tests/browser-cold-starts.mjs')]))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    local_python = ROOT / 'application/.venv/bin/python'
    parser.add_argument('--python', default=str(local_python) if local_python.is_file() else sys.executable,
                        help='Python 3.11–3.14 environment containing the apps and test dependencies')
    parser.add_argument('--node', default='node', help='Node executable for offline JavaScript checks')
    parser.add_argument('--browser', action='store_true',
                        help='Also run Chrome/Playwright workflows against an isolated fake server (requires Playwright)')
    parser.add_argument('--logs-dir', type=Path, help='Directory for check logs; defaults to a new temporary directory')
    parser.add_argument('--unittest-suite', nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.unittest_suite:
        return run_unittest_suite(*args.unittest_suite)
    try:
        python = executable(args.python, 'Python')
        node = executable(args.node, 'Node')
        checks = build_checks(ROOT, python, node, browser=args.browser)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    version = subprocess.run([python, '-c', 'import sys; print(".".join(map(str, sys.version_info[:2])))'],
                             capture_output=True, text=True, check=True).stdout.strip()
    if not (3, 11) <= tuple(map(int, version.split('.'))) < (3, 15):
        parser.error(f'Python {version} is outside the supported 3.11–3.14 range. Pass --python with a supported environment.')
    logs = args.logs_dir.expanduser().absolute() if args.logs_dir else Path(tempfile.mkdtemp(prefix='boldstone-checks-'))
    logs.mkdir(parents=True, exist_ok=True)
    failed = []
    print(f'Offline checks using Python {version}. Logs: {logs}', flush=True)
    for name, directory, command in checks:
        environment = os.environ.copy()
        if (directory / 'src').is_dir():
            environment['PYTHONPATH'] = str(directory / 'src')
        if name in ('browser-smoke', 'browser-cold-starts'):
            environment['REVIEW_BROWSER_PYTHON'] = python
            environment['REVIEW_BROWSER_OUTPUT'] = str(logs / 'browser')
        path = logs / (name + '.log')
        with path.open('w', encoding='utf-8') as stream:
            result = subprocess.run(command, cwd=directory, env=environment,
                                    stdout=stream, stderr=subprocess.STDOUT)
        print(f'{"PASS" if result.returncode == 0 else "FAIL"} {name}', flush=True)
        if result.returncode:
            failed.append(name)
            print('\n'.join(path.read_text(errors='replace').splitlines()[-10:]), flush=True)
    if failed:
        print(f'{len(failed)} check(s) failed. Details: {logs}', flush=True)
        return 1
    print(f'All {len(checks)} offline check groups passed. Private-data/live checks are separate.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
