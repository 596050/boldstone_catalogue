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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    local_python = ROOT / 'application/.venv/bin/python'
    parser.add_argument('--python', default=str(local_python) if local_python.is_file() else sys.executable,
                        help='Python 3.11–3.14 environment containing the apps and test dependencies')
    parser.add_argument('--node', default='node', help='Node executable for offline JavaScript checks')
    parser.add_argument('--browser', action='store_true',
                        help='Also run Chrome/Playwright workflows against an isolated fake server (requires Playwright)')
    parser.add_argument('--logs-dir', type=Path, help='Directory for check logs; defaults to a new temporary directory')
    args = parser.parse_args()
    try:
        python = executable(args.python, 'Python')
        node = executable(args.node, 'Node')
    except ValueError as exc:
        parser.error(str(exc))
    version = subprocess.run([python, '-c', 'import sys; print(".".join(map(str, sys.version_info[:2])))'],
                             capture_output=True, text=True, check=True).stdout.strip()
    if not (3, 11) <= tuple(map(int, version.split('.'))) < (3, 15):
        parser.error(f'Python {version} is outside the supported 3.11–3.14 range. Pass --python with a supported environment.')
    logs = args.logs_dir.expanduser().absolute() if args.logs_dir else Path(tempfile.mkdtemp(prefix='boldstone-checks-'))
    logs.mkdir(parents=True, exist_ok=True)
    checks = [
        ('data-layout', ROOT, [python, str(ROOT / 'scripts/check_data_layout.py')]),
        ('data-regressions', ROOT, [python, '-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_*.py']),
        ('review-python', ROOT, [python, '-m', 'unittest', 'discover', '-s', 'catalogue-review/tests', '-p', 'test_*.py']),
        ('review-javascript', ROOT, [node, '--test',
            *map(str, sorted((ROOT / 'catalogue-review/tests').glob('*.cjs'))),
            *map(str, sorted((ROOT / 'catalogue-review/tests').glob('test_*.mjs')))]),
        ('auditor', ROOT / 'application', [python, '-m', 'pytest', '-o', 'addopts=', '-q']),
        ('auditor-lint', ROOT / 'application', [python, '-m', 'ruff', 'check', 'src', 'tests']),
        ('search-toolkit', ROOT / 'search-analytics-toolkit', [python, '-m', 'pytest', '-o', 'addopts=', '-q']),
        ('search-toolkit-lint', ROOT / 'search-analytics-toolkit', [python, '-m', 'ruff', 'check', 'src', 'tests']),
        ('image-processing', ROOT, [python, '-m', 'pytest', '-q', 'image-processing']),
        ('content-pipeline', ROOT, [python, '-m', 'unittest', 'discover', '-s', 'SquareSpace product upload/scripts/tests']),
        ('channel-preparation', ROOT, [python, '-m', 'unittest', 'discover', '-s', 'channel-update-playbook/automation', '-p', 'test_*.py']),
        ('channel-tracking', ROOT, [node, str(ROOT / 'channel-update-playbook/automation/test_pinterest_tag.cjs')]),
    ]
    if args.browser:
        checks.append(('browser-smoke', ROOT, [node, str(ROOT / 'catalogue-review/tests/browser-offline-smoke.mjs')]))
    failed = []
    print(f'Offline checks using Python {version}. Logs: {logs}', flush=True)
    for name, directory, command in checks:
        environment = os.environ.copy()
        if (directory / 'src').is_dir():
            environment['PYTHONPATH'] = str(directory / 'src')
        if name == 'browser-smoke':
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
