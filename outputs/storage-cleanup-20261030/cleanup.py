"""Explicitly authorised local cleanup with durable receipts and exact readback."""
from pathlib import Path
import argparse
import fcntl
import gzip
import hashlib
import json
import os
import shutil
import stat
import subprocess
import time
import uuid
import zipfile
import storage_primitives as native

ROOT = Path('/Users/tprice/Documents/boldstone')
HERE = Path(__file__).resolve().parent
AUDIT = ROOT / 'outputs/readiness-and-space-audit-20261030'
load = lambda p: json.loads(Path(p).read_text())
PROTECTED = {x['path'] for x in load(HERE / 'live-protected-before.json')['files']}
OPENED = {x['path'] for x in load(HERE / 'open-files-before.json')}
EXCLUDED_ROOTS = ('application/', 'search-analytics-toolkit/', 'dropbox resolution/', 'boldstone_flat_migration_local_2026-10-15/')

def write_json(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())

def log(event):
    with (HERE / 'journal.jsonl').open('a') as stream:
        stream.write(json.dumps({'utc': native.now(), **event}) + '\n')
        stream.flush()
        os.fsync(stream.fileno())

def guarded(path, mutate=True):
    path = Path(path)
    if not path.is_relative_to(ROOT) or path.resolve() != path or not path.is_file() or path.is_symlink():
        raise RuntimeError('Not a regular in-scope file: ' + str(path))
    if mutate and (str(path) in PROTECTED | OPENED or str(path.relative_to(ROOT)).startswith(EXCLUDED_ROOTS)):
        raise RuntimeError('Protected file: ' + str(path))
    if path.stat().st_nlink != 1:
        raise RuntimeError('Unexpected hard link: ' + str(path))
    return path.stat()

def identical_stat(path, expected):
    if native.identity(path.stat()) != native.identity(expected):
        raise RuntimeError('File changed: ' + str(path))

def sha_stream(stream):
    return hashlib.file_digest(stream, 'sha256').hexdigest()

def archive_exports():
    receipt = HERE / 'exports-complete.json'
    if receipt.exists():
        return load(receipt)
    selected = [r for r in load(AUDIT / 'verified-test-export-candidates.json')['results'] if r['status'] == 'PASS_BYTE_IDENTICAL_ARCHIVE']
    results = []
    for row in selected:
        directory, archive = ROOT / row['directory'], ROOT / row['archive']
        archive_stat = guarded(archive, mutate=False)
        archive_sha = native.digest(archive)
        members = {str(p.relative_to(directory)): p for p in directory.rglob('*') if p.is_file()}
        originals = {}
        with zipfile.ZipFile(archive) as z:
            names = [x for x in z.namelist() if not x.endswith('/')]
            if len(names) != len(set(names)) or set(names) != set(members):
                raise RuntimeError('Archive file set changed: ' + str(directory))
            for name, p in members.items():
                before = guarded(p)
                h = native.digest(p)
                with z.open(name) as stored:
                    if sha_stream(stored) != h:
                        raise RuntimeError('Archive bytes differ: ' + str(p))
                identical_stat(p, before)
                originals[name] = {'path': str(p), 'sha256': h, 'identity': native.identity(before), 'metadata': native.metadata(p)}
            identical_stat(archive, archive_stat)
            log({'phase': 'exports', 'status': 'VERIFIED_ARCHIVE_BEFORE_RETIREMENT', 'directory': str(directory), 'archive': str(archive), 'archive_sha256': archive_sha, 'files': originals})
            for name, p in members.items():
                guarded(p)
                if native.identity(p.stat()) != originals[name]['identity']:
                    raise RuntimeError('Export changed before retirement: ' + str(p))
                p.unlink()
        # Only empty directories are removed; unexpected new files stop this step.
        for p in sorted((p for p in directory.rglob('*') if p.is_dir()), key=lambda p:len(p.parts), reverse=True):
            p.rmdir()
        directory.rmdir()
        if native.digest(archive) != archive_sha:
            raise RuntimeError('Retained archive changed')
        result = {'directory': str(directory), 'archive': str(archive), 'archive_sha256': archive_sha, 'files': len(originals), 'allocated_bytes_retired': row['allocated_bytes'], 'status': 'VERIFIED_ARCHIVE_RETAINED'}
        log({'phase': 'exports', **result})
        results.append(result)
    result = {'status': 'PASS', 'results': results, 'files_retired': sum(r['files'] for r in results), 'allocated_bytes_retired': sum(r['allocated_bytes_retired'] for r in results), 'space_after': native.space()}
    write_json(receipt, result)
    print(json.dumps({'phase':'exports', 'status':'PASS', 'files':result['files_retired'], 'available':result['space_after']['available_bytes']}), flush=True)
    return result

