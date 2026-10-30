"""Scoped local image archival. Dropbox is read-only; retirement requires --apply."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import argparse
import collections
import datetime
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

ROOT = Path('/Users/tprice/Documents/boldstone')
HERE = Path(__file__).resolve().parent
AUDIT = ROOT / 'outputs/local-image-storage-audit-20261030'
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
sys.path.insert(0, str(ROOT / 'outputs/storage-cleanup-20261030'))
import storage_primitives as native
sys.path.insert(0, str(ROOT / 'catalogue-review'))


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as out:
        json.dump(value, out, ensure_ascii=False, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())


def log(kind, **data):
    with (HERE / 'journal.jsonl').open('a') as out:
        out.write(json.dumps({'utc': now(), 'kind': kind, **data}) + '\n')
        out.flush()
        os.fsync(out.fileno())


def emit(**data):
    print(json.dumps(data), flush=True)


def hashes(path):
    path = Path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.resolve() != path or before.st_nlink != 1:
        raise ValueError('Not an independent regular file: ' + str(path))
    sha, dropbox = hashlib.sha256(), hashlib.sha256()
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        if native.identity(os.fstat(stream.fileno())) != native.identity(before):
            raise ValueError('File changed before hashing')
        while block := stream.read(4 * 1024 * 1024):
            sha.update(block)
            dropbox.update(hashlib.sha256(block).digest())
        if native.identity(os.fstat(stream.fileno())) != native.identity(before):
            raise ValueError('File changed during hashing')
    if native.identity(path.lstat()) != native.identity(before):
        raise ValueError('File changed after hashing')
    return sha.hexdigest(), dropbox.hexdigest(), native.identity(before)


def cloud_inventory(name):
    from delete_dropbox import connection
    from dropbox.files import FileMetadata
    result = []
    with connection(ROOT) as (client, root):
        page = client.files_list_folder(root, recursive=True, include_deleted=False, limit=2000)
        pages = 0
        while True:
            pages += 1
            for m in page.entries:
                if isinstance(m, FileMetadata):
                    if not (m.path_display or '').casefold().startswith(root.casefold() + '/'):
                        raise ValueError('Inventory outside the expected root')
                    result.append({'id': m.id, 'path': m.path_display, 'revision': m.rev,
                                   'bytes': m.size, 'content_hash': m.content_hash,
                                   'downloadable': m.is_downloadable})
            emit(phase='Dropbox read-only inventory', pages=pages, files=len(result))
            if not page.has_more:
                break
            page = client.files_list_folder_continue(page.cursor)
    payload = {'checked_utc': now(), 'root': root, 'files': result, 'cloud_mutations': 0}
    write(HERE / name, payload)
    return payload


def open_files():
    command = subprocess.run(['lsof', '-nP', '-Fn'], capture_output=True, text=True, timeout=45)
    if command.returncode not in (0, 1):
        raise RuntimeError('Could not inspect open file handles')
    return {line[1:] for line in command.stdout.splitlines() if line.startswith('n' + str(ROOT) + '/')}


def fresh_dependencies():
    """Rebuild current media paths with the same overlays as the live app."""
    import urllib.request
    from catalogue import Catalogue
    from dropbox_sync import apply_inventory
    from filename_overlay import apply_filename_overlay
    from media import MediaCache
    from organisation import apply_location
    MediaCache.flush = lambda self: None
    boot = json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap', timeout=90))
    runtime = Path(boot['data_directory'])
    cat = Catalogue(ROOT, runtime)
    live = boot['source'].get('live_dropbox')
    if live:
        inventory = read(live['path'])
        inventory.update(snapshot_path=live['path'], snapshot_sha256=live['sha256'], checked_utc=live['checked_utc'])
        cat = apply_inventory(cat, inventory, runtime)
    apply_filename_overlay(cat, runtime)
    with sqlite3.connect('file:' + str(runtime / 'reviews.sqlite3') + '?mode=ro', uri=True) as db:
        for (raw,) in db.execute("SELECT result FROM background_jobs WHERE kind='organise' AND state='completed' ORDER BY updated_at"):
            result = json.loads(raw)
            if result.get('checked_utc', '') > (live or {}).get('checked_utc', ''):
                apply_location(cat, result)
    paths = {str(Path(value[0]).resolve()) for value in cat.paths.values()}
    paths.update(str(Path(value).resolve()) for value in cat.preview_paths.values())
    return paths


def prepare():
    if (HERE / 'manifest.json').exists():
        raise ValueError('Manifest exists; inspect before resuming')
    protected = {r['path'] for r in read(HERE / 'live-protected-before.json')['files']}
    protected |= fresh_dependencies()
    opened = open_files()
    if not (HERE / 'space-before.json').exists():
        write(HERE / 'space-before.json', native.space())
    cloud = cloud_inventory('dropbox-before.json')
    cloud_by_hash = collections.defaultdict(list)
    for item in cloud['files']:
        if item['downloadable'] and item['content_hash']:
            cloud_by_hash[(item['content_hash'], item['bytes'])].append(item)
    rows = json.load(gzip.open(AUDIT / 'inventory.json.gz', 'rt'))
    candidates = [r for r in rows if r['image'] and str(ROOT / r['path']) not in protected]
    skipped = []

    def inspect(row):
        path = ROOT / row['path']
        if not path.is_relative_to(ROOT) or path.resolve() != path or str(path) in opened:
            return None, {'path': row['path'], 'reason': 'Open or noncanonical path'}
        if path.suffix.lower() in ('.svg', '.ico') or any(x in path.parts for x in ('.venv', 'node_modules', 'tests')):
            return None, {'path': row['path'], 'reason': 'Code dependency or test asset'}
        try:
            s = path.lstat()
            if (s.st_size, s.st_mtime_ns) != (row['bytes'], row['mtime_ns']):
                return None, {'path': row['path'], 'reason': 'Changed since audit'}
            meta = native.metadata(path)
            # Extended metadata is not silently discarded by archive restoration.
            if meta['acl'] or meta['xattrs'] or meta['flags']:
                return None, {'path': row['path'], 'reason': 'Extended metadata retained in place'}
            sha, dh, identity = hashes(path)
            return {'path': row['path'], 'bytes': s.st_size, 'sha256': sha,
                    'dropbox_content_hash': dh, 'identity': identity,
                    'metadata': meta, 'atime_ns': s.st_atime_ns}, None
        except (OSError, ValueError) as error:
            return None, {'path': row['path'], 'reason': type(error).__name__}

    records = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for index, (record, skip) in enumerate(pool.map(inspect, candidates), 1):
            if record:
                records.append(record)
            if skip:
                skipped.append(skip)
            if index % 1000 == 0:
                emit(phase='Hashing historical image copies', checked=index, total=len(candidates))
    blobs = {}
    for r in records:
        blob = blobs.setdefault(r['sha256'], {'sha256': r['sha256'], 'bytes': r['bytes'],
                                             'dropbox_content_hash': r['dropbox_content_hash'], 'source_path': r['path']})
        if blob['bytes'] != r['bytes'] or blob['dropbox_content_hash'] != r['dropbox_content_hash']:
            raise ValueError('Inconsistent byte identity')
    # Prefer a retained active local copy when it already supplies identical bytes.
    keepers = {r['sha256']: r for r in read(HERE / 'live-protected-before.json')['files']}
    counts = collections.Counter()
    for sha, blob in blobs.items():
        if sha in keepers and keepers[sha]['bytes'] == blob['bytes']:
            blob.update(storage='active-local', keeper=keepers[sha]['path'])
        elif available := cloud_by_hash.get((blob['dropbox_content_hash'], blob['bytes'])):
            blob.update(storage='dropbox', cloud=sorted(available, key=lambda x: x['path'])[0])
        else:
            blob.update(storage='archive', member='images/' + sha)
        counts[blob['storage']] += 1
    manifest = {'schema': 'boldstone-historical-images/v1', 'created_utc': now(), 'project': str(ROOT),
                'protected_paths': sorted(protected), 'records': records, 'blobs': blobs, 'skipped': skipped,
                'cloud_inventory': 'dropbox-before.json', 'archive': 'historical-images.zip',
                'cloud_mutations': 0, 'authorization': 'User requested historical review archiving and removal of verified downloaded copies.'}
    write(HERE / 'manifest.json', manifest)
    write(HERE / 'manifest.sha256.json', {'sha256': native.digest(HERE / 'manifest.json')})
    emit(phase='Prepared', files=len(records), logical_GiB=sum(r['bytes'] for r in records)/2**30,
         distinct_images=len(blobs), storage=dict(counts), skipped=len(skipped),
         archive_input_GiB=sum(b['bytes'] for b in blobs.values() if b['storage']=='archive')/2**30)


def manifest():
    if native.digest(HERE / 'manifest.json') != read(HERE / 'manifest.sha256.json')['sha256']:
        raise ValueError('Manifest changed')
    return read(HERE / 'manifest.json')


def build_archive():
    m = manifest()
    target = HERE / m['archive']
    if target.exists():
        raise ValueError('Archive already exists; verify it instead')
    partial = target.with_suffix('.zip.partial')
    blobs = [b for b in m['blobs'].values() if b['storage'] == 'archive']
    with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        z.writestr('manifest.json', (HERE / 'manifest.json').read_bytes())
        for index, b in enumerate(blobs, 1):
            path = ROOT / b['source_path']
            if native.digest(path) != b['sha256']:
                raise ValueError('Archive source changed')
            z.write(path, b['member'])
            if index % 250 == 0:
                emit(phase='Writing deduplicated image archive', images=index, total=len(blobs))
    with partial.open('rb') as stream:
        os.fsync(stream.fileno())
    partial.rename(target)
    write(HERE / 'archive-built.json', {'sha256': native.digest(target), 'bytes': target.stat().st_size,
                                      'images': len(blobs), 'created_utc': now()})
    emit(phase='Archive created', images=len(blobs), archive_GiB=target.stat().st_size/2**30)


def verify_archive():
    m = manifest()
    path = HERE / m['archive']
    assert native.digest(path) == read(HERE / 'archive-built.json')['sha256']
    blobs = [b for b in m['blobs'].values() if b['storage'] == 'archive']
    restored = HERE / '.restore-verification'
    restored.mkdir(exist_ok=True)
    with zipfile.ZipFile(path) as z:
        assert set(z.namelist()) == {'manifest.json', *(b['member'] for b in blobs)}
        assert z.read('manifest.json') == (HERE / 'manifest.json').read_bytes()
        for index, b in enumerate(blobs, 1):
            tmp = restored / b['sha256']
            with z.open(b['member']) as source, tmp.open('xb') as dest:
                shutil.copyfileobj(source, dest, 2*1024*1024)
            sha, dh, identity = hashes(tmp)
            assert sha == b['sha256'] and dh == b['dropbox_content_hash'] and identity[2] == b['bytes']
            tmp.unlink()
            if index % 500 == 0:
                emit(phase='Restored archive bytes verified', images=index, total=len(blobs))
    restored.rmdir()
    write(HERE / 'archive-verified.json', {'status': 'PASS_ALL_ARCHIVED_IMAGES_RESTORED_AND_HASH_VERIFIED',
          'images': len(blobs), 'archive_sha256': native.digest(path), 'checked_utc': now()})
    emit(phase='Archive restoration verified', images=len(blobs))


def load_image(m, blob, client=None):
    if blob['storage'] == 'archive':
        with zipfile.ZipFile(HERE / m['archive']) as z:
            data = z.read(blob['member'])
    elif blob['storage'] == 'active-local':
        data = Path(blob['keeper']).read_bytes()
    elif blob['storage'] == 'dropbox':
        if client is None:
            from delete_dropbox import connection
            with connection(ROOT) as (client, _):
                return load_image(m, blob, client)
        metadata, response = client.files_download('rev:' + blob['cloud']['revision'])
        with closing(response):
            if (metadata.id, metadata.rev, metadata.content_hash, metadata.size) != (
                    blob['cloud']['id'], blob['cloud']['revision'], blob['dropbox_content_hash'], blob['bytes']):
                raise ValueError('Dropbox revision does not match the archived source')
            data = response.content
    else:
        raise ValueError('Unsupported storage')
    if len(data) != blob['bytes'] or hashlib.sha256(data).hexdigest() != blob['sha256']:
        raise ValueError('Restored image content differs')
    return data


def restore(row, dest, m, client=None):
    dest = Path(dest)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError('Restoration never overwrites an existing path')
    data = load_image(m, m['blobs'][row['sha256']], client)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name('.restore-' + uuid.uuid4().hex)
    try:
        with temp.open('xb') as out:
            out.write(data); out.flush(); os.fsync(out.fileno())
        meta = row['metadata']
        if meta['acl'] or meta['xattrs'] or meta['flags']:
            raise ValueError('Extended metadata requires a different restorer')
        os.chmod(temp, stat.S_IMODE(meta['mode']))
        os.chown(temp, meta['uid'], meta['gid'])
        os.utime(temp, ns=(row['atime_ns'], meta['mtime_ns']))
        native.creation_time(temp, meta['birthtime_ns'])
        if native.digest(temp) != row['sha256'] or native.metadata(temp) != meta:
            raise ValueError('Restored bytes or metadata differ')
        # RENAME_EXCL prevents concurrent destination replacement; no overwrite.
        native.native(native.LIB.renamex_np, os.fsencode(temp), os.fsencode(dest), 4)
    finally:
        temp.unlink(missing_ok=True)


def retire(apply=False):
    if not apply:
        raise ValueError('Retirement requires explicit --apply')
    m = manifest()
    v = read(HERE / 'archive-verified.json')
    assert v['status'] == 'PASS_ALL_ARCHIVED_IMAGES_RESTORED_AND_HASH_VERIFIED'
    assert native.digest(HERE / m['archive']) == v['archive_sha256']
    assert read(HERE / 'access-verification.json')['status'] == 'PASS'
    with (RUNTIME / 'native-jobs/writer.lock').open('a') as writer:
        # Briefly reserve the existing writer while checking remote keepers and retiring local copies.
        fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cloud = cloud_inventory('dropbox-before-retirement.json')
        current = {r['id']: r for r in cloud['files']}
        protected = set(m['protected_paths']) | fresh_dependencies()
        opened = open_files()
        verified_local = set()
        for b in m['blobs'].values():
            if b['storage'] == 'active-local':
                if native.digest(Path(b['keeper'])) != b['sha256']:
                    raise ValueError('Retained active image changed')
                verified_local.add(b['sha256'])
        eligible, skipped = [], []
        for row in m['records']:
            p = ROOT / row['path']; b = m['blobs'][row['sha256']]
            if str(p) in protected | opened:
                skipped.append({'path': row['path'], 'reason': 'New active reference or open handle'});continue
            if not p.exists() or p.resolve() != p or native.identity(p.lstat()) != row['identity']:
                skipped.append({'path': row['path'], 'reason': 'Local identity changed'});continue
            if b['storage'] == 'dropbox':
                live = current.get(b['cloud']['id'])
                if not live or (live['revision'], live['content_hash'], live['bytes'], live['downloadable']) != (
                        b['cloud']['revision'], b['dropbox_content_hash'], b['bytes'], True):
                    skipped.append({'path': row['path'], 'reason': 'Dropbox original changed or unavailable'});continue
            eligible.append(row)
        write(HERE / 'retirement-plan.json', {'created_utc': now(), 'files': len(eligible),
            'paths': [r['path'] for r in eligible], 'skipped': skipped, 'protected_paths': sorted(protected)})
        # Re-hash before unlink; do not assume that a previous match still applies.
        for index, row in enumerate(eligible, 1):
            p = ROOT / row['path']
            sha, dh, identity = hashes(p)
            if (sha, dh, identity) != (row['sha256'], row['dropbox_content_hash'], row['identity']):
                raise ValueError('Source changed before retirement: ' + row['path'])
            log('VERIFIED_LOCAL_RETIREMENT_INTENT', path=row['path'], sha256=sha,
                storage=m['blobs'][sha]['storage'])
            p.unlink()
            log('LOCAL_COPY_REMOVED', path=row['path'], sha256=sha, bytes=row['bytes'])
            if index % 1000 == 0:
                emit(phase='Verified local copies removed', files=index, total=len(eligible))
    write(HERE / 'retirement-complete.json', {'status': 'PASS', 'files': len(eligible),
         'logical_bytes_removed': sum(r['bytes'] for r in eligible), 'skipped': skipped,
         'completed_utc': now(), 'space_after': native.space(), 'cloud_mutations': 0})
    emit(phase='Retirement complete', files=len(eligible), skipped=len(skipped))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','archive','verify','retire','restore'])
    p.add_argument('path', nargs='?');p.add_argument('--apply',action='store_true')
    p.add_argument('--destination',type=Path)
    args=p.parse_args()
    with (HERE/'archive.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':prepare()
        elif args.action=='archive':build_archive()
        elif args.action=='verify':verify_archive()
        elif args.action=='retire':retire(args.apply)
        else:
            m=manifest();row=next(r for r in m['records'] if r['path']==args.path)
            dest=args.destination or ROOT/row['path']
            if not args.apply:emit(action='restore',path=str(dest),sha256=row['sha256'])
            else:restore(row,dest,m);emit(status='RESTORED_AND_VERIFIED',path=str(dest))


if __name__=='__main__':main()
