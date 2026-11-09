"""Read-only, file-level Toshiba census. Outputs are written only in this repo.

Payload bodies are not hashed here. Every filesystem entry, including zero-byte
files, hidden files and partial downloads, is recorded. Links are not followed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import time
import bulk_metadata

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    part = path.with_suffix(path.suffix + '.tmp')
    part.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(part, path)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def category(rel):
    low = rel.lower()
    if low == 'macroeconomics' or low.startswith('macroeconomics/'):
        return 'macroeconomics'
    if low == 'marketmaker/macro_archive' or low.startswith('marketmaker/macro_archive/'):
        return 'macroeconomics'
    if low.startswith('marketmaker/data/raw/non_price/macro'):
        return 'macroeconomics'
    if 'iqfeed' in low:
        return 'iqfeed_related'
    return 'other'


def priority(rel):
    c = category(rel)
    return (0 if c == 'macroeconomics' else 1 if c == 'iqfeed_related' else 2, rel)


def file_record(root, path, st, observed):
    rel = path.relative_to(root).as_posix()
    mode = st.st_mode
    kind = ('file' if stat.S_ISREG(mode) else 'directory' if stat.S_ISDIR(mode)
            else 'symlink' if stat.S_ISLNK(mode) else 'special')
    return {
        'path': rel, 'kind': kind, 'category': category(rel),
        'bytes': st.st_size if kind == 'file' else 0,
        'allocated_bytes': st.st_blocks * 512 if st.st_blocks is not None else None,
        'allocation_status': 'OBSERVED' if st.st_blocks is not None else 'NOT_REQUESTED_FOR_FAST_METADATA_CENSUS',
        'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns,
        'observed_at_utc': observed, 'device': st.st_dev, 'inode': st.st_ino,
        'mode': stat.S_IMODE(mode),
        'partial_download_or_temporary_name': (
            any(x in rel.lower().split('/') for x in ('incomplete', 'partials'))
            or rel.lower().endswith(('.part', '.partial', '.tmp', '.download'))
        ),
        'payload_sha256': None,
        'payload_hash_status': 'NOT_READ_BY_METADATA_CENSUS',
    }


def metadata_worker(conn):
    """One read-only subprocess, replaceable if a filesystem call stalls."""
    while True:
        request = conn.recv()
        if request is None:
            return
        root, path = Path(request['root']), Path(request['path'])
        names = request.get('names')
        try:
            conn.send({'type': 'operation', 'operation': 'directory_lstat', 'path': str(path)})
            before = path.lstat()
            if names is None:
                iterator = iter(bulk_metadata.entries(path))
                while True:
                    conn.send({'type': 'operation', 'operation': 'getattrlistbulk', 'path': str(path)})
                    try:
                        item = next(iterator)
                    except StopIteration:
                        break
                    child = path / item['name']
                    st = item['stat']
                    if not item['valid']:
                        conn.send({'type': 'operation', 'operation': 'unsupported_attribute_lstat', 'path': str(child)})
                        st = child.lstat()
                    row = file_record(root, child, st, utc())
                    row['metadata_method'] = 'getattrlistbulk' if item['valid'] else 'lstat_fallback'
                    if row['kind'] == 'symlink':
                        row['link_target'] = os.readlink(child)
                    conn.send({'type': 'entry', 'row': row})
                conn.send({'type': 'operation', 'operation': 'directory_restat', 'path': str(path)})
                after = path.lstat()
                changed = (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns)
                conn.send({'type': 'done', 'changed': changed})
                continue
            conn.send({'type': 'names', 'names': names})
            for i, name in enumerate(names):
                child = path / name
                conn.send({'type': 'operation', 'operation': 'entry_lstat', 'path': str(child), 'index': i})
                try:
                    st = child.lstat()
                    row = file_record(root, child, st, utc())
                    if row['kind'] == 'symlink':
                        row['link_target'] = os.readlink(child)
                    conn.send({'type': 'entry', 'row': row, 'index': i})
                except OSError as exc:
                    conn.send({'type': 'error', 'path': str(child), 'operation': 'entry_lstat',
                               'error_type': type(exc).__name__, 'error': str(exc), 'index': i})
            conn.send({'type': 'operation', 'operation': 'directory_restat', 'path': str(path)})
            after = path.lstat()
            changed = (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns)
            conn.send({'type': 'done', 'changed': changed})
        except OSError as exc:
            conn.send({'type': 'error', 'path': str(path), 'operation': 'directory_read',
                       'error_type': type(exc).__name__, 'error': str(exc)})
            conn.send({'type': 'done', 'changed': None})


class BoundedReader:
    def __init__(self, root, timeout=10):
        self.root, self.timeout = root, timeout
        self.process = self.conn = None

    def start(self):
        context = multiprocessing.get_context('spawn')
        self.conn, child = context.Pipe()
        self.process = context.Process(target=metadata_worker, args=(child,), daemon=True)
        self.process.start()
        child.close()

    def close(self):
        if self.process is not None:
            self.process.kill()
            self.process.join(timeout=1)
            self.conn.close()
            self.process = self.conn = None

    def directory(self, path):
        remaining = None
        while True:
            if self.process is None:
                self.start()
            self.conn.send({'root': str(self.root), 'path': str(path), 'names': remaining})
            names = None
            operation = {'path': str(path), 'operation': 'directory_request'}
            while True:
                if not self.conn.poll(self.timeout):
                    self.close()
                    yield {'type': 'error', 'path': operation['path'],
                           'operation': operation['operation'], 'error_type': 'MetadataTimeout',
                           'error': f'No response in {self.timeout} seconds; owned reader replaced.'}
                    # A single unreadable entry must not hide its remaining siblings.
                    if names is not None and 'index' in operation:
                        remaining = names[operation['index'] + 1:]
                        break
                    yield {'type': 'done', 'changed': None}
                    return
                event = self.conn.recv()
                if event['type'] == 'operation':
                    operation = event
                elif event['type'] == 'names':
                    names = event['names']
                else:
                    yield event
                    if event['type'] == 'done':
                        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mount', type=Path, default=Path('/Volumes/Toshiba 2TB'))
    ap.add_argument('--run-id', default='run_03')
    args = ap.parse_args()
    root = args.mount
    if not os.path.ismount(root):
        raise SystemExit(f'Expected mounted volume is unavailable: {root}')
    config = json.loads((REPO / 'data_paths.json').read_text())
    expected = config['external_storage']
    identity_path = root / expected['identity_file']
    identity = json.loads(identity_path.read_text())
    for key in ('identity_token', 'usb_serial', 'volume_uuid'):
        if identity[key] != expected[key]:
            raise SystemExit(f'Volume identity mismatch: {key}')
    if root.resolve() != Path(expected['mount_point']).resolve():
        raise SystemExit('Mount path does not match the registry')
    info = subprocess.run(['diskutil', 'info', '-plist', str(root)],
                          capture_output=True, check=True, timeout=15)
    disk_info = plistlib.loads(info.stdout)
    if disk_info.get('VolumeUUID') != expected['volume_uuid']:
        raise SystemExit('Live filesystem UUID does not match the registry')
    out = HERE / args.run_id
    out.mkdir(exist_ok=False)
    device = root.stat().st_dev
    started = utc()
    write_json(out / 'SOURCE_IDENTITY.json', {
        'observed_at_utc': started, 'mount': str(root), 'device': device,
        'storage_identity': identity, 'diskutil_info': disk_info,
        'registry_sha256': digest(REPO / 'data_paths.json'),
        'scanner_sha256': digest(Path(__file__)),
        'bulk_reader_sha256': digest(Path(bulk_metadata.__file__)),
        'usage_before': shutil.disk_usage(root)._asdict(),
    })
    # Only these handles are writable. All source operations below are reads.
    names = ['FILES.jsonl.gz', 'DIRECTORIES.jsonl.gz', 'OTHER_ENTRIES.jsonl.gz',
             'DIRECTORY_READS.jsonl.gz', 'ERRORS.jsonl.gz']
    streams = {n: gzip.open(out / (n + '.partial'), 'wt', encoding='utf-8', compresslevel=6)
               for n in names}
    totals = Counter()
    categories = {}
    stack = [root]
    visited = set()
    current = '.'
    last_report = 0.0
    exception = None
    reader = BoundedReader(root)

    def emit(name, value):
        streams[name].write(json.dumps(value, separators=(',', ':')) + '\n')

    def error(path, operation, exc):
        totals['errors'] += 1
        emit('ERRORS.jsonl.gz', {'path': str(path.relative_to(root)),
             'operation': operation, 'error_type': type(exc).__name__,
             'error': str(exc), 'observed_at_utc': utc()})

    def progress(force=False):
        nonlocal last_report
        if not force and time.monotonic() - last_report < 10:
            return
        for f in streams.values():
            f.flush()
        value = {'status': 'RUNNING', 'started_at_utc': started,
                 'observed_at_utc': utc(), 'current_directory': current,
                 'pending_directories': len(stack), 'totals': dict(totals),
                 'categories': categories}
        write_json(out / 'PROGRESS.json', value)
        print(json.dumps(value), flush=True)
        last_report = time.monotonic()

    try:
        while stack:
            path = stack.pop()
            current = path.relative_to(root).as_posix()
            progress()
            if not os.path.ismount(root) or root.stat().st_dev != device:
                raise RuntimeError('Volume disappeared or its device changed')
            # No path is scheduled twice; never resolve symlinks into another tree.
            if current in visited:
                raise RuntimeError(f'Duplicate traversal path: {current}')
            visited.add(current)
            children = []
            count = 0
            status = 'COMPLETE'
            changed = None
            try:
                for event in reader.directory(path):
                    if event['type'] == 'error':
                        totals['errors'] += 1
                        emit('ERRORS.jsonl.gz', {**event, 'path': str(Path(event['path']).relative_to(root)),
                             'observed_at_utc': utc()})
                        status = 'READ_ERROR'
                    elif event['type'] == 'done':
                        changed = event['changed']
                    elif event['type'] == 'entry':
                        row = event['row']
                        child = root / row['path']
                        count += 1
                        totals['entries'] += 1
                        totals['allocated_bytes_all_entries'] += row['allocated_bytes'] or 0
                        totals['entries_without_allocation_measurement'] += row['allocated_bytes'] is None
                        kind = row['kind']
                        if kind == 'file':
                            emit('FILES.jsonl.gz', row)
                            totals['files'] += 1
                            totals['file_bytes'] += row['bytes']
                            totals['allocated_file_bytes'] += row['allocated_bytes'] or 0
                            totals['zero_byte_files'] += row['bytes'] == 0
                            totals['partial_or_temporary_files'] += row['partial_download_or_temporary_name']
                            group = categories.setdefault(row['category'], {'files': 0, 'bytes': 0, 'allocated_bytes': 0})
                            group['files'] += 1; group['bytes'] += row['bytes']
                            group['allocated_bytes'] += row['allocated_bytes'] or 0
                        elif kind == 'directory':
                            emit('DIRECTORIES.jsonl.gz', row)
                            totals['directories'] += 1
                            if row['device'] == device:
                                children.append(child)
                            else:
                                error(child, 'device_boundary_not_followed', RuntimeError('Different filesystem'))
                        else:
                            emit('OTHER_ENTRIES.jsonl.gz', row)
                            totals[kind] += 1
                    progress()
                totals['directories_changed_during_listing'] += changed is True
            except OSError as exc:
                error(path, 'scandir_or_directory_restat', exc)
                status = 'READ_ERROR'
                changed = None
            emit('DIRECTORY_READS.jsonl.gz', {'path': current, 'status': status,
                 'entries_read': count, 'changed_during_listing': changed,
                 'observed_at_utc': utc()})
            totals['directories_attempted'] += 1
            if status == 'COMPLETE':
                totals['directories_read_complete'] += 1
            stack.extend(sorted(children, key=lambda p: priority(p.relative_to(root).as_posix()), reverse=True))
    except BaseException as exc:
        exception = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        reader.close()
        progress(True)
        for f in streams.values():
            f.close()
        for name in names:
            os.replace(out / (name + '.partial'), out / name)
        identity_after = None
        try:
            identity_after = json.loads(identity_path.read_text())
            device_after = root.stat().st_dev
            usage_after = shutil.disk_usage(root)._asdict()
        except OSError as exc:
            device_after = None
            usage_after = None
            if exception is None:
                exception = {'type': type(exc).__name__, 'message': str(exc)}
        result = {
            'schema': 'marketmaker.external_file_manifest.v1',
            'root': str(root), 'started_at_utc': started, 'finished_at_utc': utc(),
            'status': ('INTERRUPTED' if exception else 'COMPLETED_WITH_EXCLUSIONS'
                       if totals['errors'] else 'COMPLETED'),
            'scope': 'Every reachable entry on this volume; IQFeed and macroeconomics visited first.',
            'metadata_read_timeout_seconds': reader.timeout,
            'allocation_policy': 'Physical allocation generally not requested; per-file null is unknown, not zero. Aggregate allocated bytes sum only known observations.',
            'atomic_snapshot': False, 'source_mutations_performed': False,
            'payload_hashes_computed': False, 'archive_members_expanded': False,
            'symlinks_followed': False, 'other_filesystems_followed': False,
            'totals': dict(totals), 'categories': categories,
            'identity_unchanged': identity_after == identity and device_after == device,
            'usage_after': usage_after, 'exception': exception,
            'pending_directories': [str(p.relative_to(root)) for p in stack],
            'files': {n: {'sha256': digest(out / n), 'bytes': (out / n).stat().st_size} for n in names},
        }
        write_json(out / 'SUMMARY.json', result)
        write_json(out / 'PROGRESS.json', {**result, 'current_directory': current})
        print(json.dumps(result), flush=True)
    if exception:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
