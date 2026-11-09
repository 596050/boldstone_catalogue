"""Copy the original hybrid's exact sources and verify every remote file.

This is a source-preservation job, not a new strategy or statistical verdict.
The existing encrypted repository and its pinned SSH/repository identities apply.
No source is removed, overwritten, or registered as a replacement by this job.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from utils.external_storage.hetzner import storage_box as sb

ORIGINAL = ROOT / 'research/candidates/directional_forecasting/full_history_shadow_vote_hybrid_20260922_v2'
METADATA = ROOT / 'research/utility/full_history_14model_comparison_20260913_v1/contract/metadata_20260911/ORIGINAL_METADATA.json'
MOUNT = Path('/Volumes/Toshiba 2TB')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def stat(path):
    s = Path(path).stat()
    return dict(bytes=s.st_size, mtime_ns=s.st_mtime_ns, inode=s.st_ino, device=s.st_dev)


def save(name, value):
    sb.write_json(HERE / name, value)


def inventory():
    from utils.data_paths import resolve_storage_reference
    if (HERE / 'SOURCE_MANIFEST.json').exists():
        raise RuntimeError('Preserve the existing manifest; use it to resume.')
    frozen = json.loads((ORIGINAL / 'run_01/FREEZE.json').read_text())
    meta = json.loads(METADATA.read_text())
    files = []
    parents = {}
    def physical(name):
        original = Path(name)
        # The declared collection is relocated as a directory. Resolve/validate
        # each parent once, then check every selected real file below it.
        if original.parent not in parents:
            parents[original.parent] = resolve_storage_reference(original.parent, require_exists=True)
        return parents[original.parent] / original.name
    for f in frozen['daily_raw']:
        p = physical(f['path'])
        files.append(dict(path=str(p), original_path=f['path'], cadence='daily', symbol=p.stem,
                          sha256=f['sha256'], before=stat(p)))
    for symbol, v in meta['source_consumption']['partitions'].items():
        for f in v['raw_files']:
            p = physical(f['path'])
            s = stat(p)
            if s['bytes'] != f['bytes_consumed']:
                raise RuntimeError(f'Source size drift: {p}')
            files.append(dict(path=str(p), original_path=f['path'], cadence='minute', symbol=symbol,
                              sha256=f['sha256'], before=s, bar_label=f['bar_label']))
    assert len({f['path'] for f in files}) == len(files)
    assert {f['symbol'] for f in files if f['cadence'] == 'daily'} == set(meta['contract']['baseline_symbols'])
    assert len(meta['contract']['baseline_symbols']) == 96
    profile = sb.Profile(sb.DEFAULT_ROOT / 'market-data-parallel')
    sb.check_sources([f['path'] for f in files], profile, MOUNT)
    provenance = []
    for p in (METADATA, ORIGINAL / 'run_01/FREEZE.json', ORIGINAL / 'CONFIG.json', ORIGINAL / 'STATISTICAL_DESIGN.json'):
        provenance.append(dict(path=str(p), sha256=sha(p), before=stat(p), cadence='provenance'))
    value = dict(schema=1, created_at=sb.now(), purpose='Exact original hybrid source preservation',
                 symbols=meta['contract']['baseline_symbols'], source_files=files, provenance_files=provenance,
                 repository=profile.data['repository'], repository_id=profile.data['repository_id'],
                 group='frozen96-original-hybrid-sources-20260922', profile='market-data-parallel',
                 source_deletions=0, overwrite_sources=False, statistical_confirmation=False,
                 source_file_count=len(files), source_bytes=sum(f['before']['bytes'] for f in files),
                 expected_hash_authority='Original sealed daily FREEZE and full-consumption minute metadata; every remote byte must reproduce these hashes.')
    save('SOURCE_MANIFEST.json', value)
    print(json.dumps({k:v for k,v in value.items() if k not in ('symbols','source_files','provenance_files')}, indent=2))


def repository(profile):
    r = sb.Repository(profile)
    r.base = ['sftp.connections=8' if x == 'sftp.connections=2' else x for x in r.base]
    r.bind()
    return r


def archive():
    manifest = json.loads((HERE / 'SOURCE_MANIFEST.json').read_text())
    profile = sb.Profile(sb.DEFAULT_ROOT / manifest['profile'])
    with sb.locked(profile.directory):
        r = repository(profile)
        paths = [f['path'] for f in manifest['source_files'] + manifest['provenance_files']] + [str(HERE / 'SOURCE_MANIFEST.json')]
        sb.check_sources(paths, profile, MOUNT)
        for f in manifest['source_files'] + manifest['provenance_files']:
            if stat(f['path']) != f['before']:
                raise RuntimeError(f'Source stat drift before backup: {f["path"]}')
        state_path = HERE / 'ARCHIVE.json'
        prior = json.loads(state_path.read_text()) if state_path.exists() else {}
        if prior.get('status') == 'COPY_COMPLETE_READBACK_PENDING':
            return
        if prior.get('status') == 'VERIFIED':
            return
        token = 'frozen96-' + uuid.uuid4().hex
        state = dict(started_at=sb.now(), status='COPYING', run=token, repository_id=r.profile.data['repository_id'],
                     manifest_sha256=sha(HERE / 'SOURCE_MANIFEST.json'), source_deletions=0)
        save('ARCHIVE.json', state)
        args = ['backup', '--force', '--json', '--host', 'storagebox-' + profile.directory.name,
                '--tag', sb.PENDING, '--tag', 'run:' + token, '--tag', 'group:' + manifest['group'], '--', *paths]
        summary = None
        last_save = 0
        with (HERE / 'backup.jsonl').open('a') as log, (HERE / 'backup.stderr.log').open('a') as errors:
            with subprocess.Popen(r.base + args, env=r.env, stdout=subprocess.PIPE, stderr=errors, text=True) as proc:
                for line in proc.stdout:
                    log.write(line); log.flush()
                    event = json.loads(line)
                    if event.get('message_type') == 'summary':
                        summary = event
                    if time.monotonic() - last_save > 15 or summary:
                        state.update(progress=event, updated_at=sb.now(), pid=proc.pid)
                        save('ARCHIVE.json', state); last_save = time.monotonic()
                code = proc.wait()
        if code or not summary:
            state.update(status='COPY_INCOMPLETE', exit_code=code, finished_at=sb.now())
            save('ARCHIVE.json', state)
            raise RuntimeError(f'Backup did not complete: {code}')
        drift = [f['path'] for f in manifest['source_files'] + manifest['provenance_files'] if stat(f['path']) != f['before']]
        if drift:
            state.update(status='SOURCE_DRIFT', drift=drift); save('ARCHIVE.json', state)
            raise RuntimeError('Source changed during copy')
        rows = r.snapshots('run:' + token)
        assert len(rows) == 1
        r.successful(['tag', '--retry-lock', '5m', '--add', sb.COMPLETE, '--remove', sb.PENDING, rows[0]['id']])
        rows = r.snapshots('run:' + token + ',' + sb.COMPLETE)
        assert len(rows) == 1
        state.update(status='COPY_COMPLETE_READBACK_PENDING', snapshot_id=rows[0]['id'], copy_finished_at=sb.now(), summary=summary)
        save('ARCHIVE.json', state)
        profile.receipt(token, state)
        print(json.dumps(state, indent=2))


def verify():
    manifest = json.loads((HERE / 'SOURCE_MANIFEST.json').read_text())
    state = json.loads((HERE / 'ARCHIVE.json').read_text())
    if state['status'] == 'VERIFIED':
        print('Already verified'); return
    if state['status'] not in ('COPY_COMPLETE_READBACK_PENDING', 'READBACK_RUNNING', 'READBACK_FAILED'):
        raise RuntimeError('No completed snapshot to read back')
    expected = {f['path']: f for f in manifest['source_files'] + manifest['provenance_files']}
    expected[str(HERE / 'SOURCE_MANIFEST.json')] = dict(sha256=state['manifest_sha256'], before=stat(HERE / 'SOURCE_MANIFEST.json'))
    r = repository(sb.Profile(sb.DEFAULT_ROOT / manifest['profile']))
    snapshots = r.snapshots('run:' + state['run'])
    if len(snapshots) != 1 or snapshots[0]['id'] != state['snapshot_id']:
        raise RuntimeError('Uploaded snapshot identity mismatch')
    snapshot_before = snapshots[0]
    if sb.COMPLETE not in snapshot_before.get('tags', []) and sb.PENDING not in snapshot_before.get('tags', []):
        raise RuntimeError('Unexpected snapshot publication state')
    state.update(status='READBACK_RUNNING', readback_started_at=sb.now())
    save('ARCHIVE.json', state)
    rows, total = [], 0
    seen = set()
    try:
        with (HERE / 'readback.stderr.log').open('a') as errors:
            with subprocess.Popen(r.base + ['dump', state['snapshot_id'], '/'], env=r.env, stdout=subprocess.PIPE, stderr=errors) as proc:
                with tarfile.open(fileobj=proc.stdout, mode='r|') as tar:
                    for member in tar:
                        if member.isdir():
                            continue
                        path = '/' + member.name.lstrip('/')
                        if not member.isfile() or path not in expected or path in seen:
                            raise RuntimeError(f'Unexpected remote member: {path}')
                        h = hashlib.sha256(); n = 0
                        with tar.extractfile(member) as f:
                            for b in iter(lambda:f.read(4 * 1024**2), b''):
                                h.update(b); n += len(b)
                        target = expected[path]
                        if h.hexdigest() != target['sha256'] or n != target['before']['bytes']:
                            raise RuntimeError(f'Remote content mismatch: {path}')
                        seen.add(path); total += n
                        rows.append(dict(path=path, bytes=n, sha256=h.hexdigest(), status='PASS'))
                        state.update(readback_files=len(rows), readback_bytes=total, updated_at=sb.now())
                        save('ARCHIVE.json', state)
                # Drain archive padding before waiting so pipe backpressure cannot deadlock.
                while proc.stdout.read(1024**2):
                    pass
                code = proc.wait()
        if code or seen != set(expected):
            raise RuntimeError(f'Incomplete remote readback: exit={code}, missing={len(set(expected)-seen)}')
        read_snapshot = state['snapshot_id']
        if sb.COMPLETE not in snapshot_before.get('tags', []):
            r.successful(['tag','--retry-lock','5m','--add',sb.COMPLETE,'--remove',sb.PENDING,read_snapshot])
            completed = r.snapshots('run:' + state['run'] + ',' + sb.COMPLETE)
            if len(completed) != 1 or completed[0]['tree'] != snapshot_before['tree']:
                raise RuntimeError('Snapshot tree changed during publication')
            state['snapshot_id'] = completed[0]['id']
        save('REMOTE_READBACK.json', dict(status='PASS', snapshot_id=state['snapshot_id'], read_snapshot_id=read_snapshot, completed_at=sb.now(),
                                       method='Restic authenticated decrypt and full streaming SHA256 of every file; no archive extracted to disk',
                                       files=rows, file_count=len(rows), bytes=total))
        state.update(status='VERIFIED', verified_at=sb.now(), remote_readback_sha256=sha(HERE / 'REMOTE_READBACK.json'))
    except BaseException as e:
        state.update(status='READBACK_FAILED', error=str(e), failed_at=sb.now())
        raise
    finally:
        save('ARCHIVE.json', state)
    print(json.dumps(state, indent=2))


def accept_uploaded():
    """Use the completed upload receipt; publish only after full byte readback.

    Post-copy Toshiba metadata is optional for this immutable-original-source
    copy: its contents must match *every sealed original SHA256* independently.
    A snapshot containing changed/partial source bytes cannot pass that test.
    Do not misrepresent the stalled extra filesystem census as a passed check.
    """
    manifest = json.loads((HERE/'SOURCE_MANIFEST.json').read_text())
    state = json.loads((HERE/'ARCHIVE.json').read_text())
    summary = state.get('progress', {})
    assert state['status'] == 'COPYING' and summary.get('message_type') == 'summary'
    assert sha(HERE/'SOURCE_MANIFEST.json') == state['manifest_sha256']
    files = manifest['source_files'] + manifest['provenance_files']
    assert summary['total_files_processed'] == len(files) + 1
    assert summary['total_bytes_processed'] == sum(f['before']['bytes'] for f in files) + (HERE/'SOURCE_MANIFEST.json').stat().st_size
    profile = sb.Profile(sb.DEFAULT_ROOT / manifest['profile'])
    with sb.locked(profile.directory):
        r = repository(profile)
        rows = r.snapshots('run:' + state['run'])
        assert len(rows) == 1 and rows[0]['id'] == summary['snapshot_id']
        expected = {f['path'] for f in files} | {str(HERE/'SOURCE_MANIFEST.json')}
        assert set(rows[0]['paths']) == expected
        save('POST_COPY_SOURCE_IDENTITY.json', dict(status='NOT_COMPLETED_FILESYSTEM_METADATA_STALLED',
              at_utc=sb.now(),pre_copy_identity_checked=True,post_copy_identity_checked=False,
              replacement='Full remote decrypted SHA256 readback against all sealed original hashes; completion tag withheld until every file passes',
              explanation='Both scalar stat and bulk metadata walks stalled on Toshiba. They are retained as incomplete auxiliary checks, not claimed as passes.'))
        state.update(status='COPY_COMPLETE_READBACK_PENDING',snapshot_id=rows[0]['id'],copy_finished_at=sb.now(),
                     summary=summary,completion_tag_withheld_until_hash_readback=True,
                     finalization='Snapshot and exact paths/bytes verified; all original hashes must pass remote readback before publication')
        save('ARCHIVE.json',state)
        print(json.dumps(dict(status=state['status'],snapshot_id=state['snapshot_id']),indent=2))


def finish_copy():
    """Finish an uploaded snapshot using bounded bulk exFAT metadata reads.

    macOS stat asks for allocation information and can walk enormous exFAT FAT
    chains. The existing getattrlistbulk utility requests only logical lengths
    and identity/time fields. Content confirmation still requires full remote
    SHA256 readback against the sealed original source hashes.
    """
    manifest = json.loads((HERE / 'SOURCE_MANIFEST.json').read_text())
    state = json.loads((HERE / 'ARCHIVE.json').read_text())
    summary = state.get('progress', {})
    if state['status'] != 'COPYING' or summary.get('message_type') != 'summary':
        raise RuntimeError('Only an already completed upload may use this finalizer')
    assert summary['total_files_processed'] == len(manifest['source_files']) + len(manifest['provenance_files']) + 1
    profile = sb.Profile(sb.DEFAULT_ROOT / manifest['profile'])
    with sb.locked(profile.directory):
        r = repository(profile)
        sb.check_sources([manifest['source_files'][0]['path']], profile, MOUNT)
        spec = importlib.util.spec_from_file_location('frozen96_bulk_metadata', ROOT / 'research/utility/toshiba_data_manifest_20260913_v1/bulk_metadata.py')
        bulk = importlib.util.module_from_spec(spec); spec.loader.exec_module(bulk)
        groups = {}
        for f in manifest['source_files'] + manifest['provenance_files']:
            groups.setdefault(Path(f['path']).parent, {})[Path(f['path']).name] = f
        checked = []
        for parent, wanted in groups.items():
            if not parent.is_relative_to(MOUNT):
                actual = {name: stat(parent / name) for name in wanted}
            else:
                actual = {}
                for row in bulk.entries(parent, stat_empty_files=False):
                    if row['name'] not in wanted:
                        continue
                    if not row['valid']:
                        raise RuntimeError('Invalid bulk source metadata')
                    s = row['stat']
                    actual[row['name']] = dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,device=s.st_dev)
                    if set(actual) == set(wanted): break
            if set(actual) != set(wanted): raise RuntimeError('Missing post-copy source file')
            for name, f in wanted.items():
                if actual[name] != f['before']:
                    raise RuntimeError('Source identity changed during copy: ' + f['path'])
                checked.append(dict(path=f['path'],after=actual[name],status='PASS'))
        save('POST_COPY_SOURCE_IDENTITY.json',dict(status='PASS',at_utc=sb.now(),files=checked,
              method='Existing macOS getattrlistbulk reader; compare logical bytes, mtime_ns, inode and device; full remote hashes checked separately'))
        rows = r.snapshots('run:' + state['run'])
        assert len(rows) == 1 and rows[0]['id'] == summary['snapshot_id']
        r.successful(['tag','--retry-lock','5m','--add',sb.COMPLETE,'--remove',sb.PENDING,rows[0]['id']])
        rows = r.snapshots('run:' + state['run'] + ',' + sb.COMPLETE)
        assert len(rows) == 1
        state.update(status='COPY_COMPLETE_READBACK_PENDING',snapshot_id=rows[0]['id'],copy_finished_at=sb.now(),
                     summary=summary,post_copy_identity=sha(HERE / 'POST_COPY_SOURCE_IDENTITY.json'),
                     finalization='Completed upload resumed after slow scalar stat traversal; no data re-upload or source changes')
        save('ARCHIVE.json',state);profile.receipt(state['run'],state)
        print(json.dumps(state,indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('operation', choices=['inventory', 'archive', 'verify', 'finish_copy', 'accept_uploaded'])
    globals()[p.parse_args().operation]()
