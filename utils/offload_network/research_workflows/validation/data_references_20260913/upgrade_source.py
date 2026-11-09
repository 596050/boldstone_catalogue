"""Controlled source-coordinator update, retaining its exact old module snapshot."""

import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

PACKAGE = Path(__file__).resolve().parents[3]
REPO = PACKAGE.parents[1]
STATE = PACKAGE / '.source-state/math-loop-20260911-v1'
DEST = PACKAGE / '.source-state/data-reference-source-0.6.12'
SERVICE = STATE / 'queue/orchestrator/SERVICE.json'
WHEEL = PACKAGE / '.source-state/data-reference-validation-20260913-v1/release-wheel/fleet_offload_orchestration-0.6.12-py3-none-any.whl'
EXPECTED = '1d87ee4f512c8a846a20a0f46cdf2533cc1048bad49a140e7701fba9613c0a2a'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = json.loads(SERVICE.read_text())
    old_runtime = next((root for root in (STATE / 'orchestrator-runtimes').iterdir()
                        if all((root / 'research_workflows' / name).is_file()
                               and sha(root / 'research_workflows' / name) == value
                               for name, value in before['controller_bindings'].items())), None)
    if old_runtime is None or sha(WHEEL) != EXPECTED:
        raise RuntimeError('Exact previous runtime or verified new wheel is unavailable; nothing stopped')
    old_pid = before['pid']
    old_command = subprocess.check_output(['ps', '-p', str(old_pid), '-o', 'args='], text=True).strip()
    if 'research_workflows orchestrate --config ' + str(STATE / 'project.json') not in old_command:
        raise RuntimeError('Coordinator process identity differs')
    argv = shlex.split(old_command)
    DEST.mkdir(mode=0o700, exist_ok=False)
    (DEST / 'SERVICE_BEFORE.json').write_text(json.dumps(before, indent=2) + '\n')
    subprocess.run([sys.executable, '-m', 'venv', str(DEST / 'venv')], check=True)
    executable = DEST / 'venv/bin/python'
    subprocess.run([str(executable), '-m', 'pip', 'install', '--no-index', '--no-deps', str(WHEEL)],
                   check=True, stdout=subprocess.DEVNULL)
    if json.loads(SERVICE.read_text())['pid'] != old_pid:
        raise RuntimeError('Coordinator changed concurrently; nothing stopped')
    os.kill(old_pid, signal.SIGTERM)
    for _ in range(150):
        if subprocess.run(['ps', '-p', str(old_pid)], stdout=subprocess.DEVNULL).returncode != 0:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError('Old coordinator has not stopped; no force kill attempted')

    def launch(command, env, filename):
        with (DEST / filename).open('ab') as log:
            return subprocess.Popen(command, cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=log, start_new_session=True)

    process = launch([str(executable), *argv[1:]], dict(os.environ, PYTHONPATH=''), 'coordinator.log')
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError('Updated coordinator exited')
            try:
                with urlopen('http://127.0.0.1:8766/api/queue', timeout=2) as response:
                    queue = json.load(response)
                service = json.loads(SERVICE.read_text())
                if service['pid'] == process.pid and 'data_references.py' in service['controller_bindings']:
                    break
            except OSError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError('Updated coordinator did not become ready')
    except BaseException:
        process.terminate()
        process.wait(timeout=30)
        launch(argv, dict(os.environ, PYTHONPATH=str(old_runtime)), 'rollback.log')
        raise
    record = {'version': '0.6.12', 'wheel_sha256': EXPECTED, 'previous_pid': old_pid,
              'pid': process.pid, 'previous_runtime': str(old_runtime), 'runtime': str(DEST / 'venv'),
              'config_unchanged': sha(STATE / 'project.json') == before['config_sha256'],
              'controller_bindings': service['controller_bindings'],
              'job_counts_after': queue.get('job_counts'), 'worker_jobs_cancelled': 0}
    (DEST / 'UPGRADE.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
