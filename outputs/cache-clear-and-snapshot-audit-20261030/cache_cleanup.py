"""Retire only verified, unused BoldstoneLocal image cache files.

Dropbox is read-only. Source retirement and restoration require --apply.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import argparse
import base64
import collections
import fcntl
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
import urllib.request
import uuid
import zipfile

ROOT = Path('/Users/tprice/Documents/boldstone')
HERE = Path(__file__).resolve().parent
CACHE = Path.home() / 'Library/Application Support/BoldstoneLocal/cache'
RUNTIME = Path.home() / 'Library/Application Support/BoldstoneReview'
HIST = ROOT / 'outputs/historical-image-archive-20261030'
sys.path.insert(0, str(HIST))
import archive_images as a
native = a.native
read, write, now, hashes = a.read, a.write, a.now, a.hashes


def emit(**data):
    print(json.dumps(data), flush=True)


def journal(kind, **data):
    with (HERE / 'cache-journal.jsonl').open('a') as f:
        f.write(json.dumps({'utc': now(), 'kind': kind, **data}) + '\n')
        f.flush(); os.fsync(f.fileno())


def open_paths():
    p = subprocess.run(['lsof', '-nP', '-Fn'], capture_output=True, text=True, timeout=45)
    if p.returncode not in (0, 1):
        raise RuntimeError('Open-file check failed')
    return {x[1:] for x in p.stdout.splitlines() if x.startswith('n/')}


def snapshot():
    with urllib.request.urlopen('http://127.0.0.1:8767/api/bootstrap', timeout=90) as response:
        boot = json.load(response)
    protected = a.fresh_dependencies()
    history = a.manifest()
    protected.update(b['keeper'] for b in history['blobs'].values() if b['storage'] == 'active-local')
    pointer = read(ROOT / 'sculpture-catalogue/current-master.json')
    immutable = {str(ROOT / 'sculpture-catalogue/current-master.json'), boot['source']['register'],
                 boot['source']['gallery_database']}
    for section in ('current_app_review_workbook', 'current_upload_preparation'):
        for key, value in pointer.get(section, {}).items():
            if isinstance(value, str) and value.startswith(str(ROOT) + '/') and Path(value).is_file():
                immutable.add(value)
    # Cache files used by the app and current publication sources must remain byte-identical.
    protected_files = sorted({p for p in protected if Path(p).is_relative_to(CACHE)} | immutable)
    rows = []
    for p in protected_files:
        path = Path(p)
        s = path.stat()
        rows.append({'path': p, 'bytes': s.st_size, 'mtime_ns': s.st_mtime_ns,
                     'sha256': native.digest(path)})
    with sqlite3.connect('file:' + str(RUNTIME / 'reviews.sqlite3') + '?mode=ro', uri=True) as db:
        cutoff = db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
        tables = {}
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            if name.startswith('sqlite_'): continue
            values = db.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall()
            tables[name] = {'rows': len(values), 'sha256': hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()}
    return {'utc': now(), 'protected_paths': sorted(protected), 'protected_files': rows,
            'source': boot['source'], 'event_cutoff': cutoff, 'tables': tables}


def image_file(path):
    with path.open('rb') as f: h = f.read(32)
    return (h.startswith((b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF87a', b'GIF89a', b'BM', b'II*\0', b'MM\0*'))
            or (h.startswith(b'RIFF') and h[8:12] == b'WEBP'))


def cloud_inventory(name):
    from delete_dropbox import connection
    from dropbox.files import FileMetadata
    from dropbox.exceptions import InternalServerError, RateLimitError
    from requests.exceptions import ConnectionError, Timeout
    def checked(call):
        for attempt in range(4):
            try:return call()
            except (ConnectionError,Timeout,InternalServerError,RateLimitError) as error:
                if attempt==3:raise
                delay=min(30,max(2**attempt,float(getattr(error,'backoff',0) or 0)))
                emit(phase='Retrying read-only Dropbox page',attempt=attempt+1,error=type(error).__name__,delay_seconds=delay)
                time.sleep(delay)
    files=[];pages=0
    with connection(ROOT) as (client,root):
        page=checked(lambda:client.files_list_folder(root,recursive=True,include_deleted=False,limit=2000))
        while True:
            pages+=1
            for m in page.entries:
                if not isinstance(m,FileMetadata):continue
                if not (m.path_display or '').casefold().startswith(root.casefold()+'/'):raise ValueError('Unexpected inventory scope')
                files.append({'id':m.id,'path':m.path_display,'revision':m.rev,'bytes':m.size,
                              'content_hash':m.content_hash,'downloadable':m.is_downloadable})
            if pages%5==0:emit(phase='Dropbox read-only inventory',pages=pages,files=len(files))
            if not page.has_more:break
            cursor=page.cursor
            page=checked(lambda:client.files_list_folder_continue(cursor))
    result={'checked_utc':now(),'root':root,'files':files,'cloud_mutations':0}
    write(HERE/name,result)
    return result


def prepare():
    if (HERE / 'cache-manifest.json').exists(): raise ValueError('Manifest already exists')
    if not (HERE/'space-before.json').exists():write(HERE / 'space-before.json', native.space())
    snap = read(HERE/'protected-before.json') if (HERE/'protected-before.json').exists() else snapshot()
    if not (HERE/'protected-before.json').exists():write(HERE / 'protected-before.json', snap)
    opened, protected = open_paths(), set(snap['protected_paths'])
    candidates, retained = [], []
    for directory, dirs, files in os.walk(CACHE, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if path.is_symlink() or not path.is_file(): continue
            if str(path) in protected:
                retained.append({'path': str(path), 'reason': 'Current app or retained archive dependency', 'bytes': path.stat().st_size}); continue
            if not image_file(path):
                retained.append({'path': str(path), 'reason': 'Not an image cache file', 'bytes': path.stat().st_size}); continue
            if str(path) in opened:
                retained.append({'path': str(path), 'reason': 'Open file', 'bytes': path.stat().st_size}); continue
            candidates.append(path)

    def inspect(path):
        s = path.lstat(); meta = native.metadata(path)
        if meta['acl'] or meta['xattrs'] or meta['flags']:
            return None, {'path': str(path), 'reason': 'Extended metadata retained in place', 'bytes': s.st_size}
        sha, dh, identity = hashes(path)
        return {'path': str(path), 'relative': str(path.relative_to(CACHE)), 'bytes': s.st_size,
                'sha256': sha, 'dropbox_content_hash': dh, 'identity': identity,
                'metadata': meta, 'atime_ns': s.st_atime_ns}, None

    records = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for index, (row, skip) in enumerate(pool.map(inspect, candidates), 1):
            if row: records.append(row)
            if skip: retained.append(skip)
            if index % 200 == 0: emit(phase='Cache images hashed', checked=index, total=len(candidates))
    cloud = read(HERE/'dropbox-current.json') if (HERE/'dropbox-current.json').exists() else cloud_inventory('dropbox-current.json')
    lookup = collections.defaultdict(list)
    for item in cloud['files']:
        if item['downloadable'] and item['content_hash']:
            lookup[(item['content_hash'], item['bytes'])].append(item)
    history = a.manifest()
    history_receipt = read(HIST / 'archive-verified.json')
    if native.digest(HIST / history['archive']) != history_receipt['archive_sha256']:
        raise ValueError('Existing historical archive changed')
    blobs = {}
    for row in records:
        sha = row['sha256']
        if sha in blobs: continue
        b = {k: row[k] for k in ('sha256', 'dropbox_content_hash', 'bytes')}
        b['source_path'] = row['path']
        if matches := lookup.get((b['dropbox_content_hash'], b['bytes'])):
            b.update(storage='dropbox', cloud=sorted(matches, key=lambda x: ('/Products/' not in x['path'], x['path']))[0])
        elif sha in history['blobs'] and history['blobs'][sha]['storage'] == 'archive':
            b.update(storage='existing-archive', archive=str(HIST / history['archive']),
                     member=history['blobs'][sha]['member'], archive_sha256=history_receipt['archive_sha256'])
        else:
            b.update(storage='archive', member='images/' + sha)
        blobs[sha] = b
    payload = {'schema': 'boldstone-unused-cache-retirement/v1', 'utc': now(), 'cache_root': str(CACHE),
               'authorization': 'User requested verification and clearing of originals outside current app references.',
               'records': records, 'blobs': blobs, 'retained': retained, 'archive': 'cache-originals.zip',
               'cloud_mutations': 0}
    write(HERE / 'cache-manifest.json', payload)
    write(HERE / 'cache-manifest.sha256.json', {'sha256': native.digest(HERE / 'cache-manifest.json')})
    emit(phase='Cache plan prepared', files=len(records), logical_GiB=sum(x['bytes'] for x in records)/2**30,
         distinct_contents=len(blobs), sources=dict(collections.Counter(b['storage'] for b in blobs.values())),
         new_archive_GiB=sum(b['bytes'] for b in blobs.values() if b['storage']=='archive')/2**30,
         retained=dict(collections.Counter(x['reason'] for x in retained)))


def manifest():
    if native.digest(HERE / 'cache-manifest.json') != read(HERE / 'cache-manifest.sha256.json')['sha256']:
        raise ValueError('Cache manifest changed')
    m = read(HERE / 'cache-manifest.json')
    if m['cache_root'] != str(CACHE): raise ValueError('Wrong cache root')
    return m


def amend_media_metadata():
    """Include restorable Mac attributes and the verified cached QuickTime original."""
    m=manifest()
    if (HERE/'cache-manifest-initial.json').exists():raise ValueError('Amendment already applied')
    if (HERE/'cache-archive-verified.json').exists():raise ValueError('Amend before archive verification')
    cloud=read(HERE/'dropbox-current.json')
    by_hash=collections.defaultdict(list)
    for r in cloud['files']:
        if r['downloadable']:by_hash[(r['content_hash'],r['bytes'])].append(r)
    history=a.manifest();history_receipt=read(HIST/'archive-verified.json')
    added=[];retained=[]
    for r in m['retained']:
        path=Path(r['path'])
        with path.open('rb') as f:h=f.read(24)
        video=(path.suffix=='.original' and h[4:8]==b'ftyp' and h[8:12]==b'qt  ')
        if r['reason']!='Extended metadata retained in place' and not (r['reason']=='Not an image cache file' and video):
            retained.append(r);continue
        meta=native.metadata(path)
        if meta['acl'] or meta['flags']:
            retained.append(r);continue
        attrs={os.fsdecode(k):base64.b64encode(v).decode('ascii') for k,v in native.xattrs(path).items()}
        # Verify every extended-attribute value can actually be re-created on this Mac.
        with tempfile.TemporaryDirectory(prefix='.metadata-probe-',dir=HERE) as td:
            probe=Path(td)/'probe';probe.write_bytes(b'')
            for key,value in attrs.items():
                raw=base64.b64decode(value)
                native.native(native.LIB.setxattr,os.fsencode(probe),os.fsencode(key),raw,len(raw),0,1)
            if native.metadata(probe)['xattrs']!=meta['xattrs']:raise ValueError('Attribute restoration failed')
        s=path.lstat();sha,dh,ident=hashes(path)
        row={'path':str(path),'relative':str(path.relative_to(CACHE)),'bytes':s.st_size,'sha256':sha,
             'dropbox_content_hash':dh,'identity':ident,'metadata':meta,'atime_ns':s.st_atime_ns,
             'xattrs_base64':attrs,'media_kind':'video' if video else 'image'}
        if sha not in m['blobs']:
            b={k:row[k] for k in ('sha256','dropbox_content_hash','bytes')};b['source_path']=str(path)
            matches=by_hash.get((dh,s.st_size),[])
            if matches:b.update(storage='dropbox',cloud=sorted(matches,key=lambda x:('/Products/' not in x['path'],x['path']))[0])
            elif sha in history['blobs'] and history['blobs'][sha]['storage']=='archive':
                b.update(storage='existing-archive',archive=str(HIST/history['archive']),member=history['blobs'][sha]['member'],archive_sha256=history_receipt['archive_sha256'])
            else:
                if video:raise ValueError('Cached video has no byte-identical Dropbox original')
                b.update(storage='archive',member='images/'+sha)
            m['blobs'][sha]=b
        m['records'].append(row);added.append(row)
    m['retained']=retained
    m['amendment']={'utc':now(),'reason':'Correct QuickTime media identification; preserve verified-restorable Mac metadata',
                    'files_added':len(added),'bytes_added':sum(r['bytes'] for r in added)}
    (HERE/'cache-manifest.json').rename(HERE/'cache-manifest-initial.json')
    (HERE/'cache-manifest.sha256.json').rename(HERE/'cache-manifest-initial.sha256.json')
    write(HERE/'cache-manifest.json',m)
    write(HERE/'cache-manifest.sha256.json',{'sha256':native.digest(HERE/'cache-manifest.json')})
    emit(phase='Cache plan extended after metadata restoration tests',files=len(m['records']),
         logical_GiB=sum(r['bytes'] for r in m['records'])/2**30,
         sources=dict(collections.Counter(b['storage'] for b in m['blobs'].values())),
         new_archive_GiB=sum(b['bytes'] for b in m['blobs'].values() if b['storage']=='archive')/2**30)


def archive_and_verify():
    m = manifest(); target = HERE / m['archive']
    new = [b for b in m['blobs'].values() if b['storage'] == 'archive']
    if new:
        partial = target.with_suffix('.zip.partial')
        with zipfile.ZipFile(partial, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
            z.writestr('manifest.json', (HERE / 'cache-manifest.json').read_bytes())
            for i, b in enumerate(new, 1):
                if native.digest(Path(b['source_path'])) != b['sha256']: raise ValueError('Archive source changed')
                z.write(b['source_path'], b['member'])
                if i % 100 == 0: emit(phase='Archiving cache-only originals', images=i, total=len(new))
        with partial.open('rb') as stream: os.fsync(stream.fileno())
        partial.rename(target)
    checks = []
    archived = [b for b in m['blobs'].values() if b['storage'] in ('archive', 'existing-archive')]
    with tempfile.TemporaryDirectory(prefix='.restore-check-', dir=HERE) as td:
        for i, b in enumerate(archived, 1):
            archive_path = target if b['storage']=='archive' else Path(b['archive'])
            dest = Path(td) / b['sha256']
            with zipfile.ZipFile(archive_path) as z, z.open(b['member']) as source, dest.open('xb') as out:
                shutil.copyfileobj(source, out, 2*1024*1024)
            sha, dh, ident = hashes(dest)
            if (sha, dh, ident[2]) != (b['sha256'], b['dropbox_content_hash'], b['bytes']):
                raise ValueError('Archive restore differs')
            dest.unlink(); checks.append(sha)
            if i % 100 == 0: emit(phase='Cache archive restore verified', images=i, total=len(archived))
    write(HERE / 'cache-archive-verified.json', {'status': 'PASS', 'utc': now(), 'restored_contents': checks,
          'new_archive_bytes': target.stat().st_size if new else 0,
          'new_archive_sha256': native.digest(target) if new else None})
    emit(phase='Archive restoration passed', restored=len(checks), new_archive_GiB=(target.stat().st_size if new else 0)/2**30)


def eligible(row, blob, protected, opened, cloud):
    path = Path(row['path'])
    if not path.is_relative_to(CACHE) or path.resolve() != path or path.is_symlink(): return 'Noncanonical or out-of-scope path'
    if str(path) in protected | opened: return 'New active dependency or open file'
    if not path.exists() or native.identity(path.lstat()) != row['identity']: return 'Local file changed'
    if blob['storage']=='dropbox':
        live = cloud.get(blob['cloud']['id'])
        if not live or (live['id'],live['revision'],live['content_hash'],live['bytes'],live['downloadable']) != (blob['cloud']['id'],blob['cloud']['revision'],blob['dropbox_content_hash'],blob['bytes'],True):
            return 'Dropbox original changed or unavailable'
    return None


def retire(apply=False):
    if not apply: raise ValueError('Retirement requires --apply')
    m = manifest(); v = read(HERE / 'cache-archive-verified.json')
    if v['status'] != 'PASS': raise ValueError('Archive verification missing')
    if v['new_archive_sha256'] and native.digest(HERE/m['archive']) != v['new_archive_sha256']:
        raise ValueError('New archive changed')
    for b in m['blobs'].values():
        if b['storage']=='existing-archive':
            if native.digest(Path(b['archive'])) != b['archive_sha256']: raise ValueError('Existing archive changed')
            break
    with (RUNTIME / 'native-jobs/writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cloud = cloud_inventory('dropbox-before-cache-removal.json')
        current = {r['id']:r for r in cloud['files']}
        protected, opened = a.fresh_dependencies(), open_paths()
        protected.update(b['keeper'] for b in a.manifest()['blobs'].values() if b['storage']=='active-local')
        plan, skipped = [], []
        for row in m['records']:
            reason = eligible(row,m['blobs'][row['sha256']],protected,opened,current)
            if reason: skipped.append({'path':row['path'],'reason':reason})
            else: plan.append(row)
        write(HERE/'cache-retirement-plan.json',{'utc':now(),'paths':[r['path'] for r in plan],'skipped':skipped})
        for i,row in enumerate(plan,1):
            path=Path(row['path']);sha,dh,ident=hashes(path)
            if (sha,dh,ident)!=(row['sha256'],row['dropbox_content_hash'],row['identity']): raise ValueError('Cache source changed during retirement')
            journal('VERIFIED_CACHE_RETIREMENT_INTENT',path=row['path'],sha256=sha,source=m['blobs'][sha]['storage'])
            path.unlink()
            journal('CACHE_COPY_REMOVED',path=row['path'],sha256=sha,bytes=row['bytes'])
            if i % 200==0:emit(phase='Verified unused cache files removed',files=i,total=len(plan))
    write(HERE/'cache-retirement-complete.json',{'status':'PASS','utc':now(),'files':len(plan),
          'logical_bytes_removed':sum(r['bytes'] for r in plan),'skipped':skipped,'space_after':native.space(),'cloud_mutations':0})
    emit(phase='Cache retirement completed',files=len(plan),skipped=len(skipped))


def data_for(blob,m,client=None):
    if blob['storage'] in ('archive','existing-archive'):
        path=HERE/m['archive'] if blob['storage']=='archive' else Path(blob['archive'])
        with zipfile.ZipFile(path) as z: data=z.read(blob['member'])
    elif blob['storage']=='dropbox':
        if client is None:
            from delete_dropbox import connection
            with connection(ROOT) as (client,_):return data_for(blob,m,client)
        meta,response=client.files_download('rev:'+blob['cloud']['revision'])
        with closing(response):
            if (meta.id,meta.rev,meta.content_hash,meta.size)!=(blob['cloud']['id'],blob['cloud']['revision'],blob['dropbox_content_hash'],blob['bytes']):
                raise ValueError('Dropbox source differs')
            data=response.content
    else: raise ValueError('Unsupported source')
    if len(data)!=blob['bytes'] or hashlib.sha256(data).hexdigest()!=blob['sha256']:raise ValueError('Restored content differs')
    return data


def write_restored(blob,m,destination,client=None):
    """Stream originals so restoring a multi-gigabyte video does not fill RAM."""
    if blob['storage'] in ('archive','existing-archive'):
        path=HERE/m['archive'] if blob['storage']=='archive' else Path(blob['archive'])
        with zipfile.ZipFile(path) as z,z.open(blob['member']) as source,destination.open('xb') as out:
            shutil.copyfileobj(source,out,2*1024*1024);out.flush();os.fsync(out.fileno())
    elif blob['storage']=='dropbox':
        if client is None:
            from delete_dropbox import connection
            with connection(ROOT) as (client,_):return write_restored(blob,m,destination,client)
        meta,response=client.files_download('rev:'+blob['cloud']['revision'])
        with closing(response):
            if (meta.id,meta.rev,meta.content_hash,meta.size)!=(blob['cloud']['id'],blob['cloud']['revision'],blob['dropbox_content_hash'],blob['bytes']):
                raise ValueError('Dropbox source differs')
            with destination.open('xb') as out:
                for chunk in response.iter_content(2*1024*1024):out.write(chunk)
                out.flush();os.fsync(out.fileno())
    else:raise ValueError('Unsupported source')
    sha,dh,ident=hashes(destination)
    if (sha,dh,ident[2])!=(blob['sha256'],blob['dropbox_content_hash'],blob['bytes']):raise ValueError('Restored content differs')


def restore(path,destination=None,apply=False):
    m=manifest();row=next(r for r in m['records'] if r['path']==path or r['relative']==path)
    dest=Path(destination or row['path'])
    if dest.exists() or dest.is_symlink():raise FileExistsError('Restore never overwrites an existing path')
    if not apply:emit(action='restore',path=str(dest),sha256=row['sha256']);return
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_name('.cache-restore-'+uuid.uuid4().hex)
    try:
        write_restored(m['blobs'][row['sha256']],m,temp)
        meta=row['metadata']
        if meta['acl'] or meta['flags']:raise ValueError('Unsupported extended metadata')
        for key,value in row.get('xattrs_base64',{}).items():
            raw=base64.b64decode(value)
            native.native(native.LIB.setxattr,os.fsencode(temp),os.fsencode(key),raw,len(raw),0,1)
        os.chmod(temp,stat.S_IMODE(meta['mode']));os.chown(temp,meta['uid'],meta['gid'])
        os.utime(temp,ns=(row['atime_ns'],meta['mtime_ns']))
        native.creation_time(temp,meta['birthtime_ns'])
        if native.digest(temp)!=row['sha256'] or native.metadata(temp)!=meta:raise ValueError('Restore identity differs')
        native.native(native.LIB.renamex_np,os.fsencode(temp),os.fsencode(dest),4)
    finally:temp.unlink(missing_ok=True)
    emit(status='RESTORED',path=str(dest))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','amend','archive','retire','restore'])
    p.add_argument('path',nargs='?');p.add_argument('--apply',action='store_true');p.add_argument('--destination')
    args=p.parse_args()
    with (HERE/'cache-cleanup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='prepare':prepare()
        elif args.action=='amend':amend_media_metadata()
        elif args.action=='archive':archive_and_verify()
        elif args.action=='retire':retire(args.apply)
        else:restore(args.path,args.destination,args.apply)
