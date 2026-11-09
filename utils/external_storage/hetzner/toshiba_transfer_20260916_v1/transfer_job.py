#!/usr/bin/env python3
"""Resumable Toshiba source migration; preserve originals and publish evidence.

Uses the existing Storage Box utility for encrypted uploads, completion tags and
verified restores. This job never deletes source data or changes acquisition paths.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import importlib.util
import ipaddress
import io
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import socket
import sqlite3
import stat
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MOUNT = Path('/Volumes/Toshiba 2TB')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


sb = module('storage_box', HERE.parent / 'storage_box.py')
bulk = module('bulk_metadata', ROOT / 'research/utility/toshiba_data_manifest_20260913_v1/bulk_metadata.py')


def save(name, value):
    sb.write_json(HERE / name, value)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory(paths):
    """Stream all entries; a failed/invalid read aborts, never silently excludes."""
    pending = []
    for path in paths:
        p = Path(path)
        yield str(p), p.lstat()
        if p.is_dir() and not p.is_symlink():
            pending.append(p)
    while pending:
        directory = pending.pop()
        for row in bulk.entries(directory):
            if not row['valid']:
                raise RuntimeError(f'Invalid source metadata: {directory / row["name"]}')
            p = directory / row['name']
            st = row['stat']
            yield str(p), st
            if stat.S_ISDIR(st.st_mode):
                pending.append(p)


def identity(st):
    kind = 'file' if stat.S_ISREG(st.st_mode) else 'dir' if stat.S_ISDIR(st.st_mode) else 'symlink' if stat.S_ISLNK(st.st_mode) else 'other'
    return kind, st.st_size if kind == 'file' else 0, st.st_mtime_ns, st.st_ino


def make_plan():
    if (HERE / 'PLAN.json').exists():
        raise RuntimeError('Plan already exists; preserve the existing migration identity.')
    profile = sb.Profile(sb.DEFAULT_ROOT / 'market-data')
    roots = [MOUNT / p for p in [
        'raw_price_data', 'other_data/macroeconomics',
        'other_data/non_price_provider_archive', 'other_data/non_price_legacy',
        'other_data/raw', 'other_data/legacy_ibkr_files', 'other_data/migration',
        'DATA_LAYOUT.md',
    ]]
    sb.check_sources(roots, profile, MOUNT)
    paths = []
    for root in roots:
        if root.name in ('raw_price_data', 'non_price_provider_archive'):
            for row in bulk.entries(root):
                if not row['valid']:
                    raise RuntimeError(f'Cannot partition {root}')
                child = root / row['name']
                if child.name == 'iqfeed_archive':
                    for entry in bulk.entries(child):
                        if not entry['valid']:
                            raise RuntimeError(f'Cannot partition {child}')
                        paths.append(child / entry['name'])
                else:
                    paths.append(child)
        else:
            paths.append(root)
    for a in paths:
        for b in paths:
            if a != b and a.is_relative_to(b):
                raise RuntimeError(f'Overlapping selections: {a}, {b}')
    census = ROOT / 'research/utility/toshiba_data_manifest_20260913_v1/run_09_organized_complete_20260915/FILES.jsonl.gz'
    counts = {str(p): [0, 0] for p in paths}
    selections = {str(p.relative_to(MOUNT)): str(p) for p in paths}
    root_names = [str(p.relative_to(MOUNT)) for p in roots]
    with gzip.open(census, 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            relative = row['path']
            prefix = relative
            while prefix and prefix not in selections:
                prefix = prefix.rpartition('/')[0]
            if prefix:
                c = counts[selections[prefix]]
                c[0] += 1
                c[1] += row['bytes']
            elif any(relative == p or relative.startswith(p + '/') for p in root_names):
                raise RuntimeError(f'Prior source omitted: {relative}')
    batches = []
    for path in paths:
        rel = str(path.relative_to(MOUNT))
        suffix = hashlib.sha256(rel.encode()).hexdigest()[:8]
        slug = re.sub('[^A-Za-z0-9_.-]+', '-', path.name)[:48].strip('.-') or 'root'
        batches.append({'group': 'toshiba-' + slug + '-' + suffix, 'paths': [str(path)],
                        'prior_files': counts[str(path)][0], 'prior_bytes': counts[str(path)][1]})
    batches.sort(key=lambda b: (0 if any('/migration' in p or p.endswith('DATA_LAYOUT.md') for p in b['paths']) else 1, b['prior_bytes'], b['group']))
    plan = {'schema': 1, 'created_at': sb.now(), 'profile': 'market-data', 'box_id': profile.data['box_id'],
            'source_roots': list(map(str, roots)), 'batches': batches,
            'prior_census': str(census), 'prior_census_sha256': digest(census),
            'inventory_note': 'Prior counts guide ordering only. Every batch receives fresh pre/post inventories and remote path/size reconciliation.',
            'source_deletion': False, 'atomic_snapshot': False,
            'volume_uuid': '087E2AA1-5151-322D-8C09-9852ECD979B5'}
    save('PLAN.json', plan)
    print(json.dumps({'batches': len(batches), 'prior_files': sum(b['prior_files'] for b in batches), 'prior_bytes': sum(b['prior_bytes'] for b in batches)}), flush=True)


def temporary_dns_route(repo):
    """Use a recorded DNS address only while local NXDOMAIN is cached.

    The SSH destination name and strict published host-key check remain intact.
    No system DNS/hosts configuration is modified. The override expires in one hour.
    """
    host = repo.profile.data.get('host')
    if not host:
        return repo
    try:
        socket.getaddrinfo(host, 23, type=socket.SOCK_STREAM)
        return repo
    except socket.gaierror:
        route = json.loads((HERE / 'DNS_FALLBACK.json').read_text())
        if route['host'] != host or time.time() > route['expires_epoch']:
            raise RuntimeError('Temporary verified DNS route is absent, mismatched or expired.')
        address = str(ipaddress.ip_address(route['address']))
        for i, arg in enumerate(repo.base):
            if i == 0 or repo.base[i - 1] != '-o':
                continue
            decoded = next(sb.csv.reader([arg]))
            if len(decoded) == 1 and decoded[0].startswith('sftp.command='):
                command = shlex.split(decoded[0].removeprefix('sftp.command='))
                command[1:1] = ['-o', f'ProxyCommand=/usr/bin/nc {address} 23']
                repo.base[i] = sb.restic_option('sftp.command=' + shlex.join(command))
                return repo
        raise RuntimeError('No explicit SSH command is available for the temporary DNS route.')


class ProgressRepository(sb.Repository):
    def __init__(self, profile, batch, state):
        super().__init__(profile)
        temporary_dns_route(self)
        self.batch, self.state = batch, state

    def run(self, args, capture=False):
        if not args or args[0] != 'backup' or capture:
            return super().run(args, capture=capture)
        command = self.base + ['--json'] + list(args)
        logfile = HERE / 'logs' / (self.batch + '.jsonl')
        logfile.parent.mkdir(exist_ok=True)
        last = 0.0
        with logfile.open('a') as log:
            child = subprocess.Popen(command, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.state['restic_pid'] = child.pid
            save('STATE.json', self.state)
            try:
                for line in child.stdout:
                    try:
                        event = json.loads(line)
                    except ValueError:
                        event = {'message_type': 'text', 'message': line.rstrip()}
                    is_status = event.get('message_type') == 'status'
                    if not is_status or time.monotonic() - last >= 10:
                        log.write(json.dumps({'observed_at': sb.now(), **event}) + '\n')
                        log.flush()
                        if is_status or event.get('message_type') == 'summary':
                            self.state['progress'] = event
                            self.state['updated_at'] = sb.now()
                            save('STATE.json', self.state)
                            last = time.monotonic()
                return subprocess.CompletedProcess(command, child.wait())
            finally:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()


def prepare_prior():
    plan = json.loads((HERE / 'PLAN.json').read_text())
    if (HERE / 'PRIOR_EXPECTED_BINDING.json').exists():
        raise RuntimeError('Prior binding already exists; retain its identity.')
    directory = HERE / 'prior_expected'
    directory.mkdir(exist_ok=True)
    selections = {str(Path(p).relative_to(MOUNT)): b['group'] for b in plan['batches'] for p in b['paths']}
    counts = {b['group']: 0 for b in plan['batches']}
    with contextlib.ExitStack() as stack:
        outputs = {group: stack.enter_context(gzip.open(directory / (group + '.jsonl.gz'), 'wt')) for group in counts}
        with gzip.open(plan['prior_census'], 'rt') as stream:
            for line in stream:
                row = json.loads(line)
                prefix = row['path']
                while prefix and prefix not in selections:
                    prefix = prefix.rpartition('/')[0]
                if prefix:
                    group = selections[prefix]
                    outputs[group].write(json.dumps([str(MOUNT / row['path']), row['bytes'], row['mtime_ns']], separators=(',', ':')) + '\n')
                    counts[group] += 1
    if any(counts[b['group']] != b['prior_files'] for b in plan['batches']):
        raise RuntimeError('Prior counts changed while preparing binding.')
    if digest(plan['prior_census']) != plan['prior_census_sha256']:
        raise RuntimeError('Prior census identity changed.')
    save('PRIOR_EXPECTED_BINDING.json', {'plan_sha256': digest(HERE / 'PLAN.json'),
        'created_at': sb.now(), 'files': {g: {'files': n, 'sha256': digest(directory / (g + '.jsonl.gz'))} for g, n in counts.items()}})
    print(json.dumps({'prior_files_bound': sum(counts.values()), 'batches': len(counts)}), flush=True)


def write_handles(paths):
    run = subprocess.run(['lsof', '-nP', '-Fpcfan', '+f', '--', str(MOUNT)], capture_output=True, text=True)
    if run.returncode not in (0, 1):
        raise RuntimeError('Could not inspect open source files; see lsof.')
    access = None
    hits = []
    for line in run.stdout.splitlines():
        if line.startswith('f'):
            access = None
        elif line.startswith('a'):
            access = line[1:]
        elif line.startswith('n') and access in ('w', 'u'):
            path = Path(line[1:])
            if any(path == Path(p) or path.is_relative_to(Path(p)) for p in paths):
                hits.append(str(path))
    return hits


def census_into(db, paths, out, stage):
    files = size = directories = 0
    with gzip.open(out, 'wt') as stream:
        for path, st in inventory(paths):
            kind, length, mtime, inode = identity(st)
            if kind == 'other':
                raise RuntimeError(f'Unsupported source entry: {path}')
            row = (path, kind, length, mtime, inode)
            # File IDs are unsigned 64-bit values; SQLite INTEGER is signed.
            # exFAT also synthesizes changing IDs for empty files. Retain the
            # observed ID in the manifest, but compare empty files by path,
            # type, zero length and mtime. Their content is necessarily empty.
            inode_key = None if kind == 'file' and length == 0 else str(inode)
            comparison = (kind, length, mtime, inode_key)
            stream.write(json.dumps(row, separators=(',', ':')) + '\n')
            if stage == 'pre':
                db.execute('INSERT INTO entries(path,kind,bytes,mtime,inode) VALUES(?,?,?,?,?)', (path, *comparison))
            else:
                previous = db.execute('SELECT kind,bytes,mtime,inode FROM entries WHERE path=?', (path,)).fetchone()
                if previous != comparison:
                    raise RuntimeError(f'Source changed during transfer: {path}')
                db.execute('UPDATE entries SET post=1 WHERE path=?', (path,))
            files += kind == 'file'
            directories += kind == 'dir'
            size += length
    db.commit()
    return {'files': files, 'directories': directories, 'bytes': size, 'manifest_sha256': digest(out)}


def create_coverage_schema(db):
    db.execute('CREATE TABLE entries(path TEXT PRIMARY KEY,kind TEXT,bytes INTEGER,mtime INTEGER,inode TEXT,remote INTEGER DEFAULT 0,post INTEGER DEFAULT 0)')


def validate_completed(receipt, batch, plan_hash, repository_id, snapshots):
    if receipt['plan_sha256'] != plan_hash or receipt['repository_id'] != repository_id:
        raise RuntimeError('Completed receipt belongs to a different plan/repository.')
    snapshot = snapshots.get(receipt['snapshot_id'])
    required_tags = {sb.COMPLETE, 'group:' + batch['group']}
    if (snapshot is None or not required_tags.issubset(snapshot.get('tags', []))
            or sorted(snapshot.get('paths', [])) != sorted(batch['paths'])
            or receipt['paths'] != batch['paths']):
        raise RuntimeError('Completed snapshot is absent or its tags/source paths differ.')


def reconcile_remote(repo, snapshot, db, paths, out):
    command = repo.base + ['ls', '--json', snapshot]
    count = 0
    with gzip.open(out, 'wt') as stream, (out.parent / 'remote_ls.stderr').open('w') as errors:
        child = subprocess.Popen(command, env=repo.env, stdout=subprocess.PIPE, stderr=errors, text=True)
        try:
            for line in child.stdout:
                row = json.loads(line)
                path = row.get('path')
                if path is None or not any(Path(path) == Path(p) or Path(path).is_relative_to(Path(p)) for p in paths):
                    continue
                stream.write(line)
                expected = db.execute('SELECT kind,bytes,remote FROM entries WHERE path=?', (path,)).fetchone()
                size = row.get('size', 0) if row.get('type') == 'file' else 0
                if expected is None or expected[:2] != (row.get('type'), size) or expected[2]:
                    raise RuntimeError(f'Remote path/type/size mismatch: {path}')
                db.execute('UPDATE entries SET remote=1 WHERE path=?', (path,))
                count += 1
            if child.wait():
                raise RuntimeError('Could not read complete remote snapshot listing.')
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait()
    db.commit()
    missing = db.execute('SELECT path FROM entries WHERE remote=0 LIMIT 1').fetchone()
    if missing:
        raise RuntimeError(f'Source missing from remote snapshot: {missing[0]}')
    return {'entries_matched': count, 'manifest_sha256': digest(out)}


def uploaded_receipt(profile, group, started):
    rows = [json.loads(p.read_text()) for p in (profile.directory / 'receipts').glob('upload-*.json')]
    matches = [r for r in rows if r['group'] == group and r['started_at'] >= started and not r['dry_run']]
    if len(matches) != 1 or matches[0]['status'] != 'complete':
        raise RuntimeError('No uniquely completed upload receipt.')
    return matches[0]


def trial():
    profile = sb.Profile(sb.DEFAULT_ROOT / 'market-data')
    selected = json.loads((HERE / 'TRIAL_SELECTION.json').read_text())
    paths = [str(MOUNT / p) for p in selected]
    before = [{'path': p, 'bytes': Path(p).stat().st_size, 'sha256': digest(p)} for p in paths]
    save('TRIAL_SOURCE_HASHES.json', before)
    state = {'status': 'TRIAL_RUNNING', 'pid': os.getpid(), 'started_at': sb.now(), 'source_deletions': 0}
    with sb.locked(profile.directory):
        repo = ProgressRepository(profile, 'live-trial', state)
        repo.bind()
        db = sqlite3.connect(':memory:')
        create_coverage_schema(db)
        census_into(db, paths, HERE / 'TRIAL_SOURCE_BEFORE.jsonl.gz', 'pre')
        args = sb.parser().parse_args(['upload', *paths, '--group', 'toshiba-live-trial', '--require-mount', str(MOUNT), '--dry-run'])
        sb.upload(repo, args)
        args.dry_run = False
        started = sb.now()
        sb.upload(repo, args)
        receipt = uploaded_receipt(profile, args.group, started)
        matched = reconcile_remote(repo, receipt['snapshot_id'], db, paths, HERE / 'TRIAL_REMOTE.jsonl.gz')
        census_into(db, paths, HERE / 'TRIAL_SOURCE_AFTER.jsonl.gz', 'post')
        if db.execute('SELECT count(*) FROM entries WHERE post=0').fetchone()[0]:
            raise RuntimeError('Trial source disappeared.')
        repo.successful(['check', '--read-data'])
        target = Path.home() / '.cache' / ('toshiba-hetzner-trial-' + uuid.uuid4().hex)
        args = sb.parser().parse_args(['recover', receipt['snapshot_id'], '--target', str(target)])
        sb.recover(repo, args)
        for row in before:
            restored = target / row['path'].lstrip('/')
            if digest(restored) != row['sha256'] or digest(row['path']) != row['sha256']:
                raise RuntimeError(f'Trial SHA-256 comparison failed: {row["path"]}')
        result = {'status': 'PASS', 'finished_at': sb.now(), 'repository_id': profile.data['repository_id'],
                  'snapshot_id': receipt['snapshot_id'], 'files': len(before), 'bytes': sum(r['bytes'] for r in before),
                  'remote_all_packs_read': True, 'restore_verified': True, 'sha256_matches': True,
                  'remote_manifest_reconciliation': matched,
                  'restored_target': str(target), 'source_deletions': 0}
        save('LIVE_TRIAL.json', result)
        save('STATE.json', {**state, 'status': 'TRIAL_VERIFIED', 'updated_at': sb.now()})
        print(json.dumps(result), flush=True)


def run_transfer():
    plan_path = HERE / 'PLAN.json'
    plan = json.loads(plan_path.read_text())
    trial_result = json.loads((HERE / 'LIVE_TRIAL.json').read_text())
    profile = sb.Profile(sb.DEFAULT_ROOT / plan['profile'])
    if trial_result['status'] != 'PASS' or trial_result['repository_id'] != profile.data.get('repository_id') or plan['box_id'] != profile.data['box_id']:
        raise RuntimeError('Verified live trial and planned destination must match.')
    state = {'status': 'RUNNING', 'pid': os.getpid(), 'started_at': sb.now(), 'updated_at': sb.now(),
             'plan_sha256': digest(plan_path), 'repository_id': profile.data['repository_id'],
             'source_deletions': 0, 'completed_batches': [], 'total_batches': len(plan['batches'])}
    save('STATE.json', state)
    with sb.locked(profile.directory):
        # Reconcile prior completed batches against one current remote listing.
        # This avoids reconnecting twice per completed batch during resumption.
        resume_repo = temporary_dns_route(sb.Repository(profile))
        resume_repo.bind()
        resume_snapshots = {s['id']: s for s in resume_repo.snapshots(sb.COMPLETE)}
        for batch in plan['batches']:
            group, paths = batch['group'], batch['paths']
            state.update(current_batch=group, phase='preflight', updated_at=sb.now(), progress=None)
            save('STATE.json', state)
            output = HERE / 'batches' / group
            output.mkdir(parents=True, exist_ok=True)
            completed = output / 'COMPLETE.json'
            if completed.exists():
                old = json.loads(completed.read_text())
                validate_completed(old, batch, state['plan_sha256'], state['repository_id'], resume_snapshots)
                state['completed_batches'].append(old)
                continue
            repo = ProgressRepository(profile, group, state)
            repo.bind()
            sb.check_sources(paths, profile, MOUNT)
            handles = write_handles(paths)
            if handles:
                raise RuntimeError('Selected source has an open write handle: ' + handles[0])
            if shutil.disk_usage(HERE).free < 800_000_000:
                raise RuntimeError('Less than 800 MB free on the Mac for transfer metadata and Restic temporary packs.')
            attempt = output / ('attempt-' + uuid.uuid4().hex)
            attempt.mkdir()
            with sqlite3.connect(attempt / 'coverage.sqlite3') as db:
                create_coverage_schema(db)
                state['phase'] = 'source_inventory_before'
                save('STATE.json', state)
                pre = census_into(db, paths, attempt / 'source_before.jsonl.gz', 'pre')
                expected = HERE / 'prior_expected' / (group + '.jsonl.gz')
                binding = json.loads((HERE / 'PRIOR_EXPECTED_BINDING.json').read_text())
                if binding['plan_sha256'] != state['plan_sha256'] or digest(expected) != binding['files'][group]['sha256']:
                    raise RuntimeError('Prior source manifest binding mismatch.')
                drift = []
                prior_count = 0
                with gzip.open(expected, 'rt') as stream:
                    for line in stream:
                        path, length, mtime = json.loads(line)
                        previous = db.execute('SELECT bytes,mtime FROM entries WHERE path=? AND kind=\'file\'', (path,)).fetchone()
                        if previous is None:
                            raise RuntimeError(f'File from the verified prior census is missing: {path}')
                        if previous != (length, mtime):
                            drift.append({'path': path, 'prior': [length, mtime], 'current': previous})
                        prior_count += 1
                if prior_count != batch['prior_files']:
                    raise RuntimeError('Prior source file count does not match the bound plan.')
                sb.write_json(attempt / 'PRIOR_RECONCILIATION.json', {'prior_files_present': prior_count,
                    'metadata_changed': drift, 'note': 'Changed current versions are uploaded and explicitly recorded; old bytes are not inferred from metadata.'})
                state.update(phase='upload', current_source_totals=pre, updated_at=sb.now())
                save('STATE.json', state)
                started = sb.now()
                print(json.dumps({'started_at': started, 'batch': group, **pre}), flush=True)
                args = sb.parser().parse_args(['upload', *paths, '--group', group, '--require-mount', str(MOUNT)])
                sb.upload(repo, args)
                receipt = uploaded_receipt(profile, group, started)
                state.update(phase='remote_manifest_reconciliation', updated_at=sb.now())
                save('STATE.json', state)
                remote = reconcile_remote(repo, receipt['snapshot_id'], db, paths, attempt / 'remote.jsonl.gz')
                state.update(phase='source_inventory_after', updated_at=sb.now())
                save('STATE.json', state)
                post = census_into(db, paths, attempt / 'source_after.jsonl.gz', 'post')
                missing = db.execute('SELECT path FROM entries WHERE post=0 LIMIT 1').fetchone()
                if missing or write_handles(paths):
                    raise RuntimeError('Source disappeared or acquired a writer during transfer.')
                result = {'status': 'CAPTURED_AND_RECONCILED', 'finished_at': sb.now(), 'group': group,
                          'plan_sha256': state['plan_sha256'], 'repository_id': state['repository_id'],
                          'paths': paths, 'snapshot_id': receipt['snapshot_id'], 'upload_receipt': receipt['run'],
                          'before': pre, 'after': post, 'remote': remote, 'evidence_directory': str(attempt),
                          'prior_census_files_present': prior_count, 'prior_metadata_changes': len(drift),
                          'empty_file_identity': 'Path, type, zero length and mtime; unstable exFAT empty-file IDs retained in manifests but not compared.',
                          'full_remote_readback': 'PENDING_FINAL_CHECK', 'source_deletions': 0}
                sb.write_json(completed, result)
            # Compressed exact inventories retain the evidence; this is a disposable lookup index.
            (attempt / 'coverage.sqlite3').unlink()
            state['completed_batches'].append(result)
            save('STATE.json', state)
        catalog = {'schema': 1, 'repository': profile.data['repository'],
            'repository_id': state['repository_id'], 'box_id': profile.data['box_id'],
            'source_roots': plan['source_roots'], 'batches': state['completed_batches'],
            'full_readback': 'PENDING_FINAL_CHECK', 'source_deletions': 0,
            'note': 'Recover each root using its recorded snapshot ID. Latest alone is not the full multi-batch archive.'}
        save('REMOTE_SOURCE_CATALOG.json', catalog)
        # Publish a fixed recovery catalogue before the final all-pack readback.
        publication = HERE / 'publication'
        publication.mkdir(exist_ok=True)
        for name in ('PLAN.json', 'REMOTE_SOURCE_CATALOG.json', 'LIVE_TRIAL.json', 'PRIOR_EXPECTED_BINDING.json', 'transfer_job.py'):
            shutil.copy2(HERE / name, publication / name)
        state.update(phase='publish_recovery_catalogue', updated_at=sb.now())
        save('STATE.json', state)
        repo = ProgressRepository(profile, 'transfer-catalogue', state)
        repo.bind()
        started = sb.now()
        args = sb.parser().parse_args(['upload', str(publication), '--group', 'toshiba-transfer-catalogue'])
        sb.upload(repo, args)
        state['catalogue_snapshot_id'] = uploaded_receipt(profile, args.group, started)['snapshot_id']
        state.update(status='VERIFYING_ALL_REMOTE_DATA', phase='restic_check_read_data', updated_at=sb.now())
        save('STATE.json', state)
        print(json.dumps({'phase': state['phase'], 'time': sb.now()}), flush=True)
        repo = temporary_dns_route(sb.Repository(profile))
        repo.bind()
        started = sb.now()
        with (HERE / 'FULL_READBACK.log').open('a') as log:
            result = subprocess.run(repo.base + ['check', '--read-data'], env=repo.env, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'Full remote readback failed: exit {result.returncode}')
        save('FULL_READBACK.json', {'status': 'PASS', 'started_at': started, 'finished_at': sb.now(),
                                  'repository_id': state['repository_id'], 'all_packs_read': True,
                                  'snapshot_ids': [b['snapshot_id'] for b in state['completed_batches']]})
        state.update(status='UPLOADED_AND_READBACK_VERIFIED', phase='retained_sources_pending_final_move_review', updated_at=sb.now())
        save('STATE.json', state)
        save('REMOTE_SOURCE_CATALOG.json', {**catalog, 'full_readback': 'FULL_READBACK.json',
                                           'catalogue_snapshot_id': state['catalogue_snapshot_id']})
        print(json.dumps({'status': state['status'], 'batches': len(state['completed_batches'])}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['plan', 'prepare', 'trial', 'run', 'status'])
    args = parser.parse_args()
    if args.command == 'status':
        print((HERE / 'STATE.json').read_text())
        return 0
    try:
        with sb.locked(HERE / 'job-lock'):
            {'plan': make_plan, 'prepare': prepare_prior, 'trial': trial, 'run': run_transfer}[args.command]()
        return 0
    except BaseException as exc:
        previous = json.loads((HERE / 'STATE.json').read_text()) if (HERE / 'STATE.json').exists() else {}
        save('STATE.json', {**previous, 'status': 'STOPPED_INCOMPLETE', 'updated_at': sb.now(),
                            'error_type': type(exc).__name__, 'error': str(exc), 'source_deletions': 0})
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
