"""Transparent APFS compression of named, closed historical audit snapshots.

Keeps every pathname and logical byte readable through normal file APIs. No
active database, image cache, browser data or cloud file is eligible.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'outputs/storage-cleanup-20261030'))
import storage_primitives as sp


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def eligible(p):
    s = p.lstat()
    return (p.is_file() and not p.is_symlink() and s.st_nlink == 1
            and s.st_flags == 0 and s.st_size >= 10 * 1024**2
            and str(p).startswith(str(ROOT / 'outputs') + '/'))


def metadata_expected(before, after):
    return after == {**before, 'flags': before['flags'] | 32}


def prepare():
    items = json.loads((HERE / 'json-compression-candidates.json').read_text())
    paths = [Path(r['path']) for r in items]
    # These are old spreadsheet inspection exports, not the workbook or source.
    for folder in (ROOT / 'outputs').iterdir():
        if folder.is_dir() and any(f'2026110{i}' in folder.name for i in range(1, 8)):
            paths.extend(folder.rglob('authored.xlsx.inspect.ndjson'))
    manifest = []
    for p in sorted(set(paths)):
        if not eligible(p):
            continue
        s = p.lstat()
        manifest.append({'path': str(p), 'identity': sp.identity(s),
                         'bytes': s.st_size, 'allocated_bytes': s.st_blocks * 512,
                         'sha256': sp.digest(p), 'metadata': sp.metadata(p)})
    target = HERE / 'compression-manifest.json'
    with target.open('x') as f:
        json.dump({'created_at': stamp(), 'space_before': sp.space(),
                   'items': manifest}, f, indent=2)
    print(json.dumps({'prepared': len(manifest),
                      'allocated_bytes': sum(r['allocated_bytes'] for r in manifest)}))


def apply():
    plan = json.loads((HERE / 'compression-manifest.json').read_text())
    journal = HERE / 'compression-receipts.jsonl'
    if journal.exists():
        raise RuntimeError('Receipt already exists; reconcile before another apply')
    paths = [r['path'] for r in plan['items']]
    cp = subprocess.run(['/usr/sbin/lsof', '-Fn', '--', *paths],
                        capture_output=True, text=True)
    if cp.returncode not in (0, 1) or any(x.startswith('n') for x in cp.stdout.splitlines()):
        raise RuntimeError('An eligible snapshot has an open file handle; stopped')
    if cp.stderr.strip():
        raise RuntimeError('Cannot establish closed snapshot state: ' + cp.stderr[:500])
    total_saved = 0
    with journal.open('x') as log:
        for row in plan['items']:
            p = Path(row['path'])
            if (not eligible(p) or sp.identity(p.lstat()) != row['identity']
                    or sp.digest(p) != row['sha256'] or sp.metadata(p) != row['metadata']):
                raise RuntimeError('Snapshot drift: ' + str(p))
            temp = p.with_name('.' + p.name + '.compress-' + uuid.uuid4().hex)
            swapped = False
            try:
                cp = subprocess.run(['/usr/bin/ditto', '--hfsCompression', '--rsrc',
                                     '--extattr', '--acl', str(p), str(temp)],
                                    capture_output=True, text=True)
                if cp.returncode:
                    raise RuntimeError(cp.stderr)
                sp.creation_time(temp, row['metadata']['birthtime_ns'])
                with temp.open('rb') as f:
                    os.fsync(f.fileno())
                if (sp.digest(temp) != row['sha256']
                        or not metadata_expected(row['metadata'], sp.metadata(temp))):
                    raise RuntimeError('Compressed copy byte or metadata verification failed')
                if temp.stat().st_blocks * 512 >= row['allocated_bytes']:
                    raise RuntimeError('Compression did not reduce allocation')
                if sp.identity(p.lstat()) != row['identity']:
                    raise RuntimeError('Snapshot changed during preparation')
                sp.swap(p, temp)
                swapped = True
                if (sp.digest(p) != row['sha256']
                        or not metadata_expected(row['metadata'], sp.metadata(p))):
                    raise RuntimeError('Readback after atomic swap failed')
                if p.suffix == '.json':
                    # Verify ordinary application reads work without decompression steps.
                    with p.open() as f:
                        json.load(f)
                allocated = p.stat().st_blocks * 512
                receipt = {**row, 'completed_at': stamp(), 'status': 'BYTE_AND_METADATA_VERIFIED',
                           'allocated_after_bytes': allocated,
                           'allocation_reduction_bytes': row['allocated_bytes'] - allocated,
                           'metadata_after': sp.metadata(p)}
                log.write(json.dumps(receipt) + '\n')
                log.flush()
                os.fsync(log.fileno())
                # This removes the old physical representation only after verification.
                temp.unlink()
                total_saved += receipt['allocation_reduction_bytes']
            except BaseException:
                if swapped and temp.exists():
                    sp.swap(p, temp)
                if temp.exists():
                    temp.unlink()
                raise
    summary = {'completed_at': stamp(), 'files': len(plan['items']),
               'logical_bytes_unchanged': sum(r['bytes'] for r in plan['items']),
               'allocation_reduction_bytes': total_saved,
               'space_before': plan['space_before'], 'space_after': sp.space(),
               'paths_content_permissions_times_acl_and_noncompression_xattrs_preserved': True,
               'browser_data_active_databases_and_image_cache_changed': False}
    (HERE / 'compression-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('operation', choices=['prepare', 'apply'])
    args = p.parse_args()
    globals()[args.operation]()
