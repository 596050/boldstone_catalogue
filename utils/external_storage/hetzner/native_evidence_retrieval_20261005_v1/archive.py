"""Queue this exact frozen batch behind existing storage work, then verify recovery.

Uses the existing wrapper's profile lock, source guards, completed snapshot tags,
and restore --verify. Never unlocks, deletes, provisions, or switches profiles.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import storage_box as sb


def now():
    return datetime.now(timezone.utc).isoformat()


def save(name, value):
    with (HERE / name).open('x') as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')


def check(path, expected):
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise RuntimeError('Nonregular frozen file: ' + str(p))
    with p.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    if p.stat().st_size != expected['bytes'] or digest != expected['sha256']:
        raise RuntimeError('Frozen content mismatch: ' + str(p))


def main(wait_seconds):
    manifest_bytes = (HERE / 'MANIFEST.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    profile_dir = Path.home() / '.config/marketmaker-storagebox/market-data'
    save('QUEUE_START.json', dict(at_utc=now(), pid=os.getpid(), wait_seconds=wait_seconds,
                                group=manifest['group'], manifest_sha256=manifest_sha256,
                                status='QUEUED', no_source_deletions=True))
    started = time.monotonic()
    while True:
        lock = sb.locked(profile_dir)
        try:
            lock.__enter__()
            break
        except sb.Error as exc:
            if str(exc) != 'Another operation is using this profile.':
                raise
            if time.monotonic() - started >= wait_seconds:
                save('QUEUE_DEFERRED.json', dict(at_utc=now(), status='DEFERRED_PROFILE_BUSY',
                                               upload_attempted=False, no_source_deletions=True))
                print('DEFERRED_PROFILE_BUSY', flush=True)
                return
            print('WAITING_FOR_EXISTING_STORAGE_OPERATION', flush=True)
            time.sleep(max(0, min(20, wait_seconds - (time.monotonic() - started))))
    try:
        for row in manifest['files']:
            check(row['path'], row)
        if (HERE / 'MANIFEST.json').read_bytes() != manifest_bytes:
            raise RuntimeError('Manifest changed while queued')
        profile = sb.Profile(profile_dir)
        repo = sb.Repository(profile)
        with (HERE / 'TRANSFER.log').open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            os.fchmod(log.fileno(), 0o600)
            repo.bind()
            if repo.profile.data['repository_id'] != manifest['repository_id']:
                raise RuntimeError('Repository identity changed')
            selected_paths = [row['path'] for row in manifest['files']] + [str(HERE / 'MANIFEST.json')]
            if len(selected_paths) != len(set(selected_paths)):
                raise RuntimeError('Duplicate manifest selection')
            args = SimpleNamespace(paths=selected_paths,
                                   require_mount='/Volumes/Toshiba 2TB', group=manifest['group'], dry_run=False)
            sb.upload(repo, args)
            receipts = []
            for path in (profile_dir / 'receipts').glob('upload-*.json'):
                r = json.loads(path.read_text())
                if r.get('group') == manifest['group'] and r.get('dry_run') is False:
                    receipts.append(r)
            if len(receipts) != 1 or receipts[0]['status'] != 'complete':
                raise RuntimeError('Expected exactly one completed upload')
            uploaded = receipts[0]
            save('UPLOAD.json', uploaded)
            target = Path('/Users/tprice/Downloads/native-evidence-recovery-20261005-v1')
            if target.exists():
                raise RuntimeError('Recovery target already exists')
            target.mkdir(mode=0o700)
            recovery = SimpleNamespace(snapshot=uploaded['snapshot_id'], group=manifest['group'],
                                       target=str(target), subtree=None, include=[], resume=False, dry_run=False)
            sb.recover(repo, recovery)
        restored_paths = {str(p.relative_to(target)) for p in target.rglob('*') if p.is_file() or p.is_symlink()}
        if restored_paths != {str(Path(p).relative_to('/')) for p in selected_paths}:
            raise RuntimeError('Recovered file roster differs from exact selection')
        for row in manifest['files']:
            check(target / Path(row['path']).relative_to('/'), row)
            check(row['path'], row)
        recovered_manifest = target / (HERE / 'MANIFEST.json').relative_to('/')
        if recovered_manifest.read_bytes() != manifest_bytes or (HERE / 'MANIFEST.json').read_bytes() != manifest_bytes:
            raise RuntimeError('Recovered manifest differs')
        save('REMOTE_READBACK.json', dict(at_utc=now(), status='PASS',
             snapshot_id=uploaded['snapshot_id'], repository_id=manifest['repository_id'],
             group=manifest['group'], files_verified=len(manifest['files']),
             manifest_sha256=manifest_sha256, exact_restored_file_roster=True,
             bytes_verified=sum(r['bytes'] for r in manifest['files']), recovery_target=str(target),
             verification='Completed snapshot restored with --verify; every manifest file SHA-256 and source rechecked.',
             historical_data_completeness_established=False, no_source_deletions=True))
        print('PASS_REMOTE_RECOVERY_AND_EVERY_FILE_SHA256', flush=True)
    finally:
        lock.__exit__(None, None, None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-seconds', type=int, default=3600)
    options = parser.parse_args()
    if options.wait_seconds < 0:
        parser.error('wait-seconds must be nonnegative')
    try:
        main(options.wait_seconds)
    except BaseException as exc:
        # No arbitrary exception/command text, request headers or credentials.
        if not (HERE / 'ARCHIVE_FAILURE.json').exists():
            save('ARCHIVE_FAILURE.json', dict(at_utc=now(), status='FAILED', error_type=type(exc).__name__))
        raise
