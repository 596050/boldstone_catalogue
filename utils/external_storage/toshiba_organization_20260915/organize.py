#!/usr/bin/env python3
"""Journalled, no-overwrite, same-volume moves; never recursively deletes data."""
from __future__ import annotations
import argparse
from collections import Counter
import ctypes
import errno
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'research/utility/toshiba_data_manifest_20260913_v1'))
import bulk_metadata

MOUNT = Path('/Volumes/Toshiba 2TB')
VOLUME_UUID = '087E2AA1-5151-322D-8C09-9852ECD979B5'
USER_HISTORY_PATH = None
USER_HISTORY = []


class ActiveSource(RuntimeError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


def append_event(path, value):
    with path.open('a') as f:
        f.write(json.dumps({'at_utc': utc(), **value}, separators=(',', ':')) + '\n')
        f.flush(); os.fsync(f.fileno())


def validate_volume(mount=MOUNT):
    if not os.path.ismount(mount):
        raise RuntimeError('Expected Toshiba volume is not mounted')
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(mount)], timeout=20))
    if info.get('VolumeUUID') != VOLUME_UUID or info.get('WritableVolume') is not True:
        raise RuntimeError('Wrong volume identity or volume is not writable')
    return info


def safe_path(relative, mount=MOUNT):
    relative = Path(relative)
    if relative.is_absolute() or not relative.parts or any(p in {'.', '..'} for p in relative.parts):
        raise ValueError('Unsafe relative path')
    result = mount / relative
    current = mount
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f'Symlink in move path: {current}')
    return result


def no_replace_rename(source, target):
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    if source.stat(follow_symlinks=False).st_dev != target.parent.stat().st_dev:
        raise RuntimeError('Cross-filesystem copy/delete is forbidden')
    # Darwin RENAME_EXCL refuses a concurrent destination collision atomically.
    libc = ctypes.CDLL(None, use_errno=True)
    libc.renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    libc.renamex_np.restype = ctypes.c_int
    if libc.renamex_np(os.fsencode(source), os.fsencode(target), 4):
        e = ctypes.get_errno()
        if e == errno.ENOTSUP:
            # Apple's exFAT driver rejects RENAME_EXCL. The CLI owns an
            # exclusive migration lock and the destination namespace has no
            # published consumers during migration. Never overwrite an
            # observed target; ordinary rename preserves the same data extents.
            # This fallback is not an atomic no-clobber primitive against an
            # unrelated process writing the same new destination concurrently.
            if target.exists() or target.is_symlink():
                raise FileExistsError(target)
            os.rename(source, target)
            return 'rename_exfat_under_exclusive_migration_lock'
        raise OSError(e, os.strerror(e), str(target))
    return 'renamex_np_exclusive'


def sample_digest(path, size):
    with path.open('rb') as f:
        if size <= 131072:
            data = f.read()
            if len(data) != size:
                raise RuntimeError(f'File changed during checksum: {path}')
            return {'kind': 'full_sha256', 'sha256': hashlib.sha256(data).hexdigest()}
        first = f.read(65536)
        f.seek(size - 65536)
        last = f.read(65536)
        return {'kind': 'first_and_last_64KiB_sha256', 'sha256': hashlib.sha256(first + last).hexdigest()}


