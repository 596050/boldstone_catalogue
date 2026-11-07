"""Search, export or restore the verified historical inspection archives."""
import argparse
import gzip
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
import archive_inspections as a

parser = argparse.ArgumentParser(description=__doc__)
sub = parser.add_subparsers(dest='action', required=True)
sub.add_parser('list')
search = sub.add_parser('search')
search.add_argument('text')
export = sub.add_parser('export')
export.add_argument('original_path')
export.add_argument('--to', required=True)
restore = sub.add_parser('restore')
restore.add_argument('original_path')
restore.add_argument('--apply', action='store_true')
args = parser.parse_args()
assert a.digest(a.OUT / 'manifest.json') == a.read(a.OUT / 'manifest.sha256.json')['sha256']
complete = a.read(a.OUT / 'complete.json')
assert complete['status'] == 'PASS_VERIFIED_RESTORABLE_INSPECTION_ARCHIVES'
records = complete['records']


def archive(record):
    path = Path(record['archive_path'])
    assert path.is_file() and not path.is_symlink() and a.digest(path) == record['archive_sha256']
    return path


def selected(value):
    path = Path(value)
    if not path.is_absolute():
        path = a.ROOT / path
    matches = [r for r in records if r['original_path'] == str(path)]
    assert len(matches) == 1, 'Use an original path from the verified archive list'
    return matches[0]


if args.action == 'list':
    print(json.dumps([dict(original_path=r['original_path'], archive_path=r['archive_path'], bytes=r['bytes'], sha256=r['sha256'], retained_workbook=r['retained_workbook']) for r in records], indent=2))
elif args.action == 'search':
    needle = args.text.encode('utf-8')
    assert needle, 'Search text cannot be empty'
    for record in records:
        tail, matched = b'', False
        with gzip.open(archive(record), 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                data = tail + chunk
                if needle in data:
                    matched = True
                    break
                tail = data[-(len(needle) - 1):] if len(needle) > 1 else b''
        if matched:
            print(json.dumps(dict(original_path=record['original_path'], archive_path=record['archive_path'])))
elif args.action == 'export':
    record = selected(args.original_path)
    target = Path(args.to)
    digest = hashlib.sha256()
    with gzip.open(archive(record), 'rb') as source, target.open('xb') as output:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    assert digest.hexdigest() == record['sha256'], 'Export differs'
    print(json.dumps(dict(status='EXPORTED_EXACT_BYTES', path=str(target), sha256=digest.hexdigest())))
else:
    record = selected(args.original_path)
    target = Path(record['original_path'])
    assert not target.exists() and target.resolve() == target and target.is_relative_to(a.ROOT), 'Original path already exists or is unsafe'
    source = archive(record)
    if not args.apply:
        print(json.dumps(dict(status='PREVIEW_ONLY', restore_to=str(target), bytes=record['bytes'], instruction='Add --apply to restore this exact original, including its Mac metadata.')))
    else:
        temporary = target.parent / ('.inspection-restoration-' + uuid.uuid4().hex)
        try:
            a.restore_to(source, temporary, record)
            a.native.native(a.native.LIB.renamex_np, os.fsencode(temporary), os.fsencode(target), 4)
            assert a.digest(target) == record['sha256'] and a.native.metadata(target) == record['metadata']
            print(json.dumps(dict(status='RESTORED_AND_BYTE_METADATA_VERIFIED', path=str(target), archive_retained=str(source), sha256=record['sha256'])))
        finally:
            if temporary.exists():
                temporary.unlink()
