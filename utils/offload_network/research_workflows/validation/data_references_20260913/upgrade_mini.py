"""Install the verified runtime separately, then replace only an idle owned worker."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path('/Users/tomprice/marketmaker-offload')
CONFIG = ROOT / 'worker/worker.json'
RUNTIME = ROOT / 'runtime-0.6.12'
WHEEL = ROOT / 'fleet_offload_orchestration-0.6.12-py3-none-any.whl'
EXPECTED = '1d87ee4f512c8a846a20a0f46cdf2533cc1048bad49a140e7701fba9613c0a2a'
ENV = dict(os.environ, PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
           DOCKER_CONTEXT='colima-marketmaker', PYTHONUNBUFFERED='1')


def pending():
    with sqlite3.connect((ROOT / 'worker/state/jobs.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        return {table: db.execute(f"SELECT COUNT(*) FROM {table} WHERE state NOT IN "
                                 "('succeeded','failed','interrupted','cancelled','blocked_dependency')").fetchone()[0]
                for table in ('jobs', 'workflow_nodes')}


def start(executable, log_name):
    with (ROOT / log_name).open('ab') as log:
        return subprocess.Popen([str(executable), 'serve', '--config', str(CONFIG)],
                                cwd=ROOT, env=ENV, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=log, start_new_session=True)


def main():
    if ROOT.is_symlink() or RUNTIME.exists():
        raise RuntimeError('Expected fresh dedicated runtime directory')
    with WHEEL.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != EXPECTED:
            raise ValueError('Wheel hash differs')
    subprocess.run(['/opt/homebrew/opt/python@3.12/bin/python3.12', '-m', 'venv', str(RUNTIME)], check=True)
    subprocess.run([str(RUNTIME / 'bin/python'), '-m', 'pip', 'install', '--no-index', '--no-deps', str(WHEEL)],
                   check=True, stdout=subprocess.DEVNULL)
    before = pending()
    if any(before.values()):
        raise RuntimeError('Worker is not idle; it was not stopped')
    process_list = subprocess.check_output(['ps', '-axo', 'pid,args'], text=True)
    marker = str(ROOT / 'venv/bin/offload-worker') + ' serve --config ' + str(CONFIG)
    matches = [int(line.split(None, 1)[0]) for line in process_list.splitlines() if marker in line]
    if len(matches) != 1:
        raise RuntimeError('Exact original worker process could not be uniquely identified')
    old_pid = matches[0]
    os.kill(old_pid, signal.SIGTERM)
    for _ in range(100):
        old = subprocess.run(['ps', '-p', str(old_pid), '-o', 'args='], capture_output=True, text=True)
        if old.returncode != 0:
            break
        if marker not in old.stdout:
            raise RuntimeError('Original process identity changed')
        time.sleep(0.1)
    else:
        raise RuntimeError('Worker did not stop; no force kill or state change attempted')
    try:
        if any(pending().values()):
            raise RuntimeError('Job admission raced with the idle check')
        process = start(RUNTIME / 'bin/offload-worker', 'worker-0.6.12.log')
        token = (ROOT / 'worker/access-token').read_text().strip()
        for _ in range(50):
            try:
                with urlopen(Request('http://127.0.0.1:8765/v2/capabilities',
                                     headers={'Authorization': 'Bearer ' + token}), timeout=2) as response:
                    capabilities = json.load(response)
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError('New worker exited')
                time.sleep(0.1)
        else:
            raise RuntimeError('New worker did not become ready')
        if 'data_ref' not in capabilities['input_modes']:
            raise RuntimeError('New worker lacks data reference support')
    except BaseException:
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        start(ROOT / 'venv/bin/offload-worker', 'worker-rollback-0.6.11.log')
        raise
    record = {'at_utc': datetime.now(timezone.utc).isoformat(), 'version': '0.6.12',
              'wheel_sha256': EXPECTED, 'previous_worker_pid': old_pid,
              'worker_pid': process.pid, 'runtime': str(RUNTIME),
              'pending_before': before, 'config_unchanged': True,
              'original_runtime_retained': str(ROOT / 'venv'),
              'capabilities': capabilities, 'existing_jobs_cancelled': 0,
              'new_source_credentials_configured': False}
    with (ROOT / 'UPGRADE-0.6.12.json').open('x') as out:
        json.dump(record, out, indent=2)
        out.write('\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
