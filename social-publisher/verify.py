#!/usr/bin/env python3
"""Run relevant offline checks and optionally a read-only default-Chrome probe."""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from common import ROOT, atomic_json, digest, read_json, utc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-probe', action='store_true')
    args = parser.parse_args()
    results = []
    with tempfile.TemporaryDirectory(prefix='boldstone-social-verification-') as temp:
        commands = [
            ('python-recovery', [sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'), '-p', 'test_*.py', '-v']),
            ('dom-and-helper-worker', ['node', '--test', str(ROOT / 'tests' / 'dom.test.cjs'), str(ROOT / 'tests' / 'helper-worker.test.cjs')]),
            ('chrome-upload-fixture', [sys.executable, str(ROOT / 'tests' / 'chrome_upload_fixture.py')]),
            ('compile-bridge', ['/usr/bin/osacompile', '-o', temp + '/chrome.scpt', str(ROOT / 'chrome.applescript')]),
            ('compile-launcher', ['/usr/bin/osacompile', '-o', temp + '/Run.scpt', str(ROOT / 'Run.applescript')]),
        ]
        for name, argv in commands:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
            results.append({'check': name, 'passed': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr})
    if args.live_probe:
        result = subprocess.run([sys.executable, str(ROOT / 'publisher.py'), 'doctor', '--probe'], capture_output=True, text=True, timeout=60, check=False)
        results.append({'check': 'live-readonly-transport', 'passed': result.returncode == 0, 'stdout': result.stdout, 'stderr': result.stderr})
    source_hashes = {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in sorted(ROOT.rglob('*'))
                     if path.is_file() and not any(part in {'state', '__pycache__'} for part in path.relative_to(ROOT).parts)
                     and path.name != 'verification.json' and path.suffix not in {'.pyc', '.scpt'}}
    report = {'utc': utc(), 'status': 'OFFLINE_CHECKS_PASSED_LIVE_PUBLISHING_NOT_RUN' if all(r['passed'] for r in results) else 'CHECK_FAILED',
              'checks': results, 'source_sha256': source_hashes, 'live_publication': 'NOT_RUN', 'new_public_posts': 0}
    if args.live_probe and (ROOT / 'state' / 'health.json').exists():
        report['live_health'] = read_json(ROOT / 'state' / 'health.json')
    atomic_json(ROOT / 'verification.json', report)
    print(json.dumps({'status': report['status'], 'checks': [{k: r[k] for k in ['check', 'passed']} for r in results],
                      'report': str(ROOT / 'verification.json')}, indent=2))
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())