def restore_to(archive, destination, metadata):
    with gzip.open(archive, 'rb') as source, destination.open('xb') as target:
        shutil.copyfileobj(source, target, 2 * 1024 * 1024)
        target.flush()
        os.fsync(target.fileno())
    m = metadata['metadata']
    if m['acl'] or m['xattrs'] or m['flags']:
        raise RuntimeError('Restore requires extended metadata support')
    os.chmod(destination, stat.S_IMODE(m['mode']))
    os.chown(destination, m['uid'], m['gid'])
    os.utime(destination, ns=(metadata['atime_ns'], m['mtime_ns']))
    native.creation_time(destination, m['birthtime_ns'])
    if native.digest(destination) != metadata['sha256'] or native.metadata(destination) != m:
        raise RuntimeError('Archive restoration differs: ' + str(archive))

def archive_databases():
    receipt = HERE / 'databases-complete.json'
    if receipt.exists():
        return load(receipt)
    exports = [r['directory']+'/' for r in load(AUDIT / 'verified-test-export-candidates.json')['results'] if r['status']=='PASS_BYTE_IDENTICAL_ARCHIVE']
    rows = [r for r in load(AUDIT / 'database-archive-candidates.json') if not any(r['path'].startswith(p) for p in exports)]
    results = []
    for row in rows:
        path = ROOT / row['path']
        archive = Path(str(path) + '.gz')
        info_path = Path(str(archive) + '.restore.json')
        if not path.exists() and archive.exists() and info_path.exists():
            info = load(info_path)
            with gzip.open(archive, 'rb') as stream:
                assert sha_stream(stream) == row['sha256'] == info['sha256']
            results.append(info)
            continue
        before = guarded(path)
        if native.digest(path) != row['sha256']:
            raise RuntimeError('Historical database changed: ' + str(path))
        meta = native.metadata(path)
        if meta['acl'] or meta['xattrs'] or meta['flags']:
            raise RuntimeError('Historical database has extended metadata')
        if archive.exists() or info_path.exists():
            raise RuntimeError('Archive destination already exists: ' + str(archive))
        partial = path.parent / ('.boldstone-archive-' + uuid.uuid4().hex)
        restored = path.parent / ('.boldstone-restore-check-' + uuid.uuid4().hex)
        info = {'original_path': str(path), 'archive_path': str(archive), 'sha256': row['sha256'],
                'bytes': before.st_size, 'allocated_bytes_before': before.st_blocks*512,
                'metadata': meta, 'atime_ns': before.st_atime_ns, 'verified_utc': native.now()}
        log({'phase':'databases','status':'ARCHIVE_INTENT', **info, 'partial':str(partial), 'restored':str(restored)})
        try:
            with partial.open('xb') as raw:
                with gzip.GzipFile(fileobj=raw, mode='wb', filename='', compresslevel=6, mtime=0) as target, path.open('rb') as source:
                    shutil.copyfileobj(source, target, 2*1024*1024)
                raw.flush()
                os.fsync(raw.fileno())
            os.chmod(partial, stat.S_IMODE(before.st_mode))
            restore_to(partial, restored, info)
            identical_stat(path, before)
            info['archive_sha256'] = native.digest(partial)
            info['archive_bytes'] = partial.stat().st_size
            # Persist verified archive and restore metadata before retiring the raw copy.
            os.rename(partial, archive)
            write_json(info_path, info)
            log({'phase':'databases','status':'RESTORE_VERIFIED_RAW_STILL_PRESENT', **info})
            identical_stat(path, before)
            guarded(path)
            path.unlink()
            restored.unlink()
            log({'phase':'databases','status':'RAW_COPY_RETIRED_ARCHIVE_RETAINED','original_path':str(path),'archive_path':str(archive),'sha256':info['sha256']})
            results.append(info)
        finally:
            if partial.exists():partial.unlink()
            if restored.exists():restored.unlink()
        if len(results)%10==0:
            print(json.dumps({'phase':'databases','verified_archives':len(results),'total':len(rows),'available':native.space()['available_bytes']}),flush=True)
    result = {'status':'PASS','files':len(results),'raw_bytes':sum(r['bytes'] for r in results),'archive_bytes':sum(r['archive_bytes'] for r in results),'results':results,'space_after':native.space()}
    write_json(receipt,result)
    print(json.dumps({'phase':'databases','status':'PASS','files':len(results),'archive_bytes':result['archive_bytes']}),flush=True)
    return result