def inventory(source, output, sample_limit=16):
    """Every entry, without following links; allocation-chain walks are avoided.

    Content samples supplement the identity proof of a same-volume rename. This
    is deliberately not represented as a full payload hash or media-health scan.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + '.partial')
    counts = Counter()
    # Commutative 256-bit digest permits order-independent namespace comparison.
    total_digest = 0
    sample_count = 0
    stack = [(source, '')]
    try:
        root_descriptor = os.open(source, os.O_RDONLY | os.O_DIRECTORY)
    except NotADirectoryError:
        root_is_directory = False
    else:
        root_is_directory = True
        os.close(root_descriptor)
    sample_names = []
    last_progress = time.monotonic()
    with gzip.open(partial, 'wt', compresslevel=3) as f:
        while stack:
            directory, prefix = stack.pop()
            if directory == source and not root_is_directory:
                st = directory.lstat()
                items = [{'name': '', 'stat': st, 'valid': True}]
            else:
                # Empty-file IDs on exFAT are synthetic and deliberately excluded
                # from the identity digest. Avoid an expensive lstat for each one.
                items = bulk_metadata.entries(directory, stat_empty_files=False)
            for item in items:
                name, st = item['name'], item['stat']
                path = directory / name if name else directory
                rel = str(Path(prefix) / name) if name else '.'
                if not item['valid']:
                    st = path.lstat()
                kind = 'file' if stat.S_ISREG(st.st_mode) else 'directory' if stat.S_ISDIR(st.st_mode) else 'symlink' if stat.S_ISLNK(st.st_mode) else 'special'
                if kind == 'special':
                    raise RuntimeError(f'Unsupported special entry: {path}')
                row = {'relative': rel, 'kind': kind}
                counts[kind] += 1
                if kind == 'directory':
                    stack.append((path, rel))
                elif kind == 'file':
                    row.update(bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                               inode=st.st_ino if st.st_size else None)
                    counts['bytes'] += st.st_size
                    # Choose deterministic samples independent of directory enumeration order.
                    if (sample_count == 0 or int(hashlib.sha256(rel.encode()).hexdigest()[:8], 16) % 10000 < 10
                            or rel == '.') and sample_count < sample_limit:
                        before = (st.st_size, st.st_mtime_ns)
                        row['sample'] = sample_digest(path, st.st_size)
                        after = path.stat()
                        if before != (after.st_size, after.st_mtime_ns):
                            raise RuntimeError(f'File changed during inventory: {path}')
                        sample_names.append(rel)
                        sample_count += 1
                else:
                    row['link_target'] = os.readlink(path)
                encoded = json.dumps(row, sort_keys=True, separators=(',', ':'))
                f.write(encoded + '\n')
                # Sample selection/order is separately replayed, not part of namespace digest.
                identity = dict(row); identity.pop('sample', None)
                total_digest = (total_digest + int.from_bytes(hashlib.sha256(
                    json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).digest(), 'big')) % (1 << 256)
                if time.monotonic() - last_progress > 10:
                    print(json.dumps({'inventory': str(source), 'counts': dict(counts), 'at_utc': utc()}), flush=True)
                    last_progress = time.monotonic()
    with partial.open('rb') as f:
        os.fsync(f.fileno())
    os.replace(partial, output)
    return {'counts': dict(counts), 'namespace_identity_sum256': f'{total_digest:064x}',
            'samples': sample_names, 'inventory': str(output), 'at_utc': utc()}


def check_samples(source, before_inventory):
    checked = 0
    with gzip.open(before_inventory, 'rt') as f:
        for line in f:
            row = json.loads(line)
            if 'sample' in row:
                path = source if row['relative'] == '.' else source / row['relative']
                if sample_digest(path, row['bytes']) != row['sample']:
                    raise RuntimeError(f'Content sample differs after rename: {path}')
                checked += 1
    return checked


def retain_live_users(current, previous, births):
    """A reader remains a fence between open calls, until its process exits."""
    retained = {}
    for row in previous:
        if row.get('process_birth') and births.get(row['pid']) == row['process_birth']:
            retained[(row['pid'], row['path'])] = row
    for row in current:
        row = dict(row, process_birth=births.get(row['pid']))
        retained[(row['pid'], row['path'])] = row
    return list(retained.values())


def active_paths(mount=MOUNT):
    global USER_HISTORY
    result = subprocess.run(['lsof', '-nP', '-b', '-Fpcfan', str(mount)], capture_output=True, text=True, timeout=25)
    if result.returncode not in {0, 1}:
        raise RuntimeError('Cannot inspect open files safely')
    rows, pid, command, access = [], None, None, None
    for line in result.stdout.splitlines():
        if line.startswith('p'): pid = int(line[1:])
        elif line.startswith('c'): command = line[1:]
        elif line.startswith('a'): access = line[1:]
        elif line.startswith('n') and line[1:].startswith(str(mount) + '/'):
            rows.append({'pid': pid, 'command': command, 'access': access, 'path': line[1:]})
    images = plistlib.loads(subprocess.check_output(['hdiutil', 'info', '-plist'], timeout=20))
    for item in images.get('images', []):
        for field in ['image-path', 'shadow-path']:
            if str(item.get(field, '')).startswith(str(mount) + '/'):
                rows.append({'pid': item.get('process-id'), 'command': 'mounted_disk_image',
                             'access': 'mounted', 'path': item[field]})
    pids = sorted({r['pid'] for r in rows + USER_HISTORY if isinstance(r.get('pid'), int) and r['pid'] != os.getpid()})
    births = {}
    if pids:
        probe = subprocess.run(['ps', '-p', ','.join(map(str, pids)), '-o', 'pid=,lstart='],
                               capture_output=True, text=True, timeout=10)
        if probe.returncode not in {0, 1}:
            raise RuntimeError('Cannot check lifetime of previously observed data users')
        for line in probe.stdout.splitlines():
            pid, born = line.strip().split(None, 1)
            births[int(pid)] = born
    rows = [row for row in rows if row['pid'] != os.getpid()]
    USER_HISTORY = retain_live_users(rows, USER_HISTORY, births)
    if USER_HISTORY_PATH is not None:
        atomic_json(USER_HISTORY_PATH, USER_HISTORY)
    return USER_HISTORY


def move_one(action, state, mount=MOUNT, blockers=None, recheck=None):
    source, target = safe_path(action['source'], mount), safe_path(action['target'], mount)
    if action['source'].split('/')[0] not in {'marketmaker', 'marketmaker_v2', 'macroeconomics'}:
        raise ValueError('Source is outside the three authorized data trees')
    if action['target'].split('/')[0] not in {'raw_price_data', 'other_data'}:
        raise ValueError('Destination is outside the selected layout')
    identifier = hashlib.sha256((action['source'] + '\0' + action['target']).encode()).hexdigest()[:24]
    folder = state / 'moves' / identifier
    folder.mkdir(parents=True, exist_ok=True)
    receipt_path = folder / 'RECEIPT.json'
    old = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    if old and old.get('status') == 'VERIFIED':
        if source.exists() or not target.exists():
            raise RuntimeError('Completed move paths no longer match the receipt')
        return old
    for row in blockers or []:
        opened = Path(row['path'])
        if opened == source or source in opened.parents:
            raise ActiveSource(f"Move is blocked by {row['command']} PID {row['pid']}: {row['path']}")
    if not source.exists():
        if not old or old.get('status') not in {'PREPARED', 'RENAMED'} or not target.exists():
            raise RuntimeError(f'Unexplained missing source: {source}')
        before = old['before']
    else:
        if target.exists():
            raise FileExistsError(target)
        if old:
            attempt = str(time.time_ns())
            atomic_json(folder / ('PREVIOUS_RECEIPT_' + attempt + '.json'), old)
            previous_inventory = folder / 'BEFORE.jsonl.gz'
            if previous_inventory.exists():
                os.rename(previous_inventory, folder / ('PREVIOUS_BEFORE_' + attempt + '.jsonl.gz'))
        before = inventory(source, folder / 'BEFORE.jsonl.gz', sample_limit=action.get('sample_limit', 16))
        old = {'status': 'PREPARED', 'action': action, 'before': before, 'prepared_at_utc': utc()}
        atomic_json(receipt_path, old)
        append_event(state / 'JOURNAL.jsonl', {'event': 'PREPARED', 'id': identifier, 'action': action})
        if recheck is not None:
            for row in recheck():
                opened = Path(row['path'])
                if opened == source or source in opened.parents:
                    raise ActiveSource(f"New active user prevents rename: {row['command']} PID {row['pid']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        old['rename_method'] = no_replace_rename(source, target)
        old['status'] = 'RENAMED'
        atomic_json(receipt_path, old)
    after = inventory(target, folder / 'AFTER.jsonl.gz', sample_limit=0)
    if before['counts'] != after['counts'] or before['namespace_identity_sum256'] != after['namespace_identity_sum256']:
        old.update(status='VERIFICATION_FAILED_RETAINED', after=after)
        atomic_json(receipt_path, old)
        raise RuntimeError('Post-move namespace/file identity differs; data retained at destination; no cleanup allowed')
    samples = check_samples(target, folder / 'BEFORE.jsonl.gz')
    old.update(status='VERIFIED', after=after, samples_verified=samples, verified_at_utc=utc())
    atomic_json(receipt_path, old)
    append_event(state / 'JOURNAL.jsonl', {'event': 'VERIFIED', 'id': identifier, 'action': action,
                                        'counts': after['counts']})
    return old


def main():
    global USER_HISTORY_PATH, USER_HISTORY
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['inventory', 'active', 'apply'])
    p.add_argument('--source')
    p.add_argument('--output', type=Path)
    p.add_argument('--sample-limit', type=int, default=16)
    p.add_argument('--plan', type=Path)
    p.add_argument('--state', type=Path, default=HERE / 'execution')
    p.add_argument('--skip-active', action='store_true', help='Leave busy sources in place and continue independent moves; exit 2 if any remain')
    args = p.parse_args()
    validate_volume()
    if args.command == 'inventory':
        result = inventory(safe_path(args.source), args.output, sample_limit=args.sample_limit)
        atomic_json(args.output.with_suffix('.summary.json'), result)
        print(json.dumps(result), flush=True)
    elif args.command == 'active':
        print(json.dumps(active_paths(), indent=2), flush=True)
    else:
        plan = json.loads(args.plan.read_text())
        if plan.get('volume_uuid') != VOLUME_UUID:
            raise RuntimeError('Plan is bound to another volume')
        args.state.mkdir(parents=True, exist_ok=True)
        import fcntl
        owner = (args.state / 'owner.lock').open('a')
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        USER_HISTORY_PATH = args.state / 'KNOWN_SOURCE_USERS.json'
        if USER_HISTORY_PATH.exists():
            USER_HISTORY = json.loads(USER_HISTORY_PATH.read_text())
        blocked = []
        completed = set()
        device = MOUNT.stat().st_dev
        checked_volume_at = time.monotonic()
        blockers, checked_open_at = active_paths(), time.monotonic()
        for action in plan['actions']:
            # Keep per-rename filesystem checks; amortize the external diskutil
            # process across small files. Every pending rename still gets a
            # fresh open-file and mounted-image check immediately beforehand.
            if not os.path.ismount(MOUNT) or MOUNT.stat().st_dev != device:
                raise RuntimeError('Mounted filesystem changed during migration')
            if time.monotonic() - checked_volume_at > 10:
                validate_volume()
                checked_volume_at = time.monotonic()
            ident = hashlib.sha256((action['source'] + '\0' + action['target']).encode()).hexdigest()[:24]
            saved = args.state / 'moves' / ident / 'RECEIPT.json'
            already_verified = saved.exists() and json.loads(saved.read_text()).get('status') == 'VERIFIED'
            if not already_verified and time.monotonic() - checked_open_at > 10:
                blockers, checked_open_at = active_paths(), time.monotonic()
            print(json.dumps({'starting': action, 'at_utc': utc()}), flush=True)
            try:
                pending_children = [child['source'] for child in plan['actions']
                                    if child['source'].startswith(action['source'] + '/')
                                    and child['source'] not in completed]
                if pending_children:
                    raise ActiveSource('Child extractions must complete first: ' + ', '.join(pending_children[:5]))
                result = move_one(action, args.state, blockers=blockers, recheck=active_paths)
            except ActiveSource as exc:
                if not args.skip_active: raise
                blocked.append({'action': action, 'reason': str(exc), 'at_utc': utc()})
                atomic_json(args.state / 'BLOCKED.json', blocked)
                print(json.dumps({'blocked': action, 'reason': str(exc)}), flush=True)
                continue
            completed.add(action['source'])
            print(json.dumps({'status': result['status'], 'action': action,
                              'counts': result['after']['counts']}), flush=True)
        atomic_json(args.state / 'BLOCKED.json', blocked)
        if blocked: raise SystemExit(2)


if __name__ == '__main__':
    main()
