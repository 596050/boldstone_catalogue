"""Parallel append and exact-snapshot recovery with normal Restic repository locks.

Uses the existing immutable connection configuration without changing it. A
task-local lock prevents duplicate runs. Snapshot tagging remains an exclusive
operation, separate from data transfer and content verification.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT.parent))
import storage_box as sb

EXPECTED_MANIFEST = '78aeef49638101ad5f4614bb256b42ee189917dadf083702f5d0018cb65e1b21'
PROFILE = Path.home() / '.config/marketmaker-storagebox/market-data'
GROUP = 'native-evidence-retrieval-20261005-parallel-01'
TARGET = Path('/Users/tprice/Downloads/native-evidence-parallel-recovery-20261005-v1')


def now():
    return datetime.now(timezone.utc).isoformat()


def save(name, value):
    with (HERE / name).open('x') as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')


def ref(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise RuntimeError('Expected real regular source file')
    before = path.stat()
    with path.open('rb') as f:
        sha = hashlib.file_digest(f, 'sha256').hexdigest()
    after = path.stat()
    if (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size):
        raise RuntimeError('Source changed while hashing')
    return dict(path=str(path), bytes=after.st_size, sha256=sha)


def verify_sources(rows):
    for row in rows:
        if ref(row['path']) != row:
            raise RuntimeError('Source identity changed')


def command(repo, args, name):
    save(name + '_START.json', dict(at_utc=now(), operation=args[0], pid=os.getpid(),
                                  repository_locks_enabled=True))
    with (HERE / (name + '.stdout')).open('x') as out, (HERE / (name + '.stderr')).open('x') as err:
        os.fchmod(out.fileno(), 0o600)
        os.fchmod(err.fileno(), 0o600)
        process = subprocess.run(repo.base + args, env=repo.env, stdout=out, stderr=err)
    save(name + '_EXIT.json', dict(at_utc=now(), exit_code=process.returncode,
                                 stdout=ref(HERE / (name + '.stdout')), stderr=ref(HERE / (name + '.stderr'))))
    return process.returncode


def main():
    with sb.locked(HERE):
        if (HERE / 'PLAN.json').exists():
            raise RuntimeError('Existing attempt must be inspected; never duplicate automatically')
        old_manifest = PARENT / 'MANIFEST.json'
        if ref(old_manifest)['sha256'] != EXPECTED_MANIFEST:
            raise RuntimeError('Original manifest changed')
        old = json.loads(old_manifest.read_text())
        replaced = json.loads((PARENT / 'QUEUE_REPLACED.json').read_text())
        if replaced['status'] != 'OWN_QUEUED_WORKER_REPLACED_BEFORE_TRANSFER':
            raise RuntimeError('Original worker not replaced safely')
        rows = list(old['files']) + [ref(p) for p in [old_manifest, PARENT / 'CASH_LABEL_READBACK.json',
                                                     PARENT / 'QUEUE_REPLACED.json', Path(__file__)]]
        if len({r['path'] for r in rows}) != len(rows):
            raise RuntimeError('Duplicate file path')
        if len(rows) > 500 or sum(r['bytes'] for r in rows) > 32 * 1024 * 1024:
            raise RuntimeError('Bounded batch limit exceeded')
        verify_sources(rows)
        profile = sb.Profile(PROFILE)
        config_ref = ref(PROFILE / 'profile.json')
        if profile.data.get('repository_id') != old['repository_id']:
            raise RuntimeError('Configured repository identity differs')
        run_tag = 'run:native-parallel-' + uuid.uuid4().hex
        save('PLAN.json', dict(at_utc=now(), group=GROUP, run_tag=run_tag,
             repository_id=old['repository_id'], original_manifest_sha256=EXPECTED_MANIFEST,
             files=rows, file_count=len(rows), logical_bytes=sum(r['bytes'] for r in rows),
             repository_locks_enabled=True, local_lock='Task-specific; original profile is read only.',
             authorization='User explicitly requested this batch be transferred in parallel.',
             no_source_deletions=True, no_credentials_copied=True,
             no_other_workers_interrupted=True, concurrent_sftp_connections=1,
             recovery_target=str(TARGET)))
        selected = rows + [ref(HERE / 'PLAN.json')]
        paths = [r['path'] for r in selected]
        sb.check_sources(paths, profile, '/Volumes/Toshiba 2TB')
        if TARGET.exists() or any(p.is_symlink() for p in [TARGET, *TARGET.parents]):
            raise RuntimeError('Recovery target exists or contains symlink component')
        repo = sb.Repository(profile)
        repo.base = ['sftp.connections=1' if x == 'sftp.connections=2' else x for x in repo.base]
        repo.bind()
        if ref(PROFILE / 'profile.json') != config_ref:
            raise RuntimeError('Connection configuration changed')
        print('PARALLEL_BACKUP_STARTED', flush=True)
        args = ['backup', '--retry-lock', '2m', '--force', '--json', '--host', 'native-evidence-parallel',
                '--tag', sb.PENDING, '--tag', 'group:' + GROUP, '--tag', run_tag, '--', *paths]
        code = command(repo, args, 'BACKUP')
        if code != 0:
            raise RuntimeError('Backup did not complete; preserve pending attempt')
        summaries = [json.loads(l) for l in (HERE / 'BACKUP.stdout').read_text().splitlines()
                     if l.startswith('{')]
        summary = [x for x in summaries if x.get('message_type') == 'summary']
        snapshots = repo.snapshots(run_tag)
        if len(summary) != 1 or len(snapshots) != 1 or summary[0].get('snapshot_id') != snapshots[0]['id']:
            raise RuntimeError('Backup identity not uniquely corroborated')
        snap = snapshots[0]
        snapshot_id = snap['id']
        tree = snap.get('tree')
        if not isinstance(tree, str) or len(tree) != 64 or any(c not in '0123456789abcdef' for c in tree):
            raise RuntimeError('Snapshot tree identity missing or malformed')
        if set(snap.get('paths', [])) != set(paths):
            raise RuntimeError('Snapshot selected paths differ')
        if sb.PENDING not in snap.get('tags', []):
            raise RuntimeError('Expected pending snapshot')
        save('UPLOAD.json', dict(at_utc=now(), status='UPLOADED_CONTENT_VERIFICATION_PENDING',
             repository_id=old['repository_id'], snapshot_id=snapshot_id, group=GROUP,
             restic_exit_code=0, files=len(selected), logical_bytes=sum(r['bytes'] for r in selected),
             snapshot_tree=snap.get('tree'), completion_tag=False))
        verify_sources(selected)
        TARGET.mkdir(mode=0o700)
        print('PARALLEL_EXACT_SNAPSHOT_RESTORE_STARTED', flush=True)
        code = command(repo, ['restore', '--retry-lock', '2m', snapshot_id, '--target', str(TARGET),
                              '--verify', '--json'], 'RESTORE')
        if code != 0:
            raise RuntimeError('Restore or built-in content verification failed')
        actual = {str(p.relative_to(TARGET)) for p in TARGET.rglob('*') if p.is_file() or p.is_symlink()}
        if actual != {str(Path(p).relative_to('/')) for p in paths}:
            raise RuntimeError('Restored file roster differs')
        for row in selected:
            restored = ref(TARGET / Path(row['path']).relative_to('/'))
            if any(restored[k] != row[k] for k in ['bytes', 'sha256']):
                raise RuntimeError('Restored source SHA-256 differs')
        verify_sources(selected)
        if ref(PROFILE / 'profile.json') != config_ref:
            raise RuntimeError('Connection configuration changed')
        save('REMOTE_READBACK.json', dict(at_utc=now(), status='PASS',
             repository_id=old['repository_id'], snapshot_id=snapshot_id, group=GROUP,
             files_verified=len(selected), bytes_verified=sum(r['bytes'] for r in selected),
             restored_exact_file_roster=True, source_rehash_passed=True,
             recovery_target=str(TARGET), original_manifest_sha256=EXPECTED_MANIFEST,
             verification='Restic restore --verify plus independent per-file source SHA-256 and exact roster.',
             complete_tag_pending=True, historical_broker_comparison_complete=False,
             no_source_deletions=True))
        print('PASS_PARALLEL_UPLOAD_AND_RESTORED_FILE_HASHES', flush=True)
        code = command(repo, ['tag', '--retry-lock', '2m', '--add', sb.COMPLETE, '--remove', sb.PENDING,
                              snapshot_id], 'TAG')
        if code != 0:
            save('TAG_PENDING.json', dict(at_utc=now(), status='CONTENT_VERIFIED_TAG_FINALIZATION_PENDING',
                 repository_id=old['repository_id'], snapshot_id=snapshot_id, group=GROUP,
                 run_tag=run_tag, tag_exit_code=code))
            print('CONTENT_VERIFIED_TAG_FINALIZATION_PENDING', flush=True)
            return
        completed = repo.snapshots(run_tag + ',' + sb.COMPLETE)
        if len(completed) != 1 or completed[0].get('tree') != snap.get('tree') or completed[0].get('paths') != snap.get('paths'):
            raise RuntimeError('Tagged snapshot content identity changed')
        if sb.PENDING in completed[0].get('tags', []):
            raise RuntimeError('Completed snapshot still pending')
        save('COMPLETE.json', dict(at_utc=now(), status='PASS_COMPLETE_SNAPSHOT_AND_RESTORED_SHA256',
             repository_id=old['repository_id'], snapshot_id=completed[0]['id'], verified_snapshot_id=snapshot_id,
             group=GROUP, files_verified=len(selected), bytes_verified=sum(r['bytes'] for r in selected),
             snapshot_tree=completed[0].get('tree'), no_source_deletions=True,
             readback=ref(HERE / 'REMOTE_READBACK.json')))
        print('PASS_COMPLETE_SNAPSHOT_AND_RESTORED_SHA256', flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if not (HERE / 'FAILURE.json').exists():
            save('FAILURE.json', dict(at_utc=now(), status='FAILED', error_type=type(exc).__name__,
                                     reason=str(exc) if isinstance(exc, RuntimeError) else None))
        print(type(exc).__name__, flush=True)
        raise SystemExit(1)
