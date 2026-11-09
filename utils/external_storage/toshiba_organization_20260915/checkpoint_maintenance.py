"""Controlled stop/resume of the exact checkpointed reader blocking relocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from organize import HERE, REPO, atomic_json, utc

SCRIPT = REPO / 'research/utility/persistence_freeze_source_repair_20260915_v1/run_price_replay_03.py'
OUTPUT = Path('/Users/tprice/marketmaker-research-data/persistence_freeze_source_repair_20260915_v1/minute_price_replay_03')
STATE = HERE / 'CHECKPOINT_MAINTENANCE.json'
NOTICE = SCRIPT.parent / 'STORAGE_MAINTENANCE_20260915.json'


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def processes():
    rows = []
    for line in subprocess.check_output(['ps', '-axo', 'pid=,command='], text=True).splitlines():
        pid, command = line.strip().split(None, 1)
        if ('Python -B -u ' in command or 'python3 -B -u ' in command) and str(SCRIPT.relative_to(REPO)) in command:
            rows.append({'pid': int(pid), 'command': command})
    return rows


def references(obj):
    if isinstance(obj, dict):
        if {'path', 'bytes', 'sha256'} <= obj.keys():
            yield obj
        else:
            for value in obj.values(): yield from references(value)
    elif isinstance(obj, list):
        for value in obj: yield from references(value)


def checkpoint():
    failures = []
    for path in sorted(OUTPUT.glob('checkpoint_*.json'), reverse=True):
        try:
            value = json.loads(path.read_text())
            unique = {r['path']: r for r in references(value)}
            for name, ref in unique.items():
                p = Path(name)
                if p.stat().st_size != ref['bytes'] or sha(p) != ref['sha256']:
                    raise ValueError('Checkpoint reference does not match: ' + name)
                with p.open('rb') as f: os.fsync(f.fileno())
            return {'path': str(path), 'sha256': sha(path), 'stop': value['stop'],
                    'verified_references': len(unique), 'incomplete_later_checkpoints': failures}
        except (ValueError, KeyError, OSError) as exc:
            failures.append({'path': str(path), 'error': str(exc)})
    raise RuntimeError('No fully verified checkpoint is available')


def save(value):
    atomic_json(STATE, value)
    # An operational handoff beside the running utility; no sealed source,
    # freeze, existing log or checkpoint is edited.
    atomic_json(NOTICE, value)


def stop():
    owners = processes()
    if len(owners) != 1:
        raise RuntimeError(f'Expected exactly one known reader, found {len(owners)}')
    before = checkpoint()
    record = {'at_utc': utc(), 'state': 'CONTROLLED_CHECKPOINT_STOP_FOR_STORAGE_RELOCATION',
              'reader': owners[0], 'script': str(SCRIPT), 'script_sha256': sha(SCRIPT),
              'checkpoint_before_stop': before,
              'resume_command': ['/opt/homebrew/bin/python3', '-B', '-u', str(SCRIPT.relative_to(REPO)), '--resume'],
              'reason': 'Complete authorized Toshiba reorganization; preserve checkpoint and every partial output; resume after final path publication'}
    save(record)
    os.kill(owners[0]['pid'], signal.SIGINT)
    deadline = time.monotonic() + 25
    while any(p['pid'] == owners[0]['pid'] for p in processes()):
        if time.monotonic() > deadline:
            raise RuntimeError('Reader has not exited after SIGINT; no forced kill or source move permitted')
        time.sleep(.2)
    after = checkpoint()
    # Resume writes only the next chunk. Preserve incomplete later chunk files
    # separately so exclusive-create cannot collide with an interrupted attempt.
    retained = []
    retained_root = OUTPUT / ('storage_maintenance_retained_' + str(time.time_ns()))
    for path in sorted(OUTPUT.iterdir()):
        match = re.fullmatch(r'(?:checkpoint_(\d+)\.json|states_(\d+)\.npz|rows_(\d+)\.json\.gz)', path.name)
        if not match: continue
        number = int(next(v for v in match.groups() if v is not None))
        if number <= after['stop']: continue
        if not path.is_file() or path.is_symlink(): raise RuntimeError('Unexpected partial chunk kind')
        old_sha, size = sha(path), path.stat().st_size
        retained_root.mkdir(exist_ok=True)
        target = retained_root / path.name
        if target.exists(): raise FileExistsError(target)
        os.rename(path, target)
        if sha(target) != old_sha: raise RuntimeError('Partial chunk retention failed checksum')
        retained.append({'original': str(path), 'retained': str(target), 'bytes': size, 'sha256': old_sha})
    record.update(state='PAUSED_AT_VERIFIED_CHECKPOINT', stopped_at_utc=utc(),
                  checkpoint=after, retained_partial_chunks=retained, payload_files_deleted=0)
    save(record)
    print(json.dumps(record, indent=2), flush=True)


def resume():
    record = json.loads(STATE.read_text())
    if json.loads((REPO / 'data_paths.json').read_text()).get('organization', {}).get('state') != 'COMPLETE_RECONCILED':
        raise RuntimeError('Storage organization must be reconciled and published before resume')
    if sha(SCRIPT) != record['script_sha256']:
        raise RuntimeError('Replay code changed during maintenance; do not silently change the saved replay')
    owners = processes()
    if owners:
        if len(owners) != 1: raise RuntimeError('Multiple replay owners; do not launch another')
        record.update(state='READER_ALREADY_RESTARTED', resumed_reader=owners[0])
    else:
        latest = checkpoint()
        if latest['sha256'] != record['checkpoint']['sha256']:
            raise RuntimeError('Checkpoint changed during maintenance')
        log_path = HERE / 'REPLAY_RESUME.log'
        with log_path.open('xb') as log:
            child = subprocess.Popen(record['resume_command'], cwd=REPO,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        record.update(state='RESUME_LAUNCHED_AWAITING_PROGRESS', resumed_pid=child.pid, resume_log=str(log_path))
    record['resumed_at_utc'] = utc()
    save(record)
    print(json.dumps({k:v for k,v in record.items() if k not in {'retained_partial_chunks'}}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'stop', 'resume'])
    args = parser.parse_args()
    if args.command == 'inspect': print(json.dumps({'readers': processes(), 'checkpoint': checkpoint()}, indent=2))
    elif args.command == 'stop': stop()
    else: resume()