def deduplicate():
    receipt = HERE / 'dedup-complete.json'
    if receipt.exists():return load(receipt)
    groups = json.load(gzip.open(AUDIT / 'exact-duplicates.json.gz','rt'))
    completed = set()
    if (HERE/'journal.jsonl').exists():
        for line in (HERE/'journal.jsonl').read_text().splitlines():
            row=json.loads(line)
            if row.get('status')=='COW_VERIFIED_OLD_STORAGE_RETIRED':completed.add(row['path'])
    count=0; logical=0; skipped=[]; last=time.monotonic()
    for group in groups:
        files = [r for r in group['files'] if (ROOT/r['path']).exists() and not r['path'].startswith(EXCLUDED_ROOTS)]
        if len(files)<2:continue
        files.sort(key=lambda r:(str(ROOT/r['path']) not in PROTECTED, r['path'] not in [x['path'] for x in group['files'][:1]],len(r['path'])))
        keeper = ROOT/files[0]['path']
        guarded(keeper,mutate=False)
        if str(keeper) in OPENED:
            skipped.append({'path':str(keeper),'reason':'Keeper open'});continue
        if native.digest(keeper)!=group['sha256']:
            skipped.append({'path':str(keeper),'reason':'Keeper changed'});continue
        keeper_meta=native.metadata(keeper)
        for row in files[1:]:
            target=ROOT/row['path']
            if str(target) in completed:continue
            if str(target) in PROTECTED|OPENED or target.suffix in ('.py','.dylib'):
                skipped.append({'path':str(target),'reason':'Active dependency, open file or source code'});continue
            before=guarded(target)
            if before.st_size!=row['bytes'] or native.digest(target)!=group['sha256']:
                skipped.append({'path':str(target),'reason':'Target changed'});continue
            meta=native.metadata(target)
            temporary=target.parent/('.boldstone-storage-dedup-'+uuid.uuid4().hex)
            swapped=False;retired=False;clone_inode=None
            log({'phase':'dedup','status':'COW_INTENT','path':str(target),'keeper':str(keeper),'sha256':group['sha256'],'temporary':str(temporary),'original_identity':native.identity(before),'original_metadata':meta})
            try:
                native.clone_with_metadata(keeper,target,temporary)
                clone_inode=temporary.stat().st_ino
                if native.digest(temporary)!=group['sha256']:
                    raise RuntimeError('Clone content verification failed')
                clone_meta=native.metadata(temporary)
                if clone_meta!=meta:
                    # Some macOS managed access attributes are reapplied by
                    # the filesystem. Never weaken or discard them to dedup.
                    # The original has not been swapped and remains intact.
                    reason={'path':str(target),'reason':'Original retained: macOS metadata could not be preserved exactly',
                            'different_fields':[k for k in meta if meta[k]!=clone_meta[k]]}
                    skipped.append(reason)
                    temporary.unlink()
                    log({'phase':'dedup','status':'SKIPPED_ORIGINAL_UNCHANGED',**reason})
                    continue
                with temporary.open('rb') as f:os.fsync(f.fileno())
                identical_stat(target,before)
                if native.metadata(keeper)!=keeper_meta:
                    raise RuntimeError('Keeper metadata changed')
                native.swap(temporary,target);swapped=True
                log({'phase':'dedup','status':'COW_SWAPPED_OLD_RETAINED','path':str(target),'temporary':str(temporary),'new_inode':clone_inode})
                old=temporary.stat()
                if target.stat().st_ino!=clone_inode or native.metadata(target)!=meta or native.digest(target)!=group['sha256'] or (old.st_dev,old.st_ino,old.st_size,old.st_mtime_ns)!=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns):
                    raise RuntimeError('Post-swap readback failed')
                temporary.unlink();retired=True
                log({'phase':'dedup','status':'COW_VERIFIED_OLD_STORAGE_RETIRED','path':str(target),'keeper':str(keeper),'sha256':group['sha256'],'bytes':before.st_size})
                count+=1;logical+=before.st_size
            except BaseException:
                if swapped and not retired and temporary.exists():
                    if target.stat().st_ino!=clone_inode:
                        raise RuntimeError('Concurrent change: original inode retained at '+str(temporary))
                    native.swap(temporary,target)
                    log({'phase':'dedup','status':'ROLLED_BACK_ORIGINAL','path':str(target)})
                if temporary.exists():temporary.unlink()
                raise
            if time.monotonic()-last>15:
                print(json.dumps({'phase':'dedup','files_verified':count,'logical_duplicate_bytes':logical,'available':native.space()['available_bytes']}),flush=True);last=time.monotonic()
    result={'status':'PASS_PENDING_FULL_READBACK','cloned_files_this_run':count,'duplicate_logical_bytes_this_run':logical,'previously_completed':len(completed),'skipped':skipped,'all_duplicate_pathnames_retained':True,'hard_links_created':0,'space_after':native.space()}
    write_json(receipt,result)
    print(json.dumps({k:v for k,v in result.items() if k!='skipped'}),flush=True)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['exports','databases','dedup']);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:parser.error('Explicit --apply required')
    with (HERE/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not (HERE/'space-before.json').exists():write_json(HERE/'space-before.json',native.space())
        {'exports':archive_exports,'databases':archive_databases,'dedup':deduplicate}[args.phase]()

if __name__=='__main__':main()
