"""Reversibly archive only previously assessed inactive XLSX inspection dumps."""
import argparse
import base64
import csv
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
OLD = ROOT / 'outputs/storage-cleanup-20261030'
sys.path.insert(0, str(OLD))
import storage_primitives as native
import cleanup

now = lambda: datetime.now(timezone.utc).isoformat()
read = lambda p: json.loads(p.read_text())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value, exclusive=False):
    with path.open('x' if exclusive else 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def app_source():
    with urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap', timeout=120) as response:
        return json.load(response)['source']


def paths(value):
    if isinstance(value, str) and value.startswith(str(ROOT) + '/'):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from paths(v)
    elif isinstance(value, list):
        for v in value:
            yield from paths(v)


def opened(files):
    if not files:
        return set()
    proc = subprocess.run(['lsof', '-nP', '-Fn', '--', *map(str, files)], capture_output=True, text=True, timeout=45)
    assert proc.returncode in (0, 1), 'Open-file check failed'
    return {line[1:] for line in proc.stdout.splitlines() if line.startswith('n/')}


def regular(path):
    s = path.lstat()
    assert path.is_relative_to(ROOT) and path.resolve() == path and stat.S_ISREG(s.st_mode) and s.st_nlink == 1
    return s


def restore_to(archive, destination, info):
    with gzip.open(archive, 'rb') as source, destination.open('xb') as target:
        shutil.copyfileobj(source, target, 2 * 1024 * 1024)
        target.flush()
        os.fsync(target.fileno())
    m = info['metadata']
    assert not m['acl'] and not m['flags']
    os.chmod(destination, stat.S_IMODE(m['mode']))
    os.chown(destination, m['uid'], m['gid'])
    for name, encoded in info.get('xattrs_base64', {}).items():
        value = base64.b64decode(encoded, validate=True)
        native.native(native.LIB.setxattr, os.fsencode(destination), os.fsencode(name), value, len(value), 0, 1)
    os.utime(destination, ns=(info['atime_ns'], m['mtime_ns']))
    native.creation_time(destination, m['birthtime_ns'])
    assert digest(destination) == info['sha256'] and native.metadata(destination) == m, 'Restoration differs'


def prepare():
    assert not (OUT / 'manifest.json').exists(), 'Existing manifest must be reconciled'
    pointer_path = ROOT / 'sculpture-catalogue/current-master.json'
    pointer = read(pointer_path)
    source = app_source()
    protected = set(paths(pointer)) | set(paths(source))
    parents = {Path(source[k]).parent for k in ['register', 'gallery_database']}
    for section in ['current_app_review_workbook', 'current_upload_preparation']:
        if pointer.get(section, {}).get('path'):
            parents.add(Path(pointer[section]['path']).parent)
    rows = list(csv.DictReader((ROOT / 'outputs/cache-clear-and-snapshot-audit-20261030/snapshot-candidates.csv').open()))
    rows = [r for r in rows if r['category'] == 'Workbook inspection dumps with retained XLSX']
    open_files = opened([ROOT / r['path'] for r in rows])
    eligible, retained = [], []
    for row in rows:
        path = ROOT / row['path']
        if not path.exists():
            retained.append(dict(path=str(path), reason='No longer present'))
            continue
        if str(path) in protected or str(path) in open_files or any(path.is_relative_to(parent) for parent in parents):
            retained.append(dict(path=str(path), reason='Current source, publication directory or open file'))
            continue
        before = regular(path)
        assert path.name.endswith('.xlsx.inspect.ndjson')
        if before.st_size != int(row['bytes']) or digest(path) != row['sha256']:
            retained.append(dict(path=str(path), reason='Changed since read-only assessment'))
            continue
        workbook = ROOT / row['retained_workbook']
        assert workbook == path.with_name(path.name.removesuffix('.inspect.ndjson'))
        regular(workbook)
        with zipfile.ZipFile(workbook) as z:
            assert z.testzip() is None and 'xl/workbook.xml' in z.namelist()
        metadata = native.metadata(path)
        if metadata['acl'] or metadata['flags']:
            retained.append(dict(path=str(path), reason='Extended metadata retained in place'))
            continue
        attributes = {os.fsdecode(k): base64.b64encode(v).decode('ascii') for k, v in native.xattrs(path).items()}
        try:
            with tempfile.TemporaryDirectory(prefix='.inspection-attribute-probe-', dir=OUT) as directory:
                probe = Path(directory) / 'empty-probe'
                probe.touch()
                for name, encoded in attributes.items():
                    value = base64.b64decode(encoded, validate=True)
                    native.native(native.LIB.setxattr, os.fsencode(probe), os.fsencode(name), value, len(value), 0, 1)
                assert native.metadata(probe)['xattrs'] == metadata['xattrs']
        except (OSError, AssertionError):
            retained.append(dict(path=str(path), reason='Extended attributes could not be recreated exactly'))
            continue
        assert not Path(str(path) + '.gz').exists() and not Path(str(path) + '.gz.restore.json').exists()
        eligible.append(dict(original_path=str(path), archive_path=str(path) + '.gz', bytes=before.st_size, allocated_bytes_before=before.st_blocks * 512, sha256=row['sha256'], identity=native.identity(before), metadata=metadata, xattrs_base64=attributes, atime_ns=before.st_atime_ns, retained_workbook=str(workbook), retained_workbook_sha256=digest(workbook)))
    manifest = dict(status='PREPARED', schema='boldstone-inactive-inspection-archive/v1', prepared_utc=now(), authorization='Earlier owner request to archive historical reviews and inactive snapshots; bounded storage relief for current browser no-space errors. No current workbook, original photograph, app state, browser profile or Dropbox content is removed.', pointer_sha256=digest(pointer_path), app_source=source, protected_directories=[str(p) for p in sorted(parents)], space_before=native.space(), records=eligible, retained=retained)
    write(OUT / 'manifest.json', manifest, True)
    write(OUT / 'manifest.sha256.json', {'sha256': digest(OUT / 'manifest.json')}, True)
    print(json.dumps(dict(status='PREPARED', eligible_files=len(eligible), logical_bytes=sum(r['bytes'] for r in eligible), retained=len(retained))), flush=True)


def apply():
    manifest_path = OUT / 'manifest.json'
    assert digest(manifest_path) == read(OUT / 'manifest.sha256.json')['sha256']
    manifest = read(manifest_path)
    assert manifest['status'] == 'PREPARED' and not (OUT / 'complete.json').exists()
    pointer_path = ROOT / 'sculpture-catalogue/current-master.json'
    assert digest(pointer_path) == manifest['pointer_sha256'] and app_source() == manifest['app_source']
    records = manifest['records']
    assert not opened([Path(r['original_path']) for r in records])
    journal = OUT / 'journal.jsonl'

    def event(value):
        with journal.open('a') as stream:
            stream.write(json.dumps(dict(utc=now(), **value)) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    with (OUT / 'archive.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verified = []
        for i, record in enumerate(records, 1):
            path, archive = Path(record['original_path']), Path(record['archive_path'])
            assert native.identity(regular(path)) == record['identity'] and digest(path) == record['sha256']
            assert digest(Path(record['retained_workbook'])) == record['retained_workbook_sha256']
            info_path = Path(str(archive) + '.restore.json')
            assert not archive.exists() and not info_path.exists()
            partial = path.parent / ('.inspection-archive-' + uuid.uuid4().hex)
            restored = path.parent / ('.inspection-restore-check-' + uuid.uuid4().hex)
            event(dict(status='COMPRESSING_RAW_RETAINED', original_path=str(path), partial=str(partial), restored=str(restored)))
            try:
                with partial.open('xb') as raw:
                    with gzip.GzipFile(fileobj=raw, mode='wb', filename='', compresslevel=6, mtime=0) as target, path.open('rb') as source:
                        shutil.copyfileobj(source, target, 2 * 1024 * 1024)
                    raw.flush()
                    os.fsync(raw.fileno())
                os.chmod(partial, stat.S_IMODE(record['metadata']['mode']))
                info = dict(record, archive_sha256=digest(partial), archive_bytes=partial.stat().st_size, verified_utc=now())
                restore_to(partial, restored, info)
                assert native.identity(regular(path)) == record['identity']
                assert native.metadata(restored) == record['metadata']
                assert digest(restored) == record['sha256']
                native.native(native.LIB.renamex_np, os.fsencode(partial), os.fsencode(archive), 4)
                write(info_path, info, True)
                event(dict(status='RESTORE_VERIFIED_RAW_RETAINED', **info))
                verified.append(info)
            finally:
                if partial.exists():
                    partial.unlink()
                if restored.exists():
                    restored.unlink()
            if i % 5 == 0:
                print(json.dumps(dict(status='ARCHIVES_VERIFIED_RAW_STILL_PRESENT', files=i, total=len(records))), flush=True)
        assert digest(pointer_path) == manifest['pointer_sha256'] and app_source() == manifest['app_source']
        assert not opened([Path(r['original_path']) for r in records])
        for record in verified:
            path, archive = Path(record['original_path']), Path(record['archive_path'])
            assert native.identity(regular(path)) == record['identity'] and digest(path) == record['sha256']
            assert digest(archive) == record['archive_sha256']
            path.unlink()
            event(dict(status='RAW_INSPECTION_RETIRED_VERIFIED_ARCHIVE_RETAINED', original_path=str(path), archive_path=str(archive), sha256=record['sha256']))
        result = dict(status='PASS_VERIFIED_RESTORABLE_INSPECTION_ARCHIVES', completed_utc=now(), files=len(verified), logical_raw_bytes=sum(r['bytes'] for r in verified), archive_bytes=sum(r['archive_bytes'] for r in verified), current_source_and_master_preserved=True, retained_workbooks_preserved=True, browser_profile_changes=0, dropbox_mutations=0, space_before=manifest['space_before'], space_after=native.space(), records=verified, caveat='Logical compression reduction and observed free-space change are separate; APFS shared extents and concurrent activity affect physical savings.')
        write(OUT / 'complete.json', result, True)
        print(json.dumps({k: v for k, v in result.items() if k != 'records'}), flush=True)


def amend_attributes():
    assert not (OUT / 'journal.jsonl').exists() and not (OUT / 'complete.json').exists()
    original = read(OUT / 'manifest.json')
    assert original['status'] == 'PREPARED'
    for record in original['records']:
        assert not Path(record['archive_path']).exists()
    assert not (OUT / 'manifest-initial.json').exists()
    (OUT / 'manifest.json').rename(OUT / 'manifest-initial.json')
    (OUT / 'manifest.sha256.json').rename(OUT / 'manifest-initial.sha256.json')
    prepare()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'amend-attributes', 'apply'])
    args = parser.parse_args()
    {'prepare': prepare, 'amend-attributes': amend_attributes, 'apply': apply}[args.action]()
